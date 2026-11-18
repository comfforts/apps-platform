"""Deterministic loading and policy for App Platform infrastructure configuration."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Sequence

from contracts.validation import (
    Violation,
    load_json_document,
    load_schema_registry,
    validate_contract_instance,
)


CONFIG_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_DIRECTORY = CONFIG_DIRECTORY / "schemas"
EXAMPLE_DIRECTORY = CONFIG_DIRECTORY / "examples"
SCHEMA_FILES = (
    "backend-configuration.v1.schema.json",
    "cross-state-reference.v1.schema.json",
    "fixture-configuration.v1.schema.json",
    "operator-input-manifest.v1.schema.json",
    "platform-configuration.v1.schema.json",
    "workflow-configuration.v1.schema.json",
)
SCHEMA_IDS = {
    "backend": "urn:comfforts:app-platform:infrastructure-config:backend:v1",
    "cross-state-reference": (
        "urn:comfforts:app-platform:infrastructure-config:cross-state-reference:v1"
    ),
    "fixture": "urn:comfforts:app-platform:infrastructure-config:fixture:v1",
    "operator-input-manifest": (
        "urn:comfforts:app-platform:infrastructure-config:operator-input-manifest:v1"
    ),
    "platform": "urn:comfforts:app-platform:infrastructure-config:platform:v1",
    "workflow": "urn:comfforts:app-platform:infrastructure-config:workflow:v1",
}
FIXTURE_MODES = {
    "fixture-public": "public",
    "fixture-authenticated": "authenticated",
    "fixture-restricted": "restricted",
}
FIXED_PROJECT_ID = "comfforts-platform-non-prod"
FIXED_PROJECT_NUMBER = "455651441682"
FIXED_REGION = "us-west1"
FIXED_HOSTNAME = "apps-staging.comfforts.com"
FIXED_REPOSITORY = "comfforts/apps-platform"

_PROHIBITED_KEYS = {
    "access_token",
    "credential",
    "credentials",
    "oauth_token",
    "password",
    "private_key",
    "provider_response",
    "restricted_members",
    "saved_plan",
    "secret",
    "secret_value",
    "state_address",
    "terraform_state",
}
_PROHIBITED_VALUE_MARKERS = (
    "-----begin private key-----",
    "terraform_remote_state",
    ".tfplan",
    ".tfstate",
    "ya29.",
    "ghp_",
)


@dataclass(frozen=True, slots=True)
class ConfigurationResult:
    """One accepted configuration value or ordered violations."""

    value: dict[str, Any] | None
    violations: tuple[Violation, ...]


@dataclass(frozen=True, slots=True)
class OperatorManifestChainResult:
    """One accepted append-only manifest chain and its canonical revision digests."""

    values: tuple[dict[str, Any], ...] | None
    digests: tuple[str, ...]
    violations: tuple[Violation, ...]


def _pointer(path: str, token: str | int) -> str:
    encoded = str(token).replace("~", "~0").replace("/", "~1")
    return f"{path}/{encoded}" if path else f"/{encoded}"


def _violation(code: str, path: str, message: str) -> Violation:
    return Violation(code, path, message)


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


def _normalized_operator_manifest(value: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(value)
    controls = normalized.get("repository_controls")
    if isinstance(controls, dict) and isinstance(controls.get("workflow_references"), list):
        controls["workflow_references"] = sorted(
            controls["workflow_references"],
            key=lambda item: (
                item.get("operation", "") if isinstance(item, dict) else "",
                item.get("target_id", "") if isinstance(item, dict) else "",
            ),
        )
    federation = normalized.get("federation")
    if isinstance(federation, dict) and isinstance(
        federation.get("operation_identities"), list
    ):
        for identity in federation["operation_identities"]:
            if isinstance(identity, dict):
                if isinstance(identity.get("permissions"), list):
                    identity["permissions"] = sorted(identity["permissions"])
                if isinstance(identity.get("resource_scopes"), list):
                    identity["resource_scopes"] = sorted(identity["resource_scopes"])
        federation["operation_identities"] = sorted(
            federation["operation_identities"],
            key=lambda item: (
                item.get("operation", "") if isinstance(item, dict) else "",
                item.get("target_id", "") if isinstance(item, dict) else "",
            ),
        )
    state = normalized.get("state")
    if isinstance(state, dict):
        if isinstance(state.get("buckets"), list):
            state["buckets"] = sorted(
                state["buckets"],
                key=lambda item: item.get("bucket_role", "") if isinstance(item, dict) else "",
            )
        if isinstance(state.get("lineages"), list):
            state["lineages"] = sorted(
                state["lineages"],
                key=lambda item: item.get("root_target", "") if isinstance(item, dict) else "",
            )
    registration = normalized.get("registration_inputs")
    if isinstance(registration, dict) and isinstance(registration.get("application_ids"), list):
        registration["application_ids"] = sorted(registration["application_ids"])
    return normalized


def _operator_manifest_digest(value: dict[str, Any]) -> str:
    payload = _canonical_bytes(_normalized_operator_manifest(value))
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def load_configuration_schemas(
    schema_directory: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load the exact local Version 1 infrastructure schema registry."""

    return load_schema_registry(schema_directory or SCHEMA_DIRECTORY, SCHEMA_FILES)


