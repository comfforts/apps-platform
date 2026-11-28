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
    load_versioned_lifecycle_document,
    validate_versioned_lifecycle_document,
    validate_versioned_lifecycle_relationships,
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
                "urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v2",
                "urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v3",
                "urn:comfforts:app-platform:lifecycle:deployment-specification:v1",
                "urn:comfforts:app-platform:lifecycle:environment-profile:v1",
                "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1",
                "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v2",
                "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v3",
                "urn:comfforts:app-platform:lifecycle:qualification-evidence:v1",
                "urn:comfforts:app-platform:lifecycle:registration-intent:v2",
                "urn:comfforts:app-platform:lifecycle:registration-intent:v3",
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

    def test_v3_root_only_and_multi_attachment_families_are_valid(self) -> None:
        integration = _vector(
            "platform-integration-bundle.staging.synthetic.v3.json"
        )
        self.assertEqual(
            integration["attachment_contract"],
            {
                "adapter_kind": "gcp-cloud-run-v1",
                "ingress_mode": "shared_edge_only",
                "maximum_additional_attachments": 15,
                "root_attachment_required": True,
            },
        )
        for shape in ("root-only", "multi"):
            with self.subTest(shape=shape):
                attachment = _vector(
                    f"application-attachment-bundle.staging.{shape}.synthetic.v3.json"
                )
                intent = _vector(
                    f"registration-intent.staging.{shape}.synthetic.v3.json"
                )
                self.assertEqual(
                    validate_versioned_lifecycle_relationships(
                        integration_bundle=integration,
                        attachment_bundle=attachment,
                        registration_intent=intent,
                    ),
                    (),
                )
        for field, value in (
            ("root_attachment_required", False),
            ("maximum_additional_attachments", 14),
        ):
            with self.subTest(field=field):
                invalid = copy.deepcopy(integration)
                invalid["attachment_contract"][field] = value  # type: ignore[index]
                self.assertIn(
                    "FIELD_PATTERN",
                    {
                        item.code
                        for item in validate_versioned_lifecycle_document(
                            invalid,
                            "platform-integration-bundle",
                        )
                    },
                )

    def test_v3_fifteen_additional_attachments_are_valid(self) -> None:
        integration = _vector(
            "platform-integration-bundle.staging.synthetic.v3.json"
        )
        attachment = _vector(
            "application-attachment-bundle.staging.multi.synthetic.v3.json"
        )
        intent = _vector("registration-intent.staging.multi.synthetic.v3.json")
        additional_template = copy.deepcopy(attachment["additional_attachments"][0])  # type: ignore[index]
        binding_template = copy.deepcopy(intent["additional_attachment_bindings"][0])  # type: ignore[index]
        additional = []
        bindings = []
        for index in range(1, 16):
            attachment_id = f"api-{index:02d}"
            entry = copy.deepcopy(additional_template)
            entry["attachment_id"] = attachment_id
            entry["target"]["resource_reference"] = (  # type: ignore[index]
                "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
                f"us-west1:fixture-multi-api-{index:02d}"
            )
            additional.append(entry)
            binding = copy.deepcopy(binding_template)
            binding["attachment_id"] = attachment_id
            binding["mount_path"] = f"/api-{index:02d}"
            bindings.append(binding)
        attachment["additional_attachments"] = additional
        intent["additional_attachment_bindings"] = bindings

        self.assertEqual(
            validate_versioned_lifecycle_relationships(
                integration_bundle=integration,
                attachment_bundle=attachment,
                registration_intent=intent,
            ),
            (),
        )

    def test_v3_complete_set_rejects_cardinality_and_relationship_failures(self) -> None:
        integration = _vector(
            "platform-integration-bundle.staging.synthetic.v3.json"
        )
        attachment = _vector(
            "application-attachment-bundle.staging.multi.synthetic.v3.json"
        )
        intent = _vector("registration-intent.staging.multi.synthetic.v3.json")

        missing_root = copy.deepcopy(attachment)
        del missing_root["target"]

        sixteen = copy.deepcopy(attachment)
        template = copy.deepcopy(sixteen["additional_attachments"][0])  # type: ignore[index]
        sixteen["additional_attachments"] = []
        for index in range(16):
            entry = copy.deepcopy(template)
            entry["attachment_id"] = f"api-{index:02d}"
            sixteen["additional_attachments"].append(entry)  # type: ignore[union-attr]

        duplicate_ids = copy.deepcopy(attachment)
        duplicate_entry = copy.deepcopy(duplicate_ids["additional_attachments"][0])  # type: ignore[index]
        duplicate_entry["target"]["resource_reference"] = (  # type: ignore[index]
            "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
            "us-west1:fixture-multi-api-copy"
        )
        duplicate_ids["additional_attachments"].append(duplicate_entry)  # type: ignore[union-attr]

        noncanonical = copy.deepcopy(attachment)
        second = copy.deepcopy(noncanonical["additional_attachments"][0])  # type: ignore[index]
        second["attachment_id"] = "admin"
        second["target"]["resource_reference"] = (  # type: ignore[index]
            "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
            "us-west1:fixture-multi-admin"
        )
        noncanonical["additional_attachments"].append(second)  # type: ignore[union-attr]

        repeated_target = copy.deepcopy(attachment)
        repeated_entry = copy.deepcopy(repeated_target["additional_attachments"][0])  # type: ignore[index]
        repeated_entry["attachment_id"] = "api-copy"
        repeated_target["additional_attachments"].append(repeated_entry)  # type: ignore[union-attr]

        cases = (
            (missing_root, "FIELD_REQUIRED"),
            (sixteen, "FIELD_BOUNDS"),
            (duplicate_ids, "ATTACHMENT_ID_CONFLICT"),
            (noncanonical, "ATTACHMENT_ORDER_INVALID"),
            (repeated_target, "ATTACHMENT_TARGET_CONFLICT"),
        )
        for candidate, code in cases:
            with self.subTest(code=code):
                self.assertIn(
                    code,
                    {
                        item.code
                        for item in validate_versioned_lifecycle_document(
                            candidate,
                            "application-attachment-bundle",
                        )
                    },
                )

        missing_bindings = copy.deepcopy(intent)
        del missing_bindings["additional_attachment_bindings"]
        mismatched_bindings = copy.deepcopy(intent)
        mismatched_bindings["additional_attachment_bindings"][0][  # type: ignore[index]
            "attachment_id"
        ] = "other"
        root_reused = copy.deepcopy(intent)
        root_reused["additional_attachment_bindings"][0][  # type: ignore[index]
            "attachment_id"
        ] = root_reused["attachment_id"]
        non_root = copy.deepcopy(intent)
        non_root["mount_path"] = "/web"
        duplicate_mount = copy.deepcopy(intent)
        duplicate_mount["additional_attachment_bindings"][0][  # type: ignore[index]
            "mount_path"
        ] = "/"
        noncanonical_bindings = copy.deepcopy(intent)
        second_binding = copy.deepcopy(
            noncanonical_bindings["additional_attachment_bindings"][0]  # type: ignore[index]
        )
        second_binding["attachment_id"] = "admin"
        second_binding["mount_path"] = "/admin"
        noncanonical_bindings["additional_attachment_bindings"].append(  # type: ignore[union-attr]
            second_binding
        )

        relationship_cases = (
            (attachment, missing_bindings, "ATTACHMENT_SET_MISMATCH"),
            (attachment, mismatched_bindings, "ATTACHMENT_SET_MISMATCH"),
            (attachment, root_reused, "ATTACHMENT_ID_CONFLICT"),
            (attachment, non_root, "ROOT_MOUNT_INVALID"),
            (attachment, duplicate_mount, "ATTACHMENT_MOUNT_CONFLICT"),
            (attachment, noncanonical_bindings, "ATTACHMENT_ORDER_INVALID"),
        )
        for candidate_attachment, candidate_intent, code in relationship_cases:
            with self.subTest(code=code):
                self.assertIn(
                    code,
                    {
                        item.code
                        for item in validate_versioned_lifecycle_relationships(
                            integration_bundle=integration,
                            attachment_bundle=candidate_attachment,
                            registration_intent=candidate_intent,
                        )
                    },
                )

        root_only = _vector(
            "application-attachment-bundle.staging.root-only.synthetic.v3.json"
        )
        self.assertIn(
            "ATTACHMENT_SET_MISMATCH",
            {
                item.code
                for item in validate_versioned_lifecycle_relationships(
                    integration_bundle=integration,
                    attachment_bundle=root_only,
                    registration_intent=intent,
                )
            },
        )
        self.assertIn(
            "DOCUMENT_REQUIRED",
            {
                item.code
                for item in validate_versioned_lifecycle_relationships(
                    integration_bundle=integration,
                    attachment_bundle=attachment,
                )
            },
        )

    def test_v3_rejects_mixed_versions_stale_digest_and_prohibited_material(self) -> None:
        integration = _vector(
            "platform-integration-bundle.staging.synthetic.v3.json"
        )
        attachment = _vector(
            "application-attachment-bundle.staging.multi.synthetic.v3.json"
        )
        intent = _vector("registration-intent.staging.multi.synthetic.v3.json")

        mixed_families = (
            (
                attachment,
                _vector("registration-intent.staging.synthetic.v2.json"),
            ),
            (
                _vector("application-attachment-bundle.staging.synthetic.v1.json"),
                intent,
            ),
        )
        for mixed_attachment, mixed_intent in mixed_families:
            with self.subTest(version=mixed_attachment["contract_version"]):
                self.assertIn(
                    "CONTRACT_VERSION_MIXED",
                    {
                        item.code
                        for item in validate_versioned_lifecycle_relationships(
                            integration_bundle=integration,
                            attachment_bundle=mixed_attachment,
                            registration_intent=mixed_intent,
                        )
                    },
                )

        stale = copy.deepcopy(attachment)
        stale["platform_integration_bundle_digest"] = "sha256:" + "f" * 64
        self.assertIn(
            "DIGEST_MISMATCH",
            {
                item.code
                for item in validate_versioned_lifecycle_relationships(
                    integration_bundle=integration,
                    attachment_bundle=stale,
                    registration_intent=intent,
                )
            },
        )

        secret = copy.deepcopy(attachment)
        secret["additional_attachments"][0]["secret"] = "not-allowed"  # type: ignore[index]
        self.assertIn(
            "PROHIBITED_MATERIAL",
            {
                item.code
                for item in validate_versioned_lifecycle_document(
                    secret,
                    "application-attachment-bundle",
                )
            },
        )
        member_bearing = copy.deepcopy(attachment)
        member_bearing["additional_attachments"][0]["members"] = []  # type: ignore[index]
        self.assertIn(
            "PROHIBITED_MATERIAL",
            {
                item.code
                for item in validate_versioned_lifecycle_document(
                    member_bearing,
                    "application-attachment-bundle",
                )
            },
        )

    def test_v3_every_target_shares_application_scoped_posture(self) -> None:
        integration = _vector(
            "platform-integration-bundle.staging.synthetic.v3.json"
        )
        attachment = _vector(
            "application-attachment-bundle.staging.multi.synthetic.v3.json"
        )
        intent = _vector("registration-intent.staging.multi.synthetic.v3.json")
        for field, value in (
            ("application_project_id", "other-project-nonprod"),
            (
                "network_reference",
                "projects/other-project-nonprod/global/networks/other-network",
            ),
            (
                "subnetwork_reference",
                "projects/other-project-nonprod/regions/us-west1/subnetworks/other-subnet",
            ),
            (
                "resource_reference",
                "urn:comfforts:app-platform:gcp:cloud-run:999999999999:"
                "us-west1:fixture-multi-attachment-api",
            ),
        ):
            with self.subTest(field=field):
                candidate = copy.deepcopy(attachment)
                candidate["additional_attachments"][0]["target"][field] = value  # type: ignore[index]
                self.assertIn(
                    "ATTACHMENT_POSTURE_INVALID",
                    {
                        item.code
                        for item in validate_versioned_lifecycle_relationships(
                            integration_bundle=integration,
                            attachment_bundle=candidate,
                            registration_intent=intent,
                        )
                    },
                )

    def test_v3_loader_rejects_noncanonical_document_bytes(self) -> None:
        value = _vector("registration-intent.staging.multi.synthetic.v3.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registration-intent.v3.json"
            path.write_text(json.dumps(value, indent=2), encoding="utf-8")
            loaded = load_versioned_lifecycle_document(path, "registration-intent")

        self.assertEqual(
            [(item.code, item.path) for item in loaded.violations],
            [("DOCUMENT_NOT_CANONICAL", "")],
        )


if __name__ == "__main__":
    unittest.main()
