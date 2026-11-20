"""Exact-plan stage execution for the AP-M9 interactive deployment lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import stat
from pathlib import Path
from typing import Any, Protocol

from contracts.lifecycle import validate_lifecycle_material
from infrastructure.backend import (
    EnvironmentUnavailableError,
    PhasePlanRequest,
    TerraformPlanCommands,
    prepare_phase_plan,
)
from infrastructure.operator._interfaces import StageContext, StageExecution


@dataclass(frozen=True, slots=True)
class TerraformPlanArtifact:
    """Private saved plan plus its redacted, policy-checkable observation."""

    saved_plan_path: Path
    observation: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExactTerraformPlan:
    """One saved plan bound to its file digest and canonical policy digest."""

    saved_plan_path: Path
    saved_plan_digest: str
    policy_digest: str
    canonical_summary: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TerraformReadbackRequest:
    """Exact stage and phase context for state plus provider reconciliation."""

    stage_id: str
    phase: str
    environment: str
    source_revision: str
    specification_digest: str
    inputs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class TerraformReadback:
    """Closed non-secret outputs or fail-closed readback blockers."""

    matched: bool
    outputs: tuple[tuple[str, str], ...] = ()
    blockers: tuple[str, ...] = ()
    ready: bool = True


@dataclass(frozen=True, slots=True)
class StageReadback:
    """Provider-verified output for a non-Terraform stage."""

    matched: bool
    outputs: tuple[tuple[str, str], ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """Canonical non-secret proposal for one non-Terraform mutation."""

    action: str
    summary: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExactAction:
    """A proposed external action bound to its approved stage and digest."""

    action: str
    digest: str
    summary: dict[str, object]


@dataclass(frozen=True, slots=True)
class ManualCheckpoint:
    """Exact non-secret values displayed for one human provider action."""

    checkpoint: str
    instructions: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CheckpointVerification:
    """One bounded readback attempt following a human checkpoint."""

    outcome: str
    outputs: tuple[tuple[str, str], ...] = ()
    acknowledgement: str = "not-required"
    blockers: tuple[str, ...] = ()


class DeploymentCommandError(RuntimeError):
    """A safe blocker code returned by the external command boundary."""


class DeploymentTerminal(Protocol):
    def confirm(self, prompt: str) -> bool: ...

    def confirm_exact(self, prompt: str, expected: str) -> bool: ...

    def write(self, message: str) -> None: ...

    def pause(self, prompt: str) -> None: ...


class WaitAdapter(Protocol):
    def wait(self, seconds: int) -> None: ...


@dataclass(frozen=True, slots=True)
class _ImmediateWaiter:
    def wait(self, seconds: int) -> None:
        del seconds


class DeploymentCommands(Protocol):
    """Only seam allowed to create, apply, or read back a Terraform plan."""

    def create_terraform_plan(
        self,
        request: PhasePlanRequest,
    ) -> TerraformPlanArtifact: ...

    def apply_terraform_plan(
        self,
        request: PhasePlanRequest,
        plan: ExactTerraformPlan,
    ) -> None: ...

    def readback_terraform(
        self,
        request: TerraformReadbackRequest,
    ) -> TerraformReadback: ...

    def read_stage(self, context: StageContext) -> StageReadback: ...

    def prepare_action(self, context: StageContext) -> ActionProposal: ...

    def execute_action(self, context: StageContext, action: ExactAction) -> None: ...

    def readback_action(self, context: StageContext) -> StageReadback: ...

    def prepare_manual_checkpoint(self, context: StageContext) -> ManualCheckpoint: ...

    def verify_manual_checkpoint(
        self,
        context: StageContext,
        attempt: int,
    ) -> CheckpointVerification: ...


@dataclass
class _ArtifactObserver(TerraformPlanCommands):
    commands: DeploymentCommands
    request: PhasePlanRequest | None = None
    artifact: TerraformPlanArtifact | None = None

    def observe_plan(self, request: PhasePlanRequest) -> dict[str, object]:
        self.request = request
        self.artifact = self.commands.create_terraform_plan(request)
        return self.artifact.observation


_TERRAFORM_PHASES = {
    "bootstrap": "bootstrap",
    "foundation": "platform-foundation",
    "shared-edge": "shared-edge",
    "tls-readiness": "shared-edge",
}
_READ_ONLY_STAGES = {"preflight", "readback"}
_ACTION_STAGES = {"image-publish"}
_MANUAL_STAGES = {"oauth-configuration", "external-dns"}
_POLLING = {
    "external-dns": (12, 10),
    "tls-readiness": (30, 10),
}


class DeploymentExecutor:
    """Execute exact Terraform stages; later adapters add the non-Terraform stages."""

    def __init__(
        self,
        working_root: Path,
        terminal: DeploymentTerminal,
        commands: DeploymentCommands,
        *,
        waiter: WaitAdapter | None = None,
    ) -> None:
        self._working_root = working_root.resolve()
        self._terminal = terminal
        self._commands = commands
        self._waiter = waiter or _ImmediateWaiter()
        self._seen_saved_plans: set[Path] = set()
        if not self._working_root.is_dir():
            raise ValueError("deployment working root must already exist")
        if stat.S_IMODE(self._working_root.stat().st_mode) & 0o077:
            raise ValueError("deployment working root must be private")

    @staticmethod
    def _failure(*blockers: str) -> StageExecution:
        return StageExecution(
            outcome="failed",
            blockers=tuple(sorted(set(blockers))),
        )

    def _bind_saved_plan(
        self,
        artifact: TerraformPlanArtifact,
        policy_digest: str,
        summary: dict[str, Any],
    ) -> ExactTerraformPlan | StageExecution:
        path = artifact.saved_plan_path
        if path.is_symlink():
            return self._failure("SAVED_PLAN_PATH_INVALID")
        resolved = path.resolve()
        if (
            resolved == self._working_root
            or self._working_root not in resolved.parents
            or not resolved.is_file()
        ):
            return self._failure("SAVED_PLAN_PATH_INVALID")
        if stat.S_IMODE(resolved.stat().st_mode) & 0o077:
            return self._failure("SAVED_PLAN_NOT_PRIVATE")
        if resolved in self._seen_saved_plans:
            return self._failure("SAVED_PLAN_NOT_FRESH")
        self._seen_saved_plans.add(resolved)
        digest = f"sha256:{hashlib.sha256(resolved.read_bytes()).hexdigest()}"
        return ExactTerraformPlan(
            saved_plan_path=resolved,
            saved_plan_digest=digest,
            policy_digest=policy_digest,
            canonical_summary=summary,
        )

    @staticmethod
    def _requires_apply(summary: dict[str, Any]) -> bool:
        changes = summary.get("changes")
        assert isinstance(changes, list)
        return any(
            isinstance(change, dict)
            and isinstance(change.get("actions"), list)
            and any(
                action in {"create", "delete", "update"}
                for action in change["actions"]
            )
            for change in changes
        )

    @staticmethod
    def _expected_outputs(context: StageContext) -> tuple[str, ...]:
        produces = context.stage.get("produces")
        if not isinstance(produces, list):
            return ()
        return tuple(str(value) for value in produces)

    @staticmethod
    def _readback_result(
        context: StageContext,
        readback: StageReadback,
        *,
        plan_digest: str | None = None,
        acknowledgement: str = "not-required",
    ) -> StageExecution:
        if not readback.matched:
            return StageExecution(
                outcome="failed",
                plan_digest=plan_digest,
                blockers=readback.blockers or ("STAGE_READBACK_MISMATCH",),
            )
        expected = DeploymentExecutor._expected_outputs(context)
        if tuple(name for name, _ in readback.outputs) != expected:
            return StageExecution(
                outcome="failed",
                plan_digest=plan_digest,
                blockers=("STAGE_READBACK_OUTPUT_MISMATCH",),
            )
        return StageExecution(
            outcome="succeeded",
            outputs=readback.outputs,
            plan_digest=plan_digest,
            manual_acknowledgement=acknowledgement,
        )

    @staticmethod
    def _bound_digest(context: StageContext, value: object) -> str:
        bound = {
            "environment": context.environment,
            "inputs": [{"name": name, "value": item} for name, item in context.inputs],
            "source_revision": context.source_revision,
            "specification_digest": context.specification_digest,
            "stage": dict(context.stage),
            "value": value,
        }
        contents = json.dumps(
            bound,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(contents).hexdigest()}"

    @staticmethod
    def _safe_canonical(value: object) -> str | None:
        if validate_lifecycle_material(value):
            return None
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def _execute_read_only(self, context: StageContext) -> StageExecution:
        try:
            readback = self._commands.read_stage(context)
        except DeploymentCommandError as error:
            return self._failure(str(error))
        return self._readback_result(context, readback)

    def _execute_action(self, context: StageContext, stage_id: str) -> StageExecution:
        try:
            proposal = self._commands.prepare_action(context)
        except DeploymentCommandError as error:
            return self._failure(str(error))
        value = {"action": proposal.action, "summary": proposal.summary}
        canonical = self._safe_canonical(value)
        if canonical is None:
            return self._failure("PROHIBITED_ACTION_MATERIAL")
        digest = self._bound_digest(context, value)
        exact = ExactAction(proposal.action, digest, proposal.summary)
        self._terminal.write(f"ACTION {canonical}")
        self._terminal.write(f"ACTION_DIGEST {digest}")
        if not self._terminal.confirm(
            f"Execute the reviewed {stage_id} action {digest}? [y/N] "
        ):
            return StageExecution(
                outcome="cancelled",
                plan_digest=digest,
                blockers=("ACTION_NOT_CONFIRMED",),
            )
        try:
            self._commands.execute_action(context, exact)
            readback = self._commands.readback_action(context)
        except DeploymentCommandError as error:
            return StageExecution(
                outcome="failed",
                plan_digest=digest,
                blockers=(str(error),),
            )
        return self._readback_result(context, readback, plan_digest=digest)

    def _execute_manual(self, context: StageContext, stage_id: str) -> StageExecution:
        try:
            checkpoint = self._commands.prepare_manual_checkpoint(context)
        except DeploymentCommandError as error:
            return self._failure(str(error))
        expected_checkpoint = context.stage.get("manual_checkpoint")
        if checkpoint.checkpoint != expected_checkpoint:
            return self._failure("MANUAL_CHECKPOINT_SCOPE_MISMATCH")
        if len({name for name, _ in checkpoint.instructions}) != len(
            checkpoint.instructions
        ):
            return self._failure("MANUAL_CHECKPOINT_INVALID")
        value = {
            "checkpoint": checkpoint.checkpoint,
            "instructions": [
                {"name": name, "value": item}
                for name, item in checkpoint.instructions
            ],
        }
        canonical = self._safe_canonical(value)
        if canonical is None:
            return self._failure("PROHIBITED_CHECKPOINT_MATERIAL")
        digest = self._bound_digest(context, value)
        self._terminal.write(f"CHECKPOINT {canonical}")
        self._terminal.write(f"CHECKPOINT_DIGEST {digest}")
        if stage_id == "oauth-configuration":
            self._terminal.write(
                "Enter the OAuth client secret in Secret Manager directly; "
                "never enter it in this terminal."
            )
        self._terminal.pause(
            f"Complete checkpoint {checkpoint.checkpoint!r}, then Press Enter to verify: "
        )

        max_attempts, interval = _POLLING.get(stage_id, (1, 0))
        latest_blockers: tuple[str, ...] = ()
        for attempt in range(1, max_attempts + 1):
            try:
                verification = self._commands.verify_manual_checkpoint(
                    context,
                    attempt,
                )
            except DeploymentCommandError as error:
                return StageExecution(
                    outcome="failed",
                    plan_digest=digest,
                    blockers=(str(error),),
                )
            latest_blockers = verification.blockers
            if verification.outcome == "failed":
                return StageExecution(
                    outcome="failed",
                    plan_digest=digest,
                    blockers=latest_blockers or ("CHECKPOINT_READBACK_MISMATCH",),
                )
            if verification.outcome == "succeeded":
                if (
                    stage_id == "external-dns"
                    and verification.acknowledgement != "provider-verified"
                ):
                    return StageExecution(
                        outcome="failed",
                        plan_digest=digest,
                        blockers=("DNS_PROVIDER_VERIFICATION_REQUIRED",),
                    )
                return self._readback_result(
                    context,
                    StageReadback(True, verification.outputs),
                    plan_digest=digest,
                    acknowledgement=verification.acknowledgement,
                )
            if verification.outcome != "waiting":
                return StageExecution(
                    outcome="failed",
                    plan_digest=digest,
                    blockers=("CHECKPOINT_OUTCOME_INVALID",),
                )
            if attempt < max_attempts:
                self._waiter.wait(interval)
        return StageExecution(
            outcome="waiting",
            plan_digest=digest,
            blockers=tuple(
                sorted({*latest_blockers, "CHECKPOINT_POLL_EXHAUSTED"})
            ),
        )

    def _execute_terraform(
        self,
        context: StageContext,
        stage_id: str,
        phase: str,
    ) -> StageExecution:
        observer = _ArtifactObserver(self._commands)
        try:
            evaluated = prepare_phase_plan(
                context.environment,
                phase,
                context.source_revision,
                self._working_root,
                observer,
            )
        except EnvironmentUnavailableError as error:
            return self._failure(str(error))
        except DeploymentCommandError as error:
            return self._failure(str(error))

        if not evaluated.accepted:
            return self._failure(*(violation.code for violation in evaluated.violations))
        if (
            observer.request is None
            or observer.artifact is None
            or evaluated.plan_digest is None
            or evaluated.canonical_summary is None
        ):
            return self._failure("PLAN_BINDING_INCOMPLETE")

        exact_plan = self._bind_saved_plan(
            observer.artifact,
            evaluated.plan_digest,
            evaluated.canonical_summary,
        )
        if isinstance(exact_plan, StageExecution):
            return exact_plan

        canonical_summary = json.dumps(
            exact_plan.canonical_summary,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        self._terminal.write(f"PLAN {canonical_summary}")
        self._terminal.write(f"PLAN_DIGEST {exact_plan.policy_digest}")

        if self._requires_apply(exact_plan.canonical_summary):
            if not self._terminal.confirm(
                f"Apply the reviewed {stage_id} plan "
                f"{exact_plan.policy_digest}? [y/N] "
            ):
                return StageExecution(
                    outcome="cancelled",
                    plan_digest=exact_plan.policy_digest,
                    blockers=("PLAN_NOT_CONFIRMED",),
                )
            try:
                self._commands.apply_terraform_plan(observer.request, exact_plan)
            except DeploymentCommandError as error:
                return StageExecution(
                    outcome="failed",
                    plan_digest=exact_plan.policy_digest,
                    blockers=(str(error),),
                )

        request = TerraformReadbackRequest(
            stage_id=stage_id,
            phase=phase,
            environment=context.environment,
            source_revision=context.source_revision,
            specification_digest=context.specification_digest,
            inputs=context.inputs,
        )
        max_attempts, interval = _POLLING.get(stage_id, (1, 0))
        readback: TerraformReadback | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                readback = self._commands.readback_terraform(request)
            except DeploymentCommandError as error:
                return StageExecution(
                    outcome="failed",
                    plan_digest=exact_plan.policy_digest,
                    blockers=(str(error),),
                )
            if not readback.matched:
                blockers = readback.blockers or ("TERRAFORM_READBACK_MISMATCH",)
                return StageExecution(
                    outcome="failed",
                    plan_digest=exact_plan.policy_digest,
                    blockers=tuple(sorted(set(blockers))),
                )
            if readback.ready:
                break
            if attempt < max_attempts:
                self._waiter.wait(interval)
        assert readback is not None
        if not readback.ready:
            return StageExecution(
                outcome="waiting",
                plan_digest=exact_plan.policy_digest,
                blockers=tuple(
                    sorted({*readback.blockers, "TERRAFORM_READINESS_PENDING"})
                ),
            )
        output_names = tuple(name for name, _ in readback.outputs)
        if output_names != self._expected_outputs(context):
            return StageExecution(
                outcome="failed",
                plan_digest=exact_plan.policy_digest,
                blockers=("TERRAFORM_READBACK_OUTPUT_MISMATCH",),
            )
        return StageExecution(
            outcome="succeeded",
            outputs=readback.outputs,
            plan_digest=exact_plan.policy_digest,
        )

    def execute(self, context: StageContext) -> StageExecution:
        stage_id = str(context.stage.get("stage_id", ""))
        if context.environment == "production":
            return self._failure("OWNERSHIP_TRANSFER_REQUIRED")
        if stage_id in _READ_ONLY_STAGES:
            return self._execute_read_only(context)
        if stage_id in _ACTION_STAGES:
            return self._execute_action(context, stage_id)
        if stage_id in _MANUAL_STAGES:
            return self._execute_manual(context, stage_id)
        try:
            phase = _TERRAFORM_PHASES[stage_id]
        except KeyError:
            return self._failure("DEPLOYMENT_STAGE_UNAVAILABLE")
        return self._execute_terraform(context, stage_id, phase)


__all__ = (
    "ActionProposal",
    "CheckpointVerification",
    "DeploymentCommandError",
    "DeploymentCommands",
    "DeploymentExecutor",
    "DeploymentTerminal",
    "ExactAction",
    "ExactTerraformPlan",
    "ManualCheckpoint",
    "StageReadback",
    "TerraformPlanArtifact",
    "TerraformReadback",
    "TerraformReadbackRequest",
    "WaitAdapter",
)
