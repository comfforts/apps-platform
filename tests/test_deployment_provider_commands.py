"""Closed provider-command tests for the interactive staging deployment."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator.deployment_provider import (
    ClosedDeploymentGcloudRunner,
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

    def run(self, request: ProviderCommandRequest) -> ProviderCommandResult:
        self.requests.append(request)
        arguments = request.argv[1:]
        if arguments[:2] == ("services", "enable"):
            return ProviderCommandResult(0, b"", b"")
        if arguments[:2] == ("services", "describe"):
            return ProviderCommandResult(0, b"ENABLED\n", b"")
        if arguments[:2] == ("storage", "cp"):
            if request.stdin != self.generation_contents:
                return ProviderCommandResult(1, b"", b"wrong secret contents")
            return ProviderCommandResult(0, b"", b"")
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
            mutation.argv[1:5],
            (
                "services",
                "enable",
                "serviceusage.googleapis.com",
                "storage.googleapis.com",
            ),
        )
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", dict(mutation.environment))
        self.assertFalse(
            any(value.startswith("--impersonate-service-account=") for value in mutation.argv)
        )

    def test_initial_generation_is_create_only_and_content_verified(self) -> None:
        generation = initial_generation("b" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            object_generation = provider.publish_initial_generation(generation)

        self.assertEqual(object_generation, 42)
        upload = fake.requests[0]
        self.assertEqual(upload.argv[1:3], ("storage", "cp"))
        self.assertIn("--if-generation-match=0", upload.argv)
        self.assertEqual(upload.stdin, generation.contents)

    def test_non_secret_versions_and_certificate_are_closed_readbacks(self) -> None:
        generation = initial_generation("c" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(generation.contents)
            provider = self._provider(directory, fake)

            signing = provider.active_signing_key_version()
            secret = provider.oauth_secret_version()
            certificate = provider.certificate_readback()

        self.assertTrue(signing.endswith("/cryptoKeyVersions/1"))
        self.assertTrue(secret.endswith("/versions/1"))
        self.assertTrue(certificate.ready)
        self.assertNotIn("secret payload", repr((signing, secret, certificate)))

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
