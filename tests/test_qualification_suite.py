"""AP-M9-W8 closed qualification profile and failure-injection tests."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from infrastructure.operator.qualification import (
    QUALIFICATION_CHECK_CAPABILITIES,
    ComponentRevision,
    FixtureRevision,
    QualificationFailureInjection,
    QualificationProbeOutcome,
    QualificationProbeRequest,
    QualificationReadback,
    QualificationSuiteEvaluator,
)


def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


def readback() -> QualificationReadback:
    return QualificationReadback(
        environment="staging",
        lifecycle_state="deployed",
        source_revision="a" * 40,
        profile_digest=_digest("1"),
        specification_digest=_digest("2"),
        deployment_progress_digest=_digest("3"),
        registration_generation_digest=_digest("4"),
        component_revisions=(
            ComponentRevision("fixture-image", _digest("5")),
            ComponentRevision("shared-edge-image", _digest("6")),
        ),
        fixture_revisions=tuple(
            FixtureRevision(
                application_id=f"fixture-{mode}",
                application_source_revision=character * 40,
                integration_bundle_digest=_digest(character),
                attachment_bundle_digest=_digest(character.upper()),
            )
            for mode, character in (
                ("authenticated", "a"),
                ("public", "b"),
                ("restricted", "c"),
            )
        ),
    )


@dataclass
class RecordingProbe:
    failures: dict[str, str] = field(default_factory=dict)
    requests: list[QualificationProbeRequest] = field(default_factory=list)

    def evaluate(self, request: QualificationProbeRequest) -> QualificationProbeOutcome:
        self.requests.append(request)
        blocker = self.failures.get(request.check_id)
        return QualificationProbeOutcome(
            outcome="fail" if blocker else "pass",
            observation={
                "capabilities": list(request.capabilities),
                "check_id": request.check_id,
                "revision_count": (
                    len(request.current.component_revisions)
                    + len(request.current.fixture_revisions)
                ),
            },
            blockers=(blocker,) if blocker else (),
        )


class QualificationSuiteTest(unittest.TestCase):
    def test_profile_covers_every_required_live_behavior_once(self) -> None:
        expected = {
            "active-generation",
            "application-feature-denial",
            "attachment-iam",
            "authenticated-membership-independence",
            "cache-window",
            "catalogue",
            "component-revisions",
            "concurrency",
            "cross-application-isolation",
            "detachment",
            "direct-origin-denial",
            "directory-unavailability",
            "dns",
            "download",
            "expired-session",
            "failure-isolation",
            "fixture-revisions",
            "http",
            "jwks",
            "logout",
            "member-add",
            "member-reactivate",
            "member-remove",
            "member-suspend",
            "mount-rewrite",
            "oauth",
            "owner-only-member-baseline",
            "public-identity-none",
            "public-identity-optional",
            "reactivation",
            "redaction",
            "restricted-member-admission",
            "retirement",
            "rollback",
            "route-selection",
            "session",
            "signed-assertion",
            "source-revision",
            "sse",
            "stale-member-cache-bound",
            "stream-limits",
            "timeout",
            "tls",
            "upload",
            "visitor-header-replacement",
            "websocket",
        }
        flattened = [
            capability
            for capabilities in QUALIFICATION_CHECK_CAPABILITIES.values()
            for capability in capabilities
        ]

        self.assertEqual(set(flattened), expected)
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertEqual(len(QUALIFICATION_CHECK_CAPABILITIES), 10)

    def test_suite_runs_the_closed_profile_against_one_exact_readback(self) -> None:
        probe = RecordingProbe()
        evaluator = QualificationSuiteEvaluator(probe)
        current = readback()

        observations = evaluator.evaluate(current)

        self.assertEqual(len(observations), 10)
        self.assertEqual(
            [item.check_id for item in observations],
            [
                *sorted(
                    set(QUALIFICATION_CHECK_CAPABILITIES)
                    - {"lifecycle-rollback"}
                ),
                "lifecycle-rollback",
            ],
        )
        self.assertEqual(
            [request.check_id for request in probe.requests],
            [item.check_id for item in observations],
        )
        self.assertTrue(all(request.current is current for request in probe.requests))
        self.assertTrue(all(item.outcome == "pass" for item in observations))
        self.assertEqual(
            {item.verification for item in observations},
            {"deterministic", "provider-verified", "runtime-verified"},
        )

    def test_probe_failure_is_coarse_and_stops_that_check_from_passing(self) -> None:
        probe = RecordingProbe(failures={"dns-tls": "DNS_MISMATCH"})

        observations = QualificationSuiteEvaluator(probe).evaluate(readback())

        failed = next(item for item in observations if item.check_id == "dns-tls")
        self.assertEqual(failed.outcome, "fail")
        self.assertEqual(failed.blockers, ("DNS_MISMATCH",))
        self.assertNotIn("provider", repr(failed.observation).lower())
        rollback = next(
            item for item in observations if item.check_id == "lifecycle-rollback"
        )
        self.assertEqual(rollback.outcome, "blocked")
        self.assertEqual(
            rollback.blockers,
            ("QUALIFICATION_ROLLBACK_PREREQUISITE_FAILED",),
        )
        self.assertNotIn(
            "lifecycle-rollback",
            {request.check_id for request in probe.requests},
        )

    def test_deterministic_failure_injection_bypasses_external_probe(self) -> None:
        probe = RecordingProbe()
        injection = QualificationFailureInjection(
            check_id="isolation-limits",
            blocker="INJECTED_FAILURE_ISOLATION",
        )

        observations = QualificationSuiteEvaluator(
            probe,
            failure_injections=(injection,),
        ).evaluate(readback())

        failed = next(
            item for item in observations if item.check_id == "isolation-limits"
        )
        self.assertEqual(failed.outcome, "fail")
        self.assertEqual(failed.verification, "deterministic")
        self.assertEqual(failed.blockers, ("INJECTED_FAILURE_ISOLATION",))
        self.assertNotIn(
            "isolation-limits",
            {request.check_id for request in probe.requests},
        )

    def test_invalid_injection_or_probe_result_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "qualification check"):
            QualificationFailureInjection(
                check_id="unknown-check",
                blocker="INJECTED_UNKNOWN",
            )
        with self.assertRaisesRegex(ValueError, "blocker"):
            QualificationFailureInjection(
                check_id="dns-tls",
                blocker="raw provider error: secret",
            )

        @dataclass
        class InvalidProbe:
            def evaluate(
                self,
                request: QualificationProbeRequest,
            ) -> QualificationProbeOutcome:
                del request
                return QualificationProbeOutcome(
                    outcome="pass",
                    observation={"result": "ok"},
                    blockers=("IMPOSSIBLE_PASS_BLOCKER",),
                )

        failed = QualificationSuiteEvaluator(InvalidProbe()).evaluate(readback())
        self.assertTrue(
            all(
                item.outcome == "fail"
                for item in failed
                if item.check_id != "lifecycle-rollback"
            )
        )
        self.assertTrue(
            all(
                item.blockers == ("QUALIFICATION_PROBE_RESULT_INVALID",)
                for item in failed
                if item.check_id != "lifecycle-rollback"
            )
        )
        rollback = next(
            item for item in failed if item.check_id == "lifecycle-rollback"
        )
        self.assertEqual(rollback.outcome, "blocked")
        self.assertEqual(
            rollback.blockers,
            ("QUALIFICATION_ROLLBACK_PREREQUISITE_FAILED",),
        )


if __name__ == "__main__":
    unittest.main()