def _prohibited_material_violations(value: Any, path: str = "") -> list[Violation]:
    violations: list[Violation] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = _pointer(path, key)
            if key.lower() in _PROHIBITED_KEYS:
                violations.append(
                    _violation(
                        "PROHIBITED_MATERIAL",
                        item_path,
                        "secret, credential, state, plan, or provider material is prohibited",
                    )
                )
            violations.extend(_prohibited_material_violations(item, item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_prohibited_material_violations(item, _pointer(path, index)))
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in _PROHIBITED_VALUE_MARKERS):
            violations.append(
                _violation(
                    "PROHIBITED_MATERIAL",
                    path,
                    "secret, credential, state, plan, or provider material is prohibited",
                )
            )
    return violations


def _field_equals(
    value: dict[str, Any],
    field: str,
    expected: object,
    violations: list[Violation],
) -> None:
    if field in value and value[field] != expected:
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                f"/{field}",
                f"field must equal the reviewed value {expected!r}",
            )
        )


def _reserved_synthetic_violations(value: Any, path: str = "") -> list[Violation]:
    violations: list[Violation] = []
    if isinstance(value, dict):
        for key, item in value.items():
            violations.extend(_reserved_synthetic_violations(item, _pointer(path, key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_reserved_synthetic_violations(item, _pointer(path, index)))
    elif isinstance(value, str):
        lowered = value.lower()
        digest_payload = lowered.removeprefix("sha256:")
        reserved = (
            "synthetic" in lowered
            or ".invalid" in lowered
            or lowered == "0" * 40
            or lowered == "billingaccounts/000000-000000-000000"
            or (
                lowered.startswith("sha256:")
                and len(digest_payload) == 64
                and len(set(digest_payload)) == 1
            )
        )
        if reserved:
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    path,
                    "operator configuration cannot select a reserved synthetic value",
                )
            )
    return violations


def _fixed_operator_violations(value: dict[str, Any]) -> list[Violation]:
    if value.get("configuration_class") != "operator":
        return []
    violations = _reserved_synthetic_violations(value)
    kind = value.get("configuration_kind")
    if kind in {"backend", "fixture", "platform"}:
        _field_equals(value, "project_id", FIXED_PROJECT_ID, violations)
        _field_equals(value, "region", FIXED_REGION, violations)
    if kind in {"fixture", "platform"}:
        _field_equals(value, "project_number", FIXED_PROJECT_NUMBER, violations)
    if kind == "fixture":
        _field_equals(
            value,
            "platform_issuer",
            f"https://{FIXED_HOSTNAME}/_platform",
            violations,
        )
    if kind == "platform":
        _field_equals(value, "qualification_hostname", FIXED_HOSTNAME, violations)
        _field_equals(value, "repository", FIXED_REPOSITORY, violations)
    if kind == "workflow":
        _field_equals(value, "repository", FIXED_REPOSITORY, violations)
        environment = value.get("protected_environment")
        if isinstance(environment, str) and environment.startswith("synthetic-"):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/protected_environment",
                    "operator configuration cannot select a synthetic environment",
                )
            )
    if kind == "cross-state-reference":
        reference = value.get("reference")
        if isinstance(reference, dict) and reference.get("reference_kind") == "platform":
            if reference.get("project_number") != FIXED_PROJECT_NUMBER:
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/reference/project_number",
                        "platform reference must use the reviewed project number",
                    )
                )
            if reference.get("public_key_reference") != (
                f"https://{FIXED_HOSTNAME}/.well-known/jwks.json"
            ):
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/reference/public_key_reference",
                        "platform public-key reference must use the reviewed qualification hostname",
                    )
                )
            if reference.get("region") != FIXED_REGION:
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/reference/region",
                        "platform reference must use the reviewed region",
                    )
                )
    return violations


