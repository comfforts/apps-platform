"""Exact local readback and execution adapters for safe platform destruction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
from typing import Any, Protocol

from contracts.lifecycle import load_lifecycle_document
from infrastructure.backend import (
    PhasePlanRequest,
    backend_declarations,
    prepare_phase_plan,
    render_backend_declaration,
)
from infrastructure.operator._interfaces import StageContext, StageExecution, StatusResult
from infrastructure.operator.deployment import TerraformPlanArtifact
from infrastructure.operator.destruction import (
    DESTRUCTIBLE_PLATFORM_RESOURCES,
    RETAINED_PLATFORM_RESOURCES,
    DestructionSnapshot,
)
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_deployment import (
    DeploymentConfigurationRenderer,
    RenderedTerraformInput,
)


_RETAINED_STATE_PREFIXES = (
    "module.platform_foundation.google_project_service.platform",
    "module.platform_foundation.google_storage_bucket.configuration",
    "module.platform_foundation.google_kms_key_ring.assertion_signing",
    "module.platform_foundation.google_kms_crypto_key.assertion_signing",
    "module.platform_controls.google_storage_bucket.evidence",
    "module.platform_controls.google_storage_bucket_iam_member.evidence_owner_reader",
    "module.platform_controls.google_logging_project_exclusion.edge_from_default",
)
_OWNED_STATE_PREFIXES = (
    "module.platform_foundation.",
    "module.platform_controls.",
    "module.shared_edge[0].",
)
_FULL_STATE_MARKERS = (
    "module.platform_foundation.google_storage_bucket.configuration",
    "module.platform_foundation.google_firestore_database.sessions[0]",
    "module.platform_controls.google_storage_bucket.evidence",
    "module.platform_controls.google_artifact_registry_repository.qualification_images[0]",
    "module.shared_edge[0].google_cloud_run_v2_service.edge",
    "module.shared_edge[0].google_compute_global_address.edge",
)


class DestructionCommandError(RuntimeError):
    """Coarse safe blocker that never includes provider or state payloads."""


class DestructionTerraform(Protocol):
    def create_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        variable_file: Path,
        *,
        bootstrap_remote: bool = False,
        destroy: bool = False,
    ) -> TerraformPlanArtifact: ...

    def apply_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        saved_plan: Path,
    ) -> None: ...

    def platform_state_addresses(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> tuple[str, ...]: ...


class DestructionProvider(Protocol):
    def read_current(self, environment: str): ...  # type: ignore[no-untyped-def]

    def shared_edge_ingress(self, environment: str) -> str: ...

    def shared_edge_exists(self, environment: str) -> bool: ...


class DestructionDns(Protocol):
    def absent(self): ...  # type: ignore[no-untyped-def]


class DestructionTerminal(Protocol):
    def confirm(self, prompt: str) -> bool: ...

    def pause(self, prompt: str) -> None: ...

    def write(self, message: str) -> None: ...


class DestructionWaiter(Protocol):
    def wait(self, seconds: int) -> None: ...


class DestructionStatusReader(Protocol):
    def status(self, environment: str) -> StatusResult: ...


class DestructionGenerationReader(Protocol):
    def current(
        self,
        environment: str,
    ) -> RegistrationGenerationProposal | None: ...


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _attestation(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _phase_request(
    environment: str,
    phase: str,
    source_revision: str,
    working_root: Path,
) -> PhasePlanRequest:
    matches = tuple(
        declaration
        for declaration in backend_declarations(environment)
        if declaration.phase == phase
    )
    if len(matches) != 1:
        raise DestructionCommandError("DESTRUCTION_TERRAFORM_PHASE_INVALID")
    declaration = matches[0]
    rendered = render_backend_declaration(
        declaration,
        working_root,
        f"{phase}/backend.tf",
    )
    return PhasePlanRequest(
        environment=environment,
        source_revision=source_revision,
        phase=phase,
        terraform_root=declaration.terraform_root,
        state_owner=declaration.state_owner,
        owner_id=declaration.owner_id,
        project_id=declaration.project_id,
        backend_path=rendered.path,
        backend_digest=rendered.digest,
        backend_bucket=declaration.bucket,
        backend_prefix=declaration.prefix,
    )


def _journal(filesystem: LocalFilesystem, environment: str) -> dict[str, Any]:
    pointer_payload = filesystem.read_state(
        f"environments/{environment}/current-journal.v1.json"
    )
    if pointer_payload is None:
        raise DestructionCommandError("DESTRUCTION_JOURNAL_UNAVAILABLE")
    try:
        pointer = json.loads(pointer_payload)
        digest = pointer["journal_digest"]
        revision = pointer["journal_revision"]
        specification = pointer["specification_digest"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DestructionCommandError("DESTRUCTION_JOURNAL_INVALID") from error
    if not isinstance(digest, str) or not isinstance(revision, int) or not isinstance(
        specification, str
    ):
        raise DestructionCommandError("DESTRUCTION_JOURNAL_INVALID")
    path = (
        f"environments/{environment}/journals/{specification[7:]}/"
        f"{revision:08d}.v1.json"
    )
    loaded = load_lifecycle_document(
        filesystem.state_path(path),
        "execution-journal",
    )
    if loaded.value is None or loaded.violations or loaded.digest != digest:
        raise DestructionCommandError("DESTRUCTION_JOURNAL_INVALID")
    return loaded.value


def deployed_outputs(
    filesystem: LocalFilesystem,
    environment: str,
) -> dict[str, str]:
    """Read only closed non-secret outputs from the current deployment journal."""

    entries = _journal(filesystem, environment).get("entries")
    if not isinstance(entries, list):
        raise DestructionCommandError("DESTRUCTION_JOURNAL_INVALID")
    outputs: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("outcome") != "succeeded":
            continue
        values = entry.get("outputs")
        if not isinstance(values, list):
            raise DestructionCommandError("DESTRUCTION_JOURNAL_INVALID")
        for item in values:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("value"), str)
            ):
                raise DestructionCommandError("DESTRUCTION_JOURNAL_INVALID")
            outputs[item["name"]] = item["value"]
    required = {
        "foundation-reference",
        "oauth-client-id",
        "oauth-secret-version",
        "registration-generation-reference",
        "reserved-address",
        "shared-edge-image-digest",
    }
    if not required <= set(outputs):
        raise DestructionCommandError("DESTRUCTION_DEPLOYMENT_BINDING_INCOMPLETE")
    return outputs


class LocalDestructionStateReader:
    """Join local authority, provider facts, and address-only Platform State."""

    def __init__(
        self,
        filesystem: LocalFilesystem,
        status_reader: DestructionStatusReader,
        generations: DestructionGenerationReader,
        provider: DestructionProvider,
        terraform: DestructionTerraform,
        renderer: DeploymentConfigurationRenderer,
        working_root: Path,
    ) -> None:
        self._filesystem = filesystem
        self._status_reader = status_reader
        self._generations = generations
        self._provider = provider
        self._terraform = terraform
        self._renderer = renderer
        self._working_root = working_root

    def _qualification_digest(
        self,
        environment: str,
        status: dict[str, Any],
        generation_digest: str,
    ) -> str:
        source_authority = status.get("source_authority")
        if source_authority not in {"accepted", "candidate"}:
            raise DestructionCommandError("QUALIFICATION_EVIDENCE_INVALID")
        qualification_root = (
            "qualification"
            if source_authority == "accepted"
            else "qualification/candidates"
        )
        expected_outcome = (
            "qualified" if source_authority == "accepted" else "candidate-qualified"
        )
        payload = self._filesystem.read_state(
            f"environments/{environment}/{qualification_root}/current-evidence.v1.json"
        )
        if payload is None:
            raise DestructionCommandError("QUALIFICATION_EVIDENCE_UNAVAILABLE")
        try:
            pointer = json.loads(payload)
            digest = pointer["evidence_digest"]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DestructionCommandError("QUALIFICATION_EVIDENCE_INVALID") from error
        if not isinstance(digest, str) or pointer.get("outcome") != expected_outcome:
            raise DestructionCommandError("QUALIFICATION_EVIDENCE_INVALID")
        loaded = load_lifecycle_document(
            self._filesystem.state_path(
                f"environments/{environment}/{qualification_root}/evidence/"
                f"{digest[7:]}.v1.json"
            ),
            "qualification-evidence",
        )
        if loaded.value is None or loaded.violations or loaded.digest != digest:
            raise DestructionCommandError("QUALIFICATION_EVIDENCE_INVALID")
        evidence = loaded.value
        bindings = {
            "environment": environment,
            "source_authority": source_authority,
            "source_revision": status.get("source_revision"),
            "profile_digest": status.get("profile_digest"),
            "specification_digest": status.get("specification_digest"),
            "deployment_journal_digest": status.get("journal_digest"),
            "registration_generation_digest": generation_digest,
            "verdict": "qualified",
        }
        if any(evidence.get(name) != value for name, value in bindings.items()):
            raise DestructionCommandError("QUALIFICATION_EVIDENCE_MISMATCH")
        return digest

    def _has_partial_progress(self, environment: str) -> bool:
        root = self._filesystem.state_path(
            f"environments/{environment}/destruction"
        )
        if not root.exists():
            return False
        if root.is_symlink() or not root.is_dir():
            raise DestructionCommandError("DESTRUCTION_PROGRESS_INVALID")
        return any(
            path.is_file()
            for path in root.glob("*/progress/*.v1.json")
        )

    def read_current(self, environment: str) -> DestructionSnapshot:
        if environment != "staging":
            raise DestructionCommandError("PRODUCTION_DESTRUCTION_UNAVAILABLE")
        result = self._status_reader.status(environment)
        status = result.environment_status
        if result.conflicts or status.get("lifecycle_state") != "deployed":
            raise DestructionCommandError("ENVIRONMENT_NOT_DEPLOYED")
        required = (
            "source_authority",
            "source_revision",
            "profile_digest",
            "specification_digest",
            "journal_digest",
        )
        if any(not isinstance(status.get(name), str) for name in required):
            raise DestructionCommandError("ENVIRONMENT_STATUS_INVALID")
        generation = self._generations.current(environment)
        if generation is None:
            raise DestructionCommandError("REGISTRATION_GENERATION_UNAVAILABLE")
        registrations = generation.registration_set.get("registrations")
        if not isinstance(registrations, list):
            raise DestructionCommandError("REGISTRATION_GENERATION_INVALID")
        active: list[str] = []
        for registration in registrations:
            if not isinstance(registration, dict):
                raise DestructionCommandError("REGISTRATION_GENERATION_INVALID")
            if registration.get("lifecycle") == "active":
                application_id = registration.get("application_id")
                if not isinstance(application_id, str):
                    raise DestructionCommandError("REGISTRATION_GENERATION_INVALID")
                active.append(application_id)
        partial = self._has_partial_progress(environment)
        if not partial:
            provider = self._provider.read_current(environment)
            if provider.active_generation_digest != generation.generation_digest:
                raise DestructionCommandError("DESTRUCTION_PROVIDER_MISMATCH")

        outputs = deployed_outputs(self._filesystem, environment)
        request = _phase_request(
            environment,
            "platform-foundation",
            str(status["source_revision"]),
            self._working_root,
        )
        rendered = self._renderer.render_transition(request, "none", outputs)
        addresses = self._terraform.platform_state_addresses(
            request,
            rendered.terraform_root,
        )
        owned = bool(addresses) and all(
            address.startswith(_OWNED_STATE_PREFIXES) for address in addresses
        )
        if not partial:
            owned = owned and all(marker in addresses for marker in _FULL_STATE_MARKERS)
        evidence_digest = self._qualification_digest(
            environment,
            status,
            generation.generation_digest,
        )
        return DestructionSnapshot(
            environment=environment,
            lifecycle_state="destroying" if partial else "deployed",
            source_revision=str(status["source_revision"]),
            profile_digest=str(status["profile_digest"]),
            deployed_specification_digest=str(status["specification_digest"]),
            deployment_journal_digest=str(status["journal_digest"]),
            registration_generation_digest=generation.generation_digest,
            qualification_evidence_digest=evidence_digest,
            active_application_ids=tuple(sorted(active)),
            platform_resource_types=(
                DESTRUCTIBLE_PLATFORM_RESOURCES if owned else ()
            ),
            retained_resource_types=(RETAINED_PLATFORM_RESOURCES if owned else ()),
            ownership_matches=owned,
            source_authority=str(status["source_authority"]),
        )


class _PlanObserver:
    def __init__(
        self,
        renderer: DeploymentConfigurationRenderer,
        terraform: DestructionTerraform,
        mode: str,
        outputs: dict[str, str],
    ) -> None:
        self._renderer = renderer
        self._terraform = terraform
        self._mode = mode
        self._outputs = outputs
        self.request: PhasePlanRequest | None = None
        self.rendered: RenderedTerraformInput | None = None
        self.artifact: TerraformPlanArtifact | None = None

    def observe_plan(self, request: PhasePlanRequest) -> dict[str, object]:
        self.request = request
        self.rendered = self._renderer.render_transition(
            request,
            self._mode,
            self._outputs,
        )
        self.artifact = self._terraform.create_plan(
            request,
            self.rendered.terraform_root,
            self.rendered.variable_file,
        )
        return self.artifact.observation


class LocalDestructionExecutor:
    """Execute exact transitions without ever issuing a blind Terraform destroy."""

    def __init__(
        self,
        filesystem: LocalFilesystem,
        working_root: Path,
        renderer: DeploymentConfigurationRenderer,
        terraform: DestructionTerraform,
        provider: DestructionProvider,
        dns: DestructionDns,
        terminal: DestructionTerminal,
        waiter: DestructionWaiter,
    ) -> None:
        self._filesystem = filesystem
        self._working_root = working_root.resolve()
        self._renderer = renderer
        self._terraform = terraform
        self._provider = provider
        self._dns = dns
        self._terminal = terminal
        self._waiter = waiter
        self._seen_plans: set[Path] = set()

    @staticmethod
    def _failed(*blockers: str) -> StageExecution:
        return StageExecution("failed", blockers=tuple(sorted(set(blockers))))

    @staticmethod
    def _output(context: StageContext, value: object) -> StageExecution:
        produces = context.stage.get("produces")
        if not isinstance(produces, list) or len(produces) != 1:
            return LocalDestructionExecutor._failed("DESTRUCTION_OUTPUT_INVALID")
        return StageExecution(
            "succeeded",
            ((str(produces[0]), _attestation(value)),),
        )

    @staticmethod
    def _requires_apply(summary: dict[str, Any]) -> bool:
        changes = summary.get("changes")
        return isinstance(changes, list) and any(
            isinstance(change, dict)
            and any(
                action in {"create", "delete", "update"}
                for action in change.get("actions", [])
            )
            for change in changes
        )

    def _plan(
        self,
        context: StageContext,
        phase: str,
        mode: str,
        *,
        destructive: bool,
    ) -> tuple[str, PhasePlanRequest, RenderedTerraformInput]:
        outputs = deployed_outputs(self._filesystem, context.environment)
        observer = _PlanObserver(self._renderer, self._terraform, mode, outputs)
        result = prepare_phase_plan(
            context.environment,
            phase,
            context.source_revision,
            self._working_root,
            observer,
            destructive=destructive,
        )
        if not result.accepted:
            codes = sorted({violation.code for violation in result.violations})
            raise DestructionCommandError(codes[0] if codes else "PLAN_REJECTED")
        if (
            result.plan_digest is None
            or result.canonical_summary is None
            or observer.request is None
            or observer.rendered is None
            or observer.artifact is None
        ):
            raise DestructionCommandError("PLAN_BINDING_INCOMPLETE")
        path = observer.artifact.saved_plan_path
        resolved = path.resolve()
        if (
            path.is_symlink()
            or resolved == self._working_root
            or self._working_root not in resolved.parents
            or not resolved.is_file()
            or stat.S_IMODE(resolved.stat().st_mode) & 0o077
            or resolved in self._seen_plans
        ):
            raise DestructionCommandError("SAVED_PLAN_INVALID")
        self._seen_plans.add(resolved)
        summary = json.dumps(
            result.canonical_summary,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        self._terminal.write(f"PLAN {summary}")
        self._terminal.write(f"PLAN_DIGEST {result.plan_digest}")
        if self._requires_apply(result.canonical_summary):
            if not self._terminal.confirm(
                f"Apply the reviewed {mode} plan {result.plan_digest}? [y/N] "
            ):
                raise DestructionCommandError("PLAN_NOT_CONFIRMED")
            self._terraform.apply_plan(
                observer.request,
                observer.rendered.terraform_root,
                resolved,
            )
        return result.plan_digest, observer.request, observer.rendered

    def _state(
        self,
        request: PhasePlanRequest,
        rendered: RenderedTerraformInput,
    ) -> tuple[str, ...]:
        return self._terraform.platform_state_addresses(
            request,
            rendered.terraform_root,
        )

    def execute(self, context: StageContext) -> StageExecution:
        stage_id = str(context.stage.get("stage_id", ""))
        if context.environment != "staging":
            return self._failed("PRODUCTION_DESTRUCTION_UNAVAILABLE")
        try:
            if stage_id == "destruction-preflight":
                return self._output(
                    context,
                    {
                        "environment": context.environment,
                        "source_revision": context.source_revision,
                        "specification_digest": context.specification_digest,
                    },
                )
            if stage_id == "traffic-disable":
                digest, _, _ = self._plan(
                    context,
                    "shared-edge",
                    "shared-edge-unlock",
                    destructive=False,
                )
                if self._provider.shared_edge_ingress(context.environment) != "internal":
                    return self._failed("TRAFFIC_DISABLE_READBACK_MISMATCH")
                return self._output(context, {"plan_digest": digest, "traffic": "disabled"})
            if stage_id == "traffic-drain":
                self._terminal.write("TRAFFIC_DRAIN_SECONDS 30")
                self._waiter.wait(30)
                return self._output(context, {"drain_seconds": 30})
            if stage_id == "external-dns-destroy":
                outputs = deployed_outputs(self._filesystem, context.environment)
                self._terminal.write(
                    "DELETE_DNS_RECORD Squarespace A apps-staging "
                    f"apps-staging.comfforts.com {outputs['reserved-address']}"
                )
                self._terminal.pause(
                    "Delete the displayed Squarespace A record, then Press Enter to verify: "
                )
                for attempt in range(12):
                    readback = self._dns.absent()
                    if readback.ready and readback.attestation is not None:
                        return self._output(
                            context,
                            {"dns_attestation": readback.attestation},
                        )
                    if attempt < 11:
                        self._waiter.wait(10)
                return StageExecution(
                    "waiting",
                    blockers=("DNS_REMOVAL_PROPAGATION_PENDING",),
                )
            if stage_id == "edge-destroy":
                digest, request, rendered = self._plan(
                    context,
                    "shared-edge",
                    "shared-edge-remove",
                    destructive=True,
                )
                addresses = self._state(request, rendered)
                if any(address.startswith("module.shared_edge[0].") for address in addresses):
                    return self._failed("EDGE_DESTRUCTION_READBACK_MISMATCH")
                if self._provider.shared_edge_exists(context.environment):
                    return self._failed("EDGE_DESTRUCTION_READBACK_MISMATCH")
                return self._output(context, {"plan_digest": digest, "edge": "absent"})
            if stage_id == "identity-destroy":
                client_id = deployed_outputs(
                    self._filesystem,
                    context.environment,
                )["oauth-client-id"]
                self._terminal.write(f"DELETE_OAUTH_CLIENT {client_id}")
                self._terminal.pause(
                    "Delete the displayed OAuth client in Google Auth Platform, "
                    "then Press Enter to attest completion: "
                )
                return self._output(
                    context,
                    {"oauth_client_id": client_id, "readback": "operator-attested"},
                )
            if stage_id == "foundation-destroy":
                unlock_digest, _, _ = self._plan(
                    context,
                    "platform-foundation",
                    "platform-unlock",
                    destructive=False,
                )
                destroy_digest, request, rendered = self._plan(
                    context,
                    "platform-foundation",
                    "retained",
                    destructive=True,
                )
                addresses = self._state(request, rendered)
                if not addresses or any(
                    not address.startswith(_RETAINED_STATE_PREFIXES)
                    for address in addresses
                ):
                    return self._failed("FOUNDATION_DESTRUCTION_READBACK_MISMATCH")
                return self._output(
                    context,
                    {
                        "destroy_plan_digest": destroy_digest,
                        "retained_addresses": len(addresses),
                        "unlock_plan_digest": unlock_digest,
                    },
                )
            if stage_id == "destruction-readback":
                outputs = deployed_outputs(self._filesystem, context.environment)
                request = _phase_request(
                    context.environment,
                    "platform-foundation",
                    context.source_revision,
                    self._working_root,
                )
                rendered = self._renderer.render_transition(
                    request,
                    "retained",
                    outputs,
                )
                addresses = self._state(request, rendered)
                if not addresses or any(
                    not address.startswith(_RETAINED_STATE_PREFIXES)
                    for address in addresses
                ):
                    return self._failed("DESTRUCTION_FINAL_READBACK_MISMATCH")
                return self._output(
                    context,
                    {"retained_addresses": len(addresses), "status": "destroyed"},
                )
        except DestructionCommandError as error:
            return self._failed(str(error))
        except Exception:
            return self._failed("DESTRUCTION_COMMAND_FAILED")
        return self._failed("DESTRUCTION_STAGE_UNAVAILABLE")


__all__ = (
    "DestructionCommandError",
    "LocalDestructionExecutor",
    "LocalDestructionStateReader",
    "deployed_outputs",
)
