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

__all__ = (
    "BackendDeclaration",
    "EnvironmentUnavailableError",
    "OperationAuthority",
    "RenderedBackend",
    "backend_declarations",
    "operation_authorities",
    "render_backend_declaration",
)