def _backend_violations(value: dict[str, Any]) -> list[Violation]:
    buckets = value.get("state_buckets")
    if not isinstance(buckets, list):
        return []
    expected = {
        ("platform", "app-platform"): "platform",
        ("application", "fixture-public"): "fixtures/fixture-public",
        ("application", "fixture-authenticated"): "fixtures/fixture-authenticated",
        ("application", "fixture-restricted"): "fixtures/fixture-restricted",
    }
    seen: set[tuple[object, object]] = set()
    bucket_names: set[object] = set()
    violations: list[Violation] = []
    for index, bucket in enumerate(buckets):
        if not isinstance(bucket, dict):
            continue
        owner = (bucket.get("state_owner"), bucket.get("owner_id"))
        path = f"/state_buckets/{index}"
        if owner not in expected:
            violations.append(
                _violation("OWNER_CONFLICT", f"{path}/owner_id", "state owner is not approved")
            )
        elif bucket.get("backend_prefix") != expected[owner]:
            violations.append(
                _violation(
                    "OWNER_CONFLICT",
                    f"{path}/backend_prefix",
                    "backend prefix does not match its exclusive state owner",
                )
            )
        if owner in seen:
            violations.append(
                _violation("OWNER_CONFLICT", f"{path}/owner_id", "state owner is duplicated")
            )
        seen.add(owner)
        bucket_name = bucket.get("bucket_name")
        if bucket_name in bucket_names:
            violations.append(
                _violation(
                    "OWNER_CONFLICT",
                    f"{path}/bucket_name",
                    "state bucket is shared by multiple owners",
                )
            )
        bucket_names.add(bucket_name)
    if seen != set(expected):
        violations.append(
            _violation(
                "OWNER_CONFLICT",
                "/state_buckets",
                "all four independent state owners are required exactly once",
            )
        )
    return violations


def _platform_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    project_id = value.get("project_id")
    region = value.get("region")
    image = value.get("edge_image_digest")
    if isinstance(image, str) and isinstance(project_id, str) and isinstance(region, str):
        if not image.startswith(f"{region}-docker.pkg.dev/{project_id}/"):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/edge_image_digest",
                    "edge image scope must match the configured project and region",
                )
            )
    scoped_fields = {
        "oauth_client_secret_version": f"projects/{project_id}/",
        "signing_key_version": f"projects/{project_id}/locations/{region}/",
        "managed_zone_resource": f"projects/{project_id}/",
        "notification_destination": f"projects/{project_id}/",
    }
    for field, prefix in scoped_fields.items():
        field_value = value.get(field)
        if isinstance(field_value, str) and not field_value.startswith(prefix):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    f"/{field}",
                    "resource reference scope does not match platform configuration",
                )
            )
    buckets = [value.get(name) for name in ("configuration_bucket", "log_bucket", "evidence_bucket")]
    if all(isinstance(bucket, str) for bucket in buckets) and len(set(buckets)) != 3:
        violations.append(
            _violation(
                "OWNER_CONFLICT",
                "/configuration_bucket",
                "configuration, log, and evidence buckets must be distinct",
            )
        )
    generation = value.get("registration_generation")
    if isinstance(generation, dict):
        number = generation.get("generation")
        object_name = generation.get("object_name")
        if isinstance(number, int) and object_name != f"generations/{number}/compiled.json":
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/registration_generation/object_name",
                    "generation object name must bind the declared generation",
                )
            )
    return violations


def _fixture_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    application_id = value.get("application_id")
    mode = value.get("admission_mode")
    expected_mode = FIXTURE_MODES.get(application_id)
    if expected_mode is None or mode != expected_mode:
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/admission_mode",
                "fixture identity and admission mode must match the approved profile",
            )
        )
    audience = value.get("assertion_audience")
    if (mode == "public" and audience is not None) or (
        mode in {"authenticated", "restricted"} and not isinstance(audience, str)
    ):
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/assertion_audience",
                "public fixtures omit an audience and protected fixtures require one",
            )
        )
    if isinstance(application_id, str) and value.get("service_name") != application_id:
        violations.append(
            _violation(
                "OWNER_CONFLICT",
                "/service_name",
                "fixture service must remain scoped to its application owner",
            )
        )
    labels = value.get("labels")
    if isinstance(labels, dict) and labels.get("application_id") != application_id:
        violations.append(
            _violation(
                "OWNER_CONFLICT",
                "/labels/application_id",
                "fixture label must match its application owner",
            )
        )
    project_id = value.get("project_id")
    region = value.get("region")
    image = value.get("image_digest")
    if isinstance(image, str) and isinstance(project_id, str) and isinstance(region, str):
        if not image.startswith(f"{region}-docker.pkg.dev/{project_id}/"):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/image_digest",
                    "fixture image scope must match the configured project and region",
                )
            )
    principal = value.get("edge_caller_principal")
    if isinstance(principal, str) and isinstance(project_id, str):
        if not principal.endswith(f"@{project_id}.iam.gserviceaccount.com"):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/edge_caller_principal",
                    "edge caller principal must match the configured project",
                )
            )
    return violations


