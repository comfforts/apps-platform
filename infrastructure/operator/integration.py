"""Application handoff lifecycle behind deterministic injected readback seams."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Protocol

from contracts import compile_registration_set
from contracts.lifecycle import (
    lifecycle_digest,
    validate_lifecycle_document,
    validate_lifecycle_relationships,
)
from infrastructure.operator._interfaces import OperatorInterrupted


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


@dataclass(frozen=True, slots=True)
class RegistrationIntent:
    """Explicit platform-facing registration decisions absent from an attachment."""

    catalogue_visibility: str
    catalogue_title: str
    catalogue_summary: str
    attachment_id: str
    mount_path: str
    forwarding_mode: str
    restricted_members: tuple[tuple[str, str], ...] = ()


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
    ) -> RegistrationGenerationProposal | None: ...

    def publish(
        self,
        proposal: RegistrationGenerationProposal,
    ) -> GenerationPublicationReadback: ...

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback: ...


class IntegrationTerminal(Protocol):
    def write(self, message: str) -> None: ...

    def confirm_exact(self, prompt: str, expected: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class RegistrationLifecycleResult:
    """One complete registration lifecycle outcome."""

    outcome: str
    generation: int | None
    generation_digest: str | None
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LifecycleChangeRequest:
    """Exact active-generation precondition for detach or retirement."""

    environment: str
    application_id: str
    expected_platform_source_revision: str
    expected_generation_digest: str


class ApplicationIntegrationLifecycle:
    """Generate least-data application handoffs from exact platform readback."""

    def __init__(
        self,
        platform_reader: PlatformIntegrationReader,
        *,
        attachment_reader: AttachmentTargetReader | None = None,
        generation_control: RegistrationGenerationControl | None = None,
        terminal: IntegrationTerminal | None = None,
    ) -> None:
        self._platform_reader = platform_reader
        self._attachment_reader = attachment_reader
        self._generation_control = generation_control
        self._terminal = terminal

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
        try:
            state = self._platform_reader.read_platform(environment)
        except Exception:
            return self._attachment_blocked("PLATFORM_READBACK_FAILED")
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

    @staticmethod
    def _registration_blocked(
        *blockers: str,
        outcome: str = "blocked",
        proposal: RegistrationGenerationProposal | None = None,
    ) -> RegistrationLifecycleResult:
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
        )

    @staticmethod
    def _registration_intent_valid(
        access_mode: object,
        intent: RegistrationIntent,
    ) -> bool:
        if access_mode == "restricted":
            return bool(intent.restricted_members)
        return access_mode in {"public", "authenticated"} and not intent.restricted_members

    @staticmethod
    def _application_registration(
        integration_bundle: dict[str, Any],
        attachment_bundle: dict[str, Any],
        intent: RegistrationIntent,
        lifecycle: str,
        registration_revision: int,
    ) -> dict[str, Any]:
        access_mode = str(integration_bundle["access_mode"])
        identity = integration_bundle["identity"]
        target = attachment_bundle["target"]
        assert isinstance(identity, dict)
        assert isinstance(target, dict)
        admission: dict[str, Any] = {"mode": access_mode}
        if access_mode == "restricted":
            admission["members"] = [
                {"issuer": issuer, "subject": subject}
                for issuer, subject in sorted(intent.restricted_members)
            ]
        return {
            "contract_version": 1,
            "application_id": integration_bundle["application_id"],
            "registration_revision": registration_revision,
            "route_prefix": integration_bundle["route_intent"],
            "catalogue": {
                "visibility": intent.catalogue_visibility,
                "title": intent.catalogue_title,
                "summary": intent.catalogue_summary,
            },
            "admission": admission,
            "lifecycle": lifecycle,
            "attachments": [
                {
                    "contract_version": 1,
                    "owner_application_id": integration_bundle["application_id"],
                    "attachment_id": intent.attachment_id,
                    "adapter_kind": target["adapter_kind"],
                    "resource_reference": target["resource_reference"],
                    "mount_path": intent.mount_path,
                    "forwarding_mode": intent.forwarding_mode,
                    "identity_requirement": (
                        "none" if access_mode == "public" else "verified"
                    ),
                    "audience": identity["audience"],
                    "ingress_mode": target["ingress_mode"],
                }
            ],
        }

    @staticmethod
    def _canonical_digest(value: object) -> str:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    @classmethod
    def _compile_generation(
        cls,
        environment: str,
        source_revision: str,
        current: RegistrationGenerationProposal | None,
        registration: dict[str, Any],
        change_summary: str,
    ) -> RegistrationGenerationProposal | None:
        previous = current.registration_set if current is not None else None
        registrations = (
            copy.deepcopy(previous["registrations"])
            if previous is not None
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
            "contract_version": 1,
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
        compilation = compile_registration_set(
            previous,
            registration_set,
            {
                "contract_version": 1,
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
    ) -> RegistrationLifecycleResult:
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
        expected = (
            f"ACTIVATE {proposal.environment} GENERATION {generation} "
            f"{proposal.generation_digest}"
        )
        self._terminal.write(
            f"GENERATION {generation} {proposal.generation_digest}"
        )
        try:
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
        )
        if attachment.outcome != "validated":
            return self._registration_blocked(*attachment.blockers)
        if not self._registration_intent_valid(
            integration_bundle.get("access_mode"),
            intent,
        ):
            return self._registration_blocked("REGISTRATION_INTENT_INVALID")
        if self._generation_control is None:
            return self._registration_blocked("GENERATION_CONTROL_UNAVAILABLE")
        if self._terminal is None:
            return self._registration_blocked("INTEGRATION_TERMINAL_UNAVAILABLE")

        environment = str(integration_bundle["environment"])
        current = self._generation_control.current(environment)
        if current is not None and current.environment != environment:
            return self._registration_blocked("GENERATION_ENVIRONMENT_MISMATCH")
        application_id = str(integration_bundle["application_id"])
        current_registration = None
        if current is not None:
            current_registration = next(
                (
                    item
                    for item in current.registration_set["registrations"]
                    if item["application_id"] == application_id
                ),
                None,
            )
        if current_registration is not None and current_registration["lifecycle"] == "retired":
            return self._registration_blocked("APPLICATION_RETIRED")

        first_lifecycle = "staged" if current_registration is None else "active"
        desired = self._application_registration(
            integration_bundle,
            attachment_bundle,
            intent,
            first_lifecycle,
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
            if previous_values == desired_values:
                return RegistrationLifecycleResult(
                    outcome="unchanged",
                    generation=int(current.registration_set["generation"]),
                    generation_digest=current.generation_digest,
                )
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
        if result.outcome != "activated" or first_lifecycle == "active":
            return result

        active = copy.deepcopy(desired)
        active["lifecycle"] = "active"
        active["registration_revision"] = int(desired["registration_revision"]) + 1
        active_proposal = self._compile_generation(
            environment,
            source_revision,
            proposal,
            active,
            f"Activate {application_id}",
        )
        if active_proposal is None:
            return self._registration_blocked(
                "REGISTRATION_COMPILATION_FAILED",
                proposal=proposal,
            )
        return self._publish_and_activate(active_proposal)

    def _transition(
        self,
        request: LifecycleChangeRequest,
        target_lifecycle: str,
    ) -> RegistrationLifecycleResult:
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
        registration = next(
            (
                item
                for item in current.registration_set["registrations"]
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
    "AttachmentTargetReadback",
    "AttachmentTargetReader",
    "AttachmentValidationResult",
    "GenerationActivationReadback",
    "GenerationPublicationReadback",
    "IntegrationTerminal",
    "IntegrationBundleRequest",
    "IntegrationBundleResult",
    "LifecycleChangeRequest",
    "OperatorInterrupted",
    "PlatformIntegrationReader",
    "PlatformIntegrationState",
    "RegistrationGenerationControl",
    "RegistrationGenerationProposal",
    "RegistrationIntent",
    "RegistrationLifecycleResult",
)
