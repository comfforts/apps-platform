"""AP-M9-W6 closed argv construction for the non-fake Terraform boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import stat
import tempfile
import unittest

from infrastructure.backend import PhasePlanRequest
from infrastructure.operator.commands import (
    ClosedSubprocessRunner,
    CommandRequest,
    CommandResult,
    TerraformCliAdapter,
)
from infrastructure.operator.deployment import DeploymentCommandError


SOURCE_REVISION = "6" * 40


def _phase_request(root: Path, phase: str = "platform-foundation") -> PhasePlanRequest:
    terraform_root = {
        "bootstrap": "infrastructure/terraform/bootstrap",
        "platform-foundation": "infrastructure/terraform/platform",
        "shared-edge": "infrastructure/terraform/platform",
        "fixture-public": "infrastructure/terraform/fixtures/fixture-public",
    }[phase]
    fixture = phase.startswith("fixture-")
    return PhasePlanRequest(
        environment="staging",
        source_revision=SOURCE_REVISION,
        phase=phase,
        terraform_root=terraform_root,
        state_owner="application" if fixture else "platform",
        owner_id=phase if fixture else "app-platform",
        project_id="comfforts-platform-non-prod",
        backend_path=root / "backend.tf",
        backend_digest="sha256:" + "7" * 64,
        backend_bucket=(
            "comfforts-ap-stg-455651441682-fixture-public-state"
            if fixture
            else "comfforts-ap-stg-455651441682-platform-state"
        ),
        backend_prefix=(
            "fixtures/fixture-public"
            if fixture
            else ("bootstrap" if phase == "bootstrap" else "platform")
        ),
    )


@dataclass
class FakeRunner:
    results: list[CommandResult]
    requests: list[CommandRequest] = field(default_factory=list)
    plan_mode: int = 0o600

    def run(self, request: CommandRequest) -> CommandResult:
        self.requests.append(request)
        for argument in request.argv:
            if argument.startswith("-out="):
                plan = Path(argument.removeprefix("-out="))
                plan.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                plan.write_bytes(b"fake exact saved plan")
                plan.chmod(self.plan_mode)
        return self.results.pop(0)


class OperatorCommandTest(unittest.TestCase):
    def _private_file(self, path: Path, contents: bytes) -> Path:
        path.write_bytes(contents)
        path.chmod(0o600)
        return path

    def _failed_apply(self, stderr: bytes) -> DeploymentCommandError:
        runner = FakeRunner([CommandResult(1, b"", stderr)])
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "root"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            saved_plan = self._private_file(workspace / "plan.tfplan", b"exact-plan")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            with self.assertRaises(DeploymentCommandError) as raised:
                adapter.apply_plan(request, root, saved_plan)

        return raised.exception

    def test_plan_uses_closed_argv_exact_identity_and_in_memory_redacted_projection(
        self,
    ) -> None:
        plan_json = {
            "format_version": "1.2",
            "terraform_version": "1.17.2",
            "resource_changes": [
                {
                    "address": "module.foundation.google_storage_bucket.configuration",
                    "type": "google_storage_bucket",
                    "provider_name": "registry.terraform.io/hashicorp/google",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {"prohibited_raw_value": "not-retained"},
                    },
                }
            ],
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(2, b"", b""),
                CommandResult(0, json.dumps(plan_json).encode(), b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "root"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            variable_file = self._private_file(
                workspace / "values.auto.tfvars.json",
                b"{}\n",
            )
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"provider_installation {}\n")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            artifact = adapter.create_plan(request, root, variable_file)

        self.assertEqual(len(runner.requests), 3)
        init, plan, show = runner.requests
        self.assertEqual(init.argv[0], str(terraform.resolve()))
        self.assertIn("init", init.argv)
        self.assertIn(
            f"-backend-config=bucket={request.backend_bucket}",
            init.argv,
        )
        self.assertIn(f"-backend-config=prefix={request.backend_prefix}", init.argv)
        self.assertIn("-lockfile=readonly", init.argv)
        self.assertIn("-lock=true", plan.argv)
        self.assertNotIn("-lock=false", plan.argv)
        self.assertIn("show", show.argv)
        self.assertNotIn("GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", dict(show.environment))
        self.assertEqual(
            artifact.observation["changes"],
            [
                {
                    "address": "module.foundation.google_storage_bucket.configuration",
                    "resource_type": "google_storage_bucket",
                    "provider_source": "registry.terraform.io/hashicorp/google",
                    "actions": ["create"],
                }
            ],
        )
        self.assertNotIn("before", json.dumps(artifact.observation))
        self.assertNotIn("after", json.dumps(artifact.observation))

    def test_diagnostic_plan_disables_remote_state_locking(self) -> None:
        plan_json = {
            "format_version": "1.2",
            "terraform_version": "1.17.2",
            "resource_changes": [],
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(0, b"", b""),
                CommandResult(0, json.dumps(plan_json).encode(), b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "root"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            variables = self._private_file(workspace / "values.json", b"{}\n")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
                plan_lock=False,
            )

            adapter.create_plan(request, root, variables)

        plan = runner.requests[1]
        self.assertIn("-lock=false", plan.argv)
        self.assertNotIn("-lock=true", plan.argv)
        self.assertNotIn("-lock-timeout=0s", plan.argv)

    def test_plan_normalizes_tool_created_file_permissions(self) -> None:
        plan_json = {
            "format_version": "1.2",
            "terraform_version": "1.17.2",
            "resource_changes": [],
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(0, b"", b""),
                CommandResult(0, json.dumps(plan_json).encode(), b""),
            ],
            plan_mode=0o644,
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "root"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            variable_file = self._private_file(workspace / "values.json", b"{}\n")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            artifact = adapter.create_plan(request, root, variable_file)
            mode = artifact.saved_plan_path.stat().st_mode & 0o777

        self.assertEqual(mode, 0o600)

    def test_refresh_only_plan_is_explicit_and_never_combined_with_destroy(self) -> None:
        plan_json = {
            "format_version": "1.2",
            "terraform_version": "1.17.2",
            "resource_changes": [],
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(0, b"", b""),
                CommandResult(0, json.dumps(plan_json).encode(), b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "root"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            variable_file = self._private_file(workspace / "values.json", b"{}\n")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            artifact = adapter.create_plan(
                request,
                root,
                variable_file,
                refresh_only=True,
            )
            with self.assertRaises(ValueError):
                adapter.create_plan(
                    request,
                    root,
                    variable_file,
                    destroy=True,
                    refresh_only=True,
                )

        self.assertIn("-refresh-only", runner.requests[1].argv)
        self.assertEqual(artifact.observation["planning_mode"], "refresh-only")

    def test_apply_accepts_only_the_same_private_saved_plan_and_operator_session(self) -> None:
        runner = FakeRunner([CommandResult(0, b"", b"")])
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "root"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            saved_plan = self._private_file(workspace / "plan.tfplan", b"exact-plan")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
                operator_environment=(
                    ("CLOUDSDK_CONFIG", str(workspace / "gcloud")),
                    ("HOME", str(workspace / "home")),
                ),
            )

            adapter.apply_plan(request, root, saved_plan)

        invocation = runner.requests[0]
        self.assertEqual(
            invocation.argv[-1],
            str(saved_plan.resolve()),
        )
        self.assertIn("apply", invocation.argv)
        self.assertIn("-auto-approve", invocation.argv)
        self.assertIn("-no-color", invocation.argv)
        self.assertNotIn("GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", dict(invocation.environment))
        self.assertEqual(dict(invocation.environment)["HOME"], str(workspace / "home"))
        self.assertEqual(
            dict(invocation.environment)["CLOUDSDK_CONFIG"],
            str(workspace / "gcloud"),
        )

    def test_apply_classifies_identity_propagation_without_exposing_provider_output(
        self,
    ) -> None:
        error = self._failed_apply(
            b"Service account private-runtime@example.invalid does not exist."
        )
        self.assertEqual(
            str(error),
            "TERRAFORM_APPLY_IDENTITY_PROPAGATION_PENDING",
        )
        self.assertNotIn("private-runtime", str(error))

    def test_apply_reports_only_bounded_provider_diagnostics(self) -> None:
        error = self._failed_apply(
            b"Error: Error creating Budget: googleapi: Error 403: "
            b"Cloud Billing Budget API has not been used in project "
            b"comfforts-platform-non-prod or it is disabled.\n\n"
            b"Reason: SERVICE_DISABLED\n"
            b"Service: billingbudgets.googleapis.com\n\n"
            b"  with module.platform_controls.google_billing_budget."
            b"qualification[0],\n"
            b"client_secret=must-not-be-reported\n"
        )
        self.assertEqual(str(error), "TERRAFORM_APPLY_SERVICE_DISABLED")
        self.assertEqual(
            error.diagnostic,
            {
                "http_status": 403,
                "operation": "creating Budget",
                "provider_status": "SERVICE_DISABLED",
                "resource_address": (
                    "module.platform_controls.google_billing_budget.qualification[0]"
                ),
                "service": "billingbudgets.googleapis.com",
            },
        )
        self.assertNotIn(
            "must-not-be-reported",
            json.dumps(error.diagnostic),
        )

    def test_failed_apply_persists_exact_output_only_in_private_diagnostics(
        self,
    ) -> None:
        stdout = b"google_billing_budget.qualification: Creating...\n"
        stderr = (
            b"Error: Error creating Budget: provider detail "
            b"client_secret=must-remain-private\n"
        )
        runner = FakeRunner([CommandResult(1, stdout, stderr)])
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / ".platform-operator"
            state_root.mkdir(mode=0o700)
            work = state_root / "work"
            work.mkdir(mode=0o700)
            workspace = work / "deployment"
            workspace.mkdir(mode=0o700)
            root = workspace / "platform-foundation"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            saved_plan = self._private_file(workspace / "plan.tfplan", b"exact-plan")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
                private_state_root=state_root,
            )

            with self.assertRaises(DeploymentCommandError) as raised:
                adapter.apply_plan(request, root, saved_plan)

            diagnostic_path = Path(raised.exception.diagnostic["diagnostic_path"])
            diagnostic_directory = diagnostic_path.parent
            manifest = json.loads(
                (diagnostic_directory / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(diagnostic_path.read_bytes(), stderr)
            self.assertEqual((diagnostic_directory / "stdout.log").read_bytes(), stdout)
            self.assertEqual(stat.S_IMODE(diagnostic_path.stat().st_mode), 0o600)
            self.assertEqual(
                stat.S_IMODE((diagnostic_directory / "stdout.log").stat().st_mode),
                0o600,
            )
            self.assertEqual(stat.S_IMODE(diagnostic_directory.stat().st_mode), 0o700)
            self.assertEqual(manifest["operation"], "apply")
            self.assertEqual(manifest["phase"], "platform-foundation")
            self.assertEqual(manifest["environment"], "staging")
            self.assertEqual(
                raised.exception.diagnostic["diagnostic_digest"],
                manifest["diagnostic_digest"],
            )
            self.assertTrue(
                str(raised.exception.diagnostic["diagnostic_digest"]).startswith(
                    "sha256:"
                )
            )
            self.assertNotIn(
                "must-remain-private",
                json.dumps(raised.exception.diagnostic),
            )

    def test_failed_plan_persists_private_diagnostics_before_plan_cleanup(self) -> None:
        stderr = (
            b"Error: Instance cannot be destroyed\n"
            b"Resource module.shared_edge[0].google_compute_global_address.edge has\n"
            b"lifecycle.prevent_destroy set, but the plan calls for this resource "
            b"to be destroyed.\n"
            b"client_secret=must-remain-private\n"
        )
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(1, b"plan progress\n", stderr),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / ".platform-operator"
            state_root.mkdir(mode=0o700)
            work = state_root / "work"
            work.mkdir(mode=0o700)
            workspace = work / "deployment"
            workspace.mkdir(mode=0o700)
            root = workspace / "platform-foundation"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(
                request.backend_path,
                b'terraform { backend "gcs" {} }\n',
            )
            variables = self._private_file(workspace / "values.json", b"{}\n")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
                private_state_root=state_root,
            )

            with self.assertRaises(DeploymentCommandError) as raised:
                adapter.create_plan(request, root, variables)

            diagnostic_path = Path(raised.exception.diagnostic["diagnostic_path"])
            plan_files = tuple((workspace / "plans").glob("*.tfplan"))

            self.assertEqual(
                str(raised.exception),
                "TERRAFORM_PROTECTED_RESOURCE_DELETE_PROPOSED",
            )
            self.assertEqual(
                raised.exception.diagnostic["resource_address"],
                "module.shared_edge[0].google_compute_global_address.edge",
            )
            self.assertEqual(diagnostic_path.read_bytes(), stderr)
            self.assertEqual(plan_files, ())
            self.assertNotIn(
                "must-remain-private",
                json.dumps(raised.exception.diagnostic),
            )

    def test_failed_init_persists_private_diagnostics_and_names_module_error(
        self,
    ) -> None:
        stdout = b"Initializing the backend...\nInitializing modules...\n"
        stderr = (
            b"Error: Unreadable module directory\n\n"
            b"Unable to evaluate directory symlink: lstat ../../modules: "
            b"no such file or directory\n"
            b"client_secret=must-remain-private\n"
        )
        runner = FakeRunner([CommandResult(1, stdout, stderr)])
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / ".platform-operator"
            state_root.mkdir(mode=0o700)
            work = state_root / "work"
            work.mkdir(mode=0o700)
            workspace = work / "fixtures"
            workspace.mkdir(mode=0o700)
            root = workspace / "fixture-public"
            root.mkdir(mode=0o700)
            request = _phase_request(root, "fixture-public")
            self._private_file(
                request.backend_path,
                b'terraform { backend "gcs" {} }\n',
            )
            variables = self._private_file(workspace / "values.json", b"{}\n")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
                private_state_root=state_root,
            )

            with self.assertRaises(DeploymentCommandError) as raised:
                adapter.create_plan(request, root, variables)

            diagnostic_path = Path(raised.exception.diagnostic["diagnostic_path"])
            diagnostic_directory = diagnostic_path.parent
            manifest = json.loads(
                (diagnostic_directory / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(
                str(raised.exception),
                "TERRAFORM_INIT_MODULE_UNREADABLE",
            )
            self.assertEqual(diagnostic_path.read_bytes(), stderr)
            self.assertEqual((diagnostic_directory / "stdout.log").read_bytes(), stdout)
            self.assertEqual(manifest["operation"], "init")
            self.assertEqual(manifest["phase"], "fixture-public")
            self.assertNotIn(
                "must-remain-private",
                json.dumps(raised.exception.diagnostic),
            )

    def test_diagnostic_symlink_is_rejected_without_masking_apply_failure(self) -> None:
        runner = FakeRunner(
            [CommandResult(1, b"", b"Error: unclassified provider failure\n")]
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            state_root = temporary / ".platform-operator"
            state_root.mkdir(mode=0o700)
            outside = temporary / "outside"
            outside.mkdir(mode=0o700)
            (state_root / "diagnostics").symlink_to(outside, target_is_directory=True)
            work = state_root / "work"
            work.mkdir(mode=0o700)
            workspace = work / "deployment"
            workspace.mkdir(mode=0o700)
            root = workspace / "platform-foundation"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            saved_plan = self._private_file(workspace / "plan.tfplan", b"exact-plan")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
                private_state_root=state_root,
            )

            with self.assertRaises(DeploymentCommandError) as raised:
                adapter.apply_plan(request, root, saved_plan)

            self.assertEqual(
                str(raised.exception),
                "TERRAFORM_APPLY_FAILED_UNKNOWN",
            )
            self.assertEqual(
                raised.exception.diagnostic["diagnostic_capture"],
                "failed",
            )
            self.assertEqual(tuple(outside.iterdir()), ())

    def test_apply_classifies_provider_inconsistent_result_with_resource(self) -> None:
        error = self._failed_apply(
            b"Error: Provider produced inconsistent result after apply\n\n"
            b"When applying changes to module.platform_controls."
            b"google_logging_project_sink.edge[0], provider "
            b'\"registry.terraform.io/hashicorp/google\" produced an unexpected '
            b"new value: .unique_writer_identity: was cty.False, but now "
            b"cty.True.\n"
        )
        self.assertEqual(
            str(error),
            "TERRAFORM_APPLY_PROVIDER_INCONSISTENT_RESULT",
        )
        self.assertEqual(
            error.diagnostic,
            {
                "resource_address": (
                    "module.platform_controls.google_logging_project_sink.edge[0]"
                )
            },
        )

    def test_apply_failure_classifier_uses_specific_safe_codes(self) -> None:
        cases = {
            b"Error 401: UNAUTHENTICATED": "TERRAFORM_APPLY_AUTHENTICATION_FAILED",
            b"notification channel does not exist": (
                "TERRAFORM_APPLY_DEPENDENCY_PROPAGATION_PENDING"
            ),
            b"concurrent policy changes": "TERRAFORM_APPLY_IAM_CONFLICT",
            b"Error acquiring the state lock": "TERRAFORM_APPLY_STATE_LOCKED",
            b"Error 429: RESOURCE_EXHAUSTED": "TERRAFORM_APPLY_QUOTA_EXCEEDED",
            b"Error 403: PERMISSION_DENIED": "TERRAFORM_APPLY_PERMISSION_DENIED",
            b"Error 400: INVALID_ARGUMENT": "TERRAFORM_APPLY_INVALID_ARGUMENT",
            b"Error 409: ALREADY_EXISTS": "TERRAFORM_APPLY_CONFLICT",
            (
                b"Error 409: Revision named 'app-platform-edge-g1-deadbeef0000' "
                b"with different configuration already exists."
            ): "TERRAFORM_APPLY_IMMUTABLE_REVISION_CONFLICT",
            b"plugin did not respond": "TERRAFORM_APPLY_PLUGIN_FAILED",
            b"unclassified provider failure": "TERRAFORM_APPLY_FAILED_UNKNOWN",
        }
        for stderr, expected in cases.items():
            with self.subTest(stderr=stderr):
                self.assertEqual(
                    TerraformCliAdapter._apply_failure_code(stderr),
                    expected,
                )

    def test_fixture_destroy_plan_and_empty_state_readback_are_explicit(self) -> None:
        plan_json = {
            "format_version": "1.2",
            "terraform_version": "1.17.2",
            "resource_changes": [
                {
                    "address": "module.fixture.google_cloud_run_v2_service.runtime",
                    "type": "google_cloud_run_v2_service",
                    "provider_name": "registry.terraform.io/hashicorp/google",
                    "change": {"actions": ["delete"]},
                }
            ]
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(2, b"", b""),
                CommandResult(0, json.dumps(plan_json).encode(), b""),
                CommandResult(0, b"\n", b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "fixture-public"
            root.mkdir(mode=0o700)
            request = _phase_request(root, "fixture-public")
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            variables = self._private_file(root / "values.json", b"{}\n")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            artifact = adapter.create_plan(
                request,
                root,
                variables,
                destroy=True,
            )
            empty = adapter.state_empty(request, root)

        self.assertIn("-destroy", runner.requests[1].argv)
        self.assertEqual(artifact.observation["changes"][0]["actions"], ["delete"])
        self.assertTrue(empty)
        self.assertEqual(runner.requests[3].argv[1:3], ("state", "list"))
        self.assertEqual(runner.requests[3].authority, "application-state-read")

    def test_platform_state_projection_initializes_only_the_exact_lineage(self) -> None:
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(
                    0,
                    b"module.platform_foundation.google_storage_bucket.configuration\n",
                    b"",
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "platform-foundation"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            addresses = adapter.platform_state_addresses(request, root)

        self.assertEqual(
            addresses,
            ("module.platform_foundation.google_storage_bucket.configuration",),
        )
        self.assertEqual(runner.requests[0].argv[1], "init")
        self.assertEqual(runner.requests[1].argv[1:], ("state", "list"))
        self.assertEqual(runner.requests[1].authority, "platform-state-read")

    def test_platform_state_projection_treats_absent_initial_state_as_empty(self) -> None:
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(1, b"", b"No state file was found!\n"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "platform-foundation"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            addresses = adapter.platform_state_addresses(request, root)

        self.assertEqual(addresses, ())

    def test_bootstrap_uses_explicit_local_backend_and_short_lived_human_session(self) -> None:
        plan_json = {
            "format_version": "1.2",
            "terraform_version": "1.17.2",
            "resource_changes": [],
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(0, b"", b""),
                CommandResult(0, json.dumps(plan_json).encode(), b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "root"
            root.mkdir(mode=0o700)
            request = _phase_request(root, "bootstrap")
            variable_file = self._private_file(workspace / "values.json", b"{}")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            adapter.create_plan(request, root, variable_file)

        self.assertIn("-backend=false", runner.requests[0].argv)
        self.assertNotIn(
            "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT",
            dict(runner.requests[1].environment),
        )

    def test_protected_signing_key_ring_taint_is_classified_and_plan_removed(
        self,
    ) -> None:
        diagnostic = b"""
