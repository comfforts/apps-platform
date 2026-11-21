"""Deterministic exact-plan coverage for the real safe-destruction adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from infrastructure.operator.deployment import TerraformPlanArtifact
from infrastructure.operator.destruction import (
    DESTRUCTIBLE_PLATFORM_RESOURCES,
    RETAINED_PLATFORM_RESOURCES,
    DestructionLifecycle,
    DestructionSnapshot,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_deployment import RenderedTerraformInput
from infrastructure.operator.local_destruction import LocalDestructionControl
from infrastructure.operator.local_destruction_commands import (
    LocalDestructionExecutor,
)


SOURCE = "a" * 40
DIGEST = "sha256:" + "b" * 64
OUTPUTS = {
    "foundation-reference": json.dumps({"signing_key_version": "version"}),
    "oauth-client-id": "123456789-fixture.apps.googleusercontent.com",
    "oauth-secret-version": "projects/project/secrets/secret/versions/1",
    "registration-generation-reference": "{}",
    "reserved-address": "192.0.2.10",
    "shared-edge-image-digest": "image@sha256:" + "c" * 64,
}
RETAINED_ADDRESSES = (
    'module.platform_foundation.google_project_service.platform["run.googleapis.com"]',
    "module.platform_foundation.google_storage_bucket.configuration",
    "module.platform_foundation.google_kms_key_ring.assertion_signing",
    "module.platform_foundation.google_kms_crypto_key.assertion_signing",
    "module.platform_controls.google_storage_bucket.evidence",
    "module.platform_controls.google_storage_bucket_iam_member.evidence_owner_reader",
    "module.platform_controls.google_logging_project_exclusion.edge_from_default",
)


class FakeStateReader:
    def read_current(self, environment: str) -> DestructionSnapshot:
        return DestructionSnapshot(
            environment=environment,
            lifecycle_state="deployed",
            source_revision=SOURCE,
            profile_digest=DIGEST,
            deployed_specification_digest=DIGEST,
            deployment_progress_digest=DIGEST,
            registration_generation_digest=DIGEST,
            qualification_evidence_digest=DIGEST,
            active_application_ids=(),
            platform_resource_types=DESTRUCTIBLE_PLATFORM_RESOURCES,
            retained_resource_types=RETAINED_PLATFORM_RESOURCES,
            ownership_matches=True,
        )


@dataclass
class FakeTerminal:
    messages: list[str] = field(default_factory=list)
    confirmations: list[str] = field(default_factory=list)
    pauses: list[str] = field(default_factory=list)

    def write(self, message: str) -> None:
        self.messages.append(message)

    def confirm(self, prompt: str) -> bool:
        self.confirmations.append(prompt)
        return True

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.confirmations.append(prompt)
        return expected.startswith("DESTROY staging PLATFORM sha256:")

    def pause(self, prompt: str) -> None:
        self.pauses.append(prompt)


@dataclass
class FakeWaiter:
    waits: list[int] = field(default_factory=list)

    def wait(self, seconds: int) -> None:
        self.waits.append(seconds)


class FakeRenderer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.mode = ""
        self.modes: list[str] = []

    def render_transition(self, request, mode, outputs):  # type: ignore[no-untyped-def]
        self.mode = mode
        self.modes.append(mode)
        self.assert_outputs = outputs
        root = self.root / request.phase
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        variables = root / "terraform.tfvars.json"
        variables.write_text("{}\n", encoding="utf-8")
        variables.chmod(0o600)
        return RenderedTerraformInput(root, variables, DIGEST)


class FakeTerraform:
    def __init__(self, root: Path, renderer: FakeRenderer) -> None:
        self.root = root
        self.renderer = renderer
        self.applied: list[str] = []
        self.sequence = 0

    def create_plan(
        self,
        request,
        terraform_root,
        variable_file,
        *,
        bootstrap_remote=False,
        destroy=False,
    ):  # type: ignore[no-untyped-def]
        del terraform_root, variable_file, bootstrap_remote, destroy
        self.sequence += 1
        path = self.root / "plans" / f"{self.sequence}.tfplan"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(f"plan-{self.sequence}".encode())
        path.chmod(0o600)
        mode = self.renderer.mode
        action = "update" if mode.endswith("unlock") else "delete"
        if mode.startswith("shared-edge"):
            resource_type = "google_cloud_run_v2_service"
            address = "module.shared_edge[0].google_cloud_run_v2_service.edge"
        else:
            resource_type = "google_secret_manager_secret"
            address = "module.platform_foundation.google_secret_manager_secret.edge_oauth[0]"
        return TerraformPlanArtifact(
            path,
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
                        "address": address,
                        "resource_type": resource_type,
                        "provider_source": "registry.terraform.io/hashicorp/google",
                        "actions": [action],
                    }
                ],
            },
        )

    def apply_plan(self, request, terraform_root, saved_plan):  # type: ignore[no-untyped-def]
        del request, terraform_root, saved_plan
        self.applied.append(self.renderer.mode)

    def platform_state_addresses(self, request, terraform_root):  # type: ignore[no-untyped-def]
        del request, terraform_root
        if self.renderer.mode == "retained":
            return RETAINED_ADDRESSES
        return (
            "module.platform_foundation.google_storage_bucket.configuration",
        )


class FakeProvider:
    def shared_edge_ingress(self, environment: str) -> str:
        self.environment = environment
        return "internal"

    def shared_edge_exists(self, environment: str) -> bool:
        self.environment = environment
        return False


class FakeDns:
    @dataclass(frozen=True)
    class Result:
        ready: bool = True
        attestation: str = DIGEST

    def absent(self) -> Result:
        return self.Result()


class LocalDestructionCommandsTest(unittest.TestCase):
    def test_complete_journey_uses_four_exact_transitions_and_retains_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            state.mkdir(mode=0o700)
            work = state / "work" / "destruction"
            work.mkdir(mode=0o700, parents=True)
            filesystem = LocalFilesystem(root, state)
            renderer = FakeRenderer(work)
            terraform = FakeTerraform(work, renderer)
            terminal = FakeTerminal()
            waiter = FakeWaiter()
            lifecycle = DestructionLifecycle(
                FakeStateReader(),
                LocalDestructionControl(filesystem),
                terminal,
                LocalDestructionExecutor(
                    filesystem,
                    work,
                    renderer,  # type: ignore[arg-type]
                    terraform,
                    FakeProvider(),
                    FakeDns(),
                    terminal,
                    waiter,
                ),
            )
            with mock.patch(
                "infrastructure.operator.local_destruction_commands.deployed_outputs",
                return_value=OUTPUTS,
            ):
                result = lifecycle.destroy_current("staging")

        self.assertEqual(result.outcome, "destroyed")
        self.assertEqual(result.last_closed_stage, "destruction-readback")
        self.assertEqual(
            renderer.modes,
            [
                "shared-edge-unlock",
                "shared-edge-remove",
                "platform-unlock",
                "retained",
                "retained",
            ],
        )
        self.assertEqual(
            terraform.applied,
            [
                "shared-edge-unlock",
                "shared-edge-remove",
                "platform-unlock",
                "retained",
            ],
        )
        self.assertEqual(waiter.waits, [30])
        self.assertEqual(len(terminal.pauses), 2)
        self.assertTrue(any("DELETE_DNS_RECORD" in item for item in terminal.messages))
        self.assertTrue(any("DELETE_OAUTH_CLIENT" in item for item in terminal.messages))
        self.assertEqual(len(terminal.confirmations), 5)


if __name__ == "__main__":
    unittest.main()
