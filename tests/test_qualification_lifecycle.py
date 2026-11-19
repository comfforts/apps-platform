"""AP-M9-W8 revision-bound qualification lifecycle tests."""

from __future__ import annotations

import copy
from dataclasses import replace
import unittest

from infrastructure.operator.qualification import (
    ComponentRevision,
    FixtureRevision,
    QualificationCheckObservation,
    QualificationLifecycle,
    QualificationReadback,
    QualificationRequest,
)


SOURCE_REVISION = "a" * 40


def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


COMPONENTS = (
    ComponentRevision("registration-compiler", _digest("5")),
    ComponentRevision("shared-edge-image", _digest("6")),
    ComponentRevision("shared-edge-runtime", _digest("7")),
)
FIXTURES = (
    FixtureRevision(
        "fixture-authenticated",
        "b" * 40,
        _digest("b"),
        _digest("e"),
    ),
    FixtureRevision(
        "fixture-public",
        "c" * 40,
        _digest("c"),
        _digest("f"),
    ),
    FixtureRevision(
        "fixture-restricted",
        "d" * 40,
        _digest("d"),
        _digest("8"),
    ),
)
CHECKS = (
    ("admission-identity", "runtime-verified"),
    ("assertion-jwks", "runtime-verified"),
    ("attachment-posture", "provider-verified"),
    ("catalogue-routing", "runtime-verified"),
    ("direct-origin-denial", "runtime-verified"),
    ("dns-tls", "provider-verified"),
    ("isolation-limits", "runtime-verified"),
    ("lifecycle-rollback", "runtime-verified"),
    ("redaction", "deterministic"),
    ("source-integrity", "provider-verified"),
)


def request() -> QualificationRequest:
    return QualificationRequest(
        environment="staging",
        source_revision=SOURCE_REVISION,
        profile_digest=_digest("1"),
        specification_digest=_digest("2"),
        deployment_journal_digest=_digest("3"),
        registration_generation_digest=_digest("4"),
        component_revisions=COMPONENTS,
        fixture_revisions=FIXTURES,
    )


def readback() -> QualificationReadback:
    expected = request()
    return QualificationReadback(
        environment=expected.environment,
        lifecycle_state="deployed",
        source_revision=expected.source_revision,
        profile_digest=expected.profile_digest,
        specification_digest=expected.specification_digest,
        deployment_journal_digest=expected.deployment_journal_digest,
        registration_generation_digest=expected.registration_generation_digest,
        component_revisions=expected.component_revisions,
        fixture_revisions=expected.fixture_revisions,
    )


def passing_observations() -> tuple[QualificationCheckObservation, ...]:
    return tuple(
        QualificationCheckObservation(
            check_id=check_id,
            outcome="pass",
            verification=verification,
            observation={"result": "verified", "subject": check_id},
        )
        for check_id, verification in CHECKS
    )


class FakeStateReader:
    def __init__(self, value: QualificationReadback | BaseException | None = None) -> None:
        self.value = value or readback()
        self.environments: list[str] = []

    def read_current(self, environment: str) -> QualificationReadback:
        self.environments.append(environment)
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value


class FakeEvaluator:
    def __init__(
        self,
        observations: tuple[QualificationCheckObservation, ...] | None = None,
    ) -> None:
        self.observations = observations or passing_observations()
        self.requests: list[QualificationReadback] = []

    def evaluate(
        self,
        current: QualificationReadback,
    ) -> tuple[QualificationCheckObservation, ...]:
        self.requests.append(current)
        return self.observations


