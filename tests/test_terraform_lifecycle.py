"""AP-M9-W5 Terraform lifecycle integration through deterministic command fakes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import unittest

from infrastructure.backend import (
    EnvironmentUnavailableError,
    PhasePlanRequest,
    prepare_phase_plan,
)


SOURCE_REVISION = "3" * 40
RESOURCE_TYPES = {
    "bootstrap": "google_storage_bucket",
    "platform-foundation": "google_storage_bucket",
    "shared-edge": "google_compute_global_address",
}


@dataclass
class FakeTerraformCommands:
    requests: list[PhasePlanRequest] = field(default_factory=list)
    wrong_project: bool = False

    def observe_plan(self, request: PhasePlanRequest) -> dict[str, object]:
        self.requests.append(request)
        return {
            "environment": request.environment,
            "source_revision": request.source_revision,
            "state_owner": request.state_owner,
            "owner_id": request.owner_id,
            "terraform_root": request.terraform_root,
            "phase": request.phase,
            "provider": {
                "source": "registry.terraform.io/hashicorp/google",
                "service": "google",
                "project_id": (
                    "wrong-project" if self.wrong_project else request.project_id
                ),
                "configuration": "explicit",
            },
            "changes": [
                {
                    "address": f"module.subject.{RESOURCE_TYPES[request.phase]}.subject",
                    "resource_type": RESOURCE_TYPES[request.phase],
                    "provider_source": "registry.terraform.io/hashicorp/google",
                    "actions": ["create"],
                }
            ],
        }


class TerraformLifecycleIntegrationTest(unittest.TestCase):
    def test_fake_plans_bind_backend_policy_and_one_platform_lineage(self) -> None:
        fake = FakeTerraformCommands()
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_root = Path(temporary_directory)
            results = tuple(
                prepare_phase_plan(
                    "staging",
                    phase,
                    SOURCE_REVISION,
                    working_root,
                    fake,
                )
                for phase in ("bootstrap", "platform-foundation", "shared-edge")
            )

        self.assertTrue(all(result.accepted for result in results))
        self.assertTrue(all(result.plan_digest for result in results))
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual(fake.requests[1].backend_digest, fake.requests[2].backend_digest)
        self.assertEqual(fake.requests[1].backend_prefix, "platform")
        self.assertEqual(fake.requests[2].backend_prefix, "platform")
        self.assertNotEqual(fake.requests[0].backend_digest, fake.requests[1].backend_digest)

    def test_policy_refusal_returns_no_consumable_plan_digest(self) -> None:
        fake = FakeTerraformCommands(wrong_project=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = prepare_phase_plan(
                "staging",
                "platform-foundation",
                SOURCE_REVISION,
                Path(temporary_directory),
                fake,
            )

        self.assertFalse(result.accepted)
        self.assertIsNone(result.plan_digest)
        self.assertIn("PROJECT_MISMATCH", [item.code for item in result.violations])

    def test_production_refuses_before_render_or_command_invocation(self) -> None:
        fake = FakeTerraformCommands()
        with tempfile.TemporaryDirectory() as temporary_directory:
            working_root = Path(temporary_directory)
            with self.assertRaisesRegex(
                EnvironmentUnavailableError,
                "OWNERSHIP_TRANSFER_REQUIRED",
            ):
                prepare_phase_plan(
                    "production",
                    "platform-foundation",
                    SOURCE_REVISION,
                    working_root,
                    fake,
                )
            self.assertEqual(fake.requests, [])
            self.assertEqual(tuple(working_root.iterdir()), ())


if __name__ == "__main__":
    unittest.main()
