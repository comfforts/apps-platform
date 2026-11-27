"""Deterministic loading and policy for App Platform infrastructure configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts.validation import (
    Violation,
    load_json_document,
    load_schema_registry,
    validate_contract_instance,
)
from infrastructure.config.project_identity import fixtures_project_id


CONFIG_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_DIRECTORY = CONFIG_DIRECTORY / "schemas"
EXAMPLE_DIRECTORY = CONFIG_DIRECTORY / "examples"
SCHEMA_FILES = (
    "backend-configuration.v1.schema.json",
    "cross-state-reference.v1.schema.json",
    "fixture-configuration.v1.schema.json",
    "platform-configuration.v2.schema.json",
    "workflow-configuration.v1.schema.json",
)
SCHEMA_IDS = {
    "backend": "urn:comfforts:app-platform:infrastructure-config:backend:v1",
    "cross-state-reference": (
        "urn:comfforts:app-platform:infrastructure-config:cross-state-reference:v1"
    ),
    "fixture": "urn:comfforts:app-platform:infrastructure-config:fixture:v1",
    "platform": "urn:comfforts:app-platform:infrastructure-config:platform:v2",
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


def _pointer(path: str, token: str | int) -> str:
    encoded = str(token).replace("~", "~0").replace("/", "~1")
    return f"{path}/{encoded}" if path else f"/{encoded}"


def _violation(code: str, path: str, message: str) -> Violation:
    return Violation(code, path, message)


def _ordered(violations: list[Violation]) -> tuple[Violation, ...]:
    return tuple(sorted(violations, key=lambda item: (item.path, item.code, item.message)))


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
    if kind == "backend":
        _field_equals(value, "project_id", FIXED_PROJECT_ID, violations)
        _field_equals(value, "region", FIXED_REGION, violations)
    if kind == "fixture":
        _field_equals(value, "project_id", fixtures_project_id(), violations)
        _field_equals(value, "region", FIXED_REGION, violations)
    if kind == "fixture":
        _field_equals(
            value,
            "platform_issuer",
            f"https://{FIXED_HOSTNAME}/_platform",
            violations,
        )
    if kind == "platform":
        _field_equals(value, "repository", FIXED_REPOSITORY, violations)
        foundation = value.get("foundation")
        if isinstance(foundation, dict):
            expected = {
                "project_id": FIXED_PROJECT_ID,
                "project_number": FIXED_PROJECT_NUMBER,
                "region": FIXED_REGION,
                "hostname": FIXED_HOSTNAME,
            }
            for field, expected_value in expected.items():
                if foundation.get(field) != expected_value:
                    violations.append(
                        _violation(
                            "CONFIGURATION_POLICY_INVALID",
                            f"/foundation/{field}",
                            f"field must equal the reviewed value {expected_value!r}",
                        )
                    )
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
            if reference.get("project_id") != FIXED_PROJECT_ID:
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/reference/project_id",
                        "platform reference must use the reviewed project ID",
                    )
                )
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
            if reference.get("shared_network_reference") != (
                f"projects/{FIXED_PROJECT_ID}/global/networks/app-platform-shared"
            ):
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/reference/shared_network_reference",
                        "platform reference must use the reviewed Shared VPC",
                    )
                )
            if reference.get("application_subnet_reference") != (
                f"projects/{FIXED_PROJECT_ID}/regions/{FIXED_REGION}/subnetworks/"
                f"app-platform-applications-{FIXED_REGION}"
            ):
                violations.append(
                    _violation(
                        "CONFIGURATION_POLICY_INVALID",
                        "/reference/application_subnet_reference",
                        "platform reference must use the reviewed application subnet",
                    )
                )
    return violations


def _backend_violations(value: dict[str, Any]) -> list[Violation]:
    buckets = value.get("state_buckets")
    if not isinstance(buckets, list):
        return []
    expected = {
        ("platform", "app-platform"): "platform",
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
                "the platform bootstrap state owner is required exactly once",
            )
        )
    return violations


def _platform_violations(value: dict[str, Any]) -> list[Violation]:
    """Return closed ownership and immutable-reference violations for one platform input."""

    violations: list[Violation] = []
    phase = value.get("phase")
    destruction_mode = value.get("destruction_mode")
    foundation = value.get("foundation")
    shared_edge = value.get("shared_edge")
    if phase == "foundation" and shared_edge is not None:
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/shared_edge",
                "foundation phase must not contain later Shared Edge values",
            )
        )
    if phase == "shared-edge" and not isinstance(shared_edge, dict):
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/shared_edge",
                "Shared Edge phase requires its complete generated input binding",
            )
        )
    expected_phase = {
        "shared-edge-unlock": "shared-edge",
        "shared-edge-remove": "foundation",
        "platform-unlock": "foundation",
        "retained": "foundation",
    }.get(destruction_mode)
    if expected_phase is not None and phase != expected_phase:
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/destruction_mode",
                "destruction transition does not match its exact platform phase",
            )
        )
    if not isinstance(foundation, dict):
        return violations
    project_id = foundation.get("project_id")
    region = foundation.get("region")
    image = shared_edge.get("edge_image_digest") if isinstance(shared_edge, dict) else None
    if isinstance(image, str) and isinstance(project_id, str) and isinstance(region, str):
        if not image.startswith(f"{region}-docker.pkg.dev/{project_id}/"):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/shared_edge/edge_image_digest",
                    "edge image scope must match the configured project and region",
                )
            )
    scoped_fields = {
        "oauth_client_secret_version": f"projects/{project_id}/",
        "signing_key_version": f"projects/{project_id}/locations/{region}/",
    }
    for field, prefix in scoped_fields.items():
        field_value = shared_edge.get(field) if isinstance(shared_edge, dict) else None
        if isinstance(field_value, str) and not field_value.startswith(prefix):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    f"/shared_edge/{field}",
                    "resource reference scope does not match platform configuration",
                )
            )
    buckets = [
        foundation.get(name)
        for name in ("configuration_bucket", "log_bucket", "evidence_bucket")
    ]
    if all(isinstance(bucket, str) for bucket in buckets) and len(set(buckets)) != 3:
        violations.append(
            _violation(
                "OWNER_CONFLICT",
                "/foundation/configuration_bucket",
                "configuration, log, and evidence buckets must be distinct",
            )
        )
    generation = (
        shared_edge.get("registration_generation")
        if isinstance(shared_edge, dict)
        else None
    )
    if isinstance(generation, dict):
        number = generation.get("generation")
        generation_digest = generation.get("generation_digest")
        object_name = generation.get("object_name")
        environment = value.get("environment")
        compiled_names = (
            "compiled-shared-edge.v1.json",
            "compiled-shared-edge.v2.json",
        )
        legacy_initial = (
            number == 1 and object_name == "generations/1/compiled.json"
        )
        legacy_content_addressed = (
            isinstance(generation_digest, str)
            and object_name in (
                f"generations/{generation_digest.removeprefix('sha256:')}/{name}"
                for name in compiled_names
            )
        )
        environment_scoped = (
            isinstance(environment, str)
            and isinstance(number, int)
            and object_name in (
                f"environments/{environment}/generations/{number}/{name}"
                for name in compiled_names
            )
        )
        if not (legacy_initial or legacy_content_addressed or environment_scoped):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/shared_edge/registration_generation/object_name",
                    "generation object name must bind the declared environment, generation, and digest",
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
    if mode in {"authenticated", "restricted"} and not isinstance(audience, str):
        violations.append(
            _violation(
                "CONFIGURATION_POLICY_INVALID",
                "/assertion_audience",
                "protected fixtures require an application-bound audience",
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
    host_project_id = value.get("network_host_project_id")
    if isinstance(principal, str) and isinstance(host_project_id, str):
        if not principal.endswith(f"@{host_project_id}.iam.gserviceaccount.com"):
            violations.append(
                _violation(
                    "CONFIGURATION_POLICY_INVALID",
                    "/edge_caller_principal",
                    "edge caller principal must match the platform network host project",
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


def _semantic_violations(value: dict[str, Any]) -> list[Violation]:
    kind = value.get("configuration_kind")
    handlers = {
        "backend": _backend_violations,
        "cross-state-reference": _cross_state_violations,
        "fixture": _fixture_violations,
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
