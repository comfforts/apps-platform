"""Deterministic backend lineages without backend access or initialization."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile


_STAGING_PROJECT_ID = "comfforts-platform-non-prod"
_STAGING_PROJECT_NUMBER = "455651441682"
_STAGING_BUCKETS = {
    "platform": "comfforts-ap-stg-455651441682-platform-state",
    "fixture-public": "comfforts-ap-stg-455651441682-fixture-public-state",
    "fixture-authenticated": (
        "comfforts-ap-stg-455651441682-fixture-authenticated-state"
    ),
    "fixture-restricted": (
        "comfforts-ap-stg-455651441682-fixture-restricted-state"
    ),
}


class EnvironmentUnavailableError(ValueError):
    """The requested environment has no deployment authority."""


@dataclass(frozen=True, slots=True)
class BackendDeclaration:
    """One phase-to-lineage binding with no credential or backend contents."""

    environment: str
    phase: str
    terraform_root: str
    state_owner: str
    owner_id: str
    project_id: str
    project_number: str
    bucket: str
    prefix: str


@dataclass(frozen=True, slots=True)
class RenderedBackend:
    """Result of rendering one private generated backend declaration."""

    path: Path
    digest: str
    created: bool


@dataclass(frozen=True, slots=True)
class OperationAuthority:
    """One exact local impersonation scope; it creates no identity or token."""

    environment: str
    terraform_root: str
    state_owner: str
    owner_id: str
    project_id: str
    action: str
    service_account_id: str
    service_account_email: str
    backend_bucket: str
    backend_prefix: str
    backend_access: tuple[str, ...]
    provider_access: str
    credential_source: str = "short-lived-human-adc"
    token_lifetime_seconds: int = 3600
    service_account_key_allowed: bool = False
    self_administration_allowed: bool = False

    @property
    def impersonation_environment(self) -> tuple[tuple[str, str], ...]:
        """Return the only non-secret environment binding for this authority."""

        return (("GOOGLE_IMPERSONATE_SERVICE_ACCOUNT", self.service_account_email),)


def backend_declarations(environment: str) -> tuple[BackendDeclaration, ...]:
    """Return the exact reviewed phase bindings for an enabled environment."""

    if environment == "production":
        raise EnvironmentUnavailableError("OWNERSHIP_TRANSFER_REQUIRED")
    if environment != "staging":
        raise EnvironmentUnavailableError(f"unsupported environment {environment!r}")

    shared = {
        "environment": "staging",
        "project_id": _STAGING_PROJECT_ID,
        "project_number": _STAGING_PROJECT_NUMBER,
    }
    platform_bucket = _STAGING_BUCKETS["platform"]
    return (
        BackendDeclaration(
            **shared,
            phase="bootstrap",
            terraform_root="infrastructure/terraform/bootstrap",
            state_owner="platform",
            owner_id="app-platform",
            bucket=platform_bucket,
            prefix="bootstrap",
        ),
        BackendDeclaration(
            **shared,
            phase="platform-foundation",
            terraform_root="infrastructure/terraform/platform",
            state_owner="platform",
            owner_id="app-platform",
            bucket=platform_bucket,
            prefix="platform",
        ),
        BackendDeclaration(
            **shared,
            phase="shared-edge",
            terraform_root="infrastructure/terraform/platform",
            state_owner="platform",
            owner_id="app-platform",
            bucket=platform_bucket,
            prefix="platform",
        ),
        *(
            BackendDeclaration(
                **shared,
                phase=owner_id,
                terraform_root=f"infrastructure/terraform/fixtures/{owner_id}",
                state_owner="application",
                owner_id=owner_id,
                bucket=_STAGING_BUCKETS[owner_id],
                prefix=f"fixtures/{owner_id}",
            )
            for owner_id in (
                "fixture-public",
                "fixture-authenticated",
                "fixture-restricted",
            )
        ),
    )


_BACKEND_ACCESS = {
    "apply": ("read-state", "write-state", "lock"),
    "bootstrap": (),
    "destroy": ("read-state", "write-state", "lock"),
    "plan": ("read-state", "lock"),
    "readback": ("read-metadata",),
    "recovery": ("read-state", "write-state", "lock", "recovery-copy"),
    "rollback": ("read-state", "write-state", "lock"),
}
_PROVIDER_ACCESS = {
    "apply": "mutate-owned-resources",
    "bootstrap": "create-backend-and-operation-identities",
    "destroy": "destroy-owned-resources",
    "plan": "read-owned-resources",
    "readback": "read-owned-resources",
    "recovery": "none",
    "rollback": "mutate-owned-resources",
}
_ROOT_CODES = {
    "infrastructure/terraform/bootstrap": "bootstrap",
    "infrastructure/terraform/platform": "platform",
    "infrastructure/terraform/fixtures/fixture-public": "fxpub",
    "infrastructure/terraform/fixtures/fixture-authenticated": "fxauth",
    "infrastructure/terraform/fixtures/fixture-restricted": "fxrest",
}


def operation_authorities(environment: str) -> tuple[OperationAuthority, ...]:
    """Return exact keyless operation scopes for every independent lineage."""

    declarations = backend_declarations(environment)
    lineages: list[BackendDeclaration] = []
    observed: set[tuple[str, str]] = set()
    for declaration in declarations:
        lineage = (declaration.bucket, declaration.prefix)
        if lineage not in observed:
            observed.add(lineage)
            lineages.append(declaration)

    values: list[OperationAuthority] = []
    actions = ("plan", "apply", "readback", "rollback", "destroy", "recovery")
    for declaration in lineages:
        selected_actions = actions
        if declaration.phase == "bootstrap":
            selected_actions = ("bootstrap", *actions)
        root_code = _ROOT_CODES[declaration.terraform_root]
        for action in selected_actions:
            account_id = f"ap-stg-{root_code}-{action}"
            values.append(
                OperationAuthority(
                    environment=declaration.environment,
                    terraform_root=declaration.terraform_root,
                    state_owner=declaration.state_owner,
                    owner_id=declaration.owner_id,
                    project_id=declaration.project_id,
                    action=action,
                    service_account_id=account_id,
                    service_account_email=(
                        f"{account_id}@{declaration.project_id}.iam.gserviceaccount.com"
                    ),
                    backend_bucket=declaration.bucket,
                    backend_prefix=declaration.prefix,
                    backend_access=_BACKEND_ACCESS[action],
                    provider_access=_PROVIDER_ACCESS[action],
                )
            )
    return tuple(values)


def _backend_bytes(declaration: BackendDeclaration) -> bytes:
    bucket = json.dumps(declaration.bucket, ensure_ascii=True)
    prefix = json.dumps(declaration.prefix, ensure_ascii=True)
    return (
        "terraform {\n"
        '  backend "gcs" {\n'
        f"    bucket = {bucket}\n"
        f"    prefix = {prefix}\n"
        "  }\n"
        "}\n"
    ).encode("utf-8")


def _bounded(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("backend destination must be a relative path")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        raise ValueError("backend destination escapes its approved root")
    return candidate


def render_backend_declaration(
    declaration: BackendDeclaration,
    destination_root: Path,
    relative_path: str,
) -> RenderedBackend:
    """Render one canonical declaration without contacting or initializing it."""

    destination = _bounded(destination_root, relative_path)
    contents = _backend_bytes(declaration)
    digest = f"sha256:{hashlib.sha256(contents).hexdigest()}"
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != contents:
            raise FileExistsError("refusing to replace a different backend declaration")
        return RenderedBackend(destination, digest, False)

    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".backend-",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)
        destination.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return RenderedBackend(destination, digest, True)
