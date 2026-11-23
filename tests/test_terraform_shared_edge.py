"""AP-M7-W7 Shared Edge and hostname-forwarding checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from infrastructure.config.validation import validate_configuration


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = PROJECT_ROOT / "infrastructure" / "terraform"
PLATFORM_ROOT = TERRAFORM_ROOT / "platform"
MODULE_ROOT = TERRAFORM_ROOT / "modules" / "shared-edge"
EXAMPLE_ROOT = PROJECT_ROOT / "infrastructure" / "config" / "examples"


def _terraform_sources(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.glob("*.tf"))
    )


class TerraformSharedEdgeTest(unittest.TestCase):
    def test_root_composes_one_deep_shared_edge_module(self) -> None:
        main = (PLATFORM_ROOT / "main.tf").read_text(encoding="utf-8")
        variables = (PLATFORM_ROOT / "variables.tf").read_text(encoding="utf-8")

        self.assertEqual(
            re.findall(r'^module "([^"]+)"', main, re.MULTILINE),
            ["platform_foundation", "platform_controls", "shared_edge"],
        )
        self.assertIn('source = "../modules/shared-edge"', main)
        self.assertEqual(main.count("edge_configuration = {"), 1)
        self.assertIn(
            'edge_revision_binding_digest = var.platform_configuration.phase == "shared-edge" ? sha256(jsonencode({',
            main,
        )
        self.assertIn("edge_candidate_revision", main)
        self.assertIn(
            "module.platform_foundation.foundation_reference.edge_runtime_email",
            main,
        )
        self.assertIn('count  = var.platform_configuration.phase == "shared-edge"', main)
        self.assertNotIn('resource "', main)
        self.assertNotIn('data "', main)

        for required_validation in (
            'contains(["foundation", "shared-edge"]',
            'phase == "foundation"',
            "shared_edge.edge_image_digest",
            "shared_edge.oauth_client_secret_version",
            "shared_edge.signing_key_version",
            "shared_edge.registration_generation",
        ):
            self.assertIn(required_validation, variables)

    def test_module_owns_exactly_one_edge_and_one_load_balancer(self) -> None:
        module = _terraform_sources(MODULE_ROOT)
        resources = re.findall(
            r'^resource "([^"]+)" "([^"]+)"', module, re.MULTILINE
        )
        self.assertEqual(
            resources,
            [
                ("google_cloud_run_v2_service", "edge"),
                ("google_cloud_run_v2_service_iam_member", "load_balancer_invoker"),
                ("google_compute_region_network_endpoint_group", "edge"),
                ("google_compute_backend_service", "edge"),
                ("google_compute_global_address", "edge"),
                ("google_compute_managed_ssl_certificate", "edge"),
                ("google_compute_url_map", "edge"),
                ("google_compute_target_https_proxy", "edge"),
                ("google_compute_global_forwarding_rule", "https"),
                ("google_compute_url_map", "http_redirect"),
                ("google_compute_target_http_proxy", "http_redirect"),
                ("google_compute_global_forwarding_rule", "http_redirect"),
            ],
        )
        self.assertEqual(module.count('resource "google_cloud_run_v2_service"'), 1)
        self.assertEqual(module.count('resource "google_compute_backend_service"'), 1)
        self.assertEqual(module.count('resource "google_compute_global_address"'), 1)
        self.assertEqual(
            module.count('resource "google_compute_managed_ssl_certificate"'), 1
        )
        self.assertEqual(module.count('resource "google_compute_target_https_proxy"'), 1)

    def test_edge_revision_is_immutable_bounded_and_closed_to_direct_origin(self) -> None:
        module = _terraform_sources(MODULE_ROOT)
        for required_control in (
            'deletion_policy      = var.destruction_enabled ? "DELETE" : "PREVENT"',
            'ingress              = var.destruction_enabled ? "INGRESS_TRAFFIC_INTERNAL_ONLY" : "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"',
            "default_uri_disabled = true",
            "invoker_iam_disabled = false",
            "revision                         = var.edge_configuration.candidate_revision",
            'timeout                          = "3600s"',
            "max_instance_request_concurrency = 20",
            "min_instance_count = 0",
            "max_instance_count = 2",
            'cpu    = "1"',
            'memory = "512Mi"',
            "image = var.edge_configuration.image_digest",
            'type     = "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"',
            "revision = var.edge_configuration.candidate_revision",
            "percent  = 100",
            'role     = "roles/run.invoker"',
            'member   = "allUsers"',
        ):
            self.assertIn(required_control, module)

        for binding_name in (
            "APP_PLATFORM_SOURCE_REVISION",
            "APP_PLATFORM_PROJECT_NUMBER",
            "APP_PLATFORM_COMPILER_VERSION",
            "APP_PLATFORM_REGISTRATION_GENERATION",
            "APP_PLATFORM_GENERATION_DIGEST",
            "APP_PLATFORM_CONFIGURATION_BUCKET",
            "APP_PLATFORM_CONFIGURATION_OBJECT",
            "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION",
            "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST",
            "APP_PLATFORM_IDENTITY_CONTRACT_VERSION",
            "APP_PLATFORM_ATTACHMENT_ADAPTER",
            "APP_PLATFORM_CONFIGURATION_CONTRACT_VERSION",
            "APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION",
            "APP_PLATFORM_SIGNING_KEY_VERSION",
        ):
            self.assertIn(binding_name, module)

    def test_forwarding_has_one_hostname_backend_and_no_application_routes(self) -> None:
        main = (MODULE_ROOT / "main.tf").read_text(encoding="utf-8")
        for required_control in (
            'network_endpoint_type = "SERVERLESS"',
            "service = google_cloud_run_v2_service.edge.name",
            'load_balancing_scheme = "EXTERNAL_MANAGED"',
            'protocol              = "HTTP"',
            "enable_cdn            = false",
            'address_type = "EXTERNAL"',
            'ip_version   = "IPV4"',
            'network_tier          = "PREMIUM"',
            "domains = [var.edge_configuration.qualification_hostname]",
            "hosts        = [var.edge_configuration.qualification_hostname]",
            "default_service = google_compute_backend_service.edge.id",
            "https_redirect         = true",
            'redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"',
            'port_range            = "443"',
            'port_range            = "80"',
        ):
            self.assertIn(required_control, main)

        for prohibited in (
            "path_rule",
            "route_rules",
            "url_mask",
            "security_policy",
            "edge_security_policy",
            "cdn_policy",
            "google_compute_security_policy",
            "google_dns_",
            "google_compute_backend_bucket",
        ):
            self.assertNotIn(prohibited, main)

    def test_serverless_backend_uses_provider_managed_timeout(self) -> None:
        main = (MODULE_ROOT / "main.tf").read_text(encoding="utf-8")
        backend_service = main.split(
            'resource "google_compute_backend_service" "edge" {', 1
        )[1].split("\n}", 1)[0]

        self.assertNotIn("timeout_sec", backend_service)

    def test_application_attachment_data_is_not_a_terraform_root_input(self) -> None:
        names = (
            "cross-state-attachment-public.synthetic.v1.json",
            "cross-state-attachment.synthetic.v1.json",
            "cross-state-attachment-restricted.synthetic.v1.json",
        )
        values = []
        for name in names:
            value = json.loads((EXAMPLE_ROOT / name).read_text(encoding="utf-8"))
            self.assertEqual(
                validate_configuration(
                    value,
                    "cross-state-reference",
                    allow_synthetic=True,
                ),
                (),
            )
            values.append(value["reference"])

        self.assertEqual(
            {value["application_id"] for value in values},
            {"fixture-public", "fixture-authenticated", "fixture-restricted"},
        )
        self.assertIsNone(values[0]["audience"])
        self.assertEqual(
            values[1]["audience"],
            "urn:comfforts:app-platform:audience:fixture-authenticated",
        )
        self.assertEqual(
            values[2]["audience"],
            "urn:comfforts:app-platform:audience:fixture-restricted",
        )

        module = _terraform_sources(MODULE_ROOT)
        root = _terraform_sources(PLATFORM_ROOT)
        self.assertNotIn("fixture_attachment_references", root)
        self.assertNotIn("attachment_references", module)
        for prohibited in (
            'backend "',
            'provider "',
            'data "',
            "terraform_remote_state",
            "google_cloud_run_v2_service.runtime",
            "google_service_account",
            "google_project_iam",
            "google_dns_",
            "https://fixture-",
            "fixture-public-runtime",
            "fixture-authenticated-runtime",
            "fixture-restricted-runtime",
        ):
            self.assertNotIn(prohibited, module)

    def test_plan_test_uses_only_mocked_plan_mode(self) -> None:
        test_file = (PLATFORM_ROOT / "tests/shared_edge.tftest.hcl").read_text(
            encoding="utf-8"
        )
        self.assertIn('mock_provider "google"', test_file)
        self.assertEqual(test_file.count("command = plan"), 2)
        self.assertNotIn("command = apply", test_file)
        self.assertIn("platform-shared-edge.synthetic.v2.json", test_file)
        for required_policy in (
            "public_direct_origin",
            "traffic_percent == 100",
            "application_prefix_routes == 0",
            "serverless_backend_count == 1",
            "application_runtime_management",
            "attachment_discovery",
            "application_owned_values",
            "arbitrary_target_url",
            "plans_reserved_address_before_dns_verified_tls",
        ):
            self.assertIn(required_policy, test_file)


if __name__ == "__main__":
    unittest.main()
