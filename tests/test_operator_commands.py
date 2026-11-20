"""AP-M9-W6 closed argv construction for the non-fake Terraform boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.backend import PhasePlanRequest
from infrastructure.operator.commands import (
    ClosedSubprocessRunner,
    CommandRequest,
    CommandResult,
    TerraformCliAdapter,
)


SOURCE_REVISION = "6" * 40


def _phase_request(root: Path, phase: str = "platform-foundation") -> PhasePlanRequest:
    terraform_root = {
        "bootstrap": "infrastructure/terraform/bootstrap",
        "platform-foundation": "infrastructure/terraform/platform",
        "shared-edge": "infrastructure/terraform/platform",
    }[phase]
    return PhasePlanRequest(
        environment="staging",
        source_revision=SOURCE_REVISION,
        phase=phase,
        terraform_root=terraform_root,
        state_owner="platform",
        owner_id="app-platform",
        project_id="comfforts-platform-non-prod",
        backend_path=root / "backend.tf",
        backend_digest="sha256:" + "7" * 64,
        backend_bucket="comfforts-ap-stg-455651441682-platform-state",
        backend_prefix="bootstrap" if phase == "bootstrap" else "platform",
    )


@dataclass
class FakeRunner:
    results: list[CommandResult]
    requests: list[CommandRequest] = field(default_factory=list)

    def run(self, request: CommandRequest) -> CommandResult:
        self.requests.append(request)
        for argument in request.argv:
            if argument.startswith("-out="):
                plan = Path(argument.removeprefix("-out="))
                plan.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                plan.write_bytes(b"fake exact saved plan")
                plan.chmod(0o600)
        return self.results.pop(0)


class OperatorCommandTest(unittest.TestCase):
    def _private_file(self, path: Path, contents: bytes) -> Path:
        path.write_bytes(contents)
        path.chmod(0o600)
        return path

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
        self.assertNotIn("GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", dict(invocation.environment))
        self.assertEqual(dict(invocation.environment)["HOME"], str(workspace / "home"))
        self.assertEqual(
            dict(invocation.environment)["CLOUDSDK_CONFIG"],
            str(workspace / "gcloud"),
        )

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
