"""Public AP-M9 Terraform-backend lifecycle interface."""

from infrastructure.backend._lifecycle import (
    BackendDeclaration,
    EnvironmentUnavailableError,
    RenderedBackend,
    backend_declarations,
    render_backend_declaration,
)

__all__ = (
    "BackendDeclaration",
    "EnvironmentUnavailableError",
    "RenderedBackend",
    "backend_declarations",
    "render_backend_declaration",
)
