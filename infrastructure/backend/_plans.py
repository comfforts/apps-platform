"""Redacted canonical plan policy for AP-M9 Terraform phases."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from infrastructure.backend._lifecycle import EnvironmentUnavailableError
from infrastructure.config.project_identity import fixtures_project_id


_GOOGLE_PROVIDER = "registry.terraform.io/hashicorp/google"
_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
_PHASE_INVENTORIES = {
    "bootstrap": {
        "terraform_root": "infrastructure/terraform/bootstrap",
        "state_owner": "platform",
        "owner_id": "app-platform",
        "resource_types": ("google_storage_bucket",),
    },
    "platform-foundation": {
        "terraform_root": "infrastructure/terraform/platform",
        "state_owner": "platform",
        "owner_id": "app-platform",
        "resource_types": (
            "google_artifact_registry_repository",
            "google_billing_budget",
            "google_firestore_database",
            "google_firestore_field",
            "google_kms_crypto_key",
            "google_kms_crypto_key_iam_member",
            "google_kms_key_ring",
            "google_logging_project_bucket_config",
            "google_logging_project_exclusion",
            "google_logging_project_sink",
            "google_monitoring_notification_channel",
            "google_project_iam_member",
            "google_project_iam_custom_role",
            "google_project_service",
            "google_compute_network",
            "google_compute_router",
            "google_compute_router_nat",
            "google_compute_subnetwork",
            "google_compute_shared_vpc_host_project",
            "google_secret_manager_secret",
            "google_secret_manager_secret_iam_member",
            "google_service_account",
            "google_service_account_iam_member",
            "google_storage_bucket",
            "google_storage_bucket_iam_member",
        ),
    },
    "shared-edge": {
        "terraform_root": "infrastructure/terraform/platform",
        "state_owner": "platform",
        "owner_id": "app-platform",
        "resource_types": (
            "google_cloud_run_v2_service",
            "google_cloud_run_v2_service_iam_member",
            "google_compute_backend_service",
            "google_compute_global_address",
            "google_compute_global_forwarding_rule",
            "google_compute_managed_ssl_certificate",
            "google_compute_region_network_endpoint_group",
            "google_compute_target_http_proxy",
            "google_compute_target_https_proxy",
            "google_compute_url_map",
            "google_project_service",
            "google_service_account_iam_member",
        ),
    },
    **{
        owner_id: {
            "terraform_root": f"infrastructure/terraform/fixtures/{owner_id}",
            "state_owner": "application",
            "owner_id": owner_id,
            "resource_types": (
                "google_cloud_run_v2_service",
                "google_cloud_run_v2_service_iam_member",
                "google_service_account",
            ),
        }
        for owner_id in (
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
        )
    },
}
_INHERITED_READ_ONLY_INVENTORIES = {
    "platform-foundation": {
        "resource_types": _PHASE_INVENTORIES["shared-edge"]["resource_types"],
        "address_prefixes": ("module.shared_edge[",),
    },
    "shared-edge": {
        "resource_types": _PHASE_INVENTORIES["platform-foundation"][
            "resource_types"
        ],
        "address_prefixes": (
            "module.platform_foundation.",
            "module.platform_controls.",
        ),
    },
}
_PHASE_EXACT_RESOURCE_ADDRESSES = {
    "shared-edge": {
        "google_project_service": (
            "module.shared_edge[0].google_project_service.iam_credentials",
        ),
        "google_service_account_iam_member": (
            "module.shared_edge[0].google_service_account_iam_member."
            "edge_caller_token_creator",
        ),
    },
}
_PHASE_EXACT_FORGET_ADDRESSES = {
    "bootstrap": frozenset(
        f'module.state_bucket["{application_id}"].google_storage_bucket.state'
        for application_id in (
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
        )
    ),
}
_PHASE_EXACT_INHERITED_MUTATIONS = {
    "shared-edge": {
        (
            "module.platform_controls.google_artifact_registry_repository."
            "qualification_images[0]"
        ): frozenset({("update",)}),
        (
            "module.platform_foundation."
            "google_compute_shared_vpc_host_project.platform"
        ): frozenset({("create",)}),
        (
            "module.platform_foundation.google_compute_subnetwork.applications"
        ): frozenset({("create",)}),
        (
            "module.platform_foundation.google_compute_network.shared"
        ): frozenset({("create",)}),
        (
            "module.platform_foundation."
            "google_compute_router.applications[0]"
        ): frozenset({("create",)}),
        (
            "module.platform_foundation."
            "google_compute_router_nat.applications[0]"
        ): frozenset({("create",)}),
        (
            "module.platform_foundation.google_project_iam_member."
            "edge_session_store[0]"
        ): frozenset({("create",), ("update",)}),
        (
            "module.platform_foundation.google_firestore_database."
            "member_directory[0]"
        ): frozenset({("create",)}),
        (
            "module.platform_foundation.google_project_iam_custom_role."
            "edge_member_directory_reader[0]"
        ): frozenset({("create",)}),
        (
            "module.platform_foundation.google_project_iam_member."
            "edge_member_directory_reader[0]"
        ): frozenset({("create",)}),
    },
}


@dataclass(frozen=True, slots=True)
class PlanPolicy:
    """Exact allowed context and resource/action inventory for one plan."""

    environment: str
    source_revision: str
    state_owner: str
    owner_id: str
    terraform_root: str
    phase: str
    project_id: str
    provider_source: str
    provider_service: str
    allowed_resource_types: tuple[str, ...]
    inherited_read_only_resource_types: tuple[str, ...]
    inherited_read_only_address_prefixes: tuple[str, ...]
    allowed_planning_modes: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    prohibited_delete_address_prefixes: tuple[str, ...]
    destructive: bool


@dataclass(frozen=True, slots=True)
class PlanViolation:
    code: str
    path: str
    message: str
    address: str | None = None
    resource_type: str | None = None
    actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanPolicyResult:
    accepted: bool
    plan_digest: str | None
    canonical_summary: dict[str, Any] | None
    violations: tuple[PlanViolation, ...]


def plan_policy(
    environment: str,
    phase: str,
    source_revision: str,
    *,
    destructive: bool,
) -> PlanPolicy:
    """Build one closed staging policy; production has no deployment authority."""

    if environment == "production":
        raise EnvironmentUnavailableError("OWNERSHIP_TRANSFER_REQUIRED")
    if environment != "staging":
        raise EnvironmentUnavailableError(f"unsupported environment {environment!r}")
    if not _SOURCE_REVISION.fullmatch(source_revision):
        raise ValueError("source revision must be an exact lowercase Git commit")
    try:
        inventory = _PHASE_INVENTORIES[phase]
    except KeyError as error:
        raise ValueError(f"unsupported Terraform phase {phase!r}") from error
    actions = ("delete", "no-op", "read") if destructive else (
        "create",
        "no-op",
        "read",
        "update",
    )
    retained_prefixes = (
        "module.platform_foundation.google_project_service.platform",
        "module.platform_foundation.google_storage_bucket.configuration",
        "module.platform_foundation.google_kms_key_ring.assertion_signing",
        "module.platform_foundation.google_kms_crypto_key.assertion_signing",
        "module.platform_foundation.google_compute_shared_vpc_host_project.platform",
        "module.platform_foundation.google_compute_network.shared",
        "module.platform_foundation.google_compute_subnetwork.applications",
        "module.platform_controls.google_storage_bucket.evidence",
        "module.platform_controls.google_storage_bucket_iam_member.evidence_owner_reader",
        "module.platform_controls.google_logging_project_exclusion.edge_from_default",
    ) if destructive and phase == "platform-foundation" else ()
    inherited = _INHERITED_READ_ONLY_INVENTORIES.get(phase, {})
    return PlanPolicy(
        environment="staging",
        source_revision=source_revision,
        state_owner=str(inventory["state_owner"]),
        owner_id=str(inventory["owner_id"]),
        terraform_root=str(inventory["terraform_root"]),
        phase=phase,
        project_id=(
            fixtures_project_id()
            if phase.startswith("fixture-")
            else "comfforts-platform-non-prod"
        ),
        provider_source=_GOOGLE_PROVIDER,
        provider_service="google",
        allowed_resource_types=tuple(inventory["resource_types"]),
        inherited_read_only_resource_types=tuple(
            inherited.get("resource_types", ())
        ),
        inherited_read_only_address_prefixes=tuple(
            inherited.get("address_prefixes", ())
        ),
        allowed_planning_modes=(
            ("normal", "refresh-only")
            if phase == "platform-foundation" and not destructive
            else ("normal",)
        ),
        allowed_actions=actions,
        prohibited_delete_address_prefixes=retained_prefixes,
        destructive=destructive,
    )


def _violation(
    code: str,
    path: str,
    message: str,
    *,
    address: str | None = None,
    resource_type: str | None = None,
    actions: tuple[str, ...] = (),
) -> PlanViolation:
    return PlanViolation(
        code,
        path,
        message,
        address,
        resource_type,
        actions,
    )


def _ordered(values: list[PlanViolation]) -> tuple[PlanViolation, ...]:
    return tuple(sorted(values, key=lambda value: (value.path, value.code, value.message)))


def _compare_context(
    observation: dict[str, Any],
    policy: PlanPolicy,
    violations: list[PlanViolation],
) -> None:
    expected = {
        "environment": (policy.environment, "ENVIRONMENT_MISMATCH"),
        "source_revision": (policy.source_revision, "SOURCE_MISMATCH"),
        "state_owner": (policy.state_owner, "OWNER_MISMATCH"),
        "owner_id": (policy.owner_id, "OWNER_MISMATCH"),
        "terraform_root": (policy.terraform_root, "ROOT_MISMATCH"),
        "phase": (policy.phase, "PHASE_MISMATCH"),
    }
    for field, (expected_value, code) in expected.items():
        if observation.get(field) != expected_value:
            violations.append(
                _violation(code, f"/{field}", f"field must equal {expected_value!r}")
            )


def _provider_summary(
    observation: dict[str, Any],
    policy: PlanPolicy,
    violations: list[PlanViolation],
) -> dict[str, str] | None:
    provider = observation.get("provider")
    if not isinstance(provider, dict):
        violations.append(
            _violation("SERVICE_MISMATCH", "/provider", "explicit Google provider is required")
        )
        return None
    if provider.get("configuration") != "explicit":
        violations.append(
            _violation(
                "PROVIDER_DEFAULT_PROHIBITED",
                "/provider/configuration",
                "ambient or default provider configuration is prohibited",
            )
        )
    if provider.get("project_id") != policy.project_id:
        violations.append(
            _violation(
                "PROJECT_MISMATCH",
                "/provider/project_id",
                "provider project does not match the approved environment",
            )
        )
    if (
        provider.get("source") != policy.provider_source
        or provider.get("service") != policy.provider_service
    ):
        violations.append(
            _violation(
                "SERVICE_MISMATCH",
                "/provider",
                "provider service does not match the approved Google provider",
            )
        )
    return {
        "configuration": str(provider.get("configuration", "")),
        "project_id": str(provider.get("project_id", "")),
        "service": str(provider.get("service", "")),
        "source": str(provider.get("source", "")),
    }


def _planning_mode(
    observation: dict[str, Any],
    policy: PlanPolicy,
    violations: list[PlanViolation],
) -> str:
    mode = observation.get("planning_mode", "normal")
    if not isinstance(mode, str) or mode not in policy.allowed_planning_modes:
        violations.append(
            _violation(
                "PLANNING_MODE_MISMATCH",
                "/planning_mode",
                "planning mode is outside the approved phase modes",
            )
        )
        return str(mode or "")
    return mode


def _change_summaries(
    observation: dict[str, Any],
    policy: PlanPolicy,
    planning_mode: str,
    violations: list[PlanViolation],
) -> list[dict[str, object]]:
    changes = observation.get("changes")
    if not isinstance(changes, list):
        violations.append(
            _violation("PLAN_SHAPE_INVALID", "/changes", "changes must be a list")
        )
        return []
    summaries: list[dict[str, object]] = []
    for index, change in enumerate(changes):
        path = f"/changes/{index}"
        if not isinstance(change, dict):
            violations.append(
                _violation("PLAN_SHAPE_INVALID", path, "change must be an object")
            )
            continue
        address = change.get("address")
        resource_type = change.get("resource_type")
        provider_source = change.get("provider_source")
        actions = change.get("actions")
        safe_address = str(address or "")
        safe_resource_type = str(resource_type or "")
        safe_actions = tuple(
            action for action in actions if isinstance(action, str)
        ) if isinstance(actions, list) else ()
        if not isinstance(address, str) or not address:
            violations.append(
                _violation("PLAN_SHAPE_INVALID", f"{path}/address", "address is required")
            )
        phase_resource = resource_type in policy.allowed_resource_types
        exact_phase_addresses = _PHASE_EXACT_RESOURCE_ADDRESSES.get(
            policy.phase,
            {},
        ).get(str(resource_type))
        if exact_phase_addresses is not None:
            phase_resource = phase_resource and address in exact_phase_addresses
        inherited_read_only_resource = (
            resource_type in policy.inherited_read_only_resource_types
            and isinstance(address, str)
            and any(
                address.startswith(prefix)
                for prefix in policy.inherited_read_only_address_prefixes
            )
        )
        if not phase_resource and not inherited_read_only_resource:
            violations.append(
                _violation(
                    "RESOURCE_PROHIBITED",
                    f"{path}/resource_type",
                    "resource type is outside the approved phase inventory",
                    address=safe_address,
                    resource_type=safe_resource_type,
                    actions=safe_actions,
                )
            )
        if provider_source != policy.provider_source:
            violations.append(
                _violation(
                    "SERVICE_MISMATCH",
                    f"{path}/provider_source",
                    "resource provider does not match the approved service",
                )
            )
        valid_actions = (
            isinstance(actions, list)
            and bool(actions)
            and all(isinstance(action, str) for action in actions)
        )
        if not valid_actions:
            violations.append(
                _violation(
                    "PLAN_SHAPE_INVALID",
                    f"{path}/actions",
                    "actions must be a non-empty string list",
                )
            )
            normalized_actions: tuple[str, ...] = ()
        else:
            normalized_actions = tuple(actions)
            if (
                planning_mode == "refresh-only"
                and normalized_actions not in {("no-op",), ("read",)}
            ):
                violations.append(
                    _violation(
                        "REFRESH_ONLY_MUTATION_PROHIBITED",
                        f"{path}/actions",
                        "refresh-only planning may only preserve or read resources",
                        address=safe_address,
                        resource_type=safe_resource_type,
                        actions=normalized_actions,
                    )
                )
            elif (
                inherited_read_only_resource
                and normalized_actions not in {("no-op",), ("read",)}
                and normalized_actions
                not in _PHASE_EXACT_INHERITED_MUTATIONS.get(
                    policy.phase,
                    {},
                ).get(safe_address, frozenset())
            ):
                violations.append(
                    _violation(
                        "INHERITED_RESOURCE_MUTATION_PROHIBITED",
                        f"{path}/actions",
                        "an inherited resource may only remain unchanged or be read",
                        address=safe_address,
                        resource_type=safe_resource_type,
                        actions=normalized_actions,
                    )
                )
            elif "create" in normalized_actions and "delete" in normalized_actions:
                violations.append(
                    _violation(
                        "REPLACEMENT_PROHIBITED",
                        f"{path}/actions",
                        "resource replacement is never implicit plan authority",
                        address=safe_address,
                        resource_type=safe_resource_type,
                        actions=normalized_actions,
                    )
                )
            elif "delete" in normalized_actions and not policy.destructive:
                violations.append(
                    _violation(
                        "DESTRUCTIVE_ACTION_PROHIBITED",
                        f"{path}/actions",
                        "delete requires a separate destructive policy",
                        address=safe_address,
                        resource_type=safe_resource_type,
                        actions=normalized_actions,
                    )
                )
            elif "delete" in normalized_actions and any(
                isinstance(address, str) and address.startswith(prefix)
                for prefix in policy.prohibited_delete_address_prefixes
            ):
                violations.append(
                    _violation(
                        "RETAINED_RESOURCE_DELETE_PROHIBITED",
                        f"{path}/address",
                        "retained recovery, evidence, or provider material cannot be deleted",
                        address=safe_address,
                        resource_type=safe_resource_type,
                        actions=normalized_actions,
                    )
                )
            elif (
                normalized_actions == ("forget",)
                and safe_address
                in _PHASE_EXACT_FORGET_ADDRESSES.get(policy.phase, frozenset())
            ):
                pass
            elif (
                len(normalized_actions) != 1
                or normalized_actions[0] not in policy.allowed_actions
            ):
                violations.append(
                    _violation(
                        "ACTION_PROHIBITED",
                        f"{path}/actions",
                        "action is outside the approved phase inventory",
                        address=safe_address,
                        resource_type=safe_resource_type,
                        actions=normalized_actions,
                    )
                )
        summaries.append(
            {
                "actions": list(normalized_actions),
                "address": str(address or ""),
                "provider_source": str(provider_source or ""),
                "resource_type": str(resource_type or ""),
            }
        )
    return sorted(
        summaries,
        key=lambda value: (
            str(value["resource_type"]),
            str(value["address"]),
            tuple(value["actions"]),
        ),
    )


def evaluate_plan(
    policy: PlanPolicy,
    observation: dict[str, Any],
) -> PlanPolicyResult:
    """Canonicalize and authorize a redacted plan observation or fail closed."""

    if not isinstance(observation, dict):
        violation = _violation("PLAN_SHAPE_INVALID", "", "plan observation must be an object")
        return PlanPolicyResult(False, None, None, (violation,))
    violations: list[PlanViolation] = []
    _compare_context(observation, policy, violations)
    provider = _provider_summary(observation, policy, violations)
    planning_mode = _planning_mode(observation, policy, violations)
    changes = _change_summaries(observation, policy, planning_mode, violations)
    ordered = _ordered(violations)
    if ordered or provider is None:
        return PlanPolicyResult(False, None, None, ordered)

    summary: dict[str, Any] = {
        "changes": changes,
        "destructive_boundary": {"allowed": policy.destructive},
        "environment": policy.environment,
        "owner_id": policy.owner_id,
        "phase": policy.phase,
        "planning_mode": planning_mode,
        "project_id": policy.project_id,
        "provider": provider,
        "source_revision": policy.source_revision,
        "state_owner": policy.state_owner,
        "terraform_root": policy.terraform_root,
    }
    contents = json.dumps(
        summary,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    digest = f"sha256:{hashlib.sha256(contents).hexdigest()}"
    return PlanPolicyResult(True, digest, summary, ())
