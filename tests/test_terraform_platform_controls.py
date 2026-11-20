"""AP-M7-W8 observability, evidence, retention, label, and cost checks."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = PROJECT_ROOT / "infrastructure" / "terraform"
PLATFORM_ROOT = TERRAFORM_ROOT / "platform"
MODULE_ROOT = TERRAFORM_ROOT / "modules" / "platform-controls"


def _terraform_sources(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.glob("*.tf"))
    )


class TerraformPlatformControlsTest(unittest.TestCase):
    def test_root_composes_one_deep_controls_module_from_existing_inputs(self) -> None:
        main = (PLATFORM_ROOT / "main.tf").read_text(encoding="utf-8")
        variables = (PLATFORM_ROOT / "variables.tf").read_text(encoding="utf-8")

        self.assertEqual(
            re.findall(r'^module "([^"]+)"', main, re.MULTILINE),
            ["platform_foundation", "platform_controls", "shared_edge"],
        )
        self.assertIn('source = "../modules/platform-controls"', main)
        self.assertEqual(main.count("controls_configuration = {"), 1)
        for explicit_input in (
            "foundation.log_bucket",
            "foundation.evidence_bucket",
            "foundation.billing_account_reference",
            "foundation.notification_email",
            '"user:${local.foundation.notification_email}"',
            "foundation.artifact_repository_id",
        ):
            self.assertIn(explicit_input, main)
        self.assertEqual(
            re.findall(r'^variable "([^"]+)"', variables, re.MULTILINE),
            ["platform_configuration"],
        )
        self.assertNotIn('resource "', main)
        self.assertNotIn('data "', main)

    def test_module_owns_only_the_nine_platform_control_resources(self) -> None:
        module = _terraform_sources(MODULE_ROOT)
        resources = re.findall(
            r'^resource "([^"]+)" "([^"]+)"', module, re.MULTILINE
        )
        self.assertEqual(
            resources,
            [
                ("google_logging_project_bucket_config", "edge"),
                ("google_logging_project_sink", "edge"),
                ("google_logging_project_exclusion", "edge_from_default"),
                ("google_project_iam_member", "log_owner_reader"),
                ("google_storage_bucket", "evidence"),
                ("google_storage_bucket_iam_member", "evidence_owner_reader"),
                ("google_monitoring_notification_channel", "budget_email"),
                ("google_billing_budget", "qualification"),
                ("google_artifact_registry_repository", "qualification_images"),
            ],
        )
        for prohibited in (
            'backend "',
            'provider "',
            'data "',
            "terraform_remote_state",
            "google_dns_",
            "google_compute_security_policy",
            "google_compute_backend_bucket",
            "google_cloudfunctions",
            "google_pubsub",
            "google_service_account_key",
            "google_kms_crypto_key_version",
            "terraform apply",
            "terraform destroy",
        ):
            self.assertNotIn(prohibited, module)

    def test_logging_is_regional_minimized_excluded_and_not_exported(self) -> None:
        main = (MODULE_ROOT / "main.tf").read_text(encoding="utf-8")
        for required_control in (
            "location         = var.controls_configuration.region",
            "retention_days   = 7",
            "enable_analytics = false",
            'deletion_policy  = "PREVENT"',
            "logging.googleapis.com/projects/${var.controls_configuration.project_id}/locations/${var.controls_configuration.region}/buckets/",
            'resource.type=\\"cloud_run_revision\\"',
            'jsonPayload.event_type=\\"request_completion\\"',
            'jsonPayload.component=\\"shared-edge\\"',
            "unique_writer_identity = false",
            'resource "google_logging_project_exclusion" "edge_from_default"',
            'name        = "app-platform-edge-from-default"',
            "filter      = local.edge_resource_filter",
            "depends_on = [google_logging_project_sink.edge]",
            "prevent_destroy = true",
            'role    = "roles/logging.viewAccessor"',
        ):
            self.assertIn(required_control, main)
        self.assertEqual(main.count("exclusions {"), 3)
        for prohibited_field in (
            "assertion",
            "session_id",
            "restricted_members",
            "email",
            "remoteIp",
            "userAgent",
            "request_body",
            "response_body",
            "application_data",
            "stream_chunk",
            "provider_response",
            "credential",
            "terraform_state",
            "saved_plan",
        ):
            self.assertIn(prohibited_field, main)
        for external_destination in (
            "pubsub.googleapis.com",
            "bigquery.googleapis.com",
            "storage.googleapis.com",
        ):
            self.assertNotIn(external_destination, main)

    def test_evidence_is_private_owner_readable_and_expires_at_thirty_days(self) -> None:
        main = (MODULE_ROOT / "main.tf").read_text(encoding="utf-8")
        for required_control in (
            "name     = var.controls_configuration.evidence_bucket",
            "location = upper(var.controls_configuration.region)",
            "labels   = var.controls_configuration.labels",
            "force_destroy               = false",
            'deletion_policy             = "PREVENT"',
            "uniform_bucket_level_access = true",
            'public_access_prevention    = "enforced"',
            "retention_period = 2592000",
            "is_locked        = false",
            "age = 30",
            'type = "Delete"',
            'role   = "roles/storage.objectViewer"',
        ):
            self.assertIn(required_control, main)
        self.assertNotIn("google_storage_bucket_object", main)
        self.assertNotIn("allUsers", main)
        self.assertNotIn("allAuthenticatedUsers", main)

    def test_budget_notifies_without_automatic_mutation_or_implicit_recipient(self) -> None:
        main = (MODULE_ROOT / "main.tf").read_text(encoding="utf-8")
        self.assertIn(
            "billing_account = var.controls_configuration.billing_account_reference",
            main,
        )
        self.assertIn(
            'projects = ["projects/${var.controls_configuration.project_number}"]',
            main,
        )
        self.assertIn('currency_code = "USD"', main)
        self.assertIn('units         = "20"', main)
        self.assertEqual(main.count("threshold_rules {"), 3)
        for threshold in ("0.5", "0.8", "1.0"):
            self.assertIn(f"threshold_percent = {threshold}", main)
        self.assertEqual(main.count('spend_basis       = "CURRENT_SPEND"'), 3)
        self.assertIn(
            "monitoring_notification_channels = [google_monitoring_notification_channel.budget_email.id]",
            main,
        )
        self.assertIn(
            "email_address = var.controls_configuration.notification_email",
            main,
        )
        self.assertIn("disable_default_iam_recipients   = true", main)
        self.assertIn("enable_project_level_recipients  = false", main)
        for prohibited in (
            "billing_enabled",
            "disable_billing",
            "google_pubsub",
            "google_cloudfunctions",
            "google_cloud_run_v2_job",
        ):
            self.assertNotIn(prohibited, main)

    def test_artifact_cleanup_is_dry_run_first_and_keeps_three_roles(self) -> None:
        main = (MODULE_ROOT / "main.tf").read_text(encoding="utf-8")
        for required_control in (
            'format        = "DOCKER"',
            'mode          = "STANDARD_REPOSITORY"',
            "labels        = var.controls_configuration.labels",
            "cleanup_policy_dry_run = true",
            'deletion_policy        = "PREVENT"',
            'id     = "retain-generation-roles"',
            'action = "KEEP"',
            'tag_prefixes = ["active", "rollback", "candidate"]',
            'id     = "retain-three-per-service"',
            "package_name_prefixes = var.controls_configuration.artifact_packages",
            "keep_count            = 3",
            'id     = "delete-unretained-after-rollback-window"',
            'action = "DELETE"',
            'older_than = "1d"',
        ):
            self.assertIn(required_control, main)
        self.assertEqual(main.count("cleanup_policies {"), 3)

    def test_existing_runtime_caps_and_labels_remain_exact(self) -> None:
        edge = _terraform_sources(TERRAFORM_ROOT / "modules" / "shared-edge")
        fixture = _terraform_sources(TERRAFORM_ROOT / "modules" / "fixture-application")
        roots = "\n".join(
            _terraform_sources(TERRAFORM_ROOT / "fixtures" / application_id)
            for application_id in (
                "fixture-public",
                "fixture-authenticated",
                "fixture-restricted",
            )
        )
        for required_edge_control in (
            "min_instance_count = 0",
            "max_instance_count = 2",
            'cpu    = "1"',
            'memory = "512Mi"',
            "max_instance_request_concurrency = 20",
            'enable_cdn            = false',
        ):
            self.assertIn(required_edge_control, edge)
        for required_fixture_control in (
            "min_instance_count = 0",
            "max_instance_count = 1",
            'cpu    = "1"',
            'memory = "512Mi"',
            "max_instance_request_concurrency = 10",
        ):
            self.assertIn(required_fixture_control, fixture)
        self.assertIn("labels   = var.runtime_configuration.labels", fixture)
        self.assertIn(
            "application_id     = var.fixture_configuration.application_id",
            roots,
        )

    def test_plan_test_uses_only_mocked_plan_mode(self) -> None:
        test_file = (PLATFORM_ROOT / "tests/controls.tftest.hcl").read_text(
            encoding="utf-8"
        )
        self.assertIn('mock_provider "google"', test_file)
        self.assertEqual(test_file.count("command = plan"), 1)
        self.assertNotIn("command = apply", test_file)
        for required_policy in (
            "retention_days == 7",
            "retention_days == 30",
            "threshold_percents == [50, 80, 100]",
            "cleanup_dry_run",
            "most_recent_versions_per_service == 3",
            "automatic_billing_disablement",
            "automatic-cleanup-deletion",
            "application_id_when_applicable",
        ):
            self.assertIn(required_policy, test_file)


if __name__ == "__main__":
    unittest.main()
