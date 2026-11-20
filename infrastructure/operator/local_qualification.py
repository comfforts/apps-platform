"""Exact local and provider readback composition for qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from infrastructure.operator._interfaces import StatusResult
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.qualification import (
    ComponentRevision,
    QualificationReadback,
)


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
            "journal_digest",
            "profile_digest",
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
            deployment_journal_digest=str(status["journal_digest"]),
            registration_generation_digest=proposal.generation_digest,
            component_revisions=tuple(sorted(provider.component_revisions)),
            fixture_revisions=tuple(sorted(fixtures)),
        )


__all__ = (
    "EnvironmentStatusReader",
    "LocalQualificationStateReader",
    "ProviderQualificationSnapshot",
    "QualificationProviderReader",
    "RegistrationGenerationReader",
)
