"""Focused application-project bootstrap and connection lifecycle tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import unittest

from infrastructure.operator.project_connections import (
    ApplicationProjectLifecycle,
    ApplicationProjectReadback,
    PLATFORM_PROJECT_ID,
)
from infrastructure.operator.local_project_connections import (
    GcloudApplicationProjectProvider,
    ProjectCommandError,
)
from tests.environment import FIXTURES_PROJECT_ID


class Terminal:
    def __init__(self, confirmed: bool = True) -> None:
        self.confirmed = confirmed
        self.messages: list[str] = []

    def ask(self, prompt: str) -> str:
        raise AssertionError(prompt)

    def confirm(self, prompt: str) -> bool:
        self.messages.append(prompt)
        return self.confirmed

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        raise AssertionError((prompt, expected))

    def write(self, message: str) -> None:
        self.messages.append(message)

    def pause(self, prompt: str) -> None:
        raise AssertionError(prompt)


class Store:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def write_connection(self, document: dict[str, object]) -> str:
        self.documents.append(document)
        return "/private/project-connection.v1.json"


class Provider:
    def __init__(self, readback: ApplicationProjectReadback) -> None:
        self.readback = readback
        self.bootstraps = 0
        self.connections = 0

    def read_project(self, project_id: str) -> ApplicationProjectReadback:
        return replace(self.readback, project_id=project_id)

    def bootstrap_fixture_project(self, project_id: str) -> None:
        self.bootstraps += 1
        self.readback = ApplicationProjectReadback(
            project_id,
            True,
            "123456789012",
            "organization/123456789",
            "billingAccounts/AAAAAA-BBBBBB-CCCCCC",
            (
                "artifactregistry.googleapis.com",
                "cloudbuild.googleapis.com",
                "cloudresourcemanager.googleapis.com",
                "compute.googleapis.com",
                "iam.googleapis.com",
                "run.googleapis.com",
                "serviceusage.googleapis.com",
                "storage.googleapis.com",
            ),
            True,
            True,
            fixture_ownership_matches=True,
        )

    def connect_project(self, project_id: str, project_number: str) -> None:
        self.connections += 1
        self.readback = replace(
            self.readback,
            project_id=project_id,
            project_number=project_number,
            host_project_id=PLATFORM_PROJECT_ID,
            network_viewer_granted=True,
            subnet_user_granted=True,
        )


class ApplicationProjectLifecycleTest(unittest.TestCase):
    def test_fixture_bootstrap_uses_the_bounded_storage_command(self) -> None:
        class RecordingProvider(GcloudApplicationProjectProvider):
            def __init__(self, root: Path) -> None:
                super().__init__(
                    root / "gcloud",
                    root / "config",
                    root,
                    FIXTURES_PROJECT_ID,
                )
                self.commands: list[tuple[str, ...]] = []

            def _json(self, *arguments: str) -> object | None:
                if arguments == ("projects", "describe", PLATFORM_PROJECT_ID):
                    return {"parent": {"type": "organization", "id": "123"}}
                if arguments == (
                    "billing",
                    "projects",
                    "describe",
                    PLATFORM_PROJECT_ID,
                ):
                    return {"billingAccountName": "billingAccounts/ABCDEF-ABCDEF-ABCDEF"}
                return None

            def _run(self, *arguments: str, check: bool = True):  # type: ignore[no-untyped-def]
                del check
                self.commands.append(arguments)
                return subprocess.CompletedProcess(arguments, 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            provider = RecordingProvider(Path(directory))
            provider.bootstrap_fixture_project(FIXTURES_PROJECT_ID)

        update = next(
            command
            for command in provider.commands
            if command[:3] == ("storage", "buckets", "update")
        )
        self.assertIn("--default-storage-class=STANDARD", update)
        self.assertIn("--uniform-bucket-level-access", update)
        self.assertIn("--public-access-prevention", update)
        self.assertIn("--versioning", update)
        self.assertFalse(
            any(command[:2] == ("storage", "storage") for command in provider.commands)
        )

    def test_fixture_bootstrap_refuses_an_existing_project_under_another_parent(self) -> None:
        class ConflictingProvider(GcloudApplicationProjectProvider):
            def _json(self, *arguments: str) -> object | None:
                if arguments == ("projects", "describe", PLATFORM_PROJECT_ID):
                    return {"parent": {"type": "organization", "id": "123"}}
                if arguments == (
                    "billing",
                    "projects",
                    "describe",
                    PLATFORM_PROJECT_ID,
                ):
                    return {"billingAccountName": "billingAccounts/ABCDEF-ABCDEF-ABCDEF"}
                if arguments == ("projects", "describe", FIXTURES_PROJECT_ID):
                    return {"parent": {"type": "folder", "id": "456"}}
                return None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = ConflictingProvider(
                root / "gcloud",
                root / "config",
                root,
                FIXTURES_PROJECT_ID,
            )
            with self.assertRaisesRegex(
                ProjectCommandError,
                "FIXTURE_PROJECT_PARENT_CONFLICT",
            ):
                provider.bootstrap_fixture_project(FIXTURES_PROJECT_ID)

    def test_fixture_state_bucket_requires_complete_recovery_posture(self) -> None:
        bucket = {
            "projectNumber": "123456789012",
            "location": "US-WEST1",
            "storageClass": "STANDARD",
            "labels": {
                "environment": "qualification",
                "managed_by": "apps-platform-operator",
                "state_owner": "application",
            },
            "iamConfiguration": {
                "publicAccessPrevention": "enforced",
                "uniformBucketLevelAccess": {"enabled": True},
            },
            "versioning": {"enabled": True},
            "lifecycle": {
                "rule": [
                    {
                        "action": {"type": "Delete"},
                        "condition": {
                            "daysSinceNoncurrentTime": 90,
                            "numNewerVersions": 20,
                        },
                    }
                ]
            },
        }

        self.assertTrue(
            GcloudApplicationProjectProvider._bucket_ready(
                bucket,
                "123456789012",
            )
        )
        bucket["versioning"] = {"enabled": False}
        self.assertFalse(
            GcloudApplicationProjectProvider._bucket_ready(
                bucket,
                "123456789012",
            )
        )

    def test_fixture_image_repository_requires_immutable_tags(self) -> None:
        repository = {
            "name": (
                f"projects/{FIXTURES_PROJECT_ID}/locations/us-west1/"
                "repositories/app-platform-images"
            ),
            "format": "DOCKER",
            "labels": {
                "environment": "qualification",
                "state_owner": "application",
            },
            "dockerConfig": {"immutableTags": True},
        }

        self.assertTrue(
            GcloudApplicationProjectProvider._repository_ready(
                repository,
                FIXTURES_PROJECT_ID,
            )
        )
        repository["dockerConfig"] = {"immutableTags": False}
        self.assertFalse(
            GcloudApplicationProjectProvider._repository_ready(
                repository,
                FIXTURES_PROJECT_ID,
            )
        )

    def test_project_number_is_provider_readback_not_fixture_configuration(self) -> None:
        class ReadbackProvider(GcloudApplicationProjectProvider):
            def _json(self, *arguments: str) -> object | None:
                if arguments == ("projects", "describe", FIXTURES_PROJECT_ID):
                    return {
                        "projectNumber": "987654321098",
                        "parent": {"type": "organization", "id": "123"},
                    }
                if arguments == ("projects", "describe", PLATFORM_PROJECT_ID):
                    return {"parent": {"type": "organization", "id": "123"}}
                if arguments == (
                    "billing",
                    "projects",
                    "describe",
                    FIXTURES_PROJECT_ID,
                ):
                    return {
                        "billingAccountName": "billingAccounts/ABCDEF-ABCDEF-ABCDEF"
                    }
                if arguments == (
                    "billing",
                    "projects",
                    "describe",
                    PLATFORM_PROJECT_ID,
                ):
                    return {
                        "billingAccountName": "billingAccounts/ABCDEF-ABCDEF-ABCDEF"
                    }
                return None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readback = ReadbackProvider(
                root / "gcloud",
                root / "config",
                root,
                FIXTURES_PROJECT_ID,
            ).read_project(FIXTURES_PROJECT_ID)

        self.assertEqual(readback.project_number, "987654321098")

    def test_fixture_bootstrap_is_explicit_idempotent_and_creates_no_runtime(self) -> None:
        provider = Provider(ApplicationProjectReadback(FIXTURES_PROJECT_ID, False))
        terminal = Terminal()
        lifecycle = ApplicationProjectLifecycle(provider, Store(), terminal)

        created = lifecycle.bootstrap_fixture("staging", FIXTURES_PROJECT_ID)
        unchanged = lifecycle.bootstrap_fixture("staging", FIXTURES_PROJECT_ID)

        self.assertEqual(created.outcome, "bootstrapped")
        self.assertEqual(unchanged.outcome, "unchanged")
        self.assertEqual(provider.bootstraps, 1)
        self.assertIn("no application runtime exists", " ".join(terminal.messages))

    def test_connection_records_only_verified_shared_vpc_binding(self) -> None:
        provider = Provider(
            ApplicationProjectReadback(
                FIXTURES_PROJECT_ID,
                True,
                "123456789012",
                "organization/123456789",
                "billingAccounts/AAAAAA-BBBBBB-CCCCCC",
            )
        )
        store = Store()
        lifecycle = ApplicationProjectLifecycle(provider, store, Terminal())

        result = lifecycle.connect("staging", FIXTURES_PROJECT_ID)

        self.assertEqual(result.outcome, "connected")
        self.assertEqual(provider.connections, 1)
        self.assertEqual(store.documents[0]["host_project_id"], PLATFORM_PROJECT_ID)
        self.assertEqual(store.documents[0]["egress_mode"], "all-traffic")
        self.assertIs(store.documents[0]["network_viewer_granted"], True)
        self.assertIs(store.documents[0]["subnet_user_granted"], True)

    def test_connection_fails_closed_for_another_shared_vpc_owner(self) -> None:
        provider = Provider(
            ApplicationProjectReadback(
                FIXTURES_PROJECT_ID,
                True,
                "123456789012",
                host_project_id="another-host-project",
            )
        )
        result = ApplicationProjectLifecycle(
            provider,
            Store(),
            Terminal(),
        ).connect("staging", FIXTURES_PROJECT_ID)

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(
            result.blockers,
            ("APPLICATION_PROJECT_NETWORK_OWNER_CONFLICT",),
        )
        self.assertEqual(provider.connections, 0)

    def test_connection_refuses_the_platform_host_project(self) -> None:
        provider = Provider(
            ApplicationProjectReadback(
                PLATFORM_PROJECT_ID,
                True,
                "455651441682",
            )
        )

        result = ApplicationProjectLifecycle(
            provider,
            Store(),
            Terminal(),
        ).connect("staging", PLATFORM_PROJECT_ID)

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(
            result.blockers,
            ("APPLICATION_PROJECT_MUST_BE_SEPARATE",),
        )
        self.assertEqual(provider.connections, 0)


if __name__ == "__main__":
    unittest.main()
