"""Public AP-M9 Terraform-backend lifecycle interface."""

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
    "PlanPolicy",
    "PlanPolicyResult",
    "PlanViolation",
    "RenderedBackend",
    "backend_declarations",
    "evaluate_plan",
    "operation_authorities",
    "plan_policy",
    "render_backend_declaration",
)
