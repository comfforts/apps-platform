"""Application handoff lifecycle behind deterministic injected readback seams."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Protocol

from contracts import compile_registration_set_v2, migrate_registration_set_v1_to_v2
from contracts.lifecycle import (
    validate_versioned_lifecycle_document,
    validate_versioned_lifecycle_relationships,
    versioned_lifecycle_digest,
)
from infrastructure.config.project_identity import fixtures_project_id
from infrastructure.operator._interfaces import OperatorInterrupted, OperatorTerminal


@dataclass(frozen=True, slots=True)
class PlatformIntegrationState:
    """Closed non-secret platform facts eligible for an application handoff."""

    environment: str
    lifecycle_state: str
    profile_digest: str
    platform_source_revision: str
    specification_digest: str
    progress_digest: str
    generation: int
    hostname: str
    oauth_client_id: str | None
    edge_caller_reference: str
    qualification_status: str
    source_authority: str = "accepted"
    host_project_id: str = "comfforts-platform-non-prod"
    host_project_number: str = "455651441682"
    region: str = "us-west1"
    network_reference: str = (
        "projects/comfforts-platform-non-prod/global/networks/app-platform-shared"
    )
    subnetwork_reference: str = (
        "projects/comfforts-platform-non-prod/regions/us-west1/subnetworks/"
        "app-platform-applications-us-west1"
    )


class PlatformIntegrationReader(Protocol):
    """Read the already-reconciled platform state without reading Application State."""

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        """Return the selected environment's bounded platform integration facts."""
        ...


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
    application_project_id: str | None = None
    network_reference: str | None = None
    subnetwork_reference: str | None = None
    egress_mode: str | None = None
    blockers: tuple[str, ...] = ()


class AttachmentTargetReader(Protocol):
    """Read one exact provider target and its ownership/IAM posture."""

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback:
        """Return bounded posture for one exact target without reading Application State."""
        ...


@dataclass(frozen=True, slots=True)
class IntegrationBundleRequest:
    """One application-scoped request bound to an expected platform revision."""

    environment: str
    application_id: str
    access_mode: str
    identity_delivery: str
    route_intent: str
    expected_platform_source_revision: str
    expected_generation: int
    application_project_id: str = field(default_factory=fixtures_project_id)
    handoff_version: int = 2


@dataclass(frozen=True, slots=True)
class ApplicationProjectConnection:
    environment: str
    project_id: str
    project_number: str
    host_project_id: str
    host_project_number: str
    region: str
    network_reference: str
    subnetwork_reference: str
    egress_mode: str


class ApplicationProjectConnectionReader(Protocol):
    """Read the reviewed project-to-platform network connection facts."""

    def read_connection(
        self,
        environment: str,
        project_id: str,
    ) -> ApplicationProjectConnection:
        """Return one exact project connection selected by project identifier."""
        ...

    def read_project_number(
        self,
        environment: str,
        project_number: str,
    ) -> ApplicationProjectConnection:
        """Return one exact project connection selected by numeric identifier."""
        ...


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
    target_violations: tuple[AttachmentTargetViolation, ...] = ()


@dataclass(frozen=True, slots=True)
class AttachmentTargetViolation:
    """One redacted target failure keyed only by reviewed attachment ID and code."""

    attachment_id: str
    code: str


@dataclass(frozen=True, slots=True)
class RegistrationAttachmentBinding:
    """One additional V3 attachment's reviewed registration routing choices."""

    attachment_id: str
    mount_path: str
    forwarding_mode: str

    def document(self) -> dict[str, str]:
        """Return the closed contract representation without target or provider data."""

        return {
            "attachment_id": self.attachment_id,
            "mount_path": self.mount_path,
            "forwarding_mode": self.forwarding_mode,
        }


@dataclass(frozen=True, slots=True)
class RegistrationIntent:
    """Explicit platform-facing registration decisions absent from an attachment."""

    application_id: str
    access_mode: str
    identity_delivery: str
    catalogue_visibility: str
    catalogue_title: str
    catalogue_summary: str
    attachment_id: str
    mount_path: str
    forwarding_mode: str
    contract_version: int = 2
    additional_attachment_bindings: tuple[RegistrationAttachmentBinding, ...] = ()

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> RegistrationIntent:
        """Construct one intent only from a validated closed V2 or V3 document.

        The method performs no file, provider, or Application State access.  It
        revalidates the supplied mapping before projecting optional bindings so
        internal callers cannot accidentally accept a partial or mixed-version
        family.
        """

        if validate_versioned_lifecycle_document(value, "registration-intent"):
            raise ValueError("invalid registration intent")
        additional = value.get("additional_attachment_bindings", [])
        if not isinstance(additional, list) or any(
            not isinstance(item, dict) for item in additional
        ):
            raise ValueError("invalid registration intent")
        return cls(
            application_id=str(value["application_id"]),
            access_mode=str(value["access_mode"]),
            identity_delivery=str(value["identity_delivery"]),
            catalogue_visibility=str(value["catalogue_visibility"]),
            catalogue_title=str(value["catalogue_title"]),
            catalogue_summary=str(value["catalogue_summary"]),
            attachment_id=str(value["attachment_id"]),
            mount_path=str(value["mount_path"]),
            forwarding_mode=str(value["forwarding_mode"]),
            contract_version=int(value["contract_version"]),
            additional_attachment_bindings=tuple(
                RegistrationAttachmentBinding(
                    attachment_id=str(item["attachment_id"]),
                    mount_path=str(item["mount_path"]),
                    forwarding_mode=str(item["forwarding_mode"]),
                )
                for item in additional
            ),
        )

    def document(self) -> dict[str, object]:
        """Return the exact closed V2 or V3 lifecycle-contract document."""

        document: dict[str, object] = {
            "contract_version": self.contract_version,
            "document_kind": "registration-intent",
            "application_id": self.application_id,
            "access_mode": self.access_mode,
            "identity_delivery": self.identity_delivery,
            "catalogue_visibility": self.catalogue_visibility,
            "catalogue_title": self.catalogue_title,
            "catalogue_summary": self.catalogue_summary,
            "attachment_id": self.attachment_id,
            "mount_path": self.mount_path,
            "forwarding_mode": self.forwarding_mode,
        }
        if self.additional_attachment_bindings:
            document["additional_attachment_bindings"] = [
                binding.document()
                for binding in self.additional_attachment_bindings
            ]
        return document


@dataclass(frozen=True, slots=True)
class RegistrationEntry:
    """One validated application handoff selected for atomic suite registration."""

    integration_bundle: dict[str, Any]
    attachment_bundle: dict[str, Any]
    intent: RegistrationIntent


