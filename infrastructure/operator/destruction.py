"""Fail-closed AP-M9 environment-destruction specification compiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from contracts.lifecycle import (
    lifecycle_digest,
    validate_lifecycle_document,
    validate_lifecycle_material,
)
from infrastructure.operator._interfaces import (
    OperatorInterrupted,
    OperatorTerminal,
    StageContext,
    StageExecution,
)


DESTRUCTIBLE_PLATFORM_RESOURCES = (
    "artifact-registry",
    "budget",
    "dns-a-record",
    "load-balancer",
    "logging",
    "managed-certificate",
    "oauth-client",
    "oauth-secret-version",
    "platform-identity",
    "reserved-address",
    "secret-container",
    "session-store",
    "shared-edge",
    "shared-edge-image",
)

# These resources require separately approved purge or recovery authority.
RETAINED_PLATFORM_RESOURCES = (
    "backend-bucket",
    "configuration-bucket",
    "evidence-bucket",
    "logging-exclusion",
    "provider-service",
    "recovery-copy",
    "signing-key",
    "state-backend",
)


@dataclass(frozen=True, slots=True)
class DestructionRequest:
    """Exact reviewed revisions that one destruction operation must consume."""

    environment: str
    source_revision: str
    profile_digest: str
    deployed_specification_digest: str
    deployment_progress_digest: str
    registration_generation_digest: str
    qualification_evidence_digest: str
    source_authority: str = "accepted"


@dataclass(frozen=True, slots=True)
class DestructionSnapshot:
    """Current closed inventory read before a destructive spec can be prepared."""

    environment: str
    lifecycle_state: str
    source_revision: str
    profile_digest: str
    deployed_specification_digest: str
    deployment_progress_digest: str
    registration_generation_digest: str
    qualification_evidence_digest: str
    active_application_ids: tuple[str, ...]
    platform_resource_types: tuple[str, ...]
    retained_resource_types: tuple[str, ...]
    ownership_matches: bool
    source_authority: str = "accepted"


@dataclass(frozen=True, slots=True)
class DestructionPreparationResult:
    outcome: str
    specification: dict[str, Any] | None = None
    specification_digest: str | None = None
    blockers: tuple[str, ...] = ()


def _binding(stage_id: str, output_name: str) -> dict[str, str]:
    return {"stage_id": stage_id, "output_name": output_name}


def _destruction_stages() -> list[dict[str, object]]:
    """Return the only ordered deletion graph authorized by AP-M9-W8."""

    return [
        {
            "stage_id": "destruction-preflight",
            "actions": ["read"],
            "resource_types": [
                "ownership-inventory",
                "platform-environment",
                "registration-generation",
            ],
            "consumes": [],
            "produces": ["destruction-attestation"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "traffic-disable",
            "actions": ["read", "update"],
            "resource_types": ["shared-edge"],
            "consumes": [
                _binding("destruction-preflight", "destruction-attestation")
            ],
            "produces": ["traffic-disabled"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "traffic-drain",
            "actions": ["read"],
            "resource_types": ["cache-window", "shared-edge"],
            "consumes": [_binding("traffic-disable", "traffic-disabled")],
            "produces": ["cache-window-elapsed"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "external-dns-destroy",
            "actions": ["delete", "read"],
            "resource_types": ["dns-a-record"],
            "consumes": [_binding("traffic-drain", "cache-window-elapsed")],
            "produces": ["dns-removed"],
            "manual_checkpoint": "external-dns",
            "readback": "provider-verified",
        },
        {
            "stage_id": "edge-destroy",
            "actions": ["delete", "read"],
            "resource_types": [
                "load-balancer",
                "managed-certificate",
                "reserved-address",
                "shared-edge",
            ],
            "consumes": [_binding("external-dns-destroy", "dns-removed")],
            "produces": ["edge-destroyed"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "identity-destroy",
            "actions": ["delete", "read"],
            "resource_types": ["oauth-client"],
            "consumes": [_binding("edge-destroy", "edge-destroyed")],
            "produces": ["identity-destroyed"],
            "manual_checkpoint": "provider-console",
            "readback": "provider-verified",
        },
        {
            "stage_id": "foundation-destroy",
            "actions": ["delete", "read", "update"],
            "resource_types": [
                "artifact-registry",
                "budget",
                "logging",
                "oauth-secret-version",
                "platform-identity",
                "secret-container",
                "session-store",
                "shared-edge-image",
            ],
            "consumes": [_binding("identity-destroy", "identity-destroyed")],
            "produces": ["foundation-destroyed"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "destruction-readback",
            "actions": ["read"],
            "resource_types": ["ownership-inventory", "platform-environment"],
            "consumes": [
                _binding("foundation-destroy", "foundation-destroyed")
            ],
            "produces": ["destruction-complete"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
    ]


def _blockers(
    request: DestructionRequest,
    snapshot: DestructionSnapshot,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.environment != "staging":
        blockers.append("PRODUCTION_DESTRUCTION_UNAVAILABLE")
    comparisons = (
        (snapshot.environment, request.environment, "DESTRUCTION_ENVIRONMENT_MISMATCH"),
        (snapshot.source_revision, request.source_revision, "DESTRUCTION_SOURCE_MISMATCH"),
        (
            snapshot.source_authority,
            request.source_authority,
            "DESTRUCTION_SOURCE_AUTHORITY_MISMATCH",
        ),
        (snapshot.profile_digest, request.profile_digest, "DESTRUCTION_PROFILE_MISMATCH"),
        (
            snapshot.deployed_specification_digest,
            request.deployed_specification_digest,
            "DESTRUCTION_SPECIFICATION_MISMATCH",
        ),
        (
            snapshot.deployment_progress_digest,
            request.deployment_progress_digest,
            "DESTRUCTION_PROGRESS_MISMATCH",
        ),
        (
            snapshot.registration_generation_digest,
            request.registration_generation_digest,
            "DESTRUCTION_GENERATION_MISMATCH",
        ),
        (
            snapshot.qualification_evidence_digest,
            request.qualification_evidence_digest,
            "DESTRUCTION_EVIDENCE_MISMATCH",
        ),
    )
    blockers.extend(code for actual, expected, code in comparisons if actual != expected)
    if snapshot.lifecycle_state not in {"deployed", "destroying"}:
        blockers.append("ENVIRONMENT_NOT_DEPLOYED")
    if snapshot.active_application_ids:
        blockers.append("ACTIVE_APPLICATION_ATTACHMENTS")
    if not snapshot.ownership_matches:
        blockers.append("DESTRUCTION_OWNERSHIP_MISMATCH")
    if tuple(sorted(snapshot.platform_resource_types)) != DESTRUCTIBLE_PLATFORM_RESOURCES:
        blockers.append("DESTRUCTION_INVENTORY_MISMATCH")
    if tuple(sorted(snapshot.retained_resource_types)) != RETAINED_PLATFORM_RESOURCES:
        blockers.append("DESTRUCTION_RETAINED_INVENTORY_MISMATCH")
    return tuple(sorted(set(blockers)))


def compile_destruction_specification(
    request: DestructionRequest,
    snapshot: DestructionSnapshot,
) -> DestructionPreparationResult:
    """Compile one separate exact destroy spec, or return closed blocker codes."""

    blockers = _blockers(request, snapshot)
    if blockers:
        return DestructionPreparationResult(outcome="blocked", blockers=blockers)

    specification: dict[str, Any] = {
        "contract_version": 1,
        "document_kind": "deployment-specification",
        "environment": request.environment,
        "operation": "destroy",
        "profile_digest": request.profile_digest,
        "source": {
            "authority": request.source_authority,
            "repository": "comfforts/apps-platform",
            "revision": request.source_revision,
        },
        "stages": _destruction_stages(),
        "failure_behavior": "stop",
        "destructive_boundary": {
            "allowed": True,
            "resource_types": list(DESTRUCTIBLE_PLATFORM_RESOURCES),
        },
    }
    violations = validate_lifecycle_document(
        specification,
        "deployment-specification",
    )
    if violations:
        return DestructionPreparationResult(
            outcome="blocked",
            blockers=("DESTRUCTION_SPECIFICATION_INVALID",),
        )
    return DestructionPreparationResult(
        outcome="prepared",
        specification=specification,
        specification_digest=lifecycle_digest(
            specification,
            "deployment-specification",
        ),
    )


@dataclass(frozen=True, slots=True)
class DestructionStageClosure:
    """Minimal create-only progress for one provider-read-back stage."""

    stage_id: str
    outputs: tuple[tuple[str, str], ...]


class DestructionStateReader(Protocol):
    def read_current(self, environment: str) -> DestructionSnapshot: ...


class DestructionControl(Protocol):
    """Private specification, approval, and progress persistence boundary."""

    def publish_specification(
        self,
        environment: str,
        digest: str,
        specification: dict[str, object],
    ) -> bool: ...

    def approve_specification(self, environment: str, digest: str) -> bool: ...

    def closed_stages(
        self,
        environment: str,
        digest: str,
    ) -> tuple[DestructionStageClosure, ...]: ...

    def close_stage(
        self,
        environment: str,
        digest: str,
        closure: DestructionStageClosure,
    ) -> bool: ...

    def mark_complete(self, environment: str, digest: str) -> bool: ...


class DestructionExecutor(Protocol):
    def execute(self, context: StageContext) -> StageExecution: ...


@dataclass(frozen=True, slots=True)
class DestructionResult:
    outcome: str
    specification_digest: str | None
    last_closed_stage: str | None
    blockers: tuple[str, ...] = ()


class DestructionLifecycle:
    """Confirm and resume an exact safe-destruction specification."""

    def __init__(
        self,
        state_reader: DestructionStateReader,
        control: DestructionControl,
        terminal: OperatorTerminal,
        executor: DestructionExecutor,
    ) -> None:
        self._state_reader = state_reader
        self._control = control
        self._terminal = terminal
        self._executor = executor

    @staticmethod
    def _result(
        outcome: str,
        specification_digest: str | None,
        last_closed_stage: str | None,
        *blockers: str,
    ) -> DestructionResult:
        return DestructionResult(
            outcome=outcome,
            specification_digest=specification_digest,
            last_closed_stage=last_closed_stage,
            blockers=tuple(sorted(set(blockers))),
        )

    @staticmethod
    def _expected_outputs(stage: dict[str, Any]) -> tuple[str, ...]:
        produces = stage.get("produces")
        if not isinstance(produces, list):
            return ()
        return tuple(str(item) for item in produces)

    @classmethod
    def _valid_outputs(
        cls,
        stage: dict[str, Any],
        outputs: tuple[tuple[str, str], ...],
    ) -> bool:
        if tuple(name for name, _ in outputs) != cls._expected_outputs(stage):
            return False
        material = {
            "outputs": [
                {"output_name": name, "observed_value": value}
                for name, value in outputs
            ]
        }
        return not validate_lifecycle_material(material)

    @classmethod
    def _progress(
        cls,
        stages: list[dict[str, Any]],
        closures: tuple[DestructionStageClosure, ...],
    ) -> tuple[str | None, dict[tuple[str, str], str]] | None:
        if len(closures) > len(stages):
            return None
        outputs: dict[tuple[str, str], str] = {}
        for index, closure in enumerate(closures):
            stage = stages[index]
            stage_id = str(stage["stage_id"])
            if closure.stage_id != stage_id or not cls._valid_outputs(
                stage,
                closure.outputs,
            ):
                return None
            for name, value in closure.outputs:
                outputs[(stage_id, name)] = value
        last = closures[-1].stage_id if closures else None
        return last, outputs

    @staticmethod
    def _inputs(
        stage: dict[str, Any],
        outputs: dict[tuple[str, str], str],
    ) -> tuple[tuple[str, str], ...] | None:
        resolved: list[tuple[str, str]] = []
        consumes = stage.get("consumes")
        if not isinstance(consumes, list):
            return None
        for binding in consumes:
            if not isinstance(binding, dict):
                return None
            stage_id = binding.get("stage_id")
            output_name = binding.get("output_name")
            if not isinstance(stage_id, str) or not isinstance(output_name, str):
                return None
            key = (stage_id, output_name)
            if key not in outputs:
                return None
            resolved.append((f"{stage_id}.{output_name}", outputs[key]))
        return tuple(resolved)

    def destroy(self, request: DestructionRequest) -> DestructionResult:
        """Compile, freshly confirm, re-read, then resume ordered deletion."""

        try:
            initial = self._state_reader.read_current(request.environment)
        except Exception:
            return self._result(
                "blocked",
                None,
                None,
                "DESTRUCTION_READBACK_FAILED",
            )
        prepared = compile_destruction_specification(request, initial)
        digest = prepared.specification_digest
        specification = prepared.specification
        if prepared.outcome != "prepared" or digest is None or specification is None:
            return self._result("blocked", digest, None, *prepared.blockers)

        try:
            published = self._control.publish_specification(
                request.environment,
                digest,
                specification,
            )
        except Exception:
            published = False
        if not published:
            return self._result(
                "blocked",
                digest,
                None,
                "DESTRUCTION_SPECIFICATION_PUBLICATION_FAILED",
            )

        boundary = specification["destructive_boundary"]
        assert isinstance(boundary, dict)
        resources = boundary["resource_types"]
        assert isinstance(resources, list)
        try:
            self._terminal.write(
                f"DESTRUCTION_SCOPE {request.environment} {digest} "
                + ",".join(str(resource) for resource in resources)
            )
        except Exception:
            return self._result(
                "blocked",
                digest,
                None,
                "DESTRUCTION_SCOPE_DISPLAY_FAILED",
            )
        expected = f"DESTROY {request.environment} PLATFORM {digest}"
        try:
            confirmed = self._terminal.confirm_exact(
                f"Type {expected!r} to destroy only the displayed platform scope: ",
                expected,
            )
        except OperatorInterrupted:
            return self._result(
                "interrupted",
                digest,
                None,
                "DESTRUCTION_INTERRUPTED",
            )
        except Exception:
            return self._result(
                "blocked",
                digest,
                None,
                "DESTRUCTION_CONFIRMATION_FAILED",
            )
        if not confirmed:
            return self._result(
                "cancelled",
                digest,
                None,
                "DESTRUCTION_NOT_CONFIRMED",
            )

        # Re-read after human confirmation so a newly attached application or
        # ownership drift can never race the destructive operation.
        try:
            current = self._state_reader.read_current(request.environment)
        except Exception:
            return self._result(
                "blocked",
                digest,
                None,
                "DESTRUCTION_READBACK_FAILED",
            )
        current_preparation = compile_destruction_specification(request, current)
        if (
            current_preparation.outcome != "prepared"
            or current_preparation.specification_digest != digest
        ):
            return self._result(
                "blocked",
                digest,
                None,
                *(
                    current_preparation.blockers
                    or ("DESTRUCTION_SPECIFICATION_CHANGED",)
                ),
            )
        try:
            approved = self._control.approve_specification(
                request.environment,
                digest,
            )
        except Exception:
            approved = False
        if not approved:
            return self._result(
                "blocked",
                digest,
                None,
                "DESTRUCTION_APPROVAL_PERSISTENCE_FAILED",
            )

        stages_value = specification["stages"]
        assert isinstance(stages_value, list)
        stages = [stage for stage in stages_value if isinstance(stage, dict)]
        try:
            closures = self._control.closed_stages(request.environment, digest)
        except Exception:
            return self._result(
                "blocked",
                digest,
                None,
                "DESTRUCTION_PROGRESS_READ_FAILED",
            )
        progress = self._progress(stages, closures)
        if progress is None:
            return self._result(
                "blocked",
                digest,
                None,
                "DESTRUCTION_PROGRESS_INVALID",
            )
        last_closed, outputs = progress

        for stage in stages[len(closures) :]:
            inputs = self._inputs(stage, outputs)
            if inputs is None:
                return self._result(
                    "blocked",
                    digest,
                    last_closed,
                    "DESTRUCTION_STAGE_INPUT_INVALID",
                )
            context = StageContext(
                environment=request.environment,
                source_revision=request.source_revision,
                specification_digest=digest,
                stage=stage,
                inputs=inputs,
            )
            try:
                execution = self._executor.execute(context)
            except OperatorInterrupted:
                return self._result(
                    "interrupted",
                    digest,
                    last_closed,
                    "DESTRUCTION_INTERRUPTED",
                )
            except Exception:
                return self._result(
                    "failed",
                    digest,
                    last_closed,
                    "DESTRUCTION_STAGE_EXECUTION_FAILED",
                )
            if execution.outcome != "succeeded":
                outcome = (
                    execution.outcome
                    if execution.outcome in {"failed", "interrupted", "waiting"}
                    else "failed"
                )
                return self._result(
                    outcome,
                    digest,
                    last_closed,
                    *(execution.blockers or ("DESTRUCTION_STAGE_FAILED",)),
                )
            if execution.blockers or not self._valid_outputs(stage, execution.outputs):
                return self._result(
                    "failed",
                    digest,
                    last_closed,
                    "DESTRUCTION_STAGE_OUTPUT_MISMATCH",
                )
            closure = DestructionStageClosure(
                stage_id=str(stage["stage_id"]),
                outputs=execution.outputs,
            )
            try:
                closed = self._control.close_stage(
                    request.environment,
                    digest,
                    closure,
                )
            except Exception:
                closed = False
            if not closed:
                return self._result(
                    "blocked",
                    digest,
                    last_closed,
                    "DESTRUCTION_STAGE_CLOSE_FAILED",
                )
            last_closed = closure.stage_id
            for name, value in closure.outputs:
                outputs[(closure.stage_id, name)] = value

        try:
            completed = self._control.mark_complete(request.environment, digest)
        except Exception:
            completed = False
        if not completed:
            return self._result(
                "blocked",
                digest,
                last_closed,
                "DESTRUCTION_COMPLETION_FAILED",
            )
        return self._result("destroyed", digest, last_closed)

    def destroy_current(self, environment: str) -> DestructionResult:
        """Discover exact current bindings before entering confirmed destruction."""

        try:
            current = self._state_reader.read_current(environment)
        except Exception:
            return self._result(
                "blocked",
                None,
                None,
                "DESTRUCTION_READBACK_FAILED",
            )
        request = DestructionRequest(
            environment=environment,
            source_revision=current.source_revision,
            profile_digest=current.profile_digest,
            deployed_specification_digest=(
                current.deployed_specification_digest
            ),
            deployment_progress_digest=current.deployment_progress_digest,
            registration_generation_digest=(
                current.registration_generation_digest
            ),
            qualification_evidence_digest=(
                current.qualification_evidence_digest
            ),
            source_authority=current.source_authority,
        )
        return self.destroy(request)


__all__ = (
    "DESTRUCTIBLE_PLATFORM_RESOURCES",
    "RETAINED_PLATFORM_RESOURCES",
    "DestructionControl",
    "DestructionExecutor",
    "DestructionLifecycle",
    "DestructionPreparationResult",
    "DestructionRequest",
    "DestructionResult",
    "DestructionSnapshot",
    "DestructionStageClosure",
    "DestructionStateReader",
    "compile_destruction_specification",
)