def _cross_state_violations(value: dict[str, Any]) -> list[Violation]:
    reference = value.get("reference")
    if not isinstance(reference, dict):
        return []
    violations: list[Violation] = []
    kind = reference.get("reference_kind")
    owner = reference.get("owner_id")
    if kind == "backend":
        state_owner = reference.get("state_owner")
        expected_prefix = (
            "platform" if (state_owner, owner) == ("platform", "app-platform")
            else f"fixtures/{owner}" if state_owner == "application" and owner in FIXTURE_MODES
            else None
        )
        if expected_prefix is None or reference.get("backend_prefix") != expected_prefix:
            violations.append(
                _violation(
                    "OWNER_CONFLICT",
                    "/reference/backend_prefix",
                    "backend reference does not match an approved state owner",
                )
            )
    elif kind == "platform":
        issuer = reference.get("platform_issuer")
        public_key_reference = reference.get("public_key_reference")
        expected_public_key_reference = (
            f"{issuer.removesuffix('/_platform')}/.well-known/jwks.json"
            if isinstance(issuer, str) and issuer.endswith("/_platform")
            else None
        )
        if public_key_reference != expected_public_key_reference:
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/reference/public_key_reference",
                    "platform public-key reference must be derived from its issuer hostname",
                )
            )
    elif kind == "attachment":
        application_id = reference.get("application_id")
        if owner != application_id or application_id not in FIXTURE_MODES:
            violations.append(
                _violation(
                    "OWNER_CONFLICT",
                    "/reference/owner_id",
                    "attachment reference owner must match its approved application",
                )
            )
        resource_reference = reference.get("resource_reference")
        if isinstance(resource_reference, str) and isinstance(application_id, str):
            if resource_reference.rsplit(":", 1)[-1] != application_id:
                violations.append(
                    _violation(
                        "OWNER_CONFLICT",
                        "/reference/resource_reference",
                        "Cloud Run service reference must match its application owner",
                    )
                )
            expected_scope = (
                "urn:comfforts:app-platform:gcp:cloud-run:"
                f"{FIXED_PROJECT_NUMBER}:{FIXED_REGION}:"
            )
            if value.get("configuration_class") == "operator" and not resource_reference.startswith(
                expected_scope
            ):
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/reference/resource_reference",
                        "operator attachment must use the reviewed project and region",
                    )
                )
    return violations


def _workflow_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    environment = value.get("protected_environment")
    subject = value.get("protected_subject")
    if isinstance(environment, str):
        expected_subject = f"repo:{FIXED_REPOSITORY}:environment:{environment}"
        if subject != expected_subject:
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/protected_subject",
                    "protected subject must bind the repository and environment exactly",
                )
            )
    operation = value.get("operation")
    plan_digest = value.get("plan_digest")
    destructive = value.get("destructive_target")
    digest_required = operation in {"apply", "rollback", "destroy"}
    if digest_required != isinstance(plan_digest, str):
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/plan_digest",
                "apply, rollback, and destroy require a plan digest; other operations prohibit it",
            )
        )
    destructive_required = operation in {"force-unlock", "destroy"}
    if destructive_required != isinstance(destructive, dict):
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/destructive_target",
                "force-unlock and destroy require one explicit destructive target",
            )
        )
    if isinstance(destructive, dict):
        if destructive.get("operation") != operation:
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/destructive_target/operation",
                    "destructive target operation must match workflow operation",
                )
            )
        if destructive.get("root_target") != value.get("root_target"):
            violations.append(
                _violation(
                    "OWNER_CONFLICT",
                    "/destructive_target/root_target",
                    "destructive target must remain within the selected root",
                )
            )
    return violations


_OPERATION_ENVIRONMENTS = {
    "plan": "plan",
    "apply": "apply",
    "artifact-publish": "apply",
    "generation-publish": "apply",
    "qualification-dns": "dns",
    "root-readback": "evidence",
    "evidence-finalize": "evidence",
    "rollback": "recovery",
    "force-unlock": "recovery",
    "destroy": "recovery",
}
_PROHIBITED_OPERATION_PERMISSIONS = {
    "billing.resourceAssociations.create",
    "iam.serviceAccountKeys.create",
    "iam.serviceAccounts.setIamPolicy",
    "resourcemanager.projects.setIamPolicy",
    "serviceusage.services.enable",
}
_EXPECTED_LINEAGES = {
    "bootstrap": ("platform-state", "bootstrap"),
    "platform": ("platform-state", "platform"),
    "fixture-public": ("fixture-public-state", "fixtures/fixture-public"),
    "fixture-authenticated": (
        "fixture-authenticated-state",
        "fixtures/fixture-authenticated",
    ),
    "fixture-restricted": (
        "fixture-restricted-state",
        "fixtures/fixture-restricted",
    ),
}
_EXPECTED_BUCKET_ROLES = {
    "platform-state",
    "fixture-public-state",
    "fixture-authenticated-state",
    "fixture-restricted-state",
}
_EXPECTED_APPLICATION_IDS = {
    "fixture-public",
    "fixture-authenticated",
    "fixture-restricted",
}


