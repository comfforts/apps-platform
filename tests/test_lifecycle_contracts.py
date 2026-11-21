"""Focused tests for the cross-owner lifecycle contracts."""

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
    validate_lifecycle_material,
    validate_lifecycle_relationships,
)


ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "contracts" / "lifecycle" / "test-vectors" / "valid"


def _vector(name: str) -> dict[str, object]:
    value = json.loads((VECTORS / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class LifecycleContractTest(unittest.TestCase):
    def test_registry_contains_only_owned_cross_boundary_documents(self) -> None:
        registry = load_lifecycle_schemas()

        self.assertEqual(
            set(registry),
            {
                "urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v1",
                "urn:comfforts:app-platform:lifecycle:deployment-specification:v1",
                "urn:comfforts:app-platform:lifecycle:environment-profile:v1",
                "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1",
                "urn:comfforts:app-platform:lifecycle:qualification-evidence:v1",
            },
        )

    def test_profiles_and_valid_vectors_are_canonical(self) -> None:
        cases = (
            (PROFILE_DIRECTORY / "staging.v1.json", "environment-profile"),
            (PROFILE_DIRECTORY / "production.v1.json", "environment-profile"),
            (
                VECTORS / "platform-integration-bundle.staging.synthetic.v1.json",
                "platform-integration-bundle",
            ),
            (
                VECTORS / "application-attachment-bundle.staging.synthetic.v1.json",
                "application-attachment-bundle",
            ),
            (
                VECTORS / "qualification-evidence.staging.synthetic.v1.json",
                "qualification-evidence",
            ),
        )
        for path, kind in cases:
            with self.subTest(path=path.name):
                loaded = load_lifecycle_document(path, kind)
                self.assertEqual(loaded.violations, ())
                self.assertIsNotNone(loaded.digest)

    def test_canonical_bytes_and_digest_are_stable(self) -> None:
        bundle = _vector("platform-integration-bundle.staging.synthetic.v1.json")
        canonical = canonical_lifecycle_bytes(bundle, "platform-integration-bundle")

        self.assertEqual(canonical, canonical.strip())
        self.assertRegex(
            lifecycle_digest(bundle, "platform-integration-bundle"),
            r"^sha256:[0-9a-f]{64}$",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.json"
            path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            loaded = load_lifecycle_document(path, "platform-integration-bundle")
        self.assertEqual(
            [(item.code, item.path) for item in loaded.violations],
            [("DOCUMENT_NOT_CANONICAL", "")],
        )

    def test_secret_state_plan_and_placeholder_material_are_rejected(self) -> None:
        for value in (
            {"oauth_client_secret": "value"},
            {"state": "thing.tfstate"},
            {"plan": "change.tfplan"},
            {"token": "ya29.private"},
            {"value": "REPLACE_ME"},
        ):
            with self.subTest(value=value):
                self.assertTrue(validate_lifecycle_material(value))

    def test_integration_bundle_is_least_data_and_environment_bound(self) -> None:
        bundle = _vector("platform-integration-bundle.staging.synthetic.v1.json")
        self.assertEqual(
            validate_lifecycle_document(bundle, "platform-integration-bundle"),
            (),
        )
        public = copy.deepcopy(bundle)
        public["access_mode"] = "public"
        public["identity"]["oauth_client_id"] = None  # type: ignore[index]
        public["identity"]["audience"] = None  # type: ignore[index]
        public["endpoints"]["issuer"] = None  # type: ignore[index]
        public["endpoints"]["jwks_uri"] = None  # type: ignore[index]
        public["endpoints"]["oauth_redirect_uri"] = None  # type: ignore[index]
        self.assertEqual(
            validate_lifecycle_document(public, "platform-integration-bundle"),
            (),
        )

        wrong = copy.deepcopy(bundle)
        wrong["endpoints"]["external_origin"] = "https://apps.comfforts.com"  # type: ignore[index]
        self.assertIn(
            "ENVIRONMENT_BINDING_INVALID",
            {item.code for item in validate_lifecycle_document(
                wrong, "platform-integration-bundle"
            )},
        )

    def test_attachment_must_bind_exact_bundle_owner_and_posture(self) -> None:
        bundle = _vector("platform-integration-bundle.staging.synthetic.v1.json")
        attachment = _vector(
            "application-attachment-bundle.staging.synthetic.v1.json"
        )
        attachment["platform_integration_bundle_digest"] = lifecycle_digest(
            bundle,
            "platform-integration-bundle",
        )
        self.assertEqual(
            validate_lifecycle_relationships(
                integration_bundle=bundle,
                attachment_bundle=attachment,
            ),
            (),
        )

        stale = copy.deepcopy(attachment)
        stale["platform_integration_bundle_digest"] = "sha256:" + "f" * 64
        self.assertIn(
            "DIGEST_MISMATCH",
            {item.code for item in validate_lifecycle_relationships(
                integration_bundle=bundle,
                attachment_bundle=stale,
            )},
        )

    def test_qualification_completeness_fails_closed(self) -> None:
        evidence = _vector("qualification-evidence.staging.synthetic.v1.json")
        incomplete = copy.deepcopy(evidence)
        incomplete["checks"] = incomplete["checks"][:-1]  # type: ignore[index]
        self.assertIn(
            "QUALIFICATION_CHECKS_INCOMPLETE",
            {item.code for item in validate_lifecycle_document(
                incomplete, "qualification-evidence"
            )},
        )


if __name__ == "__main__":
    unittest.main()
