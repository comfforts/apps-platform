"""AP-M7-W2 pinned Terraform foundation checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

from infrastructure.tools import terraform_check, terraform_setup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOTS = (
    "bootstrap",
    "platform",
    "fixtures/fixture-public",
    "fixtures/fixture-authenticated",
    "fixtures/fixture-multi-attachment",
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

    def test_every_root_explicitly_binds_provider_project_and_region(self) -> None:
        for root in terraform_setup.ROOTS:
            provider = (root / "provider.tf").read_text(encoding="utf-8")
            with self.subTest(root=root):
                self.assertEqual(provider.count('provider "google"'), 1)
                self.assertRegex(provider, r"(?m)^\s*project\s+=\s+var\.")
                self.assertRegex(provider, r"(?m)^\s*region\s+=\s+var\.")

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
        self.assertIn('"HOME": str(isolated_home)', check_source)
        self.assertIn('"PATH": os.environ.get("PATH", "")', check_source)
        self.assertNotIn("environment = dict(os.environ)", check_source)

    def test_provider_mirror_uses_a_module_free_selection_directory(self) -> None:
        provider_payload = b"synthetic locked provider package"
        provider_digest = hashlib.sha256(provider_payload).hexdigest()
        observed_working_directories: list[Path] = []

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            mirror = temporary / "provider-mirror"
            setup_config = temporary / "setup.tfrc"
            offline_config = temporary / "offline.tfrc"

            def mirror_provider(
                command: list[str],
                *,
                cwd: Path,
                env: dict[str, str],
                check: bool,
            ) -> subprocess.CompletedProcess[str]:
                del env
                self.assertTrue(check)
                self.assertIn("providers", command)
                self.assertIn("mirror", command)
                self.assertIn("-platform=linux_amd64", command)
                working_directory = Path(cwd)
                observed_working_directories.append(working_directory)
                self.assertNotEqual(working_directory, terraform_setup.ROOTS[0])
                self.assertEqual(
                    sorted(
                        path.relative_to(working_directory).as_posix()
                        for path in working_directory.rglob("*")
                        if path.is_file()
                    ),
                    [".terraform.lock.hcl", "versions.tf"],
                )
                package = (
                    mirror
                    / "registry.terraform.io/hashicorp/google"
                    / "terraform-provider-google_8.11.0_linux_amd64.zip"
                )
                package.parent.mkdir(parents=True)
                package.write_bytes(provider_payload)
                return subprocess.CompletedProcess(command, 0)

            with (
                mock.patch.object(terraform_setup, "MIRROR_ROOT", mirror),
                mock.patch.object(terraform_setup, "SETUP_CLI_CONFIG", setup_config),
                mock.patch.object(terraform_setup, "OFFLINE_CLI_CONFIG", offline_config),
                mock.patch.object(
                    terraform_setup,
                    "_lock_hashes",
                    return_value={provider_digest},
                ),
                mock.patch.object(
                    terraform_setup.subprocess,
                    "run",
                    side_effect=mirror_provider,
                ),
            ):
                self.assertEqual(
                    terraform_setup._populate_provider_mirror("linux_amd64"),
                    provider_digest,
                )

            self.assertEqual(len(observed_working_directories), 1)
            self.assertFalse(observed_working_directories[0].exists())
            self.assertIn(
                str(mirror.resolve()),
                offline_config.read_text(encoding="utf-8"),
            )

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
