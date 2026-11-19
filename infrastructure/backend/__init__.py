"""Public AP-M9 Terraform-backend lifecycle interface."""

from infrastructure.backend._integration import (
    PhasePlanRequest,
    PhasePlanResult,
    TerraformPlanCommands,
    prepare_phase_plan,
)
from infrastructure.backend._lifecycle import (
    BackendDeclaration,
    EnvironmentUnavailableError,
    OperationAuthority,
    RenderedBackend,
    backend_declarations,
    operation_authorities,
    render_backend_declaration,
)
from infrastructure.backend._plans import (
    PlanPolicy,
    PlanPolicyResult,
    PlanViolation,
    evaluate_plan,
    plan_policy,
)

__all__ = (
    "BackendDeclaration",
    "EnvironmentUnavailableError",
    "OperationAuthority",
    "PhasePlanRequest",
    "PhasePlanResult",
    "PlanPolicy",
    "PlanPolicyResult",
    "PlanViolation",
    "RenderedBackend",
    "TerraformPlanCommands",
    "backend_declarations",
    "evaluate_plan",
    "operation_authorities",
    "plan_policy",
    "prepare_phase_plan",
    "render_backend_declaration",
)
