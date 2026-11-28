"""Deterministic private Terraform inputs for Fixture Application roots."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

from contracts.lifecycle import validate_versioned_lifecycle_document
from infrastructure.backend import PhasePlanRequest
from infrastructure.config import validate_configuration
from infrastructure.operator._interfaces import StageContext
from infrastructure.operator.deployment import (
    DeploymentCommandError,
    ExactTerraformPlan,
    TerraformPlanArtifact,
    TerraformReadback,
    TerraformReadbackRequest,
)
from infrastructure.operator.integration import AttachmentTargetReader
from infrastructure.operator.local_deployment import (
    LocalDeploymentInputError,
    PrivateTerraformWorkspace,
    RenderedTerraformInput,
    render_private_terraform_input,
)


_REGION = "us-west1"
_FIXTURE_MODES = {
    "fixture-public": "public",
    "fixture-authenticated": "authenticated",
    "fixture-multi-attachment": "authenticated",
    "fixture-restricted": "restricted",
}


def _object(value: str, code: str) -> dict[str, Any]:
    """Parse one required JSON object or raise the caller's stable input code."""

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise LocalDeploymentInputError(code) from error
    if not isinstance(parsed, dict):
        raise LocalDeploymentInputError(code)
    return parsed


class FixtureConfigurationRenderer:
    """Derive one complete fixture root input without an operator manifest."""

    def __init__(self, project_root: Path, working_root: Path) -> None:
        """Create an isolated private Terraform workspace for fixture roots."""

        self._workspace = PrivateTerraformWorkspace(project_root, working_root)

    @staticmethod
    def _inputs(context: StageContext) -> dict[str, str]:
        """Return unique closed stage inputs or reject ambiguous duplicate keys."""

        values = dict(context.inputs)
        if len(values) != len(context.inputs):
            raise LocalDeploymentInputError("FIXTURE_INPUT_DUPLICATE")
        return values

    def render(
        self,
        context: StageContext,
        request: PhasePlanRequest,
    ) -> RenderedTerraformInput:
        """Render one private fixture-root input bound to its exact handoff family."""

        if context.environment != "staging" or request.environment != "staging":
            raise LocalDeploymentInputError("FIXTURE_ENVIRONMENT_UNAVAILABLE")
        stage_id = str(context.stage.get("stage_id", ""))
        try:
            access_mode = _FIXTURE_MODES[request.phase]
        except KeyError as error:
            raise LocalDeploymentInputError("FIXTURE_PHASE_UNAVAILABLE") from error
        if (
            request.phase != stage_id
            or request.state_owner != "application"
            or request.owner_id != request.phase
            or request.source_revision != context.source_revision
        ):
            raise LocalDeploymentInputError("FIXTURE_CONTEXT_MISMATCH")

        inputs = self._inputs(context)
        try:
            image_reference = inputs["fixture-image-reference"]
            bundle = _object(
                inputs["platform-integration-bundle"],
                "INTEGRATION_BUNDLE_INVALID",
            )
            identity = bundle["identity"]
            endpoints = bundle["endpoints"]
            application_project = bundle["application_project"]
            network = bundle["network"]
            if not all(
                isinstance(value, dict)
                for value in (identity, endpoints, application_project, network)
            ):
                raise TypeError
            external_origin = endpoints["external_origin"]
            edge_caller = identity["edge_caller_reference"]
            audience = identity["audience"]
            identity_delivery = bundle["identity_delivery"]
            source_authority = bundle["platform_source_authority"]
            project_id = application_project["project_id"]
            project_number = application_project["project_number"]
        except (KeyError, TypeError) as error:
            raise LocalDeploymentInputError("FIXTURE_INPUT_INCOMPLETE") from error
        if (
            bundle.get("contract_version")
            != (3 if request.owner_id == "fixture-multi-attachment" else 2)
            or validate_versioned_lifecycle_document(
                bundle,
                "platform-integration-bundle",
            )
            or bundle.get("environment") != "staging"
            or bundle.get("application_id") != request.owner_id
            or bundle.get("access_mode") != access_mode
            or bundle.get("route_intent") != f"/{request.owner_id}"
            or source_authority not in {"accepted", "candidate"}
            or not isinstance(external_origin, str)
            or external_origin != "https://apps-staging.comfforts.com"
            or not isinstance(edge_caller, str)
            or project_id != request.project_id
            or not isinstance(project_number, str)
            or network.get("host_project_id") != "comfforts-platform-non-prod"
            or network.get("host_project_number") != "455651441682"
            or network.get("region") != _REGION
            or network.get("egress_mode") != "all-traffic"
            or (access_mode, identity_delivery)
            not in {
                ("public", "none"),
                ("public", "optional"),
                ("authenticated", "required"),
                ("restricted", "required"),
            }
            or (identity_delivery == "none" and audience is not None)
            or (
                identity_delivery != "none"
                and not isinstance(audience, str)
            )
        ):
            raise LocalDeploymentInputError("INTEGRATION_BUNDLE_MISMATCH")

        platform_issuer = f"{external_origin}/_platform"
        target_stage = (
            {"accepted": "staging", "candidate": "qualification"}[
                source_authority
            ]
            if request.owner_id == "fixture-multi-attachment"
            else "qualification"
        )
        fixture_configuration = {
            "contract_version": 1,
            "configuration_kind": "fixture",
            "configuration_class": "operator",
            "project_id": project_id,
            "project_number": project_number,
            "region": _REGION,
            "application_id": request.owner_id,
            "state_owner": "application",
            "service_name": (
                "fixture-multi-attachment-web"
                if request.owner_id == "fixture-multi-attachment"
                else request.owner_id
            ),
            "image_digest": image_reference,
            "admission_mode": access_mode,
            "assertion_audience": audience,
            "platform_issuer": platform_issuer,
            "edge_caller_principal": edge_caller,
            "network_host_project_id": network["host_project_id"],
            "shared_network_reference": network["network_reference"],
            "application_subnet_reference": network["subnetwork_reference"],
            "vpc_egress": network["egress_mode"],
            "labels": {
                "environment": target_stage,
                "managed_by": "terraform",
                "state_owner": "application",
                "application_id": request.owner_id,
            },
        }
        if validate_configuration(fixture_configuration, "fixture"):
            raise LocalDeploymentInputError("FIXTURE_CONFIGURATION_INVALID")
        platform_reference = {
            "reference_kind": "platform",
            "state_owner": "platform",
            "owner_id": "app-platform",
            "project_id": network["host_project_id"],
            "project_number": network["host_project_number"],
            "region": _REGION,
            "platform_issuer": platform_issuer,
            "public_key_reference": f"{external_origin}/.well-known/jwks.json",
            "edge_caller_principal": edge_caller,
            "shared_network_reference": network["network_reference"],
            "application_subnet_reference": network["subnetwork_reference"],
        }

        root = self._workspace.prepare_phase(request.phase)
        if request.backend_path.resolve() != (root / "backend.tf").resolve():
            raise LocalDeploymentInputError("TERRAFORM_BACKEND_PATH_MISMATCH")
        return render_private_terraform_input(
            root,
            {
                "destruction_enabled": (
                    context.stage.get("destruction_enabled") is True
                    or "delete" in context.stage.get("actions", [])
                ),
                "fixture_configuration": fixture_configuration,
                "platform_reference": platform_reference,
            },
        )


