"""Application handoff lifecycle behind deterministic injected readback seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from contracts.lifecycle import (
    lifecycle_digest,
    validate_lifecycle_document,
)


@dataclass(frozen=True, slots=True)
class PlatformIntegrationState:
    """Closed non-secret platform facts eligible for an application handoff."""

    environment: str
    lifecycle_state: str
    profile_digest: str
    platform_source_revision: str
    specification_digest: str
    journal_digest: str
    generation: int
    hostname: str
    oauth_client_id: str | None
    edge_caller_reference: str
    qualification_status: str


class PlatformIntegrationReader(Protocol):
    """Read the already-reconciled platform state without reading Application State."""

    def read_platform(self, environment: str) -> PlatformIntegrationState: ...


@dataclass(frozen=True, slots=True)
class IntegrationBundleRequest:
    """One application-scoped request bound to an expected platform revision."""

    environment: str
    application_id: str
    access_mode: str
    route_intent: str
    expected_platform_source_revision: str
    expected_generation: int


@dataclass(frozen=True, slots=True)
class IntegrationBundleResult:
    """Validated bundle output or a fail-closed blocker set."""

    outcome: str
    bundle: dict[str, Any] | None
    bundle_digest: str | None
    blockers: tuple[str, ...] = ()


class ApplicationIntegrationLifecycle:
    """Generate least-data application handoffs from exact platform readback."""

    def __init__(self, platform_reader: PlatformIntegrationReader) -> None:
        self._platform_reader = platform_reader

    @staticmethod
    def _blocked(*blockers: str) -> IntegrationBundleResult:
        return IntegrationBundleResult(
            outcome="blocked",
            bundle=None,
            bundle_digest=None,
            blockers=tuple(sorted(set(blockers))),
        )

    def outputs(self, request: IntegrationBundleRequest) -> IntegrationBundleResult:
        """Return one exact non-secret Platform Integration Bundle."""

        if request.access_mode not in {"public", "authenticated", "restricted"}:
            return self._blocked("ACCESS_MODE_UNSUPPORTED")

        state = self._platform_reader.read_platform(request.environment)
        if state.environment != request.environment:
            return self._blocked("PLATFORM_ENVIRONMENT_MISMATCH")
        if state.platform_source_revision != request.expected_platform_source_revision:
            return self._blocked("PLATFORM_SOURCE_MISMATCH")
        if state.generation != request.expected_generation:
            return self._blocked("PLATFORM_GENERATION_MISMATCH")
        if state.lifecycle_state != "deployed":
            return self._blocked("PLATFORM_NOT_DEPLOYED")

        protected = request.access_mode in {"authenticated", "restricted"}
        origin = f"https://{state.hostname}"
        bundle: dict[str, Any] = {
            "contract_version": 1,
            "document_kind": "platform-integration-bundle",
            "environment": request.environment,
            "application_id": request.application_id,
            "access_mode": request.access_mode,
            "route_intent": request.route_intent,
            "generation": state.generation,
            "profile_digest": state.profile_digest,
            "platform_source_revision": state.platform_source_revision,
            "specification_digest": state.specification_digest,
            "journal_digest": state.journal_digest,
            "endpoints": {
                "external_origin": origin,
                "issuer": f"{origin}/_platform" if protected else None,
                "jwks_uri": f"{origin}/.well-known/jwks.json" if protected else None,
                "oauth_redirect_uri": (
                    f"{origin}/_platform/auth/callback" if protected else None
                ),
            },
            "identity": {
                "oauth_client_id": state.oauth_client_id if protected else None,
                "audience": (
                    "urn:comfforts:app-platform:audience:"
                    f"{request.application_id}"
                    if protected
                    else None
                ),
                "edge_caller_reference": state.edge_caller_reference,
            },
            "attachment_contract": {
                "adapter_kind": "gcp-cloud-run-v1",
                "ingress_mode": "shared_edge_only",
            },
            "qualification_status": state.qualification_status,
        }
        if validate_lifecycle_document(bundle, "platform-integration-bundle"):
            return self._blocked("INTEGRATION_BUNDLE_INVALID")
        return IntegrationBundleResult(
            outcome="generated",
            bundle=bundle,
            bundle_digest=lifecycle_digest(
                bundle,
                "platform-integration-bundle",
            ),
        )


__all__ = (
    "ApplicationIntegrationLifecycle",
    "IntegrationBundleRequest",
    "IntegrationBundleResult",
    "PlatformIntegrationReader",
    "PlatformIntegrationState",
)
