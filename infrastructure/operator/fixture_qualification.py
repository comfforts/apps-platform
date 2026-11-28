"""Fixture-scoped qualification for the plural attachment handoff interface.

This module deliberately does not import or call the platform-wide qualification
lifecycle.  It binds one named fixture to an already accepted platform result,
its complete Version 3 handoff, and the active Version 2 registration before
running the smaller multi-attachment gate through injected read-only seams.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Protocol

from contracts.lifecycle import validate_lifecycle_material


_APPLICATION_ID = "fixture-multi-attachment"
_CHECKS = {
    "attachment-posture",
    "direct-origin-denial",
    "failed-target-atomicity",
    "route-selection",
    "source-integrity",
    "verified-identity",
}
_BLOCKER = re.compile(r"[A-Z][A-Z0-9_]{2,95}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")


def _canonical(value: object) -> bytes:
    """Serialize one least-data result deterministically for digest binding."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    """Return the SHA-256 digest of one canonical private result value."""

    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True, order=True)
class FixtureQualificationTarget:
    """One reviewed attachment binding retained in private qualification state."""

    attachment_id: str
    mount_path: str
    resource_reference: str
    audience: str

    @property
    def resource_reference_digest(self) -> str:
        """Return a least-data binding without exposing the provider reference."""

        return _digest(self.resource_reference)


@dataclass(frozen=True, slots=True)
class FixtureQualificationReadback:
    """Exact fixture, handoff, generation, and accepted-platform readback.

    The three handoff documents remain private inputs for provider validation and
    failure injection.  Only their digests and approved identifiers are projected
    into the persisted result.
    """

    environment: str
    application_id: str
    source_authority: str
    platform_qualification_digest: str
    platform_source_revision: str
    fixture_source_revision: str
    integration_bundle_digest: str
    attachment_bundle_digest: str
    registration_generation: int
    registration_generation_digest: str
    targets: tuple[FixtureQualificationTarget, ...]
    integration_bundle: dict[str, Any]
    attachment_bundle: dict[str, Any]
    registration_intent: dict[str, Any]

    def binding(self) -> tuple[object, ...]:
        """Return every immutable fact that must survive the evaluation reread."""

        return (
            self.environment,
            self.application_id,
            self.source_authority,
            self.platform_qualification_digest,
            self.platform_source_revision,
            self.fixture_source_revision,
            self.integration_bundle_digest,
            self.attachment_bundle_digest,
            self.registration_generation,
            self.registration_generation_digest,
            self.targets,
            _digest(self.integration_bundle),
            _digest(self.attachment_bundle),
            _digest(self.registration_intent),
        )


@dataclass(frozen=True, slots=True)
class FixtureQualificationVerification:
    """One coarse injected verification with canonical blocker codes."""

    verified: bool
    facts: Mapping[str, object]
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject inconsistent, non-canonical, or sensitive adapter output."""

        normalized = tuple(sorted(set(self.blockers)))
        if normalized != self.blockers:
            raise ValueError("fixture qualification blockers are not canonical")
        if any(_BLOCKER.fullmatch(item) is None for item in normalized):
            raise ValueError("fixture qualification blocker is invalid")
        if self.verified == bool(normalized):
            raise ValueError("fixture qualification verification is inconsistent")
        if validate_lifecycle_material(self.facts):
            raise ValueError("fixture qualification facts contain prohibited material")


@dataclass(frozen=True, slots=True)
class FixtureBrowserVerification:
    """Coarse browser result proving identity and target selection after one login."""

    verified: bool
    root_target: str | None
    api_target: str | None
    apix_target: str | None
    identity_checks: int
    blockers: tuple[str, ...] = ()