class QualificationLifecycleTest(unittest.TestCase):
    def test_exact_complete_observations_compile_qualified_redacted_evidence(self) -> None:
        state = FakeStateReader()
        evaluator = FakeEvaluator()
        lifecycle = QualificationLifecycle(state, evaluator)

        result = lifecycle.qualify(request())

        self.assertEqual(result.outcome, "qualified")
        self.assertEqual(result.blockers, ())
        self.assertRegex(result.evidence_digest or "", r"^sha256:[0-9a-f]{64}$")
        assert result.evidence is not None
        self.assertEqual(result.evidence["verdict"], "qualified")
        self.assertEqual(
            {item["application_id"] for item in result.evidence["fixture_revisions"]},
            {fixture.application_id for fixture in FIXTURES},
        )
        rendered = str(result.evidence)
        self.assertNotIn("'result'", rendered)
        self.assertNotIn("subject", rendered)
        self.assertEqual(len(evaluator.requests), 1)

    def test_stale_or_incomplete_current_state_blocks_before_evaluation(self) -> None:
        cases = {
            "not deployed": (
                replace(readback(), lifecycle_state="deploying"),
                "PLATFORM_NOT_DEPLOYED",
            ),
            "source": (
                replace(readback(), source_revision="9" * 40),
                "QUALIFICATION_SOURCE_MISMATCH",
            ),
            "specification": (
                replace(readback(), specification_digest=_digest("9")),
                "QUALIFICATION_SPECIFICATION_MISMATCH",
            ),
            "journal": (
                replace(readback(), deployment_journal_digest=_digest("9")),
                "QUALIFICATION_JOURNAL_MISMATCH",
            ),
            "generation": (
                replace(readback(), registration_generation_digest=_digest("9")),
                "QUALIFICATION_GENERATION_MISMATCH",
            ),
            "components": (
                replace(readback(), component_revisions=COMPONENTS[:-1]),
                "QUALIFICATION_COMPONENT_MISMATCH",
            ),
            "fixtures": (
                replace(readback(), fixture_revisions=FIXTURES[:-1]),
                "QUALIFICATION_FIXTURE_MISMATCH",
            ),
        }

        for label, (current, blocker) in cases.items():
            with self.subTest(label=label):
                evaluator = FakeEvaluator()
                result = QualificationLifecycle(
                    FakeStateReader(current),
                    evaluator,
                ).qualify(request())
                self.assertEqual(result.outcome, "blocked")
                self.assertIn(blocker, result.blockers)
                self.assertIsNone(result.evidence)
                self.assertEqual(evaluator.requests, [])

    def test_failed_check_produces_truthful_failed_evidence(self) -> None:
        observations = list(passing_observations())
        observations[3] = replace(
            observations[3],
            outcome="fail",
            blockers=("CATALOGUE_MISMATCH",),
        )

        result = QualificationLifecycle(
            FakeStateReader(),
            FakeEvaluator(tuple(observations)),
        ).qualify(request())

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.blockers, ("CATALOGUE_MISMATCH",))
        assert result.evidence is not None
        self.assertEqual(result.evidence["verdict"], "failed")
        failed = [
            item for item in result.evidence["checks"] if item["outcome"] == "fail"
        ]
        self.assertEqual(failed[0]["check_id"], "catalogue-routing")

    def test_incomplete_duplicate_or_attested_checks_fail_closed(self) -> None:
        cases: dict[str, tuple[QualificationCheckObservation, ...]] = {
            "incomplete": passing_observations()[:-1],
            "duplicate": (
                *passing_observations()[:-1],
                passing_observations()[0],
            ),
            "attested": (
                replace(
                    passing_observations()[0],
                    verification="operator-attested",
                ),
                *passing_observations()[1:],
            ),
        }

        for label, observations in cases.items():
            with self.subTest(label=label):
                result = QualificationLifecycle(
                    FakeStateReader(),
                    FakeEvaluator(observations),
                ).qualify(request())
                self.assertEqual(result.outcome, "blocked")
                self.assertIsNone(result.evidence)

    def test_prohibited_observation_is_never_hashed_or_retained(self) -> None:
        observations = list(passing_observations())
        observations[0] = replace(
            observations[0],
            observation={"session": "sensitive-value"},
        )

        result = QualificationLifecycle(
            FakeStateReader(),
            FakeEvaluator(tuple(observations)),
        ).qualify(request())

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.blockers, ("PROHIBITED_QUALIFICATION_MATERIAL",))
        self.assertIsNone(result.evidence)
        self.assertNotIn("sensitive-value", repr(result))

    def test_readback_or_evaluator_failure_is_coarse_and_fail_closed(self) -> None:
        readback_failure = QualificationLifecycle(
            FakeStateReader(RuntimeError("sensitive provider error")),
            FakeEvaluator(),
        ).qualify(request())

        class RaisingEvaluator(FakeEvaluator):
            def evaluate(
                self,
                current: QualificationReadback,
            ) -> tuple[QualificationCheckObservation, ...]:
                del current
                raise RuntimeError("sensitive runtime error")

        evaluator_failure = QualificationLifecycle(
            FakeStateReader(),
            RaisingEvaluator(),
        ).qualify(request())

        self.assertEqual(
            readback_failure.blockers,
            ("QUALIFICATION_READBACK_FAILED",),
        )
        self.assertEqual(
            evaluator_failure.blockers,
            ("QUALIFICATION_EVALUATION_FAILED",),
        )
        self.assertNotIn("sensitive", repr(readback_failure))
        self.assertNotIn("sensitive", repr(evaluator_failure))


if __name__ == "__main__":
    unittest.main()
