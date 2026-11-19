"""AP-M9-W6 exact staged deployment through deterministic command fakes."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator import StageContext
from infrastructure.operator.deployment import (
    DeploymentCommandError,
    DeploymentExecutor,
    ExactTerraformPlan,
    TerraformPlanArtifact,
    TerraformReadback,
)


SOURCE_REVISION = "4" * 40
SPECIFICATION_DIGEST = "sha256:" + "5" * 64
GOOGLE_PROVIDER = "registry.terraform.io/hashicorp/google"
RESOURCE_TYPES = {
    "bootstrap": "google_storage_bucket",
    "platform-foundation": "google_storage_bucket",
    "shared-edge": "google_compute_global_address",
}


def _context(stage_id: str, produces: tuple[str, ...]) -> StageContext:
    return StageContext(
        environment="staging",
        source_revision=SOURCE_REVISION,
        specification_digest=SPECIFICATION_DIGEST,
        stage={
            "stage_id": stage_id,
            "actions": ["create", "read"],
            "resource_types": ["test-resource"],
            "consumes": [],
            "produces": list(produces),
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        inputs=(),
    )


@dataclass
class FakeTerminal:
    typed_approvals: list[bool] = field(default_factory=lambda: [True])
    confirmations: list[tuple[str, str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.confirmations.append((prompt, expected))
        return self.typed_approvals.pop(0)

    def write(self, message: str) -> None:
        self.messages.append(message)


@dataclass
class FakeCommands:
    working_root: Path
    actions: tuple[str, ...] = ("create",)
    wrong_project: bool = False
    readback_matches: bool = True
    apply_error: str | None = None
    planned: list[object] = field(default_factory=list)
    applied: list[tuple[object, ExactTerraformPlan]] = field(default_factory=list)
    readbacks: list[object] = field(default_factory=list)

    def create_terraform_plan(self, request: object) -> TerraformPlanArtifact:
        self.planned.append(request)
        phase = str(getattr(request, "phase"))
        path = self.working_root / f"{phase}.tfplan"
        path.write_bytes(b"private saved plan")
        path.chmod(0o600)
        return TerraformPlanArtifact(
            saved_plan_path=path,
            observation={
                "environment": getattr(request, "environment"),
                "source_revision": getattr(request, "source_revision"),
                "state_owner": getattr(request, "state_owner"),
                "owner_id": getattr(request, "owner_id"),
                "terraform_root": getattr(request, "terraform_root"),
                "phase": phase,
                "provider": {
                    "source": GOOGLE_PROVIDER,
                    "service": "google",
                    "project_id": (
                        "wrong-project"
                        if self.wrong_project
                        else getattr(request, "project_id")
                    ),
                    "configuration": "explicit",
                },
                "changes": [
                    {
                        "address": f"module.subject.{RESOURCE_TYPES[phase]}.subject",
                        "resource_type": RESOURCE_TYPES[phase],
                        "provider_source": GOOGLE_PROVIDER,
                        "actions": list(self.actions),
                    }
                ]
                if self.actions
                else [],
            },
        )

    def apply_terraform_plan(
        self,
        request: object,
        plan: ExactTerraformPlan,
    ) -> None:
        self.applied.append((request, plan))
        if self.apply_error is not None:
            raise DeploymentCommandError(self.apply_error)

    def readback_terraform(self, request: object) -> TerraformReadback:
        self.readbacks.append(request)
        stage_id = str(getattr(request, "stage_id"))
        outputs = {
            "bootstrap": (
                ("backend-reference", "verified-backend"),
                ("identity-reference", "verified-identities"),
            ),
            "foundation": (
                ("foundation-reference", "verified-foundation"),
                ("oauth-secret-container", "verified-secret-container"),
            ),
            "shared-edge": (
                ("edge-reference", "verified-edge"),
                ("reserved-address", "192.0.2.10"),
            ),
            "tls-readiness": (
                ("certificate-reference", "verified-certificate"),
            ),
        }[stage_id]
        return TerraformReadback(
            matched=self.readback_matches,
            outputs=outputs,
            blockers=() if self.readback_matches else ("TERRAFORM_READBACK_MISMATCH",),
        )


class PlatformDeploymentTest(unittest.TestCase):
    def _executor(
        self,
        root: Path,
        *,
        terminal: FakeTerminal | None = None,
        commands: FakeCommands | None = None,
    ) -> tuple[DeploymentExecutor, FakeTerminal, FakeCommands]:
        root.mkdir(mode=0o700)
        selected_terminal = terminal or FakeTerminal()
        selected_commands = commands or FakeCommands(root)
        return (
            DeploymentExecutor(root, selected_terminal, selected_commands),
            selected_terminal,
            selected_commands,
        )

    def test_exact_private_plan_is_policy_checked_confirmed_applied_and_read_back(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor, terminal, commands = self._executor(Path(directory) / "work")

            result = executor.execute(
                _context("foundation", ("foundation-reference", "oauth-secret-container"))
            )

        self.assertEqual(result.outcome, "succeeded")
        self.assertRegex(result.plan_digest or "", r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(result.outputs[0], ("foundation-reference", "verified-foundation"))
        self.assertEqual(len(commands.planned), 1)
        self.assertEqual(len(commands.applied), 1)
        self.assertEqual(len(commands.readbacks), 1)
        applied_request, applied_plan = commands.applied[0]
        self.assertIs(applied_request, commands.planned[0])
        self.assertRegex(applied_plan.saved_plan_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(applied_plan.policy_digest, result.plan_digest)
        self.assertEqual(
            terminal.confirmations[0][1],
            f"APPLY foundation {result.plan_digest}",
        )
        displayed = "\n".join(terminal.messages)
        self.assertIn(result.plan_digest or "", displayed)
        self.assertIn('"phase":"platform-foundation"', displayed)
        self.assertNotIn("private saved plan", displayed)
        self.assertNotIn(str(applied_plan.saved_plan_path), displayed)

    def test_no_change_plan_skips_confirmation_and_apply_but_requires_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(root, actions=())
            terminal = FakeTerminal([])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context("bootstrap", ("backend-reference", "identity-reference"))
            )

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(terminal.confirmations, [])
        self.assertEqual(commands.applied, [])
        self.assertEqual(len(commands.readbacks), 1)

    def test_policy_refusal_never_confirms_applies_or_reads_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(root, wrong_project=True)
            terminal = FakeTerminal([])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context("shared-edge", ("edge-reference", "reserved-address"))
            )

        self.assertEqual(result.outcome, "failed")
        self.assertIn("PROJECT_MISMATCH", result.blockers)
        self.assertEqual(terminal.confirmations, [])
        self.assertEqual(commands.applied, [])
        self.assertEqual(commands.readbacks, [])

    def test_declined_confirmation_cancels_without_apply_or_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(root)
            terminal = FakeTerminal([False])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context("foundation", ("foundation-reference", "oauth-secret-container"))
            )

        self.assertEqual(result.outcome, "cancelled")
        self.assertEqual(result.blockers, ("PLAN_NOT_CONFIRMED",))
        self.assertEqual(commands.applied, [])
        self.assertEqual(commands.readbacks, [])

    def test_apply_failure_and_readback_discrepancy_stop_the_stage(self) -> None:
        cases = {
            "apply": ("PROVIDER_APPLY_FAILED", True, "PROVIDER_APPLY_FAILED"),
            "readback": (None, False, "TERRAFORM_READBACK_MISMATCH"),
        }
        for label, (apply_error, matches, blocker) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "work"
                root.mkdir(mode=0o700)
                commands = FakeCommands(
                    root,
                    apply_error=apply_error,
                    readback_matches=matches,
                )
                executor = DeploymentExecutor(root, FakeTerminal(), commands)

                result = executor.execute(
                    _context("foundation", ("foundation-reference", "oauth-secret-container"))
                )

                self.assertEqual(result.outcome, "failed")
                self.assertIn(blocker, result.blockers)

    def test_saved_plan_must_be_private_and_bounded(self) -> None:
        class UnsafeCommands(FakeCommands):
            def create_terraform_plan(self, request: object) -> TerraformPlanArtifact:
                artifact = super().create_terraform_plan(request)
                os.chmod(artifact.saved_plan_path, 0o644)
                return artifact

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = UnsafeCommands(root)
            executor = DeploymentExecutor(root, FakeTerminal([]), commands)

            result = executor.execute(
                _context("bootstrap", ("backend-reference", "identity-reference"))
            )

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.blockers, ("SAVED_PLAN_NOT_PRIVATE",))
        self.assertEqual(commands.applied, [])

    def test_production_refuses_before_any_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(root)
            executor = DeploymentExecutor(root, FakeTerminal([]), commands)
            context = _context(
                "bootstrap",
                ("backend-reference", "identity-reference"),
            )
            context = StageContext(
                environment="production",
                source_revision=context.source_revision,
                specification_digest=context.specification_digest,
                stage=context.stage,
                inputs=context.inputs,
            )

            result = executor.execute(context)

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.blockers, ("OWNERSHIP_TRANSFER_REQUIRED",))
        self.assertEqual(commands.planned, [])
        self.assertEqual(commands.applied, [])
        self.assertEqual(commands.readbacks, [])

    def test_terminal_receives_only_canonical_redacted_plan_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor, terminal, _ = self._executor(Path(directory) / "work")

            executor.execute(
                _context("foundation", ("foundation-reference", "oauth-secret-container"))
            )

        summary = json.loads(terminal.messages[0].split(" ", maxsplit=1)[1])
        self.assertEqual(summary["phase"], "platform-foundation")
        self.assertNotIn("before", summary)
        self.assertNotIn("after", summary)


if __name__ == "__main__":
    unittest.main()