class FixtureQualificationStateReader(Protocol):
    """Read exact fixture qualification inputs without provider mutation."""

    def read_current(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureQualificationReadback:
        """Return the complete current binding or fail closed."""

        ...


class FixtureAttachmentVerifier(Protocol):
    """Verify complete provider posture and edge-only target access."""

    def verify_attachment_set(
        self,
        current: FixtureQualificationReadback,
    ) -> FixtureQualificationVerification:
        """Read and verify every target in the exact Version 3 family."""

        ...

    def verify_direct_origin_denial(
        self,
        current: FixtureQualificationReadback,
    ) -> FixtureQualificationVerification:
        """Prove both targets remain private to the Shared Edge caller."""

        ...


class FixtureBrowserVerifier(Protocol):
    """Exercise authenticated fixture routes in one browser session."""

    def verify(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureBrowserVerification:
        """Return only identity counts and safe target markers."""

        ...


class FixtureRouteVerifier(Protocol):
    """Verify the closed unauthenticated route surface without browser state."""

    def verify(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureQualificationVerification:
        """Verify root, API, and segment-boundary routing entry points."""

        ...


class FixtureFailedTargetVerifier(Protocol):
    """Exercise invalid-target refusal without a publication or activation seam."""

    def verify(
        self,
        current: FixtureQualificationReadback,
    ) -> FixtureQualificationVerification:
        """Prove root and API failure preserve the exact active generation."""

        ...


@dataclass(frozen=True, slots=True)
class FixtureQualificationPublication:
    """Private result and current-status paths returned by the evidence adapter."""

    result_path: str
    status_path: str


class FixtureQualificationEvidenceWriter(Protocol):
    """Persist one immutable result and a separate source-scoped status pointer."""

    def publish(
        self,
        result: dict[str, Any],
        result_digest: str,
    ) -> FixtureQualificationPublication:
        """Write and reread the exact least-data result and current status."""

        ...


@dataclass(frozen=True, slots=True)
class FixtureQualificationObservation:
    """One closed check result whose raw facts are hashed then discarded."""

    check_id: str
    outcome: str
    verification: str
    facts: Mapping[str, object]
    blockers: tuple[str, ...] = ()


class FixtureQualificationEvaluator:
    """Run only the plural-fixture checks through explicit injected adapters."""

    def __init__(
        self,
        attachments: FixtureAttachmentVerifier,
        browser: FixtureBrowserVerifier,
        routes: FixtureRouteVerifier,
        failed_targets: FixtureFailedTargetVerifier,
    ) -> None:
        """Bind provider, browser, route, and failed-candidate read-only seams."""

        self._attachments = attachments
        self._browser = browser
        self._routes = routes
        self._failed_targets = failed_targets

    @staticmethod
    def _observation(
        check_id: str,
        verification: str,
        result: FixtureQualificationVerification,
    ) -> FixtureQualificationObservation:
        """Convert one validated adapter result into the closed check vocabulary."""

        return FixtureQualificationObservation(
            check_id,
            "pass" if result.verified else "fail",
            verification,
            result.facts,
            result.blockers,
        )

    @staticmethod
    def _source_integrity(
        current: FixtureQualificationReadback,
    ) -> FixtureQualificationObservation:
        """Verify closed identifier, revision, digest, and attachment-set bindings."""

        target_shape = tuple(
            (item.attachment_id, item.mount_path) for item in current.targets
        )
        valid = (
            current.environment == "staging"
            and current.application_id == _APPLICATION_ID
            and current.source_authority in {"accepted", "candidate"}
            and _REVISION.fullmatch(current.platform_source_revision) is not None
            and _REVISION.fullmatch(current.fixture_source_revision) is not None
            and all(
                _DIGEST.fullmatch(value) is not None
                for value in (
                    current.platform_qualification_digest,
                    current.integration_bundle_digest,
                    current.attachment_bundle_digest,
                    current.registration_generation_digest,
                )
            )
            and current.registration_generation >= 1
            and target_shape == (("api", "/api"), ("web", "/"))
            and len({item.audience for item in current.targets}) == 1
        )
        blockers = () if valid else ("FIXTURE_SOURCE_INTEGRITY_MISMATCH",)
        return FixtureQualificationObservation(
            "source-integrity",
            "pass" if valid else "fail",
            "deterministic",
            {
                "attachment_ids": [item.attachment_id for item in current.targets],
                "bundle_family_version": 3,
                "registration_contract_version": 2,
                "result": "verified" if valid else "mismatch",
            },
            blockers,
        )

    def evaluate(
        self,
        current: FixtureQualificationReadback,
    ) -> tuple[FixtureQualificationObservation, ...]:
        """Evaluate the six fixture-only checks without platform-wide journeys."""

        observations: list[FixtureQualificationObservation] = [
            self._source_integrity(current)
        ]
        try:
            observations.append(
                self._observation(
                    "attachment-posture",
                    "provider-verified",
                    self._attachments.verify_attachment_set(current),
                )
            )
        except Exception:
            observations.append(
                FixtureQualificationObservation(
                    "attachment-posture",
                    "fail",
                    "provider-verified",
                    {"result": "adapter-failed"},
                    ("FIXTURE_ATTACHMENT_POSTURE_CHECK_FAILED",),
                )
            )
        try:
            observations.append(
                self._observation(
                    "direct-origin-denial",
                    "provider-verified",
                    self._attachments.verify_direct_origin_denial(current),
                )
            )
        except Exception:
            observations.append(
                FixtureQualificationObservation(
                    "direct-origin-denial",
                    "fail",
                    "provider-verified",
                    {"result": "adapter-failed"},
                    ("FIXTURE_DIRECT_ORIGIN_CHECK_FAILED",),
                )
            )
        try:
            observations.append(
                self._observation(
                    "route-selection",
                    "runtime-verified",
                    self._routes.verify(current.environment, current.application_id),
                )
            )
        except Exception:
            observations.append(
                FixtureQualificationObservation(
                    "route-selection",
                    "fail",
                    "runtime-verified",
                    {"result": "adapter-failed"},
                    ("FIXTURE_ROUTE_CHECK_FAILED",),
                )
            )
        try:
            browser = self._browser.verify(
                current.environment,
                current.application_id,
            )
            browser_valid = (
                browser.verified
                and browser.root_target == "web"
                and browser.api_target == "api"
                and browser.apix_target == "web"
                and browser.identity_checks == 3
                and not browser.blockers
            )
            observations.append(
                FixtureQualificationObservation(
                    "verified-identity",
                    "pass" if browser_valid else "fail",
                    "runtime-verified",
                    {
                        "browser_flows": 3,
                        "identity_checks": browser.identity_checks,
                        "route_markers": [
                            browser.root_target,
                            browser.api_target,
                            browser.apix_target,
                        ],
                        "result": "verified" if browser_valid else "mismatch",
                    },
                    (
                        ()
                        if browser_valid
                        else browser.blockers
                        or ("FIXTURE_BROWSER_IDENTITY_MISMATCH",)
                    ),
                )
            )
        except Exception:
            observations.append(
                FixtureQualificationObservation(
                    "verified-identity",
                    "fail",
                    "runtime-verified",
                    {"result": "adapter-failed"},
                    ("FIXTURE_BROWSER_CHECK_FAILED",),
                )
            )
        try:
            observations.append(
                self._observation(
                    "failed-target-atomicity",
                    "provider-verified",
                    self._failed_targets.verify(current),
                )
            )
        except Exception:
            observations.append(
                FixtureQualificationObservation(
                    "failed-target-atomicity",
                    "fail",
                    "provider-verified",
                    {"result": "adapter-failed"},
                    ("FIXTURE_FAILED_TARGET_CHECK_FAILED",),
                )
            )
        return tuple(sorted(observations, key=lambda item: item.check_id))


@dataclass(frozen=True, slots=True)
class FixtureQualificationResult:
    """Fixture-only verdict plus its separately persisted result and status paths."""

    outcome: str
    result: dict[str, Any] | None
    result_digest: str | None
    result_path: str | None
    status_path: str | None
    blockers: tuple[str, ...] = ()


class FixtureQualificationLifecycle:
    """Reread exact inputs, evaluate the fixture gate, and publish private status."""

    def __init__(
        self,
        state: FixtureQualificationStateReader,
        evaluator: FixtureQualificationEvaluator,
        evidence: FixtureQualificationEvidenceWriter,
    ) -> None:
        """Bind all read, verification, and evidence seams explicitly."""

        self._state = state
        self._evaluator = evaluator
        self._evidence = evidence

    @staticmethod
    def _blocked(*blockers: str) -> FixtureQualificationResult:
        """Return one canonical blocked result without publishing partial state."""

        return FixtureQualificationResult(
            "blocked",
            None,
            None,
            None,
            None,
            tuple(sorted(set(blockers))),
        )

    @staticmethod
    def _check_digest(facts: Mapping[str, object]) -> str | None:
        """Hash one safe observation after recursively rejecting secret material."""

        if validate_lifecycle_material(facts):
            return None
        try:
            return _digest(facts)
        except (TypeError, ValueError):
            return None

    def qualify(
        self,
        expected: FixtureQualificationReadback,
    ) -> FixtureQualificationResult:
        """Reread expected bindings, run the closed checks, and publish the verdict."""

        try:
            current = self._state.read_current(
                expected.environment,
                expected.application_id,
            )
        except Exception:
            return self._blocked("FIXTURE_QUALIFICATION_READBACK_FAILED")
        if current.binding() != expected.binding():
            return self._blocked("FIXTURE_QUALIFICATION_BINDING_CHANGED")
        try:
            observations = self._evaluator.evaluate(current)
        except Exception:
            return self._blocked("FIXTURE_QUALIFICATION_EVALUATION_FAILED")
        if {item.check_id for item in observations} != _CHECKS or len(
            observations
        ) != len(_CHECKS):
            return self._blocked("FIXTURE_QUALIFICATION_CHECK_SET_INVALID")

        blockers: set[str] = set()
        checks: list[dict[str, object]] = []
        for observation in observations:
            digest = self._check_digest(observation.facts)
            valid = (
                observation.outcome in {"pass", "fail"}
                and observation.verification
                in {"deterministic", "provider-verified", "runtime-verified"}
                and (
                    (observation.outcome == "pass" and not observation.blockers)
                    or (observation.outcome == "fail" and bool(observation.blockers))
                )
                and all(_BLOCKER.fullmatch(item) for item in observation.blockers)
                and digest is not None
            )
            if not valid:
                return self._blocked("FIXTURE_QUALIFICATION_CHECK_INVALID")
            blockers.update(observation.blockers)
            checks.append(
                {
                    "blockers": list(observation.blockers),
                    "check_id": observation.check_id,
                    "evidence_digest": digest,
                    "outcome": observation.outcome,
                    "verification": observation.verification,
                }
            )

        verdict = "failed" if blockers else "qualified"
        result: dict[str, Any] = {
            "application_id": current.application_id,
            "attachment_bundle_digest": current.attachment_bundle_digest,
            "checks": checks,
            "document_kind": "fixture-qualification-result",
            "environment": current.environment,
            "fixture_source_revision": current.fixture_source_revision,
            "format_version": 1,
            "integration_bundle_digest": current.integration_bundle_digest,
            "limitations": [
                "PLATFORM_MEMBER_LIFECYCLE_NOT_EVALUATED",
                "PLATFORM_ROLLBACK_NOT_EVALUATED",
                "REAL_APPLICATION_NOT_EVALUATED",
            ],
            "platform_qualification_digest": (
                current.platform_qualification_digest
            ),
            "platform_source_revision": current.platform_source_revision,
            "registration_generation": current.registration_generation,
            "registration_generation_digest": (
                current.registration_generation_digest
            ),
            "source_authority": current.source_authority,
            "targets": [
                {
                    "attachment_id": item.attachment_id,
                    "mount_path": item.mount_path,
                    "target_reference_digest": (
                        item.resource_reference_digest
                    ),
                }
                for item in current.targets
            ],
            "verdict": verdict,
        }
        if validate_lifecycle_material(result):
            return self._blocked("PROHIBITED_FIXTURE_QUALIFICATION_MATERIAL")
        result_digest = _digest(result)
        try:
            publication = self._evidence.publish(result, result_digest)
        except Exception:
            return self._blocked("FIXTURE_QUALIFICATION_EVIDENCE_PUBLICATION_FAILED")
        outcome = (
            "candidate-qualified"
            if verdict == "qualified" and current.source_authority == "candidate"
            else verdict
        )
        return FixtureQualificationResult(
            outcome,
            result,
            result_digest,
            publication.result_path,
            publication.status_path,
            tuple(sorted(blockers)),
        )

    def qualify_current(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureQualificationResult:
        """Discover the current fixture bindings before the mandatory evaluation reread."""

        if environment != "staging":
            return self._blocked("FIXTURE_QUALIFICATION_ENVIRONMENT_UNAVAILABLE")
        if application_id != _APPLICATION_ID:
            return self._blocked("FIXTURE_QUALIFICATION_APPLICATION_UNAVAILABLE")
        try:
            current = self._state.read_current(environment, application_id)
        except Exception:
            return self._blocked("FIXTURE_QUALIFICATION_READBACK_FAILED")
        return self.qualify(current)


__all__ = (
    "FixtureAttachmentVerifier",
    "FixtureBrowserVerification",
    "FixtureBrowserVerifier",
    "FixtureFailedTargetVerifier",
    "FixtureQualificationEvidenceWriter",
    "FixtureQualificationEvaluator",
    "FixtureQualificationLifecycle",
    "FixtureQualificationObservation",
    "FixtureQualificationPublication",
    "FixtureQualificationReadback",
    "FixtureQualificationResult",
    "FixtureQualificationStateReader",
    "FixtureQualificationTarget",
    "FixtureQualificationVerification",
    "FixtureRouteVerifier",
)