def _manifest_key(value: Any) -> tuple[object, object] | None:
    if not isinstance(value, dict):
        return None
    return value.get("operation"), value.get("target_id")


def _operator_manifest_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    revision = value.get("revision")
    predecessor = value.get("predecessor_manifest_digest")
    facts = value.get("generated_facts")
    if revision == 1:
        if predecessor is not None:
            violations.append(
                _violation(
                    "MANIFEST_CHAIN_INVALID",
                    "/predecessor_manifest_digest",
                    "the initial manifest revision must not name a predecessor",
                )
            )
        if facts != []:
            violations.append(
                _violation(
                    "MANIFEST_CHAIN_INVALID",
                    "/generated_facts",
                    "the initial manifest cannot claim facts produced by later operations",
                )
            )
    elif isinstance(revision, int) and not isinstance(predecessor, str):
        violations.append(
            _violation(
                "MANIFEST_CHAIN_INVALID",
                "/predecessor_manifest_digest",
                "a successor manifest revision must name its predecessor digest",
            )
        )

    source = value.get("source")
    resources = value.get("platform_resources")
    if isinstance(source, dict) and isinstance(resources, dict):
        source_revision = source.get("source_revision")
        evidence_prefix = resources.get("evidence_bundle_prefix")
        if isinstance(source_revision, str) and isinstance(evidence_prefix, str):
            expected_prefix = f"ap-eval-m8/{source_revision}/"
            if not evidence_prefix.startswith(expected_prefix):
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/platform_resources/evidence_bundle_prefix",
                        "evidence prefix must bind the selected protected-main revision",
                    )
                )
        if resources.get("oauth_redirect_uri") != (
            f"https://{FIXED_HOSTNAME}/_platform/auth/callback"
        ):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/platform_resources/oauth_redirect_uri",
                    "OAuth redirect must use the reviewed qualification callback",
                )
            )

    controls = value.get("repository_controls")
    workflow_by_key: dict[tuple[object, object], dict[str, Any]] = {}
    if isinstance(controls, dict):
        environments = controls.get("protected_environments")
        if isinstance(environments, dict):
            names = list(environments.values())
            if len(names) != len(set(names)):
                violations.append(
                    _violation(
                        "OWNER_CONFLICT",
                        "/repository_controls/protected_environments",
                        "the five protected environment classes require distinct names",
                    )
                )
        workflows = controls.get("workflow_references")
        workflow_paths: set[object] = set()
        if isinstance(workflows, list):
            for index, workflow in enumerate(workflows):
                if not isinstance(workflow, dict):
                    continue
                path = f"/repository_controls/workflow_references/{index}"
                key = _manifest_key(workflow)
                if key in workflow_by_key:
                    violations.append(
                        _violation(
                            "OWNER_CONFLICT",
                            f"{path}/target_id",
                            "operation and target are duplicated",
                        )
                    )
                elif key is not None:
                    workflow_by_key[key] = workflow
                operation = workflow.get("operation")
                expected_environment = _OPERATION_ENVIRONMENTS.get(operation)
                if expected_environment is not None and workflow.get(
                    "environment_class"
                ) != expected_environment:
                    violations.append(
                        _violation(
                            "CONFIGURATION_POLICY_INVALID",
                            f"{path}/environment_class",
                            "operation does not use its fixed environment class",
                        )
                    )
                workflow_path = workflow.get("workflow_path")
                if workflow_path in workflow_paths:
                    violations.append(
                        _violation(
                            "OWNER_CONFLICT",
                            f"{path}/workflow_path",
                            "one rendered workflow path cannot authorize multiple operations",
                        )
                    )
                workflow_paths.add(workflow_path)

    federation = value.get("federation")
    identity_by_key: dict[tuple[object, object], dict[str, Any]] = {}
    identity_index_by_key: dict[tuple[object, object], int] = {}
    if isinstance(federation, dict):
        expected_pool_prefix = "projects/455651441682/locations/global/workloadIdentityPools/"
        pool = federation.get("pool_resource")
        provider = federation.get("provider_resource")
        audience = federation.get("provider_audience")
        if isinstance(pool, str) and not pool.startswith(expected_pool_prefix):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/federation/pool_resource",
                    "pool resource must remain in the reviewed qualification project",
                )
            )
        if isinstance(pool, str) and isinstance(provider, str) and not provider.startswith(
            f"{pool}/providers/"
        ):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/federation/provider_resource",
                    "provider resource must remain under the selected pool",
                )
            )
        if isinstance(provider, str) and audience != f"//iam.googleapis.com/{provider}":
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/federation/provider_audience",
                    "provider audience must bind the selected provider resource",
                )
            )
        identities = federation.get("operation_identities")
        service_accounts: set[object] = set()
        if isinstance(identities, list):
            for index, identity in enumerate(identities):
                if not isinstance(identity, dict):
                    continue
                path = f"/federation/operation_identities/{index}"
                key = _manifest_key(identity)
                if key in identity_by_key:
                    violations.append(
                        _violation(
                            "OWNER_CONFLICT",
                            f"{path}/target_id",
                            "operation identity and target are duplicated",
                        )
                    )
                elif key is not None:
                    identity_by_key[key] = identity
                    identity_index_by_key[key] = index
                operation = identity.get("operation")
                expected_environment = _OPERATION_ENVIRONMENTS.get(operation)
                if expected_environment is not None and identity.get(
                    "environment_class"
                ) != expected_environment:
                    violations.append(
                        _violation(
                            "CONFIGURATION_POLICY_INVALID",
                            f"{path}/environment_class",
                            "operation identity does not use its fixed environment class",
                        )
                    )
                service_account = identity.get("service_account_resource")
                if service_account in service_accounts:
                    violations.append(
                        _violation(
                            "OWNER_CONFLICT",
                            f"{path}/service_account_resource",
                            "operation identities require distinct service accounts",
                        )
                    )
                service_accounts.add(service_account)
                permissions = identity.get("permissions")
                if isinstance(permissions, list):
                    for permission_index, permission in enumerate(permissions):
                        if permission in _PROHIBITED_OPERATION_PERMISSIONS:
                            violations.append(
                                _violation(
                                    "CONFIGURATION_POLICY_INVALID",
                                    f"{path}/permissions/{permission_index}",
                                    "operation identities cannot administer IAM, billing, keys, or APIs",
                                )
                            )

    if set(workflow_by_key) != set(identity_by_key):
        violations.append(
            _violation(
                "OWNER_CONFLICT",
                "/federation/operation_identities",
                "each workflow operation and target requires exactly one matching identity",
            )
        )
    for key in set(workflow_by_key) & set(identity_by_key):
        workflow = workflow_by_key[key]
        identity = identity_by_key[key]
        identity_index = identity_index_by_key[key]
        path = f"/federation/operation_identities/{identity_index}"
        for field in ("environment_class", "workflow_path"):
            if identity.get(field) != workflow.get(field):
                violations.append(
                    _violation(
                        "OWNER_CONFLICT",
                        f"{path}/{field}",
                        "operation identity must match its exact workflow reference",
                    )
                )

    state = value.get("state")
    state_bucket_names: list[object] = []
    if isinstance(state, dict):
        buckets = state.get("buckets")
        if isinstance(buckets, list):
            roles = {
                bucket.get("bucket_role")
                for bucket in buckets
                if isinstance(bucket, dict)
            }
            if roles != _EXPECTED_BUCKET_ROLES:
                violations.append(
                    _violation(
                        "OWNER_CONFLICT",
                        "/state/buckets",
                        "all four independent state bucket roles are required exactly once",
                    )
                )
            state_bucket_names = [
                bucket.get("bucket_name")
                for bucket in buckets
                if isinstance(bucket, dict)
            ]
            if len(state_bucket_names) != len(set(state_bucket_names)):
                violations.append(
                    _violation(
                        "OWNER_CONFLICT",
                        "/state/buckets",
                        "the four state buckets require globally distinct names",
                    )
                )
        lineages = state.get("lineages")
        if isinstance(lineages, list):
            observed: dict[object, tuple[object, object]] = {}
            access_bindings: set[object] = set()
            for index, lineage in enumerate(lineages):
                if not isinstance(lineage, dict):
                    continue
                root = lineage.get("root_target")
                path = f"/state/lineages/{index}"
                if root in observed:
                    violations.append(
                        _violation(
                            "OWNER_CONFLICT",
                            f"{path}/root_target",
                            "state root lineage is duplicated",
                        )
                    )
                observed[root] = (
                    lineage.get("bucket_role"),
                    lineage.get("backend_prefix"),
                )
                binding = lineage.get("access_binding_reference")
                if binding in access_bindings:
                    violations.append(
                        _violation(
                            "OWNER_CONFLICT",
                            f"{path}/access_binding_reference",
                            "state lineages require distinct access bindings",
                        )
                    )
                access_bindings.add(binding)
            if observed != _EXPECTED_LINEAGES:
                violations.append(
                    _violation(
                        "OWNER_CONFLICT",
                        "/state/lineages",
                        "the fixed five root lineages and prefixes are required",
                    )
                )

    if isinstance(resources, dict):
        resource_bucket_names = [
            resources.get(field)
            for field in ("configuration_bucket", "log_bucket", "evidence_bucket")
        ]
        all_bucket_names = state_bucket_names + resource_bucket_names
        if len(all_bucket_names) != len(set(all_bucket_names)):
            violations.append(
                _violation(
                    "OWNER_CONFLICT",
                    "/platform_resources/configuration_bucket",
                    "state, configuration, log, and evidence buckets require distinct names",
                )
            )

    registration = value.get("registration_inputs")
    if isinstance(registration, dict):
        if set(registration.get("application_ids", [])) != _EXPECTED_APPLICATION_IDS:
            violations.append(
                _violation(
                    "OWNER_CONFLICT",
                    "/registration_inputs/application_ids",
                    "the three synthetic qualification applications are required exactly once",
                )
            )
        if registration.get("restricted_members_source") != registration.get(
            "registration_set_path"
        ):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/registration_inputs/restricted_members_source",
                    "restricted synthetic members must remain inside the reviewed Registration Set",
                )
            )

    if isinstance(facts, list):
        fact_keys: set[tuple[object, object]] = set()
        fact_patterns = {
            "image-digest": r".+@sha256:[0-9a-f]{64}",
            "state-lineage-digest": r"sha256:[0-9a-f]{64}",
            "configuration-object-generation": r"[1-9][0-9]{0,18}",
            "plan-digest": r"sha256:[0-9a-f]{64}",
            "workflow-run-id": r"[1-9][0-9]{0,18}",
        }
        for index, fact in enumerate(facts):
            if not isinstance(fact, dict):
                continue
            path = f"/generated_facts/{index}"
            key = (fact.get("fact_kind"), fact.get("target_id"))
            if key in fact_keys:
                violations.append(
                    _violation(
                        "MANIFEST_CHAIN_INVALID",
                        f"{path}/target_id",
                        "a generated fact kind and target can be recorded only once",
                    )
                )
            fact_keys.add(key)
            pattern = fact_patterns.get(fact.get("fact_kind"))
            fact_value = fact.get("value")
            if pattern is not None and (
                not isinstance(fact_value, str) or re.fullmatch(pattern, fact_value) is None
            ):
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        f"{path}/value",
                        "generated fact value does not match its immutable kind",
                    )
                )
    return violations


