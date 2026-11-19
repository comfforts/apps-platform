"""Credential-free composition of backend, identity, command, and plan policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from infrastructure.backend._lifecycle import (
    BackendDeclaration,
    backend_declarations,
    operation_authorities,
    render_backend_declaration,
)
from infrastructure.backend._plans import (
    PlanViolation,
    evaluate_plan,
    plan_policy,
)


@dataclass(frozen=True, slots=True)
class PhasePlanRequest:
    """Exact non-secret input to an injected Terraform plan command boundary."""

    environment: str
    source_revision: str
    phase: str
    terraform_root: str
    state_owner: str
    owner_id: str
    project_id: str
    backend_path: Path
    backend_digest: str
    backend_bucket: str
    backend_prefix: str
    service_account_email: str
    impersonation_environment: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PhasePlanResult:
    """Accepted canonical plan binding or ordered fail-closed violations."""

    phase: str
    accepted: bool
    backend_digest: str
    plan_digest: str | None
    violations: tuple[PlanViolation, ...]


class TerraformPlanCommands(Protocol):
    """The only W5 seam where a later package may observe a Terraform plan."""

    def observe_plan(self, request: PhasePlanRequest) -> dict[str, object]: ...


def _phase_declaration(environment: str, phase: str) -> BackendDeclaration:
    matches = tuple(
        value
        for value in backend_declarations(environment)
        if value.phase == phase
    )
    if len(matches) != 1:
        raise ValueError(f"unsupported Terraform phase {phase!r}")
    return matches[0]


def prepare_phase_plan(
    environment: str,
    phase: str,
    source_revision: str,
    working_root: Path,
    commands: TerraformPlanCommands,
) -> PhasePlanResult:
    """Render and policy-check one fake-observed phase plan without applying it."""

    declaration = _phase_declaration(environment, phase)
    authorities = tuple(
        value
        for value in operation_authorities(environment)
        if value.action == "plan"
        and value.terraform_root == declaration.terraform_root
        and value.backend_bucket == declaration.bucket
        and value.backend_prefix == declaration.prefix
    )
    if len(authorities) != 1:
        raise ValueError("phase has no unique plan authority")
    authority = authorities[0]
    rendered = render_backend_declaration(
        declaration,
        working_root,
        f"{phase}/backend.tf",
    )
    request = PhasePlanRequest(
        environment=environment,
        source_revision=source_revision,
        phase=phase,
        terraform_root=declaration.terraform_root,
        state_owner=declaration.state_owner,
        owner_id=declaration.owner_id,
        project_id=declaration.project_id,
        backend_path=rendered.path,
        backend_digest=rendered.digest,
        backend_bucket=declaration.bucket,
        backend_prefix=declaration.prefix,
        service_account_email=authority.service_account_email,
        impersonation_environment=authority.impersonation_environment,
    )
    observed = commands.observe_plan(request)
    result = evaluate_plan(
        plan_policy(
            environment,
            phase,
            source_revision,
            destructive=False,
        ),
        observed,
    )
    return PhasePlanResult(
        phase=phase,
        accepted=result.accepted,
        backend_digest=rendered.digest,
        plan_digest=result.plan_digest,
        violations=result.violations,
    )
