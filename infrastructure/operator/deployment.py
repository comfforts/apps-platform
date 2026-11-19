"""Exact-plan stage execution for the AP-M9 interactive deployment lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import stat
from pathlib import Path
from typing import Any, Protocol

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


class DeploymentCommandError(RuntimeError):
    """A safe blocker code returned by the external command boundary."""


class DeploymentTerminal(Protocol):
    def confirm_exact(self, prompt: str, expected: str) -> bool: ...

    def write(self, message: str) -> None: ...


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


class DeploymentExecutor:
    """Execute exact Terraform stages; later adapters add the non-Terraform stages."""

    def __init__(
        self,
        working_root: Path,
        terminal: DeploymentTerminal,
        commands: DeploymentCommands,
    ) -> None:
        self._working_root = working_root.resolve()
        self._terminal = terminal
        self._commands = commands
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
            expected = f"APPLY {stage_id} {exact_plan.policy_digest}"
            if not self._terminal.confirm_exact(
                f"Type {expected!r} to apply the exact private plan: ",
                expected,
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

        try:
            readback = self._commands.readback_terraform(
                TerraformReadbackRequest(
                    stage_id=stage_id,
                    phase=phase,
                    environment=context.environment,
                    source_revision=context.source_revision,
                    specification_digest=context.specification_digest,
                    inputs=context.inputs,
                )
            )
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
        try:
            phase = _TERRAFORM_PHASES[stage_id]
        except KeyError:
            return self._failure("DEPLOYMENT_STAGE_UNAVAILABLE")
        return self._execute_terraform(context, stage_id, phase)


__all__ = (
    "DeploymentCommandError",
    "DeploymentCommands",
    "DeploymentExecutor",
    "DeploymentTerminal",
    "ExactTerraformPlan",
    "TerraformPlanArtifact",
    "TerraformReadback",
    "TerraformReadbackRequest",
)
