"""Exact local and provider readback composition for qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from infrastructure.operator._interfaces import OperatorTerminal, StatusResult
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.qualification import (
    ComponentRevision,
    FixtureQualificationPolicy,
    QualificationReadback,
    QualificationVerificationResult,
)
from infrastructure.operator.rollback import (
    GenerationRollbackLifecycle,
    ReviewedGenerationControl,
    RollbackRequest,
)
from infrastructure.operator.integration import PlatformIntegrationReader


_REQUIRED_FIXTURES = {
    "fixture-authenticated",
    "fixture-public",
    "fixture-restricted",
}
_FIXTURE_ADMISSION = {
    "fixture-authenticated": "authenticated",
    "fixture-public": "public",
    "fixture-restricted": "restricted",
}


class EnvironmentStatusReader(Protocol):
    def status(self, environment: str) -> StatusResult: ...


class RegistrationGenerationReader(Protocol):
    def current(
        self,
        environment: str,
    ) -> RegistrationGenerationProposal | None: ...


@dataclass(frozen=True, slots=True)
class ProviderQualificationSnapshot:
    environment: str
    active_generation_digest: str
    component_revisions: tuple[ComponentRevision, ...]


class QualificationProviderReader(Protocol):
    def read_current(
        self,
        environment: str,
    ) -> ProviderQualificationSnapshot: ...


class LocalQualificationStateReader:
    """Join exact local authority with provider facts, never Application State."""

    def __init__(
        self,
        status_reader: EnvironmentStatusReader,
        generations: RegistrationGenerationReader,
        handoffs: LocalApplicationHandoffs,
        provider: QualificationProviderReader,
    ) -> None:
        self._status_reader = status_reader
        self._generations = generations
        self._handoffs = handoffs
        self._provider = provider

    @staticmethod
    def _fixture_policy(
        registration: dict[str, object],
    ) -> FixtureQualificationPolicy:
        """Project one validated active fixture into least-data expectations."""

        application_id = registration.get("application_id")
        admission = registration.get("admission")
        identity_delivery = registration.get("identity_delivery")
        catalogue = registration.get("catalogue")
        lifecycle = registration.get("lifecycle")
        route_prefix = registration.get("route_prefix")
        attachments = registration.get("attachments")
        if (
            not isinstance(application_id, str)
            or application_id not in _REQUIRED_FIXTURES
            or not isinstance(admission, dict)
            or admission.get("mode") != _FIXTURE_ADMISSION[application_id]
            or identity_delivery not in {"none", "optional", "required"}
            or not isinstance(catalogue, dict)
            or catalogue.get("visibility") not in {"listed", "unlisted"}
            or not isinstance(catalogue.get("title"), str)
            or lifecycle != "active"
            or route_prefix != f"/{application_id}"
            or not isinstance(attachments, list)
            or len(attachments) != 1
            or not isinstance(attachments[0], dict)
        ):
            raise ValueError("active qualification fixture policy is invalid")
        attachment = attachments[0]
        audience = attachment.get("audience")
        if (
            attachment.get("owner_application_id") != application_id
            or not isinstance(attachment.get("resource_reference"), str)
            or (identity_delivery == "none" and audience is not None)
            or (
                identity_delivery != "none"
                and not isinstance(audience, str)
            )
            or (
                application_id == "fixture-public"
                and identity_delivery not in {"none", "optional"}
            )
            or (
                application_id != "fixture-public"
                and identity_delivery != "required"
            )
        ):
            raise ValueError("active qualification fixture attachment is invalid")
        return FixtureQualificationPolicy(
            application_id=application_id,
            admission_mode=str(admission["mode"]),
            identity_delivery=str(identity_delivery),
            catalogue_visibility=str(catalogue["visibility"]),
            catalogue_title=str(catalogue["title"]),
            route_prefix=str(route_prefix),
            target_reference=str(attachment["resource_reference"]),
            target_audience=audience if isinstance(audience, str) else None,
        )

    def read_current(self, environment: str) -> QualificationReadback:
        """Join deployed state, active policy, handoffs, and provider readback."""

        status_result = self._status_reader.status(environment)
        if status_result.conflicts:
            raise ValueError("environment status has unresolved conflicts")
        status = status_result.environment_status
        if (
            status.get("environment") != environment
            or status.get("lifecycle_state") != "deployed"
        ):
            raise ValueError("environment is not deployed")
        required_status = (
            "progress_digest",
            "profile_digest",
            "source_authority",
            "source_revision",
            "specification_digest",
        )
        if any(not isinstance(status.get(name), str) for name in required_status):
            raise ValueError("environment status is incomplete")

        proposal = self._generations.current(environment)
        if proposal is None or proposal.environment != environment:
            raise ValueError("active registration generation is unavailable")
        generation = proposal.registration_set.get("generation")
        registrations = proposal.registration_set.get("registrations")
        if not isinstance(generation, int) or not isinstance(registrations, list):
            raise ValueError("active registration generation is invalid")
        active_fixtures: set[str] = set()
        fixture_policies: list[FixtureQualificationPolicy] = []
        for registration in registrations:
            if not isinstance(registration, dict):
                raise ValueError("active registration generation is invalid")
            application_id = registration.get("application_id")
            lifecycle = registration.get("lifecycle")
            if (
                isinstance(application_id, str)
                and application_id.startswith("fixture-")
                and lifecycle == "active"
            ):
                active_fixtures.add(application_id)
                fixture_policies.append(self._fixture_policy(registration))
        if active_fixtures != _REQUIRED_FIXTURES:
            raise ValueError("required qualification fixtures are not active")

        fixtures = []
        for application_id in sorted(active_fixtures):
            handoff = self._handoffs.latest_for_application(
                environment,
                application_id,
                generation,
            )
            if handoff is None:
                raise ValueError("qualification fixture handoff is unavailable")
            fixtures.append(handoff.fixture_revision)

        provider = self._provider.read_current(environment)
        if (
            provider.environment != environment
            or provider.active_generation_digest != proposal.generation_digest
            or not provider.component_revisions
            or len({item.name for item in provider.component_revisions})
            != len(provider.component_revisions)
        ):
            raise ValueError("provider qualification readback is mismatched")
        return QualificationReadback(
            environment=environment,
            lifecycle_state="deployed",
            source_revision=str(status["source_revision"]),
            profile_digest=str(status["profile_digest"]),
            specification_digest=str(status["specification_digest"]),
            deployment_progress_digest=str(status["progress_digest"]),
            registration_generation_digest=proposal.generation_digest,
            component_revisions=tuple(sorted(provider.component_revisions)),
            fixture_revisions=tuple(sorted(fixtures)),
            source_authority=str(status["source_authority"]),
            fixture_policies=tuple(sorted(fixture_policies)),
        )


class LiveGenerationRollbackExercise:
    """Review one predecessor activation and restore the exact original generation."""

    def __init__(
        self,
        platform: PlatformIntegrationReader,
        generations: ReviewedGenerationControl,
        terminal: OperatorTerminal,
        predecessor_public_none: Callable[[], QualificationVerificationResult],
    ) -> None:
        self._platform = platform
        self._generations = generations
        self._terminal = terminal
        self._predecessor_public_none = predecessor_public_none

    @staticmethod
    def _failed(*blockers: str) -> QualificationVerificationResult:
        """Return one canonical least-data failure without runtime payloads."""

        return QualificationVerificationResult(
            False,
            tuple(sorted(set(blockers))),
        )

    def verify_rollback(
        self,
        environment: str,
        generation_digest: str,
    ) -> QualificationVerificationResult:
        """Activate, exercise, and restore one reviewed predecessor generation."""

        try:
            platform = self._platform.read_platform(environment)
            original = self._generations.current(environment)
        except Exception:
            return self._failed("LIVE_ROLLBACK_READBACK_FAILED")
        if (
            original is None
            or original.proposal.generation_digest != generation_digest
        ):
            return self._failed("LIVE_ROLLBACK_ACTIVE_GENERATION_MISMATCH")
        predecessor_digest = original.proposal.registration_set.get(
            "previous_generation_digest"
        )
        if not isinstance(predecessor_digest, str):
            return self._failed("LIVE_ROLLBACK_PREDECESSOR_UNAVAILABLE")
        generation = original.proposal.registration_set.get("generation")
        if not isinstance(generation, int) or generation < 2:
            return self._failed("LIVE_ROLLBACK_PREDECESSOR_UNAVAILABLE")
        predecessor_generation = generation - 1
        self._terminal.write(
            "LIVE ROLLBACK CHECK\n"
            f"This check will temporarily send 100 percent of {environment} traffic "
            f"to reviewed predecessor generation {predecessor_generation}.\n"
            f"After that activation is verified, this same command will require "
            f"a second exact confirmation to restore generation {generation}.\n"
            "Keep the command running through both confirmations. Declining or "
            "interrupting restoration leaves the predecessor active and requires "
            "an explicit recovery before qualification can succeed."
        )
        rollback = GenerationRollbackLifecycle(
            self._platform,
            self._generations,
            self._terminal,
        ).rollback(
            RollbackRequest(
                environment=environment,
                expected_platform_source_revision=(
                    platform.platform_source_revision
                ),
                expected_active_generation_digest=generation_digest,
                target_generation_digest=predecessor_digest,
            )
        )
        if rollback.outcome != "activated":
            return self._failed(
                *(rollback.blockers or ("LIVE_ROLLBACK_ACTIVATION_FAILED",))
            )

        try:
            predecessor_result = self._predecessor_public_none()
        except Exception:
            predecessor_result = self._failed(
                "LIVE_PREDECESSOR_BROWSER_CHECK_FAILED"
            )
        if not predecessor_result.verified:
            self._terminal.write(
                "PREDECESSOR CHECK FAILED "
                f"({', '.join(predecessor_result.blockers)}): the reviewed "
                "predecessor did not "
                "prove that a platform-authenticated session reaches the public "
                "fixture without Platform Identity. Restoration will continue."
            )

        expected = f"RESTORE {environment} GENERATION {generation} {generation_digest}"
        self._terminal.write(
            f"The predecessor generation {predecessor_generation} is now active "
            "and serving 100 percent of staging traffic.\n"
            f"RESTORE_GENERATION {generation} {generation_digest}"
        )
        try:
            confirmed = self._terminal.confirm_exact(
                f"Type {expected!r} to restore the reviewed generation: ",
                expected,
            )
        except Exception:
            self._terminal.write(
                f"RESTORATION REQUIRED: predecessor generation "
                f"{predecessor_generation} remains active. Restore reviewed "
                f"generation {generation} before continuing qualification."
            )
            return self._failed(
                "LIVE_ROLLBACK_RESTORATION_REQUIRED",
                *predecessor_result.blockers,
            )
        if not confirmed:
            self._terminal.write(
                f"RESTORATION REQUIRED: predecessor generation "
                f"{predecessor_generation} remains active. Restore reviewed "
                f"generation {generation} before continuing qualification."
            )
            return self._failed(
                "LIVE_ROLLBACK_RESTORATION_REQUIRED",
                *predecessor_result.blockers,
            )
        try:
            restored = self._generations.activate(
                environment,
                original.publication_reference,
                generation_digest,
            )
            current = self._generations.current(environment)
        except Exception:
            self._terminal.write(
                f"RESTORATION REQUIRED: the restoration of reviewed generation "
                f"{generation} could not be verified. Inspect the active "
                "generation before continuing qualification."
            )
            return self._failed(
                "LIVE_ROLLBACK_RESTORATION_FAILED",
                *predecessor_result.blockers,
            )
        verified = (
            restored.activated
            and restored.active_generation_digest == generation_digest
            and current is not None
            and current.proposal.generation_digest == generation_digest
        )
        if verified:
            self._terminal.write(
                f"Reviewed generation {generation} is restored and serving "
                "100 percent of staging traffic."
            )
        else:
            self._terminal.write(
                f"RESTORATION REQUIRED: the restoration of reviewed generation "
                f"{generation} did not match provider readback. Inspect the "
                "active generation before continuing qualification."
            )
        if not verified:
            return self._failed(
                "LIVE_ROLLBACK_RESTORATION_MISMATCH",
                *predecessor_result.blockers,
            )
        if not predecessor_result.verified:
            return predecessor_result
        return QualificationVerificationResult(True)


__all__ = (
    "EnvironmentStatusReader",
    "LiveGenerationRollbackExercise",
    "LocalQualificationStateReader",
    "ProviderQualificationSnapshot",
    "QualificationProviderReader",
    "RegistrationGenerationReader",
)
