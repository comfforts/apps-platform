"""Deep AP-M9 lifecycle orchestration behind the small operator interface."""

from __future__ import annotations

import json
from typing import Any

from contracts.lifecycle import (
    canonical_lifecycle_bytes,
    lifecycle_digest,
    load_lifecycle_document,
    validate_lifecycle_document,
)
from infrastructure.operator._interfaces import (
    DiscoverySnapshot,
    GitSnapshot,
    OperatorAdapters,
    PrepareResult,
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
            "stage_id": "bootstrap",
            "actions": ["create", "read"],
            "resource_types": ["backend-bucket", "operation-identity"],
            "consumes": [
                {"stage_id": "preflight", "output_name": "preflight-attestation"}
            ],
            "produces": ["backend-reference", "identity-reference"],
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
                {"stage_id": "bootstrap", "output_name": "identity-reference"},
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

    def __init__(self, adapters: OperatorAdapters) -> None:
        self._adapters = adapters

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

    @staticmethod
    def _source_blockers(snapshot: GitSnapshot) -> list[str]:
        blockers: list[str] = []
        if snapshot.repository != "comfforts/apps-platform":
            blockers.append("REPOSITORY_MISMATCH")
        if not snapshot.clean:
            blockers.append("SOURCE_NOT_CLEAN")
        if snapshot.branch != "main":
            blockers.append("SOURCE_NOT_MAIN")
        if not (
            snapshot.revision
            == snapshot.main_revision
            == snapshot.origin_main_revision
        ):
            blockers.append("SOURCE_NOT_CURRENT")
        return blockers

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

    @staticmethod
    def _specification(
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

    def _approved(self, environment: str, digest: str) -> bool:
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

    def prepare(self, environment: str) -> PrepareResult:
        """Read source and bounded discoveries, then request exact digest approval."""

        profile, profile_digest = self._load_profile(environment)
        profile_blockers = tuple(profile.get("blockers", ()))
        if profile.get("lifecycle_state") != "enabled":
            return PrepareResult(
                "blocked", False, False, None, None, profile_blockers
            )

        git = self._adapters.git.inspect()
        discoveries = (
            self._adapters.github.inspect(profile),
            self._adapters.gcp.inspect(profile),
            self._adapters.terraform.inspect(),
            self._adapters.dns.inspect(profile),
        )
        blockers = self._source_blockers(git)
        blockers.extend(
            blocker for discovery in discoveries for blocker in discovery.blockers
        )
        blockers.extend(self._discovery_conflicts(profile, discoveries))
        ordered_blockers = tuple(sorted(set(blockers)))
        if ordered_blockers:
            return PrepareResult(
                "blocked", False, False, None, None, ordered_blockers
            )

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
