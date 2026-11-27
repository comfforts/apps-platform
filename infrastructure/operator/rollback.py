"""Reviewed whole-generation rollback without generation reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from infrastructure.operator._interfaces import OperatorInterrupted
from infrastructure.operator._interfaces import OperatorTerminal
from infrastructure.operator.integration import (
    GenerationActivationReadback,
    PlatformIntegrationReader,
    RegistrationGenerationProposal,
)


@dataclass(frozen=True, slots=True)
class ReviewedGeneration:
    """One immutable generation and the platform source of its provider runtime."""

    publication_reference: str
    proposal: RegistrationGenerationProposal
    platform_source_revision: str

    def __post_init__(self) -> None:
        """Reject a reviewed generation without one exact provider source binding."""

        if (
            len(self.platform_source_revision) != 40
            or any(
                character not in "0123456789abcdef"
                for character in self.platform_source_revision
            )
        ):
            raise ValueError("reviewed generation platform source is invalid")


class ReviewedGenerationControl(Protocol):
    def current(self, environment: str) -> ReviewedGeneration | None: ...

    def read_reviewed(
        self,
        environment: str,
        generation_digest: str,
    ) -> ReviewedGeneration | None: ...

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback: ...


@dataclass(frozen=True, slots=True)
class RollbackRequest:
    environment: str
    expected_platform_source_revision: str
    expected_active_generation_digest: str
    target_generation_digest: str


@dataclass(frozen=True, slots=True)
class RollbackResult:
    outcome: str
    generation: int | None
    generation_digest: str | None
    blockers: tuple[str, ...] = ()


class GenerationRollbackLifecycle:
    """Activate one retained reviewed predecessor and nothing else."""

    def __init__(
        self,
        platform_reader: PlatformIntegrationReader,
        generation_control: ReviewedGenerationControl,
        terminal: OperatorTerminal,
    ) -> None:
        self._platform_reader = platform_reader
        self._generation_control = generation_control
        self._terminal = terminal

    @staticmethod
    def _result(
        outcome: str,
        *blockers: str,
        generation: int | None = None,
        generation_digest: str | None = None,
    ) -> RollbackResult:
        return RollbackResult(
            outcome=outcome,
            generation=generation,
            generation_digest=generation_digest,
            blockers=tuple(sorted(set(blockers))),
        )

    def rollback(self, request: RollbackRequest) -> RollbackResult:
        try:
            platform = self._platform_reader.read_platform(request.environment)
        except Exception:
            return self._result("blocked", "PLATFORM_READBACK_FAILED")
        if platform.environment != request.environment:
            return self._result("blocked", "PLATFORM_ENVIRONMENT_MISMATCH")
        if (
            platform.platform_source_revision
            != request.expected_platform_source_revision
        ):
            return self._result("blocked", "PLATFORM_SOURCE_MISMATCH")
        if platform.lifecycle_state != "deployed":
            return self._result("blocked", "PLATFORM_NOT_DEPLOYED")

        try:
            current = self._generation_control.current(request.environment)
        except Exception:
            return self._result("blocked", "GENERATION_READBACK_FAILED")
        if current is None:
            return self._result("blocked", "GENERATION_NOT_FOUND")
        if (
            current.proposal.generation_digest
            != request.expected_active_generation_digest
        ):
            return self._result("blocked", "GENERATION_CONFLICT")
        try:
            target = self._generation_control.read_reviewed(
                request.environment,
                request.target_generation_digest,
            )
        except Exception:
            return self._result("blocked", "ROLLBACK_TARGET_READBACK_FAILED")
        if target is None:
            return self._result("blocked", "ROLLBACK_TARGET_NOT_FOUND")
        if (
            target.proposal.environment != request.environment
            or target.proposal.generation_digest
            != request.target_generation_digest
            or not target.publication_reference
        ):
            return self._result("blocked", "ROLLBACK_TARGET_MISMATCH")

        current_set = current.proposal.registration_set
        target_set = target.proposal.registration_set
        current_generation = current_set.get("generation")
        target_generation = target_set.get("generation")
        if (
            not isinstance(current_generation, int)
            or not isinstance(target_generation, int)
            or target_generation != current_generation - 1
            or current_set.get("previous_generation_digest")
            != target.proposal.generation_digest
        ):
            return self._result("blocked", "ROLLBACK_TARGET_NOT_PREDECESSOR")
        if (
            target.platform_source_revision
            != request.expected_platform_source_revision
        ):
            self._terminal.write(
                "ROLLBACK PREDECESSOR SOURCE MISMATCH\n"
                f"Reviewed predecessor generation {target_generation} is bound "
                f"to platform source {target.platform_source_revision}, while "
                "the active candidate uses "
                f"{request.expected_platform_source_revision}.\n"
                "No traffic was changed. Recreate fixture-public as public `none` "
                "under the active candidate, then create its public `optional` "
                "successor and retry qualification."
            )
            return self._result(
                "blocked",
                "ROLLBACK_PREDECESSOR_SOURCE_MISMATCH",
                generation=target_generation,
                generation_digest=target.proposal.generation_digest,
            )

        expected = (
            f"ROLLBACK {request.environment} GENERATION {target_generation} "
            f"{target.proposal.generation_digest}"
        )
        self._terminal.write(
            f"ROLLBACK_GENERATION {target_generation} "
            f"{target.proposal.generation_digest}"
        )
        try:
            confirmed = self._terminal.confirm_exact(
                f"Type {expected!r} to activate the reviewed predecessor: ",
                expected,
            )
        except OperatorInterrupted:
            return self._result(
                "interrupted",
                "ROLLBACK_INTERRUPTED",
                generation=target_generation,
                generation_digest=target.proposal.generation_digest,
            )
        except Exception:
            return self._result("blocked", "ROLLBACK_CONFIRMATION_FAILED")
        if not confirmed:
            return self._result(
                "cancelled",
                "ROLLBACK_NOT_CONFIRMED",
                generation=target_generation,
                generation_digest=target.proposal.generation_digest,
            )
        try:
            activated = self._generation_control.activate(
                request.environment,
                target.publication_reference,
                target.proposal.generation_digest,
            )
        except Exception:
            return self._result(
                "blocked",
                "ROLLBACK_ACTIVATION_FAILED",
                generation=target_generation,
                generation_digest=target.proposal.generation_digest,
            )
        if (
            not activated.activated
            or activated.active_generation_digest
            != target.proposal.generation_digest
        ):
            return self._result(
                "blocked",
                "ROLLBACK_ACTIVATION_MISMATCH",
                generation=target_generation,
                generation_digest=target.proposal.generation_digest,
            )
        return self._result(
            "activated",
            generation=target_generation,
            generation_digest=target.proposal.generation_digest,
        )


__all__ = (
    "GenerationRollbackLifecycle",
    "ReviewedGeneration",
    "ReviewedGenerationControl",
    "RollbackRequest",
    "RollbackResult",
)