class FixtureTerraform(Protocol):
    """Only Terraform operations needed by the four fixture roots."""

    def create_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        variable_file: Path,
        *,
        bootstrap_remote: bool = False,
        destroy: bool = False,
    ) -> TerraformPlanArtifact:
        """Create one saved fixture-root plan without applying it."""

        ...

    def apply_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        saved_plan: Path,
    ) -> None:
        """Apply the exact saved fixture-root plan bound to the request."""

        ...

    def read_output(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        output_name: str,
    ) -> object:
        """Read one allowlisted non-secret Terraform output."""

        ...

    def state_empty(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> bool:
        """Return whether the selected fixture state contains no resources."""

        ...


@dataclass(frozen=True, slots=True)
class _RenderedFixturePlan:
    request: PhasePlanRequest
    rendered: RenderedTerraformInput
    destructive: bool


class LocalFixtureDeploymentCommands:
    """Bind fixture rendering to exact Terraform plan/apply/readback execution."""

    def __init__(
        self,
        renderer: FixtureConfigurationRenderer,
        terraform: FixtureTerraform,
        target_reader: AttachmentTargetReader | None = None,
    ) -> None:
        """Bind deterministic rendering, Terraform execution, and target readback."""

        self._renderer = renderer
        self._terraform = terraform
        self._target_reader = target_reader
        self._plans_by_stage: dict[str, _RenderedFixturePlan] = {}
        self._plans_by_request: dict[int, _RenderedFixturePlan] = {}

    def create_terraform_plan(
        self,
        context: StageContext,
        request: PhasePlanRequest,
    ) -> TerraformPlanArtifact:
        """Render and plan the exact fixture root without exposing private inputs."""

        try:
            rendered = self._renderer.render(context, request)
            actions = context.stage.get("actions")
            destructive = isinstance(actions, list) and "delete" in actions
            planned = _RenderedFixturePlan(request, rendered, destructive)
            stage_id = str(context.stage.get("stage_id", ""))
            self._plans_by_stage[stage_id] = planned
            self._plans_by_request[id(request)] = planned
            return self._terraform.create_plan(
                request,
                rendered.terraform_root,
                rendered.variable_file,
                destroy=destructive,
            )
        except DeploymentCommandError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise DeploymentCommandError("FIXTURE_PLAN_COMMAND_FAILED") from error

    def apply_terraform_plan(
        self,
        request: PhasePlanRequest,
        plan: ExactTerraformPlan,
    ) -> None:
        """Apply only the saved plan previously bound to this fixture request."""

        try:
            rendered = self._plans_by_request[id(request)].rendered
            self._terraform.apply_plan(
                request,
                rendered.terraform_root,
                plan.saved_plan_path,
            )
        except KeyError as error:
            raise DeploymentCommandError("FIXTURE_PLAN_CONTEXT_MISSING") from error
        except DeploymentCommandError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise DeploymentCommandError("FIXTURE_APPLY_COMMAND_FAILED") from error

    @staticmethod
    def _attachment_output(
        value: object,
        request: PhasePlanRequest,
        rendered: RenderedTerraformInput,
    ) -> str:
        """Validate and serialize the root's complete non-secret attachment output."""

        try:
            variables = json.loads(rendered.variable_file.read_bytes())
            configuration = variables["fixture_configuration"]
            expected_audience = configuration["assertion_audience"]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DeploymentCommandError("FIXTURE_INPUT_READBACK_INVALID") from error

        def reference(attachment_id: str, service_name: str) -> dict[str, object]:
            """Build the exact expected non-secret attachment reference."""

            return {
                "reference_kind": "attachment",
                "state_owner": "application",
                "owner_id": request.owner_id,
                "application_id": request.owner_id,
                "attachment_id": attachment_id,
                "adapter_kind": "gcp-cloud-run-v1",
                "resource_reference": (
                    "urn:comfforts:app-platform:gcp:cloud-run:"
                    f"{configuration['project_number']}:{_REGION}:{service_name}"
                ),
                "audience": expected_audience,
            }

        expected: object
        if request.owner_id == "fixture-multi-attachment":
            expected = {
                "api": reference("api", "fixture-multi-attachment-api"),
                "web": reference("web", "fixture-multi-attachment-web"),
            }
        else:
            expected = reference("primary", request.owner_id)
        if value != expected:
            raise DeploymentCommandError("FIXTURE_READBACK_MISMATCH")
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def readback_terraform(
        self,
        request: TerraformReadbackRequest,
    ) -> TerraformReadback:
        """Read the exact complete attachment set or prove every target was destroyed."""

        try:
            planned = self._plans_by_stage[request.stage_id]
        except KeyError:
            return TerraformReadback(False, blockers=("FIXTURE_PLAN_CONTEXT_MISSING",))
        if (
            planned.request.phase != request.phase
            or planned.request.owner_id != request.stage_id
            or planned.request.environment != request.environment
            or planned.request.source_revision != request.source_revision
        ):
            return TerraformReadback(False, blockers=("FIXTURE_CONTEXT_MISMATCH",))
        try:
            if planned.destructive:
                if self._target_reader is None:
                    return TerraformReadback(
                        False,
                        blockers=("FIXTURE_TARGET_READBACK_UNAVAILABLE",),
                    )
                state_empty = self._terraform.state_empty(
                    planned.request,
                    planned.rendered.terraform_root,
                )
                variables = json.loads(
                    planned.rendered.variable_file.read_bytes()
                )
                project_number = variables["fixture_configuration"][
                    "project_number"
                ]
                service_names = (
                    (
                        "fixture-multi-attachment-api",
                        "fixture-multi-attachment-web",
                    )
                    if planned.request.owner_id == "fixture-multi-attachment"
                    else (planned.request.owner_id,)
                )
                targets = tuple(
                    self._target_reader.read_target(
                        request.environment,
                        "urn:comfforts:app-platform:gcp:cloud-run:"
                        f"{project_number}:{_REGION}:{service_name}",
                    )
                    for service_name in service_names
                )
                if not state_empty or any(target.exists for target in targets):
                    return TerraformReadback(
                        False,
                        blockers=("FIXTURE_DESTRUCTION_READBACK_MISMATCH",),
                    )
                return TerraformReadback(
                    True,
                    (("fixture-destroyed", planned.request.owner_id),),
                )
            multi_attachment = planned.request.owner_id == "fixture-multi-attachment"
            value = self._terraform.read_output(
                planned.request,
                planned.rendered.terraform_root,
                "attachment_references" if multi_attachment else "attachment_reference",
            )
            reference = self._attachment_output(
                value,
                planned.request,
                planned.rendered,
            )
            return TerraformReadback(
                True,
                (
                    (
                        "attachment-references"
                        if multi_attachment
                        else "attachment-reference",
                        reference,
                    ),
                ),
            )
        except DeploymentCommandError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise DeploymentCommandError("FIXTURE_READBACK_FAILED") from error


__all__ = (
    "FixtureConfigurationRenderer",
    "FixtureTerraform",
    "LocalFixtureDeploymentCommands",
)
