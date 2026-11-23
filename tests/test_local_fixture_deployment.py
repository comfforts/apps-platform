"""Deterministic fixture Terraform rendering without hand-authored manifests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import stat
import tempfile
import unittest

from infrastructure.backend import (
    PhasePlanRequest,
    backend_declarations,
    render_backend_declaration,
)
from infrastructure.operator import StageContext
from infrastructure.operator.deployment import (
    DeploymentExecutor,
    TerraformPlanArtifact,
)
from infrastructure.operator.local_deployment import LocalDeploymentInputError
from infrastructure.operator.local_fixture_deployment import (
    FixtureConfigurationRenderer,
    LocalFixtureDeploymentCommands,
)
from infrastructure.operator.integration import AttachmentTargetReadback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "a" * 40
SPECIFICATION_DIGEST = "sha256:" + ("b" * 64)
IMAGE_REFERENCE = (
    "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
    "app-platform-images/fixture@sha256:"
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
)
EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)


def _bundle(application_id: str, access_mode: str) -> dict[str, object]:
    protected = access_mode != "public"
    origin = "https://apps-staging.comfforts.com"
    return {
        "contract_version": 1,
        "document_kind": "platform-integration-bundle",
        "environment": "staging",
        "application_id": application_id,
        "access_mode": access_mode,
        "route_intent": f"/{application_id}",
        "generation": 7,
        "profile_digest": "sha256:" + ("1" * 64),
        "platform_source_authority": "accepted",
        "platform_source_revision": "b" * 40,
        "specification_digest": "sha256:" + ("2" * 64),
        "deployment_progress_digest": "sha256:" + ("3" * 64),
        "endpoints": {
            "external_origin": origin,
            "issuer": f"{origin}/_platform" if protected else None,
            "jwks_uri": f"{origin}/.well-known/jwks.json" if protected else None,
            "oauth_redirect_uri": (
                f"{origin}/_platform/auth/callback" if protected else None
            ),
        },
        "identity": {
            "oauth_client_id": (
                "1234567890-appsplatform.apps.googleusercontent.com"
                if protected
                else None
            ),
            "audience": (
                f"urn:comfforts:app-platform:audience:{application_id}"
                if protected
                else None
            ),
            "edge_caller_reference": EDGE_CALLER,
        },
        "attachment_contract": {
            "adapter_kind": "gcp-cloud-run-v1",
            "ingress_mode": "shared_edge_only",
        },
        "qualification_status": "unqualified",
    }


def _context(application_id: str, access_mode: str) -> StageContext:
    return StageContext(
        environment="staging",
        source_revision=SOURCE_REVISION,
        specification_digest=SPECIFICATION_DIGEST,
        stage={
            "stage_id": application_id,
            "actions": ["create", "read", "update"],
            "resource_types": [
                "google_service_account",
                "google_cloud_run_v2_service",
                "google_cloud_run_v2_service_iam_member",
            ],
            "consumes": ["fixture-image-reference", "platform-integration-bundle"],
            "produces": ["attachment-reference"],
            "manual_checkpoint": "none",
            "readback": "provider-verified",
        },
        inputs=(
            ("fixture-image-reference", IMAGE_REFERENCE),
            (
                "platform-integration-bundle",
                json.dumps(_bundle(application_id, access_mode), sort_keys=True),
            ),
        ),
    )


def _request(root: Path, application_id: str) -> PhasePlanRequest:
    declaration = next(
        value
        for value in backend_declarations("staging")
        if value.phase == application_id
    )
    rendered = render_backend_declaration(
        declaration,
        root,
        f"{application_id}/backend.tf",
    )
    return PhasePlanRequest(
        environment="staging",
        source_revision=SOURCE_REVISION,
        phase=application_id,
        terraform_root=declaration.terraform_root,
        state_owner=declaration.state_owner,
        owner_id=declaration.owner_id,
        project_id=declaration.project_id,
        backend_path=rendered.path,
        backend_digest=rendered.digest,
        backend_bucket=declaration.bucket,
        backend_prefix=declaration.prefix,
    )


class FixtureConfigurationRendererTest(unittest.TestCase):
    def test_renders_complete_private_inputs_for_all_three_roots(self) -> None:
        profiles = (
            ("fixture-public", "public", None),
            (
                "fixture-authenticated",
                "authenticated",
                "urn:comfforts:app-platform:audience:fixture-authenticated",
            ),
            (
                "fixture-restricted",
                "restricted",
                "urn:comfforts:app-platform:audience:fixture-restricted",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_root = Path(temporary_directory) / "private"
            renderer = FixtureConfigurationRenderer(PROJECT_ROOT, working_root)
            rendered = []
            for application_id, access_mode, audience in profiles:
                value = renderer.render(
                    _context(application_id, access_mode),
                    _request(working_root, application_id),
                )
                rendered.append(value)
                variables = json.loads(value.variable_file.read_bytes())
                configuration = variables["fixture_configuration"]
                self.assertEqual(configuration["application_id"], application_id)
                self.assertEqual(configuration["admission_mode"], access_mode)
                self.assertEqual(configuration["assertion_audience"], audience)
                self.assertEqual(configuration["image_digest"], IMAGE_REFERENCE)
                self.assertFalse(variables["destruction_enabled"])
                self.assertEqual(
                    variables["platform_reference"]["state_owner"],
                    "platform",
                )
                self.assertEqual(
                    stat.S_IMODE(value.variable_file.stat().st_mode),
                    0o600,
                )
                module_root = (
                    value.terraform_root / "../../modules/fixture-application"
                ).resolve()
                self.assertTrue(module_root.is_dir())
                self.assertTrue((module_root / "main.tf").is_file())

        self.assertEqual(len({value.terraform_root for value in rendered}), 3)
        self.assertEqual(len({value.configuration_digest for value in rendered}), 3)

    def test_rejects_cross_owner_bundle_before_writing_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_root = Path(temporary_directory) / "private"
            renderer = FixtureConfigurationRenderer(PROJECT_ROOT, working_root)
            context = _context("fixture-public", "public")
            inputs = dict(context.inputs)
            inputs["platform-integration-bundle"] = json.dumps(
                _bundle("fixture-authenticated", "authenticated"),
                sort_keys=True,
            )
            context = replace(context, inputs=tuple(inputs.items()))

            with self.assertRaisesRegex(
                LocalDeploymentInputError,
                "INTEGRATION_BUNDLE_MISMATCH",
            ):
                renderer.render(context, _request(working_root, "fixture-public"))

            self.assertFalse(
                (working_root / "fixture-public" / "terraform.tfvars.json").exists()
            )


@dataclass
class FakeTerminal:
    confirmed: bool = True
    messages: list[str] = field(default_factory=list)

    def ask(self, prompt: str) -> str:
        del prompt
        raise AssertionError("fixture Terraform does not prompt for values")

    def confirm(self, prompt: str) -> bool:
        self.messages.append(prompt)
        return self.confirmed

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        del prompt, expected
        raise AssertionError("fixture create/update uses y/N plan confirmation")

    def write(self, message: str) -> None:
        self.messages.append(message)

    def pause(self, prompt: str) -> None:
        del prompt
        raise AssertionError("fixture Terraform has no manual checkpoint")


@dataclass
class FakeTerraform:
    applied: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    prohibited_resource: bool = False
    plan_count: int = 0
    destroyed: bool = False
    planned_destroy: dict[int, bool] = field(default_factory=dict)

    def create_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        variable_file: Path,
        *,
        bootstrap_remote: bool = False,
        destroy: bool = False,
    ) -> TerraformPlanArtifact:
        if bootstrap_remote:
            raise AssertionError("fixture roots never use bootstrap migration")
        if stat.S_IMODE(variable_file.stat().st_mode) != 0o600:
            raise AssertionError("fixture variables are not private")
        self.plan_count += 1
        saved_plan = terraform_root / f"saved-{self.plan_count}.tfplan"
        saved_plan.write_bytes(b"exact fixture plan")
        saved_plan.chmod(0o600)
        resource_type = (
            "google_storage_bucket"
            if self.prohibited_resource
            else "google_cloud_run_v2_service"
        )
        artifact = TerraformPlanArtifact(
            saved_plan,
            {
                "environment": request.environment,
                "source_revision": request.source_revision,
                "state_owner": request.state_owner,
                "owner_id": request.owner_id,
                "terraform_root": request.terraform_root,
                "phase": request.phase,
                "provider": {
                    "source": "registry.terraform.io/hashicorp/google",
                    "service": "google",
                    "project_id": request.project_id,
                    "configuration": "explicit",
                },
                "changes": [
                    {
                        "address": f"module.fixture.{resource_type}.runtime",
                        "resource_type": resource_type,
                        "provider_source": (
                            "registry.terraform.io/hashicorp/google"
                        ),
                        "actions": ["delete" if destroy else "create"],
                    }
                ],
            },
        )
        self.planned_destroy[id(request)] = destroy
        return artifact

    def apply_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        saved_plan: Path,
    ) -> None:
        del terraform_root
        if saved_plan.read_bytes() != b"exact fixture plan":
            raise AssertionError("a different plan was applied")
        self.applied.append(request.phase)
        if self.planned_destroy.get(id(request), False):
            self.destroyed = True

    def read_output(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        output_name: str,
    ) -> object:
        if output_name != "attachment_reference":
            raise AssertionError("unexpected fixture output")
        variables = json.loads(
            (terraform_root / "terraform.tfvars.json").read_bytes()
        )
        configuration = variables["fixture_configuration"]
        self.outputs.append(request.phase)
        return {
            "reference_kind": "attachment",
            "state_owner": "application",
            "owner_id": request.owner_id,
            "application_id": request.owner_id,
            "attachment_id": "primary",
            "adapter_kind": "gcp-cloud-run-v1",
            "resource_reference": (
                "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
                f"us-west1:{request.owner_id}"
            ),
            "audience": configuration["assertion_audience"],
        }

    def state_empty(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> bool:
        del request, terraform_root
        return self.destroyed


@dataclass
class FakeTargetReader:
    terraform: FakeTerraform

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback:
        del environment
        application_id = resource_reference.rsplit(":", maxsplit=1)[1]
        return AttachmentTargetReadback(
            exists=not self.terraform.destroyed,
            ready=not self.terraform.destroyed,
            owner_application_id=application_id,
            adapter_kind="gcp-cloud-run-v1",
            resource_reference=resource_reference,
            ingress_mode="shared_edge_only",
            caller_grant=EDGE_CALLER,
            audience=(
                "urn:comfforts:app-platform:audience:fixture-authenticated"
            ),
        )


class FixtureExactPlanExecutionTest(unittest.TestCase):
    def _execute(
        self,
        temporary_directory: str,
        *,
        terminal: FakeTerminal | None = None,
        terraform: FakeTerraform | None = None,
    ):
        working_root = Path(temporary_directory) / "private"
        working_root.mkdir(mode=0o700)
        renderer = FixtureConfigurationRenderer(PROJECT_ROOT, working_root)
        selected_terminal = terminal or FakeTerminal()
        selected_terraform = terraform or FakeTerraform()
        commands = LocalFixtureDeploymentCommands(renderer, selected_terraform)
        executor = DeploymentExecutor(
            working_root,
            selected_terminal,
            commands,  # type: ignore[arg-type]
        )
        result = executor.execute(_context("fixture-authenticated", "authenticated"))
        return result, selected_terminal, selected_terraform

    def test_checks_confirms_applies_and_reads_back_one_exact_fixture_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result, terminal, terraform = self._execute(temporary_directory)

        self.assertEqual(result.outcome, "succeeded")
        self.assertEqual(terraform.applied, ["fixture-authenticated"])
        self.assertEqual(terraform.outputs, ["fixture-authenticated"])
        self.assertEqual(result.outputs[0][0], "attachment-reference")
        self.assertTrue(any(message.startswith("PLAN\n{") for message in terminal.messages))
        self.assertTrue(any("Apply the reviewed" in message for message in terminal.messages))

    def test_policy_refusal_or_operator_cancellation_never_applies(self) -> None:
        cases = (
            (FakeTerminal(), FakeTerraform(prohibited_resource=True), "failed"),
            (FakeTerminal(confirmed=False), FakeTerraform(), "cancelled"),
        )
        for terminal, terraform, outcome in cases:
            with self.subTest(outcome=outcome):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    result, _, _ = self._execute(
                        temporary_directory,
                        terminal=terminal,
                        terraform=terraform,
                    )
                self.assertEqual(result.outcome, outcome)
                self.assertEqual(terraform.applied, [])
                self.assertEqual(terraform.outputs, [])

    def test_unlock_then_destroy_uses_separate_exact_plans_and_empty_readback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_root = Path(temporary_directory) / "private"
            working_root.mkdir(mode=0o700)
            terminal = FakeTerminal()
            terraform = FakeTerraform()
            commands = LocalFixtureDeploymentCommands(
                FixtureConfigurationRenderer(PROJECT_ROOT, working_root),
                terraform,
                FakeTargetReader(terraform),
            )
            executor = DeploymentExecutor(working_root, terminal, commands)  # type: ignore[arg-type]
            unlock_context = _context(
                "fixture-authenticated",
                "authenticated",
            )
            unlock_context = replace(
                unlock_context,
                stage={
                    **unlock_context.stage,
                    "actions": ["read", "update"],
                    "destruction_enabled": True,
                },
            )
            destroy_context = replace(
                unlock_context,
                stage={
                    **unlock_context.stage,
                    "actions": ["delete", "read"],
                    "produces": ["fixture-destroyed"],
                },
            )

            unlocked = executor.execute(unlock_context)
            destroyed = executor.execute(destroy_context)

        self.assertEqual(unlocked.outcome, "succeeded")
        self.assertEqual(destroyed.outcome, "succeeded")
        self.assertEqual(destroyed.outputs, (("fixture-destroyed", "fixture-authenticated"),))
        self.assertEqual(terraform.applied, ["fixture-authenticated"] * 2)
        self.assertTrue(terraform.destroyed)


if __name__ == "__main__":
    unittest.main()
