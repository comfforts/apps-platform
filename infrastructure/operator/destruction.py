"""Fail-closed AP-M9 environment-destruction specification compiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts.lifecycle import lifecycle_digest, validate_lifecycle_document


DESTRUCTIBLE_PLATFORM_RESOURCES = (
    "artifact-registry",
    "budget",
    "configuration-bucket",
    "dns-a-record",
    "load-balancer",
    "logging",
    "managed-certificate",
    "oauth-client",
    "oauth-secret-version",
    "operation-identity",
    "platform-identity",
    "reserved-address",
    "secret-container",
    "session-store",
    "shared-edge",
    "shared-edge-image",
    "signing-key",
)

# These resources require separately approved purge or recovery authority.
RETAINED_PLATFORM_RESOURCES = (
    "backend-bucket",
    "evidence-bucket",
    "recovery-copy",
    "state-backend",
)


@dataclass(frozen=True, slots=True)
class DestructionRequest:
    """Exact reviewed revisions that one destruction operation must consume."""

    environment: str
    source_revision: str
    profile_digest: str
    deployed_specification_digest: str
    deployment_journal_digest: str
    registration_generation_digest: str
    qualification_evidence_digest: str


@dataclass(frozen=True, slots=True)
class DestructionSnapshot:
    """Current closed inventory read before a destructive spec can be prepared."""

    environment: str
    lifecycle_state: str
    source_revision: str
    profile_digest: str
    deployed_specification_digest: str
    deployment_journal_digest: str
    registration_generation_digest: str
    qualification_evidence_digest: str
    active_application_ids: tuple[str, ...]
    platform_resource_types: tuple[str, ...]
    retained_resource_types: tuple[str, ...]
    ownership_matches: bool


@dataclass(frozen=True, slots=True)
class DestructionPreparationResult:
    outcome: str
    specification: dict[str, Any] | None = None
    specification_digest: str | None = None
    blockers: tuple[str, ...] = ()


def _binding(stage_id: str, output_name: str) -> dict[str, str]:
    return {"stage_id": stage_id, "output_name": output_name}


def _destruction_stages() -> list[dict[str, object]]:
    """Return the only ordered deletion graph authorized by AP-M9-W8."""

    return [
        {
            "stage_id": "destruction-preflight",
            "actions": ["read"],
            "resource_types": [
                "ownership-inventory",
                "platform-environment",
                "registration-generation",
            ],
            "consumes": [],
            "produces": ["destruction-attestation"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "traffic-disable",
            "actions": ["read", "update"],
            "resource_types": ["shared-edge"],
            "consumes": [
                _binding("destruction-preflight", "destruction-attestation")
            ],
            "produces": ["traffic-disabled"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "external-dns-destroy",
            "actions": ["delete", "read"],
            "resource_types": ["dns-a-record"],
            "consumes": [_binding("traffic-disable", "traffic-disabled")],
            "produces": ["dns-removed"],
            "manual_checkpoint": "external-dns",
            "readback": "provider-verified",
        },
        {
            "stage_id": "edge-destroy",
            "actions": ["delete", "read"],
            "resource_types": [
                "load-balancer",
                "managed-certificate",
                "reserved-address",
                "shared-edge",
            ],
            "consumes": [_binding("external-dns-destroy", "dns-removed")],
            "produces": ["edge-destroyed"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "identity-destroy",
            "actions": ["delete", "read"],
            "resource_types": [
                "oauth-client",
                "oauth-secret-version",
                "session-store",
                "signing-key",
            ],
            "consumes": [_binding("edge-destroy", "edge-destroyed")],
            "produces": ["identity-destroyed"],
            "manual_checkpoint": "provider-console",
            "readback": "provider-verified",
        },
        {
            "stage_id": "foundation-destroy",
            "actions": ["delete", "read"],
            "resource_types": [
                "artifact-registry",
                "budget",
                "configuration-bucket",
                "logging",
                "operation-identity",
                "platform-identity",
                "secret-container",
                "shared-edge-image",
            ],
            "consumes": [_binding("identity-destroy", "identity-destroyed")],
            "produces": ["foundation-destroyed"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "destruction-readback",
            "actions": ["read"],
            "resource_types": ["ownership-inventory", "platform-environment"],
            "consumes": [
                _binding("foundation-destroy", "foundation-destroyed")
            ],
            "produces": ["destruction-complete"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
    ]


def _blockers(
    request: DestructionRequest,
    snapshot: DestructionSnapshot,
) -> tuple[str, ...]:
    blockers: list[str] = []
    comparisons = (
        (snapshot.environment, request.environment, "DESTRUCTION_ENVIRONMENT_MISMATCH"),
        (snapshot.source_revision, request.source_revision, "DESTRUCTION_SOURCE_MISMATCH"),
        (snapshot.profile_digest, request.profile_digest, "DESTRUCTION_PROFILE_MISMATCH"),
        (
            snapshot.deployed_specification_digest,
            request.deployed_specification_digest,
            "DESTRUCTION_SPECIFICATION_MISMATCH",
        ),
        (
            snapshot.deployment_journal_digest,
            request.deployment_journal_digest,
            "DESTRUCTION_JOURNAL_MISMATCH",
        ),
        (
            snapshot.registration_generation_digest,
            request.registration_generation_digest,
            "DESTRUCTION_GENERATION_MISMATCH",
        ),
        (
            snapshot.qualification_evidence_digest,
            request.qualification_evidence_digest,
            "DESTRUCTION_EVIDENCE_MISMATCH",
        ),
    )
    blockers.extend(code for actual, expected, code in comparisons if actual != expected)
    if snapshot.lifecycle_state != "deployed":
        blockers.append("ENVIRONMENT_NOT_DEPLOYED")
    if snapshot.active_application_ids:
        blockers.append("ACTIVE_APPLICATION_ATTACHMENTS")
    if not snapshot.ownership_matches:
        blockers.append("DESTRUCTION_OWNERSHIP_MISMATCH")
    if tuple(sorted(snapshot.platform_resource_types)) != DESTRUCTIBLE_PLATFORM_RESOURCES:
        blockers.append("DESTRUCTION_INVENTORY_MISMATCH")
    if tuple(sorted(snapshot.retained_resource_types)) != RETAINED_PLATFORM_RESOURCES:
        blockers.append("DESTRUCTION_RETAINED_INVENTORY_MISMATCH")
    return tuple(sorted(set(blockers)))


def compile_destruction_specification(
    request: DestructionRequest,
    snapshot: DestructionSnapshot,
) -> DestructionPreparationResult:
    """Compile one separate exact destroy spec, or return closed blocker codes."""

    blockers = _blockers(request, snapshot)
    if blockers:
        return DestructionPreparationResult(outcome="blocked", blockers=blockers)

    specification: dict[str, Any] = {
        "contract_version": 1,
        "document_kind": "deployment-specification",
        "environment": request.environment,
        "operation": "destroy",
        "profile_digest": request.profile_digest,
        "source": {
            "repository": "comfforts/apps-platform",
            "revision": request.source_revision,
        },
        "stages": _destruction_stages(),
        "failure_behavior": "stop",
        "destructive_boundary": {
            "allowed": True,
            "resource_types": list(DESTRUCTIBLE_PLATFORM_RESOURCES),
        },
    }
    violations = validate_lifecycle_document(
        specification,
        "deployment-specification",
    )
    if violations:
        return DestructionPreparationResult(
            outcome="blocked",
            blockers=("DESTRUCTION_SPECIFICATION_INVALID",),
        )
    return DestructionPreparationResult(
        outcome="prepared",
        specification=specification,
        specification_digest=lifecycle_digest(
            specification,
            "deployment-specification",
        ),
    )
