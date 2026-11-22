"""AP-M7-W6 Platform State identity and generation foundation checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = PROJECT_ROOT / "infrastructure" / "terraform"
PLATFORM_ROOT = TERRAFORM_ROOT / "platform"
MODULE_ROOT = TERRAFORM_ROOT / "modules" / "platform-foundation"
PLATFORM_EXAMPLE = (
    PROJECT_ROOT
    / "infrastructure/config/examples/platform-foundation.synthetic.v2.json"
)


def _terraform_sources(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.glob("*.tf"))
    )


class TerraformPlatformFoundationTest(unittest.TestCase):
    def test_platform_root_keeps_its_interfaces_explicit(self) -> None:
        variables = (PLATFORM_ROOT / "variables.tf").read_text(encoding="utf-8")
        outputs = (PLATFORM_ROOT / "outputs.tf").read_text(encoding="utf-8")
        main = (PLATFORM_ROOT / "main.tf").read_text(encoding="utf-8")
        backend = (PLATFORM_ROOT / "backend.tf").read_text(encoding="utf-8")

        self.assertEqual(
            re.findall(r'^variable "([^"]+)"', variables, re.MULTILINE),
            ["platform_configuration"],
        )
        self.assertEqual(
            re.findall(r'^output "([^"]+)"', outputs, re.MULTILINE),
            ["foundation_phase_output", "shared_edge_phase_output"],
        )
        self.assertEqual(
            re.findall(r'^module "([^"]+)"', main, re.MULTILINE),
            ["platform_foundation", "platform_controls", "shared_edge"],
        )
        self.assertIn('source = "../modules/platform-foundation"', main)
        self.assertIn('source = "../modules/shared-edge"', main)
        self.assertIn('source = "../modules/platform-controls"', main)
        self.assertEqual(backend.count('backend "gcs" {}'), 1)
        self.assertNotIn("bucket", backend)
        self.assertNotIn("prefix", backend)

    def test_internal_module_owns_only_w6_platform_state_resources(self) -> None:
        module = _terraform_sources(MODULE_ROOT)
        resources = re.findall(
            r'^resource "([^"]+)" "([^"]+)"', module, re.MULTILINE
        )

        self.assertEqual(
            resources,
            [
                ("google_project_service", "platform"),
                ("google_storage_bucket", "configuration"),
                ("google_service_account", "edge_runtime"),
                ("google_service_account", "edge_caller"),
                ("google_storage_bucket_iam_member", "edge_configuration_reader"),
                ("google_firestore_database", "sessions"),
                ("google_firestore_field", "session_expiration"),
                ("google_kms_key_ring", "assertion_signing"),
                ("google_kms_crypto_key", "assertion_signing"),
                ("google_kms_crypto_key_iam_member", "edge_signer"),
                ("google_secret_manager_secret", "edge_oauth"),
                (
                    "google_secret_manager_secret_iam_member",
                    "edge_oauth_secret_reader",
                ),
            ],
        )
        for required_control in (
            'public_access_prevention    = "enforced"',
            "uniform_bucket_level_access = true",
            "enabled = true",
            "retention_period = 86400",
            'type        = "FIRESTORE_NATIVE"',
            'database_edition                  = "STANDARD"',
            'point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"',
            'delete_protection_state           = local.destruction_enabled ? "DELETE_PROTECTION_DISABLED" : "DELETE_PROTECTION_ENABLED"',
            "ttl_config {}",
            'purpose  = "ASYMMETRIC_SIGN"',
            'algorithm        = "EC_SIGN_P256_SHA256"',
            'protection_level = "SOFTWARE"',
            "prevent_destroy = true",
            'role          = "roles/cloudkms.signerVerifier"',
            'role   = "roles/storage.objectViewer"',
            'role      = "roles/secretmanager.secretAccessor"',
            'resource "google_secret_manager_secret" "edge_oauth"',
            "deletion_protection = !local.destruction_enabled",
            "manual_rotation_days",
            "verification_overlap_hours",
            'registration_generation         = "later-stage-input"',
            '"cloudbuild.googleapis.com"',
            '"cloudresourcemanager.googleapis.com"',
            "disable_on_destroy         = false",
            "depends_on = [google_project_service.platform]",
            'retained_only          = var.destruction_mode == "retained"',
            'deletion_policy = local.destruction_enabled ? "DELETE" : "PREVENT"',
        ):
            self.assertIn(required_control, module)
        self.assertEqual(
            module.count("depends_on = [google_service_account.edge_runtime]"),
            3,
        )

    def test_module_has_no_later_slice_secret_or_activation_resource(self) -> None:
        module = _terraform_sources(MODULE_ROOT)
        for prohibited in (
            'backend "',
            'provider "',
            'data "',
            "environment",
            "state_owner",
            "terraform_remote_state",
            'resource "google_storage_bucket_object"',
            'resource "google_secret_manager_secret_version"',
            'resource "google_service_account_key"',
            'resource "google_kms_crypto_key_version"',
            "rotation_period",
            "google_cloud_run",
            "google_compute_",
            "google_dns_",
            "google_logging_",
            "google_billing_",
            "allUsers",
            "allAuthenticatedUsers",
            "restricted_members =",
            "secret_data",
            "private_key",
        ):
            self.assertNotIn(prohibited, module)

    def test_root_variable_duplicates_platform_schema_security_constraints(self) -> None:
        schema = json.loads(
            (
                PROJECT_ROOT
                / "infrastructure/config/schemas/platform-configuration.v2.schema.json"
            ).read_text(encoding="utf-8")
        )
        variables = (PLATFORM_ROOT / "variables.tf").read_text(encoding="utf-8")

        for field in schema["required"]:
            self.assertIn(field, variables)
        for mirrored_constraint in (
            'contract_version == 2',
            'configuration_kind == "platform"',
            '["operator", "synthetic"]',
            'repository == "comfforts/apps-platform"',
            'foundation.state_owner == "platform"',
            "@sha256:[0-9a-f]{64}",
            "/secrets/",
            "/cryptoKeyVersions/",
            "generation_digest",
            "content_digest",
            'labels.environment == "staging"',
            'labels.managed_by == "terraform"',
            "operator platform configuration must use the reviewed staging scope",
        ):
            self.assertIn(mirrored_constraint, variables)

    def test_foundation_example_contains_no_later_phase_values(self) -> None:
        platform = json.loads(PLATFORM_EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(platform["phase"], "foundation")
        self.assertEqual(platform["destruction_mode"], "none")
        self.assertIsNone(platform["shared_edge"])
        foundation = platform["foundation"]
        self.assertNotIn("edge_image_digest", foundation)
        self.assertNotIn("oauth_client_id", foundation)
        self.assertNotIn("signing_key_version", foundation)
        self.assertNotIn("registration_generation", foundation)

    def test_plan_test_uses_only_mocked_plan_mode_and_w3_example(self) -> None:
        test_file = (PLATFORM_ROOT / "tests/foundation.tftest.hcl").read_text(
            encoding="utf-8"
        )
        self.assertIn('mock_provider "google"', test_file)
        self.assertEqual(test_file.count("command = plan"), 1)
        self.assertNotIn("command = apply", test_file)
        self.assertIn(
            "../../config/examples/platform-foundation.synthetic.v2.json",
            test_file,
        )
        for required_policy in (
            "absolute_lifetime_seconds == 28800",
            "POINT_IN_TIME_RECOVERY_DISABLED",
            "manual_rotation_days == 90",
            "verification_overlap_hours == 24",
            "secret_version_present",
            "secret_value_present",
            "service_account_keys",
        ):
            self.assertIn(required_policy, test_file)

    def test_platform_root_has_no_application_or_mutation_path(self) -> None:
        platform = _terraform_sources(PLATFORM_ROOT)
        for prohibited in (
            "terraform_remote_state",
            "google_cloud_run",
            "google_compute_",
            "google_dns_",
            "google_storage_bucket_object",
            "google_service_account_key",
            "terraform apply",
            "terraform destroy",
            "force-unlock",
            "fixture-public-runtime",
            "fixture-authenticated-runtime",
            "fixture-restricted-runtime",
        ):
            self.assertNotIn(prohibited, platform)


if __name__ == "__main__":
    unittest.main()