@dataclass(frozen=True, slots=True)
class RegistrationGenerationProposal:
    """One immutable whole-generation publication input."""

    environment: str
    registration_set: dict[str, Any]
    compiled_configuration: dict[str, Any]
    ownership_manifest: dict[str, Any]
    generation_digest: str
    content_digest: str


@dataclass(frozen=True, slots=True)
class GenerationPublicationReadback:
    """Create-only publication result and exact immutable readback."""

    created: bool
    publication_reference: str
    generation_digest: str
    content_digest: str
    readback_matches: bool


@dataclass(frozen=True, slots=True)
class GenerationActivationReadback:
    """Observed active whole-generation pointer after activation."""

    activated: bool
    active_generation_digest: str


class RegistrationGenerationControl(Protocol):
    """Injected immutable publication and active-pointer boundary."""

    def current(
        self,
        environment: str,
    ) -> RegistrationGenerationProposal | None:
        """Return the exact active generation or ``None`` when no generation exists."""
        ...

    def publish(
        self,
        proposal: RegistrationGenerationProposal,
    ) -> GenerationPublicationReadback:
        """Create one immutable generation and return exact bounded readback."""
        ...

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback:
        """Move the whole-generation pointer and return its exact active digest."""
        ...


@dataclass(frozen=True, slots=True)
class RegistrationLifecycleResult:
    """One complete registration lifecycle outcome."""

    outcome: str
    generation: int | None
    generation_digest: str | None
    blockers: tuple[str, ...] = ()
    target_violations: tuple[AttachmentTargetViolation, ...] = ()


@dataclass(frozen=True, slots=True)
class LifecycleChangeRequest:
    """Exact active-generation precondition for detach or retirement."""

    environment: str
    application_id: str
    expected_platform_source_revision: str
    expected_generation_digest: str


@dataclass(frozen=True, slots=True)
class RegistrationApplicationStatus:
    """Read-only registration policy and provider target status for one app."""

    application_id: str
    lifecycle: str
    catalogue_visibility: str
    resource_reference: str
    target_exists: bool
    target_ready: bool
    attachments: tuple[RegistrationAttachmentStatus, ...] = ()


@dataclass(frozen=True, slots=True)
class RegistrationAttachmentStatus:
    """Read-only provider posture for one attachment in an active registration."""

    attachment_id: str
    resource_reference: str
    target_exists: bool
    target_ready: bool


@dataclass(frozen=True, slots=True)
class RegistrationStatusResult:
    """Registration-generation status for an exact requested application set."""

    outcome: str
    generation: int | None
    generation_digest: str | None
    applications: tuple[RegistrationApplicationStatus, ...]
    blockers: tuple[str, ...] = ()
    target_violations: tuple[AttachmentTargetViolation, ...] = ()


