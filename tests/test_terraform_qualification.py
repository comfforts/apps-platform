"""AP-M7-W10 complete Terraform-and-workflow qualification checks."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from infrastructure.tools import terraform_check, terraform_setup


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TerraformQualificationGateTest(unittest.TestCase):
    def test_default_gate_runs_every_terraform_qualification_suite_once(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn(
            "check: governance-check contract-check fixture-check runtime-check terraform-check",
            makefile,
        )
        suites = (
            "tests.test_terraform_foundation",
            "tests.test_infrastructure_config",
            "tests.test_terraform_bootstrap",
            "tests.test_terraform_fixtures",
            "tests.test_terraform_platform_foundation",
            "tests.test_terraform_shared_edge",
            "tests.test_terraform_platform_controls",
            "tests.test_workflow_templates",
            "tests.test_terraform_qualification",
        )
        for suite in suites:
            with self.subTest(suite=suite):
                self.assertEqual(makefile.count(suite), 1)

        terraform_target = makefile.split("terraform-check:", maxsplit=1)[1]
        for prohibited_command in (
            "terraform apply",
            "terraform plan",
            "terraform init",
            "gcloud",
            "gsutil",
        ):
            self.assertNotIn(prohibited_command, terraform_target)

    def test_ap_eval_m7_trace_names_every_gate_and_work_package(self) -> None:
        gate_trace = {
            "AP-EVAL-M7-01": (
                "tests.test_governance.ProjectAuthorityTest",
                "tests.test_terraform_foundation.TerraformFoundationTest",
                "tests.test_runtime_qualification.GateIntegrityTest.test_complete_gate_runs_from_an_unchanged_history_independent_copy",
            ),
            "AP-EVAL-M7-02": (
                "tests.test_terraform_bootstrap.TerraformBootstrapTest",
                "tests.test_terraform_fixtures.TerraformFixtureApplicationTest",
                "tests.test_terraform_platform_foundation.TerraformPlatformFoundationTest",
            ),
            "AP-EVAL-M7-03": (
                "tests.test_infrastructure_config.InfrastructureConfigurationTest",
                "tests.test_terraform_foundation.TerraformFoundationTest",
            ),
            "AP-EVAL-M7-04": (
                "tests.test_terraform_bootstrap.TerraformBootstrapTest",
            ),
            "AP-EVAL-M7-05": (
                "tests.test_terraform_fixtures.TerraformFixtureApplicationTest",
            ),
            "AP-EVAL-M7-06": (
                "tests.test_terraform_platform_foundation.TerraformPlatformFoundationTest",
            ),
            "AP-EVAL-M7-07": (
                "tests.test_terraform_shared_edge.TerraformSharedEdgeTest",
            ),
            "AP-EVAL-M7-08": (
                "tests.test_terraform_platform_controls.TerraformPlatformControlsTest",
            ),
            "AP-EVAL-M7-09": (
                "tests.test_workflow_templates.WorkflowTemplateTest",
            ),
            "AP-EVAL-M7-10": (
                "tests.test_terraform_qualification.TerraformQualificationGateTest",
                "tests.test_runtime_qualification.GateIntegrityTest.test_complete_gate_runs_from_an_unchanged_history_independent_copy",
            ),
        }
        work_package_trace = {
            "AP-M7-W1": (
                "docs/03_system_design.md",
                "docs/04_implementation_plan.md",
                "docs/05_evaluation_strategy.md",
                "docs/06_threat_model.md",
            ),
            "AP-M7-W2": (
                ".terraform-version",
                "infrastructure/tools/terraform_setup.py",
                "infrastructure/tools/terraform_check.py",
            ),
            "AP-M7-W3": (
                "infrastructure/config/README.md",
                "infrastructure/config/validation.py",
            ),
            "AP-M7-W4": (
                "infrastructure/terraform/bootstrap/main.tf",
                "infrastructure/terraform/modules/state-bucket/main.tf",
            ),
            "AP-M7-W5": (
                "infrastructure/terraform/modules/fixture-application/main.tf",
                "tests/test_terraform_fixtures.py",
            ),
            "AP-M7-W6": (
                "infrastructure/terraform/modules/platform-foundation/main.tf",
                "tests/test_terraform_platform_foundation.py",
            ),
            "AP-M7-W7": (
                "infrastructure/terraform/modules/shared-edge/main.tf",
                "tests/test_terraform_shared_edge.py",
            ),
            "AP-M7-W8": (
                "infrastructure/terraform/modules/platform-controls/main.tf",
                "tests/test_terraform_platform_controls.py",
            ),
            "AP-M7-W9": (
                "infrastructure/workflows/README.md",
                "tests/test_workflow_templates.py",
            ),
            "AP-M7-W10": ("tests/test_terraform_qualification.py",),
            "AP-M7-W11": (
                "README.md",
                "docs/README.md",
                "prompts/starting_prompt.md",
            ),
        }

        self.assertEqual(
            set(gate_trace),
            {f"AP-EVAL-M7-{index:02d}" for index in range(1, 11)},
        )
        self.assertEqual(
            set(work_package_trace),
            {f"AP-M7-W{index}" for index in range(1, 12)},
        )
        loader = unittest.TestLoader()
        for gate, test_names in gate_trace.items():
            with self.subTest(gate=gate):
                self.assertTrue(test_names)
                for test_name in test_names:
                    error_count = len(loader.errors)
                    self.assertGreater(
                        loader.loadTestsFromName(test_name).countTestCases(),
                        0,
                        test_name,
                    )
                    self.assertEqual(loader.errors[error_count:], [], test_name)
        for work_package, paths in work_package_trace.items():
            with self.subTest(work_package=work_package):
                self.assertTrue(paths)
                self.assertTrue(
                    all((PROJECT_ROOT / path).is_file() for path in paths),
                    paths,
                )

    def test_every_root_has_explicit_plan_only_mocked_provider_tests(self) -> None:
        observed_roots = tuple(
            root.relative_to(terraform_check.TERRAFORM_SOURCE).as_posix()
            for root in terraform_setup.ROOTS
        )
        self.assertEqual(
            observed_roots,
            (
                "bootstrap",
                "platform",
                "fixtures/fixture-public",
                "fixtures/fixture-authenticated",
                "fixtures/fixture-restricted",
            ),
        )
        test_files = tuple(
            test_file
            for root in terraform_setup.ROOTS
            for test_file in terraform_check._plan_only_test_files(root)
        )
        self.assertEqual(len(test_files), 7)
        for test_file in test_files:
            contents = test_file.read_text(encoding="utf-8")
            with self.subTest(test_file=test_file):
                self.assertIn('mock_provider "google"', contents)
                self.assertIn("command = plan", contents)
                self.assertNotIn("command = apply", contents)

    def test_plan_test_policy_rejects_apply_and_implicit_apply_modes(self) -> None:
        for command in ("command = apply", ""):
            with self.subTest(command=command or "implicit apply"):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    tests = root / "tests"
                    tests.mkdir()
                    (tests / "unsafe.tftest.hcl").write_text(
                        'mock_provider "google" {}\n\n'
                        'run "unsafe" {\n'
                        f"  {command}\n"
                        "}\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "command = plan|apply-mode",
                    ):
                        terraform_check._plan_only_test_files(root)

    def test_offline_environment_exposes_no_host_credentials_or_operator_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            offline_cli_config = terraform_check._write_offline_cli_configuration(
                Path(temporary_directory) / "offline.tfrc"
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GOOGLE_APPLICATION_CREDENTIALS": "/private/credential.json",
                    "TF_TOKEN_example_com": "token",
                    "TF_VAR_project_id": "live-project",
                },
            ):
                environment = terraform_check._environment(
                    Path(temporary_directory) / "data",
                    offline_cli_config,
                )
            offline_configuration = offline_cli_config.read_text(encoding="utf-8")

        self.assertEqual(environment["GCE_METADATA_HOST"], "127.0.0.1:1")
        self.assertEqual(environment["HTTP_PROXY"], "http://127.0.0.1:1")
        self.assertEqual(environment["HTTPS_PROXY"], "http://127.0.0.1:1")
        self.assertTrue(environment["HOME"].startswith(temporary_directory))
        self.assertEqual(environment["TF_CLI_CONFIG_FILE"], str(offline_cli_config))
        self.assertIn(
            str(terraform_setup.MIRROR_ROOT.resolve()),
            offline_configuration,
        )
        self.assertIn(terraform_setup.GOOGLE_PROVIDER_SOURCE, offline_configuration)
        self.assertEqual(
            set(environment),
            {
                "CHECKPOINT_DISABLE",
                "GCE_METADATA_HOST",
                "HOME",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "NO_PROXY",
                "PATH",
                "TF_CLI_CONFIG_FILE",
                "TF_DATA_DIR",
                "TF_IN_AUTOMATION",
                "TMPDIR",
                "XDG_CONFIG_HOME",
            },
        )

    def test_terraform_command_warnings_fail_the_gate(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["terraform", "validate"],
            returncode=0,
            stdout="Warning: unexpected condition\n",
            stderr="",
        )
        with mock.patch.object(terraform_check.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "failed or warned"):
                terraform_check._run(
                    ["terraform", "validate"],
                    cwd=PROJECT_ROOT,
                    environment={},
                )

    def test_repository_has_no_state_plan_credential_or_mutation_workflow(self) -> None:
        ignored_parts = {".cache", ".git", ".tools", ".venv", "__pycache__"}
        prohibited: list[str] = []
        for path in PROJECT_ROOT.rglob("*"):
            relative = path.relative_to(PROJECT_ROOT)
            if ignored_parts.intersection(relative.parts):
                continue
            if ".terraform" in relative.parts:
                prohibited.append(relative.as_posix())
                continue
            if not path.is_file():
                continue
            name = path.name
            if (
                name.endswith(
                    (
                        ".tfstate",
                        ".tfplan",
                        ".tfplan.json",
                        ".tfvars",
                        ".auto.tfvars",
                        ".pem",
                        ".key",
                    )
                )
                or ".tfstate." in name
                or name == ".env"
                or (name.startswith(".env.") and name != ".env.example")
                or (name.startswith("credentials") and name.endswith(".json"))
                or name.startswith("gha-creds-")
            ):
                prohibited.append(relative.as_posix())
        self.assertEqual(prohibited, [])

        executable_workflows = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (PROJECT_ROOT / ".github/workflows").iterdir()
            if path.is_file()
        )
        self.assertEqual(executable_workflows, [".github/workflows/check.yml"])
        check_workflow = (PROJECT_ROOT / executable_workflows[0]).read_text(
            encoding="utf-8"
        )
        self.assertIn("permissions:\n  contents: read", check_workflow)
        self.assertNotIn("id-token: write", check_workflow)
        self.assertNotIn("terraform apply", check_workflow)

    def test_status_preserves_ap_m7_and_routes_next_work_to_ap_m9_w4(self) -> None:
        overview = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(
            encoding="utf-8"
        )
        combined = " ".join((overview, index, prompt))
        self.assertIn("AP-M7 implements statically verified Terraform", combined)
        self.assertIn("AP-M7 | complete | static Terraform", index)
        self.assertIn("AP-M8 | historical", index)
        self.assertIn("AP-M9-W2 — retired manifest cleanup (implemented)", index)
        self.assertIn("AP-M9-W3 — lifecycle contracts and profiles (implemented)", index)
        self.assertIn("AP-M9-W3 lifecycle-contract pull request has merged", prompt)
        self.assertIn("Implement one deep Python lifecycle module", prompt)
        self.assertIn("Leave AP-M9-W5's deployable Terraform lifecycle", prompt)
        self.assertIn("no platform environment is deployed or qualified", combined)
        for false_claim in (
            "AP-M7 is deployed",
            "AP-M7 is Live-qualified",
            "AP-M7 supplies Application Adoption",
            "AP-M8 is deployed",
            "AP-M8 is Live-qualified",
            "AP-M8-W3 is implemented",
            "real operator manifest is accepted",
        ):
            self.assertNotIn(false_claim, combined)


if __name__ == "__main__":
    unittest.main()
