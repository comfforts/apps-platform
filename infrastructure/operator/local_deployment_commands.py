"""Real staging deployment commands composed behind deterministic adapter seams."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Protocol

from infrastructure.backend import (
    PhasePlanRequest,
    backend_declarations,
    render_backend_declaration,
)
from infrastructure.operator._interfaces import StageContext
from infrastructure.operator.deployment import (
    ActionProposal,
    CheckpointVerification,
    DeploymentCommandError,
    ExactAction,
    ExactTerraformPlan,
    ManualCheckpoint,
    StageReadback,
    TerraformPlanArtifact,
    TerraformReadback,
    TerraformReadbackRequest,
)
from infrastructure.operator.deployment_dns import DnsReadback, DnsReadbackError
from infrastructure.operator.deployment_provider import DeploymentProviderError
from infrastructure.operator.local_deployment import (
    DeploymentConfigurationRenderer,
    InitialGeneration,
    OperatorSessionFacts,
    RenderedTerraformInput,
    initial_generation,
)


_PROJECT_ID = "comfforts-platform-non-prod"
_REGION = "us-west1"
_HOSTNAME = "apps-staging.comfforts.com"
_CONFIGURATION_BUCKET = "comfforts-ap-stg-455651441682-configuration"
_OAUTH_SECRET = f"projects/{_PROJECT_ID}/secrets/app-platform-edge-oauth"
_CLIENT_ID = re.compile(r"[0-9]+-[a-z0-9-]+\.apps\.googleusercontent\.com")
_IPV4 = re.compile(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}")


class DeploymentTerraform(Protocol):
    def create_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        variable_file: Path,
        *,
        bootstrap_remote: bool = False,
    ) -> TerraformPlanArtifact: ...

    def apply_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        saved_plan: Path,
    ) -> None: ...

    def migrate_bootstrap_state(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> None: ...

    def read_output(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        output_name: str,
    ) -> object: ...


class DeploymentProvider(Protocol):
    def enable_bootstrap_services(self) -> None: ...

    def bootstrap_services_ready(self) -> bool: ...

    def bootstrap_backend_ready(self) -> bool: ...

    def publish_initial_generation(self, generation: InitialGeneration) -> int: ...

    def read_initial_generation(self, generation: InitialGeneration) -> int: ...

    def publish_shared_edge_image(self, source_revision: str) -> str: ...

    def read_shared_edge_image(self, source_revision: str) -> str | None: ...

    def active_signing_key_version(self) -> str: ...

    def oauth_secret_version(self) -> str: ...

    def certificate_readback(self): ...


class DeploymentDns(Protocol):
    def read(self, expected_address: str) -> DnsReadback: ...


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _dict(value: object, code: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DeploymentCommandError(code)
    return value


@dataclass(frozen=True, slots=True)
class _RenderedPlan:
    request: PhasePlanRequest
    rendered: RenderedTerraformInput
    initial_bootstrap: bool = False


class LocalDeploymentCommands:
    """Compose exact Terraform, provider, OAuth, DNS, and readback stages."""

    def __init__(
        self,
        renderer: DeploymentConfigurationRenderer,
        terraform: DeploymentTerraform,
        provider: DeploymentProvider,
        dns: DeploymentDns,
        session: OperatorSessionFacts,
    ) -> None:
        self._renderer = renderer
        self._terraform = terraform
        self._provider = provider
        self._dns = dns
        self._session = session
        self._plans_by_stage: dict[str, _RenderedPlan] = {}
        self._plans_by_request: dict[int, _RenderedPlan] = {}

    @staticmethod
    def _stage_id(context: StageContext) -> str:
        return str(context.stage.get("stage_id", ""))

    @staticmethod
    def _inputs(context: StageContext) -> dict[str, str]:
        return dict(context.inputs)

    @staticmethod
    def _provider_error(error: BaseException) -> DeploymentCommandError:
        return DeploymentCommandError(str(error) or "DEPLOYMENT_PROVIDER_FAILED")

    def create_terraform_plan(
        self,
        context: StageContext,
        request: PhasePlanRequest,
    ) -> TerraformPlanArtifact:
        try:
            rendered = self._renderer.render(context, request)
            bootstrap_remote = False
            initial_bootstrap = False
            if request.phase == "bootstrap":
                bootstrap_remote = self._provider.bootstrap_backend_ready()
                initial_bootstrap = not bootstrap_remote
                if initial_bootstrap:
                    contents = request.backend_path.read_bytes()
                    digest = "sha256:" + hashlib.sha256(contents).hexdigest()
                    if digest != request.backend_digest:
                        raise DeploymentCommandError(
                            "TERRAFORM_BACKEND_BINDING_MISMATCH"
                        )
                    request.backend_path.unlink()
            plan = _RenderedPlan(request, rendered, initial_bootstrap)
            stage_id = self._stage_id(context)
            self._plans_by_stage[stage_id] = plan
            self._plans_by_request[id(request)] = plan
            return self._terraform.create_plan(
                request,
                rendered.terraform_root,
                rendered.variable_file,
                bootstrap_remote=bootstrap_remote,
            )
        except DeploymentCommandError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise DeploymentCommandError("TERRAFORM_PLAN_COMMAND_FAILED") from error

    def apply_terraform_plan(
        self,
        request: PhasePlanRequest,
        plan: ExactTerraformPlan,
    ) -> None:
        try:
            rendered_plan = self._plans_by_request[id(request)]
            rendered = rendered_plan.rendered
            self._terraform.apply_plan(
                request,
                rendered.terraform_root,
                plan.saved_plan_path,
            )
            if rendered_plan.initial_bootstrap:
                declaration = next(
                    item
                    for item in backend_declarations(request.environment)
                    if item.phase == "bootstrap"
                )
                restored = render_backend_declaration(
                    declaration,
                    rendered.terraform_root.parent,
                    "bootstrap/backend.tf",
                )
                if (
                    restored.path.resolve() != request.backend_path.resolve()
                    or restored.digest != request.backend_digest
                ):
                    raise DeploymentCommandError(
                        "TERRAFORM_BACKEND_BINDING_MISMATCH"
                    )
                self._terraform.migrate_bootstrap_state(
                    request,
                    rendered.terraform_root,
                )
        except KeyError as error:
            raise DeploymentCommandError("TERRAFORM_PLAN_CONTEXT_MISSING") from error
        except DeploymentCommandError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise DeploymentCommandError("TERRAFORM_APPLY_COMMAND_FAILED") from error

    @staticmethod
    def _bootstrap_reference(value: object) -> str:
        output = _dict(value, "BOOTSTRAP_READBACK_INVALID")
        if (
            output.get("contract_version") != 1
            or output.get("output_kind") != "bootstrap"
            or output.get("environment") != "staging"
            or output.get("project_id") != _PROJECT_ID
            or output.get("region") != _REGION
            or output.get("state_owner") != "platform"
            or output.get("owner_id") != "app-platform"
            or not isinstance(output.get("lineages"), dict)
        ):
            raise DeploymentCommandError("BOOTSTRAP_READBACK_INVALID")
        return _canonical(output)

    def _foundation_references(self, value: object) -> tuple[str, str]:
        output = _dict(value, "FOUNDATION_READBACK_INVALID")
        foundation = output.get("foundation")
        if (
            output.get("contract_version") != 1
            or output.get("output_kind") != "platform-foundation"
            or output.get("environment") != "staging"
            or output.get("project_id") != _PROJECT_ID
            or output.get("region") != _REGION
            or output.get("hostname") != _HOSTNAME
            or not isinstance(foundation, dict)
            or foundation.get("configuration_bucket") != _CONFIGURATION_BUCKET
            or foundation.get("oauth_secret_id") != _OAUTH_SECRET
        ):
            raise DeploymentCommandError("FOUNDATION_READBACK_INVALID")
        try:
            signing_version = self._provider.active_signing_key_version()
        except DeploymentProviderError as error:
            raise self._provider_error(error) from error
        reference = {**output, "signing_key_version": signing_version}
        return _canonical(reference), _OAUTH_SECRET

    @staticmethod
    def _edge_references(value: object, *, tls_enabled: bool) -> tuple[str, str]:
        output = _dict(value, "SHARED_EDGE_READBACK_INVALID")
        edge = output.get("edge")
        if (
            output.get("contract_version") != 1
            or output.get("output_kind") != "shared-edge"
            or output.get("environment") != "staging"
            or output.get("project_id") != _PROJECT_ID
            or output.get("region") != _REGION
            or not isinstance(edge, dict)
            or edge.get("hostname") != _HOSTNAME
            or edge.get("service_name") != "app-platform-edge"
            or edge.get("tls_enabled") is not tls_enabled
            or not isinstance(edge.get("reserved_address"), str)
            or _IPV4.fullmatch(str(edge["reserved_address"])) is None
        ):
            raise DeploymentCommandError("SHARED_EDGE_READBACK_INVALID")
        return _canonical(output), str(edge["reserved_address"])

    def readback_terraform(
        self,
        request: TerraformReadbackRequest,
    ) -> TerraformReadback:
        try:
            planned = self._plans_by_stage[request.stage_id]
        except KeyError:
            return TerraformReadback(False, blockers=("TERRAFORM_PLAN_CONTEXT_MISSING",))
        if (
            planned.request.phase != request.phase
            or planned.request.environment != request.environment
            or planned.request.source_revision != request.source_revision
        ):
            return TerraformReadback(False, blockers=("TERRAFORM_CONTEXT_MISMATCH",))
        try:
            output_name = {
                "bootstrap": "bootstrap_phase_output",
                "foundation": "foundation_phase_output",
                "shared-edge": "shared_edge_phase_output",
                "tls-readiness": "shared_edge_phase_output",
            }[request.stage_id]
            value = self._terraform.read_output(
                planned.request,
                planned.rendered.terraform_root,
                output_name,
            )
            if request.stage_id == "bootstrap":
                return TerraformReadback(
                    True,
                    (("backend-reference", self._bootstrap_reference(value)),),
                )
            if request.stage_id == "foundation":
                foundation, secret = self._foundation_references(value)
                return TerraformReadback(
                    True,
                    (
                        ("foundation-reference", foundation),
                        ("oauth-secret-container", secret),
                    ),
                )
            if request.stage_id == "shared-edge":
                edge, address = self._edge_references(value, tls_enabled=False)
                return TerraformReadback(
                    True,
                    (("edge-reference", edge), ("reserved-address", address)),
                )
            self._edge_references(value, tls_enabled=True)
            certificate = self._provider.certificate_readback()
            return TerraformReadback(
                True,
                (("certificate-reference", certificate.reference),)
                if certificate.ready
                else (),
                blockers=() if certificate.ready else ("CERTIFICATE_READINESS_PENDING",),
                ready=certificate.ready,
            )
        except DeploymentCommandError:
            raise
        except (DeploymentProviderError, OSError, RuntimeError, ValueError) as error:
            raise self._provider_error(error) from error

    def read_stage(self, context: StageContext) -> StageReadback:
        stage_id = self._stage_id(context)
        if stage_id == "preflight":
            return StageReadback(True)
        if stage_id == "readback":
            try:
                certificate = self._provider.certificate_readback()
            except DeploymentProviderError as error:
                raise self._provider_error(error) from error
            if not certificate.ready:
                return StageReadback(False, blockers=("CERTIFICATE_READINESS_PENDING",))
            return StageReadback(True)
        raise DeploymentCommandError("READBACK_STAGE_UNAVAILABLE")

    def prepare_action(self, context: StageContext) -> ActionProposal:
        stage_id = self._stage_id(context)
        if stage_id == "bootstrap-services":
            return ActionProposal(
                "enable-bootstrap-provider-services",
                {"services": [
                    "serviceusage.googleapis.com",
                    "storage.googleapis.com",
                ]},
            )
        if stage_id == "image-publish":
            return ActionProposal(
                "publish-source-bound-shared-edge-image",
                {
                    "package": (
                        f"{_REGION}-docker.pkg.dev/{_PROJECT_ID}/"
                        "app-platform-images/shared-edge"
                    ),
                    "source_revision": context.source_revision,
                },
            )
        if stage_id == "generation-publish":
            generation = initial_generation(context.source_revision)
            return ActionProposal(
                "publish-initial-registration-generation",
                {
                    "content_digest": generation.content_digest,
                    "generation": 1,
                    "generation_digest": generation.generation_digest,
                    "object_name": generation.object_name,
                },
            )
        raise DeploymentCommandError("DEPLOYMENT_ACTION_UNAVAILABLE")

    def execute_action(self, context: StageContext, action: ExactAction) -> None:
        proposal = self.prepare_action(context)
        if action.action != proposal.action or action.summary != proposal.summary:
            raise DeploymentCommandError("DEPLOYMENT_ACTION_BINDING_MISMATCH")
        try:
            if action.action == "enable-bootstrap-provider-services":
                self._provider.enable_bootstrap_services()
            elif action.action == "publish-source-bound-shared-edge-image":
                self._provider.publish_shared_edge_image(context.source_revision)
            elif action.action == "publish-initial-registration-generation":
                self._provider.publish_initial_generation(
                    initial_generation(context.source_revision)
                )
            else:
                raise DeploymentCommandError("DEPLOYMENT_ACTION_UNAVAILABLE")
        except DeploymentProviderError as error:
            raise self._provider_error(error) from error

    def readback_action(self, context: StageContext) -> StageReadback:
        stage_id = self._stage_id(context)
        try:
            if stage_id == "bootstrap-services":
                ready = self._provider.bootstrap_services_ready()
                return StageReadback(
                    ready,
                    (),
                    () if ready else ("BOOTSTRAP_SERVICES_READBACK_MISMATCH",),
                )
            if stage_id == "image-publish":
                image = self._provider.read_shared_edge_image(context.source_revision)
                return StageReadback(
                    image is not None,
                    (("shared-edge-image-digest", image),) if image else (),
                    () if image else ("EDGE_IMAGE_READBACK_MISSING",),
                )
            if stage_id == "generation-publish":
                generation = initial_generation(context.source_revision)
                object_generation = self._provider.read_initial_generation(generation)
                return StageReadback(
                    True,
                    ((
                        "registration-generation-reference",
                        generation.reference(object_generation),
                    ),),
                )
        except DeploymentProviderError as error:
            raise self._provider_error(error) from error
        raise DeploymentCommandError("DEPLOYMENT_ACTION_UNAVAILABLE")

    def prepare_manual_checkpoint(self, context: StageContext) -> ManualCheckpoint:
        stage_id = self._stage_id(context)
        if stage_id == "oauth-configuration":
            return ManualCheckpoint(
                "provider-console",
                (
                    ("application_name", "Comfforts Apps Staging"),
                    ("support_email", self._session.active_account),
                    ("homepage_url", f"https://{_HOSTNAME}"),
                    ("authorized_origin", f"https://{_HOSTNAME}"),
                    (
                        "redirect_uri",
                        f"https://{_HOSTNAME}/_platform/auth/callback",
                    ),
                    ("secret_manager_target", _OAUTH_SECRET),
                    (
                        "secret_instruction",
                        "Add the client secret as one enabled Secret Manager version",
                    ),
                ),
            )
        if stage_id == "external-dns":
            try:
                address = self._inputs(context)["shared-edge.reserved-address"]
            except KeyError as error:
                raise DeploymentCommandError("DNS_ADDRESS_MISSING") from error
            if _IPV4.fullmatch(address) is None:
                raise DeploymentCommandError("DNS_ADDRESS_INVALID")
            return ManualCheckpoint(
                "external-dns",
                (
                    ("provider", "Squarespace"),
                    ("record_type", "A"),
                    ("record_name", "apps-staging"),
                    ("hostname", _HOSTNAME),
                    ("address", address),
                    ("ttl_seconds", "1800"),
                ),
            )
        raise DeploymentCommandError("MANUAL_CHECKPOINT_UNAVAILABLE")

    def verify_manual_checkpoint(
        self,
        context: StageContext,
        attempt: int,
        supplied_inputs: tuple[tuple[str, str], ...],
    ) -> CheckpointVerification:
        del attempt
        stage_id = self._stage_id(context)
        if stage_id == "oauth-configuration":
            supplied = dict(supplied_inputs)
            client_id = supplied.get("oauth-client-id", "")
            if (
                len(supplied) != 1
                or _CLIENT_ID.fullmatch(client_id) is None
            ):
                return CheckpointVerification(
                    "failed",
                    blockers=("OAUTH_CLIENT_ID_INVALID",),
                )
            try:
                secret_version = self._provider.oauth_secret_version()
            except DeploymentProviderError as error:
                raise self._provider_error(error) from error
            return CheckpointVerification(
                "succeeded",
                (
                    ("oauth-client-id", client_id),
                    ("oauth-secret-version", secret_version),
                ),
                "operator-attested",
            )
        if stage_id == "external-dns":
            if supplied_inputs:
                return CheckpointVerification(
                    "failed",
                    blockers=("DNS_CHECKPOINT_INPUT_PROHIBITED",),
                )
            address = self._inputs(context).get("shared-edge.reserved-address", "")
            try:
                result = self._dns.read(address)
            except DnsReadbackError as error:
                raise DeploymentCommandError(str(error)) from error
            if not result.ready:
                return CheckpointVerification(
                    "waiting",
                    blockers=("DNS_PROPAGATION_PENDING",),
                )
            return CheckpointVerification(
                "succeeded",
                (),
                "provider-verified",
            )
        raise DeploymentCommandError("MANUAL_CHECKPOINT_UNAVAILABLE")


__all__ = (
    "DeploymentDns",
    "DeploymentProvider",
    "DeploymentTerraform",
    "LocalDeploymentCommands",
)
