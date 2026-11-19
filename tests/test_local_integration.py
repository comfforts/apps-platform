"""Local platform integration readback tests."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator._interfaces import StatusResult
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_integration import LocalPlatformIntegrationReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeStatus:
    def __init__(self, journal_digest: str) -> None:
        self._journal_digest = journal_digest

    def status(self, environment: str) -> StatusResult:
        return StatusResult(
            {
                "environment": environment,
                "journal_digest": self._journal_digest,
                "lifecycle_state": "deployed",
                "profile_digest": "sha256:" + ("1" * 64),
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
    def test_reads_only_closed_platform_outputs_and_reports_unqualified(self) -> None:
        vector = json.loads(
            (
                PROJECT_ROOT
                / "contracts/lifecycle/test-vectors/valid/"
                "execution-journal.staging.synthetic.v1.json"
            ).read_text(encoding="utf-8")
        )
        vector["entries"].append(
            {
                "sequence": 4,
                "stage_id": "oauth-configuration",
                "stage_input_digest": "sha256:" + ("8" * 64),
                "outcome": "succeeded",
                "plan_digest": "sha256:" + ("9" * 64),
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
                "manual_acknowledgement": "operator-attested",
            }
        )
        # Use the canonical lifecycle helper through the production writer's
        # accepted vector rather than hand-building a second journal chain.
        from contracts.lifecycle import canonical_lifecycle_bytes, lifecycle_digest

        digest = lifecycle_digest(vector, "execution-journal")
        specification_digest = str(vector["specification_digest"])
        with tempfile.TemporaryDirectory() as directory:
            filesystem = LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
            filesystem.write_state(
                (
                    "environments/staging/journals/"
                    f"{specification_digest[7:]}/00000001.v1.json"
                ),
                canonical_lifecycle_bytes(vector, "execution-journal") + b"\n",
                replace=False,
            )
            filesystem.write_state(
                "environments/staging/current-journal.v1.json",
                json.dumps(
                    {
                        "journal_digest": digest,
                        "journal_revision": 1,
                        "specification_digest": specification_digest,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n",
                replace=False,
            )
            reader = LocalPlatformIntegrationReader(
                filesystem,
                FakeStatus(digest),
                FakeGenerations(),
            )

            current = reader.read_platform("staging")

        self.assertEqual(current.generation, 7)
        self.assertEqual(
            current.oauth_client_id,
            "client.apps.googleusercontent.com",
        )
        self.assertEqual(current.qualification_status, "unqualified")


if __name__ == "__main__":
    unittest.main()
