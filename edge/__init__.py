"""Public interface for the App Platform Shared Edge."""

from typing import TYPE_CHECKING

from .verification import (
    ApplicationIdentityVerifier,
    HttpJwksFetcher,
    VerificationResult,
    VerifiedIdentityContext,
)

if TYPE_CHECKING:
    from ._runtime import RuntimeAdapters, RuntimeConfiguration, create_app


_RUNTIME_EXPORTS = frozenset(
    {
        "RuntimeAdapters",
        "RuntimeConfiguration",
        "create_app",
    }
)


def __getattr__(name: str) -> object:
    """Load platform-runtime exports only when a runtime consumer requests them.

    Application images import ``edge.verification`` from this package but do not
    package the platform-owned runtime or member-directory implementation.  Lazy
    runtime exports preserve the public ``edge`` construction API without making
    application-side verification import those platform-only dependencies.
    """

    if name not in _RUNTIME_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from ._runtime import RuntimeAdapters, RuntimeConfiguration, create_app

    exports = {
        "RuntimeAdapters": RuntimeAdapters,
        "RuntimeConfiguration": RuntimeConfiguration,
        "create_app": create_app,
    }
    value = exports[name]
    globals()[name] = value
    return value


__all__ = [
    "ApplicationIdentityVerifier",
    "HttpJwksFetcher",
    "RuntimeAdapters",
    "RuntimeConfiguration",
    "VerificationResult",
    "VerifiedIdentityContext",
    "create_app",
]
