"""Digest-bound identity bootstrap intent without credentials or provider access."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from infrastructure.backend._lifecycle import operation_authorities
from infrastructure.backend._permissions import (
    OperationRoleBinding,
    operation_role_bindings,
)


_HUMAN_PRINCIPAL = re.compile(
    r"^user:[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$"
)


@dataclass(frozen=True, slots=True, order=True)
class ImpersonationGrant:
    """One human-to-operation-identity short-lived token grant."""

    service_account_email: str
    operator_principal: str
    role: str = "roles/iam.serviceAccountTokenCreator"


@dataclass(frozen=True, slots=True)
class IdentityBootstrapPlan:
    """Complete private identity-bootstrap scope bound to a canonical digest."""

    environment: str
    project_id: str
    operator_principal: str
    identities: tuple[str, ...]
    impersonation_grants: tuple[ImpersonationGrant, ...]
    role_bindings: tuple[OperationRoleBinding, ...]
    digest: str


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def compile_identity_bootstrap_plan(
    environment: str,
    *,
    operator_principal: str,
    billing_account_reference: str,
) -> IdentityBootstrapPlan:
    """Compile exact create/grant intent; do not contact IAM or retain a token."""

    if _HUMAN_PRINCIPAL.fullmatch(operator_principal) is None:
        raise ValueError("operator principal must be one explicit human user")
    authorities = operation_authorities(environment)
    identities = tuple(sorted(item.service_account_email for item in authorities))
    grants = tuple(
        ImpersonationGrant(identity, operator_principal)
        for identity in identities
    )
    bindings = operation_role_bindings(
        environment,
        billing_account_reference=billing_account_reference,
    )
    project_ids = {item.project_id for item in authorities}
    if len(project_ids) != 1:
        raise ValueError("identity bootstrap spans more than one project")
    project_id = next(iter(project_ids))
    material = {
        "environment": environment,
        "identities": list(identities),
        "impersonation_grants": [asdict(item) for item in grants],
        "operator_principal": operator_principal,
        "project_id": project_id,
        "role_bindings": [asdict(item) for item in bindings],
    }
    digest = f"sha256:{hashlib.sha256(_canonical_bytes(material)).hexdigest()}"
    return IdentityBootstrapPlan(
        environment=environment,
        project_id=project_id,
        operator_principal=operator_principal,
        identities=identities,
        impersonation_grants=grants,
        role_bindings=bindings,
        digest=digest,
    )


__all__ = (
    "IdentityBootstrapPlan",
    "ImpersonationGrant",
    "compile_identity_bootstrap_plan",
)
