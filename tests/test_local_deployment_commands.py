"""Real deployment composition through deterministic provider and command fakes."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.backend import PhasePlanRequest
from infrastructure.operator import StageContext
from infrastructure.operator.deployment import (
    ExactAction,
    ExactTerraformPlan,
    TerraformPlanArtifact,
    TerraformReadbackRequest,
)
from infrastructure.operator.deployment_dns import DnsReadback
from infrastructure.operator.deployment_provider import CertificateReadback
from infrastructure.operator.local_deployment import (
    DeploymentConfigurationRenderer,
    InitialGeneration,
    OperatorSessionFacts,
    initial_generation,
)
from infrastructure.operator.local_deployment_commands import LocalDeploymentCommands


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a" * 40
SPECIFICATION = "sha256:" + "b" * 64


def _context(
    stage_id: str,
    produces: tuple[str, ...],
    inputs: tuple[tuple[str, str], ...] = (),
) -> StageContext:
    return StageContext(
        environment="staging",
        source_revision=SOURCE,
        specification_digest=SPECIFICATION,
        stage={
            "stage_id": stage_id,
            "actions": ["create", "read"],
            "resource_types": ["test"],
            "consumes": [],
            "produces": list(produces),
            "manual_checkpoint": {
                "oauth-configuration": "provider-console",
                "external-dns": "external-dns",
            }.get(stage_id, "none"),
            "readback": "provider-verified",
        },
        inputs=inputs,
    )


def _request(root: Path, phase: str) -> PhasePlanRequest:
    return PhasePlanRequest(
        environment="staging",
        source_revision=SOURCE,
        phase=phase,
        terraform_root={
            "bootstrap": "infrastructure/terraform/bootstrap",
            "platform-foundation": "infrastructure/terraform/platform",
            "shared-edge": "infrastructure/terraform/platform",
        }[phase],
        state_owner="platform",
        owner_id="app-platform",
        project_id="comfforts-platform-non-prod",
        backend_path=root / phase / "backend.tf",
        backend_digest="sha256:" + "c" * 64,
        backend_bucket="comfforts-ap-stg-455651441682-platform-state",
        backend_prefix="bootstrap" if phase == "bootstrap" else "platform",
    )


@dataclass
class FakeTerraform:
    applied: list[str] = field(default_factory=list)
    migrated: int = 0

    def create_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        variable_file: Path,
    ) -> TerraformPlanArtifact:
        self.assert_private(variable_file)
        plan = terraform_root / "saved.tfplan"
        plan.write_bytes(b"saved plan")
        plan.chmod(0o600)
        return TerraformPlanArtifact(
            plan,
            {
                "environment": "staging",
                "source_revision": SOURCE,
                "state_owner": "platform",
                "owner_id": "app-platform",
                "terraform_root": request.terraform_root,
                "phase": request.phase,
                "provider": {
                    "source": "registry.terraform.io/hashicorp/google",
                    "service": "google",
                    "project_id": "comfforts-platform-non-prod",
                    "configuration": "explicit",
                },
                "changes": [],
            },
        )

    @staticmethod
    def assert_private(path: Path) -> None:
        if path.stat().st_mode & 0o077:
            raise AssertionError("variables are not private")

    def apply_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        saved_plan: Path,
    ) -> None:
        del terraform_root, saved_plan
        self.applied.append(request.phase)

    def migrate_bootstrap_state(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> None:
        del terraform_root
        if request.phase != "bootstrap":
            raise AssertionError("wrong migration")
        self.migrated += 1

    def read_output(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        output_name: str,
    ) -> object:
        del request
        if output_name == "bootstrap_phase_output":
            return {
                "contract_version": 1,
                "output_kind": "bootstrap",
                "environment": "staging",
                "project_id": "comfforts-platform-non-prod",
                "region": "us-west1",
                "state_owner": "platform",
                "owner_id": "app-platform",
                "lineages": {"bootstrap": {"prefix": "bootstrap"}},
            }
        if output_name == "foundation_phase_output":
            return {
                "contract_version": 1,
                "output_kind": "platform-foundation",
                "environment": "staging",
                "state_owner": "platform",
                "owner_id": "app-platform",
                "project_id": "comfforts-platform-non-prod",
                "project_number": "455651441682",
                "region": "us-west1",
                "hostname": "apps-staging.comfforts.com",
                "foundation": {
                    "configuration_bucket": (
                        "comfforts-ap-stg-455651441682-configuration"
                    ),
                    "oauth_secret_id": (
                        "projects/comfforts-platform-non-prod/secrets/"
                        "app-platform-edge-oauth"
                    ),
                },
                "controls": {},
            }
        variables = json.loads(
            (terraform_root / "terraform.tfvars.json").read_text(encoding="utf-8")
        )
        tls = variables["platform_configuration"]["shared_edge"]["tls_enabled"]
        return {
            "contract_version": 1,
            "output_kind": "shared-edge",
            "environment": "staging",
            "state_owner": "platform",
            "owner_id": "app-platform",
            "project_id": "comfforts-platform-non-prod",
            "region": "us-west1",
            "edge": {
                "hostname": "apps-staging.comfforts.com",
                "reserved_address": "34.120.10.20",
                "service_name": "app-platform-edge",
                "tls_enabled": tls,
            },
        }


@dataclass
class FakeProvider:
    services: bool = False
    image: str | None = None
    generation: int | None = None
    certificate_ready: bool = True

    def enable_bootstrap_services(self) -> None:
        self.services = True

    def bootstrap_services_ready(self) -> bool:
        return self.services

    def publish_initial_generation(self, generation: InitialGeneration) -> int:
        del generation
        self.generation = 42
        return 42

    def read_initial_generation(self, generation: InitialGeneration) -> int:
        del generation
        if self.generation is None:
            raise AssertionError("generation missing")
        return self.generation

    def publish_shared_edge_image(self, source_revision: str) -> str:
        del source_revision
        self.image = (
            "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
            "app-platform-images/shared-edge@sha256:" + "d" * 64
        )
        return self.image

    def read_shared_edge_image(self, source_revision: str) -> str | None:
        del source_revision
        return self.image

    def active_signing_key_version(self) -> str:
        return (
            "projects/comfforts-platform-non-prod/locations/us-west1/keyRings/"
            "app-platform/cryptoKeys/edge-signing/cryptoKeyVersions/1"
        )

    def oauth_secret_version(self) -> str:
        return (
            "projects/comfforts-platform-non-prod/secrets/"
            "app-platform-edge-oauth/versions/1"
        )

    def certificate_readback(self) -> CertificateReadback:
        return CertificateReadback(
            "https://compute.googleapis.com/projects/example/certificates/edge",
            self.certificate_ready,
        )


@dataclass
class FakeDns:
    ready: bool = True
    addresses: list[str] = field(default_factory=list)

    def read(self, expected_address: str) -> DnsReadback:
        self.addresses.append(expected_address)
        return DnsReadback(
            self.ready,
            "sha256:" + "e" * 64 if self.ready else None,
        )


class LocalDeploymentCommandsTest(unittest.TestCase):
    def _commands(
        self,
        directory: str,
    ) -> tuple[LocalDeploymentCommands, FakeTerraform, FakeProvider, FakeDns, Path]:
        work = Path(directory) / "work"
        work.mkdir(mode=0o700)
        session = OperatorSessionFacts(
            active_account="operator@example.com",
            billing_account_reference="billingAccounts/ABCDEF-123456-789ABC",
            operator_issuer="https://accounts.google.com",
            operator_subject="123456789012345678901",
        )
        terraform = FakeTerraform()
        provider = FakeProvider()
        dns = FakeDns()
        return (
            LocalDeploymentCommands(
                DeploymentConfigurationRenderer(PROJECT_ROOT, work, session),
                terraform,
                provider,
                dns,
                session,
            ),
            terraform,
            provider,
            dns,
            work,
        )

    @staticmethod
    def _readback(
        commands: LocalDeploymentCommands,
        context: StageContext,
        phase: str,
    ):
        return commands.readback_terraform(
            TerraformReadbackRequest(
                stage_id=str(context.stage["stage_id"]),
                phase=phase,
                environment="staging",
                source_revision=SOURCE,
                specification_digest=SPECIFICATION,
                inputs=context.inputs,
            )
        )

    def test_bootstrap_plan_apply_migrates_and_reads_remote_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands, terraform, _, _, work = self._commands(directory)
            context = _context("bootstrap", ("backend-reference",))
            request = _request(work, "bootstrap")
            artifact = commands.create_terraform_plan(context, request)
            commands.apply_terraform_plan(
                request,
                ExactTerraformPlan(artifact.saved_plan_path, "sha256:x", "sha256:y", {}),
            )
            result = self._readback(commands, context, "bootstrap")

        self.assertTrue(result.matched)
        self.assertEqual(terraform.applied, ["bootstrap"])
        self.assertEqual(terraform.migrated, 1)
        self.assertEqual(result.outputs[0][0], "backend-reference")

    def test_foundation_and_edge_readbacks_feed_later_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands, _, _, _, work = self._commands(directory)
            foundation = _context(
                "foundation",
                ("foundation-reference", "oauth-secret-container"),
            )
            commands.create_terraform_plan(
                foundation,
                _request(work, "platform-foundation"),
            )
            foundation_result = self._readback(
                commands,
                foundation,
                "platform-foundation",
            )
            reference = dict(foundation_result.outputs)["foundation-reference"]
            generation = initial_generation(SOURCE)
            edge = _context(
                "shared-edge",
                ("edge-reference", "reserved-address"),
                (
                    ("foundation.foundation-reference", reference),
                    (
                        "image-publish.shared-edge-image-digest",
                        "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
                        "app-platform-images/shared-edge@sha256:" + "d" * 64,
                    ),
                    ("oauth-configuration.oauth-client-id", "123-client.apps.googleusercontent.com"),
                    (
                        "oauth-configuration.oauth-secret-version",
                        "projects/comfforts-platform-non-prod/secrets/"
                        "app-platform-edge-oauth/versions/1",
                    ),
                    (
                        "generation-publish.registration-generation-reference",
                        generation.reference(42),
                    ),
                ),
            )
            commands.create_terraform_plan(edge, _request(work, "shared-edge"))
            edge_result = self._readback(commands, edge, "shared-edge")

        self.assertTrue(foundation_result.matched)
        self.assertIn("signing_key_version", json.loads(reference))
        self.assertEqual(
            dict(edge_result.outputs)["reserved-address"],
            "34.120.10.20",
        )

    def test_actions_are_exact_idempotent_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands, _, provider, _, _ = self._commands(directory)
            cases = (
                ("bootstrap-services", ("bootstrap-services-attestation",)),
                ("image-publish", ("shared-edge-image-digest",)),
                ("generation-publish", ("registration-generation-reference",)),
            )
            outputs = []
            for stage_id, produces in cases:
                context = _context(stage_id, produces)
                proposal = commands.prepare_action(context)
                commands.execute_action(
                    context,
                    ExactAction(proposal.action, "sha256:" + "f" * 64, proposal.summary),
                )
                outputs.append(commands.readback_action(context))

        self.assertTrue(provider.services)
        self.assertIsNotNone(provider.image)
        self.assertEqual(provider.generation, 42)
        self.assertTrue(all(result.matched for result in outputs))

    def test_oauth_prompts_only_non_secret_input_and_reads_secret_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands, _, _, _, _ = self._commands(directory)
            context = _context(
                "oauth-configuration",
                ("oauth-client-id", "oauth-secret-version"),
            )
            checkpoint = commands.prepare_manual_checkpoint(context)
            result = commands.verify_manual_checkpoint(
                context,
                1,
                (("oauth-client-id", "123-client.apps.googleusercontent.com"),),
            )

        transcript = json.dumps(checkpoint.instructions)
        self.assertIn("Comfforts Apps Staging", transcript)
        self.assertIn("/_platform/auth/callback", transcript)
        self.assertNotIn("client_secret", transcript)
        self.assertEqual(result.outcome, "succeeded")
        self.assertTrue(dict(result.outputs)["oauth-secret-version"].endswith("/1"))

    def test_dns_checkpoint_waits_then_returns_provider_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            commands, _, _, dns, _ = self._commands(directory)
            context = _context(
                "external-dns",
                ("dns-attestation",),
                (("shared-edge.reserved-address", "34.120.10.20"),),
            )
            checkpoint = commands.prepare_manual_checkpoint(context)
            dns.ready = False
            waiting = commands.verify_manual_checkpoint(context, 1, ())
            dns.ready = True
            verified = commands.verify_manual_checkpoint(context, 2, ())

        self.assertIn(("ttl_seconds", "1800"), checkpoint.instructions)
        self.assertEqual(waiting.outcome, "waiting")
        self.assertEqual(verified.outcome, "succeeded")
        self.assertEqual(dns.addresses, ["34.120.10.20", "34.120.10.20"])


if __name__ == "__main__":
    unittest.main()
