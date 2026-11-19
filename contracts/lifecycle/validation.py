"""Deterministic loading and policy for AP-M9 lifecycle documents."""

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
PROFILE_DIRECTORY = LIFECYCLE_DIRECTORY.parents[1] / "infrastructure" / "config" / "profiles"
SCHEMA_FILES = ("environment-profile.v1.schema.json",)
SCHEMA_IDS = {
    "environment-profile": (
        "urn:comfforts:app-platform:lifecycle:environment-profile:v1"
    ),
}

_PROHIBITED_KEYS = {
    "access_token",
    "credential",
    "credentials",
    "oauth_client_secret",
    "password",
    "private_key",
    "provider_response",
    "saved_plan",
    "secret",
    "secret_value",
    "terraform_state",
}
_PROHIBITED_VALUE_MARKERS = (
    "-----begin private key-----",
    ".tfplan",
    ".tfstate",
    "ghp_",
    "terraform_remote_state",
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
    """One accepted canonical lifecycle document or ordered violations."""

    value: dict[str, Any] | None
    canonical_bytes: bytes | None
    digest: str | None
    violations: tuple[Violation, ...]


def _pointer(path: str, token: str | int) -> str:
    encoded = str(token).replace("~", "~0").replace("/", "~1")
    return f"{path}/{encoded}" if path else f"/{encoded}"


def _ordered(violations: list[Violation]) -> tuple[Violation, ...]:
    return tuple(sorted(violations, key=lambda item: (item.path, item.code, item.message)))


def load_lifecycle_schemas(
    schema_directory: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load the exact bounded local AP-M9 lifecycle schema registry."""

    return load_schema_registry(schema_directory or SCHEMA_DIRECTORY, SCHEMA_FILES)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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
    elif isinstance(value, list):
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
    environment = value.get("environment")
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
    }
    selected = expected.get(environment)
    if selected is None:
        return []
    return [
        Violation(
            "ENVIRONMENT_PROFILE_INVALID",
            f"/{field}",
            f"field must equal the reviewed {environment} value",
        )
        for field, expected_value in selected.items()
        if value.get(field) != expected_value
    ]


def validate_lifecycle_document(
    value: Any,
    expected_kind: str,
    *,
    registry: dict[str, dict[str, Any]] | None = None,
) -> tuple[Violation, ...]:
    """Validate one AP-M9 document without environment or provider access."""

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
        if expected_kind == "environment-profile":
            violations.extend(_profile_violations(value))
    return _ordered(violations)


def canonical_lifecycle_bytes(value: Any, expected_kind: str) -> bytes:
    """Return canonical bytes for one valid lifecycle document."""

    violations = validate_lifecycle_document(value, expected_kind)
    if violations:
        raise ValueError(f"invalid {expected_kind}: {violations!r}")
    return _canonical_bytes(value)


def lifecycle_digest(value: Any, expected_kind: str) -> str:
    """Return the lowercase SHA-256 digest of one valid canonical document."""

    canonical = canonical_lifecycle_bytes(value, expected_kind)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def load_lifecycle_document(
    path: Path,
    expected_kind: str,
    *,
    max_bytes: int = 262_144,
) -> LifecycleDocument:
    """Load one bounded document and require exact canonical bytes."""

    loaded = load_json_document(path, max_bytes=max_bytes)
    if loaded.violations:
        return LifecycleDocument(None, None, None, loaded.violations)
    violations = validate_lifecycle_document(loaded.value, expected_kind)
    if violations or not isinstance(loaded.value, dict):
        return LifecycleDocument(None, None, None, violations)
    canonical = _canonical_bytes(loaded.value)
    stored = path.read_bytes()
    if stored not in {canonical, canonical + b"\n"}:
        violation = Violation(
            "DOCUMENT_NOT_CANONICAL",
            "",
            "document bytes do not match App Platform Canonical JSON Version 1",
        )
        return LifecycleDocument(None, canonical, None, (violation,))
    digest = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return LifecycleDocument(loaded.value, canonical, digest, ())
