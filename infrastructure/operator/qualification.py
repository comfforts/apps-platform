"""Revision-bound AP-M9 qualification behind two injected read-only seams."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Protocol

from contracts.lifecycle import (
    lifecycle_digest,
    validate_lifecycle_document,
    validate_lifecycle_material,
)


_CHECKS = {
    "admission-identity",
    "assertion-jwks",
    "attachment-posture",
    "catalogue-routing",
    "direct-origin-denial",
    "dns-tls",
    "isolation-limits",
    "lifecycle-rollback",
    "redaction",
    "source-integrity",
}
_VERIFICATIONS = {
    "deterministic",
    "provider-verified",
    "runtime-verified",
}


@dataclass(frozen=True, slots=True, order=True)
class ComponentRevision:
    name: str
    digest: str


@dataclass(frozen=True, slots=True, order=True)
class FixtureRevision:
    application_id: str
    application_source_revision: str
    integration_bundle_digest: str
    attachment_bundle_digest: str


@dataclass(frozen=True, slots=True)
class QualificationRequest:
    environment: str
    source_revision: str
    profile_digest: str
    specification_digest: str
    deployment_journal_digest: str
    registration_generation_digest: str
    component_revisions: tuple[ComponentRevision, ...]
    fixture_revisions: tuple[FixtureRevision, ...]


@dataclass(frozen=True, slots=True)
class QualificationReadback:
    """Closed current facts; deliberately exposes no Application State accessor."""

    environment: str
    lifecycle_state: str
    source_revision: str
    profile_digest: str
    specification_digest: str
    deployment_journal_digest: str
    registration_generation_digest: str
    component_revisions: tuple[ComponentRevision, ...]
    fixture_revisions: tuple[FixtureRevision, ...]


@dataclass(frozen=True, slots=True)
class QualificationCheckObservation:
    """One bounded result whose raw observation is scanned, hashed, then discarded."""

    check_id: str
    outcome: str
    verification: str
    observation: Mapping[str, object]
    blockers: tuple[str, ...] = ()


class QualificationStateReader(Protocol):
    def read_current(self, environment: str) -> QualificationReadback: ...


class QualificationEvaluator(Protocol):
    def evaluate(
        self,
        current: QualificationReadback,
    ) -> tuple[QualificationCheckObservation, ...]: ...


@dataclass(frozen=True, slots=True)
class QualificationResult:
    outcome: str
    evidence: dict[str, Any] | None
    evidence_digest: str | None
    blockers: tuple[str, ...] = ()


class QualificationLifecycle:
    """Validate current state and compile only redacted qualification evidence."""

    def __init__(
        self,
        state_reader: QualificationStateReader,
        evaluator: QualificationEvaluator,
    ) -> None:
        self._state_reader = state_reader
        self._evaluator = evaluator

    @staticmethod
    def _blocked(*blockers: str) -> QualificationResult:
        return QualificationResult(
            outcome="blocked",
            evidence=None,
            evidence_digest=None,
            blockers=tuple(sorted(set(blockers))),
        )

    @staticmethod
    def _readback_blockers(
        request: QualificationRequest,
        current: QualificationReadback,
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        comparisons = (
            (
                current.environment == request.environment,
                "QUALIFICATION_ENVIRONMENT_MISMATCH",
            ),
            (
                current.source_revision == request.source_revision,
                "QUALIFICATION_SOURCE_MISMATCH",
            ),
            (
                current.profile_digest == request.profile_digest,
                "QUALIFICATION_PROFILE_MISMATCH",
            ),
            (
                current.specification_digest == request.specification_digest,
                "QUALIFICATION_SPECIFICATION_MISMATCH",
            ),
            (
                current.deployment_journal_digest
                == request.deployment_journal_digest,
                "QUALIFICATION_JOURNAL_MISMATCH",
            ),
            (
                current.registration_generation_digest
                == request.registration_generation_digest,
                "QUALIFICATION_GENERATION_MISMATCH",
            ),
            (
                tuple(sorted(current.component_revisions))
                == tuple(sorted(request.component_revisions)),
                "QUALIFICATION_COMPONENT_MISMATCH",
            ),
            (
                tuple(sorted(current.fixture_revisions))
                == tuple(sorted(request.fixture_revisions)),
                "QUALIFICATION_FIXTURE_MISMATCH",
            ),
        )
        if current.lifecycle_state != "deployed":
            blockers.append("PLATFORM_NOT_DEPLOYED")
        blockers.extend(code for matches, code in comparisons if not matches)
        return tuple(sorted(set(blockers)))

    @staticmethod
    def _observation_digest(observation: Mapping[str, object]) -> str | None:
        if validate_lifecycle_material(observation):
            return None
        try:
            payload = json.dumps(
                observation,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            return None
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _fixture_value(fixture: FixtureRevision) -> dict[str, str]:
        return {
            "application_id": fixture.application_id,
            "application_source_revision": fixture.application_source_revision,
            "integration_bundle_digest": fixture.integration_bundle_digest,
            "attachment_bundle_digest": fixture.attachment_bundle_digest,
        }

    def qualify(self, request: QualificationRequest) -> QualificationResult:
        try:
            current = self._state_reader.read_current(request.environment)
        except Exception:
            return self._blocked("QUALIFICATION_READBACK_FAILED")
        readback_blockers = self._readback_blockers(request, current)
        if readback_blockers:
            return self._blocked(*readback_blockers)

        try:
            observations = self._evaluator.evaluate(current)
        except Exception:
            return self._blocked("QUALIFICATION_EVALUATION_FAILED")
        identifiers = [item.check_id for item in observations]
        if len(identifiers) != len(set(identifiers)) or set(identifiers) != _CHECKS:
            return self._blocked("QUALIFICATION_CHECK_SET_INVALID")
        if any(item.verification not in _VERIFICATIONS for item in observations):
            return self._blocked("QUALIFICATION_VERIFICATION_INVALID")
        if any(item.outcome not in {"blocked", "fail", "pass", "unavailable"} for item in observations):
            return self._blocked("QUALIFICATION_OUTCOME_INVALID")

        checks: list[dict[str, object]] = []
        result_blockers: set[str] = set()
        for item in sorted(observations, key=lambda value: value.check_id):
            evidence_digest = self._observation_digest(item.observation)
            if evidence_digest is None:
                return self._blocked("PROHIBITED_QUALIFICATION_MATERIAL")
            if item.outcome == "pass" and item.blockers:
                return self._blocked("QUALIFICATION_CHECK_INVALID")
            if item.outcome != "pass" and not item.blockers:
                return self._blocked("QUALIFICATION_CHECK_INVALID")
            result_blockers.update(item.blockers)
            checks.append(
                {
                    "check_id": item.check_id,
                    "outcome": item.outcome,
                    "verification": item.verification,
                    "evidence_digest": evidence_digest,
                    "blockers": list(sorted(set(item.blockers))),
                }
            )

        verdict = "failed" if result_blockers else "qualified"
        evidence: dict[str, Any] = {
            "contract_version": 1,
            "document_kind": "qualification-evidence",
            "environment": request.environment,
            "source_revision": request.source_revision,
            "profile_digest": request.profile_digest,
            "specification_digest": request.specification_digest,
            "deployment_journal_digest": request.deployment_journal_digest,
            "registration_generation_digest": request.registration_generation_digest,
            "component_revisions": [
                {"name": item.name, "digest": item.digest}
                for item in sorted(request.component_revisions)
            ],
            "fixture_revisions": [
                self._fixture_value(item)
                for item in sorted(request.fixture_revisions)
            ],
            "checks": checks,
            "limitations": ["DISTRIBUTED_REPLAY_PREVENTION_UNAVAILABLE"],
            "verdict": verdict,
        }
        if validate_lifecycle_document(evidence, "qualification-evidence"):
            return self._blocked("QUALIFICATION_EVIDENCE_INVALID")
        return QualificationResult(
            outcome=verdict,
            evidence=evidence,
            evidence_digest=lifecycle_digest(
                evidence,
                "qualification-evidence",
            ),
            blockers=tuple(sorted(result_blockers)),
        )


__all__ = (
    "ComponentRevision",
    "FixtureRevision",
    "QualificationCheckObservation",
    "QualificationEvaluator",
    "QualificationLifecycle",
    "QualificationReadback",
    "QualificationRequest",
    "QualificationResult",
    "QualificationStateReader",
)
