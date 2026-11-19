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
PROFILE_DIRECTORY = (
    LIFECYCLE_DIRECTORY.parents[1] / "infrastructure" / "config" / "profiles"
)
SCHEMA_FILES = (
    "deployment-specification.v1.schema.json",
    "environment-profile.v1.schema.json",
    "execution-journal.v1.schema.json",
)
SCHEMA_IDS = {
    "deployment-specification": (
        "urn:comfforts:app-platform:lifecycle:deployment-specification:v1"
    ),
    "environment-profile": (
        "urn:comfforts:app-platform:lifecycle:environment-profile:v1"
    ),
    "execution-journal": (
        "urn:comfforts:app-platform:lifecycle:execution-journal:v1"
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


def _specification_violations(value: dict[str, Any]) -> list[Violation]:
    stages = value.get("stages")
    if not isinstance(stages, list):
        return []
    violations: list[Violation] = []
    declared_outputs: dict[str, set[str]] = {}
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        stage_id = stage.get("stage_id")
        stage_path = f"/stages/{index}"
        if isinstance(stage_id, str):
            if stage_id in declared_outputs:
                violations.append(
                    Violation(
                        "STAGE_DUPLICATE",
                        f"{stage_path}/stage_id",
                        "stage identifier must be unique within a specification",
                    )
                )
            produces = stage.get("produces")
            declared_outputs[stage_id] = (
                {item for item in produces if isinstance(item, str)}
                if isinstance(produces, list)
                else set()
            )
        consumes = stage.get("consumes")
        if not isinstance(consumes, list):
            continue
        prior_stage_ids = {
            item.get("stage_id")
            for item in stages[:index]
            if isinstance(item, dict) and isinstance(item.get("stage_id"), str)
        }
        for binding_index, binding in enumerate(consumes):
            if not isinstance(binding, dict):
                continue
            binding_path = f"{stage_path}/consumes/{binding_index}"
            producer = binding.get("stage_id")
            output_name = binding.get("output_name")
            if producer not in prior_stage_ids:
                violations.append(
                    Violation(
                        "STAGE_BINDING_INVALID",
                        f"{binding_path}/stage_id",
                        "stage output must come from a declared earlier stage",
                    )
                )
            elif output_name not in declared_outputs.get(producer, set()):
                violations.append(
                    Violation(
                        "STAGE_BINDING_INVALID",
                        f"{binding_path}/output_name",
                        "stage output is not declared by its producer",
                    )
                )
    operation = value.get("operation")
    boundary = value.get("destructive_boundary")
    if isinstance(boundary, dict):
        allowed = boundary.get("allowed")
        resources = boundary.get("resource_types")
        if operation == "destroy":
            if allowed is not True:
                violations.append(
                    Violation(
                        "DESTRUCTIVE_BOUNDARY_INVALID",
                        "/destructive_boundary/allowed",
                        "destroy specifications require an explicit destructive boundary",
                    )
                )
            if resources == []:
                violations.append(
                    Violation(
                        "DESTRUCTIVE_BOUNDARY_INVALID",
                        "/destructive_boundary/resource_types",
                        "destroy specifications require explicit destructive resource types",
                    )
                )
        elif allowed is not False or resources != []:
            violations.append(
                Violation(
                    "DESTRUCTIVE_BOUNDARY_INVALID",
                    "/destructive_boundary/allowed",
                    "non-destroy specifications cannot authorize destructive scope",
                )
            )
    return violations


def _journal_violations(value: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    revision = value.get("journal_revision")
    predecessor = value.get("previous_journal_digest")
    if revision == 1 and predecessor is not None:
        violations.append(
            Violation(
                "JOURNAL_CHAIN_INVALID",
                "/previous_journal_digest",
                "journal revision 1 has no predecessor",
            )
        )
    if isinstance(revision, int) and revision > 1 and not isinstance(predecessor, str):
        violations.append(
            Violation(
                "JOURNAL_CHAIN_INVALID",
                "/previous_journal_digest",
                "later journal revisions require the predecessor digest",
            )
        )
    entries = value.get("entries")
    if isinstance(entries, list):
        for index, entry in enumerate(entries):
            if isinstance(entry, dict) and entry.get("sequence") != index + 1:
                violations.append(
                    Violation(
                        "JOURNAL_SEQUENCE_INVALID",
                        f"/entries/{index}/sequence",
                        "journal entry sequence must be contiguous and one-based",
                    )
                )
    return violations


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
        elif expected_kind == "deployment-specification":
            violations.extend(_specification_violations(value))
        elif expected_kind == "execution-journal":
            violations.extend(_journal_violations(value))
    return _ordered(violations)


def _relationship_violation(code: str, path: str, message: str) -> Violation:
    return Violation(code, path, message)


def _prefixed_violations(
    prefix: str,
    violations: tuple[Violation, ...],
) -> list[Violation]:
    return [
        Violation(
            item.code,
            f"/{prefix}{item.path}" if item.path else f"/{prefix}",
            item.message,
        )
        for item in violations
    ]


def validate_lifecycle_relationships(
    *,
    specification: dict[str, Any] | None = None,
    journal: dict[str, Any] | None = None,
    previous_journal: dict[str, Any] | None = None,
    status: dict[str, Any] | None = None,
    integration_bundle: dict[str, Any] | None = None,
    attachment_bundle: dict[str, Any] | None = None,
) -> tuple[Violation, ...]:
    """Validate digest, environment, source, stage, and append-only relationships."""

    violations: list[Violation] = []
    documents = (
        ("specification", specification, "deployment-specification"),
        ("journal", journal, "execution-journal"),
        ("previous_journal", previous_journal, "execution-journal"),
    )
    for prefix, document, kind in documents:
        if document is not None:
            violations.extend(
                _prefixed_violations(
                    prefix,
                    validate_lifecycle_document(document, kind),
                )
            )
    del status, integration_bundle, attachment_bundle
    if violations:
        return _ordered(violations)

    if specification is not None and journal is not None:
        expected_digest = lifecycle_digest(specification, "deployment-specification")
        if journal.get("specification_digest") != expected_digest:
            violations.append(
                _relationship_violation(
                    "DIGEST_MISMATCH",
                    "/journal/specification_digest",
                    "journal is not bound to the exact specification digest",
                )
            )
        for field in ("environment", "operation"):
            if journal.get(field) != specification.get(field):
                violations.append(
                    _relationship_violation(
                        "DOCUMENT_RELATION_INVALID",
                        f"/journal/{field}",
                        f"journal {field} does not match the specification",
                    )
                )
        source = specification.get("source")
        expected_revision = source.get("revision") if isinstance(source, dict) else None
        if journal.get("source_revision") != expected_revision:
            violations.append(
                _relationship_violation(
                    "DOCUMENT_RELATION_INVALID",
                    "/journal/source_revision",
                    "journal source revision does not match the specification",
                )
            )
        stages = specification.get("stages")
        declared_stages = (
            {
                stage.get("stage_id"): stage
                for stage in stages
                if isinstance(stage, dict) and isinstance(stage.get("stage_id"), str)
            }
            if isinstance(stages, list)
            else {}
        )
        entries = journal.get("entries")
        if isinstance(entries, list):
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                entry_path = f"/journal/entries/{index}"
                stage = declared_stages.get(entry.get("stage_id"))
                if stage is None:
                    violations.append(
                        _relationship_violation(
                            "SCOPE_EXPANSION",
                            f"{entry_path}/stage_id",
                            "journal cannot name a stage outside its specification",
                        )
                    )
                    allowed_outputs: set[str] = set()
                else:
                    produces = stage.get("produces")
                    allowed_outputs = (
                        {item for item in produces if isinstance(item, str)}
                        if isinstance(produces, list)
                        else set()
                    )
                outputs = entry.get("outputs")
                if isinstance(outputs, list):
                    for output_index, output in enumerate(outputs):
                        if (
                            isinstance(output, dict)
                            and output.get("name") not in allowed_outputs
                        ):
                            violations.append(
                                _relationship_violation(
                                    "SCOPE_EXPANSION",
                                    f"{entry_path}/outputs/{output_index}/name",
                                    "journal output is not declared by its specification stage",
                                )
                            )
                    if (
                        stage is not None
                        and entry.get("outcome") == "succeeded"
                        and {output.get("name") for output in outputs if isinstance(output, dict)}
                        != allowed_outputs
                    ):
                        violations.append(
                            _relationship_violation(
                                "STAGE_OUTPUT_INCOMPLETE",
                                f"{entry_path}/outputs",
                            "a succeeded stage must record every declared output exactly once",
                            )
                        )

    if previous_journal is not None and journal is not None:
        previous_revision = previous_journal.get("journal_revision")
        if (
            not isinstance(previous_revision, int)
            or journal.get("journal_revision") != previous_revision + 1
        ):
            violations.append(
                _relationship_violation(
                    "JOURNAL_CHAIN_INVALID",
                    "/journal/journal_revision",
                    "journal revision must advance its predecessor by one",
                )
            )
        expected_predecessor = lifecycle_digest(previous_journal, "execution-journal")
        if journal.get("previous_journal_digest") != expected_predecessor:
            violations.append(
                _relationship_violation(
                    "DIGEST_MISMATCH",
                    "/journal/previous_journal_digest",
                    "journal predecessor digest is stale or incorrect",
                )
            )
        previous_entries = previous_journal.get("entries")
        current_entries = journal.get("entries")
        if isinstance(previous_entries, list) and isinstance(current_entries, list):
            for index, entry in enumerate(previous_entries):
                if index >= len(current_entries) or current_entries[index] != entry:
                    violations.append(
                        _relationship_violation(
                            "JOURNAL_NOT_APPEND_ONLY",
                            f"/journal/entries/{index}",
                            "an existing journal entry cannot be removed or rewritten",
                        )
                    )
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
