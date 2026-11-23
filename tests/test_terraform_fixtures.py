"""AP-M7-W5 Fixture Application root and internal module checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from infrastructure.config.validation import validate_configuration


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = PROJECT_ROOT / "infrastructure" / "terraform"
FIXTURE_ROOT = TERRAFORM_ROOT / "fixtures"
MODULE_ROOT = TERRAFORM_ROOT / "modules" / "fixture-application"
EXAMPLE_ROOT = PROJECT_ROOT / "infrastructure" / "config" / "examples"
FIXTURE_PROFILES = {
    "fixture-public": ("public", None),
    "fixture-authenticated": (
        "authenticated",
        "urn:comfforts:app-platform:audience:fixture-authenticated",
    ),
    "fixture-restricted": (
        "restricted",
        "urn:comfforts:app-platform:audience:fixture-restricted",
    ),
}


def _terraform_sources(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.glob("*.tf"))
    )


def _example(name: str) -> dict[str, object]:
    value = json.loads((EXAMPLE_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class TerraformFixtureApplicationTest(unittest.TestCase):
    def test_three_roots_expose_the_same_deep_interface(self) -> None:
        for application_id in FIXTURE_PROFILES:
            with self.subTest(application_id=application_id):
                root = FIXTURE_ROOT / application_id
                variables = (root / "variables.tf").read_text(encoding="utf-8")
                outputs = (root / "outputs.tf").read_text(encoding="utf-8")
                main = (root / "main.tf").read_text(encoding="utf-8")
                backend = (root / "backend.tf").read_text(encoding="utf-8")

                self.assertEqual(
                    re.findall(r'^variable "([^"]+)"', variables, re.MULTILINE),
                    [
                        "fixture_configuration",
                        "destruction_enabled",
                        "platform_reference",
                    ],
                )
                self.assertEqual(
                    re.findall(r'^output "([^"]+)"', outputs, re.MULTILINE),
                    ["attachment_reference"],
                )
                self.assertEqual(
                    re.findall(r'^module "([^"]+)"', main, re.MULTILINE),
                    ["fixture_application"],
                )
                self.assertIn('source = "../../modules/fixture-application"', main)
                self.assertEqual(backend.count('backend "gcs" {}'), 1)
                self.assertNotIn("bucket", backend)
                self.assertNotIn("prefix", backend)

    def test_each_root_is_bound_to_one_application_owner_and_profile(self) -> None:
        for application_id, (admission_mode, audience) in FIXTURE_PROFILES.items():
            with self.subTest(application_id=application_id):
                root = FIXTURE_ROOT / application_id
                variables = (root / "variables.tf").read_text(encoding="utf-8")
                outputs = (root / "outputs.tf").read_text(encoding="utf-8")

                self.assertIn(f'application_id == "{application_id}"', variables)
                self.assertIn(f'service_name == "{application_id}"', variables)
                self.assertIn(f'admission_mode == "{admission_mode}"', variables)
                expected_audience = (
                    "assertion_audience == null"
                    if audience is None
                    else f'assertion_audience == "{audience}"'
                )
                self.assertIn(expected_audience, variables)
                self.assertIn('state_owner == "application"', variables)
                self.assertIn('environment == "qualification"', variables)
                self.assertIn('managed_by == "terraform"', variables)
                self.assertIn(f'application_id == "{application_id}"', outputs)
                self.assertIn('adapter_kind       = "gcp-cloud-run-v1"', outputs)

    def test_root_variables_duplicate_fixture_and_platform_reference_contracts(self) -> None:
        fixture_schema = json.loads(
            (
                PROJECT_ROOT
                / "infrastructure/config/schemas/fixture-configuration.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        reference_schema = json.loads(
            (
                PROJECT_ROOT
                / "infrastructure/config/schemas/cross-state-reference.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        platform_fields = set(
            reference_schema["$defs"]["platformReference"]["required"]
        )
        self.assertIn("public_key_reference", platform_fields)

        for application_id in FIXTURE_PROFILES:
            variables = (
                FIXTURE_ROOT / application_id / "variables.tf"
            ).read_text(encoding="utf-8")
            for field in fixture_schema["required"]:
                self.assertIn(field, variables)
            for field in platform_fields:
                self.assertIn(field, variables)
            for mirrored_constraint in (
                'contract_version == 1',
                'configuration_kind == "fixture"',
                '["operator", "synthetic"]',
                'state_owner == "application"',
                '@sha256:[0-9a-f]{64}',
                'reference_kind == "platform"',
                'owner_id == "app-platform"',
                '/.well-known/jwks.json',
                "operator fixture configuration must use the reviewed non-production scope",
            ):
                self.assertIn(mirrored_constraint, variables)

    def test_internal_module_owns_only_fixture_runtime_resources(self) -> None:
        module = _terraform_sources(MODULE_ROOT)
        resources = re.findall(
            r'^resource "([^"]+)" "([^"]+)"', module, re.MULTILINE
        )

        self.assertEqual(
            resources,
            [
                ("google_service_account", "runtime"),
                ("google_cloud_run_v2_service", "runtime"),
                ("google_cloud_run_v2_service_iam_member", "edge_invoker"),
                ("google_cloud_run_v2_service_iam_member", "edge_metadata_reader"),
            ],
        )
        for required_control in (
            'destruction_enabled ? "DELETE" : "PREVENT"',
            "deletion_protection  = !var.runtime_configuration.destruction_enabled",
            'ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"',
            "invoker_iam_disabled = false",
            "max_instance_request_concurrency = 10",
            "min_instance_count = 0",
            "max_instance_count = 1",
            'cpu    = "1"',
            'memory = "512Mi"',
            'role     = "roles/run.invoker"',
            'role     = "roles/run.viewer"',
            "APP_PLATFORM_ISSUER",
            "APP_PLATFORM_PUBLIC_KEY_REFERENCE",
            "APP_PLATFORM_ASSERTION_AUDIENCE",
        ):
            self.assertIn(required_control, module)

        for prohibited in (
            'backend "',
            'provider "',
            'data "',
            "environment",
            "state_owner",
            "terraform_remote_state",
            "allUsers",
            "allAuthenticatedUsers",
            "google_project_iam",
            "google_compute_",
            "google_dns_",
            "google_storage_bucket",
            "google_service_account_key",
            "credential",
            "secret_key_ref",
        ):
            self.assertNotIn(prohibited, module)

    def test_attachment_outputs_conform_to_the_cross_state_contract(self) -> None:
        for application_id, (_, audience) in FIXTURE_PROFILES.items():
            fixture = _example(f"{application_id}.synthetic.v1.json")
            reference = {
                "contract_version": 1,
                "configuration_kind": "cross-state-reference",
                "configuration_class": "synthetic",
                "reference": {
                    "reference_kind": "attachment",
                    "state_owner": "application",
                    "owner_id": application_id,
                    "application_id": application_id,
                    "attachment_id": "primary",
                    "adapter_kind": "gcp-cloud-run-v1",
                    "resource_reference": (
                        "urn:comfforts:app-platform:gcp:cloud-run:"
                        f"{fixture['project_number']}:{fixture['region']}:{application_id}"
                    ),
                    "audience": audience,
                },
            }
            self.assertEqual(
                validate_configuration(
                    reference,
                    "cross-state-reference",
                    allow_synthetic=True,
                ),
                (),
            )

    def test_plan_tests_use_only_mocked_plan_mode_and_w3_examples(self) -> None:
        for application_id in FIXTURE_PROFILES:
            with self.subTest(application_id=application_id):
                test_file = (
                    FIXTURE_ROOT / application_id / "tests/fixture.tftest.hcl"
                ).read_text(encoding="utf-8")
                self.assertIn('mock_provider "google"', test_file)
                self.assertEqual(test_file.count("command = plan"), 1)
                self.assertNotIn("command = apply", test_file)
                self.assertIn(
                    f"../../../config/examples/{application_id}.synthetic.v1.json",
                    test_file,
                )
                self.assertIn(
                    "../../../config/examples/cross-state-platform.synthetic.v1.json",
                    test_file,
                )

    def test_fixture_implementation_has_no_cross_owner_or_mutation_path(self) -> None:
        fixture_terraform = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(FIXTURE_ROOT.rglob("*.tf"))
        )
        for prohibited in (
            "terraform_remote_state",
            "google_storage_bucket",
            "google_compute_",
            "google_dns_",
            "google_kms_",
            "google_secret_manager_",
            "google_firestore_",
            "terraform apply",
            "terraform destroy",
            "force-unlock",
            "feature_entitlement",
        ):
            self.assertNotIn(prohibited, fixture_terraform)


if __name__ == "__main__":
    unittest.main()
