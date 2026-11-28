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
    "application-attachment-bundle.v2.schema.json",
    "application-attachment-bundle.v3.schema.json",
    "deployment-specification.v1.schema.json",
    "environment-profile.v1.schema.json",
    "platform-integration-bundle.v1.schema.json",
    "platform-integration-bundle.v2.schema.json",
    "platform-integration-bundle.v3.schema.json",
    "qualification-evidence.v1.schema.json",
    "registration-intent.v2.schema.json",
    "registration-intent.v3.schema.json",
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
VERSIONED_SCHEMA_IDS = {
    "application-attachment-bundle": {
        1: "urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v1",
        2: "urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v2",
        3: "urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v3",
    },
    "platform-integration-bundle": {
        1: "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1",
        2: "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v2",
        3: "urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v3",
    },
    "registration-intent": {
        2: "urn:comfforts:app-platform:lifecycle:registration-intent:v2",
        3: "urn:comfforts:app-platform:lifecycle:registration-intent:v3",
    },
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
    """Append one escaped token to a JSON Pointer without mutating input."""

    encoded = str(token).replace("~", "~0").replace("/", "~1")
    return f"{path}/{encoded}" if path else f"/{encoded}"


def _ordered(violations: list[Violation]) -> tuple[Violation, ...]:
    """Return violations in stable path, code, and message order."""

    return tuple(sorted(violations, key=lambda item: (item.path, item.code, item.message)))


def _canonical_bytes(value: Any) -> bytes:
    """Serialize an in-memory value with the repository's canonical JSON rules."""

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
    """Load the fixed local lifecycle registry without remote resolution.

    ``schema_directory`` may replace the default only for deterministic verification. The function
    reads every reviewed filename in ``SCHEMA_FILES`` and returns its identifier-indexed schema;
    malformed, missing, duplicate, unsupported, or remotely referenced schemas raise the closed
    registry errors from ``load_schema_registry``. No provider or repository state is changed.
    """

    return load_schema_registry(schema_directory or SCHEMA_DIRECTORY, SCHEMA_FILES)


def _scan_prohibited(value: Any, path: str = "") -> list[Violation]:
    """Recursively report secret, state, plan, provider, and placeholder material."""

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


def _scan_member_material(value: Any, path: str = "") -> list[Violation]:
    """Return violations for directory data nested anywhere in a V2 or V3 handoff."""

    member_keys = {
        "member",
        "member_list",
        "member_records",
        "members",
        "platform_members",
        "restricted_members",
    }
    violations: list[Violation] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = _pointer(path, key)
            if key.lower() in member_keys:
                violations.append(
                    Violation(
                        "PROHIBITED_MATERIAL",
                        item_path,
                        "member data is prohibited from Version 2 and Version 3 handoffs",
                    )
                )
            violations.extend(_scan_member_material(item, item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_scan_member_material(item, _pointer(path, index)))
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
    """Validate V1 through V3 identity values against admission and delivery policy."""

    violations: list[Violation] = []
    access_mode = value.get("access_mode")
    contract_version = value.get("contract_version")
    identity_delivery = value.get("identity_delivery")
    identity = value.get("identity")
    endpoints = value.get("endpoints")
    application_id = value.get("application_id")
    identity_enabled = (
        identity_delivery in {"optional", "required"}
        if contract_version in {2, 3}
        else access_mode in {"authenticated", "restricted"}
    )
    if isinstance(identity, dict):
        expected_audience = (
            f"urn:comfforts:app-platform:audience:{application_id}"
            if identity_enabled and isinstance(application_id, str)
            else None
        )
        if identity.get("audience") != expected_audience or (
            identity_enabled != isinstance(identity.get("oauth_client_id"), str)
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
                "issuer": f"{origin}/_platform" if identity_enabled else None,
                "jwks_uri": f"{origin}/.well-known/jwks.json" if identity_enabled else None,
                "oauth_redirect_uri": (
                    f"{origin}/_platform/auth/callback" if identity_enabled else None
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
    """Validate root/additional ownership, identifier uniqueness, and canonical order."""

    violations: list[Violation] = []
    targets: list[tuple[str, dict[str, Any]]] = []
    target = value.get("target")
    if isinstance(target, dict):
        targets.append(("/target", target))
    additional = value.get("additional_attachments")
    identifiers: list[str] = []
    if isinstance(additional, list):
        seen: set[str] = set()
        for index, entry in enumerate(additional):
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("attachment_id")
            if isinstance(identifier, str):
                identifiers.append(identifier)
                if identifier in seen:
                    violations.append(
                        Violation(
                            "ATTACHMENT_ID_CONFLICT",
                            f"/additional_attachments/{index}/attachment_id",
                            "additional attachment identifier is not unique",
                        )
                    )
                seen.add(identifier)
            additional_target = entry.get("target")
            if isinstance(additional_target, dict):
                targets.append(
                    (f"/additional_attachments/{index}/target", additional_target)
                )
        if identifiers != sorted(identifiers):
            violations.append(
                Violation(
                    "ATTACHMENT_ORDER_INVALID",
                    "/additional_attachments",
                    "additional attachments must be sorted by attachment_id",
                )
            )
    resource_references: set[str] = set()
    for path, selected in targets:
        if selected.get("owner_application_id") != value.get("application_id"):
            violations.append(
                Violation(
                    "OWNER_CONFLICT",
                    f"{path}/owner_application_id",
                    "attachment owner must equal the bundle application",
                )
            )
        resource_reference = selected.get("resource_reference")
        if isinstance(resource_reference, str):
            if resource_reference in resource_references:
                violations.append(
                    Violation(
                        "ATTACHMENT_TARGET_CONFLICT",
                        f"{path}/resource_reference",
                        "one target resource cannot occupy multiple attachment entries",
                    )
                )
            resource_references.add(resource_reference)
    return violations


def _registration_intent_violations(value: dict[str, Any]) -> list[Violation]:
    """Validate Version 3 root and canonical additional binding relationships."""

    if value.get("contract_version") != 3:
        return []
    violations: list[Violation] = []
    if value.get("mount_path") != "/":
        violations.append(
            Violation(
                "ROOT_MOUNT_INVALID",
                "/mount_path",
                "the required root attachment must be mounted at /",
            )
        )
    bindings = value.get("additional_attachment_bindings")
    if not isinstance(bindings, list):
        return violations
    root_id = value.get("attachment_id")
    identifiers: list[str] = []
    seen_ids: set[str] = set()
    seen_mounts = {"/"}
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            continue
        identifier = binding.get("attachment_id")
        if isinstance(identifier, str):
            identifiers.append(identifier)
            if identifier == root_id or identifier in seen_ids:
                violations.append(
                    Violation(
                        "ATTACHMENT_ID_CONFLICT",
                        f"/additional_attachment_bindings/{index}/attachment_id",
                        "additional binding identifier repeats the root or another binding",
                    )
                )
            seen_ids.add(identifier)
        mount = binding.get("mount_path")
        if isinstance(mount, str):
            if mount in seen_mounts:
                violations.append(
                    Violation(
                        "ATTACHMENT_MOUNT_CONFLICT",
                        f"/additional_attachment_bindings/{index}/mount_path",
                        "attachment mount is already used in this intent",
                    )
                )
            seen_mounts.add(mount)
    if identifiers != sorted(identifiers):
        violations.append(
            Violation(
                "ATTACHMENT_ORDER_INVALID",
                "/additional_attachment_bindings",
                "additional bindings must be sorted by attachment_id",
            )
        )
    return violations


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
    "registration-intent": _registration_intent_violations,
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


def validate_versioned_lifecycle_document(
    value: Any,
    expected_kind: str,
    *,
    registry: dict[str, dict[str, Any]] | None = None,
) -> tuple[Violation, ...]:
    """Validate one readable V1, V2, or V3 handoff without side effects.

    The selected kind and embedded version choose the closed local schema. The result contains
    deterministic, path-qualified schema, prohibited-material, member-data, kind, and semantic
    violations; an empty tuple means the document is valid. Unknown kinds raise ``ValueError`` and
    unsupported versions return ``CONTRACT_VERSION_UNSUPPORTED`` without schema discovery.
    """

    versions = VERSIONED_SCHEMA_IDS.get(expected_kind)
    if versions is None:
        raise ValueError(f"unknown versioned lifecycle document kind: {expected_kind}")
    if not isinstance(value, dict):
        return (Violation("FIELD_TYPE", "", "document must be an object"),)
    version = value.get("contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version not in versions:
        return (
            Violation(
                "CONTRACT_VERSION_UNSUPPORTED",
                "/contract_version",
                "document contract version is not readable for this interface",
            ),
        )
    active_registry = registry or load_lifecycle_schemas()
    violations = list(
        validate_contract_instance(value, versions[version], active_registry)
    )
    violations.extend(_scan_prohibited(value))
    if version in {2, 3}:
        violations.extend(_scan_member_material(value))
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
    """Return stable prohibited-material violations for any in-memory value."""

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


def _target_relationship_violations(
    target: dict[str, Any],
    integration_bundle: dict[str, Any],
    path: str,
    *,
    complete_posture: bool,
) -> list[Violation]:
    """Compare one target with application-scoped integration policy.

    Root and additional targets share this pure comparison. ``complete_posture`` enables the V3
    project, region, network, subnet, and egress checks while V1/V2 retain their accepted
    compatibility behavior. Returned violations are not sorted until the family validator joins
    them with document-level results.
    """

    violations: list[Violation] = []
    if target.get("owner_application_id") != integration_bundle.get("application_id"):
        violations.append(
            Violation(
                "OWNER_CONFLICT",
                f"{path}/owner_application_id",
                "attachment retains the named application owner",
            )
        )
    contract = integration_bundle.get("attachment_contract")
    if isinstance(contract, dict):
        for field in ("adapter_kind", "ingress_mode"):
            if target.get(field) != contract.get(field):
                violations.append(
                    Violation(
                        "ATTACHMENT_POSTURE_INVALID",
                        f"{path}/{field}",
                        "attachment violates integration contract",
                    )
                )
    identity = integration_bundle.get("identity")
    if isinstance(identity, dict):
        for target_field, identity_field in (
            ("caller_grant", "edge_caller_reference"),
            ("audience", "audience"),
        ):
            if target.get(target_field) != identity.get(identity_field):
                violations.append(
                    Violation(
                        "ATTACHMENT_POSTURE_INVALID",
                        f"{path}/{target_field}",
                        "attachment posture does not match integration bundle",
                    )
                )
    if not complete_posture:
        return violations
    application_project = integration_bundle.get("application_project")
    network = integration_bundle.get("network")
    if not isinstance(application_project, dict) or not isinstance(network, dict):
        return violations
    comparisons = (
        ("application_project_id", application_project.get("project_id")),
        ("network_reference", network.get("network_reference")),
        ("subnetwork_reference", network.get("subnetwork_reference")),
        ("egress_mode", network.get("egress_mode")),
    )
    for field, expected in comparisons:
        if target.get(field) != expected:
            violations.append(
                Violation(
                    "ATTACHMENT_POSTURE_INVALID",
                    f"{path}/{field}",
                    "attachment posture does not match application-scoped platform values",
                )
            )
    expected_reference_prefix = (
        "urn:comfforts:app-platform:gcp:cloud-run:"
        f"{application_project.get('project_number')}:{network.get('region')}:"
    )
    reference = target.get("resource_reference")
    if not isinstance(reference, str) or not reference.startswith(
        expected_reference_prefix
    ):
        violations.append(
            Violation(
                "ATTACHMENT_POSTURE_INVALID",
                f"{path}/resource_reference",
                "attachment reference does not match the application project and region",
            )
        )
    return violations


def validate_versioned_lifecycle_relationships(
    *,
    integration_bundle: dict[str, Any] | None = None,
    attachment_bundle: dict[str, Any] | None = None,
    registration_intent: dict[str, Any] | None = None,
) -> tuple[Violation, ...]:
    """Validate one complete same-version handoff family without external effects.

    V1/V2 compatibility remains readable. V3 additionally requires a registration intent,
    validates the complete root-plus-optional identifier relationship, and compares every target
    with application-scoped project, network, caller, audience, and adapter policy. The function
    returns stable ordered violations and performs no file, provider, publication, or activation
    operation.
    """

    violations: list[Violation] = []
    documents = (
        ("integration_bundle", integration_bundle, "platform-integration-bundle"),
        ("attachment_bundle", attachment_bundle, "application-attachment-bundle"),
        ("registration_intent", registration_intent, "registration-intent"),
    )
    versions: set[int] = set()
    for prefix, document, kind in documents:
        if document is None:
            continue
        violations.extend(
            Violation(
                item.code,
                f"/{prefix}{item.path}" if item.path else f"/{prefix}",
                item.message,
            )
            for item in validate_versioned_lifecycle_document(document, kind)
        )
        version = document.get("contract_version")
        if isinstance(version, int) and not isinstance(version, bool):
            versions.add(version)
    if len(versions) > 1:
        violations.append(
            Violation(
                "CONTRACT_VERSION_MIXED",
                "",
                "one activation handoff cannot mix V1, V2, and V3 documents",
            )
        )
    selected_version = (
        integration_bundle.get("contract_version")
        if isinstance(integration_bundle, dict)
        else None
    )
    if selected_version == 3 and registration_intent is None:
        violations.append(
            Violation(
                "DOCUMENT_REQUIRED",
                "/registration_intent",
                "a Version 3 handoff requires one registration intent",
            )
        )
    if violations or integration_bundle is None or attachment_bundle is None:
        return _ordered(violations)

    if attachment_bundle.get("platform_integration_bundle_digest") != versioned_lifecycle_digest(
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
    if isinstance(target, dict):
        violations.extend(
            _target_relationship_violations(
                target,
                integration_bundle,
                "/attachment_bundle/target",
                complete_posture=selected_version == 3,
            )
        )
    if selected_version == 3:
        additional = attachment_bundle.get("additional_attachments")
        if isinstance(additional, list):
            for index, entry in enumerate(additional):
                if isinstance(entry, dict) and isinstance(entry.get("target"), dict):
                    violations.extend(
                        _target_relationship_violations(
                            entry["target"],
                            integration_bundle,
                            f"/attachment_bundle/additional_attachments/{index}/target",
                            complete_posture=True,
                        )
                    )
    if registration_intent is not None:
        for field in ("application_id", "access_mode", "identity_delivery"):
            if registration_intent.get(field) != integration_bundle.get(field):
                violations.append(
                    Violation(
                        "DOCUMENT_RELATION_INVALID",
                        f"/registration_intent/{field}",
                        f"registration intent {field} does not match integration bundle",
                    )
                )
    if selected_version == 3 and registration_intent is not None:
        additional = attachment_bundle.get("additional_attachments")
        bindings = registration_intent.get("additional_attachment_bindings")
        additional_present = isinstance(additional, list)
        bindings_present = isinstance(bindings, list)
        if additional_present != bindings_present:
            violations.append(
                Violation(
                    "ATTACHMENT_SET_MISMATCH",
                    "/registration_intent/additional_attachment_bindings",
                    "additional attachments and bindings must both be absent or present",
                )
            )
        elif additional_present and bindings_present:
            additional_ids = {
                entry.get("attachment_id")
                for entry in additional
                if isinstance(entry, dict)
            }
            binding_ids = {
                binding.get("attachment_id")
                for binding in bindings
                if isinstance(binding, dict)
            }
            if additional_ids != binding_ids:
                violations.append(
                    Violation(
                        "ATTACHMENT_SET_MISMATCH",
                        "/registration_intent/additional_attachment_bindings",
                        "additional attachment and binding identifiers must match exactly",
                    )
                )
            root_id = registration_intent.get("attachment_id")
            if root_id in additional_ids or root_id in binding_ids:
                violations.append(
                    Violation(
                        "ATTACHMENT_ID_CONFLICT",
                        "/registration_intent/attachment_id",
                        "the root attachment identifier cannot be reused as an additional ID",
                    )
                )
    return _ordered(violations)


def canonical_lifecycle_bytes(value: Any, expected_kind: str) -> bytes:
    violations = validate_lifecycle_document(value, expected_kind)
    if violations:
        raise ValueError(f"invalid {expected_kind}: {violations!r}")
    return _canonical_bytes(value)


def canonical_versioned_lifecycle_bytes(value: Any, expected_kind: str) -> bytes:
    """Return canonical bytes for one valid V1, V2, or V3 handoff.

    Validation includes the selected versioned schema and semantic policy. Invalid input raises
    ``ValueError`` and no file or external state is changed.
    """

    violations = validate_versioned_lifecycle_document(value, expected_kind)
    if violations:
        raise ValueError(f"invalid {expected_kind}: {violations!r}")
    return _canonical_bytes(value)


def lifecycle_digest(value: Any, expected_kind: str) -> str:
    canonical = canonical_lifecycle_bytes(value, expected_kind)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def versioned_lifecycle_digest(value: Any, expected_kind: str) -> str:
    """Return the SHA-256 canonical digest for a valid V1, V2, or V3 handoff."""

    canonical = canonical_versioned_lifecycle_bytes(value, expected_kind)
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


def load_versioned_lifecycle_document(
    path: Path,
    expected_kind: str,
    *,
    max_bytes: int = 262_144,
) -> LifecycleDocument:
    """Load one bounded canonical V1, V2, or V3 handoff from local storage.

    The loader performs no remote resolution or mutation. It returns the validated object,
    canonical bytes, and digest on success; malformed, unsupported, prohibited, non-canonical, or
    oversized input returns stable violations without exposing partial document data.
    """

    loaded = load_json_document(path, max_bytes=max_bytes)
    if loaded.violations:
        return LifecycleDocument(None, None, None, loaded.violations)
    violations = validate_versioned_lifecycle_document(loaded.value, expected_kind)
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
