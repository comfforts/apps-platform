"""Exact-plan stage execution for the AP-M9 interactive deployment lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import stat
from pathlib import Path
from typing import Any, Protocol

from contracts.lifecycle import validate_lifecycle_material
from infrastructure.backend import (
    EnvironmentUnavailableError,
    PhasePlanRequest,
    TerraformPlanCommands,
    prepare_phase_plan,
)
from infrastructure.operator._interfaces import (
    OperatorTerminal,
    StageContext,
    StageExecution,
    Waiter,
)


@dataclass(frozen=True, slots=True)
class TerraformPlanArtifact:
    """Private saved plan plus its redacted, policy-checkable observation."""

    saved_plan_path: Path
    observation: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExactTerraformPlan:
    """One saved plan bound to its file digest and canonical policy digest."""

    saved_plan_path: Path
    saved_plan_digest: str
    policy_digest: str
    canonical_summary: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TerraformReadbackRequest:
    """Exact stage and phase context for state plus provider reconciliation."""

    stage_id: str
    phase: str
    environment: str
    source_revision: str
    specification_digest: str
    inputs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class TerraformReadback:
    """Closed non-secret outputs or fail-closed readback blockers."""

    matched: bool
    outputs: tuple[tuple[str, str], ...] = ()
    blockers: tuple[str, ...] = ()
    ready: bool = True


@dataclass(frozen=True, slots=True)
class StageReadback:
    """Provider-verified output for a non-Terraform stage."""

    matched: bool
    outputs: tuple[tuple[str, str], ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """Canonical non-secret proposal for one non-Terraform mutation."""

    action: str
    summary: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExactAction:
    """A proposed external action bound to its approved stage and digest."""

    action: str
    digest: str
    summary: dict[str, object]


@dataclass(frozen=True, slots=True)
class ManualCheckpoint:
    """Exact non-secret values displayed for one human provider action."""

    checkpoint: str
    instructions: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CheckpointVerification:
    """One bounded readback attempt following a human checkpoint."""

    outcome: str
    outputs: tuple[tuple[str, str], ...] = ()
    acknowledgement: str = "not-required"
    blockers: tuple[str, ...] = ()


class DeploymentCommandError(RuntimeError):
    """A safe blocker code returned by the external command boundary."""

    def __init__(
        self,
        code: str,
        *,
        diagnostic: dict[str, str | int] | None = None,
    ) -> None:
        super().__init__(code)
        self.diagnostic = dict(diagnostic or {})


@dataclass(frozen=True, slots=True)
class _ImmediateWaiter:
    def wait(self, seconds: int) -> None:
        del seconds


class DeploymentCommands(Protocol):
    """Only seam allowed to create, apply, or read back a Terraform plan."""

    def create_terraform_plan(
        self,
        context: StageContext,
        request: PhasePlanRequest,
    ) -> TerraformPlanArtifact: ...

    def apply_terraform_plan(
        self,
        request: PhasePlanRequest,
        plan: ExactTerraformPlan,
    ) -> None: ...

    def signing_key_ring_recovery_identity(
        self,
        context: StageContext,
        request: PhasePlanRequest,
    ) -> str: ...

    def clear_signing_key_ring_taint(
        self,
        context: StageContext,
        request: PhasePlanRequest,
        identity: str,
    ) -> None: ...

    def readback_terraform(
        self,
        request: TerraformReadbackRequest,
    ) -> TerraformReadback: ...

    def read_stage(self, context: StageContext) -> StageReadback: ...

    def prepare_action(self, context: StageContext) -> ActionProposal: ...

    def execute_action(self, context: StageContext, action: ExactAction) -> None: ...

    def readback_action(self, context: StageContext) -> StageReadback: ...

    def prepare_manual_checkpoint(self, context: StageContext) -> ManualCheckpoint: ...

    def verify_manual_checkpoint(
        self,
        context: StageContext,
        attempt: int,
        supplied_inputs: tuple[tuple[str, str], ...],
    ) -> CheckpointVerification: ...


class CheckpointPageLauncher(Protocol):
    """Open one reviewed provider-console page for an interactive checkpoint."""

    def open(self, url: str) -> bool: ...


@dataclass
class _ArtifactObserver(TerraformPlanCommands):
    commands: DeploymentCommands
    context: StageContext
    request: PhasePlanRequest | None = None
    artifact: TerraformPlanArtifact | None = None

    def observe_plan(self, request: PhasePlanRequest) -> dict[str, object]:
        self.request = request
        self.artifact = self.commands.create_terraform_plan(self.context, request)
        return self.artifact.observation


_TERRAFORM_PHASES = {
    "bootstrap": "bootstrap",
    "foundation": "platform-foundation",
    "shared-edge": "shared-edge",
    "tls-readiness": "shared-edge",
    "fixture-public": "fixture-public",
    "fixture-authenticated": "fixture-authenticated",
    "fixture-restricted": "fixture-restricted",
}
_READ_ONLY_STAGES = {"preflight", "readback"}
_ACTION_STAGES = {"bootstrap-services", "generation-publish", "image-publish"}
_MANUAL_STAGES = {"oauth-configuration", "external-dns"}
_POLLING = {
    "external-dns": (12, 10),
    "tls-readiness": (30, 10),
}
_TERRAFORM_PLAN_GUIDANCE = {
    "TERRAFORM_BACKEND_ACCESS_DENIED": (
        "the operator session cannot read the selected Terraform backend"
    ),
    "TERRAFORM_CONFIGURATION_INVALID": (
        "the rendered Terraform configuration or variables are invalid"
    ),
    "TERRAFORM_OPERATOR_AUTHENTICATION_FAILED": (
        "the operator credentials are unavailable, expired, or require reauthentication"
    ),
    "TERRAFORM_PLAN_FAILED_UNKNOWN": (
        "Terraform returned a diagnostic outside the safe classifier"
    ),
    "TERRAFORM_PROVIDER_PERMISSION_DENIED": (
        "the provider denied a read required to produce the plan"
    ),
    "TERRAFORM_PROVIDER_PLUGIN_FAILED": (
        "Terraform could not start or negotiate with the pinned provider plugin"
    ),
    "TERRAFORM_PROVIDER_QUOTA_EXCEEDED": (
        "the provider rejected planning because a quota was exhausted"
    ),
    "TERRAFORM_STATE_LOCKED": (
        "another operation or stale lock currently owns the selected state lineage"
    ),
    "TERRAFORM_STATE_READ_FAILED": (
        "Terraform could not read the selected state lineage"
    ),
}
_TERRAFORM_APPLY_GUIDANCE = {
    "TERRAFORM_APPLY_AUTHENTICATION_FAILED": (
        "the operator credentials are unavailable, expired, or require reauthentication"
    ),
    "TERRAFORM_APPLY_CONFLICT": (
        "the provider reported a conflicting concurrent or existing operation"
    ),
    "TERRAFORM_APPLY_DEPENDENCY_PROPAGATION_PENDING": (
        "a newly created provider dependency is not readable yet; wait briefly and replan"
    ),
    "TERRAFORM_APPLY_FAILED_UNKNOWN": (
        "Terraform returned an apply diagnostic outside the safe classifier"
    ),
    "TERRAFORM_APPLY_IAM_CONFLICT": (
        "the provider reported concurrent IAM policy changes; replan after they settle"
    ),
    "TERRAFORM_APPLY_IDENTITY_PROPAGATION_PENDING": (
        "a newly created service identity is not readable yet; wait briefly and replan"
    ),
    "TERRAFORM_APPLY_INVALID_ARGUMENT": (
        "the provider rejected the rendered resource request as invalid"
    ),
    "TERRAFORM_APPLY_PERMISSION_DENIED": (
        "the provider denied a mutation required by the reviewed plan"
    ),
    "TERRAFORM_APPLY_PLUGIN_FAILED": (
        "Terraform could not continue through the pinned provider plugin"
    ),
    "TERRAFORM_APPLY_PROVIDER_INCONSISTENT_RESULT": (
        "the provider returned a resource value inconsistent with the reviewed plan"
    ),
    "TERRAFORM_APPLY_QUOTA_EXCEEDED": (
        "the provider rejected the mutation because a quota was exhausted"
    ),
    "TERRAFORM_APPLY_SERVICE_DISABLED": (
        "the named provider API is disabled in the quota project"
    ),
    "TERRAFORM_APPLY_STATE_LOCKED": (
        "another operation or stale lock currently owns the selected state lineage"
    ),
}


class DeploymentExecutor:
    """Execute exact Terraform stages; later adapters add the non-Terraform stages."""

    def __init__(
        self,
        working_root: Path,
        terminal: OperatorTerminal,
        commands: DeploymentCommands,
        *,
        waiter: Waiter | None = None,
        checkpoint_page_launcher: CheckpointPageLauncher | None = None,
    ) -> None:
        self._working_root = working_root.resolve()
        self._terminal = terminal
        self._commands = commands
        self._waiter = waiter or _ImmediateWaiter()
        self._checkpoint_page_launcher = checkpoint_page_launcher
        self._seen_saved_plans: set[Path] = set()
        if not self._working_root.is_dir():
            raise ValueError("deployment working root must already exist")
        if stat.S_IMODE(self._working_root.stat().st_mode) & 0o077:
            raise ValueError("deployment working root must be private")

    @staticmethod
    def _failure(*blockers: str) -> StageExecution:
        return StageExecution(
            outcome="failed",
            blockers=tuple(sorted(set(blockers))),
        )

    def _terraform_plan_failure(
        self,
        error: str | DeploymentCommandError,
    ) -> StageExecution:
        blocker = str(error)
        if isinstance(error, DeploymentCommandError) and error.diagnostic:
            value: dict[str, object] = {
                "blocker": blocker,
                **error.diagnostic,
            }
            if self._safe_canonical(value) is not None:
                self._terminal.write(self._pretty_json("TERRAFORM PLAN ERROR", value))
            if "diagnostic_path" in error.diagnostic:
                self._terminal.write(
                    "Private Terraform diagnostics may contain sensitive provider "
                    "data. Inspect locally; do not commit or share them unredacted."
                )
        guidance = _TERRAFORM_PLAN_GUIDANCE.get(
            blocker,
            "inspect the named Terraform planning boundary before retrying",
        )
        self._terminal.write(f"Terraform plan blocker {blocker}: {guidance}.")
        return self._failure(blocker)

    def _terraform_apply_failure(
        self,
        error: DeploymentCommandError,
    ) -> StageExecution:
        blocker = str(error)
        if error.diagnostic:
            value: dict[str, object] = {
                "blocker": blocker,
                **error.diagnostic,
            }
            if self._safe_canonical(value) is not None:
                self._terminal.write(self._pretty_json("TERRAFORM APPLY ERROR", value))
            if "diagnostic_path" in error.diagnostic:
                self._terminal.write(
                    "Private Terraform diagnostics may contain sensitive provider "
                    "data. Inspect locally; do not commit or share them unredacted."
                )
        guidance = _TERRAFORM_APPLY_GUIDANCE.get(
            blocker,
            "inspect the named Terraform apply boundary before replanning",
        )
        self._terminal.write(f"Terraform apply blocker {blocker}: {guidance}.")
        return self._failure(blocker)

    def _bind_saved_plan(
        self,
        artifact: TerraformPlanArtifact,
        policy_digest: str,
        summary: dict[str, Any],
    ) -> ExactTerraformPlan | StageExecution:
        path = artifact.saved_plan_path
        if path.is_symlink():
            return self._failure("SAVED_PLAN_PATH_INVALID")
        resolved = path.resolve()
        if (
            resolved == self._working_root
            or self._working_root not in resolved.parents
            or not resolved.is_file()
        ):
            return self._failure("SAVED_PLAN_PATH_INVALID")
        if stat.S_IMODE(resolved.stat().st_mode) & 0o077:
            return self._failure("SAVED_PLAN_NOT_PRIVATE")
        if resolved in self._seen_saved_plans:
            return self._failure("SAVED_PLAN_NOT_FRESH")
        self._seen_saved_plans.add(resolved)
        digest = f"sha256:{hashlib.sha256(resolved.read_bytes()).hexdigest()}"
        return ExactTerraformPlan(
            saved_plan_path=resolved,
            saved_plan_digest=digest,
            policy_digest=policy_digest,
            canonical_summary=summary,
        )

    @staticmethod
    def _requires_apply(summary: dict[str, Any]) -> bool:
        changes = summary.get("changes")
        assert isinstance(changes, list)
        return any(
            isinstance(change, dict)
            and isinstance(change.get("actions"), list)
            and any(
                action in {"create", "delete", "update"}
                for action in change["actions"]
            )
            for change in changes
        )

    @staticmethod
    def _expected_outputs(context: StageContext) -> tuple[str, ...]:
        produces = context.stage.get("produces")
        if not isinstance(produces, list):
            return ()
        return tuple(str(value) for value in produces)

    @staticmethod
    def _readback_result(
        context: StageContext,
        readback: StageReadback,
        *,
        plan_digest: str | None = None,
        acknowledgement: str = "not-required",
    ) -> StageExecution:
        if not readback.matched:
            return StageExecution(
                outcome="failed",
                plan_digest=plan_digest,
                blockers=readback.blockers or ("STAGE_READBACK_MISMATCH",),
            )
        expected = DeploymentExecutor._expected_outputs(context)
        if tuple(name for name, _ in readback.outputs) != expected:
            return StageExecution(
                outcome="failed",
                plan_digest=plan_digest,
                blockers=("STAGE_READBACK_OUTPUT_MISMATCH",),
            )
        return StageExecution(
            outcome="succeeded",
            outputs=readback.outputs,
            plan_digest=plan_digest,
            manual_acknowledgement=acknowledgement,
        )

    @staticmethod
    def _bound_digest(context: StageContext, value: object) -> str:
        bound = {
            "environment": context.environment,
            "inputs": [{"name": name, "value": item} for name, item in context.inputs],
            "source_revision": context.source_revision,
            "specification_digest": context.specification_digest,
            "stage": dict(context.stage),
            "value": value,
        }
        contents = json.dumps(
            bound,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(contents).hexdigest()}"

    @staticmethod
    def _safe_canonical(value: object) -> str | None:
        if validate_lifecycle_material(value):
            return None
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @staticmethod
    def _pretty_json(label: str, value: object) -> str:
        return label + "\n" + json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )

    @staticmethod
    def _manual_checkpoint_guidance(
        stage_id: str,
        instructions: dict[str, str],
    ) -> tuple[tuple[str, str], ...] | None:
        if stage_id == "oauth-configuration":
            required = {
                "application_name",
                "application_type",
                "authorized_domain",
                "authorized_origin",
                "branding_console_url",
                "clients_console_url",
                "homepage_url",
                "project_id",
                "redirect_uri",
                "oauth_store_console_url",
                "oauth_store_target",
                "support_email",
            }
            if not required.issubset(instructions):
                return None
            branding = "\n".join(
                (
                    "OAUTH STEP 1 OF 3: Configure application branding",
                    "",
                    f"The browser page is for project `{instructions['project_id']}`.",
                    "If branding is not configured, enter these exact values. If it "
                    "already exists, verify the values instead of creating another "
                    "brand:",
                    f"- Application name: {instructions['application_name']}",
                    f"- User support email: {instructions['support_email']}",
                    f"- Application homepage: {instructions['homepage_url']}",
                    "- Authorized domain, if requested: "
                    f"{instructions['authorized_domain']}",
                    "",
                    "Save the branding configuration, return to this terminal, and "
                    "press Enter. Keep the deployment running.",
                )
            )
            client = "\n".join(
                (
                    "OAUTH STEP 2 OF 3: Create the Web OAuth client",
                    "",
                    "On Google Auth Platform > Clients, create a client with these "
                    "exact values. If this deployment is resuming and an exact "
                    "matching client already exists, open and verify it instead of "
                    "creating a duplicate:",
                    f"- Application type: {instructions['application_type']}",
                    f"- Name: {instructions['application_name']}",
                    "- Authorized JavaScript origin: "
                    f"{instructions['authorized_origin']}",
                    f"- Authorized redirect URI: {instructions['redirect_uri']}",
                    "",
                    "Create or save the client. Keep both the client ID and client "
                    "secret available temporarily. Do not download or commit a JSON "
                    "credential file. Return here and press Enter; the next terminal "
                    "prompt accepts only the client ID.",
                )
            )
            provider_guidance = "\n".join(
                (
                    "OAUTH STEP 3 OF 3: Store the OAuth client secret",
                    "",
                    "The browser page opens the existing Secret Manager target:",
                    f"{instructions['oauth_store_target']}",
                    "Do not create a second secret.",
                    "",
                    "Inspect its versions before changing anything. This deployment "
                    "requires exactly one ENABLED version:",
                    "- If none is enabled, add one version containing only the OAuth "
                    "client secret.",
                    "- If one is enabled, confirm it is the intended secret for this "
                    "exact OAuth client.",
                    "- If more than one is enabled, stop and resolve stale versions "
                    "before continuing.",
                    "",
                    "Never enter the client secret in this terminal, source control, "
                    "chat, or a configuration file. After exactly one intended "
                    "version is enabled, return here and press Enter for provider "
                    "readback.",
                )
            )
            return (
                (branding, instructions["branding_console_url"]),
                (client, instructions["clients_console_url"]),
                (
                    provider_guidance,
                    instructions["oauth_store_console_url"],
                ),
            )
        if stage_id == "external-dns":
            required = {
                "address",
                "dns_zone",
                "hostname",
                "provider",
                "record_name",
                "record_type",
                "ttl_seconds",
            }
            if not required.issubset(instructions):
                return None
            guidance = "\n".join(
                (
                    "MANUAL ACTION REQUIRED: Create the external DNS record",
                    "",
                    "Keep this deployment running while you complete these steps:",
                    "",
                    f"1. Open {instructions['provider']} DNS management for "
                    f"`{instructions['dns_zone']}`.",
                    "2. Create this exact record:",
                    f"   - Type: {instructions['record_type']}",
                    f"   - Host/name: {instructions['record_name']}",
                    f"   - Full hostname: {instructions['hostname']}",
                    f"   - Value/address: {instructions['address']}",
                    f"   - TTL: {instructions['ttl_seconds']} seconds",
                    "3. Save only this record. Do not modify another hostname, "
                    "record, certificate, or application resource.",
                    "4. Return here and press Enter. The deployment will verify "
                    "authoritative and recursive DNS and wait for readable "
                    "propagation.",
                )
            )
            return ((guidance, ""),)
        return None

    def _show_checkpoint_page(self, url: str) -> None:
        if not url:
            return
        self._terminal.write(f"CONSOLE PAGE\n{url}")
        if self._checkpoint_page_launcher is None:
            self._terminal.write(
                "Open the console page above in a browser before continuing."
            )
            return
        try:
            opened = self._checkpoint_page_launcher.open(url)
        except (OSError, RuntimeError, ValueError):
            opened = False
        if opened:
            self._terminal.write("Opened the console page in the system browser.")
        else:
            self._terminal.write(
                "The console page could not be opened automatically. Open the URL "
                "above in a browser before continuing."
            )

    def _execute_read_only(self, context: StageContext) -> StageExecution:
        try:
            readback = self._commands.read_stage(context)
        except DeploymentCommandError as error:
            return self._failure(str(error))
        return self._readback_result(context, readback)

    def _execute_action(self, context: StageContext, stage_id: str) -> StageExecution:
        try:
            proposal = self._commands.prepare_action(context)
        except DeploymentCommandError as error:
            return self._failure(str(error))
        value = {"action": proposal.action, "summary": proposal.summary}
        canonical = self._safe_canonical(value)
        if canonical is None:
            return self._failure("PROHIBITED_ACTION_MATERIAL")
        digest = self._bound_digest(context, value)
        exact = ExactAction(proposal.action, digest, proposal.summary)
        self._terminal.write(self._pretty_json("ACTION", value))
        self._terminal.write(f"ACTION_DIGEST {digest}")
        if not self._terminal.confirm(
            f"Execute the reviewed {stage_id} action {digest}? [y/N] "
        ):
            return StageExecution(
                outcome="cancelled",
                plan_digest=digest,
                blockers=("ACTION_NOT_CONFIRMED",),
            )
        try:
            self._commands.execute_action(context, exact)
            readback = self._commands.readback_action(context)
        except DeploymentCommandError as error:
            return StageExecution(
                outcome="failed",
                plan_digest=digest,
                blockers=(str(error),),
            )
        if stage_id == "bootstrap-services" and readback.matched:
            services = proposal.summary.get("services")
            if not isinstance(services, list) or any(
                not isinstance(service, str) for service in services
            ):
                return self._failure("BOOTSTRAP_SERVICE_READBACK_INVALID")
            summary = {
                "stage": stage_id,
                "services": [
                    {"name": service, "state": "enabled"} for service in services
                ],
            }
            readback_summary = self._safe_canonical(summary)
            if readback_summary is None:
                return self._failure("PROHIBITED_READBACK_MATERIAL")
            self._terminal.write(self._pretty_json("READBACK", summary))
        return self._readback_result(context, readback, plan_digest=digest)

    def _execute_manual(self, context: StageContext, stage_id: str) -> StageExecution:
        try:
            checkpoint = self._commands.prepare_manual_checkpoint(context)
        except DeploymentCommandError as error:
            return self._failure(str(error))
        expected_checkpoint = context.stage.get("manual_checkpoint")
        if checkpoint.checkpoint != expected_checkpoint:
            return self._failure("MANUAL_CHECKPOINT_SCOPE_MISMATCH")
        if len({name for name, _ in checkpoint.instructions}) != len(
            checkpoint.instructions
        ):
            return self._failure("MANUAL_CHECKPOINT_INVALID")
        instruction_values = dict(checkpoint.instructions)
        operator_steps = self._manual_checkpoint_guidance(stage_id, instruction_values)
        if operator_steps is None:
            return self._failure("MANUAL_CHECKPOINT_INVALID")
        value = {
            "checkpoint": checkpoint.checkpoint,
            "instructions": [
                {"name": name, "value": item}
                for name, item in checkpoint.instructions
            ],
        }
        canonical = self._safe_canonical(value)
        if canonical is None:
            return self._failure("PROHIBITED_CHECKPOINT_MATERIAL")
        digest = self._bound_digest(context, value)
        self._terminal.write(self._pretty_json("CHECKPOINT", value))
        self._terminal.write(f"CHECKPOINT_DIGEST {digest}")
        supplied_inputs: tuple[tuple[str, str], ...] = ()
        for step_index, (guidance, console_url) in enumerate(operator_steps, start=1):
            self._terminal.write(guidance)
            self._show_checkpoint_page(console_url)
            self._terminal.pause(
                f"Complete step {step_index} of {len(operator_steps)} for "
                f"{checkpoint.checkpoint!r}, then press Enter to continue: "
            )
            if stage_id == "oauth-configuration" and step_index == 2:
                client_id = self._terminal.ask(
                    "Paste the OAuth client ID (never the client secret): "
                ).strip()
                if not client_id:
                    return StageExecution(
                        outcome="failed",
                        plan_digest=digest,
                        blockers=("OAUTH_CLIENT_ID_REQUIRED",),
                    )
                supplied_inputs = (("oauth-client-id", client_id),)

        max_attempts, interval = _POLLING.get(stage_id, (1, 0))
        latest_blockers: tuple[str, ...] = ()
        for attempt in range(1, max_attempts + 1):
            try:
                verification = self._commands.verify_manual_checkpoint(
                    context,
                    attempt,
                    supplied_inputs,
                )
            except DeploymentCommandError as error:
                return StageExecution(
                    outcome="failed",
                    plan_digest=digest,
                    blockers=(str(error),),
                )
            latest_blockers = verification.blockers
            if verification.outcome == "failed":
                return StageExecution(
                    outcome="failed",
                    plan_digest=digest,
                    blockers=latest_blockers or ("CHECKPOINT_READBACK_MISMATCH",),
                )
            if verification.outcome == "succeeded":
                if (
                    stage_id == "external-dns"
                    and verification.acknowledgement != "provider-verified"
                ):
                    return StageExecution(
                        outcome="failed",
                        plan_digest=digest,
                        blockers=("DNS_PROVIDER_VERIFICATION_REQUIRED",),
                    )
                return self._readback_result(
                    context,
                    StageReadback(True, verification.outputs),
                    plan_digest=digest,
                    acknowledgement=verification.acknowledgement,
                )
            if verification.outcome != "waiting":
                return StageExecution(
                    outcome="failed",
                    plan_digest=digest,
                    blockers=("CHECKPOINT_OUTCOME_INVALID",),
                )
            if attempt < max_attempts:
                self._waiter.wait(interval)
        return StageExecution(
            outcome="waiting",
            plan_digest=digest,
            blockers=tuple(
                sorted({*latest_blockers, "CHECKPOINT_POLL_EXHAUSTED"})
            ),
        )

    def _execute_terraform(
        self,
        context: StageContext,
        stage_id: str,
        phase: str,
    ) -> StageExecution:
        observer = _ArtifactObserver(self._commands, context)
        actions = context.stage.get("actions")
        destructive = isinstance(actions, list) and "delete" in actions
        try:
            evaluated = prepare_phase_plan(
                context.environment,
                phase,
                context.source_revision,
                self._working_root,
                observer,
                destructive=destructive,
            )
        except EnvironmentUnavailableError as error:
            return self._failure(str(error))
        except DeploymentCommandError as error:
            if (
                str(error) != "TERRAFORM_PROTECTED_SIGNING_KEY_RING_TAINTED"
                or stage_id != "foundation"
                or observer.request is None
            ):
                return self._terraform_plan_failure(error)
            try:
                identity = self._commands.signing_key_ring_recovery_identity(
                    context,
                    observer.request,
                )
            except DeploymentCommandError as recovery_error:
                return self._failure(str(recovery_error))
            self._terminal.write(
                "RECOVERY Terraform state marks the existing protected signing "
                "key ring as tainted."
            )
            self._terminal.write(f"RECOVERY_LIVE_IDENTITY {identity}")
            self._terminal.write(
                "RECOVERY_EFFECT Clear only the Terraform taint marker; the live "
                "key ring is not replaced or changed."
            )
            if not self._terminal.confirm(
                "Clear only its Terraform taint marker and generate a fresh "
                "foundation plan? [y/N] "
            ):
                return StageExecution(
                    outcome="cancelled",
                    blockers=(
                        "TERRAFORM_PROTECTED_RESOURCE_RECOVERY_NOT_CONFIRMED",
                    ),
                )
            try:
                self._commands.clear_signing_key_ring_taint(
                    context,
                    observer.request,
                    identity,
                )
            except DeploymentCommandError as recovery_error:
                return self._failure(str(recovery_error))
            observer = _ArtifactObserver(self._commands, context)
            try:
                evaluated = prepare_phase_plan(
                    context.environment,
                    phase,
                    context.source_revision,
                    self._working_root,
                    observer,
                    destructive=destructive,
                )
            except (EnvironmentUnavailableError, DeploymentCommandError) as retry_error:
                return self._terraform_plan_failure(retry_error)

        if not evaluated.accepted:
            return self._failure(*(violation.code for violation in evaluated.violations))
        if (
            observer.request is None
            or observer.artifact is None
            or evaluated.plan_digest is None
            or evaluated.canonical_summary is None
        ):
            return self._failure("PLAN_BINDING_INCOMPLETE")

        exact_plan = self._bind_saved_plan(
            observer.artifact,
            evaluated.plan_digest,
            evaluated.canonical_summary,
        )
        if isinstance(exact_plan, StageExecution):
            return exact_plan

        self._terminal.write(
            self._pretty_json("PLAN", exact_plan.canonical_summary)
        )
        self._terminal.write(f"PLAN_DIGEST {exact_plan.policy_digest}")

        if self._requires_apply(exact_plan.canonical_summary):
            if not self._terminal.confirm(
                f"Apply the reviewed {stage_id} plan "
                f"{exact_plan.policy_digest}? [y/N] "
            ):
                return StageExecution(
                    outcome="cancelled",
                    plan_digest=exact_plan.policy_digest,
                    blockers=("PLAN_NOT_CONFIRMED",),
                )
            try:
                self._commands.apply_terraform_plan(observer.request, exact_plan)
            except DeploymentCommandError as error:
                failed = self._terraform_apply_failure(error)
                return StageExecution(
                    outcome=failed.outcome,
                    plan_digest=exact_plan.policy_digest,
                    blockers=failed.blockers,
                )

        request = TerraformReadbackRequest(
            stage_id=stage_id,
            phase=phase,
            environment=context.environment,
            source_revision=context.source_revision,
            specification_digest=context.specification_digest,
            inputs=context.inputs,
        )
        max_attempts, interval = _POLLING.get(stage_id, (1, 0))
        readback: TerraformReadback | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                readback = self._commands.readback_terraform(request)
            except DeploymentCommandError as error:
                return StageExecution(
                    outcome="failed",
                    plan_digest=exact_plan.policy_digest,
                    blockers=(str(error),),
                )
            if not readback.matched:
                blockers = readback.blockers or ("TERRAFORM_READBACK_MISMATCH",)
                return StageExecution(
                    outcome="failed",
                    plan_digest=exact_plan.policy_digest,
                    blockers=tuple(sorted(set(blockers))),
                )
            if readback.ready:
                break
            if attempt < max_attempts:
                self._waiter.wait(interval)
        assert readback is not None
        if not readback.ready:
            return StageExecution(
                outcome="waiting",
                plan_digest=exact_plan.policy_digest,
                blockers=tuple(
                    sorted({*readback.blockers, "TERRAFORM_READINESS_PENDING"})
                ),
            )
        output_names = tuple(name for name, _ in readback.outputs)
        if output_names != self._expected_outputs(context):
            return StageExecution(
                outcome="failed",
                plan_digest=exact_plan.policy_digest,
                blockers=("TERRAFORM_READBACK_OUTPUT_MISMATCH",),
            )
        return StageExecution(
            outcome="succeeded",
            outputs=readback.outputs,
            plan_digest=exact_plan.policy_digest,
        )

    def execute(self, context: StageContext) -> StageExecution:
        stage_id = str(context.stage.get("stage_id", ""))
        if context.environment == "production":
            return self._failure("OWNERSHIP_TRANSFER_REQUIRED")
        if stage_id in _READ_ONLY_STAGES:
            return self._execute_read_only(context)
        if stage_id in _ACTION_STAGES:
            return self._execute_action(context, stage_id)
        if stage_id in _MANUAL_STAGES:
            return self._execute_manual(context, stage_id)
        try:
            phase = _TERRAFORM_PHASES[stage_id]
        except KeyError:
            return self._failure("DEPLOYMENT_STAGE_UNAVAILABLE")
        return self._execute_terraform(context, stage_id, phase)


__all__ = (
    "ActionProposal",
    "CheckpointVerification",
    "DeploymentCommandError",
    "DeploymentCommands",
    "DeploymentExecutor",
    "ExactAction",
    "ExactTerraformPlan",
    "ManualCheckpoint",
    "StageReadback",
    "TerraformPlanArtifact",
    "TerraformReadback",
    "TerraformReadbackRequest",
)
