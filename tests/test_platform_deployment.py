"""AP-M9-W6 exact multi-stage deployment through deterministic command fakes."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator import (
    LifecycleOperator,
    OperatorAdapters,
    OperatorInterrupted,
    StageContext,
)
from infrastructure.operator.deployment import (
    ActionProposal,
    CheckpointVerification,
    DeploymentCommandError,
    DeploymentExecutor,
    ExactTerraformPlan,
    ManualCheckpoint,
    StageReadback,
    TerraformPlanArtifact,
    TerraformReadback,
)
from infrastructure.operator.local import LocalFilesystem
from tests.test_operator_lifecycle import (
    FakeDiscovery,
    FakeGit,
    FakeTerraform,
    FixedClock,
)


SOURCE_REVISION = "4" * 40
SPECIFICATION_DIGEST = "sha256:" + "5" * 64
GOOGLE_PROVIDER = "registry.terraform.io/hashicorp/google"
RESOURCE_TYPES = {
    "bootstrap": "google_storage_bucket",
    "platform-foundation": "google_storage_bucket",
    "shared-edge": "google_compute_global_address",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
            "manual_checkpoint": {
                "external-dns": "external-dns",
                "oauth-configuration": "provider-console",
            }.get(stage_id, "none"),
            "readback": "provider-verified",
        },
        inputs=(),
    )


@dataclass
class FakeTerminal:
    typed_approvals: list[bool] = field(default_factory=lambda: [True])
    approvals: list[bool] = field(default_factory=lambda: [True])
    confirmations: list[tuple[str, str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    pauses: list[str] = field(default_factory=list)
    answers: list[str] = field(
        default_factory=lambda: ["verified-client-id.apps.googleusercontent.com"]
    )
    questions: list[str] = field(default_factory=list)

    def ask(self, prompt: str) -> str:
        self.questions.append(prompt)
        return self.answers.pop(0)

    def confirm(self, prompt: str) -> bool:
        self.confirmations.append((prompt, "yes"))
        return self.approvals.pop(0)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.confirmations.append((prompt, expected))
        return self.typed_approvals.pop(0)

    def write(self, message: str) -> None:
        self.messages.append(message)

    def pause(self, prompt: str) -> None:
        self.pauses.append(prompt)


@dataclass
class FakeWaiter:
    delays: list[int] = field(default_factory=list)

    def wait(self, seconds: int) -> None:
        self.delays.append(seconds)


@dataclass
class FakeCommands:
    working_root: Path
    actions: tuple[str, ...] = ("create",)
    wrong_project: bool = False
    readback_matches: bool = True
    apply_error: str | DeploymentCommandError | None = None
    planned: list[object] = field(default_factory=list)
    applied: list[tuple[object, ExactTerraformPlan]] = field(default_factory=list)
    readbacks: list[object] = field(default_factory=list)
    stage_readback_matches: bool = True
    prepared_actions: list[StageContext] = field(default_factory=list)
    executed_actions: list[object] = field(default_factory=list)
    action_readbacks: list[StageContext] = field(default_factory=list)
    manual_preparations: list[StageContext] = field(default_factory=list)
    manual_verifications: list[
        tuple[StageContext, int, tuple[tuple[str, str], ...]]
    ] = field(default_factory=list)
    checkpoint_outcomes: list[str] = field(default_factory=lambda: ["succeeded"])
    terraform_readiness: list[bool] = field(default_factory=list)
    plan_errors: list[str | DeploymentCommandError] = field(default_factory=list)
    recovered_taints: list[str] = field(default_factory=list)

    def create_terraform_plan(
        self,
        context: StageContext,
        request: object,
    ) -> TerraformPlanArtifact:
        del context
        self.planned.append(request)
        if self.plan_errors:
            error = self.plan_errors.pop(0)
            if isinstance(error, DeploymentCommandError):
                raise error
            raise DeploymentCommandError(error)
        phase = str(getattr(request, "phase"))
        path = self.working_root / f"{phase}-{len(self.planned):04d}.tfplan"
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

    def signing_key_ring_recovery_identity(
        self,
        context: StageContext,
        request: object,
    ) -> str:
        del context, request
        return (
            "projects/comfforts-platform-non-prod/locations/us-west1/keyRings/"
            "app-platform"
        )

    def clear_signing_key_ring_taint(
        self,
        context: StageContext,
        request: object,
        identity: str,
    ) -> None:
        del context, request
        self.recovered_taints.append(identity)

    def apply_terraform_plan(
        self,
        request: object,
        plan: ExactTerraformPlan,
    ) -> None:
        self.applied.append((request, plan))
        if self.apply_error is not None:
            if isinstance(self.apply_error, DeploymentCommandError):
                raise self.apply_error
            raise DeploymentCommandError(self.apply_error)

    def readback_terraform(self, request: object) -> TerraformReadback:
        self.readbacks.append(request)
        stage_id = str(getattr(request, "stage_id"))
        outputs = {
            "bootstrap": (
                ("backend-reference", "verified-backend"),
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
        ready = self.terraform_readiness.pop(0) if self.terraform_readiness else True
        return TerraformReadback(
            matched=self.readback_matches,
            outputs=outputs,
            blockers=(
                ()
                if self.readback_matches and ready
                else ("CERTIFICATE_READINESS_PENDING",)
                if self.readback_matches
                else ("TERRAFORM_READBACK_MISMATCH",)
            ),
            ready=ready,
        )

    def read_stage(self, context: StageContext) -> StageReadback:
        stage_id = str(context.stage["stage_id"])
        outputs = {
            "preflight": (),
            "readback": (),
        }[stage_id]
        return StageReadback(
            matched=self.stage_readback_matches,
            outputs=outputs,
            blockers=() if self.stage_readback_matches else ("STAGE_READBACK_MISMATCH",),
        )

    def prepare_action(self, context: StageContext) -> ActionProposal:
        self.prepared_actions.append(context)
        if context.stage["stage_id"] == "bootstrap-services":
            return ActionProposal(
                action="enable-bootstrap-provider-services",
                summary={
                    "services": [
                        "serviceusage.googleapis.com",
                        "storage.googleapis.com",
                        "cloudresourcemanager.googleapis.com",
                    ]
                },
            )
        if context.stage["stage_id"] == "generation-publish":
            return ActionProposal(
                action="publish-initial-registration-generation",
                summary={
                    "generation": 1,
                    "generation_digest": "sha256:" + "b" * 64,
                },
            )
        return ActionProposal(
            action="publish-immutable-image",
            summary={
                "image": "us-west1-docker.pkg.dev/example/edge@sha256:" + "a" * 64,
                "identity": "ap-stg-platform-apply@example.iam.gserviceaccount.com",
            },
        )

    def execute_action(self, context: StageContext, action: object) -> None:
        self.executed_actions.append(action)

    def readback_action(self, context: StageContext) -> StageReadback:
        self.action_readbacks.append(context)
        if context.stage["stage_id"] == "bootstrap-services":
            return StageReadback(
                matched=True,
                outputs=(),
            )
        if context.stage["stage_id"] == "generation-publish":
            return StageReadback(
                matched=True,
                outputs=(("registration-generation-reference", "verified-generation"),),
            )
        return StageReadback(
            matched=True,
            outputs=(("shared-edge-image-digest", "sha256:" + "a" * 64),),
        )

    def prepare_manual_checkpoint(self, context: StageContext) -> ManualCheckpoint:
        self.manual_preparations.append(context)
        stage_id = str(context.stage["stage_id"])
        if stage_id == "oauth-configuration":
            return ManualCheckpoint(
                checkpoint="provider-console",
                instructions=(
                    ("application_name", "Comfforts Apps Staging"),
                    ("redirect_uri", "https://apps-staging.comfforts.com/oauth/callback"),
                    ("secret_manager_target", "projects/example/secrets/oauth-client"),
                ),
            )
        return ManualCheckpoint(
            checkpoint="external-dns",
            instructions=(
                ("record_type", "A"),
                ("hostname", "apps-staging.comfforts.com"),
                ("address", dict(context.inputs)["shared-edge.reserved-address"]),
                ("ttl_seconds", "300"),
            ),
        )

    def verify_manual_checkpoint(
        self,
        context: StageContext,
        attempt: int,
        supplied_inputs: tuple[tuple[str, str], ...],
    ) -> CheckpointVerification:
        self.manual_verifications.append((context, attempt, supplied_inputs))
        outcome = (
            self.checkpoint_outcomes.pop(0)
            if self.checkpoint_outcomes
            else "succeeded"
        )
        if outcome == "waiting":
            return CheckpointVerification(
                outcome="waiting",
                blockers=("DNS_PROPAGATION_PENDING",),
            )
        if outcome == "failed":
            return CheckpointVerification(
                outcome="failed",
                blockers=("CHECKPOINT_READBACK_MISMATCH",),
            )
        stage_id = str(context.stage["stage_id"])
        if stage_id == "oauth-configuration":
            supplied = dict(supplied_inputs)
            return CheckpointVerification(
                outcome="succeeded",
                outputs=(
                    ("oauth-client-id", supplied["oauth-client-id"]),
                    ("oauth-secret-version", "projects/example/secrets/oauth-client/versions/1"),
                ),
                acknowledgement="operator-attested",
            )
        return CheckpointVerification(
            outcome="succeeded",
            outputs=(),
            acknowledgement="provider-verified",
        )


class PlatformDeploymentTest(unittest.TestCase):
    def _executor(
        self,
        root: Path,
        *,
        terminal: FakeTerminal | None = None,
        commands: FakeCommands | None = None,
        waiter: FakeWaiter | None = None,
    ) -> tuple[DeploymentExecutor, FakeTerminal, FakeCommands]:
        root.mkdir(mode=0o700)
        selected_terminal = terminal or FakeTerminal()
        selected_commands = commands or FakeCommands(root)
        return (
            DeploymentExecutor(
                root,
                selected_terminal,
                selected_commands,
                waiter=waiter,
            ),
            selected_terminal,
            selected_commands,
        )

    def _lifecycle_operator(
        self,
        state_root: Path,
        terminal: FakeTerminal,
        executor: DeploymentExecutor,
        *,
        git: FakeGit | None = None,
    ) -> LifecycleOperator:
        return LifecycleOperator(
            OperatorAdapters(
                git=git or FakeGit(),
                github=FakeDiscovery(
                    "github",
                    (("repository", "comfforts/apps-platform"),),
                ),
                gcp=FakeDiscovery(
                    "gcp",
                    (
                        ("project_id", "comfforts-platform-non-prod"),
                        ("project_number", "455651441682"),
                        ("region", "us-west1"),
                    ),
                ),
                terraform=FakeTerraform(),
                dns=FakeDiscovery(
                    "dns",
                    (
                        ("provider_class", "squarespace-v1"),
                        ("hostname", "apps-staging.comfforts.com"),
                    ),
                ),
                terminal=terminal,
                filesystem=LocalFilesystem(PROJECT_ROOT, state_root),
                clock=FixedClock(),
                executor=executor,
            )
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
            "yes",
        )
        displayed = "\n".join(terminal.messages)
        self.assertIn(result.plan_digest or "", displayed)
        self.assertIn('"phase": "platform-foundation"', displayed)
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
                _context("bootstrap", ("backend-reference",))
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
            terminal = FakeTerminal(approvals=[False])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context("foundation", ("foundation-reference", "oauth-secret-container"))
            )

        self.assertEqual(result.outcome, "cancelled")
        self.assertEqual(result.blockers, ("PLAN_NOT_CONFIRMED",))
        self.assertEqual(commands.applied, [])
        self.assertEqual(commands.readbacks, [])

    def test_protected_signing_key_ring_taint_is_confirmed_repaired_and_replanned(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(
                root,
                plan_errors=["TERRAFORM_PROTECTED_SIGNING_KEY_RING_TAINTED"],
            )
            terminal = FakeTerminal(approvals=[True, True])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context(
                    "foundation",
                    ("foundation-reference", "oauth-secret-container"),
                )
            )

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(len(commands.planned), 2)
        self.assertEqual(len(commands.recovered_taints), 1)
        self.assertEqual(len(commands.applied), 1)
        self.assertIn("Clear only its Terraform taint marker", terminal.confirmations[0][0])
        self.assertIn(commands.recovered_taints[0], "\n".join(terminal.messages))

    def test_declined_signing_key_ring_recovery_preserves_tainted_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(
                root,
                plan_errors=["TERRAFORM_PROTECTED_SIGNING_KEY_RING_TAINTED"],
            )
            terminal = FakeTerminal(approvals=[False])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context(
                    "foundation",
                    ("foundation-reference", "oauth-secret-container"),
                )
            )

        self.assertEqual(result.outcome, "cancelled")
        self.assertEqual(
            result.blockers,
            ("TERRAFORM_PROTECTED_RESOURCE_RECOVERY_NOT_CONFIRMED",),
        )
        self.assertEqual(commands.recovered_taints, [])
        self.assertEqual(commands.applied, [])

    def test_apply_failure_and_readback_discrepancy_stop_the_stage(self) -> None:
        cases = {
            "apply": (
                DeploymentCommandError(
                    "TERRAFORM_APPLY_INVALID_ARGUMENT",
                    diagnostic={
                        "diagnostic_digest": "sha256:" + "b" * 64,
                        "diagnostic_path": (
                            "/private/operator/diagnostics/staging/"
                            "failure/stderr.log"
                        ),
                        "http_status": 400,
                        "operation": "creating Budget",
                        "resource_address": (
                            "module.platform_controls.google_billing_budget."
                            "qualification[0]"
                        ),
                    },
                ),
                True,
                "TERRAFORM_APPLY_INVALID_ARGUMENT",
            ),
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
                terminal = FakeTerminal()
                executor = DeploymentExecutor(root, terminal, commands)

                result = executor.execute(
                    _context("foundation", ("foundation-reference", "oauth-secret-container"))
                )

                self.assertEqual(result.outcome, "failed")
                self.assertIn(blocker, result.blockers)
                if label == "apply":
                    displayed = "\n".join(terminal.messages)
                    self.assertIn("TERRAFORM APPLY ERROR\n{", displayed)
                    self.assertIn('"http_status": 400', displayed)
                    self.assertIn(
                        '"resource_address": '
                        '"module.platform_controls.google_billing_budget.'
                        'qualification[0]"',
                        displayed,
                    )
                    self.assertIn(
                        "Private Terraform diagnostics may contain sensitive",
                        displayed,
                    )

    def test_plan_failure_reports_safe_operator_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(
                root,
                plan_errors=["TERRAFORM_STATE_LOCKED"],
            )
            terminal = FakeTerminal([])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context(
                    "foundation",
                    ("foundation-reference", "oauth-secret-container"),
                )
            )

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.blockers, ("TERRAFORM_STATE_LOCKED",))
        self.assertIn(
            "Terraform plan blocker TERRAFORM_STATE_LOCKED:",
            "\n".join(terminal.messages),
        )

    def test_plan_failure_reports_private_diagnostic_reference_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(
                root,
                plan_errors=[
                    DeploymentCommandError(
                        "TERRAFORM_PLAN_FAILED_UNKNOWN",
                        diagnostic={
                            "diagnostic_digest": "sha256:" + "a" * 64,
                            "diagnostic_path": (
                                "/private/operator/diagnostics/staging/"
                                "failure/stderr.log"
                            ),
                        },
                    )
                ],
            )
            terminal = FakeTerminal([])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context(
                    "foundation",
                    ("foundation-reference", "oauth-secret-container"),
                )
            )

        displayed = "\n".join(terminal.messages)
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.blockers, ("TERRAFORM_PLAN_FAILED_UNKNOWN",))
        self.assertIn("TERRAFORM PLAN ERROR\n{", displayed)
        self.assertIn('"diagnostic_digest": "sha256:', displayed)
        self.assertIn('"diagnostic_path": "/private/operator/', displayed)
        self.assertIn(
            "Private Terraform diagnostics may contain sensitive",
            displayed,
        )

    def test_saved_plan_must_be_private_and_bounded(self) -> None:
        class UnsafeCommands(FakeCommands):
            def create_terraform_plan(
                self,
                context: StageContext,
                request: object,
            ) -> TerraformPlanArtifact:
                artifact = super().create_terraform_plan(context, request)
                os.chmod(artifact.saved_plan_path, 0o644)
                return artifact

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = UnsafeCommands(root)
            executor = DeploymentExecutor(root, FakeTerminal([]), commands)

            result = executor.execute(
                _context("bootstrap", ("backend-reference",))
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
                ("backend-reference",),
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

        self.assertTrue(terminal.messages[0].startswith("PLAN\n{\n  \"changes\":"))
        summary = json.loads(terminal.messages[0].removeprefix("PLAN\n"))
        self.assertEqual(summary["phase"], "platform-foundation")
        self.assertNotIn("before", summary)
        self.assertNotIn("after", summary)

    def test_read_only_preflight_and_final_readback_close_only_on_exact_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor, _, commands = self._executor(Path(directory) / "work")

            preflight = executor.execute(
                _context("preflight", ())
            )
            final = executor.execute(
                _context("readback", ())
            )

        self.assertEqual(preflight.outcome, "succeeded")
        self.assertEqual(final.outcome, "succeeded")
        commands.stage_readback_matches = False

    def test_image_publication_uses_digest_bound_action_confirmation_and_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor, terminal, commands = self._executor(Path(directory) / "work")

            result = executor.execute(
                _context("image-publish", ("shared-edge-image-digest",))
            )

        self.assertEqual(result.outcome, "succeeded")
        self.assertRegex(result.plan_digest or "", r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(commands.executed_actions), 1)
        self.assertEqual(len(commands.action_readbacks), 1)
        self.assertEqual(
            terminal.confirmations[0][1],
            "yes",
        )
        self.assertTrue(
            terminal.messages[0].startswith("ACTION\n{\n  \"action\":")
        )
        self.assertIn("publish-immutable-image", "\n".join(terminal.messages))

    def test_bootstrap_service_readback_displays_verified_services(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor, terminal, _ = self._executor(Path(directory) / "work")

            result = executor.execute(_context("bootstrap-services", ()))

        self.assertEqual(result.outcome, "succeeded")
        readback = next(
            message for message in terminal.messages if message.startswith("READBACK\n")
        )
        self.assertEqual(
            json.loads(readback.removeprefix("READBACK\n")),
            {
                "services": [
                    {
                        "name": "serviceusage.googleapis.com",
                        "state": "enabled",
                    },
                    {"name": "storage.googleapis.com", "state": "enabled"},
                    {
                        "name": "cloudresourcemanager.googleapis.com",
                        "state": "enabled",
                    },
                ],
                "stage": "bootstrap-services",
            },
        )

    def test_oauth_checkpoint_displays_exact_values_pauses_and_never_receives_a_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor, terminal, commands = self._executor(Path(directory) / "work")

            result = executor.execute(
                _context(
                    "oauth-configuration",
                    ("oauth-client-id", "oauth-secret-version"),
                )
            )

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(result.manual_acknowledgement, "operator-attested")
        self.assertEqual(len(terminal.pauses), 1)
        self.assertIn("Press Enter", terminal.pauses[0])
        transcript = "\n".join([*terminal.messages, *terminal.pauses])
        self.assertIn("Comfforts Apps Staging", transcript)
        self.assertIn("Secret Manager directly", transcript)
        self.assertNotIn("client_secret", transcript)
        self.assertEqual(
            terminal.questions,
            ["Paste the OAuth client ID (never the client secret): "],
        )
        self.assertEqual(
            commands.manual_verifications[0][2],
            (("oauth-client-id", "verified-client-id.apps.googleusercontent.com"),),
        )
        self.assertEqual(len(commands.manual_verifications), 1)

    def test_dns_checkpoint_polls_authoritative_and_recursive_readback_with_a_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(
                root,
                checkpoint_outcomes=["waiting", "waiting", "succeeded"],
            )
            terminal = FakeTerminal()
            waiter = FakeWaiter()
            executor = DeploymentExecutor(
                root,
                terminal,
                commands,
                waiter=waiter,
            )
            context = _context("external-dns", ())
            context = StageContext(
                environment=context.environment,
                source_revision=context.source_revision,
                specification_digest=context.specification_digest,
                stage=context.stage,
                inputs=(("shared-edge.reserved-address", "192.0.2.10"),),
            )

            result = executor.execute(context)

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(result.manual_acknowledgement, "provider-verified")
        self.assertEqual(waiter.delays, [10, 10])
        self.assertEqual(
            [attempt for _, attempt, _ in commands.manual_verifications],
            [1, 2, 3],
        )
        transcript = "\n".join(terminal.messages)
        self.assertIn("apps-staging.comfforts.com", transcript)
        self.assertIn("192.0.2.10", transcript)

    def test_dns_poll_exhaustion_is_truthful_waiting_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(root, checkpoint_outcomes=["waiting"] * 12)
            executor = DeploymentExecutor(
                root,
                FakeTerminal(),
                commands,
                waiter=FakeWaiter(),
            )
            context = _context("external-dns", ())
            context = StageContext(
                environment=context.environment,
                source_revision=context.source_revision,
                specification_digest=context.specification_digest,
                stage=context.stage,
                inputs=(("shared-edge.reserved-address", "192.0.2.10"),),
            )

            result = executor.execute(context)

        self.assertEqual(result.outcome, "waiting")
        self.assertIn("CHECKPOINT_POLL_EXHAUSTED", result.blockers)
        self.assertEqual(len(commands.manual_verifications), 12)

    def test_tls_readiness_is_bounded_and_closes_only_after_provider_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = FakeCommands(
                root,
                terraform_readiness=[False, False, True],
            )
            waiter = FakeWaiter()
            executor = DeploymentExecutor(
                root,
                FakeTerminal(),
                commands,
                waiter=waiter,
            )

            result = executor.execute(
                _context("tls-readiness", ("certificate-reference",))
            )

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(waiter.delays, [10, 10])
        self.assertEqual(len(commands.readbacks), 3)

    def test_prohibited_checkpoint_or_action_material_is_never_displayed(self) -> None:
        class UnsafeActionCommands(FakeCommands):
            def prepare_action(self, context: StageContext) -> ActionProposal:
                return ActionProposal(
                    action="publish-immutable-image",
                    summary={"credential": "must-not-appear"},
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir(mode=0o700)
            commands = UnsafeActionCommands(root)
            terminal = FakeTerminal([])
            executor = DeploymentExecutor(root, terminal, commands)

            result = executor.execute(
                _context("image-publish", ("shared-edge-image-digest",))
            )

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.blockers, ("PROHIBITED_ACTION_MATERIAL",))
        self.assertEqual(terminal.messages, [])
        self.assertEqual(terminal.confirmations, [])

    def test_complete_first_deployment_transcript_and_no_change_are_truthful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            working_root = base / "work"
            working_root.mkdir(mode=0o700)
            state_root = base / "state"
            terminal = FakeTerminal(
                approvals=[True] * 8,
            )
            commands = FakeCommands(working_root)
            executor = DeploymentExecutor(
                working_root,
                terminal,
                commands,
                waiter=FakeWaiter(),
            )
            operator = self._lifecycle_operator(
                state_root,
                terminal,
                executor,
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            deployed = operator.execute("staging", prepared.specification_digest)
            call_counts = (
                len(commands.planned),
                len(commands.executed_actions),
                len(commands.manual_preparations),
            )
            unchanged = operator.execute("staging", prepared.specification_digest)

        self.assertEqual(deployed.outcome, "succeeded")
        assert deployed.progress is not None
        self.assertEqual(
            [entry["stage_id"] for entry in deployed.progress["completed"]],
            [
                "preflight",
                "bootstrap-services",
                "bootstrap",
                "foundation",
                "image-publish",
                "generation-publish",
                "oauth-configuration",
                "shared-edge",
                "external-dns",
                "tls-readiness",
                "readback",
            ],
        )
        self.assertEqual(call_counts, (4, 3, 2))
        self.assertEqual(unchanged.outcome, "unchanged")
        self.assertEqual(
            (
                len(commands.planned),
                len(commands.executed_actions),
                len(commands.manual_preparations),
            ),
            call_counts,
        )
        transcript = "\n".join(
            [
                *(prompt for prompt, _ in terminal.confirmations),
                *terminal.messages,
                *terminal.pauses,
            ]
        )
        self.assertIn("Comfforts Apps Staging", transcript)
        self.assertIn("apps-staging.comfforts.com", transcript)
        self.assertNotIn("oauth_client_secret", transcript)

    def test_interruption_resumes_without_repeating_any_closed_mutation(self) -> None:
        @dataclass
        class InterruptOnceTerminal(FakeTerminal):
            interrupt_once: bool = True

            def pause(self, prompt: str) -> None:
                super().pause(prompt)
                if self.interrupt_once:
                    self.interrupt_once = False
                    raise OperatorInterrupted()

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            working_root = base / "work"
            working_root.mkdir(mode=0o700)
            terminal = InterruptOnceTerminal(
                approvals=[True] * 8,
            )
            commands = FakeCommands(working_root)
            executor = DeploymentExecutor(
                working_root,
                terminal,
                commands,
                waiter=FakeWaiter(),
            )
            operator = self._lifecycle_operator(
                base / "state",
                terminal,
                executor,
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            interrupted = operator.execute("staging", prepared.specification_digest)
            closed_plan_count = len(commands.planned)
            closed_action_count = len(commands.executed_actions)
            resumed = operator.execute("staging", prepared.specification_digest)
            last_closed_stage = operator.status("staging").environment_status[
                "last_closed_stage"
            ]

        self.assertEqual(interrupted.outcome, "interrupted")
        self.assertEqual(closed_plan_count, 2)
        self.assertEqual(closed_action_count, 3)
        self.assertEqual(resumed.outcome, "succeeded")
        self.assertEqual(len(commands.planned), 4)
        self.assertEqual(len(commands.executed_actions), 3)
        self.assertEqual(last_closed_stage, "readback")


if __name__ == "__main__":
    unittest.main()
