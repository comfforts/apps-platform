"""AP-M7-W2 pinned Terraform foundation checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unittest

from infrastructure.tools import terraform_check, terraform_setup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOTS = (
    "bootstrap",
    "platform",
    "fixtures/fixture-public",
    "fixtures/fixture-authenticated",
    "fixtures/fixture-restricted",
)


class TerraformFoundationTest(unittest.TestCase):
    def test_root_constraints_pin_the_approved_toolchain(self) -> None:
        self.assertEqual(
            (PROJECT_ROOT / ".terraform-version").read_text(encoding="utf-8"),
            "1.17.2\n",
        )
        observed_roots = tuple(
            root.relative_to(PROJECT_ROOT / "infrastructure/terraform").as_posix()
            for root in terraform_setup.ROOTS
        )
        self.assertEqual(observed_roots, EXPECTED_ROOTS)

        for root in terraform_setup.ROOTS:
            versions = (root / "versions.tf").read_text(encoding="utf-8")
            self.assertIn('required_version = "= 1.17.2"', versions)
            self.assertIn('source  = "hashicorp/google"', versions)
            self.assertIn('version = "= 8.11.0"', versions)
            self.assertNotIn("backend ", versions)
            self.assertNotIn("resource ", versions)

    def test_root_locks_are_identical_and_signed_for_both_platforms(self) -> None:
        locks = [
            (root / ".terraform.lock.hcl").read_bytes()
            for root in terraform_setup.ROOTS
        ]
        self.assertTrue(all(contents == locks[0] for contents in locks[1:]))
        self.assertEqual(
            hashlib.sha256(locks[0]).hexdigest(),
            "c55fbd8f6eb7a96781dc236d0687f3058bf98e2afdd17fe55a415807d30b8c74",
        )
        lock = locks[0].decode("utf-8")
        self.assertIn('provider "registry.terraform.io/hashicorp/google"', lock)
        self.assertIn('version     = "8.11.0"', lock)
        self.assertIn('constraints = "8.11.0"', lock)
        self.assertEqual(len(re.findall(r'"h1:[^"]+"', lock)), 2)
        self.assertGreaterEqual(len(re.findall(r'"zh:[0-9a-f]{64}"', lock)), 2)

    def test_setup_is_checksum_pinned_and_kept_out_of_git(self) -> None:
        self.assertEqual(terraform_setup.TERRAFORM_VERSION, "1.17.2")
        self.assertEqual(terraform_setup.GOOGLE_PROVIDER_VERSION, "8.11.0")
        self.assertEqual(
            terraform_setup.LOCK_PLATFORMS,
            ("darwin_arm64", "linux_amd64"),
        )
        self.assertEqual(
            terraform_setup.PLATFORM_ARCHIVES[("Darwin", "arm64")][1],
            "da0c7ef278a911347862758e7573a5907365e66485c2637cf5c217c5e227992e",
        )
        self.assertEqual(
            terraform_setup.PLATFORM_ARCHIVES[("Linux", "x86_64")][1],
            "e6f16b2f0b137ee5729caa8c4e79a3bae4ee261acd198a1fcfa8584a6296605b",
        )
        ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".cache/terraform/", ignore)

        setup_source = (
            PROJECT_ROOT / "infrastructure/tools/terraform_setup.py"
        ).read_text(encoding="utf-8")
        self.assertIn("https://releases.hashicorp.com/terraform/", setup_source)
        self.assertIn("filesystem_mirror", setup_source)
        self.assertIn('variable.startswith(("TF_TOKEN_", "TF_CLI_ARGS"))', setup_source)
        self.assertNotIn("gcloud", setup_source)
        self.assertNotIn("terraform init", setup_source)

        check_source = (
            PROJECT_ROOT / "infrastructure/tools/terraform_check.py"
        ).read_text(encoding="utf-8")
        self.assertIn('variable.startswith(("TF_TOKEN_", "TF_CLI_ARGS"))', check_source)

    def test_check_workflow_separates_setup_from_the_offline_gate(self) -> None:
        workflow = (PROJECT_ROOT / ".github/workflows/check.yml").read_text(
            encoding="utf-8"
        )
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("make terraform-setup"),
            workflow.index("make check"),
        )
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertIn(
            "check: governance-check contract-check fixture-check runtime-check terraform-check",
            makefile,
        )
        self.assertIn("terraform-setup:", makefile)
        self.assertIn("terraform-check:", makefile)
        self.assertNotIn("terraform apply", makefile)
        self.assertNotIn("terraform plan", makefile)

    def test_all_roots_validate_offline_in_a_disposable_copy(self) -> None:
        repository_working_data_before = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (PROJECT_ROOT / "infrastructure").rglob(".terraform")
        )
        self.assertEqual(repository_working_data_before, [])
        self.assertEqual(terraform_check.validate_foundation(), EXPECTED_ROOTS)
        repository_working_data_after = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (PROJECT_ROOT / "infrastructure").rglob(".terraform")
        )
        self.assertEqual(repository_working_data_after, [])


if __name__ == "__main__":
    unittest.main()