def _semantic_violations(value: dict[str, Any]) -> list[Violation]:
    kind = value.get("configuration_kind")
    handlers = {
        "backend": _backend_violations,
        "cross-state-reference": _cross_state_violations,
        "fixture": _fixture_violations,
        "operator-input-manifest": _operator_manifest_violations,
        "platform": _platform_violations,
        "workflow": _workflow_violations,
    }
    handler = handlers.get(kind)
    return handler(value) if handler is not None else []


def validate_configuration(
    value: Any,
    expected_kind: str,
    *,
    allow_synthetic: bool = False,
    registry: dict[str, dict[str, Any]] | None = None,
) -> tuple[Violation, ...]:
    """Validate one configuration without environment, credential, or provider access."""

    if expected_kind not in SCHEMA_IDS:
        raise ValueError(f"unknown infrastructure configuration kind: {expected_kind}")
    active_registry = registry or load_configuration_schemas()
    violations = list(
        validate_contract_instance(value, SCHEMA_IDS[expected_kind], active_registry)
    )
    violations.extend(_prohibited_material_violations(value))
    if isinstance(value, dict):
        if value.get("configuration_kind") != expected_kind:
            violations.append(
                _violation(
                    "CONFIGURATION_KIND_INVALID",
                    "/configuration_kind",
                    "configuration kind does not match the selected interface",
                )
            )
        if value.get("configuration_class") == "synthetic" and not allow_synthetic:
            violations.append(
                _violation(
                    "SYNTHETIC_CONFIGURATION_PROHIBITED",
                    "/configuration_class",
                    "synthetic examples cannot be selected as operator configuration",
                )
            )
        violations.extend(_fixed_operator_violations(value))
        violations.extend(_semantic_violations(value))
    return _ordered(violations)


