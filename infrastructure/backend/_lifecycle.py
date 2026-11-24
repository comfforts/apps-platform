"""Deterministic backend lineages without backend access or initialization."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile

from infrastructure.config.project_identity import (
    fixture_state_bucket,
    fixtures_project_id,
)


_STAGING_PROJECT_ID = "comfforts-platform-non-prod"
_STAGING_BUCKETS = {
    "platform": "comfforts-ap-stg-455651441682-platform-state",
}


class EnvironmentUnavailableError(ValueError):
    """The requested environment has no deployment authority."""


class BackendDeclarationConflictError(FileExistsError):
    """A private workspace already names a different state lineage."""


@dataclass(frozen=True, slots=True)
class BackendDeclaration:
    """One phase-to-lineage binding with no credential or backend contents."""

    environment: str
    phase: str
    terraform_root: str
    state_owner: str
    owner_id: str
    project_id: str
    bucket: str
    prefix: str


@dataclass(frozen=True, slots=True)
class RenderedBackend:
    """Result of rendering one private generated backend declaration."""

    path: Path
    digest: str
    created: bool


def backend_declarations(
    environment: str,
    fixture_project_id: str | None = None,
) -> tuple[BackendDeclaration, ...]:
    """Return the exact reviewed phase bindings for an enabled environment."""

    if environment == "production":
        raise EnvironmentUnavailableError("OWNERSHIP_TRANSFER_REQUIRED")
    if environment != "staging":
        raise EnvironmentUnavailableError(f"unsupported environment {environment!r}")

    shared = {
        "environment": "staging",
        "project_id": _STAGING_PROJECT_ID,
    }
    platform_bucket = _STAGING_BUCKETS["platform"]
    selected_fixture_project = fixture_project_id or fixtures_project_id()
    fixture_bucket = fixture_state_bucket(selected_fixture_project)
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
                environment="staging",
                project_id=selected_fixture_project,
                phase=owner_id,
                terraform_root=f"infrastructure/terraform/fixtures/{owner_id}",
                state_owner="application",
                owner_id=owner_id,
                bucket=fixture_bucket,
                prefix=f"fixtures/{owner_id}",
            )
            for owner_id in (
                "fixture-public",
                "fixture-authenticated",
                "fixture-restricted",
            )
        ),
    )


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
            raise BackendDeclarationConflictError(
                "refusing to replace a different backend declaration"
            )
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
