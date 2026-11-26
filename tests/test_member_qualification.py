"""Qualification-only composition of the existing member lifecycle service."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from infrastructure.operator.member_lifecycle import MemberLifecycleResult
from infrastructure.operator.member_qualification import MemberQualificationExercise


OWNER = "pmr1_" + "1" * 64
SECOND = "pmr1_" + "2" * 64


@dataclass
class Lifecycle:
    """Record exact lifecycle calls while modeling one temporary member."""

    second_state: str = "absent"
    fail_operation: str | None = None
    cleanup_fails: bool = False
    baseline_fails_at: int | None = None
    baseline_reads: int = 0
    calls: list[tuple[str, str | None]] = field(default_factory=list)

    def owner_only_baseline(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("baseline", reference))
        self.baseline_reads += 1
        if self.baseline_fails_at == self.baseline_reads:
            raise RuntimeError("private provider detail")
        ready = environment == "staging" and reference == OWNER and self.second_state == "absent"
        return MemberLifecycleResult(
            "baseline-ready" if ready else "conflicting",
            "ready",
            reference,
            "active",
            1,
            () if ready else ("MEMBER_OWNER_BASELINE_MISMATCH",),
        )

    def add(self, environment: str) -> MemberLifecycleResult:
        self.calls.append(("add", None))
        if self.fail_operation == "add":
            return MemberLifecycleResult(
                "blocked",
                "ready",
                SECOND,
                "absent",
                1,
                ("MEMBER_ACTION_NOT_CONFIRMED",),
            )
        self.second_state = "active"
        return MemberLifecycleResult("added", "ready", SECOND, "active", 2)

    def suspend(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("suspend", reference))
        if self.fail_operation == "suspend":
            return MemberLifecycleResult(
                "blocked",
                "ready",
                reference,
                self.second_state,  # type: ignore[arg-type]
                2,
                ("MEMBER_ACTION_NOT_CONFIRMED",),
            )
        self.second_state = "suspended"
        return MemberLifecycleResult("suspended", "ready", reference, "suspended", 3)

    def reactivate(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("reactivate", reference))
        self.second_state = "active"
        return MemberLifecycleResult("reactivated", "ready", reference, "active", 4)

    def remove(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("remove", reference))
        if self.cleanup_fails:
            return MemberLifecycleResult(
                "blocked",
                "ready",
                reference,
                self.second_state,  # type: ignore[arg-type]
                4,
                ("MEMBER_ACTION_NOT_CONFIRMED",),
            )
        self.second_state = "absent"
        return MemberLifecycleResult("removed", "ready", reference, "absent", 5)

    def status(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("status", reference))
        return MemberLifecycleResult(
            "read",
            "ready",
            reference,
            self.second_state,  # type: ignore[arg-type]
            5,
        )


@dataclass
class Admission:
    """Return exact expected route decisions while retaining no identity."""

    fail_at: int | None = None
    calls: list[tuple[str, bool]] = field(default_factory=list)

    def verify(self, application_id: str, expected_admitted: bool) -> bool:
        self.calls.append((application_id, expected_admitted))
        return self.fail_at != len(self.calls)


class MemberQualificationExerciseTest(unittest.TestCase):
    def test_complete_second_member_journey_restores_owner_only_baseline(self) -> None:
        lifecycle = Lifecycle()
        admission = Admission()
        exercise = MemberQualificationExercise(lifecycle, admission)  # type: ignore[arg-type]

        result = exercise.verify("staging", OWNER)

        self.assertTrue(result.verified)
        self.assertTrue(result.baseline_restored)
        self.assertEqual(result.member_transitions, 4)
        self.assertEqual(result.admission_checks, 4)
        self.assertEqual(result.blockers, ())
        self.assertEqual(
            admission.calls,
            [
                ("fixture-restricted", True),
                ("fixture-restricted", False),
                ("fixture-restricted", True),
                ("fixture-restricted", False),
            ],
        )
        self.assertEqual(lifecycle.calls[0], ("baseline", OWNER))
        self.assertEqual(lifecycle.calls[-1], ("baseline", OWNER))
        self.assertNotIn(OWNER, repr(result))
        self.assertNotIn(SECOND, repr(result))

    def test_failure_removes_the_temporary_member_before_returning(self) -> None:
        lifecycle = Lifecycle(fail_operation="suspend")
        exercise = MemberQualificationExercise(lifecycle, Admission())  # type: ignore[arg-type]

        result = exercise.verify("staging", OWNER)

        self.assertFalse(result.verified)
        self.assertTrue(result.baseline_restored)
        self.assertIn("MEMBER_ACTION_NOT_CONFIRMED", result.blockers)
        self.assertIn(("remove", SECOND), lifecycle.calls)
        self.assertEqual(lifecycle.second_state, "absent")

    def test_cleanup_failure_is_an_explicit_stop_condition(self) -> None:
        lifecycle = Lifecycle(fail_operation="suspend", cleanup_fails=True)
        exercise = MemberQualificationExercise(lifecycle, Admission())  # type: ignore[arg-type]

        result = exercise.verify("staging", OWNER)

        self.assertFalse(result.verified)
        self.assertFalse(result.baseline_restored)
        self.assertIn(
            "QUALIFICATION_MEMBER_BASELINE_RESTORATION_REQUIRED",
            result.blockers,
        )

    def test_final_baseline_read_failure_is_redacted_and_requires_restoration(self) -> None:
        lifecycle = Lifecycle(baseline_fails_at=2)
        exercise = MemberQualificationExercise(lifecycle, Admission())  # type: ignore[arg-type]

        result = exercise.verify("staging", OWNER)

        self.assertFalse(result.verified)
        self.assertFalse(result.baseline_restored)
        self.assertEqual(
            result.blockers,
            (
                "QUALIFICATION_MEMBER_BASELINE_READBACK_FAILED",
                "QUALIFICATION_MEMBER_BASELINE_RESTORATION_REQUIRED",
            ),
        )
        self.assertNotIn("private provider detail", repr(result))


if __name__ == "__main__":
    unittest.main()
