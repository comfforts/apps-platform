"""Small, fixed operator workflow for one Apps Platform environment.

Preparation records one source/profile-bound operation fingerprint. Deployment
follows the fixed stage order below and atomically replaces one private progress
file after each successful readback. Exact plan creation, confirmation, apply,
and provider readback remain in ``deployment.py``; this module does not model a
generic lifecycle graph or journal chain.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any

from contracts.lifecycle import load_lifecycle_document, validate_lifecycle_material
from infrastructure.operator._interfaces import (
    DiscoverySnapshot,
    ActivePlatformSourceReader,
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


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_bytes(value)).hexdigest()}"


# Executable product flow, not a data-driven extension point. The exact-plan
# executor uses this private metadata for readback output and checkpoint checks.
_DEPLOYMENT_STAGES: tuple[dict[str, object], ...] = (
    {
        "stage_id": "preflight",
        "actions": ["read"],
        "produces": [],
        "consumes": [],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "bootstrap-services",
        "actions": ["read", "update"],
        "produces": [],
        "consumes": [],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "bootstrap",
        "actions": ["create", "read"],
        "produces": ["backend-reference"],
        "consumes": [],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "foundation",
        "actions": ["create", "read", "update"],
        "produces": ["foundation-reference", "oauth-secret-container"],
        "consumes": [("bootstrap", "backend-reference")],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "image-publish",
        "actions": ["create", "read"],
        "produces": ["shared-edge-image-digest"],
        "consumes": [("foundation", "foundation-reference")],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "generation-publish",
        "actions": ["create", "read"],
        "produces": ["registration-generation-reference"],
        "consumes": [("foundation", "foundation-reference")],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "oauth-configuration",
        "actions": ["create", "read", "update"],
        "produces": ["oauth-client-id", "oauth-secret-version"],
        "consumes": [("foundation", "oauth-secret-container")],
        "manual_checkpoint": "provider-console",
    },
    {
        "stage_id": "shared-edge",
        "actions": ["create", "read", "update"],
        "produces": ["edge-reference", "hostname", "reserved-address"],
        "consumes": [
            ("foundation", "foundation-reference"),
            ("image-publish", "shared-edge-image-digest"),
            ("oauth-configuration", "oauth-client-id"),
            ("oauth-configuration", "oauth-secret-version"),
            ("generation-publish", "registration-generation-reference"),
        ],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "runtime-activation",
        "actions": ["create", "read", "update"],
        "produces": ["active-runtime-binding"],
        "consumes": [
            ("image-publish", "shared-edge-image-digest"),
            ("generation-publish", "registration-generation-reference"),
            ("shared-edge", "edge-reference"),
        ],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "external-dns",
        "actions": ["create", "read"],
        "produces": [],
        "consumes": [
            ("shared-edge", "hostname"),
            ("shared-edge", "reserved-address"),
            ("runtime-activation", "active-runtime-binding"),
        ],
        "manual_checkpoint": "external-dns",
    },
    {
        "stage_id": "tls-readiness",
        "actions": ["create", "read"],
        "produces": ["certificate-reference"],
        "consumes": [
            ("foundation", "foundation-reference"),
            ("image-publish", "shared-edge-image-digest"),
            ("oauth-configuration", "oauth-client-id"),
            ("oauth-configuration", "oauth-secret-version"),
            ("generation-publish", "registration-generation-reference"),
            ("shared-edge", "edge-reference"),
            ("runtime-activation", "active-runtime-binding"),
        ],
        "manual_checkpoint": "none",
    },
    {
        "stage_id": "readback",
        "actions": ["read"],
        "produces": [],
        "consumes": [
            ("tls-readiness", "certificate-reference"),
            ("runtime-activation", "active-runtime-binding"),
        ],
        "manual_checkpoint": "none",
    },
)

_STAGE_IDS = tuple(str(stage["stage_id"]) for stage in _DEPLOYMENT_STAGES)
_OPERATOR_STAGE_PRESENTATION = {
    "preflight": (1, "Verify source, tools, identity, and project"),
    "bootstrap-services": (2, "Bootstrap state and platform foundation"),
    "bootstrap": (2, "Bootstrap state and platform foundation"),
    "foundation": (2, "Bootstrap state and platform foundation"),
    "image-publish": (3, "Publish the immutable image and initial generation"),
    "generation-publish": (3, "Publish the immutable image and initial generation"),
    "oauth-configuration": (4, "Configure OAuth"),
    "shared-edge": (5, "Create the Shared Edge"),
    "runtime-activation": (5, "Activate the Shared Edge Runtime"),
    "external-dns": (6, "Configure DNS and TLS"),
    "tls-readiness": (6, "Configure DNS and TLS"),
    "readback": (7, "Verify the deployed platform"),
}
_OPERATOR_STAGE_COUNT = 7
_REPLACEABLE_PROGRESS = {"cancelled", "failed", "succeeded"}
_PROGRESS_STATUSES = {"cancelled", "failed", "running", "succeeded", "waiting"}
_READINESS_BLOCKER_GUIDANCE = {
    "CANDIDATE_BASE_STALE": (
        "the candidate branch does not contain current origin/main; update the branch before "
        "retrying"
    ),
    "CANDIDATE_BRANCH_REQUIRED": (
        "Candidate Source requires a non-main branch for staging"
    ),
    "CANDIDATE_NOT_PUSHED": (
        "Candidate Source requires HEAD to match the configured upstream revision"
    ),
    "CANDIDATE_SOURCE_PRODUCTION_PROHIBITED": (
        "Candidate Source is staging-only and cannot authorize production"
    ),
    "CANDIDATE_UPSTREAM_MISMATCH": (
        "the branch must track its matching origin/<branch> upstream"
    ),
    "DISCOVERY_CONFLICT": (
        "discovered repository, project, region, DNS, or tool facts do not match the "
        "environment profile"
    ),
    "DNS_TOOL_UNAVAILABLE": "the required local dig executable is unavailable",
    "CLOUD_SDK_CONFIGURATION_UNAVAILABLE": (
        "the selected Cloud SDK configuration directory is unavailable or unsafe"
    ),
    "DEPLOYMENT_EXECUTOR_CONSTRUCTION_FAILED": (
        "the bounded deployment executor could not be assembled"
    ),
    "DNS_COMMAND_ADAPTER_UNAVAILABLE": (
        "the bounded DNS command adapter could not be constructed"
    ),
    "DNS_EXECUTABLE_UNAVAILABLE": "the required local dig executable is unavailable",
    "GCLOUD_COMMAND_ADAPTER_UNAVAILABLE": (
        "the bounded Google Cloud command adapter could not be constructed"
    ),
    "GCLOUD_EXECUTABLE_UNAVAILABLE": (
        "the gcloud executable is unavailable"
    ),
    "OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_UNAVAILABLE": (
        "Application Default Credentials are unavailable or cannot mint an access token"
    ),
    "OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_TIMEOUT": (
        "Application Default Credentials did not mint an access token within the bounded retry"
    ),
    "OPERATOR_ACTIVE_ACCOUNT_READBACK_FAILED": (
        "gcloud could not read the active human account after one retry"
    ),
    "OPERATOR_ACTIVE_ACCOUNT_READBACK_TIMEOUT": (
        "gcloud timed out reading the active human account after one retry"
    ),
    "OPERATOR_BILLING_READBACK_FAILED": (
        "gcloud could not read the selected project's billing reference after one retry"
    ),
    "OPERATOR_BILLING_READBACK_TIMEOUT": (
        "gcloud timed out reading the selected project's billing reference after one retry"
    ),
    "OPERATOR_IDENTITY_SESSION_UNAVAILABLE": (
        "the active account, project, billing reference, or identity-token session could not be "
        "verified"
    ),
    "OPERATOR_IDENTITY_TOKEN_FAILED": (
        "gcloud could not mint the human operator identity token after one retry"
    ),
    "OPERATOR_IDENTITY_TOKEN_INVALID": (
        "the minted operator identity token did not match the active human account"
    ),
    "OPERATOR_IDENTITY_TOKEN_TIMEOUT": (
        "gcloud timed out minting the human operator identity token after one retry"
    ),
    "OPERATOR_PROJECT_READBACK_FAILED": (
        "gcloud could not read the active project after one retry"
    ),
    "OPERATOR_PROJECT_READBACK_TIMEOUT": (
        "gcloud timed out reading the active project after one retry"
    ),
    "OPERATOR_STATE_DIRECTORY_UNAVAILABLE": (
        "the private operator state directory is unavailable or unsafe"
    ),
    "OPERATOR_PROJECT_MISMATCH": (
        "the active gcloud project does not match the environment profile"
    ),
    "OPERATOR_SESSION_UNAVAILABLE": (
        "an active gcloud account and project are required"
    ),
    "OWNERSHIP_TRANSFER_REQUIRED": (
        "the environment remains disabled until its documented ownership transfer"
    ),
    "PINNED_TOOL_INVALID": (
        "the project-local Terraform binary or provider package failed version or checksum "
        "validation"
    ),
    "PINNED_TOOL_UNAVAILABLE": (
        "the pinned project-local Terraform binary or provider mirror is unavailable"
    ),
    "REPOSITORY_MISMATCH": (
        "the Git origin is not the canonical comfforts/apps-platform repository"
    ),
    "SOURCE_NOT_CLEAN": (
        "the repository has modified or untracked files; inspect git status --short"
    ),
    "SOURCE_NOT_CURRENT": (
        "Accepted Source requires HEAD, local main, and origin/main to be the same revision"
    ),
    "SOURCE_NOT_MAIN": (
        "Accepted Source requires main; for a pushed staging branch rerun with "
        "SOURCE_AUTHORITY=candidate"
    ),
    "TERRAFORM_CLI_CONFIGURATION_UNAVAILABLE": (
        "the pinned Terraform CLI configuration is unavailable"
    ),
    "TERRAFORM_COMMAND_ADAPTER_UNAVAILABLE": (
        "the bounded Terraform command adapter could not be constructed"
    ),
    "TERRAFORM_EXECUTABLE_UNAVAILABLE": (
        "the pinned project-local Terraform executable is unavailable"
    ),
}


@dataclass(frozen=True, slots=True)
class _CancellationResult:
    outcome: str
    progress: dict[str, Any] | None
    progress_digest: str | None
    blockers: tuple[str, ...] = ()


class LifecycleOperator:
    """Prepare, approve, execute, resume, and inspect the platform workflow."""

    def __init__(
        self,
        adapters: OperatorAdapters,
        *,
        source_authority: str = "accepted",
        active_source_reader: ActivePlatformSourceReader | None = None,
    ) -> None:
        self._adapters = adapters
        self._source_authority = validate_source_authority(source_authority)
        self._active_source_reader = active_source_reader

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

    def _load_profile(self, environment: str) -> tuple[dict[str, Any], str]:
        try:
            profile_path = _PROFILE_PATHS[environment]
        except KeyError as error:
            raise ValueError(f"unsupported environment {environment!r}") from error
        self._adapters.terminal.write(
            f"Environment profile path: {profile_path}"
        )
        loaded = load_lifecycle_document(
            self._adapters.filesystem.project_path(profile_path),
            "environment-profile",
        )
        if loaded.violations or loaded.value is None or loaded.digest is None:
            raise ValueError(f"invalid committed environment profile: {loaded.violations!r}")
        self._adapters.terminal.write(
            "Environment profile loaded: "
            f"environment={environment} lifecycle_state={loaded.value['lifecycle_state']} "
            f"digest={loaded.digest}"
        )
        return loaded.value, loaded.digest

    def _report_source(self, snapshot: GitSnapshot) -> None:
        self._adapters.terminal.write("Source snapshot:")
        values: tuple[tuple[str, object], ...] = (
            ("repository", snapshot.repository),
            ("branch", snapshot.branch),
            ("revision", snapshot.revision),
            ("clean", snapshot.clean),
            ("main_revision", snapshot.main_revision),
            ("origin_main_revision", snapshot.origin_main_revision),
            ("upstream_branch", snapshot.upstream_branch),
            ("upstream_revision", snapshot.upstream_revision),
            ("origin_main_ancestor", snapshot.origin_main_ancestor),
        )
        for name, value in values:
            self._adapters.terminal.write(
                f"  {name}: {json.dumps(value, sort_keys=True)}"
            )

    def _report_discovery(self, discovery: DiscoverySnapshot) -> None:
        outcome = "blocked" if discovery.blockers else "ready"
        self._adapters.terminal.write(
            f"Discovery {discovery.name}: {outcome}"
        )
        for name, value in discovery.facts:
            self._adapters.terminal.write(
                f"  {name}: {json.dumps(value, sort_keys=True)}"
            )
        if discovery.blockers:
            self._adapters.terminal.write(
                "  blockers: " + ", ".join(discovery.blockers)
            )

    def _report_blockers(self, blockers: tuple[str, ...]) -> None:
        for blocker in blockers:
            guidance = _READINESS_BLOCKER_GUIDANCE.get(
                blocker,
                "inspect the preceding source and discovery facts",
            )
            self._adapters.terminal.write(
                f"Readiness blocker {blocker}: {guidance}."
            )

    def _report_development_source_diagnostics(
        self,
        blockers: tuple[str, ...],
    ) -> None:
        for blocker in blockers:
            guidance = _READINESS_BLOCKER_GUIDANCE.get(
                blocker,
                "inspect the preceding source facts",
            )
            self._adapters.terminal.write(
                f"Development source diagnostic {blocker}: {guidance}. "
                "This does not block development preflight and cannot authorize an operation."
            )

    def _source_blockers(
        self,
        snapshot: GitSnapshot,
        environment: str,
    ) -> list[str]:
        return list(
            source_authority_blockers(snapshot, environment, self._source_authority)
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
        discoveries = (
            self._adapters.github.inspect(profile),
            self._adapters.gcp.inspect(profile),
            self._adapters.terraform.inspect(),
            self._adapters.dns.inspect(profile),
        )
        for discovery in discoveries:
            self._report_discovery(discovery)
        return discoveries

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
        *,
        report_blockers: bool = True,
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
            if report_blockers:
                self._report_blockers(profile_blockers)
            return profile, profile_digest, None, (), profile_blockers
        git = self._adapters.git.inspect()
        self._report_source(git)
        discoveries = self._discoveries(profile)
        blockers = self._freshness_blockers(environment, profile, git, discoveries)
        if report_blockers:
            self._report_blockers(blockers)
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
            "specification_version": 1,
            "environment": environment,
            "operation": "deploy",
            "workflow": "platform-deploy-v1",
            "profile_digest": profile_digest,
            "source": {
                "authority": self._source_authority,
                "repository": "comfforts/apps-platform",
                "revision": revision,
            },
        }

    @staticmethod
    def _valid_specification(value: dict[str, Any]) -> bool:
        source = value.get("source")
        return (
            set(value)
            == {
                "specification_version",
                "environment",
                "operation",
                "workflow",
                "profile_digest",
                "source",
            }
            and value.get("specification_version") == 1
            and value.get("environment") in _PROFILE_PATHS
            and value.get("operation") == "deploy"
            and value.get("workflow") == "platform-deploy-v1"
            and isinstance(value.get("profile_digest"), str)
            and isinstance(source, dict)
            and set(source) == {"authority", "repository", "revision"}
            and source.get("authority") in {"accepted", "candidate"}
            and source.get("repository") == "comfforts/apps-platform"
            and isinstance(source.get("revision"), str)
            and len(source["revision"]) == 40
        )

    def _current_specification_digest(self, environment: str) -> str | None:
        pointer = self._read_json_state(
            f"{self._state_directory(environment)}/current-specification.v1.json"
        )
        if pointer is None:
            return None
        digest = pointer.get("specification_digest")
        if (
            set(pointer) != {"specification_digest"}
            or not isinstance(digest, str)
            or not digest.startswith("sha256:")
        ):
            raise ValueError("current specification pointer is invalid")
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
        value = self._read_json_state(path)
        if value is None or not self._valid_specification(value) or _digest(value) != digest:
            raise ValueError("stored deployment specification is invalid or digest-mismatched")
        return value

    def _approved(
        self,
        environment: str,
        digest: str,
        *,
        profile_digest: str | None = None,
        source_revision: str | None = None,
    ) -> bool:
        approval = self._read_json_state(
            f"{self._state_directory(environment)}/approvals/{digest[7:]}.v1.json"
        )
        return (
            approval is not None
            and approval.get("approved") is True
            and approval.get("environment") == environment
            and approval.get("specification_digest") == digest
            and (profile_digest is None or approval.get("profile_digest") == profile_digest)
            and (source_revision is None or approval.get("source_revision") == source_revision)
        )

    def _store_specification(
        self,
        environment: str,
        specification: dict[str, Any],
        digest: str,
    ) -> None:
        directory = self._state_directory(environment)
        self._adapters.filesystem.write_state(
            f"{directory}/specifications/{digest[7:]}.v1.json",
            _canonical_bytes(specification) + b"\n",
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

    def _progress_path(self, environment: str) -> str:
        return f"{self._state_directory(environment)}/current-progress.v1.json"

    def _terminal_progress_path(
        self,
        environment: str,
        specification_digest: str,
    ) -> str:
        return (
            f"{self._state_directory(environment)}/progress/"
            f"{specification_digest[7:]}.final.v1.json"
        )

    def _load_progress(self, environment: str) -> dict[str, Any] | None:
        value = self._read_json_state(self._progress_path(environment))
        if value is None:
            return None
        value = self._normalize_progress(value, environment)
        if (
            value is None
            or not self._valid_progress(value, environment)
            or validate_lifecycle_material(value)
        ):
            raise ValueError("stored deployment progress is invalid")
        return value

    @staticmethod
    def _normalize_progress(
        value: dict[str, Any],
        environment: str,
    ) -> dict[str, Any] | None:
        """Upgrade the one pre-hostname private progress shape in memory."""

        normalized = json.loads(json.dumps(value))
        completed = normalized.get("completed")
        if not isinstance(completed, list):
            return normalized
        expected_hostname = {
            "staging": "apps-staging.comfforts.com",
            "production": "apps.comfforts.com",
        }.get(environment)
        for entry in completed:
            if not isinstance(entry, dict) or entry.get("stage_id") != "shared-edge":
                continue
            outputs = entry.get("outputs")
            if not isinstance(outputs, list):
                return None
            names = [
                output.get("name") if isinstance(output, dict) else None
                for output in outputs
            ]
            if names != ["edge-reference", "reserved-address"]:
                return normalized
            edge_reference = outputs[0].get("value")
            if not isinstance(edge_reference, str):
                return None
            try:
                edge = json.loads(edge_reference)
                hostname = edge["edge"]["hostname"]
            except (KeyError, TypeError, json.JSONDecodeError):
                return None
            if hostname != expected_hostname:
                return None
            outputs.insert(1, {"name": "hostname", "value": hostname})
        return normalized

    @staticmethod
    def _valid_progress(value: dict[str, Any], environment: str) -> bool:
        if set(value) != {
            "progress_version",
            "environment",
            "operation",
            "source_revision",
            "specification_digest",
            "status",
            "completed",
            "active_stage",
            "blockers",
        }:
            return False
        completed = value.get("completed")
        if (
            value.get("progress_version") != 1
            or value.get("environment") != environment
            or value.get("operation") != "deploy"
            or not isinstance(value.get("source_revision"), str)
            or not isinstance(value.get("specification_digest"), str)
            or value.get("status") not in _PROGRESS_STATUSES
            or not isinstance(completed, list)
            or not isinstance(value.get("active_stage"), (str, type(None)))
            or not isinstance(value.get("blockers"), list)
            or not all(isinstance(item, str) for item in value["blockers"])
        ):
            return False
        source_revision = value["source_revision"]
        specification_digest = value["specification_digest"]
        if (
            len(source_revision) != 40
            or any(character not in "0123456789abcdef" for character in source_revision)
            or len(specification_digest) != 71
            or not specification_digest.startswith("sha256:")
            or any(
                character not in "0123456789abcdef"
                for character in specification_digest[7:]
            )
        ):
            return False
        completed_ids: list[str] = []
        for index, item in enumerate(completed):
            if (
                not isinstance(item, dict)
                or set(item)
                != {
                    "stage_id",
                    "outputs",
                    "plan_digest",
                    "manual_acknowledgement",
                }
                or not isinstance(item.get("stage_id"), str)
                or not isinstance(item.get("outputs"), list)
                or not isinstance(item.get("plan_digest"), (str, type(None)))
                or not isinstance(item.get("manual_acknowledgement"), str)
            ):
                return False
            if item["plan_digest"] is not None and (
                len(item["plan_digest"]) != 71
                or not item["plan_digest"].startswith("sha256:")
                or any(
                    character not in "0123456789abcdef"
                    for character in item["plan_digest"][7:]
                )
            ):
                return False
            expected_stage = _DEPLOYMENT_STAGES[index]
            expected_outputs = tuple(str(name) for name in expected_stage["produces"])
            outputs = item["outputs"]
            if any(
                not isinstance(output, dict)
                or set(output) != {"name", "value"}
                or not isinstance(output.get("name"), str)
                or not isinstance(output.get("value"), str)
                for output in outputs
            ):
                return False
            if tuple(output["name"] for output in outputs) != expected_outputs:
                return False
            expected_acknowledgement = {
                "external-dns": "provider-verified",
                "provider-console": "operator-attested",
            }.get(str(expected_stage["manual_checkpoint"]), "not-required")
            if item["manual_acknowledgement"] != expected_acknowledgement:
                return False
            completed_ids.append(str(item["stage_id"]))
        if completed_ids != list(_STAGE_IDS[: len(completed_ids)]):
            return False
        expected_active_stage = (
            _STAGE_IDS[len(completed_ids)]
            if len(completed_ids) < len(_STAGE_IDS)
            else None
        )
        return (
            value["active_stage"] == expected_active_stage
            and (value["status"] == "succeeded")
            == (expected_active_stage is None)
            and (value["status"] not in {"running", "succeeded"} or not value["blockers"])
        )

    def _store_progress(self, progress: dict[str, Any]) -> str:
        environment = str(progress["environment"])
        if not self._valid_progress(progress, environment):
            raise ValueError("generated invalid deployment progress")
        if validate_lifecycle_material(progress):
            raise ValueError("generated deployment progress contains prohibited material")
        contents = _canonical_bytes(progress) + b"\n"
        self._adapters.filesystem.write_state(
            self._progress_path(environment),
            contents,
            replace=True,
        )
        if progress["status"] in _REPLACEABLE_PROGRESS:
            self._adapters.filesystem.write_state(
                self._terminal_progress_path(
                    environment,
                    str(progress["specification_digest"]),
                ),
                contents,
                replace=True,
            )
        return _digest(progress)

    def _conflicting_progress(
        self,
        environment: str,
        specification_digest: str,
    ) -> dict[str, Any] | None:
        progress = self._load_progress(environment)
        if (
            progress is not None
            and progress.get("specification_digest") != specification_digest
            and progress.get("status") not in _REPLACEABLE_PROGRESS
        ):
            return progress
        return None

    def _report_active_operation_conflict(
        self,
        environment: str,
        progress: dict[str, Any],
        *,
        requested_revision: str,
        requested_digest: str,
    ) -> None:
        completed = progress["completed"]
        last_closed_stage = completed[-1]["stage_id"] if completed else "none"
        authority = self._source_authority
        try:
            specification = self._load_specification(
                environment,
                str(progress["specification_digest"]),
            )
            authority = str(specification["source"]["authority"])
        except (KeyError, TypeError, ValueError):
            pass
        self._adapters.terminal.write(
            "\n".join(
                (
                    "Active deployment conflict:",
                    f"  environment: {environment}",
                    f"  source authority: {authority}",
                    f"  source revision: {progress['source_revision']}",
                    f"  specification digest: {progress['specification_digest']}",
                    f"  status: {progress['status']}",
                    f"  last closed stage: {last_closed_stage}",
                    f"  active stage: {progress['active_stage']}",
                    f"  requested source revision: {requested_revision}",
                    f"  requested specification digest: {requested_digest}",
                    "Close only the private active operation before preparing new intent:",
                    "  make platform-cancel "
                    f"ENVIRONMENT={environment} SOURCE_AUTHORITY={authority}",
                    "Cancellation does not change Terraform state or cloud resources.",
                )
            )
        )

    @staticmethod
    def _new_progress(
        environment: str,
        source_revision: str,
        specification_digest: str,
    ) -> dict[str, Any]:
        return {
            "progress_version": 1,
            "environment": environment,
            "operation": "deploy",
            "source_revision": source_revision,
            "specification_digest": specification_digest,
            "status": "running",
            "completed": [],
            "active_stage": "preflight",
            "blockers": [],
        }

    @staticmethod
    def _closed_outputs(
        progress: dict[str, Any],
    ) -> tuple[set[str], dict[tuple[str, str], str]]:
        closed: set[str] = set()
        outputs: dict[tuple[str, str], str] = {}
        for completed in progress["completed"]:
            stage_id = str(completed["stage_id"])
            closed.add(stage_id)
            for output in completed["outputs"]:
                outputs[(stage_id, str(output["name"]))] = str(output["value"])
        return closed, outputs

    @staticmethod
    def _stage_inputs(
        stage: dict[str, Any],
        outputs: dict[tuple[str, str], str],
    ) -> tuple[tuple[str, str], ...]:
        resolved: list[tuple[str, str]] = []
        for producer, output_name in stage["consumes"]:
            key = (str(producer), str(output_name))
            if key not in outputs:
                raise ValueError(
                    f"closed stage output is unavailable: {producer}/{output_name}"
                )
            resolved.append((f"{producer}.{output_name}", outputs[key]))
        return tuple(resolved)

    @staticmethod
    def _completed_stage(
        stage: dict[str, Any],
        result: StageExecution,
    ) -> dict[str, Any] | None:
        expected = tuple(str(item) for item in stage["produces"])
        actual = tuple(name for name, _ in result.outputs)
        outputs = [{"name": name, "value": value} for name, value in result.outputs]
        if (
            actual != expected
            or len(set(actual)) != len(actual)
            or validate_lifecycle_material(outputs)
        ):
            return None
        return {
            "stage_id": stage["stage_id"],
            "outputs": outputs,
            "plan_digest": result.plan_digest,
            "manual_acknowledgement": result.manual_acknowledgement,
        }

    def _blocked_execution(
        self,
        environment: str,
        blockers: tuple[str, ...],
    ) -> ExecutionResult:
        self._report_blockers(blockers)
        return ExecutionResult("blocked", None, None, self.status(environment), blockers)

    def status(self, environment: str) -> StatusResult:
        """Read source/profile binding and private progress without mutation."""

        profile, profile_digest = self._load_profile(environment)
        profile_blockers = tuple(profile.get("blockers", ()))
        empty = {
            "environment": environment,
            "profile_digest": profile_digest,
            "source_authority": None,
            "source_revision": None,
            "checkout_source_authority": self._source_authority,
            "checkout_source_revision": None,
            "recorded_deployment_source_authority": None,
            "recorded_deployment_source_revision": None,
            "active_runtime_source_revision": None,
            "source_diagnostics": [],
            "specification_digest": None,
            "progress_digest": None,
            "last_closed_stage": None,
            "qualification_status": "not-run",
        }
        if profile.get("lifecycle_state") != "enabled":
            value = {
                **empty,
                "lifecycle_state": "blocked",
                "blockers": list(profile_blockers),
            }
            return StatusResult(value, profile_blockers)

        specification_digest = self._current_specification_digest(environment)
        progress = self._load_progress(environment)
        if specification_digest is None or progress is None:
            return StatusResult({**empty, "lifecycle_state": "absent", "blockers": []})

        specification = self._load_specification(environment, specification_digest)
        if progress["specification_digest"] != specification_digest:
            if progress["status"] not in _REPLACEABLE_PROGRESS:
                raise ValueError("active deployment progress conflicts with current specification")
            return StatusResult({**empty, "lifecycle_state": "absent", "blockers": []})

        source = specification["source"]
        git = self._adapters.git.inspect()
        source_diagnostics = self._source_blockers(git, environment)
        if source["authority"] != self._source_authority:
            source_diagnostics.append("CHECKOUT_AUTHORITY_DIFFERS_FROM_DEPLOYMENT")
        if git.revision != source["revision"]:
            source_diagnostics.append("CHECKOUT_DIFFERS_FROM_DEPLOYMENT")
        active_runtime_source_revision = None
        if self._active_source_reader is not None:
            try:
                active_runtime_source_revision = (
                    self._active_source_reader.active_platform_source_revision(
                        environment
                    )
                )
            except Exception:
                source_diagnostics.append("ACTIVE_RUNTIME_SOURCE_UNAVAILABLE")
        if (
            active_runtime_source_revision is not None
            and git.revision != active_runtime_source_revision
        ):
            source_diagnostics.append("CHECKOUT_DIFFERS_FROM_ACTIVE_RUNTIME")
        if (
            active_runtime_source_revision is not None
            and source["revision"] != active_runtime_source_revision
        ):
            source_diagnostics.append("DEPLOYMENT_DIFFERS_FROM_ACTIVE_RUNTIME")
        conflicts = []
        if specification["profile_digest"] != profile_digest:
            conflicts.append("PROFILE_DIGEST_MISMATCH")
        ordered_conflicts = tuple(sorted(set(conflicts)))
        state = {
            "cancelled": "cancelled",
            "failed": "failed",
            "running": "deploying",
            "succeeded": "deployed",
            "waiting": "waiting",
        }[str(progress["status"])]
        completed = progress["completed"]
        value = {
            "environment": environment,
            "profile_digest": profile_digest,
            "source_authority": source["authority"],
            "source_revision": source["revision"],
            "checkout_source_authority": self._source_authority,
            "checkout_source_revision": git.revision,
            "recorded_deployment_source_authority": source["authority"],
            "recorded_deployment_source_revision": source["revision"],
            "active_runtime_source_revision": active_runtime_source_revision,
            "source_diagnostics": sorted(set(source_diagnostics)),
            "specification_digest": specification_digest,
            "progress_digest": _digest(progress),
            "lifecycle_state": state,
            "last_closed_stage": (
                str(completed[-1]["stage_id"]) if completed else None
            ),
            "blockers": list(ordered_conflicts),
            "qualification_status": "unqualified" if state == "deployed" else "not-run",
        }
        return StatusResult(value, ordered_conflicts)

    def execute(
        self,
        environment: str,
        specification_digest: str,
    ) -> ExecutionResult:
        """Execute or resume the fixed workflow for the approved preparation."""

        _, profile_digest = self._load_profile(environment)
        if self._current_specification_digest(environment) != specification_digest:
            return self._blocked_execution(environment, ("SPECIFICATION_NOT_CURRENT",))
        specification = self._load_specification(environment, specification_digest)
        source = specification["source"]
        source_revision = str(source["revision"])
        git = self._adapters.git.inspect()
        blockers = self._source_blockers(git, environment)
        if source["authority"] != self._source_authority:
            blockers.append("SOURCE_AUTHORITY_MISMATCH")
        if git.revision != source_revision:
            blockers.append("SOURCE_REVISION_MISMATCH")
        if specification["profile_digest"] != profile_digest:
            blockers.append("PROFILE_DIGEST_MISMATCH")
        if not self._approved(
            environment,
            specification_digest,
            profile_digest=profile_digest,
            source_revision=source_revision,
        ):
            blockers.append("SPECIFICATION_NOT_APPROVED")
        if self._adapters.executor is None:
            blockers.extend(
                self._adapters.execution_blockers
                or ("EXECUTION_ADAPTER_UNAVAILABLE",)
            )
        if blockers:
            return self._blocked_execution(environment, tuple(sorted(set(blockers))))

        progress = self._load_progress(environment)
        if progress is None or (
            progress["specification_digest"] != specification_digest
            and progress["status"] in _REPLACEABLE_PROGRESS
        ):
            progress = self._new_progress(environment, source_revision, specification_digest)
            progress_digest = self._store_progress(progress)
        elif progress["specification_digest"] != specification_digest:
            return self._blocked_execution(environment, ("ACTIVE_OPERATION_CONFLICT",))
        elif progress["status"] == "succeeded":
            return ExecutionResult(
                "unchanged", progress, _digest(progress), self.status(environment)
            )
        elif progress["status"] == "cancelled":
            return ExecutionResult(
                "cancelled", progress, _digest(progress), self.status(environment)
            )
        else:
            progress = {**progress, "status": "running", "blockers": []}
            progress_digest = self._store_progress(progress)

        assert self._adapters.executor is not None
        closed, outputs = self._closed_outputs(progress)
        announced_operator_stages: set[int] = set()
        for index, stage_template in enumerate(_DEPLOYMENT_STAGES):
            stage = dict(stage_template)
            stage_id = str(stage["stage_id"])
            if stage_id in closed:
                continue
            operator_stage, operator_title = _OPERATOR_STAGE_PRESENTATION[stage_id]
            if operator_stage not in announced_operator_stages:
                self._adapters.terminal.write(
                    f"▸ Stage {operator_stage}/{_OPERATOR_STAGE_COUNT} · "
                    f"{operator_title}"
                )
                announced_operator_stages.add(operator_stage)
            inputs = self._stage_inputs(stage, outputs)
            context_stage = {
                **stage,
                "consumes": [
                    {"stage_id": producer, "output_name": name}
                    for producer, name in stage["consumes"]
                ],
            }
            try:
                result = self._adapters.executor.execute(
                    StageContext(
                        environment=environment,
                        source_revision=source_revision,
                        specification_digest=specification_digest,
                        stage=MappingProxyType(context_stage),
                        inputs=inputs,
                    )
                )
            except OperatorInterrupted:
                self._adapters.terminal.write(
                    f"Interrupted before stage {stage_id} closed; safe to resume."
                )
                return ExecutionResult(
                    "interrupted", progress, progress_digest, self.status(environment)
                )

            completed_stage = (
                self._completed_stage(stage, result)
                if result.outcome == "succeeded"
                else None
            )
            blocker: str | None = None
            if result.outcome == "succeeded" and completed_stage is None:
                observed_outputs = [
                    {"name": name, "value": value}
                    for name, value in result.outputs
                ]
                blocker = (
                    "PROHIBITED_STAGE_OUTPUT"
                    if validate_lifecycle_material(observed_outputs)
                    else "STAGE_RESULT_INVALID"
                )

            if blocker is not None:
                progress = {
                    **progress,
                    "status": "failed",
                    "active_stage": stage_id,
                    "blockers": [blocker],
                }
            elif result.outcome == "succeeded":
                assert completed_stage is not None
                completed = [*progress["completed"], completed_stage]
                next_stage = (
                    str(_DEPLOYMENT_STAGES[index + 1]["stage_id"])
                    if index + 1 < len(_DEPLOYMENT_STAGES)
                    else None
                )
                progress = {
                    **progress,
                    "status": "succeeded" if next_stage is None else "running",
                    "completed": completed,
                    "active_stage": next_stage,
                    "blockers": [],
                }
            else:
                progress = {
                    **progress,
                    "status": result.outcome,
                    "active_stage": stage_id,
                    "blockers": list(result.blockers),
                }

            progress_digest = self._store_progress(progress)
            displayed = "failed" if blocker is not None else result.outcome
            self._adapters.terminal.write(
                f"Stage {stage_id} closed with outcome {displayed}."
            )
            if blocker is not None:
                return ExecutionResult(
                    "failed",
                    progress,
                    progress_digest,
                    self.status(environment),
                    (blocker,),
                )
            if result.outcome != "succeeded":
                return ExecutionResult(
                    result.outcome,
                    progress,
                    progress_digest,
                    self.status(environment),
                    result.blockers,
                )
            closed.add(stage_id)
            for name, value in result.outputs:
                outputs[(stage_id, name)] = value

        return ExecutionResult(
            "succeeded", progress, progress_digest, self.status(environment)
        )

    def current_approved_specification(
        self,
        environment: str,
    ) -> PrepareResult | None:
        """Reuse current approved preparation only after fresh read-only checks."""

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
                "blocked", False, False, None, None, ("SPECIFICATION_READBACK_FAILED",)
            )
        git = self._adapters.git.inspect()
        discoveries = self._discoveries(profile)
        blockers = self._freshness_blockers(environment, profile, git, discoveries)
        if blockers:
            return PrepareResult("blocked", False, False, None, digest, blockers)
        source = specification["source"]
        source_revision = str(source["revision"])
        if (
            specification["environment"] != environment
            or specification["profile_digest"] != profile_digest
            or source["authority"] != self._source_authority
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
            conflict = self._conflicting_progress(environment, digest)
        except ValueError:
            return PrepareResult(
                "blocked", False, False, None, digest, ("PROGRESS_READBACK_FAILED",)
            )
        if conflict:
            self._report_active_operation_conflict(
                environment,
                conflict,
                requested_revision=git.revision,
                requested_digest=digest,
            )
            return PrepareResult(
                "blocked", False, False, None, digest, ("ACTIVE_OPERATION_CONFLICT",)
            )
        self._adapters.terminal.write(
            f"Reusing current approved specification {digest} for {environment}."
        )
        return PrepareResult("unchanged", True, True, specification, digest, ())

    def preflight(
        self,
        environment: str,
        *,
        mode: str = "operational",
    ) -> PreflightResult:
        """Check readiness without writing, approving, planning, or mutating."""

        if mode not in {"development", "operational"}:
            raise ValueError(f"unsupported preflight mode {mode!r}")
        _, _, git, discoveries, all_blockers = self._readiness(
            environment,
            report_blockers=False,
        )
        source_blockers = (
            tuple(sorted(set(self._source_blockers(git, environment))))
            if git is not None
            else ()
        )
        source_codes = set(source_blockers)
        readiness_blockers = tuple(
            blocker for blocker in all_blockers if blocker not in source_codes
        )
        operational_ready = not all_blockers
        if mode == "development":
            blockers = readiness_blockers
            self._report_development_source_diagnostics(source_blockers)
            self._report_blockers(readiness_blockers)
        else:
            blockers = all_blockers
            self._report_blockers(all_blockers)
        if blockers:
            return PreflightResult(
                "blocked",
                False,
                blockers,
                source_blockers,
                operational_ready,
            )
        assert git is not None
        self._report_verified_session(discoveries)
        if mode == "development" and source_blockers:
            self._adapters.terminal.write(
                f"Development preflight ready for {environment}; source remains "
                "operationally unadmitted."
            )
        else:
            self._adapters.terminal.write(f"Preflight ready for {environment}.")
        return PreflightResult(
            "ready",
            True,
            (),
            source_blockers,
            operational_ready,
        )

    def prepare(self, environment: str) -> PrepareResult:
        """Discover readiness, display one operation fingerprint, and approve it."""

        _, profile_digest, git, discoveries, blockers = self._readiness(environment)
        if blockers:
            return PrepareResult("blocked", False, False, None, None, blockers)
        assert git is not None
        self._report_verified_session(discoveries)
        specification = self._specification(environment, profile_digest, git.revision)
        digest = _digest(specification)
        conflict = self._conflicting_progress(environment, digest)
        if conflict:
            self._report_active_operation_conflict(
                environment,
                conflict,
                requested_revision=git.revision,
                requested_digest=digest,
            )
            return PrepareResult(
                "blocked", False, False, None, None, ("ACTIVE_OPERATION_CONFLICT",)
            )
        self._store_specification(environment, specification, digest)
        if self._approved(
            environment,
            digest,
            profile_digest=profile_digest,
            source_revision=git.revision,
        ):
            self._adapters.terminal.write(
                f"Unchanged approved specification {digest} for {environment}."
            )
            return PrepareResult("unchanged", True, True, specification, digest, ())
        self._adapters.terminal.write(
            f"Deployment specification {digest} for {environment}."
        )
        approved = self._adapters.terminal.confirm(
            f"Approve exact deployment specification {digest}? [y/N] "
        )
        if not approved:
            return PrepareResult("cancelled", True, False, specification, digest, ())
        self._store_approval(environment, profile_digest, git.revision, digest)
        return PrepareResult("prepared", True, True, specification, digest, ())

    def cancel(self, environment: str) -> _CancellationResult:
        """Close one private active deployment without any external operation."""

        self._load_profile(environment)
        try:
            progress = self._load_progress(environment)
            current_digest = self._current_specification_digest(environment)
        except ValueError:
            blockers = ("PROGRESS_READBACK_FAILED",)
            self._report_blockers(blockers)
            return _CancellationResult("blocked", None, None, blockers)
        if progress is None or progress["status"] in _REPLACEABLE_PROGRESS:
            if progress is None:
                self._adapters.terminal.write(
                    f"No deployment operation exists for {environment}; nothing to cancel."
                )
                return _CancellationResult("unchanged", None, None, ())
            self._adapters.terminal.write(
                f"Deployment operation {progress['specification_digest']} is already "
                f"{progress['status']}; nothing to cancel."
            )
            return _CancellationResult(
                "unchanged",
                progress,
                _digest(progress),
                (),
            )

        specification_digest = str(progress["specification_digest"])
        if current_digest != specification_digest:
            blockers = ("PROGRESS_READBACK_FAILED",)
            self._report_blockers(blockers)
            return _CancellationResult("blocked", progress, _digest(progress), blockers)
        try:
            specification = self._load_specification(
                environment,
                specification_digest,
            )
        except ValueError:
            blockers = ("SPECIFICATION_READBACK_FAILED",)
            self._report_blockers(blockers)
            return _CancellationResult("blocked", progress, _digest(progress), blockers)
        source = specification["source"]
        authority = str(source["authority"])
        if authority != self._source_authority:
            self._adapters.terminal.write(
                "Active deployment source authority does not match this invocation. "
                f"Rerun with SOURCE_AUTHORITY={authority}."
            )
            blockers = ("SOURCE_AUTHORITY_MISMATCH",)
            return _CancellationResult("blocked", progress, _digest(progress), blockers)

        completed = progress["completed"]
        last_closed_stage = completed[-1]["stage_id"] if completed else "none"
        self._adapters.terminal.write(
            "\n".join(
                (
                    "Cancel private deployment operation:",
                    f"  environment: {environment}",
                    f"  source authority: {authority}",
                    f"  source revision: {progress['source_revision']}",
                    f"  specification digest: {specification_digest}",
                    f"  status: {progress['status']}",
                    f"  last closed stage: {last_closed_stage}",
                    f"  active stage: {progress['active_stage']}",
                    "This closes only private resume state. Terraform state and cloud "
                    "resources remain unchanged.",
                )
            )
        )
        confirmed = self._adapters.terminal.confirm(
            f"Cancel private deployment operation {specification_digest}? [y/N] "
        )
        if not confirmed:
            return _CancellationResult(
                "declined",
                progress,
                _digest(progress),
                ("CANCELLATION_DECLINED",),
            )

        cancelled = {**progress, "status": "cancelled", "blockers": []}
        progress_digest = self._store_progress(cancelled)
        self._adapters.terminal.write(
            f"Cancelled private deployment operation {specification_digest}. "
            "Terraform state and cloud resources were not changed."
        )
        return _CancellationResult("cancelled", cancelled, progress_digest, ())
