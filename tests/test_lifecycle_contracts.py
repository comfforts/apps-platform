"""AP-M9-W3 environment-profile and lifecycle-contract checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from contracts.lifecycle import (
    PROFILE_DIRECTORY,
    canonical_lifecycle_bytes,
    lifecycle_digest,
    load_lifecycle_document,
    load_lifecycle_schemas,
    validate_lifecycle_document,
    validate_lifecycle_relationships,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_FILES = {
    "production.v1.json": "production",
    "staging.v1.json": "staging",
}
ENVIRONMENT_PROFILE_SCHEMA_ID = (
    "urn:comfforts:app-platform:lifecycle:environment-profile:v1"
)
DEPLOYMENT_SPECIFICATION_SCHEMA_ID = (
    "urn:comfforts:app-platform:lifecycle:deployment-specification:v1"
)
EXECUTION_JOURNAL_SCHEMA_ID = (
    "urn:comfforts:app-platform:lifecycle:execution-journal:v1"
)


def _profile(name: str) -> dict[str, object]:
    value = json.loads((PROFILE_DIRECTORY / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _codes(violations: object) -> list[tuple[str, str]]:
    return [(item.code, item.path) for item in violations]  # type: ignore[attr-defined]


def _digest(character: str) -> str:
    return f"sha256:{character * 64}"


def _specification() -> dict[str, object]:
    return {
        "contract_version": 1,
        "document_kind": "deployment-specification",
        "environment": "staging",
        "operation": "deploy",
        "profile_digest": _digest("1"),
        "source": {
            "repository": "comfforts/apps-platform",
            "revision": "a" * 40,
        },
        "stages": [
            {
                "stage_id": "preflight",
                "actions": ["read"],
                "resource_types": ["environment-profile", "source"],
                "consumes": [],
                "produces": ["preflight-attestation"],
                "manual_checkpoint": "none",
                "readback": "provider-verified",
            },
            {
                "stage_id": "foundation",
                "actions": ["create", "read"],
                "resource_types": ["platform-foundation"],
                "consumes": [
                    {
                        "stage_id": "preflight",
                        "output_name": "preflight-attestation",
                    }
                ],
                "produces": ["reserved-address"],
                "manual_checkpoint": "none",
                "readback": "provider-verified",
            },
            {
                "stage_id": "external-dns",
                "actions": ["create", "read"],
                "resource_types": ["dns-a-record"],
                "consumes": [
                    {
                        "stage_id": "foundation",
                        "output_name": "reserved-address",
                    }
                ],
                "produces": ["dns-attestation"],
                "manual_checkpoint": "external-dns",
                "readback": "provider-verified",
            },
        ],
        "failure_behavior": "stop",
        "destructive_boundary": {
            "allowed": False,
            "resource_types": [],
        },
    }


def _journal(specification: dict[str, object]) -> dict[str, object]:
    return {
        "contract_version": 1,
        "document_kind": "execution-journal",
        "environment": "staging",
        "operation": "deploy",
        "source_revision": "a" * 40,
        "specification_digest": lifecycle_digest(
            specification,
            "deployment-specification",
        ),
        "journal_revision": 1,
        "previous_journal_digest": None,
        "status": "running",
        "entries": [
            {
                "sequence": 1,
                "stage_id": "preflight",
                "stage_input_digest": _digest("2"),
                "outcome": "succeeded",
                "plan_digest": None,
                "outputs": [
                    {
                        "name": "preflight-attestation",
                        "value": "verified",
                    }
                ],
                "manual_acknowledgement": "not-required",
            }
        ],
    }


class EnvironmentProfileContractTest(unittest.TestCase):
    def test_environment_profile_schema_registry_is_local_and_closed(self) -> None:
        registry = load_lifecycle_schemas()

        self.assertEqual(
            set(registry),
            {
                ENVIRONMENT_PROFILE_SCHEMA_ID,
                DEPLOYMENT_SPECIFICATION_SCHEMA_ID,
                EXECUTION_JOURNAL_SCHEMA_ID,
            },
        )

    def test_exact_committed_profiles_load_as_canonical_documents(self) -> None:
        self.assertEqual(
            sorted(path.name for path in PROFILE_DIRECTORY.glob("*.json")),
            sorted(PROFILE_FILES),
        )

        for filename, environment in PROFILE_FILES.items():
            with self.subTest(filename=filename):
                loaded = load_lifecycle_document(
                    PROFILE_DIRECTORY / filename,
                    "environment-profile",
                )

                self.assertEqual(loaded.violations, ())
                self.assertIsNotNone(loaded.value)
                assert loaded.value is not None
                self.assertEqual(loaded.value["environment"], environment)
                self.assertEqual(
                    loaded.canonical_bytes,
                    (PROFILE_DIRECTORY / filename).read_bytes().removesuffix(b"\n"),
                )
                self.assertRegex(loaded.digest or "", r"^sha256:[0-9a-f]{64}$")

    def test_staging_profile_contains_only_reviewed_stable_owner_decisions(self) -> None:
        staging = _profile("staging.v1.json")

        self.assertEqual(
            staging,
            {
                "contract_version": 1,
                "document_kind": "environment-profile",
                "environment": "staging",
                "lifecycle_state": "enabled",
                "provider_class": "gcp-v1",
                "dns_provider_class": "squarespace-v1",
                "project_id": "comfforts-platform-non-prod",
                "project_number": "455651441682",
                "region": "us-west1",
                "hostname": "apps-staging.comfforts.com",
            },
        )

    def test_production_profile_is_distinct_and_disabled_for_ownership_transfer(self) -> None:
        production = _profile("production.v1.json")

        self.assertEqual(
            production,
            {
                "contract_version": 1,
                "document_kind": "environment-profile",
                "environment": "production",
                "lifecycle_state": "disabled",
                "provider_class": "gcp-v1",
                "dns_provider_class": "squarespace-v1",
                "hostname": "apps.comfforts.com",
                "blockers": ["OWNERSHIP_TRANSFER_REQUIRED"],
            },
        )

    def test_profile_rejects_unknown_generated_placeholder_and_cross_environment_values(self) -> None:
        staging = _profile("staging.v1.json")
        cases = {
            "unknown generated address": ("reserved_address", "203.0.113.4", "/reserved_address"),
            "placeholder project": ("project_id", "REPLACE_ME", "/project_id"),
            "production hostname": ("hostname", "apps.comfforts.com", "/hostname"),
            "secret material": ("oauth_client_secret", "not-a-secret", "/oauth_client_secret"),
            "state material": ("terraform_state", "state", "/terraform_state"),
            "plan material": ("saved_plan", "plan", "/saved_plan"),
            "provider material": ("provider_response", "response", "/provider_response"),
        }

        for label, (field, value, path) in cases.items():
            with self.subTest(label=label):
                candidate = copy.deepcopy(staging)
                candidate[field] = value
                violations = validate_lifecycle_document(candidate, "environment-profile")

                self.assertIn(path, {item.path for item in violations})

    def test_noncanonical_profile_bytes_are_rejected(self) -> None:
        staging = _profile("staging.v1.json")
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "staging.json"
            path.write_text(json.dumps(staging, indent=2), encoding="utf-8")

            loaded = load_lifecycle_document(path, "environment-profile")

        self.assertIsNone(loaded.value)
        self.assertIn(("DOCUMENT_NOT_CANONICAL", ""), _codes(loaded.violations))


class SpecificationAndJournalContractTest(unittest.TestCase):
    def test_complete_specification_is_canonical_and_digest_bound(self) -> None:
        specification = _specification()

        self.assertEqual(
            validate_lifecycle_document(specification, "deployment-specification"),
            (),
        )
        self.assertEqual(
            canonical_lifecycle_bytes(specification, "deployment-specification"),
            canonical_lifecycle_bytes(
                {key: specification[key] for key in reversed(specification)},
                "deployment-specification",
            ),
        )
        self.assertEqual(
            lifecycle_digest(specification, "deployment-specification"),
            "sha256:9a0b560a920e9366d50ab1aa47a29d56e5ff541e5375e8549081627876282806",
        )

    def test_specification_requires_complete_prior_stage_output_bindings(self) -> None:
        cases: dict[str, tuple[dict[str, object], str]] = {}

        missing_output = _specification()
        stages = missing_output["stages"]
        assert isinstance(stages, list)
        foundation = stages[1]
        assert isinstance(foundation, dict)
        consumes = foundation["consumes"]
        assert isinstance(consumes, list)
        binding = consumes[0]
        assert isinstance(binding, dict)
        binding["output_name"] = "undeclared-output"
        cases["undeclared output"] = (
            missing_output,
            "/stages/1/consumes/0/output_name",
        )

        later_stage = _specification()
        stages = later_stage["stages"]
        assert isinstance(stages, list)
        foundation = stages[1]
        assert isinstance(foundation, dict)
        consumes = foundation["consumes"]
        assert isinstance(consumes, list)
        binding = consumes[0]
        assert isinstance(binding, dict)
        binding["stage_id"] = "external-dns"
        binding["output_name"] = "dns-attestation"
        cases["later output"] = (later_stage, "/stages/1/consumes/0/stage_id")

        duplicate_stage = _specification()
        stages = duplicate_stage["stages"]
        assert isinstance(stages, list)
        stage = stages[2]
        assert isinstance(stage, dict)
        stage["stage_id"] = "foundation"
        cases["duplicate stage"] = (duplicate_stage, "/stages/2/stage_id")

        for label, (candidate, expected_path) in cases.items():
            with self.subTest(label=label):
                violations = validate_lifecycle_document(
                    candidate,
                    "deployment-specification",
                )

                self.assertIn(expected_path, {item.path for item in violations})

    def test_deploy_specification_cannot_expand_into_destructive_scope(self) -> None:
        specification = _specification()
        boundary = specification["destructive_boundary"]
        assert isinstance(boundary, dict)
        boundary["allowed"] = True
        boundary["resource_types"] = ["platform-foundation"]

        violations = validate_lifecycle_document(
            specification,
            "deployment-specification",
        )

        self.assertIn(
            ("DESTRUCTIVE_BOUNDARY_INVALID", "/destructive_boundary/allowed"),
            _codes(violations),
        )

    def test_generated_journal_is_bound_to_the_exact_specification(self) -> None:
        specification = _specification()
        journal = _journal(specification)

        self.assertEqual(validate_lifecycle_document(journal, "execution-journal"), ())
        self.assertEqual(
            validate_lifecycle_relationships(
                specification=specification,
                journal=journal,
            ),
            (),
        )

        stale = copy.deepcopy(journal)
        stale["specification_digest"] = _digest("f")
        self.assertIn(
            ("DIGEST_MISMATCH", "/journal/specification_digest"),
            _codes(
                validate_lifecycle_relationships(
                    specification=specification,
                    journal=stale,
                )
            ),
        )

    def test_journal_revision_is_append_only_and_digest_chained(self) -> None:
        specification = _specification()
        previous = _journal(specification)
        current = copy.deepcopy(previous)
        current["journal_revision"] = 2
        current["previous_journal_digest"] = lifecycle_digest(
            previous,
            "execution-journal",
        )
        entries = current["entries"]
        assert isinstance(entries, list)
        entries.append(
            {
                "sequence": 2,
                "stage_id": "foundation",
                "stage_input_digest": _digest("3"),
                "outcome": "waiting",
                "plan_digest": _digest("4"),
                "outputs": [],
                "manual_acknowledgement": "not-required",
            }
        )
        current["status"] = "waiting"

        self.assertEqual(
            validate_lifecycle_relationships(
                specification=specification,
                journal=current,
                previous_journal=previous,
            ),
            (),
        )

        rewritten = copy.deepcopy(current)
        rewritten_entries = rewritten["entries"]
        assert isinstance(rewritten_entries, list)
        first = rewritten_entries[0]
        assert isinstance(first, dict)
        first["outcome"] = "failed"
        self.assertIn(
            ("JOURNAL_NOT_APPEND_ONLY", "/journal/entries/0"),
            _codes(
                validate_lifecycle_relationships(
                    specification=specification,
                    journal=rewritten,
                    previous_journal=previous,
                )
            ),
        )

    def test_journal_cannot_record_undeclared_stage_or_output(self) -> None:
        specification = _specification()
        journal = _journal(specification)
        entries = journal["entries"]
        assert isinstance(entries, list)
        entry = entries[0]
        assert isinstance(entry, dict)
        entry["stage_id"] = "unapproved-stage"
        outputs = entry["outputs"]
        assert isinstance(outputs, list)
        output = outputs[0]
        assert isinstance(output, dict)
        output["name"] = "unapproved-output"

        violations = validate_lifecycle_relationships(
            specification=specification,
            journal=journal,
        )

        self.assertIn(
            ("SCOPE_EXPANSION", "/journal/entries/0/stage_id"),
            _codes(violations),
        )
        self.assertIn(
            ("SCOPE_EXPANSION", "/journal/entries/0/outputs/0/name"),
            _codes(violations),
        )


if __name__ == "__main__":
    unittest.main()
