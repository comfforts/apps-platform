"""AP-M7-W4 backend-bootstrap root and state-bucket module checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from infrastructure.config.validation import validate_configuration


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = PROJECT_ROOT / "infrastructure" / "terraform"
BOOTSTRAP_ROOT = TERRAFORM_ROOT / "bootstrap"
MODULE_ROOT = TERRAFORM_ROOT / "modules" / "state-bucket"
BACKEND_EXAMPLE = (
    PROJECT_ROOT / "infrastructure/config/examples/backend.synthetic.v1.json"
)


def _terraform_sources(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.glob("*.tf"))
    )


class TerraformBootstrapTest(unittest.TestCase):
    def test_bootstrap_exposes_one_deep_root_interface(self) -> None:
        variables = (BOOTSTRAP_ROOT / "variables.tf").read_text(encoding="utf-8")
        outputs = (BOOTSTRAP_ROOT / "outputs.tf").read_text(encoding="utf-8")
        main = (BOOTSTRAP_ROOT / "main.tf").read_text(encoding="utf-8")

        self.assertEqual(
            re.findall(r'^variable "([^"]+)"', variables, re.MULTILINE),
            ["backend_configuration"],
        )
        self.assertEqual(
            re.findall(r'^output "([^"]+)"', outputs, re.MULTILINE),
            ["bootstrap_phase_output"],
        )
        self.assertEqual(re.findall(r'^module "([^"]+)"', main, re.MULTILINE), ["state_bucket"])
        self.assertIn('source   = "../modules/state-bucket"', main)
        self.assertIn("for_each = local.state_buckets", main)

    def test_internal_module_owns_only_hardened_state_buckets(self) -> None:
        module = _terraform_sources(MODULE_ROOT)
        resources = re.findall(
            r'^resource "([^"]+)" "([^"]+)"', module, re.MULTILINE
        )

        self.assertEqual(resources, [("google_storage_bucket", "state")])
        for required_control in (
            'storage_class               = "STANDARD"',
            "force_destroy               = false",
            'deletion_policy             = "PREVENT"',
            "uniform_bucket_level_access = true",
            'public_access_prevention    = "enforced"',
            "enabled = true",
            'type = "Delete"',
            "days_since_noncurrent_time",
            "num_newer_versions",
            'with_state                 = "ARCHIVED"',
            "send_age_if_zero           = false",
            "configured_labels",
            'iam_binding                       = "deferred"',
        ):
            self.assertIn(required_control, module)

        for prohibited in (
            'backend "',
            'provider "',
            'data "',
            "environment",
            "state_owner",
            "google_storage_bucket_iam",
            "google_project_iam",
            "credential",
            "terraform_remote_state",
        ):
            self.assertNotIn(prohibited, module)

    def test_root_variable_duplicates_backend_schema_security_constraints(self) -> None:
        schema = json.loads(
            (
                PROJECT_ROOT
                / "infrastructure/config/schemas/backend-configuration.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        variables = (BOOTSTRAP_ROOT / "variables.tf").read_text(encoding="utf-8")

        self.assertEqual(
            set(schema["required"]),
            {
                "contract_version",
                "configuration_kind",
                "configuration_class",
                "project_id",
                "region",
                "state_buckets",
                "recovery_policy",
            },
        )
        for field in schema["required"]:
            self.assertIn(field, variables)
        for mirrored_value in (
            'contract_version == 1',
            'configuration_kind == "backend"',
            '["operator", "synthetic"]',
            "state_buckets) == 4",
            ">= 90",
            "<= 365",
            ">= 20",
            "<= 50",
            "operator configuration cannot select reserved synthetic values",
        ):
            self.assertIn(mirrored_value, variables)

    def test_backend_references_conform_to_the_cross_state_contract(self) -> None:
        backend = json.loads(BACKEND_EXAMPLE.read_text(encoding="utf-8"))
        for bucket in backend["state_buckets"]:
            reference = {
                "contract_version": 1,
                "configuration_kind": "cross-state-reference",
                "configuration_class": "synthetic",
                "reference": {
                    "reference_kind": "backend",
                    **bucket,
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

    def test_plan_test_uses_only_the_mocked_provider_and_w3_example(self) -> None:
        test_file = (BOOTSTRAP_ROOT / "tests/backend.tftest.hcl").read_text(
            encoding="utf-8"
        )
        check = (
            PROJECT_ROOT / "infrastructure/tools/terraform_check.py"
        ).read_text(encoding="utf-8")

        self.assertIn('mock_provider "google"', test_file)
        self.assertEqual(test_file.count("command = plan"), 1)
        self.assertNotIn("command = apply", test_file)
        self.assertIn("../../config/examples/backend.synthetic.v1.json", test_file)
        self.assertIn('"test"', check)
        self.assertIn('"-test-directory=tests"', check)

    def test_bootstrap_has_no_identity_fleet_or_mutation_command(self) -> None:
        bootstrap = _terraform_sources(BOOTSTRAP_ROOT)
        bootstrap_implementation = "\n".join((bootstrap, _terraform_sources(MODULE_ROOT)))
        self.assertNotIn('backend "', bootstrap)
        for prohibited in (
            "terraform_remote_state",
            "terraform apply",
            "terraform destroy",
            "force-unlock",
            "google_service_account",
            "google_service_account_key",
            "google_project_iam",
            "google_billing_account_iam",
        ):
            self.assertNotIn(prohibited, bootstrap_implementation)


if __name__ == "__main__":
    unittest.main()
