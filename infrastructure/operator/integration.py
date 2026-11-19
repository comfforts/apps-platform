"""Application handoff lifecycle behind deterministic injected readback seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from contracts.lifecycle import (
    lifecycle_digest,
    validate_lifecycle_document,
    validate_lifecycle_relationships,
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
class AttachmentTargetReadback:
    """Provider-observed attachment posture without Application State contents."""

    exists: bool
    ready: bool
    owner_application_id: str
    adapter_kind: str
    resource_reference: str
    ingress_mode: str
    caller_grant: str
    audience: str | None


class AttachmentTargetReader(Protocol):
    """Read one exact provider target and its ownership/IAM posture."""

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback: ...


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


@dataclass(frozen=True, slots=True)
class AttachmentValidationResult:
    """Validated attachment handoff or a fail-closed blocker set."""

    outcome: str
    attachment_bundle: dict[str, Any] | None
    blockers: tuple[str, ...] = ()


class ApplicationIntegrationLifecycle:
    """Generate least-data application handoffs from exact platform readback."""

    def __init__(
        self,
        platform_reader: PlatformIntegrationReader,
        *,
        attachment_reader: AttachmentTargetReader | None = None,
    ) -> None:
        self._platform_reader = platform_reader
        self._attachment_reader = attachment_reader

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

    @staticmethod
    def _attachment_blocked(*blockers: str) -> AttachmentValidationResult:
        return AttachmentValidationResult(
            outcome="blocked",
            attachment_bundle=None,
            blockers=tuple(sorted(set(blockers))),
        )

    @staticmethod
    def _matches_platform_state(
        bundle: dict[str, Any],
        state: PlatformIntegrationState,
    ) -> bool:
        identity = bundle.get("identity")
        protected = bundle.get("access_mode") in {"authenticated", "restricted"}
        return (
            state.lifecycle_state == "deployed"
            and bundle.get("environment") == state.environment
            and bundle.get("profile_digest") == state.profile_digest
            and bundle.get("platform_source_revision")
            == state.platform_source_revision
            and bundle.get("specification_digest") == state.specification_digest
            and bundle.get("journal_digest") == state.journal_digest
            and bundle.get("generation") == state.generation
            and bundle.get("qualification_status") == state.qualification_status
            and isinstance(identity, dict)
            and identity.get("edge_caller_reference")
            == state.edge_caller_reference
            and (
                not protected
                or identity.get("oauth_client_id") == state.oauth_client_id
            )
        )

    def validate_attachment(
        self,
        integration_bundle: dict[str, Any],
        attachment_bundle: dict[str, Any],
    ) -> AttachmentValidationResult:
        """Validate one application handoff and exact provider target posture."""

        if validate_lifecycle_document(
            integration_bundle,
            "platform-integration-bundle",
        ):
            return self._attachment_blocked("INTEGRATION_BUNDLE_INVALID")
        if validate_lifecycle_document(
            attachment_bundle,
            "application-attachment-bundle",
        ):
            return self._attachment_blocked("ATTACHMENT_BUNDLE_INVALID")
        if validate_lifecycle_relationships(
            integration_bundle=integration_bundle,
            attachment_bundle=attachment_bundle,
        ):
            return self._attachment_blocked("ATTACHMENT_BUNDLE_MISMATCH")

        environment = integration_bundle["environment"]
        assert isinstance(environment, str)
        state = self._platform_reader.read_platform(environment)
        if not self._matches_platform_state(integration_bundle, state):
            return self._attachment_blocked("PLATFORM_STATE_MISMATCH")
        if self._attachment_reader is None:
            return self._attachment_blocked("ATTACHMENT_READBACK_UNAVAILABLE")

        target = attachment_bundle["target"]
        assert isinstance(target, dict)
        resource_reference = target["resource_reference"]
        assert isinstance(resource_reference, str)
        try:
            readback = self._attachment_reader.read_target(
                environment,
                resource_reference,
            )
        except Exception:
            return self._attachment_blocked("TARGET_READBACK_FAILED")
        if not readback.exists:
            return self._attachment_blocked("TARGET_NOT_FOUND")
        if not readback.ready:
            return self._attachment_blocked("TARGET_NOT_READY")

        observed = (
            readback.owner_application_id,
            readback.adapter_kind,
            readback.resource_reference,
            readback.ingress_mode,
            readback.caller_grant,
            readback.audience,
        )
        expected = (
            target["owner_application_id"],
            target["adapter_kind"],
            target["resource_reference"],
            target["ingress_mode"],
            target["caller_grant"],
            target["audience"],
        )
        if observed != expected:
            return self._attachment_blocked("TARGET_POSTURE_MISMATCH")
        return AttachmentValidationResult(
            outcome="validated",
            attachment_bundle=attachment_bundle,
        )


__all__ = (
    "ApplicationIntegrationLifecycle",
    "AttachmentTargetReadback",
    "AttachmentTargetReader",
    "AttachmentValidationResult",
    "IntegrationBundleRequest",
    "IntegrationBundleResult",
    "PlatformIntegrationReader",
    "PlatformIntegrationState",
)
