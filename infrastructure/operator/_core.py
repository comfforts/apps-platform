"""Deep AP-M9 lifecycle orchestration behind the small operator interface."""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any

from contracts.lifecycle import (
    canonical_lifecycle_bytes,
    lifecycle_digest,
    load_lifecycle_document,
    validate_lifecycle_document,
    validate_lifecycle_relationships,
)
from infrastructure.operator._interfaces import (
    DiscoverySnapshot,
    ExecutionResult,
    GitSnapshot,
    OperatorInterrupted,
    OperatorAdapters,
    PreflightResult,
    PrepareResult,
    StageContext,
    StageExecution,
    StatusResult,
)
from infrastructure.operator.source_authority import (
    source_authority_blockers,
    validate_source_authority,
)


_PROFILE_PATHS = {
    "production": "infrastructure/config/profiles/production.v1.json",
    "staging": "infrastructure/config/profiles/staging.v1.json",
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest_bytes(contents: bytes) -> str:
    return f"sha256:{hashlib.sha256(contents).hexdigest()}"


def _deployment_stages() -> list[dict[str, object]]:
    return [
        {
            "stage_id": "preflight",
            "actions": ["read"],
            "resource_types": [
                "dns-hostname",
                "environment-profile",
                "provider-project",
                "repository",
                "source",
                "toolchain",
            ],
            "consumes": [],
            "produces": ["preflight-attestation"],
            "manual_checkpoint": "none",
            "readback": "not-applicable",
        },
        {
            "stage_id": "bootstrap-services",
            "actions": ["read", "update"],
            "resource_types": ["provider-service"],
            "consumes": [
                {"stage_id": "preflight", "output_name": "preflight-attestation"}
            ],
            "produces": ["bootstrap-services-attestation"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "bootstrap",
            "actions": ["create", "read"],
            "resource_types": ["backend-bucket"],
            "consumes": [
                {
                    "stage_id": "bootstrap-services",
                    "output_name": "bootstrap-services-attestation",
                }
            ],
            "produces": ["backend-reference"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "foundation",
            "actions": ["create", "read", "update"],
            "resource_types": [
                "artifact-registry",
                "budget",
                "configuration-bucket",
                "evidence-bucket",
                "logging",
                "platform-identity",
                "secret-container",
                "session-store",
                "signing-key",
            ],
            "consumes": [
                {"stage_id": "bootstrap", "output_name": "backend-reference"},
            ],
            "produces": ["foundation-reference", "oauth-secret-container"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "image-publish",
            "actions": ["create", "read"],
            "resource_types": ["shared-edge-image"],
            "consumes": [
                {"stage_id": "foundation", "output_name": "foundation-reference"}
            ],
            "produces": ["shared-edge-image-digest"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "generation-publish",
            "actions": ["create", "read"],
            "resource_types": ["compiled-registration-generation"],
            "consumes": [
                {"stage_id": "foundation", "output_name": "foundation-reference"}
            ],
            "produces": ["registration-generation-reference"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "oauth-configuration",
            "actions": ["create", "read", "update"],
            "resource_types": ["oauth-client", "oauth-secret-version"],
            "consumes": [
                {"stage_id": "foundation", "output_name": "oauth-secret-container"}
            ],
            "produces": ["oauth-client-id", "oauth-secret-version"],
            "manual_checkpoint": "provider-console",
            "readback": "operator-attested",
        },
        {
            "stage_id": "shared-edge",
            "actions": ["create", "read", "update"],
            "resource_types": ["load-balancer", "reserved-address", "shared-edge"],
            "consumes": [
                {"stage_id": "foundation", "output_name": "foundation-reference"},
                {
                    "stage_id": "image-publish",
                    "output_name": "shared-edge-image-digest",
                },
                {
                    "stage_id": "oauth-configuration",
                    "output_name": "oauth-client-id",
                },
                {
                    "stage_id": "oauth-configuration",
                    "output_name": "oauth-secret-version",
                },
                {
                    "stage_id": "generation-publish",
                    "output_name": "registration-generation-reference",
                },
            ],
            "produces": ["edge-reference", "reserved-address"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "external-dns",
            "actions": ["create", "read"],
            "resource_types": ["dns-a-record"],
            "consumes": [
                {"stage_id": "shared-edge", "output_name": "reserved-address"}
            ],
            "produces": ["dns-attestation"],
            "manual_checkpoint": "external-dns",
            "readback": "provider-verified",
        },
        {
            "stage_id": "tls-readiness",
            "actions": ["create", "read"],
            "resource_types": ["managed-certificate"],
            "consumes": [
                {"stage_id": "external-dns", "output_name": "dns-attestation"},
                {"stage_id": "shared-edge", "output_name": "edge-reference"},
            ],
            "produces": ["certificate-reference"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        {
            "stage_id": "readback",
            "actions": ["read"],
            "resource_types": ["ownership-inventory", "platform-environment"],
            "consumes": [
                {
                    "stage_id": "tls-readiness",
                    "output_name": "certificate-reference",
                }
            ],
            "produces": ["deployment-attestation"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
    ]


class LifecycleOperator:
    """Prepare and approve exact lifecycle intent without external mutation."""

    def __init__(
        self,
        adapters: OperatorAdapters,
        *,
        source_authority: str = "accepted",
    ) -> None:
        self._adapters = adapters
        self._source_authority = validate_source_authority(source_authority)

    def _load_profile(self, environment: str) -> tuple[dict[str, Any], str]:
        try:
            profile_path = _PROFILE_PATHS[environment]
        except KeyError as error:
            raise ValueError(f"unsupported environment {environment!r}") from error
        loaded = load_lifecycle_document(
            self._adapters.filesystem.project_path(profile_path),
            "environment-profile",
        )
        if loaded.violations or loaded.value is None or loaded.digest is None:
            raise ValueError(f"invalid committed environment profile: {loaded.violations!r}")
        return loaded.value, loaded.digest

    def _source_blockers(
        self,
        snapshot: GitSnapshot,
        environment: str,
    ) -> list[str]:
        return list(
            source_authority_blockers(
                snapshot,
                environment,
                self._source_authority,
            )
        )

    @staticmethod
    def _discovery_conflicts(
        profile: dict[str, Any],
        discoveries: tuple[DiscoverySnapshot, ...],
    ) -> list[str]:
        facts = {
            f"{discovery.name}.{name}": value
            for discovery in discoveries
            for name, value in discovery.facts
        }
        expected = {
            "github.repository": "comfforts/apps-platform",
            "gcp.project_id": profile.get("project_id"),
            "gcp.project_number": profile.get("project_number"),
            "gcp.region": profile.get("region"),
            "dns.provider_class": profile.get("dns_provider_class"),
            "dns.hostname": profile.get("hostname"),
            "terraform.terraform_version": "1.17.2",
            "terraform.provider_version": "8.11.0",
        }
        if any(
            expected_value is not None and facts.get(name) != expected_value
            for name, expected_value in expected.items()
        ):
            return ["DISCOVERY_CONFLICT"]
        return []

    def _discoveries(
        self,
        profile: dict[str, Any],
    ) -> tuple[DiscoverySnapshot, ...]:
        return (
            self._adapters.github.inspect(profile),
            self._adapters.gcp.inspect(profile),
            self._adapters.terraform.inspect(),
            self._adapters.dns.inspect(profile),
        )

    def _freshness_blockers(
        self,
        environment: str,
        profile: dict[str, Any],
        git: GitSnapshot,
        discoveries: tuple[DiscoverySnapshot, ...],
    ) -> tuple[str, ...]:
        blockers = self._source_blockers(git, environment)
        blockers.extend(
            blocker for discovery in discoveries for blocker in discovery.blockers
        )
        blockers.extend(self._discovery_conflicts(profile, discoveries))
        return tuple(sorted(set(blockers)))

    def _readiness(
        self,
        environment: str,
    ) -> tuple[
        dict[str, Any],
        str,
        GitSnapshot | None,
        tuple[DiscoverySnapshot, ...],
        tuple[str, ...],
    ]:
        profile, profile_digest = self._load_profile(environment)
        profile_blockers = tuple(profile.get("blockers", ()))
        if profile.get("lifecycle_state") != "enabled":
            return profile, profile_digest, None, (), profile_blockers

        git = self._adapters.git.inspect()
        discoveries = self._discoveries(profile)
        blockers = self._freshness_blockers(
            environment,
            profile,
            git,
            discoveries,
        )
        return profile, profile_digest, git, discoveries, blockers

    def _report_verified_session(
        self,
        discoveries: tuple[DiscoverySnapshot, ...],
    ) -> None:
        gcp_facts = dict(discoveries[1].facts)
        active_account = gcp_facts.get("active_account")
        active_project = gcp_facts.get("project_id")
        if active_account and active_project:
            self._adapters.terminal.write(
                f"Verified operator session {active_account} for {active_project}."
            )

    def _specification(
        self,
        environment: str,
        profile_digest: str,
        revision: str,
    ) -> dict[str, Any]:
        return {
            "contract_version": 1,
            "document_kind": "deployment-specification",
            "environment": environment,
            "operation": "deploy",
            "profile_digest": profile_digest,
            "source": {
                "authority": self._source_authority,
                "repository": "comfforts/apps-platform",
                "revision": revision,
            },
            "stages": _deployment_stages(),
            "failure_behavior": "stop",
            "destructive_boundary": {"allowed": False, "resource_types": []},
        }

    @staticmethod
    def _state_directory(environment: str) -> str:
        return f"environments/{environment}"

    def _read_json_state(self, relative_path: str) -> dict[str, Any] | None:
        payload = self._adapters.filesystem.read_state(relative_path)
        if payload is None:
            return None
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid generated operator state {relative_path}") from error
        if not isinstance(value, dict):
            raise ValueError(f"invalid generated operator state {relative_path}")
        return value

    def _current_specification_digest(self, environment: str) -> str | None:
        pointer = self._read_json_state(
            f"{self._state_directory(environment)}/current-specification.v1.json"
        )
        if pointer is None:
            return None
        digest = pointer.get("specification_digest")
        if not isinstance(digest, str):
            raise ValueError("current specification pointer has no digest")
        return digest

    def _load_specification(
        self,
        environment: str,
        digest: str,
    ) -> dict[str, Any]:
        path = (
            f"{self._state_directory(environment)}/specifications/"
            f"{digest[7:]}.v1.json"
        )
        loaded = load_lifecycle_document(
            self._adapters.filesystem.state_path(path),
            "deployment-specification",
        )
        if loaded.value is None or loaded.digest != digest or loaded.violations:
            raise ValueError("stored deployment specification is invalid or digest-mismatched")
        return loaded.value

    def _approved(
        self,
        environment: str,
        digest: str,
        *,
        profile_digest: str | None = None,
        source_revision: str | None = None,
    ) -> bool:
        payload = self._adapters.filesystem.read_state(
            f"{self._state_directory(environment)}/approvals/{digest[7:]}.v1.json"
        )
        if payload is None:
            return False
        try:
            approval = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return (
            isinstance(approval, dict)
            and approval.get("approved") is True
            and approval.get("environment") == environment
            and approval.get("specification_digest") == digest
            and (
                profile_digest is None
                or approval.get("profile_digest") == profile_digest
            )
            and (
                source_revision is None
                or approval.get("source_revision") == source_revision
            )
        )

    def _current_journal_pointer(self, environment: str) -> dict[str, Any] | None:
        return self._read_json_state(
            f"{self._state_directory(environment)}/current-journal.v1.json"
        )

    def _load_current_journal(
        self,
        environment: str,
        specification_digest: str,
    ) -> tuple[dict[str, Any], str] | None:
        pointer = self._current_journal_pointer(environment)
        if pointer is None or pointer.get("specification_digest") != specification_digest:
            return None
        revision = pointer.get("journal_revision")
        pointer_digest = pointer.get("journal_digest")
        if not isinstance(revision, int) or not isinstance(pointer_digest, str):
            raise ValueError("current journal pointer is invalid")
        specification = self._load_specification(environment, specification_digest)
        previous: dict[str, Any] | None = None
        current: dict[str, Any] | None = None
        current_digest: str | None = None
        for expected_revision in range(1, revision + 1):
            relative_path = (
                f"{self._state_directory(environment)}/journals/"
                f"{specification_digest[7:]}/{expected_revision:08d}.v1.json"
            )
            loaded = load_lifecycle_document(
                self._adapters.filesystem.state_path(relative_path),
                "execution-journal",
            )
            if loaded.value is None or loaded.digest is None or loaded.violations:
                raise ValueError("stored journal chain contains an invalid revision")
            if loaded.value.get("journal_revision") != expected_revision:
                raise ValueError("stored journal chain has a reordered revision")
            relationships = validate_lifecycle_relationships(
                specification=specification,
                journal=loaded.value,
                previous_journal=previous,
            )
            if relationships:
                raise ValueError("stored journal chain is not append-only or digest-bound")
            previous = loaded.value
            current = loaded.value
            current_digest = loaded.digest
        if current is None or current_digest != pointer_digest:
            raise ValueError("stored journal chain does not match its current pointer")
        return current, current_digest

    def _has_conflicting_journal(
        self,
        environment: str,
        specification_digest: str,
    ) -> bool:
        pointer = self._current_journal_pointer(environment)
        if pointer is None or pointer.get("specification_digest") == specification_digest:
            return False
        other_digest = pointer.get("specification_digest")
        if not isinstance(other_digest, str):
            raise ValueError("current journal pointer is invalid")
        loaded = self._load_current_journal(environment, other_digest)
        if loaded is None:
            raise ValueError("current journal pointer does not resolve")
        journal, _ = loaded
        return journal.get("status") not in {"cancelled", "succeeded"}

    def _store_specification(
        self,
        environment: str,
        specification: dict[str, Any],
        digest: str,
    ) -> None:
        directory = self._state_directory(environment)
        self._adapters.filesystem.write_state(
            f"{directory}/specifications/{digest[7:]}.v1.json",
            canonical_lifecycle_bytes(specification, "deployment-specification") + b"\n",
            replace=False,
        )
        self._adapters.filesystem.write_state(
            f"{directory}/current-specification.v1.json",
            _canonical_bytes({"specification_digest": digest}) + b"\n",
            replace=True,
        )

    def _store_approval(
        self,
        environment: str,
        profile_digest: str,
        source_revision: str,
        specification_digest: str,
    ) -> None:
        approval = {
            "approval_version": 1,
            "approved": True,
            "approved_at": self._adapters.clock.now(),
            "environment": environment,
            "profile_digest": profile_digest,
            "source_revision": source_revision,
            "specification_digest": specification_digest,
        }
        self._adapters.filesystem.write_state(
            (
                f"{self._state_directory(environment)}/approvals/"
                f"{specification_digest[7:]}.v1.json"
            ),
            _canonical_bytes(approval) + b"\n",
            replace=False,
        )

    def _store_journal(
        self,
        specification: dict[str, Any],
        journal: dict[str, Any],
        previous_journal: dict[str, Any] | None,
    ) -> str:
        violations = validate_lifecycle_document(journal, "execution-journal")
        relationship_violations = validate_lifecycle_relationships(
            specification=specification,
            journal=journal,
            previous_journal=previous_journal,
        )
        if violations or relationship_violations:
            raise ValueError(
                "generated invalid execution journal: "
                f"{(*violations, *relationship_violations)!r}"
            )
        digest = lifecycle_digest(journal, "execution-journal")
        environment = str(journal["environment"])
        specification_digest = str(journal["specification_digest"])
        revision = int(journal["journal_revision"])
        directory = self._state_directory(environment)
        self._adapters.filesystem.write_state(
            (
                f"{directory}/journals/{specification_digest[7:]}/"
                f"{revision:08d}.v1.json"
            ),
            canonical_lifecycle_bytes(journal, "execution-journal") + b"\n",
            replace=False,
        )
        pointer = {
            "journal_digest": digest,
            "journal_revision": revision,
            "specification_digest": specification_digest,
        }
        self._adapters.filesystem.write_state(
            f"{directory}/current-journal.v1.json",
            _canonical_bytes(pointer) + b"\n",
            replace=True,
        )
        return digest

    @staticmethod
    def _new_journal(
        environment: str,
        specification: dict[str, Any],
        specification_digest: str,
    ) -> dict[str, Any]:
        source = specification["source"]
        assert isinstance(source, dict)
        return {
            "contract_version": 1,
            "document_kind": "execution-journal",
            "environment": environment,
            "operation": specification["operation"],
            "source_revision": source["revision"],
            "specification_digest": specification_digest,
            "journal_revision": 1,
            "previous_journal_digest": None,
            "status": "running",
            "entries": [],
        }

    @staticmethod
    def _advance_journal(
        journal: dict[str, Any],
        journal_digest: str,
        *,
        status: str,
        entry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entries = list(journal["entries"])
        if entry is not None:
            entries.append(entry)
        return {
            **journal,
            "journal_revision": int(journal["journal_revision"]) + 1,
            "previous_journal_digest": journal_digest,
            "status": status,
            "entries": entries,
        }

    @staticmethod
    def _closed_outputs(
        journal: dict[str, Any],
    ) -> tuple[set[str], dict[tuple[str, str], str]]:
        closed: set[str] = set()
        outputs: dict[tuple[str, str], str] = {}
        entries = journal.get("entries", [])
        assert isinstance(entries, list)
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("outcome") != "succeeded":
                continue
            stage_id = str(entry["stage_id"])
            closed.add(stage_id)
            for output in entry.get("outputs", []):
                if isinstance(output, dict):
                    outputs[(stage_id, str(output["name"]))] = str(output["value"])
        return closed, outputs

    @staticmethod
    def _stage_inputs(
        stage: dict[str, Any],
        outputs: dict[tuple[str, str], str],
    ) -> tuple[tuple[str, str], ...]:
        resolved: list[tuple[str, str]] = []
        for binding in stage["consumes"]:
            stage_id = str(binding["stage_id"])
            output_name = str(binding["output_name"])
            key = (stage_id, output_name)
            if key not in outputs:
                raise ValueError(f"closed stage output is unavailable: {stage_id}/{output_name}")
            resolved.append((f"{stage_id}.{output_name}", outputs[key]))
        return tuple(resolved)

    @staticmethod
    def _stage_input_digest(
        specification_digest: str,
        stage: dict[str, Any],
        inputs: tuple[tuple[str, str], ...],
    ) -> str:
        value = {
            "inputs": [{"name": name, "value": value} for name, value in inputs],
            "specification_digest": specification_digest,
            "stage": stage,
        }
        return _digest_bytes(_canonical_bytes(value))

    @staticmethod
    def _entry(
        sequence: int,
        stage: dict[str, Any],
        stage_input_digest: str,
        result: StageExecution,
    ) -> dict[str, Any]:
        return {
            "sequence": sequence,
            "stage_id": stage["stage_id"],
            "stage_input_digest": stage_input_digest,
            "outcome": result.outcome,
            "plan_digest": result.plan_digest,
            "outputs": [
                {"name": name, "value": value} for name, value in result.outputs
            ],
            "manual_acknowledgement": result.manual_acknowledgement,
        }

    def _blocked_execution(
        self,
        environment: str,
        blockers: tuple[str, ...],
    ) -> ExecutionResult:
        return ExecutionResult(
            "blocked",
            None,
            None,
            self.status(environment),
            blockers,
        )

    def status(self, environment: str) -> StatusResult:
        """Reconcile local lifecycle intent and progress without writing state."""

        profile, profile_digest = self._load_profile(environment)
        profile_blockers = tuple(profile.get("blockers", ()))
        if profile.get("lifecycle_state") != "enabled":
            value = {
                "contract_version": 1,
                "document_kind": "environment-status",
                "environment": environment,
                "profile_digest": profile_digest,
                "source_authority": None,
                "source_revision": None,
                "specification_digest": None,
                "journal_digest": None,
                "lifecycle_state": "blocked",
                "last_closed_stage": None,
                "blockers": list(profile_blockers),
                "qualification_status": "not-run",
            }
            if validate_lifecycle_document(value, "environment-status"):
                raise ValueError("generated invalid disabled-environment status")
            return StatusResult(value, profile_blockers)

        specification_digest = self._current_specification_digest(environment)
        if specification_digest is None:
            value = {
                "contract_version": 1,
                "document_kind": "environment-status",
                "environment": environment,
                "profile_digest": profile_digest,
                "source_authority": None,
                "source_revision": None,
                "specification_digest": None,
                "journal_digest": None,
                "lifecycle_state": "absent",
                "last_closed_stage": None,
                "blockers": [],
                "qualification_status": "not-run",
            }
            if validate_lifecycle_document(value, "environment-status"):
                raise ValueError("generated invalid absent-environment status")
            return StatusResult(value)

        specification = self._load_specification(environment, specification_digest)
        source = specification["source"]
        assert isinstance(source, dict)
        source_authority = str(source["authority"])
        source_revision = str(source["revision"])
        git = self._adapters.git.inspect()
        conflicts = self._source_blockers(git, environment)
        if source_authority != self._source_authority:
            conflicts.append("SOURCE_AUTHORITY_MISMATCH")
        if git.revision != source_revision:
            conflicts.append("SOURCE_REVISION_MISMATCH")
        if specification.get("profile_digest") != profile_digest:
            conflicts.append("PROFILE_DIGEST_MISMATCH")

        loaded_journal = self._load_current_journal(environment, specification_digest)
        ordered_conflicts = tuple(sorted(set(conflicts)))
        if loaded_journal is None:
            value = {
                "contract_version": 1,
                "document_kind": "environment-status",
                "environment": environment,
                "profile_digest": profile_digest,
                "source_authority": None,
                "source_revision": None,
                "specification_digest": None,
                "journal_digest": None,
                "lifecycle_state": "absent",
                "last_closed_stage": None,
                "blockers": list(ordered_conflicts),
                "qualification_status": "not-run",
            }
            violations = validate_lifecycle_document(value, "environment-status")
            relationships = validate_lifecycle_relationships(
                profile=profile,
                status=value,
            )
            if violations or relationships:
                raise ValueError(
                    "generated invalid prepared-environment status: "
                    f"{(*violations, *relationships)!r}"
                )
            return StatusResult(value, ordered_conflicts)

        journal: dict[str, Any] | None = None
        journal_digest: str | None = None
        lifecycle_state = "absent"
        last_closed_stage: str | None = None
        qualification_status = "not-run"
        journal, journal_digest = loaded_journal
        mapping = {
            "cancelled": "cancelled",
            "failed": "failed",
            "running": "deploying",
            "succeeded": "deployed",
            "waiting": "waiting",
        }
        lifecycle_state = mapping[str(journal["status"])]
        entries = journal["entries"]
        assert isinstance(entries, list)
        for entry in entries:
            if isinstance(entry, dict) and entry.get("outcome") == "succeeded":
                last_closed_stage = str(entry["stage_id"])
        if lifecycle_state == "deployed":
            qualification_status = "unqualified"
        value = {
            "contract_version": 1,
            "document_kind": "environment-status",
            "environment": environment,
            "profile_digest": profile_digest,
            "source_authority": source_authority,
            "source_revision": source_revision,
            "specification_digest": specification_digest,
            "journal_digest": journal_digest,
            "lifecycle_state": lifecycle_state,
            "last_closed_stage": last_closed_stage,
            "blockers": list(ordered_conflicts),
            "qualification_status": qualification_status,
        }
        violations = validate_lifecycle_document(value, "environment-status")
        relationships = validate_lifecycle_relationships(
            profile=profile,
            specification=specification,
            journal=journal,
            status=value,
        )
        if violations or relationships:
            raise ValueError(
                f"generated invalid environment status: {(*violations, *relationships)!r}"
            )
        return StatusResult(value, ordered_conflicts)

    def execute(
        self,
        environment: str,
        specification_digest: str,
    ) -> ExecutionResult:
        """Advance only the exact approved specification through an injected executor."""

        profile, profile_digest = self._load_profile(environment)
        current_digest = self._current_specification_digest(environment)
        if current_digest != specification_digest:
            return self._blocked_execution(
                environment,
                ("SPECIFICATION_NOT_CURRENT",),
            )
        specification = self._load_specification(environment, specification_digest)
        source = specification["source"]
        assert isinstance(source, dict)
        source_revision = str(source["revision"])
        git = self._adapters.git.inspect()
        blockers = self._source_blockers(git, environment)
        if source.get("authority") != self._source_authority:
            blockers.append("SOURCE_AUTHORITY_MISMATCH")
        if git.revision != source_revision:
            blockers.append("SOURCE_REVISION_MISMATCH")
        if specification.get("profile_digest") != profile_digest:
            blockers.append("PROFILE_DIGEST_MISMATCH")
        if not self._approved(
            environment,
            specification_digest,
            profile_digest=profile_digest,
            source_revision=source_revision,
        ):
            blockers.append("SPECIFICATION_NOT_APPROVED")
        if self._adapters.executor is None:
            blockers.append("EXECUTION_ADAPTER_UNAVAILABLE")
        if blockers:
            return self._blocked_execution(environment, tuple(sorted(set(blockers))))

        loaded = self._load_current_journal(environment, specification_digest)
        if loaded is None:
            journal = self._new_journal(
                environment,
                specification,
                specification_digest,
            )
            journal_digest = self._store_journal(specification, journal, None)
        else:
            journal, journal_digest = loaded
            if journal["status"] == "succeeded":
                return ExecutionResult(
                    "unchanged",
                    journal,
                    journal_digest,
                    self.status(environment),
                )
            if journal["status"] == "cancelled":
                return ExecutionResult(
                    "cancelled",
                    journal,
                    journal_digest,
                    self.status(environment),
                )
            if journal["status"] in {"failed", "waiting"}:
                previous = journal
                journal = self._advance_journal(
                    previous,
                    journal_digest,
                    status="running",
                )
                journal_digest = self._store_journal(
                    specification,
                    journal,
                    previous,
                )

        assert self._adapters.executor is not None
        stages = specification["stages"]
        assert isinstance(stages, list)
        closed, outputs = self._closed_outputs(journal)
        for stage in stages:
            assert isinstance(stage, dict)
            stage_id = str(stage["stage_id"])
            if stage_id in closed:
                continue
            inputs = self._stage_inputs(stage, outputs)
            stage_digest = self._stage_input_digest(
                specification_digest,
                stage,
                inputs,
            )
            try:
                context = StageContext(
                    environment=environment,
                    source_revision=source_revision,
                    specification_digest=specification_digest,
                    stage=MappingProxyType(dict(stage)),
                    inputs=inputs,
                )
                result = self._adapters.executor.execute(context)
            except OperatorInterrupted:
                self._adapters.terminal.write(
                    f"Interrupted before stage {stage_id} closed; safe to resume."
                )
                return ExecutionResult(
                    "interrupted",
                    journal,
                    journal_digest,
                    self.status(environment),
                )

            entry = self._entry(
                len(journal["entries"]) + 1,
                stage,
                stage_digest,
                result,
            )
            candidate_status = (
                "succeeded"
                if result.outcome == "succeeded" and stage is stages[-1]
                else "running"
                if result.outcome == "succeeded"
                else result.outcome
            )
            candidate = self._advance_journal(
                journal,
                journal_digest,
                status=candidate_status,
                entry=entry,
            )
            candidate_violations = validate_lifecycle_document(
                candidate,
                "execution-journal",
            )
            relationship_violations = validate_lifecycle_relationships(
                specification=specification,
                journal=candidate,
                previous_journal=journal,
            )
            if candidate_violations or relationship_violations:
                prohibited = any(
                    violation.code == "PROHIBITED_MATERIAL"
                    for violation in (*candidate_violations, *relationship_violations)
                )
                safe_result = StageExecution(outcome="failed")
                entry = self._entry(
                    len(journal["entries"]) + 1,
                    stage,
                    stage_digest,
                    safe_result,
                )
                candidate = self._advance_journal(
                    journal,
                    journal_digest,
                    status="failed",
                    entry=entry,
                )
                blocker = (
                    "PROHIBITED_STAGE_OUTPUT"
                    if prohibited
                    else "STAGE_RESULT_INVALID"
                )
            else:
                blocker = None

            previous = journal
            journal = candidate
            journal_digest = self._store_journal(
                specification,
                journal,
                previous,
            )
            displayed_outcome = "failed" if blocker is not None else result.outcome
            self._adapters.terminal.write(
                f"Stage {stage_id} closed with outcome {displayed_outcome}."
            )
            if blocker is not None:
                return ExecutionResult(
                    "failed",
                    journal,
                    journal_digest,
                    self.status(environment),
                    (blocker,),
                )
            if result.outcome != "succeeded":
                return ExecutionResult(
                    result.outcome,
                    journal,
                    journal_digest,
                    self.status(environment),
                    result.blockers,
                )
            closed.add(stage_id)
            for name, value in result.outputs:
                outputs[(stage_id, name)] = value

        return ExecutionResult(
            "succeeded",
            journal,
            journal_digest,
            self.status(environment),
        )

    def current_approved_specification(
        self,
        environment: str,
    ) -> PrepareResult | None:
        """Return the current approved specification when its inputs remain valid.

        Absence, source/profile drift, or a missing approval asks the caller to perform
        normal preparation. Invalid retained state and current discovery blockers fail
        closed without replacing the operator's evidence.
        """

        profile, profile_digest = self._load_profile(environment)
        if profile.get("lifecycle_state") != "enabled":
            return None

        try:
            digest = self._current_specification_digest(environment)
            if digest is None:
                return None
            specification = self._load_specification(environment, digest)
        except ValueError:
            return PrepareResult(
                "blocked",
                False,
                False,
                None,
                None,
                ("SPECIFICATION_READBACK_FAILED",),
            )

        git = self._adapters.git.inspect()
        discoveries = self._discoveries(profile)
        blockers = self._freshness_blockers(
            environment,
            profile,
            git,
            discoveries,
        )
        if blockers:
            return PrepareResult(
                "blocked", False, False, None, digest, blockers
            )

        source = specification["source"]
        assert isinstance(source, dict)
        source_revision = str(source["revision"])
        if (
            specification.get("environment") != environment
            or specification.get("profile_digest") != profile_digest
            or source.get("authority") != self._source_authority
            or source.get("repository") != "comfforts/apps-platform"
            or source_revision != git.revision
        ):
            return None
        if not self._approved(
            environment,
            digest,
            profile_digest=profile_digest,
            source_revision=source_revision,
        ):
            return None
        try:
            has_conflict = self._has_conflicting_journal(environment, digest)
        except ValueError:
            return PrepareResult(
                "blocked",
                False,
                False,
                None,
                digest,
                ("JOURNAL_READBACK_FAILED",),
            )
        if has_conflict:
            return PrepareResult(
                "blocked",
                False,
                False,
                None,
                digest,
                ("ACTIVE_JOURNAL_CONFLICT",),
            )

        self._adapters.terminal.write(
            f"Reusing current approved specification {digest} for {environment}."
        )
        return PrepareResult(
            "unchanged", True, True, specification, digest, ()
        )

    def preflight(self, environment: str) -> PreflightResult:
        """Check preparation readiness without writing or approving lifecycle state."""

        _, _, git, discoveries, blockers = self._readiness(environment)
        if blockers:
            return PreflightResult("blocked", False, blockers)
        assert git is not None
        self._report_verified_session(discoveries)
        self._adapters.terminal.write(f"Preflight ready for {environment}.")
        return PreflightResult("ready", True, ())

    def prepare(self, environment: str) -> PrepareResult:
        """Read source and bounded discoveries, then request exact digest approval."""

        profile, profile_digest, git, discoveries, blockers = self._readiness(
            environment
        )
        if blockers:
            return PrepareResult(
                "blocked", False, False, None, None, blockers
            )
        assert git is not None
        self._report_verified_session(discoveries)

        specification = self._specification(
            environment,
            profile_digest,
            git.revision,
        )
        violations = validate_lifecycle_document(
            specification,
            "deployment-specification",
        )
        if violations:
            raise ValueError(f"generated invalid deployment specification: {violations!r}")
        digest = lifecycle_digest(specification, "deployment-specification")
        if self._has_conflicting_journal(environment, digest):
            return PrepareResult(
                "blocked",
                False,
                False,
                None,
                None,
                ("ACTIVE_JOURNAL_CONFLICT",),
            )
        self._store_specification(environment, specification, digest)
        if self._approved(environment, digest):
            self._adapters.terminal.write(
                f"Unchanged approved specification {digest} for {environment}."
            )
            return PrepareResult(
                "unchanged", True, True, specification, digest, ()
            )

        self._adapters.terminal.write(
            f"Complete deployment specification {digest} for {environment}."
        )
        approved = self._adapters.terminal.confirm(
            f"Approve exact deployment specification {digest}? [y/N] "
        )
        if not approved:
            return PrepareResult(
                "cancelled", True, False, specification, digest, ()
            )
        self._store_approval(environment, profile_digest, git.revision, digest)
        return PrepareResult("prepared", True, True, specification, digest, ())
