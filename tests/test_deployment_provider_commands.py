"""Closed provider-command tests for the interactive staging deployment."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator.deployment_provider import (
    ClosedDeploymentGcloudRunner,
    DeploymentProviderError,
    GcloudDeploymentProvider,
)
from infrastructure.operator.local_deployment import initial_generation
from infrastructure.operator.provider_commands import (
    ProviderCommandRequest,
    ProviderCommandResult,
)


PROJECT = "comfforts-platform-non-prod"
REGION = "us-west1"


@dataclass
class FakeGcloud:
    generation_contents: bytes
    requests: list[ProviderCommandRequest] = field(default_factory=list)
    image_built: bool = False
    bootstrap_backend: bool = False
    enabled_bootstrap_services: tuple[str, ...] = (
        "serviceusage.googleapis.com",
        "storage.googleapis.com",
        "cloudresourcemanager.googleapis.com",
    )

    def run(self, request: ProviderCommandRequest) -> ProviderCommandResult:
        self.requests.append(request)
        arguments = request.argv[1:]
        if arguments[:2] == ("services", "enable"):
            return ProviderCommandResult(0, b"", b"")
        if arguments[:2] == ("services", "list"):
            return ProviderCommandResult(
                0,
                ("\n".join(self.enabled_bootstrap_services) + "\n").encode(),
                b"",
            )
        if arguments[:2] == ("storage", "cp"):
            if request.stdin != self.generation_contents:
                return ProviderCommandResult(1, b"", b"wrong secret contents")
            return ProviderCommandResult(0, b"", b"")
        if arguments[:3] == ("storage", "buckets", "describe"):
            if not self.bootstrap_backend:
                return ProviderCommandResult(1, b"", b"not found")
            return ProviderCommandResult(
                0,
                b"comfforts-ap-stg-455651441682-platform-state\n",
                b"",
            )
        if arguments[:3] == ("storage", "objects", "describe"):
            return ProviderCommandResult(0, b'{"generation":"42"}', b"")
        if arguments[:2] == ("storage", "cat"):
            return ProviderCommandResult(0, self.generation_contents, b"")
        if arguments[:4] == ("kms", "keys", "versions", "list"):
            name = (
                f"projects/{PROJECT}/locations/{REGION}/keyRings/app-platform/"
                "cryptoKeys/edge-signing/cryptoKeyVersions/1"
            )
            return ProviderCommandResult(
                0,
                json.dumps([{"name": name, "state": "ENABLED"}]).encode(),
                b"",
            )
        if arguments[:3] == ("kms", "keyrings", "describe"):
            name = (
                f"projects/{PROJECT}/locations/{REGION}/keyRings/app-platform"
            )
            return ProviderCommandResult(0, (name + "\n").encode(), b"")
        if arguments[:3] == ("secrets", "versions", "list"):
            name = f"projects/{PROJECT}/secrets/app-platform-edge-oauth/versions/1"
            return ProviderCommandResult(0, json.dumps([{"name": name}]).encode(), b"")
        if arguments[:3] == ("compute", "ssl-certificates", "describe"):
            return ProviderCommandResult(
                0,
                json.dumps(
                    {
                        "managed": {
                            "domains": ["apps-staging.comfforts.com"],
                            "status": "ACTIVE",
                        },
                        "selfLink": f"https://compute.googleapis.com/{PROJECT}/certificate",
                    }
                ).encode(),
                b"",
            )
        if arguments[:4] == ("artifacts", "docker", "images", "describe"):
            if not self.image_built:
                return ProviderCommandResult(1, b"", b"not found")
            return ProviderCommandResult(0, b"sha256:" + b"d" * 64 + b"\n", b"")
        if arguments[:2] == ("builds", "submit"):
            self.image_built = True
            return ProviderCommandResult(0, b"{}", b"")
        return ProviderCommandResult(2, b"", b"unexpected secret output")


class DeploymentProviderCommandsTest(unittest.TestCase):
    def _provider(
        self,
        directory: str,
        fake: FakeGcloud,
    ) -> GcloudDeploymentProvider:
        root = Path(directory)
        executable = root / "gcloud"
        executable.write_bytes(b"binary")
        executable.chmod(0o700)
        configuration = root / "cloud-sdk"
        configuration.mkdir(mode=0o700)
        return GcloudDeploymentProvider(
            executable=executable,
            cloud_sdk_configuration=configuration,
            working_root=root,
            runner=fake,
        )

    def test_bootstrap_services_are_exact_and_read_back(self) -> None:
        generation = initial_generation("a" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            provider.enable_bootstrap_services()
            ready = provider.bootstrap_services_ready()

        self.assertTrue(ready)
        mutation = fake.requests[0]
        self.assertEqual(
            mutation.argv[1:6],
            (
                "services",
                "enable",
                "serviceusage.googleapis.com",
                "storage.googleapis.com",
                "cloudresourcemanager.googleapis.com",
            ),
        )
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", dict(mutation.environment))
        self.assertFalse(
            any(value.startswith("--impersonate-service-account=") for value in mutation.argv)
        )
        readback = fake.requests[1]
        self.assertEqual(
            readback.argv[1:6],
            (
                "services",
                "list",
                "--enabled",
                "--filter=config.name=serviceusage.googleapis.com OR "
                "config.name=storage.googleapis.com OR "
                "config.name=cloudresourcemanager.googleapis.com",
                "--format=value(config.name)",
            ),
        )

    def test_bootstrap_service_readback_requires_every_service(self) -> None:
        generation = initial_generation("a" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                generation.contents,
                enabled_bootstrap_services=(
                    "serviceusage.googleapis.com",
                    "storage.googleapis.com",
                ),
            )
            provider = self._provider(directory, fake)

            ready = provider.bootstrap_services_ready()

        self.assertFalse(ready)

    def test_bootstrap_backend_readback_distinguishes_first_run_and_recovery(self) -> None:
        generation = initial_generation("f" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            first_run = provider.bootstrap_backend_ready()
            fake.bootstrap_backend = True
            recovery = provider.bootstrap_backend_ready()

        self.assertFalse(first_run)
        self.assertTrue(recovery)

    def test_initial_generation_is_create_only_and_content_verified(self) -> None:
        generation = initial_generation("b" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            reference = provider.publish_initial_generation(generation)

        self.assertEqual(reference, generation.reference(42))
        upload = fake.requests[0]
        self.assertEqual(upload.argv[1:3], ("storage", "cp"))
        self.assertIn("--if-generation-match=0", upload.argv)
        self.assertEqual(upload.stdin, generation.contents)

    def test_existing_empty_generation_is_reused_across_source_revisions(self) -> None:
        existing = initial_generation("a" * 40)
        requested = initial_generation("b" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(existing.contents)
            provider = self._provider(directory, fake)

            reference = provider.publish_initial_generation(requested)

        self.assertEqual(reference, existing.reference(42))

    def test_existing_generation_must_be_the_valid_empty_generation(self) -> None:
        requested = initial_generation("b" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(b"{}")
            provider = self._provider(directory, fake)

            with self.assertRaisesRegex(
                DeploymentProviderError,
                "INITIAL_GENERATION_READBACK_INVALID",
            ):
                provider.publish_initial_generation(requested)

    def test_non_secret_versions_and_certificate_are_closed_readbacks(self) -> None:
        generation = initial_generation("c" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            key_ring = provider.signing_key_ring_identity()
            signing = provider.active_signing_key_version()
            secret = provider.oauth_secret_version()
            certificate = provider.certificate_readback()

        self.assertEqual(
            key_ring,
            f"projects/{PROJECT}/locations/{REGION}/keyRings/app-platform",
        )
        self.assertTrue(signing.endswith("/cryptoKeyVersions/1"))
        self.assertTrue(secret.endswith("/versions/1"))
        self.assertTrue(certificate.ready)
        self.assertNotIn("secret payload", repr((signing, secret, certificate)))

    def test_shared_edge_build_is_source_tagged_and_returns_only_digest_reference(
        self,
    ) -> None:
        generation = initial_generation("d" * 40)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "infrastructure/images/shared-edge/cloudbuild.yaml"
            config.parent.mkdir(parents=True)
            config.write_text("steps: []\n", encoding="utf-8")
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            reference = provider.publish_shared_edge_image("e" * 40)
            resumed = provider.publish_shared_edge_image("e" * 40)

        self.assertEqual(reference, resumed)
        self.assertTrue(reference.endswith("@sha256:" + "d" * 64))
        builds = [
            request
            for request in fake.requests
            if request.argv[1:3] == ("builds", "submit")
        ]
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0].timeout_seconds, 900)
        self.assertIn(
            "--substitutions=_IMAGE=us-west1-docker.pkg.dev/"
            "comfforts-platform-non-prod/app-platform-images/shared-edge:source-"
            + "e" * 40,
            builds[0].argv,
        )

    def test_fixture_build_is_source_bound_and_returns_only_digest_reference(self) -> None:
        generation = initial_generation("d" * 40)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "infrastructure/images/fixture/cloudbuild.yaml"
            config.parent.mkdir(parents=True)
            config.write_text("steps: []\n", encoding="utf-8")
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            reference = provider.publish_fixture_image("f" * 40)
            resumed = provider.publish_fixture_image("f" * 40)

        self.assertEqual(reference, resumed)
        self.assertEqual(
            reference,
            "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
            "app-platform-images/fixture@sha256:" + ("d" * 64),
        )
        builds = [
            request
            for request in fake.requests
            if request.argv[1:3] == ("builds", "submit")
        ]
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0].timeout_seconds, 900)
        self.assertIn(
            "--substitutions=_IMAGE=us-west1-docker.pkg.dev/"
            "comfforts-platform-non-prod/app-platform-images/fixture:source-"
            + ("f" * 40)
            + ",_SOURCE_REVISION="
            + ("f" * 40),
            builds[0].argv,
        )

    def test_closed_runner_rejects_session_switch_and_unapproved_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "gcloud"
            executable.write_bytes(b"binary")
            configuration = root / "cloud-sdk"
            configuration.mkdir()
            runner = ClosedDeploymentGcloudRunner(executable, root, configuration)
            environment = (
                ("CLOUDSDK_CONFIG", str(configuration.resolve())),
                ("CLOUDSDK_CORE_DISABLE_PROMPTS", "1"),
                ("CLOUDSDK_PYTHON_SITEPACKAGES", "0"),
            )
            unsafe = (
                ProviderCommandRequest(
                    (str(executable), "projects", "delete", PROJECT),
                    root,
                    environment,
                ),
                ProviderCommandRequest(
                    (
                        str(executable),
                        "services",
                        "enable",
                        "storage.googleapis.com",
                        "--impersonate-service-account=not-human@example.com",
                    ),
                    root,
                    environment,
                ),
            )

            for request in unsafe:
                with self.subTest(argv=request.argv), self.assertRaises(ValueError):
                    runner.validate(request)


if __name__ == "__main__":
    unittest.main()