def load_configuration_document(
    path: Path,
    expected_kind: str,
    *,
    allow_synthetic: bool = False,
    max_bytes: int = 262_144,
) -> ConfigurationResult:
    """Load and validate one bounded configuration document from an explicit path."""

    loaded = load_json_document(path, max_bytes=max_bytes)
    if loaded.violations:
        return ConfigurationResult(None, loaded.violations)
    violations = validate_configuration(
        loaded.value,
        expected_kind,
        allow_synthetic=allow_synthetic,
    )
    value = loaded.value if isinstance(loaded.value, dict) and not violations else None
    return ConfigurationResult(value, violations)


def _revision_path(index: int, path: str) -> str:
    base = f"/revisions/{index}"
    return f"{base}{path}" if path else base


def _revision_violation(index: int, violation: Violation) -> Violation:
    return Violation(
        violation.code,
        _revision_path(index, violation.path),
        violation.message,
    )


def _immutable_manifest_view(value: dict[str, Any]) -> dict[str, Any]:
    immutable = copy.deepcopy(value)
    for field in (
        "revision",
        "predecessor_manifest_digest",
        "approval_reference",
        "generated_facts",
    ):
        immutable.pop(field, None)
    source = immutable.get("source")
    if isinstance(source, dict):
        source.pop("source_revision", None)
    resources = immutable.get("platform_resources")
    if isinstance(resources, dict):
        resources.pop("evidence_bundle_prefix", None)
    return immutable


