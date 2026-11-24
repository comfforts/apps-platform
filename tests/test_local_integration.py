"""Local platform integration readback tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator._interfaces import StatusResult
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_deployment import initial_generation
from infrastructure.operator.local_integration import (
    LocalPlatformIntegrationReader,
    PlatformIntegrationReadbackError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class FakeStatus:
    def __init__(
        self,
        progress_digest: str,
        source_revision: str = "a" * 40,
        source_authority: str = "accepted",
        conflicts: tuple[str, ...] = (),
    ) -> None:
        self._progress_digest = progress_digest
        self._source_revision = source_revision
        self._source_authority = source_authority
        self._conflicts = conflicts

    def status(self, environment: str) -> StatusResult:
        return StatusResult(
            {
                "environment": environment,
                "progress_digest": self._progress_digest,
                "lifecycle_state": "deployed",
                "profile_digest": "sha256:" + ("1" * 64),
                "source_authority": self._source_authority,
                "source_revision": self._source_revision,
                "specification_digest": "sha256:" + ("2" * 64),
            },
            self._conflicts,
        )


class FakeGenerations:
    def current(self, environment: str) -> RegistrationGenerationProposal:
        return RegistrationGenerationProposal(
            environment=environment,
            registration_set={"generation": 7, "registrations": []},
            compiled_configuration={},
            ownership_manifest={},
            generation_digest="sha256:" + ("4" * 64),
            content_digest="sha256:" + ("5" * 64),
        )


class RecoverableGenerations:
    def __init__(self, active_platform_source_revision: str = "a" * 40) -> None:
        self.current_proposal: RegistrationGenerationProposal | None = None
        self.bindings: list[tuple[str, int]] = []
        self._active_platform_source_revision = active_platform_source_revision

    def current(self, environment: str) -> RegistrationGenerationProposal | None:
        del environment
        return self.current_proposal

    def bind_deployed_initial(
        self,
        value: RegistrationGenerationProposal,
        *,
        object_name: str,
        object_generation: int,
    ) -> RegistrationGenerationProposal:
        self.bindings.append((object_name, object_generation))
        self.current_proposal = value
        return value

    def active_platform_source_revision(self, environment: str) -> str:
        del environment
        return self._active_platform_source_revision


class LocalPlatformIntegrationReaderTest(unittest.TestCase):
    def test_reads_deployed_progress_and_rejects_digest_drift(self) -> None:
        progress = {
            "progress_version": 1,
            "environment": "staging",
            "operation": "deploy",
            "source_revision": "a" * 40,
            "specification_digest": "sha256:" + ("2" * 64),
            "status": "succeeded",
            "completed": [
                {
                    "stage_id": "oauth-configuration",
                    "outputs": [
                        {
                            "name": "oauth-client-id",
                            "value": "client.apps.googleusercontent.com",
                        },
                        {
                            "name": "oauth-secret-version",
                            "value": "projects/example/secrets/client/versions/1",
                        },
                    ],
                    "plan_digest": "sha256:" + ("9" * 64),
                    "manual_acknowledgement": "operator-attested",
                }
            ],
            "active_stage": None,
            "blockers": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            filesystem = LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
            filesystem.write_state(
                "environments/staging/current-progress.v1.json",
                json.dumps(progress, sort_keys=True, separators=(",", ":")).encode()
                + b"\n",
                replace=False,
            )
            reader = LocalPlatformIntegrationReader(
                filesystem,
                FakeStatus(_digest(progress)),
                FakeGenerations(),
            )
            current = reader.read_platform("staging")

            stale = LocalPlatformIntegrationReader(
                filesystem,
                FakeStatus("sha256:" + ("f" * 64)),
                FakeGenerations(),
            )
            with self.assertRaisesRegex(ValueError, "does not match"):
                stale.read_platform("staging")

        self.assertEqual(current.generation, 7)
        self.assertEqual(
            current.oauth_client_id,
            "client.apps.googleusercontent.com",
        )
        self.assertEqual(current.qualification_status, "unqualified")

    def test_recovers_verified_deployed_initial_generation_for_first_handoff(self) -> None:
        initial_source_revision = "a" * 40
        platform_source_revision = "b" * 40
        active_platform_source_revision = "c" * 40
        initial = initial_generation(initial_source_revision)
        progress = {
            "progress_version": 1,
            "environment": "staging",
            "operation": "deploy",
            "source_revision": platform_source_revision,
            "specification_digest": "sha256:" + ("2" * 64),
            "status": "succeeded",
            "completed": [
                {
                    "stage_id": "generation-publish",
                    "outputs": [
                        {
                            "name": "registration-generation-reference",
                            "value": initial.reference(41),
                        }
                    ],
                    "plan_digest": "sha256:" + ("8" * 64),
                    "manual_acknowledgement": "operator-attested",
                },
                {
                    "stage_id": "oauth-configuration",
                    "outputs": [
                        {
                            "name": "oauth-client-id",
                            "value": "client.apps.googleusercontent.com",
                        }
                    ],
                    "plan_digest": "sha256:" + ("9" * 64),
                    "manual_acknowledgement": "operator-attested",
                },
            ],
            "active_stage": None,
            "blockers": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            filesystem = LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
            filesystem.write_state(
                "environments/staging/current-progress.v1.json",
                json.dumps(progress, sort_keys=True, separators=(",", ":")).encode()
                + b"\n",
                replace=False,
            )
            historical_progress = dict(progress)
            historical_progress["source_revision"] = initial_source_revision
            filesystem.write_state(
                "environments/staging/progress/initial.final.v1.json",
                json.dumps(
                    historical_progress,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                + b"\n",
                replace=False,
            )
            generations = RecoverableGenerations(active_platform_source_revision)
            reader = LocalPlatformIntegrationReader(
                filesystem,
                FakeStatus(
                    _digest(progress),
                    platform_source_revision,
                    "candidate",
                    (
                        "SOURCE_AUTHORITY_MISMATCH",
                        "SOURCE_REVISION_MISMATCH",
                    ),
                ),
                generations,
                initial_generation_binder=generations,
            )

            current = reader.read_platform("staging")
            blocked_reader = LocalPlatformIntegrationReader(
                filesystem,
                FakeStatus(
                    _digest(progress),
                    platform_source_revision,
                    "accepted",
                    ("SOURCE_NOT_CLEAN", "SOURCE_REVISION_MISMATCH"),
                ),
                generations,
                initial_generation_binder=generations,
            )
            with self.assertRaisesRegex(
                PlatformIntegrationReadbackError,
                "SOURCE_NOT_CLEAN",
            ):
                blocked_reader.read_platform("staging")

        self.assertEqual(current.generation, 1)
        self.assertEqual(
            current.platform_source_revision,
            active_platform_source_revision,
        )
        self.assertEqual(
            generations.bindings,
            [("generations/1/compiled.json", 41)],
        )
        assert generations.current_proposal is not None
        self.assertEqual(
            generations.current_proposal.generation_digest,
            initial.generation_digest,
        )


if __name__ == "__main__":
    unittest.main()
