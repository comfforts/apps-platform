"""Exact local and provider readback composition for qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from infrastructure.operator._interfaces import OperatorTerminal, StatusResult
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.qualification import (
    ComponentRevision,
    QualificationReadback,
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

    def read_current(self, environment: str) -> QualificationReadback:
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
        )


class LiveGenerationRollbackExercise:
    """Review one predecessor activation and restore the exact original generation."""

    def __init__(
        self,
        platform: PlatformIntegrationReader,
        generations: ReviewedGenerationControl,
        terminal: OperatorTerminal,
    ) -> None:
        self._platform = platform
        self._generations = generations
        self._terminal = terminal

    def verify_rollback(self, environment: str, generation_digest: str) -> bool:
        try:
            platform = self._platform.read_platform(environment)
            original = self._generations.current(environment)
        except Exception:
            return False
        if (
            original is None
            or original.proposal.generation_digest != generation_digest
        ):
            return False
        predecessor_digest = original.proposal.registration_set.get(
            "previous_generation_digest"
        )
        if not isinstance(predecessor_digest, str):
            return False
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
            return False

        generation = original.proposal.registration_set.get("generation")
        if not isinstance(generation, int):
            return False
        expected = f"RESTORE {environment} GENERATION {generation} {generation_digest}"
        self._terminal.write(
            f"RESTORE_GENERATION {generation} {generation_digest}"
        )
        try:
            confirmed = self._terminal.confirm_exact(
                f"Type {expected!r} to restore the reviewed generation: ",
                expected,
            )
        except Exception:
            return False
        if not confirmed:
            return False
        try:
            restored = self._generations.activate(
                environment,
                original.publication_reference,
                generation_digest,
            )
            current = self._generations.current(environment)
        except Exception:
            return False
        return (
            restored.activated
            and restored.active_generation_digest == generation_digest
            and current is not None
            and current.proposal.generation_digest == generation_digest
        )


__all__ = (
    "EnvironmentStatusReader",
    "LiveGenerationRollbackExercise",
    "LocalQualificationStateReader",
    "ProviderQualificationSnapshot",
    "QualificationProviderReader",
    "RegistrationGenerationReader",
)