def validate_operator_manifest_chain(
    revisions: Sequence[Any],
    *,
    allow_synthetic: bool = False,
    registry: dict[str, dict[str, Any]] | None = None,
) -> OperatorManifestChainResult:
    """Validate an ordered AP-M8 manifest chain without discovery or external access."""

    if not revisions:
        return OperatorManifestChainResult(
            None,
            (),
            (
                _violation(
                    "MANIFEST_CHAIN_INVALID",
                    "/revisions",
                    "at least one manifest revision is required",
                ),
            ),
        )
    active_registry = registry or load_configuration_schemas()
    violations: list[Violation] = []
    dictionaries: list[dict[str, Any]] = []
    candidate_digests: list[str | None] = []
    for index, revision in enumerate(revisions):
        revision_violations = validate_configuration(
            revision,
            "operator-input-manifest",
            allow_synthetic=allow_synthetic,
            registry=active_registry,
        )
        violations.extend(
            _revision_violation(index, violation)
            for violation in revision_violations
        )
        if isinstance(revision, dict):
            dictionaries.append(revision)
            candidate_digests.append(_operator_manifest_digest(revision))
        else:
            candidate_digests.append(None)

    if len(dictionaries) == len(revisions):
        first = dictionaries[0]
        immutable_view = _immutable_manifest_view(first)
        previous_facts: list[Any] = []
        previous_approval: object = None
        for index, revision in enumerate(dictionaries):
            expected_revision = index + 1
            if revision.get("revision") != expected_revision:
                violations.append(
                    _violation(
                        "MANIFEST_CHAIN_INVALID",
                        _revision_path(index, "/revision"),
                        "manifest revisions must start at one and increase by one",
                    )
                )
            if index > 0 and revision.get("predecessor_manifest_digest") != candidate_digests[
                index - 1
            ]:
                violations.append(
                    _violation(
                        "MANIFEST_CHAIN_INVALID",
                        _revision_path(index, "/predecessor_manifest_digest"),
                        "successor predecessor digest does not match the prior revision",
                    )
                )
            if _immutable_manifest_view(revision) != immutable_view:
                violations.append(
                    _violation(
                        "MANIFEST_CHAIN_INVALID",
                        _revision_path(index, ""),
                        "successor changed an immutable reviewed operator input",
                    )
                )
            approval = revision.get("approval_reference")
            if index > 0 and approval == previous_approval:
                violations.append(
                    _violation(
                        "MANIFEST_CHAIN_INVALID",
                        _revision_path(index, "/approval_reference"),
                        "each successor revision requires a fresh approval reference",
                    )
                )
            current_facts = revision.get("generated_facts")
            if isinstance(current_facts, list):
                if len(current_facts) < len(previous_facts) or current_facts[
                    : len(previous_facts)
                ] != previous_facts:
                    violations.append(
                        _violation(
                            "MANIFEST_CHAIN_INVALID",
                            _revision_path(index, "/generated_facts"),
                            "successor revisions must preserve the generated-fact prefix",
                        )
                    )
                if index > 0 and len(current_facts) == len(previous_facts):
                    violations.append(
                        _violation(
                            "MANIFEST_CHAIN_INVALID",
                            _revision_path(index, "/generated_facts"),
                            "a successor revision must append at least one generated fact",
                        )
                    )
                previous_facts = copy.deepcopy(current_facts)
            previous_approval = approval

    ordered = _ordered(violations)
    if ordered:
        return OperatorManifestChainResult(None, (), ordered)
    accepted = tuple(copy.deepcopy(value) for value in dictionaries)
    digests = tuple(digest for digest in candidate_digests if digest is not None)
    return OperatorManifestChainResult(accepted, digests, ())


def load_operator_manifest_chain(
    paths: Sequence[Path],
    *,
    allow_synthetic: bool = False,
    max_bytes: int = 262_144,
) -> OperatorManifestChainResult:
    """Load an explicit ordered manifest chain from bounded local JSON documents."""

    revisions: list[Any] = []
    violations: list[Violation] = []
    for index, path in enumerate(paths):
        loaded = load_json_document(path, max_bytes=max_bytes)
        if loaded.violations:
            violations.extend(
                _revision_violation(index, violation)
                for violation in loaded.violations
            )
        else:
            revisions.append(loaded.value)
    if violations:
        return OperatorManifestChainResult(None, (), _ordered(violations))
    return validate_operator_manifest_chain(
        revisions,
        allow_synthetic=allow_synthetic,
    )
