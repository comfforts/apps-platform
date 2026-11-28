"""Deterministic fixture-scoped qualification lifecycle tests."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest

from infrastructure.operator.fixture_qualification import (
    FixtureBrowserVerification,
    FixtureQualificationEvaluator,
    FixtureQualificationLifecycle,
    FixtureQualificationPublication,
    FixtureQualificationReadback,
    FixtureQualificationTarget,
    FixtureQualificationVerification,
)


def _current(authority: str = "candidate") -> FixtureQualificationReadback:
    audience = (
        "urn:comfforts:app-platform:audience:fixture-multi-attachment"
    )
    return FixtureQualificationReadback(
        environment="staging",
        application_id="fixture-multi-attachment",
        source_authority=authority,
        platform_qualification_digest="sha256:" + ("1" * 64),
        platform_source_revision="a" * 40,
        fixture_source_revision="b" * 40,
        integration_bundle_digest="sha256:" + ("2" * 64),
        attachment_bundle_digest="sha256:" + ("3" * 64),
        registration_generation=8,
        registration_generation_digest="sha256:" + ("4" * 64),
        targets=(
            FixtureQualificationTarget(
                "api",
                "/api",
                "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
                "us-west1:fixture-multi-attachment-api",
                audience,
            ),
            FixtureQualificationTarget(
                "web",
                "/",
                "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
                "us-west1:fixture-multi-attachment-web",
                audience,
            ),
        ),
        integration_bundle={"contract_version": 3},
        attachment_bundle={"contract_version": 3},
        registration_intent={"contract_version": 3},
    )


@dataclass
class State:
    current: FixtureQualificationReadback
    reads: int = 0

    def read_current(self, environment: str, application_id: str):  # type: ignore[no-untyped-def]
        self.reads += 1
        if (
            environment != self.current.environment
            or application_id != self.current.application_id
        ):
            raise ValueError("selection mismatch")
        return self.current


@dataclass
class Attachments:
    verified: bool = True

    def verify_attachment_set(self, current):  # type: ignore[no-untyped-def]
        del current
        return FixtureQualificationVerification(
            self.verified,
            {"result": "verified" if self.verified else "mismatch", "targets": 2},
            () if self.verified else ("FIXTURE_ATTACHMENT_POSTURE_MISMATCH",),
        )

    def verify_direct_origin_denial(self, current):  # type: ignore[no-untyped-def]
        del current
        return FixtureQualificationVerification(
            True,
            {"denied_targets": 2, "result": "verified"},
        )


@dataclass
class Browser:
    calls: int = 0

    def verify(self, environment: str, application_id: str):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.last = (environment, application_id)
        return FixtureBrowserVerification(True, "web", "api", "web", 3)


class Routes:
    def verify(self, environment: str, application_id: str):  # type: ignore[no-untyped-def]
        del environment, application_id
        return FixtureQualificationVerification(
            True,
            {"protected_routes": 3, "result": "verified"},
        )


class FailedTargets:
    def verify(self, current):  # type: ignore[no-untyped-def]
        del current
        return FixtureQualificationVerification(
            True,
            {
                "active_generation_preserved": True,
                "activation_attempts": 0,
                "publication_attempts": 0,
                "rejected_candidates": 2,
                "result": "verified",
            },
        )


@dataclass
class Evidence:
    values: list[dict[str, object]] = field(default_factory=list)

    def publish(self, result, result_digest):  # type: ignore[no-untyped-def]
        self.values.append(result)
        self.digest = result_digest
        return FixtureQualificationPublication(
            "fixture-qualification/result.json",
            "fixture-qualification/status.json",
        )


class FixtureQualificationLifecycleTest(unittest.TestCase):
    def _lifecycle(
        self,
        *,
        authority: str = "candidate",
        attachments: Attachments | None = None,
    ) -> tuple[FixtureQualificationLifecycle, State, Evidence, Browser]:
        state = State(_current(authority))
        evidence = Evidence()
        browser = Browser()
        lifecycle = FixtureQualificationLifecycle(
            state,
            FixtureQualificationEvaluator(
                attachments or Attachments(),
                browser,
                Routes(),
                FailedTargets(),
            ),
            evidence,
        )
        return lifecycle, state, evidence, browser

    def test_candidate_gate_rereads_and_publishes_only_fixture_bindings(self) -> None:
        lifecycle, state, evidence, browser = self._lifecycle()

        result = lifecycle.qualify_current(
            "staging",
            "fixture-multi-attachment",
        )

        self.assertEqual(result.outcome, "candidate-qualified")
        self.assertEqual(result.blockers, ())
        self.assertEqual(state.reads, 2)
        self.assertEqual(browser.calls, 1)
        self.assertEqual(len(evidence.values), 1)
        stored = evidence.values[0]
        self.assertEqual(stored["verdict"], "qualified")
        self.assertEqual(len(stored["checks"]), 6)
        self.assertEqual(
            [item["attachment_id"] for item in stored["targets"]],  # type: ignore[index]
            ["api", "web"],
        )
        serialized = repr(stored)
        self.assertNotIn("fixture-multi-attachment-api'", serialized)
        self.assertNotIn("resource_reference", serialized)
        self.assertIn("target_reference_digest", serialized)

    def test_failed_provider_check_records_failed_fixture_status(self) -> None:
        lifecycle, _state, evidence, _browser = self._lifecycle(
            authority="accepted",
            attachments=Attachments(False),
        )

        result = lifecycle.qualify_current(
            "staging",
            "fixture-multi-attachment",
        )

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(
            result.blockers,
            ("FIXTURE_ATTACHMENT_POSTURE_MISMATCH",),
        )
        self.assertEqual(evidence.values[0]["verdict"], "failed")

    def test_selection_is_closed_before_any_adapter_or_evidence_call(self) -> None:
        lifecycle, state, evidence, browser = self._lifecycle()

        result = lifecycle.qualify_current("staging", "fixture-public")

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(
            result.blockers,
            ("FIXTURE_QUALIFICATION_APPLICATION_UNAVAILABLE",),
        )
        self.assertEqual(state.reads, 0)
        self.assertEqual(browser.calls, 0)
        self.assertEqual(evidence.values, [])


if __name__ == "__main__":
    unittest.main()
