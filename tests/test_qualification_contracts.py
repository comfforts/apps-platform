"""AP-M9-W8 strict qualification-evidence contract tests."""

from __future__ import annotations

import copy
import unittest

from contracts.lifecycle import (
    canonical_lifecycle_bytes,
    lifecycle_digest,
    load_lifecycle_schemas,
    validate_lifecycle_document,
)


QUALIFICATION_EVIDENCE_SCHEMA_ID = (
    "urn:comfforts:app-platform:lifecycle:qualification-evidence:v1"
)
SOURCE_REVISION = "a" * 40


def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


def qualification_evidence() -> dict[str, object]:
    checks = (
        ("admission-identity", "runtime-verified"),
        ("assertion-jwks", "runtime-verified"),
        ("attachment-posture", "provider-verified"),
        ("catalogue-routing", "runtime-verified"),
        ("direct-origin-denial", "runtime-verified"),
        ("dns-tls", "provider-verified"),
        ("isolation-limits", "runtime-verified"),
        ("lifecycle-rollback", "runtime-verified"),
        ("redaction", "deterministic"),
        ("source-integrity", "provider-verified"),
    )
    fixtures = (
        "fixture-authenticated",
        "fixture-public",
        "fixture-restricted",
    )
    return {
        "contract_version": 1,
        "document_kind": "qualification-evidence",
        "environment": "staging",
        "source_authority": "accepted",
        "source_revision": SOURCE_REVISION,
        "profile_digest": _digest("1"),
        "specification_digest": _digest("2"),
        "deployment_progress_digest": _digest("3"),
        "registration_generation_digest": _digest("4"),
        "component_revisions": [
            {"name": "registration-compiler", "digest": _digest("5")},
            {"name": "shared-edge-image", "digest": _digest("6")},
            {"name": "shared-edge-runtime", "digest": _digest("7")},
        ],
        "fixture_revisions": [
            {
                "application_id": application_id,
                "application_source_revision": character * 40,
                "integration_bundle_digest": _digest(character),
                "attachment_bundle_digest": _digest(
                    {"b": "e", "c": "f", "d": "8"}[character]
                ),
            }
            for application_id, character in zip(fixtures, ("b", "c", "d"))
        ],
        "checks": [
            {
                "check_id": check_id,
                "outcome": "pass",
                "verification": verification,
                "evidence_digest": _digest(hex(index)[2:]),
                "blockers": [],
            }
            for index, (check_id, verification) in enumerate(checks, start=1)
        ],
        "limitations": ["DISTRIBUTED_REPLAY_PREVENTION_UNAVAILABLE"],
        "verdict": "qualified",
    }


class QualificationEvidenceContractTest(unittest.TestCase):
    def test_registry_exposes_strict_qualification_evidence_contract(self) -> None:
        registry = load_lifecycle_schemas()

        self.assertIn(QUALIFICATION_EVIDENCE_SCHEMA_ID, registry)
        self.assertEqual(
            validate_lifecycle_document(
                qualification_evidence(),
                "qualification-evidence",
            ),
            (),
        )

    def test_canonical_evidence_digest_is_stable(self) -> None:
        evidence = qualification_evidence()

        self.assertEqual(
            canonical_lifecycle_bytes(evidence, "qualification-evidence"),
            canonical_lifecycle_bytes(
                {key: evidence[key] for key in reversed(evidence)},
                "qualification-evidence",
            ),
        )
        self.assertRegex(
            lifecycle_digest(evidence, "qualification-evidence"),
            r"^sha256:[0-9a-f]{64}$",
        )

    def test_qualified_verdict_requires_complete_passing_fixture_evidence(self) -> None:
        cases: dict[str, tuple[dict[str, object], tuple[str, str]]] = {}

        missing_check = qualification_evidence()
        checks = missing_check["checks"]
        assert isinstance(checks, list)
        checks.pop()
        cases["missing check"] = (
            missing_check,
            ("QUALIFICATION_CHECKS_INCOMPLETE", "/checks"),
        )

        failed_check = qualification_evidence()
        checks = failed_check["checks"]
        assert isinstance(checks, list)
        check = checks[0]
        assert isinstance(check, dict)
        check["outcome"] = "fail"
        check["blockers"] = ["IDENTITY_MISMATCH"]
        cases["failed check"] = (
            failed_check,
            ("QUALIFICATION_VERDICT_INVALID", "/verdict"),
        )

        missing_fixture = qualification_evidence()
        fixtures = missing_fixture["fixture_revisions"]
        assert isinstance(fixtures, list)
        fixtures.pop()
        cases["missing fixture"] = (
            missing_fixture,
            ("QUALIFICATION_FIXTURES_INCOMPLETE", "/fixture_revisions"),
        )

        operator_attested = qualification_evidence()
        checks = operator_attested["checks"]
        assert isinstance(checks, list)
        check = checks[0]
        assert isinstance(check, dict)
        check["verification"] = "operator-attested"
        cases["attestation substituted"] = (
            operator_attested,
            ("QUALIFICATION_VERIFICATION_INVALID", "/checks/0/verification"),
        )

        for label, (candidate, expected) in cases.items():
            with self.subTest(label=label):
                violations = validate_lifecycle_document(
                    candidate,
                    "qualification-evidence",
                )
                self.assertIn(
                    expected,
                    [(item.code, item.path) for item in violations],
                )

    def test_evidence_rejects_prohibited_operational_and_application_material(self) -> None:
        prohibited = (
            "assertion",
            "browser_state",
            "oauth_client_secret",
            "provider_response",
            "recovery_material",
            "request_body",
            "response_body",
            "restricted_members",
            "saved_plan",
            "session",
            "terraform_state",
        )

        for field in prohibited:
            with self.subTest(field=field):
                candidate = copy.deepcopy(qualification_evidence())
                candidate[field] = "must-not-be-retained"
                violations = validate_lifecycle_document(
                    candidate,
                    "qualification-evidence",
                )
                self.assertIn(
                    ("PROHIBITED_MATERIAL", f"/{field}"),
                    [(item.code, item.path) for item in violations],
                )


if __name__ == "__main__":
    unittest.main()
