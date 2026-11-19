"""AP-M9-W3 environment-profile and lifecycle-contract checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from contracts.lifecycle import (
    PROFILE_DIRECTORY,
    load_lifecycle_document,
    load_lifecycle_schemas,
    validate_lifecycle_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_FILES = {
    "production.v1.json": "production",
    "staging.v1.json": "staging",
}
ENVIRONMENT_PROFILE_SCHEMA_ID = (
    "urn:comfforts:app-platform:lifecycle:environment-profile:v1"
)


def _profile(name: str) -> dict[str, object]:
    value = json.loads((PROFILE_DIRECTORY / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _codes(violations: object) -> list[tuple[str, str]]:
    return [(item.code, item.path) for item in violations]  # type: ignore[attr-defined]


class EnvironmentProfileContractTest(unittest.TestCase):
    def test_environment_profile_schema_registry_is_local_and_closed(self) -> None:
        registry = load_lifecycle_schemas()

        self.assertEqual(set(registry), {ENVIRONMENT_PROFILE_SCHEMA_ID})

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


if __name__ == "__main__":
    unittest.main()
