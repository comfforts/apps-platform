"""Public AP-M9 Terraform-backend lifecycle interface."""

from infrastructure.backend._integration import (
    PhasePlanRequest,
    PhasePlanResult,
    TerraformPlanCommands,
    prepare_phase_plan,
)
from infrastructure.backend._identity_bootstrap import (
    IdentityBootstrapPlan,
    ImpersonationGrant,
    compile_identity_bootstrap_plan,
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
from infrastructure.backend._permissions import (
    OperationRoleBinding,
    operation_role_bindings,
)

__all__ = (
    "BackendDeclaration",
    "EnvironmentUnavailableError",
    "IdentityBootstrapPlan",
    "ImpersonationGrant",
    "OperationAuthority",
    "OperationRoleBinding",
    "PhasePlanRequest",
    "PhasePlanResult",
    "PlanPolicy",
    "PlanPolicyResult",
    "PlanViolation",
    "RenderedBackend",
    "TerraformPlanCommands",
    "backend_declarations",
    "compile_identity_bootstrap_plan",
    "evaluate_plan",
    "operation_authorities",
    "operation_role_bindings",
    "plan_policy",
    "prepare_phase_plan",
    "render_backend_declaration",
)
