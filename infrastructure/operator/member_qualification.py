"""Cleanup-safe qualification over the existing Platform Member lifecycle.

This module adds no member-administration path.  It composes the same
source-admitted lifecycle service used by the public member commands with a
browser-held Shared Edge admission check.  The temporary second-member journey
is add/allow, suspend/deny, reactivate/allow, and remove/deny.  Every exit then
verifies the reviewed owner-only baseline and attempts removal of a retained
temporary member before returning a failure.

Only counts, booleans, and stable blocker codes leave the exercise.  Opaque
member references remain process-local, while identity, browser state, provider
payloads, and directory contents never enter the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from infrastructure.operator.member_lifecycle import (
    MemberLifecycleResult,
    PlatformMemberLifecycle,
)


class MemberAdmissionQualification(Protocol):
    """Verify one live route-bound decision through the current browser session."""

    def verify(self, application_id: str, expected_admitted: bool) -> bool:
        """Return whether the Shared Edge reported the exact expected decision."""


@dataclass(frozen=True, slots=True)
class MemberQualificationResult:
    """Least-data terminal result for one temporary member exercise."""

    verified: bool
    baseline_restored: bool
    member_transitions: int
    admission_checks: int
    blockers: tuple[str, ...] = ()


class _JourneyFailure(RuntimeError):
    """Carry one stable blocker inside the cleanup-protected control flow."""

    def __init__(self, blocker: str) -> None:
        super().__init__(blocker)
        self.blocker = blocker


class MemberQualificationExercise:
    """Exercise a second member and always reconcile the reviewed baseline."""

    _APPLICATION_ID = "fixture-restricted"

    def __init__(
        self,
        lifecycle: PlatformMemberLifecycle,
        admission: MemberAdmissionQualification,
    ) -> None:
        """Bind the existing member service and one least-data browser verifier."""

        self._lifecycle = lifecycle
        self._admission = admission

    @staticmethod
    def _require_transition(
        result: MemberLifecycleResult,
        *,
        operation: str,
        outcome: str,
        lifecycle: str,
    ) -> None:
        """Require an exact successful member transition or raise its blocker."""

        if (
            result.outcome == outcome
            and result.member_lifecycle == lifecycle
            and not result.blockers
        ):
            return
        raise _JourneyFailure(
            result.blockers[0]
            if result.blockers
            else f"QUALIFICATION_MEMBER_{operation.upper()}_FAILED"
        )

    def _verify_admission(self, expected: bool, operation: str) -> None:
        """Require one current-request decision for the restricted fixture."""

        if not self._admission.verify(self._APPLICATION_ID, expected):
            raise _JourneyFailure(
                f"LIVE_MEMBER_{operation.upper()}_ADMISSION_MISMATCH"
            )

    def _restore_temporary_member(
        self,
        environment: str,
        member_reference: str | None,
    ) -> tuple[str, ...]:
        """Remove a possibly retained temporary member without hiding failure."""

        if member_reference is None:
            return ()
        try:
            current = self._lifecycle.status(environment, member_reference)
            if current.blockers:
                return tuple(current.blockers)
            if current.member_lifecycle == "absent":
                return ()
            removed = self._lifecycle.remove(environment, member_reference)
            if (
                removed.outcome in {"removed", "unchanged"}
                and removed.member_lifecycle == "absent"
                and not removed.blockers
            ):
                return ()
            return tuple(removed.blockers) or (
                "QUALIFICATION_MEMBER_CLEANUP_FAILED",
            )
        except Exception:
            return ("QUALIFICATION_MEMBER_CLEANUP_FAILED",)

    def verify(
        self,
        environment: str,
        owner_member_reference: str,
    ) -> MemberQualificationResult:
        """Run the confirmed lifecycle and leave the owner-only baseline active.

        The initial baseline must already contain exactly the reviewed active
        owner.  The Google Visitor selected by ``add`` must be a distinct member.
        All subsequent mutations use that returned opaque reference.  A primary
        failure remains visible even when cleanup succeeds; cleanup or final
        baseline failure adds an explicit restoration-required blocker.
        """

        try:
            initial = self._lifecycle.owner_only_baseline(
                environment,
                owner_member_reference,
            )
        except Exception:
            return MemberQualificationResult(
                False,
                False,
                0,
                0,
                ("QUALIFICATION_MEMBER_BASELINE_READBACK_FAILED",),
            )
        if initial.outcome != "baseline-ready" or initial.blockers:
            return MemberQualificationResult(
                False,
                False,
                0,
                0,
                tuple(initial.blockers)
                or ("MEMBER_OWNER_BASELINE_MISMATCH",),
            )

        member_reference: str | None = None
        transitions = 0
        admission_checks = 0
        blockers: list[str] = []
        try:
            added = self._lifecycle.add(environment)
            if added.member_reference == owner_member_reference:
                raise _JourneyFailure("QUALIFICATION_MEMBER_VISITOR_NOT_DISTINCT")
            member_reference = added.member_reference
            self._require_transition(
                added,
                operation="add",
                outcome="added",
                lifecycle="active",
            )
            if member_reference is None:
                raise _JourneyFailure("QUALIFICATION_MEMBER_ADD_FAILED")
            transitions += 1
            self._verify_admission(True, "add")
            admission_checks += 1

            suspended = self._lifecycle.suspend(environment, member_reference)
            self._require_transition(
                suspended,
                operation="suspend",
                outcome="suspended",
                lifecycle="suspended",
            )
            transitions += 1
            self._verify_admission(False, "suspend")
            admission_checks += 1

            reactivated = self._lifecycle.reactivate(environment, member_reference)
            self._require_transition(
                reactivated,
                operation="reactivate",
                outcome="reactivated",
                lifecycle="active",
            )
            transitions += 1
            self._verify_admission(True, "reactivate")
            admission_checks += 1

            removed = self._lifecycle.remove(environment, member_reference)
            self._require_transition(
                removed,
                operation="remove",
                outcome="removed",
                lifecycle="absent",
            )
            transitions += 1
            self._verify_admission(False, "remove")
            admission_checks += 1
        except _JourneyFailure as error:
            blockers.append(error.blocker)
        except Exception:
            blockers.append("QUALIFICATION_MEMBER_EXERCISE_FAILED")

        cleanup_blockers = self._restore_temporary_member(
            environment,
            member_reference,
        )
        try:
            final = self._lifecycle.owner_only_baseline(
                environment,
                owner_member_reference,
            )
            final_blockers = final.blockers
            final_ready = final.outcome == "baseline-ready"
        except Exception:
            final_blockers = (
                "QUALIFICATION_MEMBER_BASELINE_READBACK_FAILED",
            )
            final_ready = False
        baseline_restored = (
            not cleanup_blockers
            and final_ready
            and not final_blockers
        )
        if not baseline_restored:
            blockers.extend(cleanup_blockers)
            blockers.extend(final_blockers)
            blockers.append(
                "QUALIFICATION_MEMBER_BASELINE_RESTORATION_REQUIRED"
            )
        verified = (
            not blockers
            and transitions == 4
            and admission_checks == 4
            and baseline_restored
        )
        return MemberQualificationResult(
            verified,
            baseline_restored,
            transitions,
            admission_checks,
            tuple(sorted(set(blockers))),
        )


__all__ = (
    "MemberAdmissionQualification",
    "MemberQualificationExercise",
    "MemberQualificationResult",
)
