"""Validation for the small set of cross-owner lifecycle documents.

Private preparation, status, and resume progress are implementation state.  The
public contract registry contains only environment decisions, destructive scope,
application handoffs, and final qualification evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts.validation import (
    Violation,
    load_json_document,
    load_schema_registry,
    validate_contract_instance,
)


LIFECYCLE_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_DIRECTORY = LIFECYCLE_DIRECTORY / "schemas"
PROFILE_DIRECTORY = (
    LIFECYCLE_DIRECTORY.parents[1] / "infrastructure" / "config" / "profiles"
)
SCHEMA_FILES = (
    "application-attachment-bundle.v1.schema.json",
    "deployment-specification.v1.schema.json",
    "environment-profile.v1.schema.json",
    "platform-integration-bundle.v1.schema.json",
    "qualification-evidence.v1.schema.json",
)
SCHEMA_IDS = {
    "application-attachment-bundle": (
        "urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v1"
    ),
    "deployment-specification": (
        "urn:comfforts:app-platform:lifecycle:deployment-specification:v1"
    ),
    "environment-profile": (
        "urn:comfforts:app-platform:lifecycle:environment-profile:v1"
    ),
    "platform-integration-bundle": (
        "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1"
    ),
    "qualification-evidence": (
        "urn:comfforts:app-platform:lifecycle:qualification-evidence:v1"
    ),
}

_PROHIBITED_KEYS = {
    "access_token",
    "assertion",
    "browser_state",
    "credential",
    "credentials",
    "oauth_client_secret",
    "password",
    "private_key",
    "provider_response",
    "recovery_material",
    "request_body",
    "response_body",
    "restricted_members",
    "saved_plan",
    "secret",
    "secret_value",
    "session",
    "terraform_state",
}
_PROHIBITED_VALUE_MARKERS = (
    "-----begin private key-----",
    ":latest",
    ".tfplan",
    ".tfstate",
    "ghp_",
    "terraform_remote_state",
    "/versions/latest",
    "ya29.",
)
_PLACEHOLDER_MARKERS = (
    "changeme",
    "example.invalid",
    "placeholder",
    "replace-me",
    "replace_me",
    "todo",
)


@dataclass(frozen=True, slots=True)
class LifecycleDocument:
    value: dict[str, Any] | None
    canonical_bytes: bytes | None
    digest: str | None
    violations: tuple[Violation, ...]


def _pointer(path: str, token: str | int) -> str:
    encoded = str(token).replace("~", "~0").replace("/", "~1")
    return f"{path}/{encoded}" if path else f"/{encoded}"


def _ordered(violations: list[Violation]) -> tuple[Violation, ...]:
    return tuple(sorted(violations, key=lambda item: (item.path, item.code, item.message)))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def load_lifecycle_schemas(
    schema_directory: Path | None = None,
) -> dict[str, dict[str, Any]]:
    return load_schema_registry(schema_directory or SCHEMA_DIRECTORY, SCHEMA_FILES)


def _scan_prohibited(value: Any, path: str = "") -> list[Violation]:
    violations: list[Violation] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = _pointer(path, key)
            if key.lower() in _PROHIBITED_KEYS:
                violations.append(
                    Violation(
                        "PROHIBITED_MATERIAL",
                        item_path,
                        "credential, secret, state, plan, or provider payload is prohibited",
                    )
                )
            violations.extend(_scan_prohibited(item, item_path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            violations.extend(_scan_prohibited(item, _pointer(path, index)))
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in _PROHIBITED_VALUE_MARKERS):
            violations.append(
                Violation(
                    "PROHIBITED_MATERIAL",
                    path,
                    "credential, secret, state, plan, or provider payload is prohibited",
                )
            )
        if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
            violations.append(
                Violation(
                    "PLACEHOLDER_PROHIBITED",
                    path,
                    "placeholder values are prohibited",
                )
            )
    return violations


def _profile_violations(value: dict[str, Any]) -> list[Violation]:
    expected = {
        "staging": {
            "lifecycle_state": "enabled",
            "provider_class": "gcp-v1",
            "dns_provider_class": "squarespace-v1",
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
            "hostname": "apps-staging.comfforts.com",
        },
        "production": {
            "lifecycle_state": "disabled",
            "provider_class": "gcp-v1",
            "dns_provider_class": "squarespace-v1",
            "hostname": "apps.comfforts.com",
            "blockers": ["OWNERSHIP_TRANSFER_REQUIRED"],
        },
    }.get(value.get("environment"))
    if expected is None:
        return []
    return [
        Violation(
            "ENVIRONMENT_PROFILE_INVALID",
            f"/{field}",
            "field does not equal the reviewed environment value",
        )
        for field, expected_value in expected.items()
        if value.get(field) != expected_value
    ]


def _specification_violations(value: dict[str, Any]) -> list[Violation]:
    """Keep the separately confirmed destruction scope closed and ordered."""

    stages = value.get("stages")
    if not isinstance(stages, list):
        return []
    violations: list[Violation] = []
    outputs_by_stage: dict[str, set[str]] = {}
    deleted: set[str] = set()
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        stage_id = stage.get("stage_id")
        if isinstance(stage_id, str):
            if stage_id in outputs_by_stage:
                violations.append(
                    Violation(
                        "STAGE_DUPLICATE",
                        f"/stages/{index}/stage_id",
                        "stage identifiers must be unique",
                    )
                )
            produces = stage.get("produces")
            outputs_by_stage[stage_id] = (
                {item for item in produces if isinstance(item, str)}
                if isinstance(produces, list)
                else set()
            )
        if isinstance(stage.get("actions"), list) and "delete" in stage["actions"]:
            resources = stage.get("resource_types")
            if isinstance(resources, list):
                deleted.update(item for item in resources if isinstance(item, str))
        consumes = stage.get("consumes")
        if not isinstance(consumes, list):
            continue
        prior = {
            item.get("stage_id")
            for item in stages[:index]
            if isinstance(item, dict)
        }
        for binding_index, binding in enumerate(consumes):
            if not isinstance(binding, dict):
                continue
            producer = binding.get("stage_id")
            output = binding.get("output_name")
            if producer not in prior or output not in outputs_by_stage.get(
                str(producer), set()
            ):
                violations.append(
                    Violation(
                        "STAGE_BINDING_INVALID",
                        f"/stages/{index}/consumes/{binding_index}",
                        "stage input must name an output of an earlier stage",
                    )
                )
    boundary = value.get("destructive_boundary")
    if value.get("operation") == "destroy" and isinstance(boundary, dict):
        allowed = {
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
        }
        resources = boundary.get("resource_types")
        if (
            boundary.get("allowed") is not True
            or not isinstance(resources, list)
            or set(resources) != deleted
            or not deleted.issubset(allowed)
        ):
            violations.append(
                Violation(
                    "DESTRUCTIVE_BOUNDARY_INVALID",
                    "/destructive_boundary",
                    "destroy scope must exactly match allowed platform deletions",
                )
            )
    return violations


def _integration_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    access_mode = value.get("access_mode")
    identity = value.get("identity")
    endpoints = value.get("endpoints")
    application_id = value.get("application_id")
    protected = access_mode in {"authenticated", "restricted"}
    if isinstance(identity, dict):
        expected_audience = (
            f"urn:comfforts:app-platform:audience:{application_id}"
            if protected and isinstance(application_id, str)
            else None
        )
        if identity.get("audience") != expected_audience or (
            protected != isinstance(identity.get("oauth_client_id"), str)
        ):
            violations.append(
                Violation(
                    "IDENTITY_HANDOFF_INVALID",
                    "/identity",
                    "identity handoff does not match the application access mode",
                )
            )
    if isinstance(endpoints, dict):
        hostname = {
            "staging": "apps-staging.comfforts.com",
            "production": "apps.comfforts.com",
        }.get(value.get("environment"))
        if hostname is not None:
            origin = f"https://{hostname}"
            expected = {
                "external_origin": origin,
                "issuer": f"{origin}/_platform" if protected else None,
                "jwks_uri": f"{origin}/.well-known/jwks.json" if protected else None,
                "oauth_redirect_uri": (
                    f"{origin}/_platform/auth/callback" if protected else None
                ),
            }
            for field, selected in expected.items():
                if endpoints.get(field) != selected:
                    violations.append(
                        Violation(
                            "ENVIRONMENT_BINDING_INVALID",
                            f"/endpoints/{field}",
                            "endpoint does not match environment and access mode",
                        )
                    )
    return violations


def _attachment_violations(value: dict[str, Any]) -> list[Violation]:
    target = value.get("target")
    if isinstance(target, dict) and target.get("owner_application_id") != value.get(
        "application_id"
    ):
        return [
            Violation(
                "OWNER_CONFLICT",
                "/target/owner_application_id",
                "attachment owner must equal the bundle application",
            )
        ]
    return []


_QUALIFICATION_CHECKS = {
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
_QUALIFICATION_FIXTURES = {
    "fixture-authenticated",
    "fixture-public",
    "fixture-restricted",
}


def _qualification_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    verdict = value.get("verdict")
    components = value.get("component_revisions")
    fixtures = value.get("fixture_revisions")
    checks = value.get("checks")
    if isinstance(components, list):
        names = [item.get("name") for item in components if isinstance(item, dict)]
        if len(names) != len(set(names)):
            violations.append(
                Violation(
                    "QUALIFICATION_COMPONENT_CONFLICT",
                    "/component_revisions",
                    "component names must be unique",
                )
            )
    if isinstance(fixtures, list):
        fixture_ids = [
            item.get("application_id") for item in fixtures if isinstance(item, dict)
        ]
        if len(fixture_ids) != len(set(fixture_ids)):
            violations.append(
                Violation(
                    "QUALIFICATION_FIXTURE_CONFLICT",
                    "/fixture_revisions",
                    "fixture identifiers must be unique",
                )
            )
        if verdict == "qualified" and set(fixture_ids) != _QUALIFICATION_FIXTURES:
            violations.append(
                Violation(
                    "QUALIFICATION_FIXTURES_INCOMPLETE",
                    "/fixture_revisions",
                    "qualified evidence requires all three fixtures",
                )
            )
    if isinstance(checks, list):
        check_ids = [item.get("check_id") for item in checks if isinstance(item, dict)]
        if len(check_ids) != len(set(check_ids)):
            violations.append(
                Violation(
                    "QUALIFICATION_CHECK_CONFLICT",
                    "/checks",
                    "check identifiers must be unique",
                )
            )
        if verdict == "qualified" and set(check_ids) != _QUALIFICATION_CHECKS:
            violations.append(
                Violation(
                    "QUALIFICATION_CHECKS_INCOMPLETE",
                    "/checks",
                    "qualified evidence requires every mandatory check",
                )
            )
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                continue
            passing = check.get("outcome") == "pass"
            blockers = check.get("blockers")
            if passing != (blockers == []):
                violations.append(
                    Violation(
                        "QUALIFICATION_CHECK_INVALID",
                        f"/checks/{index}/blockers",
                        "passing checks have no blocker; other outcomes require one",
                    )
                )
            if verdict == "qualified" and not passing:
                violations.append(
                    Violation(
                        "QUALIFICATION_VERDICT_INVALID",
                        "/verdict",
                        "qualified evidence requires verified passing checks",
                    )
                )
            if (
                verdict == "qualified"
                and check.get("verification") == "operator-attested"
            ):
                violations.append(
                    Violation(
                        "QUALIFICATION_VERIFICATION_INVALID",
                        f"/checks/{index}/verification",
                        "operator attestation cannot replace a mandatory gate",
                    )
                )
    if verdict == "qualified" and value.get("environment") != "staging":
        violations.append(
            Violation(
                "QUALIFICATION_ENVIRONMENT_INVALID",
                "/environment",
                "this gate qualifies staging only",
            )
        )
    return violations


_POLICY = {
    "environment-profile": _profile_violations,
    "deployment-specification": _specification_violations,
    "platform-integration-bundle": _integration_violations,
    "application-attachment-bundle": _attachment_violations,
    "qualification-evidence": _qualification_violations,
}


def validate_lifecycle_document(
    value: Any,
    expected_kind: str,
    *,
    registry: dict[str, dict[str, Any]] | None = None,
) -> tuple[Violation, ...]:
    if expected_kind not in SCHEMA_IDS:
        raise ValueError(f"unknown lifecycle document kind: {expected_kind}")
    active_registry = registry or load_lifecycle_schemas()
    violations = list(
        validate_contract_instance(value, SCHEMA_IDS[expected_kind], active_registry)
    )
    violations.extend(_scan_prohibited(value))
    if isinstance(value, dict):
        if value.get("document_kind") != expected_kind:
            violations.append(
                Violation(
                    "DOCUMENT_KIND_INVALID",
                    "/document_kind",
                    "document kind does not match the selected interface",
                )
            )
        violations.extend(_POLICY[expected_kind](value))
    return _ordered(violations)


def validate_lifecycle_material(value: Any) -> tuple[Violation, ...]:
    return _ordered(_scan_prohibited(value))


def validate_lifecycle_relationships(
    *,
    integration_bundle: dict[str, Any] | None = None,
    attachment_bundle: dict[str, Any] | None = None,
) -> tuple[Violation, ...]:
    """Validate the only cross-owner document relationship."""

    violations: list[Violation] = []
    for prefix, document, kind in (
        ("integration_bundle", integration_bundle, "platform-integration-bundle"),
        ("attachment_bundle", attachment_bundle, "application-attachment-bundle"),
    ):
        if document is None:
            continue
        violations.extend(
            Violation(
                item.code,
                f"/{prefix}{item.path}" if item.path else f"/{prefix}",
                item.message,
            )
            for item in validate_lifecycle_document(document, kind)
        )
    if violations or integration_bundle is None or attachment_bundle is None:
        return _ordered(violations)

    if attachment_bundle.get("platform_integration_bundle_digest") != lifecycle_digest(
        integration_bundle,
        "platform-integration-bundle",
    ):
        violations.append(
            Violation(
                "DIGEST_MISMATCH",
                "/attachment_bundle/platform_integration_bundle_digest",
                "attachment is not bound to the exact integration bundle",
            )
        )
    for field in ("environment", "application_id"):
        if attachment_bundle.get(field) != integration_bundle.get(field):
            violations.append(
                Violation(
                    "DOCUMENT_RELATION_INVALID",
                    f"/attachment_bundle/{field}",
                    f"attachment {field} does not match integration bundle",
                )
            )
    target = attachment_bundle.get("target")
    contract = integration_bundle.get("attachment_contract")
    identity = integration_bundle.get("identity")
    if isinstance(target, dict):
        if target.get("owner_application_id") != integration_bundle.get("application_id"):
            violations.append(
                Violation(
                    "OWNER_CONFLICT",
                    "/attachment_bundle/target/owner_application_id",
                    "attachment retains the named application owner",
                )
            )
        if isinstance(contract, dict):
            for field in ("adapter_kind", "ingress_mode"):
                if target.get(field) != contract.get(field):
                    violations.append(
                        Violation(
                            "ATTACHMENT_POSTURE_INVALID",
                            f"/attachment_bundle/target/{field}",
                            "attachment violates integration contract",
                        )
                    )
        if isinstance(identity, dict):
            for target_field, identity_field in (
                ("caller_grant", "edge_caller_reference"),
                ("audience", "audience"),
            ):
                if target.get(target_field) != identity.get(identity_field):
                    violations.append(
                        Violation(
                            "ATTACHMENT_POSTURE_INVALID",
                            f"/attachment_bundle/target/{target_field}",
                            "attachment posture does not match integration bundle",
                        )
                    )
    return _ordered(violations)


def canonical_lifecycle_bytes(value: Any, expected_kind: str) -> bytes:
    violations = validate_lifecycle_document(value, expected_kind)
    if violations:
        raise ValueError(f"invalid {expected_kind}: {violations!r}")
    return _canonical_bytes(value)


def lifecycle_digest(value: Any, expected_kind: str) -> str:
    canonical = canonical_lifecycle_bytes(value, expected_kind)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def load_lifecycle_document(
    path: Path,
    expected_kind: str,
    *,
    max_bytes: int = 262_144,
) -> LifecycleDocument:
    loaded = load_json_document(path, max_bytes=max_bytes)
    if loaded.violations:
        return LifecycleDocument(None, None, None, loaded.violations)
    violations = validate_lifecycle_document(loaded.value, expected_kind)
    if violations or not isinstance(loaded.value, dict):
        return LifecycleDocument(None, None, None, violations)
    canonical = _canonical_bytes(loaded.value)
    stored = path.read_bytes()
    if stored not in {canonical, canonical + b"\n"}:
        return LifecycleDocument(
            None,
            canonical,
            None,
            (
                Violation(
                    "DOCUMENT_NOT_CANONICAL",
                    "",
                    "document bytes do not match Canonical JSON Version 1",
                ),
            ),
        )
    digest = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return LifecycleDocument(loaded.value, canonical, digest, ())