Error: Instance cannot be destroyed

Resource module.platform_foundation.google_kms_key_ring.assertion_signing has
lifecycle.prevent_destroy set, but the plan calls for this resource to be
destroyed.
"""
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(1, b"", diagnostic),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "platform-foundation"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            variables = self._private_file(root / "values.json", b"{}\n")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            with self.assertRaises(DeploymentCommandError) as raised:
                adapter.create_plan(request, root, variables)
            retained_plans = list((workspace / "plans").glob("*.tfplan"))

        self.assertEqual(
            str(raised.exception),
            "TERRAFORM_PROTECTED_SIGNING_KEY_RING_TAINTED",
        )
        self.assertEqual(retained_plans, [])

    def test_plan_failures_are_safely_classified_without_exposing_stderr(self) -> None:
        cases = {
            (
                b"Error: Instance cannot be destroyed\n"
                b"Resource module.shared_edge[0].google_compute_global_address.edge has\n"
                b"lifecycle.prevent_destroy set, but the plan calls for this resource "
                b"to be destroyed."
            ): "TERRAFORM_PROTECTED_RESOURCE_DELETE_PROPOSED",
            b"Error acquiring the state lock": "TERRAFORM_STATE_LOCKED",
            b"Error loading state: backend object unavailable": (
                "TERRAFORM_STATE_READ_FAILED"
            ),
            b"Failed to get existing workspaces: querying Cloud Storage failed: 403": (
                "TERRAFORM_BACKEND_ACCESS_DENIED"
            ),
            b"oauth2: invalid_grant: reauth related error": (
                "TERRAFORM_OPERATOR_AUTHENTICATION_FAILED"
            ),
            b"Error 403: permission denied for protected resource": (
                "TERRAFORM_PROVIDER_PERMISSION_DENIED"
            ),
            b"Error 429: quota exceeded": "TERRAFORM_PROVIDER_QUOTA_EXCEEDED",
            b"Error: Missing required argument": "TERRAFORM_CONFIGURATION_INVALID",
            b"Failed to load plugin schemas": "TERRAFORM_PROVIDER_PLUGIN_FAILED",
            b"unclassified private provider diagnostic": "TERRAFORM_PLAN_FAILED_UNKNOWN",
        }

        for diagnostic, expected in cases.items():
            with self.subTest(expected=expected):
                observed = TerraformCliAdapter._plan_failure(diagnostic)

                self.assertEqual(observed, expected)
                self.assertNotIn("private", observed.lower())

    def test_signing_key_ring_taint_recovery_uses_one_exact_state_command(
        self,
    ) -> None:
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(0, b"", b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "platform-foundation"
            root.mkdir(mode=0o700)
            request = _phase_request(root)
            self._private_file(request.backend_path, b'terraform { backend "gcs" {} }\n')
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            adapter.clear_signing_key_ring_taint(request, root)

        self.assertEqual(runner.requests[0].argv[1], "init")
        self.assertEqual(
            runner.requests[1].argv[1:],
            (
                "untaint",
                "-lock=true",
                "-lock-timeout=0s",
                "module.platform_foundation.google_kms_key_ring.assertion_signing",
            ),
        )
        self.assertEqual(runner.requests[1].authority, "platform-state-recovery")

    def test_bootstrap_migrates_only_to_exact_remote_lineage_and_reads_it_back(
        self,
    ) -> None:
        output = {
            "contract_version": 1,
            "output_kind": "bootstrap",
            "environment": "staging",
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(0, json.dumps(output).encode(), b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "bootstrap"
            root.mkdir(mode=0o700)
            request = _phase_request(root, "bootstrap")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            adapter.migrate_bootstrap_state(request, root)
            observed = adapter.read_output(
                request,
                root,
                "bootstrap_phase_output",
            )

        migration, readback = runner.requests
        self.assertEqual(migration.authority, "bootstrap-state-migration")
        self.assertEqual(
            migration.argv[1:],
            (
                "init",
                "-input=false",
                "-lockfile=readonly",
                "-migrate-state",
                "-force-copy",
                "-backend-config=bucket=comfforts-ap-stg-455651441682-platform-state",
                "-backend-config=prefix=bootstrap",
            ),
        )
        self.assertEqual(
            readback.argv[1:],
            ("output", "-json", "bootstrap_phase_output"),
        )
        self.assertEqual(observed, output)

    def test_shared_edge_reads_exact_foundation_output_from_shared_lineage(
        self,
    ) -> None:
        output = {
            "contract_version": 1,
            "output_kind": "platform-foundation",
            "environment": "staging",
        }
        runner = FakeRunner(
            [CommandResult(0, json.dumps(output).encode(), b"")]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "shared-edge"
            root.mkdir(mode=0o700)
            request = _phase_request(root, "shared-edge")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            observed = adapter.read_output(
                request,
                root,
                "foundation_phase_output",
            )

        self.assertEqual(
            runner.requests[0].argv[1:],
            ("output", "-json", "foundation_phase_output"),
        )
        self.assertEqual(observed, output)

    def test_existing_bootstrap_initializes_the_exact_remote_lineage(self) -> None:
        plan_json = {
            "format_version": "1.2",
            "terraform_version": "1.17.2",
            "resource_changes": [],
        }
        runner = FakeRunner(
            [
                CommandResult(0, b"", b""),
                CommandResult(0, b"", b""),
                CommandResult(0, json.dumps(plan_json).encode(), b""),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            root = workspace / "bootstrap"
            root.mkdir(mode=0o700)
            request = _phase_request(root, "bootstrap")
            self._private_file(
                request.backend_path,
                b'terraform { backend "gcs" {} }\n',
            )
            values = self._private_file(workspace / "values.json", b"{}")
            terraform = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                terraform,
                cli_config,
                workspace,
                runner,
            )

            adapter.create_plan(
                request,
                root,
                values,
                bootstrap_remote=True,
            )

        init = runner.requests[0]
        self.assertNotIn("-backend=false", init.argv)
        self.assertIn(
            "-backend-config=bucket="
            "comfforts-ap-stg-455651441682-platform-state",
            init.argv,
        )
        self.assertIn("-backend-config=prefix=bootstrap", init.argv)

    def test_closed_runner_rejects_shells_unapproved_executables_and_ambient_environment(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = self._private_file(root / "terraform", b"binary")
            runner = ClosedSubprocessRunner((executable,), root)
            safe = CommandRequest(
                argv=(str(executable), "version"),
                cwd=root,
                environment=(("CHECKPOINT_DISABLE", "1"),),
            )
            unsafe_requests = (
                CommandRequest(("sh", "-c", "terraform apply"), root, ()),
                CommandRequest((str(executable), "state", "push"), root, ()),
                CommandRequest((str(executable), "plan", "-lock=false"), root, ()),
                CommandRequest(
                    (str(executable), "version"),
                    root,
                    (("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/key.json"),),
                ),
                CommandRequest(
                    (str(executable), "init", "-migrate-state", "-force-copy"),
                    root,
                    (),
                    authority="bootstrap-state-migration",
                ),
            )

            runner.validate(safe)
            for request in unsafe_requests:
                with self.subTest(argv=request.argv), self.assertRaises(ValueError):
                    runner.validate(request)

    def test_paths_cannot_escape_the_private_workspace(self) -> None:
        runner = FakeRunner([])
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "private"
            workspace.mkdir(mode=0o700)
            executable = self._private_file(workspace / "terraform", b"binary")
            cli_config = self._private_file(workspace / "terraform.rc", b"config")
            adapter = TerraformCliAdapter(
                executable,
                cli_config,
                workspace,
                runner,
            )
            outside = Path(directory) / "outside"
            outside.mkdir(mode=0o700)
            request = _phase_request(outside)
            values = self._private_file(workspace / "values.json", b"{}")

            with self.assertRaisesRegex(ValueError, "workspace"):
                adapter.create_plan(request, outside, values)

        self.assertEqual(runner.requests, [])


if __name__ == "__main__":
    unittest.main()