class ApplicationIntegrationLifecycle:
    """Generate least-data application handoffs from exact platform readback."""

    def __init__(
        self,
        platform_reader: PlatformIntegrationReader,
        *,
        attachment_reader: AttachmentTargetReader | None = None,
        generation_control: RegistrationGenerationControl | None = None,
        project_connections: ApplicationProjectConnectionReader | None = None,
        terminal: OperatorTerminal | None = None,
    ) -> None:
        """Bind provider-neutral orchestration to explicit read and mutation seams."""

        self._platform_reader = platform_reader
        self._attachment_reader = attachment_reader
        self._generation_control = generation_control
        self._project_connections = (
            project_connections
            if project_connections is not None
            else (
                platform_reader
                if hasattr(platform_reader, "read_connection")
                else None
            )
        )
        self._terminal = terminal

    @staticmethod
    def _blocked(*blockers: str) -> IntegrationBundleResult:
        """Return one deduplicated fail-closed integration-bundle result."""

        return IntegrationBundleResult(
            outcome="blocked",
            bundle=None,
            bundle_digest=None,
            blockers=tuple(sorted(set(blockers))),
        )

    def outputs(self, request: IntegrationBundleRequest) -> IntegrationBundleResult:
        """Return one exact non-secret V2 or explicitly selected V3 bundle.

        The request performs only bounded platform and project-connection reads. V2 remains the
        default compatibility path; V3 adds the complete attachment-set limits but no target,
        publication, activation, Application State read, or application deployment.
        """

        if request.handoff_version not in {2, 3}:
            return self._blocked("HANDOFF_VERSION_UNSUPPORTED")
        if request.access_mode not in {"public", "authenticated", "restricted"}:
            return self._blocked("ACCESS_MODE_UNSUPPORTED")
        allowed_identity_delivery = {
            ("public", "none"),
            ("public", "optional"),
            ("authenticated", "required"),
            ("restricted", "required"),
        }
        if (request.access_mode, request.identity_delivery) not in allowed_identity_delivery:
            return self._blocked("IDENTITY_DELIVERY_UNSUPPORTED")

        try:
            state = self._platform_reader.read_platform(request.environment)
        except Exception:
            return self._blocked("PLATFORM_READBACK_FAILED")
        if state.environment != request.environment:
            return self._blocked("PLATFORM_ENVIRONMENT_MISMATCH")
        if state.platform_source_revision != request.expected_platform_source_revision:
            return self._blocked("PLATFORM_SOURCE_MISMATCH")
        if state.generation != request.expected_generation:
            return self._blocked("PLATFORM_GENERATION_MISMATCH")
        if state.lifecycle_state != "deployed":
            return self._blocked("PLATFORM_NOT_DEPLOYED")
        if self._project_connections is None:
            return self._blocked("APPLICATION_PROJECT_CONNECTION_UNAVAILABLE")
        try:
            connection = self._project_connections.read_connection(
                request.environment,
                request.application_project_id,
            )
        except (OSError, ValueError):
            return self._blocked("APPLICATION_PROJECT_NOT_CONNECTED")
        if (
            connection.host_project_id != state.host_project_id
            or connection.host_project_number != state.host_project_number
            or connection.region != state.region
            or connection.network_reference != state.network_reference
            or connection.subnetwork_reference != state.subnetwork_reference
            or connection.egress_mode != "all-traffic"
        ):
            return self._blocked("APPLICATION_PROJECT_CONNECTION_MISMATCH")

        identity_enabled = request.identity_delivery in {"optional", "required"}
        origin = f"https://{state.hostname}"
        bundle: dict[str, Any] = {
            "contract_version": request.handoff_version,
            "document_kind": "platform-integration-bundle",
            "environment": request.environment,
            "application_id": request.application_id,
            "access_mode": request.access_mode,
            "identity_delivery": request.identity_delivery,
            "route_intent": request.route_intent,
            "generation": state.generation,
            "profile_digest": state.profile_digest,
            "platform_source_revision": state.platform_source_revision,
            "platform_source_authority": state.source_authority,
            "specification_digest": state.specification_digest,
            "deployment_progress_digest": state.progress_digest,
            "endpoints": {
                "external_origin": origin,
                "issuer": f"{origin}/_platform" if identity_enabled else None,
                "jwks_uri": f"{origin}/.well-known/jwks.json" if identity_enabled else None,
                "oauth_redirect_uri": (
                    f"{origin}/_platform/auth/callback" if identity_enabled else None
                ),
            },
            "identity": {
                "oauth_client_id": state.oauth_client_id if identity_enabled else None,
                "audience": (
                    "urn:comfforts:app-platform:audience:"
                    f"{request.application_id}"
                    if identity_enabled
                    else None
                ),
                "edge_caller_reference": state.edge_caller_reference,
            },
            "application_project": {
                "project_id": connection.project_id,
                "project_number": connection.project_number,
            },
            "network": {
                "host_project_id": connection.host_project_id,
                "host_project_number": connection.host_project_number,
                "region": connection.region,
                "network_reference": connection.network_reference,
                "subnetwork_reference": connection.subnetwork_reference,
                "egress_mode": connection.egress_mode,
            },
            "attachment_contract": {
                "adapter_kind": "gcp-cloud-run-v1",
                "ingress_mode": "shared_edge_only",
            },
            "qualification_status": state.qualification_status,
        }
        if request.handoff_version == 3:
            bundle["attachment_contract"].update(
                {
                    "maximum_additional_attachments": 15,
                    "root_attachment_required": True,
                }
            )
        if validate_versioned_lifecycle_document(bundle, "platform-integration-bundle"):
            return self._blocked("INTEGRATION_BUNDLE_INVALID")
        return IntegrationBundleResult(
            outcome="generated",
            bundle=bundle,
            bundle_digest=versioned_lifecycle_digest(
                bundle,
                "platform-integration-bundle",
            ),
        )

    @staticmethod
    def _attachment_blocked(
        *blockers: str,
        target_violations: tuple[AttachmentTargetViolation, ...] = (),
    ) -> AttachmentValidationResult:
        """Return one fail-closed attachment result with redacted target details."""

        return AttachmentValidationResult(
            outcome="blocked",
            attachment_bundle=None,
            blockers=tuple(sorted(set(blockers))),
            target_violations=target_violations,
        )

    @staticmethod
    def _matches_platform_state(
        bundle: dict[str, Any],
        state: PlatformIntegrationState,
    ) -> bool:
        """Compare a handoff only with bounded current platform integration facts."""

        identity = bundle.get("identity")
        identity_enabled = bundle.get("identity_delivery") in {"optional", "required"}
        return (
            state.lifecycle_state == "deployed"
            and bundle.get("environment") == state.environment
            and bundle.get("profile_digest") == state.profile_digest
            and bundle.get("platform_source_revision")
            == state.platform_source_revision
            and bundle.get("platform_source_authority")
            == state.source_authority
            and bundle.get("specification_digest") == state.specification_digest
            and bundle.get("deployment_progress_digest") == state.progress_digest
            and bundle.get("generation") == state.generation
            and bundle.get("qualification_status") == state.qualification_status
            and isinstance(identity, dict)
            and identity.get("edge_caller_reference")
            == state.edge_caller_reference
            and (
                not identity_enabled
                or identity.get("oauth_client_id") == state.oauth_client_id
            )
        )

    @staticmethod
    def _attachment_targets(
        attachment_bundle: dict[str, Any],
        intent: RegistrationIntent | None,
    ) -> tuple[tuple[str, dict[str, Any]], ...]:
        """Normalize a validated V2/V3 bundle into root-first target entries.

        V3 additional entries retain canonical attachment-ID order established by the lifecycle
        contract. The returned values contain no provider observations and are used only after the
        source documents have passed their closed schemas.
        """

        target = attachment_bundle["target"]
        assert isinstance(target, dict)
        root_id = intent.attachment_id if intent is not None else "root"
        targets: list[tuple[str, dict[str, Any]]] = [(root_id, target)]
        additional = attachment_bundle.get("additional_attachments")
        if isinstance(additional, list):
            for entry in additional:
                assert isinstance(entry, dict)
                additional_target = entry["target"]
                assert isinstance(additional_target, dict)
                targets.append((str(entry["attachment_id"]), additional_target))
        return tuple(targets)

    @staticmethod
    def _relationship_target_violations(
        violations: tuple[Any, ...],
        attachment_bundle: dict[str, Any],
        intent: RegistrationIntent | None,
    ) -> tuple[AttachmentTargetViolation, ...]:
        """Project contract target violations into approved IDs and stable codes only."""

        if intent is None:
            return ()
        additional = attachment_bundle.get("additional_attachments")
        codes_by_attachment: dict[str, set[str]] = {}
        for violation in violations:
            attachment_id: str | None = None
            if str(violation.path).startswith("/attachment_bundle/target"):
                attachment_id = intent.attachment_id
            elif str(violation.path).startswith(
                "/attachment_bundle/additional_attachments/"
            ):
                parts = str(violation.path).split("/")
                try:
                    index = int(parts[3])
                    entry = additional[index] if isinstance(additional, list) else None
                except (IndexError, TypeError, ValueError):
                    entry = None
                if isinstance(entry, dict) and isinstance(
                    entry.get("attachment_id"), str
                ):
                    attachment_id = str(entry["attachment_id"])
            if attachment_id is not None:
                codes_by_attachment.setdefault(attachment_id, set()).add(
                    str(violation.code)
                )
        return tuple(
            AttachmentTargetViolation(attachment_id, code)
            for attachment_id, _target in ApplicationIntegrationLifecycle._attachment_targets(
                attachment_bundle,
                intent,
            )
            for code in sorted(codes_by_attachment.get(attachment_id, ()))
        )

    @staticmethod
    def _target_posture_blockers(
        target: dict[str, Any],
        integration_bundle: dict[str, Any],
    ) -> tuple[str, ...]:
        """Return stable handoff relationship blockers for one validated target."""

        application_project = integration_bundle["application_project"]
        network = integration_bundle["network"]
        identity = integration_bundle["identity"]
        attachment_contract = integration_bundle["attachment_contract"]
        assert isinstance(application_project, dict)
        assert isinstance(network, dict)
        assert isinstance(identity, dict)
        assert isinstance(attachment_contract, dict)
        expected_reference_prefix = (
            "urn:comfforts:app-platform:gcp:cloud-run:"
            f"{application_project['project_number']}:{network['region']}:"
        )
        comparisons = (
            (
                target["application_project_id"],
                application_project["project_id"],
                "ATTACHMENT_PROJECT_MISMATCH",
            ),
            (
                str(target["resource_reference"]).startswith(
                    expected_reference_prefix
                ),
                True,
                "ATTACHMENT_REFERENCE_MISMATCH",
            ),
            (
                target["network_reference"],
                network["network_reference"],
                "ATTACHMENT_NETWORK_MISMATCH",
            ),
            (
                target["subnetwork_reference"],
                network["subnetwork_reference"],
                "ATTACHMENT_SUBNETWORK_MISMATCH",
            ),
            (
                target["egress_mode"],
                network["egress_mode"],
                "ATTACHMENT_EGRESS_MISMATCH",
            ),
            (
                target["adapter_kind"],
                attachment_contract["adapter_kind"],
                "ATTACHMENT_ADAPTER_MISMATCH",
            ),
            (
                target["ingress_mode"],
                attachment_contract["ingress_mode"],
                "ATTACHMENT_INGRESS_MISMATCH",
            ),
            (
                target["caller_grant"],
                identity["edge_caller_reference"],
                "ATTACHMENT_CALLER_MISMATCH",
            ),
            (
                target["audience"],
                identity["audience"],
                "ATTACHMENT_AUDIENCE_MISMATCH",
            ),
        )
        return tuple(
            blocker
            for observed, expected, blocker in comparisons
            if observed != expected
        )

    @staticmethod
    def _provider_target_blockers(
        target: dict[str, Any],
        readback: AttachmentTargetReadback,
    ) -> tuple[str, ...]:
        """Compare one provider readback with its declared target without leaking payloads."""

        if not readback.exists:
            return ("TARGET_NOT_FOUND",)
        blockers = list(readback.blockers)
        if not readback.ready:
            blockers.append("TARGET_NOT_READY")
        comparisons = (
            (
                readback.owner_application_id,
                target["owner_application_id"],
                "TARGET_OWNER_MISMATCH",
            ),
            (
                readback.adapter_kind,
                target["adapter_kind"],
                "TARGET_ADAPTER_MISMATCH",
            ),
            (
                readback.resource_reference,
                target["resource_reference"],
                "TARGET_REFERENCE_MISMATCH",
            ),
            (
                readback.ingress_mode,
                target["ingress_mode"],
                "TARGET_INGRESS_MISMATCH",
            ),
            (
                readback.caller_grant,
                target["caller_grant"],
                "TARGET_CALLER_GRANT_MISMATCH",
            ),
            (
                readback.application_project_id,
                target["application_project_id"],
                "TARGET_PROJECT_MISMATCH",
            ),
            (
                readback.network_reference,
                target["network_reference"],
                "TARGET_NETWORK_MISMATCH",
            ),
            (
                readback.subnetwork_reference,
                target["subnetwork_reference"],
                "TARGET_SUBNETWORK_MISMATCH",
            ),
            (
                readback.egress_mode,
                target["egress_mode"],
                "TARGET_EGRESS_MISMATCH",
            ),
            (
                readback.audience,
                target["audience"],
                "TARGET_AUDIENCE_MISMATCH",
            ),
        )
        blockers.extend(
            blocker
            for observed, expected, blocker in comparisons
            if observed != expected
        )
        return tuple(sorted(set(blockers)))

    def validate_attachment(
        self,
        integration_bundle: dict[str, Any],
        attachment_bundle: dict[str, Any],
        intent: RegistrationIntent | None = None,
    ) -> AttachmentValidationResult:
        """Validate a complete handoff and read every declared target atomically.

        V2 remains a readable single-target compatibility path. V3 requires its registration
        intent so root and optional target IDs can be validated as one exact family. Every validly
        declared target is read before any failure is returned; failures expose only approved
        attachment IDs and stable codes, and this method has no publication or activation seam.
        """

        selected_version = integration_bundle.get("contract_version")
        if selected_version not in {2, 3}:
            return self._attachment_blocked("INTEGRATION_BUNDLE_VERSION_UNSUPPORTED")
        if attachment_bundle.get("contract_version") != selected_version:
            return self._attachment_blocked("ATTACHMENT_BUNDLE_VERSION_UNSUPPORTED")
        if selected_version == 3 and intent is None:
            return self._attachment_blocked("REGISTRATION_INTENT_REQUIRED")
        if validate_versioned_lifecycle_document(
            integration_bundle,
            "platform-integration-bundle",
        ):
            return self._attachment_blocked("INTEGRATION_BUNDLE_INVALID")
        if validate_versioned_lifecycle_document(
            attachment_bundle,
            "application-attachment-bundle",
        ):
            return self._attachment_blocked("ATTACHMENT_BUNDLE_INVALID")
        intent_document = (
            intent.document()
            if selected_version == 3 and intent is not None
            else None
        )
        relationship_violations = validate_versioned_lifecycle_relationships(
            integration_bundle=integration_bundle,
            attachment_bundle=attachment_bundle,
            registration_intent=intent_document,
        )
        if relationship_violations:
            return self._attachment_blocked(
                "ATTACHMENT_BUNDLE_MISMATCH",
                target_violations=self._relationship_target_violations(
                    relationship_violations,
                    attachment_bundle,
                    intent,
                ),
            )

        targets = self._attachment_targets(attachment_bundle, intent)
        relationship_details = tuple(
            AttachmentTargetViolation(attachment_id, blocker)
            for attachment_id, target in targets
            for blocker in self._target_posture_blockers(
                target,
                integration_bundle,
            )
        )
        relationship_blockers = tuple(
            detail.code for detail in relationship_details
        )
        if relationship_blockers:
            return self._attachment_blocked(
                *relationship_blockers,
                target_violations=relationship_details,
            )

        environment = integration_bundle["environment"]
        assert isinstance(environment, str)
        try:
            state = self._platform_reader.read_platform(environment)
        except Exception:
            return self._attachment_blocked("PLATFORM_READBACK_FAILED")
        if not self._matches_platform_state(integration_bundle, state):
            return self._attachment_blocked("PLATFORM_STATE_MISMATCH")
        if self._attachment_reader is None:
            return self._attachment_blocked("ATTACHMENT_READBACK_UNAVAILABLE")

        target_violations: list[AttachmentTargetViolation] = []
        for attachment_id, target in targets:
            resource_reference = target["resource_reference"]
            assert isinstance(resource_reference, str)
            try:
                readback = self._attachment_reader.read_target(
                    environment,
                    resource_reference,
                )
            except Exception:
                blockers = ("TARGET_READBACK_FAILED",)
            else:
                blockers = self._provider_target_blockers(target, readback)
            target_violations.extend(
                AttachmentTargetViolation(attachment_id, blocker)
                for blocker in blockers
            )
        if target_violations:
            return self._attachment_blocked(
                *(detail.code for detail in target_violations),
                target_violations=tuple(target_violations),
            )
        return AttachmentValidationResult(
            outcome="validated",
            attachment_bundle=attachment_bundle,
        )

    @staticmethod
    def _registration_blocked(
        *blockers: str,
        outcome: str = "blocked",
        proposal: RegistrationGenerationProposal | None = None,
        target_violations: tuple[AttachmentTargetViolation, ...] = (),
    ) -> RegistrationLifecycleResult:
        """Return a fail-closed lifecycle result without publishing partial output."""

        return RegistrationLifecycleResult(
            outcome=outcome,
            generation=(
                int(proposal.registration_set["generation"])
                if proposal is not None
                else None
            ),
            generation_digest=(
                proposal.generation_digest if proposal is not None else None
            ),
            blockers=tuple(sorted(set(blockers))),
            target_violations=target_violations,
        )

    @staticmethod
    def _registration_intent_valid(
        integration_bundle: dict[str, Any],
        intent: RegistrationIntent,
    ) -> bool:
        """Require one valid same-version intent that repeats handoff policy."""

        return (
            intent.contract_version == integration_bundle.get("contract_version")
            and not validate_versioned_lifecycle_document(
                intent.document(),
                "registration-intent",
            )
            and intent.application_id == integration_bundle.get("application_id")
            and intent.access_mode == integration_bundle.get("access_mode")
            and intent.identity_delivery
            == integration_bundle.get("identity_delivery")
        )

    @staticmethod
    def _application_registration(
        integration_bundle: dict[str, Any],
        attachment_bundle: dict[str, Any],
        intent: RegistrationIntent,
        lifecycle: str,
        registration_revision: int,
    ) -> dict[str, Any]:
        """Project one validated V2/V3 handoff into the existing V2 registration."""

        access_mode = str(integration_bundle["access_mode"])
        identity_delivery = str(integration_bundle["identity_delivery"])
        identity = integration_bundle["identity"]
        target = attachment_bundle["target"]
        assert isinstance(identity, dict)
        assert isinstance(target, dict)
        targets_by_id = {
            str(entry["attachment_id"]): entry["target"]
            for entry in attachment_bundle.get("additional_attachments", [])
        }
        attachment_bindings = (
            RegistrationAttachmentBinding(
                intent.attachment_id,
                intent.mount_path,
                intent.forwarding_mode,
            ),
            *intent.additional_attachment_bindings,
        )
        registration_attachments: list[dict[str, Any]] = []
        for binding in attachment_bindings:
            selected_target = (
                target
                if binding.attachment_id == intent.attachment_id
                else targets_by_id[binding.attachment_id]
            )
            assert isinstance(selected_target, dict)
            registration_attachments.append(
                {
                    "contract_version": 2,
                    "owner_application_id": integration_bundle["application_id"],
                    "attachment_id": binding.attachment_id,
                    "adapter_kind": selected_target["adapter_kind"],
                    "resource_reference": selected_target["resource_reference"],
                    "mount_path": binding.mount_path,
                    "forwarding_mode": binding.forwarding_mode,
                    "identity_requirement": {
                        "none": "none",
                        "optional": "optional",
                        "required": "verified",
                    }[identity_delivery],
                    "audience": identity["audience"],
                    "ingress_mode": selected_target["ingress_mode"],
                }
            )
        registration_attachments.sort(key=lambda item: item["attachment_id"])
        return {
            "contract_version": 2,
            "application_id": integration_bundle["application_id"],
            "registration_revision": registration_revision,
            "route_prefix": integration_bundle["route_intent"],
            "catalogue": {
                "visibility": intent.catalogue_visibility,
                "title": intent.catalogue_title,
                "summary": intent.catalogue_summary,
            },
            "admission": {"mode": access_mode},
            "identity_delivery": identity_delivery,
            "lifecycle": lifecycle,
            "attachments": registration_attachments,
        }

    @staticmethod
    def _canonical_digest(value: object) -> str:
        """Return the deterministic digest used to bind compiled provider content."""

        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def _version_two_previous(
        previous: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Return the predecessor as V2 comparison data without changing its digest."""

        if previous is None:
            return None
        if previous.get("contract_version") == 2:
            return copy.deepcopy(previous)
        if previous.get("contract_version") == 1:
            migration = migrate_registration_set_v1_to_v2(previous)
            if migration.violations or migration.registration_set is None:
                return None
            return migration.registration_set
        return None

    @classmethod
    def _compile_generation(
        cls,
        environment: str,
        source_revision: str,
        current: RegistrationGenerationProposal | None,
        registration: dict[str, Any],
        change_summary: str,
    ) -> RegistrationGenerationProposal | None:
        """Compile one full successor while replacing exactly one application."""

        previous = current.registration_set if current is not None else None
        comparison_previous = cls._version_two_previous(previous)
        if previous is not None and comparison_previous is None:
            return None
        registrations = (
            copy.deepcopy(comparison_previous["registrations"])
            if comparison_previous is not None
            else []
        )
        registrations = [
            item
            for item in registrations
            if item["application_id"] != registration["application_id"]
        ]
        registrations.append(copy.deepcopy(registration))
        registrations.sort(key=lambda item: item["application_id"])
        registration_set = {
            "contract_version": 2,
            "generation": (
                int(previous["generation"]) + 1 if previous is not None else 1
            ),
            "previous_generation_digest": (
                current.generation_digest if current is not None else None
            ),
            "proposal": {
                "source_revision": source_revision,
                "change_summary": change_summary,
            },
            "registrations": registrations,
        }
        compilation = compile_registration_set_v2(
            previous,
            registration_set,
            {
                "contract_version": 2,
                "enabled_attachment_adapter_kinds": ["gcp-cloud-run-v1"],
            },
        )
        if (
            compilation.violations
            or compilation.compiled_configuration is None
            or compilation.ownership_manifest is None
            or compilation.generation_digest is None
        ):
            return None
        return RegistrationGenerationProposal(
            environment=environment,
            registration_set=registration_set,
            compiled_configuration=compilation.compiled_configuration,
            ownership_manifest=compilation.ownership_manifest,
            generation_digest=compilation.generation_digest,
            content_digest=cls._canonical_digest(compilation.compiled_configuration),
        )

    @classmethod
    def _compile_complete_generation(
        cls,
        environment: str,
        source_revision: str,
        current: RegistrationGenerationProposal | None,
        replacements: tuple[dict[str, Any], ...],
        change_summary: str,
    ) -> RegistrationGenerationProposal | None:
        """Compile one full successor while replacing a reviewed application set."""

        previous = current.registration_set if current is not None else None
        comparison_previous = cls._version_two_previous(previous)
        if previous is not None and comparison_previous is None:
            return None
        replacement_ids = {item["application_id"] for item in replacements}
        registrations = (
            [
                copy.deepcopy(item)
                for item in comparison_previous["registrations"]
                if item["application_id"] not in replacement_ids
            ]
            if comparison_previous is not None
            else []
        )
        registrations.extend(copy.deepcopy(item) for item in replacements)
        registrations.sort(key=lambda item: item["application_id"])
        registration_set = {
            "contract_version": 2,
            "generation": (
                int(previous["generation"]) + 1 if previous is not None else 1
            ),
            "previous_generation_digest": (
                current.generation_digest if current is not None else None
            ),
            "proposal": {
                "source_revision": source_revision,
                "change_summary": change_summary,
            },
            "registrations": registrations,
        }
        compilation = compile_registration_set_v2(
            previous,
            registration_set,
            {
                "contract_version": 2,
                "enabled_attachment_adapter_kinds": ["gcp-cloud-run-v1"],
            },
        )
        if (
            compilation.violations
            or compilation.compiled_configuration is None
            or compilation.ownership_manifest is None
            or compilation.generation_digest is None
        ):
            return None
        return RegistrationGenerationProposal(
            environment=environment,
            registration_set=registration_set,
            compiled_configuration=compilation.compiled_configuration,
            ownership_manifest=compilation.ownership_manifest,
            generation_digest=compilation.generation_digest,
            content_digest=cls._canonical_digest(compilation.compiled_configuration),
        )

    def _publish_and_activate(
        self,
        proposal: RegistrationGenerationProposal,
        *,
        reviewed_confirmation: bool = False,
    ) -> RegistrationLifecycleResult:
        """Publish one immutable proposal, confirm it, and atomically activate it."""

        assert self._generation_control is not None
        assert self._terminal is not None
        try:
            publication = self._generation_control.publish(proposal)
        except Exception:
            return self._registration_blocked("GENERATION_PUBLICATION_FAILED")
        if (
            not publication.readback_matches
            or publication.generation_digest != proposal.generation_digest
            or publication.content_digest != proposal.content_digest
            or not publication.publication_reference
        ):
            return self._registration_blocked("GENERATION_READBACK_MISMATCH")

        generation = int(proposal.registration_set["generation"])
        self._terminal.write(
            f"GENERATION {generation} {proposal.generation_digest}"
        )
        try:
            if reviewed_confirmation:
                confirmed = self._terminal.confirm(
                    "Activate the reviewed complete Fixture Application generation "
                    f"{generation} {proposal.generation_digest}? [y/N] "
                )
            else:
                expected = (
                    f"ACTIVATE {proposal.environment} GENERATION {generation} "
                    f"{proposal.generation_digest}"
                )
                confirmed = self._terminal.confirm_exact(
                    f"Type {expected!r} to activate the exact whole generation: ",
                    expected,
                )
        except OperatorInterrupted:
            return self._registration_blocked(
                "GENERATION_ACTIVATION_INTERRUPTED",
                outcome="interrupted",
                proposal=proposal,
            )
        except Exception:
            return self._registration_blocked(
                "GENERATION_CONFIRMATION_FAILED",
                proposal=proposal,
            )
        if not confirmed:
            return self._registration_blocked(
                "GENERATION_NOT_CONFIRMED",
                outcome="cancelled",
                proposal=proposal,
            )
        try:
            activation = self._generation_control.activate(
                proposal.environment,
                publication.publication_reference,
                proposal.generation_digest,
            )
        except Exception:
            return self._registration_blocked(
                "GENERATION_ACTIVATION_FAILED",
                proposal=proposal,
            )
        if (
            not activation.activated
            or activation.active_generation_digest != proposal.generation_digest
        ):
            return self._registration_blocked(
                "GENERATION_ACTIVATION_MISMATCH",
                proposal=proposal,
            )
        return RegistrationLifecycleResult(
            outcome="activated",
            generation=generation,
            generation_digest=proposal.generation_digest,
        )

    def register_complete(
        self,
        entries: tuple[RegistrationEntry, ...],
    ) -> RegistrationLifecycleResult:
        """Validate and activate one complete multi-application generation."""

        if not entries:
            return self._registration_blocked("REGISTRATION_SET_EMPTY")
        if self._generation_control is None:
            return self._registration_blocked("GENERATION_CONTROL_UNAVAILABLE")
        if self._terminal is None:
            return self._registration_blocked("INTEGRATION_TERMINAL_UNAVAILABLE")

        environments = {
            str(entry.integration_bundle.get("environment")) for entry in entries
        }
        source_revisions = {
            str(entry.integration_bundle.get("platform_source_revision"))
            for entry in entries
        }
        application_ids = [
            str(entry.integration_bundle.get("application_id")) for entry in entries
        ]
        if (
            len(environments) != 1
            or len(source_revisions) != 1
            or len(application_ids) != len(set(application_ids))
        ):
            return self._registration_blocked("REGISTRATION_SET_MISMATCH")

        environment = next(iter(environments))
        current = self._generation_control.current(environment)
        if current is not None and current.environment != environment:
            return self._registration_blocked("GENERATION_ENVIRONMENT_MISMATCH")
        comparison_current = self._version_two_previous(
            current.registration_set if current is not None else None
        )
        if current is not None and comparison_current is None:
            return self._registration_blocked("GENERATION_VERSION_UNSUPPORTED")
        current_by_id = {
            str(item["application_id"]): item
            for item in (
                comparison_current["registrations"]
                if comparison_current is not None
                else []
            )
        }
        active_registrations: list[dict[str, Any]] = []
        unchanged = (
            current is not None
            and current.registration_set.get("contract_version") == 2
        )
        for entry in entries:
            validated = self.validate_attachment(
                entry.integration_bundle,
                entry.attachment_bundle,
                entry.intent,
            )
            if validated.outcome != "validated":
                return self._registration_blocked(
                    *validated.blockers,
                    target_violations=validated.target_violations,
                )
            if not self._registration_intent_valid(
                entry.integration_bundle,
                entry.intent,
            ):
                return self._registration_blocked("REGISTRATION_INTENT_INVALID")
            application_id = str(entry.integration_bundle["application_id"])
            previous = current_by_id.get(application_id)
            if previous is not None and previous.get("lifecycle") == "retired":
                return self._registration_blocked("APPLICATION_RETIRED")
            desired_active = self._application_registration(
                entry.integration_bundle,
                entry.attachment_bundle,
                entry.intent,
                "active",
                int(previous["registration_revision"]) if previous is not None else 1,
            )
            if previous is None or {
                key: value
                for key, value in previous.items()
                if key != "registration_revision"
            } != {
                key: value
                for key, value in desired_active.items()
                if key != "registration_revision"
            }:
                unchanged = False
            active_registrations.append(
                self._application_registration(
                    entry.integration_bundle,
                    entry.attachment_bundle,
                    entry.intent,
                    "active",
                    (
                        int(previous["registration_revision"]) + 1
                        if previous is not None
                        else 1
                    ),
                )
            )

        if unchanged:
            assert current is not None
            return RegistrationLifecycleResult(
                outcome="unchanged",
                generation=int(current.registration_set["generation"]),
                generation_digest=current.generation_digest,
            )

        active_proposal = self._compile_complete_generation(
            environment,
            next(iter(source_revisions)),
            current,
            tuple(active_registrations),
            "Activate complete Fixture Application suite",
        )
        if active_proposal is None:
            return self._registration_blocked("REGISTRATION_COMPILATION_FAILED")
        return self._publish_and_activate(
            active_proposal,
            reviewed_confirmation=True,
        )

    def status_applications(
        self,
        environment: str,
        application_ids: tuple[str, ...],
    ) -> RegistrationStatusResult:
        """Read every registered target without mutating either owner.

        Application-level compatibility booleans summarize the complete attachment set. Target
        failures are accumulated for the application and expose only attachment IDs and stable
        codes, never provider payloads or Application State.
        """

        if self._generation_control is None or self._attachment_reader is None:
            return RegistrationStatusResult(
                "blocked",
                None,
                None,
                (),
                ("FIXTURE_STATUS_UNAVAILABLE",),
            )
        try:
            platform = self._platform_reader.read_platform(environment)
            current = self._generation_control.current(environment)
        except Exception:
            return RegistrationStatusResult(
                "blocked",
                None,
                None,
                (),
                ("FIXTURE_STATUS_READBACK_FAILED",),
            )
        if (
            platform.environment != environment
            or platform.lifecycle_state != "deployed"
            or current is None
            or current.environment != environment
        ):
            return RegistrationStatusResult(
                "blocked",
                None,
                None,
                (),
                ("FIXTURE_STATUS_PLATFORM_MISMATCH",),
            )
        registrations = {
            str(item["application_id"]): item
            for item in current.registration_set["registrations"]
        }
        statuses: list[RegistrationApplicationStatus] = []
        for application_id in application_ids:
            registration = registrations.get(application_id)
            if registration is None:
                return RegistrationStatusResult(
                    "blocked",
                    int(current.registration_set["generation"]),
                    current.generation_digest,
                    tuple(statuses),
                    ("FIXTURE_REGISTRATION_MISSING",),
                )
            attachments = registration.get("attachments")
            catalogue = registration.get("catalogue")
            catalogue_visibility = (
                catalogue.get("visibility")
                if isinstance(catalogue, dict)
                else None
            )
            if (
                not isinstance(attachments, list)
                or not 1 <= len(attachments) <= 16
                or catalogue_visibility not in {"listed", "unlisted"}
            ):
                return RegistrationStatusResult(
                    "blocked",
                    int(current.registration_set["generation"]),
                    current.generation_digest,
                    tuple(statuses),
                    ("FIXTURE_REGISTRATION_INVALID",),
                )
            if any(not isinstance(item, dict) for item in attachments):
                return RegistrationStatusResult(
                    "blocked",
                    int(current.registration_set["generation"]),
                    current.generation_digest,
                    tuple(statuses),
                    ("FIXTURE_REGISTRATION_INVALID",),
                )
            attachment_ids = [item.get("attachment_id") for item in attachments]
            if (
                any(not isinstance(item, str) for item in attachment_ids)
                or len(set(attachment_ids)) != len(attachment_ids)
            ):
                return RegistrationStatusResult(
                    "blocked",
                    int(current.registration_set["generation"]),
                    current.generation_digest,
                    tuple(statuses),
                    ("FIXTURE_REGISTRATION_INVALID",),
                )

            attachment_statuses: list[RegistrationAttachmentStatus] = []
            target_violations: list[AttachmentTargetViolation] = []
            for registered_attachment in attachments:
                attachment_id = str(registered_attachment["attachment_id"])
                resource_reference = registered_attachment.get(
                    "resource_reference"
                )
                if not isinstance(resource_reference, str):
                    return RegistrationStatusResult(
                        "blocked",
                        int(current.registration_set["generation"]),
                        current.generation_digest,
                        tuple(statuses),
                        ("FIXTURE_REGISTRATION_INVALID",),
                    )
                try:
                    target = self._attachment_reader.read_target(
                        environment,
                        resource_reference,
                    )
                except Exception:
                    target_violations.append(
                        AttachmentTargetViolation(
                            attachment_id,
                            "FIXTURE_TARGET_READBACK_FAILED",
                        )
                    )
                    attachment_statuses.append(
                        RegistrationAttachmentStatus(
                            attachment_id,
                            resource_reference,
                            False,
                            False,
                        )
                    )
                    continue
                if target.exists and target.owner_application_id != application_id:
                    target_violations.append(
                        AttachmentTargetViolation(
                            attachment_id,
                            "FIXTURE_TARGET_OWNER_MISMATCH",
                        )
                    )
                attachment_statuses.append(
                    RegistrationAttachmentStatus(
                        attachment_id,
                        resource_reference,
                        target.exists,
                        target.ready,
                    )
                )
            if target_violations:
                return RegistrationStatusResult(
                    "blocked",
                    int(current.registration_set["generation"]),
                    current.generation_digest,
                    tuple(statuses),
                    tuple(sorted({item.code for item in target_violations})),
                    tuple(target_violations),
                )
            root_status = next(
                (
                    attachment_status
                    for registered_attachment, attachment_status in zip(
                        attachments,
                        attachment_statuses,
                        strict=True,
                    )
                    if registered_attachment.get("mount_path") == "/"
                ),
                attachment_statuses[0],
            )
            statuses.append(
                RegistrationApplicationStatus(
                    application_id,
                    str(registration["lifecycle"]),
                    str(catalogue_visibility),
                    root_status.resource_reference,
                    all(item.target_exists for item in attachment_statuses),
                    all(item.target_ready for item in attachment_statuses),
                    tuple(attachment_statuses),
                )
            )
        return RegistrationStatusResult(
            "read",
            int(current.registration_set["generation"]),
            current.generation_digest,
            tuple(statuses),
        )

    def register(
        self,
        integration_bundle: dict[str, Any],
        attachment_bundle: dict[str, Any],
        intent: RegistrationIntent,
    ) -> RegistrationLifecycleResult:
        """Validate an attachment and activate only immutable whole generations."""

        attachment = self.validate_attachment(
            integration_bundle,
            attachment_bundle,
            intent,
        )
        if attachment.outcome != "validated":
            return self._registration_blocked(
                *attachment.blockers,
                target_violations=attachment.target_violations,
            )
        if not self._registration_intent_valid(integration_bundle, intent):
            return self._registration_blocked("REGISTRATION_INTENT_INVALID")
        if self._generation_control is None:
            return self._registration_blocked("GENERATION_CONTROL_UNAVAILABLE")
        if self._terminal is None:
            return self._registration_blocked("INTEGRATION_TERMINAL_UNAVAILABLE")

        environment = str(integration_bundle["environment"])
        current = self._generation_control.current(environment)
        if current is not None and current.environment != environment:
            return self._registration_blocked("GENERATION_ENVIRONMENT_MISMATCH")
        comparison_current = self._version_two_previous(
            current.registration_set if current is not None else None
        )
        if current is not None and comparison_current is None:
            return self._registration_blocked("GENERATION_VERSION_UNSUPPORTED")
        application_id = str(integration_bundle["application_id"])
        current_registration = None
        if comparison_current is not None:
            current_registration = next(
                (
                    item
                    for item in comparison_current["registrations"]
                    if item["application_id"] == application_id
                ),
                None,
            )
        if current_registration is not None and current_registration["lifecycle"] == "retired":
            return self._registration_blocked("APPLICATION_RETIRED")

        desired = self._application_registration(
            integration_bundle,
            attachment_bundle,
            intent,
            "active",
            (
                int(current_registration["registration_revision"])
                if current_registration is not None
                else 1
            ),
        )
        if current_registration is not None:
            previous_values = {
                key: value
                for key, value in current_registration.items()
                if key != "registration_revision"
            }
            desired_values = {
                key: value
                for key, value in desired.items()
                if key != "registration_revision"
            }
            registration_unchanged = previous_values == desired_values
            if (
                current is not None
                and current.registration_set.get("contract_version") == 2
                and registration_unchanged
            ):
                return RegistrationLifecycleResult(
                    outcome="unchanged",
                    generation=int(current.registration_set["generation"]),
                    generation_digest=current.generation_digest,
                )
            if not registration_unchanged:
                desired["registration_revision"] = (
                    int(current_registration["registration_revision"]) + 1
                )

        source_revision = str(integration_bundle["platform_source_revision"])
        proposal = self._compile_generation(
            environment,
            source_revision,
            current,
            desired,
            f"Register {application_id}",
        )
        if proposal is None:
            return self._registration_blocked("REGISTRATION_COMPILATION_FAILED")
        result = self._publish_and_activate(proposal)
        return result

    def _transition(
        self,
        request: LifecycleChangeRequest,
        target_lifecycle: str,
    ) -> RegistrationLifecycleResult:
        """Activate one app-wide lifecycle transition while preserving its attachment set."""

        if self._generation_control is None:
            return self._registration_blocked("GENERATION_CONTROL_UNAVAILABLE")
        if self._terminal is None:
            return self._registration_blocked("INTEGRATION_TERMINAL_UNAVAILABLE")
        platform = self._platform_reader.read_platform(request.environment)
        if platform.environment != request.environment:
            return self._registration_blocked("PLATFORM_ENVIRONMENT_MISMATCH")
        if (
            platform.platform_source_revision
            != request.expected_platform_source_revision
        ):
            return self._registration_blocked("PLATFORM_SOURCE_MISMATCH")
        if platform.lifecycle_state != "deployed":
            return self._registration_blocked("PLATFORM_NOT_DEPLOYED")

        current = self._generation_control.current(request.environment)
        if current is None:
            return self._registration_blocked("APPLICATION_NOT_REGISTERED")
        if current.environment != request.environment:
            return self._registration_blocked("GENERATION_ENVIRONMENT_MISMATCH")
        if current.generation_digest != request.expected_generation_digest:
            return self._registration_blocked("GENERATION_CONFLICT")
        comparison_current = self._version_two_previous(current.registration_set)
        if comparison_current is None:
            return self._registration_blocked("GENERATION_VERSION_UNSUPPORTED")
        registration = next(
            (
                item
                for item in comparison_current["registrations"]
                if item["application_id"] == request.application_id
            ),
            None,
        )
        if registration is None:
            return self._registration_blocked("APPLICATION_NOT_REGISTERED")
        current_lifecycle = str(registration["lifecycle"])
        if current_lifecycle == target_lifecycle:
            return RegistrationLifecycleResult(
                outcome="unchanged",
                generation=int(current.registration_set["generation"]),
                generation_digest=current.generation_digest,
            )
        if target_lifecycle == "suspended" and current_lifecycle != "active":
            blocker = (
                "APPLICATION_RETIRED"
                if current_lifecycle == "retired"
                else "APPLICATION_NOT_ACTIVE"
            )
            return self._registration_blocked(blocker)
        if current_lifecycle == "retired":
            return self._registration_blocked("APPLICATION_RETIRED")

        successor = copy.deepcopy(registration)
        successor["lifecycle"] = target_lifecycle
        successor["registration_revision"] = int(
            registration["registration_revision"]
        ) + 1
        verb = "Detach" if target_lifecycle == "suspended" else "Retire"
        proposal = self._compile_generation(
            request.environment,
            request.expected_platform_source_revision,
            current,
            successor,
            f"{verb} {request.application_id}",
        )
        if proposal is None:
            return self._registration_blocked("REGISTRATION_COMPILATION_FAILED")
        return self._publish_and_activate(proposal)

    def detach(
        self,
        request: LifecycleChangeRequest,
    ) -> RegistrationLifecycleResult:
        """Suspend routing without invoking or destroying Application State."""

        return self._transition(request, "suspended")

    def retire(
        self,
        request: LifecycleChangeRequest,
    ) -> RegistrationLifecycleResult:
        """Activate an immutable terminal tombstone without releasing the route."""

        return self._transition(request, "retired")


__all__ = (
    "ApplicationIntegrationLifecycle",
    "AttachmentTargetViolation",
    "AttachmentTargetReadback",
    "AttachmentTargetReader",
    "AttachmentValidationResult",
    "GenerationActivationReadback",
    "GenerationPublicationReadback",
    "IntegrationBundleRequest",
    "IntegrationBundleResult",
    "LifecycleChangeRequest",
    "OperatorInterrupted",
    "PlatformIntegrationReader",
    "PlatformIntegrationState",
    "RegistrationGenerationControl",
    "RegistrationGenerationProposal",
    "RegistrationEntry",
    "RegistrationAttachmentBinding",
    "RegistrationAttachmentStatus",
    "RegistrationApplicationStatus",
    "RegistrationStatusResult",
    "RegistrationIntent",
    "RegistrationLifecycleResult",
)
