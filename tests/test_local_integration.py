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
from infrastructure.operator.local_integration import LocalPlatformIntegrationReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class FakeStatus:
    def __init__(self, progress_digest: str) -> None:
        self._progress_digest = progress_digest

    def status(self, environment: str) -> StatusResult:
        return StatusResult(
            {
                "environment": environment,
                "progress_digest": self._progress_digest,
                "lifecycle_state": "deployed",
                "profile_digest": "sha256:" + ("1" * 64),
                "source_authority": "accepted",
                "source_revision": "a" * 40,
                "specification_digest": "sha256:" + ("2" * 64),
            }
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


if __name__ == "__main__":
    unittest.main()
