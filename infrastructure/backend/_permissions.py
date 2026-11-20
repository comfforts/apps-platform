"""Reviewable least-privilege role intents for AP-M9 operation identities."""

from __future__ import annotations

from dataclasses import dataclass
import re

from infrastructure.backend._lifecycle import (
    EnvironmentUnavailableError,
    OperationAuthority,
    operation_authorities,
)


_PROJECT_ID = "comfforts-platform-non-prod"
_PROJECT_RESOURCE = f"projects/{_PROJECT_ID}"
_CONFIGURATION_BUCKET = "comfforts-ap-stg-455651441682-configuration"
_EDGE_SERVICE = f"{_PROJECT_RESOURCE}/locations/us-west1/services/app-platform-edge"
_BILLING_ACCOUNT = re.compile(
    r"^billingAccounts/[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$"
)

_PLATFORM_READ_ROLES = (
    "roles/artifactregistry.reader",
    "roles/billing.viewer",
    "roles/browser",
    "roles/cloudkms.viewer",
    "roles/compute.viewer",
    "roles/datastore.viewer",
    "roles/iam.securityReviewer",
    "roles/iam.serviceAccountViewer",
    "roles/logging.viewer",
    "roles/monitoring.viewer",
    "roles/run.viewer",
    "roles/secretmanager.viewer",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/storage.viewer",
)
_PLATFORM_MUTATE_ROLES = (
    "roles/artifactregistry.admin",
    "roles/cloudkms.admin",
    "roles/compute.loadBalancerAdmin",
    "roles/compute.networkAdmin",
    "roles/datastore.owner",
    "roles/iam.serviceAccountAdmin",
    "roles/logging.admin",
    "roles/monitoring.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/storage.admin",
)
_FIXTURE_READ_ROLES = (
    "roles/browser",
    "roles/iam.serviceAccountViewer",
    "roles/run.viewer",
    "roles/serviceusage.serviceUsageConsumer",
)
_FIXTURE_MUTATE_ROLES = (
    "roles/browser",
    "roles/iam.serviceAccountAdmin",
    "roles/run.admin",
    "roles/serviceusage.serviceUsageConsumer",
)


@dataclass(frozen=True, slots=True, order=True)
class OperationRoleBinding:
    """One intended IAM binding with an optional exact resource condition."""

    authority_email: str
    action: str
    scope_kind: str
    scope: str
    role: str
    condition_title: str | None = None
    condition_expression: str | None = None


def _binding(
    authority: OperationAuthority,
    scope_kind: str,
    scope: str,
    role: str,
    *,
    condition_title: str | None = None,
    condition_expression: str | None = None,
) -> OperationRoleBinding:
    return OperationRoleBinding(
        authority_email=authority.service_account_email,
        action=authority.action,
        scope_kind=scope_kind,
        scope=scope,
        role=role,
        condition_title=condition_title,
        condition_expression=condition_expression,
    )


def _backend_binding(authority: OperationAuthority) -> OperationRoleBinding | None:
    if authority.action == "readback":
        role = "roles/storage.objectViewer"
    elif authority.action in {"apply", "destroy", "plan", "recovery", "rollback"}:
        role = "roles/storage.objectUser"
    else:
        return None
    prefix = authority.backend_prefix.rstrip("/") + "/"
    return _binding(
        authority,
        "bucket",
        authority.backend_bucket,
        role,
        condition_title=(
            f"{authority.service_account_id}-state-prefix"
        ),
        condition_expression=(
            "resource.name.startsWith("
            f"'projects/_/buckets/{authority.backend_bucket}/objects/{prefix}'"
            ")"
        ),
    )


def _project_roles(authority: OperationAuthority) -> tuple[str, ...]:
    root = authority.terraform_root
    action = authority.action
    if root == "infrastructure/terraform/bootstrap":
        if action in {"plan", "readback"}:
            return ("roles/storage.viewer",)
        if action in {"apply", "destroy", "rollback"}:
            return ("roles/storage.admin",)
        return ()
    if root == "infrastructure/terraform/platform":
        if action in {"plan", "readback"}:
            return _PLATFORM_READ_ROLES
        if action in {"apply", "destroy"}:
            return _PLATFORM_MUTATE_ROLES
        return ()
    if root.startswith("infrastructure/terraform/fixtures/"):
        if action in {"plan", "readback"}:
            return _FIXTURE_READ_ROLES
        if action in {"apply", "destroy"}:
            return _FIXTURE_MUTATE_ROLES
    return ()


def _resource_bindings(
    authority: OperationAuthority,
    billing_account_reference: str | None,
) -> tuple[OperationRoleBinding, ...]:
    values: list[OperationRoleBinding] = []
    if authority.terraform_root == "infrastructure/terraform/platform":
        if authority.action == "rollback":
            values.extend(
                (
                    _binding(
                        authority,
                        "cloud-run-service",
                        _EDGE_SERVICE,
                        "roles/run.admin",
                    ),
                    _binding(
                        authority,
                        "bucket",
                        _CONFIGURATION_BUCKET,
                        "roles/storage.objectViewer",
                    ),
                )
            )
        if authority.action == "apply":
            for account_id in (
                "app-platform-edge-caller",
                "app-platform-edge-runtime",
            ):
                values.append(
                    _binding(
                        authority,
                        "service-account",
                        f"{account_id}@{_PROJECT_ID}.iam.gserviceaccount.com",
                        "roles/iam.serviceAccountUser",
                    )
                )
        if (
            authority.action in {"apply", "destroy"}
            and billing_account_reference is not None
        ):
            values.append(
                _binding(
                    authority,
                    "billing-account",
                    billing_account_reference,
                    "roles/billing.costsManager",
                )
            )
    elif authority.terraform_root.startswith(
        "infrastructure/terraform/fixtures/"
    ) and authority.action == "apply":
        account_id = f"{authority.owner_id}-runtime"
        values.append(
            _binding(
                authority,
                "service-account",
                f"{account_id}@{_PROJECT_ID}.iam.gserviceaccount.com",
                "roles/iam.serviceAccountUser",
            )
        )
    return tuple(values)


def operation_role_bindings(
    environment: str,
    *,
    billing_account_reference: str | None = None,
) -> tuple[OperationRoleBinding, ...]:
    """Return deterministic IAM intent; this function performs no IAM action."""

    if environment != "staging":
        raise EnvironmentUnavailableError("OWNERSHIP_TRANSFER_REQUIRED")
    if (
        billing_account_reference is not None
        and _BILLING_ACCOUNT.fullmatch(billing_account_reference) is None
    ):
        raise ValueError("billing account reference is not canonical")
    values: list[OperationRoleBinding] = []
    for authority in operation_authorities(environment):
        backend = _backend_binding(authority)
        if backend is not None:
            values.append(backend)
        values.extend(
            _binding(
                authority,
                "project",
                _PROJECT_RESOURCE,
                role,
            )
            for role in _project_roles(authority)
        )
        values.extend(_resource_bindings(authority, billing_account_reference))
    return tuple(sorted(values))


__all__ = ("OperationRoleBinding", "operation_role_bindings")
