"""Closed provider-command tests for the interactive staging deployment."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import stat
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
from tests.environment import FIXTURES_PROJECT_ID


PROJECT = "comfforts-platform-non-prod"
PROJECT_NUMBER = "455651441682"
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
    oauth_secret_project: str = PROJECT
    certificate_status: str = "ACTIVE"
    certificate_domain_status: str = "ACTIVE"
    build_stdout: bytes = b""
    build_stderr: bytes | None = None
    member_role_permissions: tuple[str, ...] = ("datastore.entities.get",)
    member_role_stage: str = "GA"
    member_session_condition: str = (
        "resource.name == 'projects/comfforts-platform-non-prod/"
        "databases/(default)'"
    )
    member_database_condition: str = (
        "resource.name == 'projects/comfforts-platform-non-prod/"
        "databases/app-platform-members'"
    )
    extra_runtime_role: str | None = None

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
            name = (
                f"projects/{self.oauth_secret_project}/secrets/"
                "app-platform-edge-oauth/versions/1"
            )
            return ProviderCommandResult(0, json.dumps([{"name": name}]).encode(), b"")
        if arguments[:3] == ("iam", "roles", "describe"):
            return ProviderCommandResult(
                0,
                json.dumps(
                    {
                        "name": (
                            f"projects/{PROJECT}/roles/"
                            "appPlatformMemberReader"
                        ),
                        "stage": self.member_role_stage,
                        "includedPermissions": list(
                            self.member_role_permissions
                        ),
                    }
                ).encode(),
                b"",
            )
        if arguments[:2] == ("projects", "get-iam-policy"):
            principal = (
                "serviceAccount:app-platform-edge-runtime@"
                f"{PROJECT}.iam.gserviceaccount.com"
            )
            bindings = [
                {
                    "role": "roles/datastore.user",
                    "members": [principal],
                    "condition": {
                        "title": "app_platform_session_database",
                        "expression": self.member_session_condition,
                    },
                },
                {
                    "role": (
                        f"projects/{PROJECT}/roles/"
                        "appPlatformMemberReader"
                    ),
                    "members": [principal],
                    "condition": {
                        "title": "app_platform_member_database",
                        "expression": self.member_database_condition,
                    },
                },
            ]
            if self.extra_runtime_role is not None:
                bindings.append(
                    {
                        "role": self.extra_runtime_role,
                        "members": [principal],
                    }
                )
            return ProviderCommandResult(
                0,
                json.dumps({"bindings": bindings}).encode(),
                b"",
            )
        if arguments[:3] == ("compute", "ssl-certificates", "describe"):
            return ProviderCommandResult(
                0,
                json.dumps(
                    {
                        "managed": {
                            "domains": ["apps-staging.comfforts.com"],
                            "domainStatus": {
                                "apps-staging.comfforts.com": (
                                    self.certificate_domain_status
                                ),
                            },
                            "status": self.certificate_status,
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
            if self.build_stderr is not None:
                return ProviderCommandResult(
                    1,
                    self.build_stdout,
                    self.build_stderr,
                )
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
            fixture_project_id=FIXTURES_PROJECT_ID,
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
            member_iam = provider.member_directory_iam_readback()
            certificate = provider.certificate_readback()

        self.assertEqual(
            key_ring,
            f"projects/{PROJECT}/locations/{REGION}/keyRings/app-platform",
        )
        self.assertTrue(signing.endswith("/cryptoKeyVersions/1"))
        self.assertTrue(secret.endswith("/versions/1"))
        self.assertEqual(
            member_iam.member_permissions,
            ("datastore.entities.get",),
        )
        self.assertEqual(
            member_iam.member_role,
            f"projects/{PROJECT}/roles/appPlatformMemberReader",
        )
        self.assertTrue(certificate.ready)
        self.assertEqual(certificate.status, "ACTIVE")
        self.assertEqual(certificate.domain_status, "ACTIVE")
        self.assertNotIn("secret payload", repr((signing, secret, certificate)))

    def test_member_directory_readback_rejects_broader_runtime_access(self) -> None:
        generation = initial_generation("c" * 40)
        failures = (
            {
                "member_role_permissions": (
                    "datastore.entities.get",
                    "datastore.entities.list",
                ),
                "expected": "MEMBER_DIRECTORY_IAM_READBACK_INVALID",
            },
            {
                "member_role_permissions": (
                    "datastore.entities.get",
                    "datastore.entities.update",
                ),
                "expected": "MEMBER_DIRECTORY_IAM_READBACK_INVALID",
            },
            {
                "member_session_condition": "resource.name != ''",
                "expected": "MEMBER_DIRECTORY_IAM_READBACK_MISMATCH",
            },
            {
                "member_database_condition": "resource.name != ''",
                "expected": "MEMBER_DIRECTORY_IAM_READBACK_MISMATCH",
            },
            {
                "extra_runtime_role": "roles/datastore.viewer",
                "expected": "MEMBER_DIRECTORY_IAM_READBACK_MISMATCH",
            },
        )
        for values in failures:
            with self.subTest(values=values):
                expected = str(values["expected"])
                options = {
                    key: value
                    for key, value in values.items()
                    if key != "expected"
                }
                with tempfile.TemporaryDirectory() as directory:
                    provider = self._provider(
                        directory,
                        FakeGcloud(generation.contents, **options),
                    )
                    with self.assertRaisesRegex(
                        DeploymentProviderError,
                        expected,
                    ):
                        provider.member_directory_iam_readback()

    def test_certificate_readback_distinguishes_provisioning_from_failure(self) -> None:
        generation = initial_generation("c" * 40)
        with tempfile.TemporaryDirectory() as directory:
            provisioning = self._provider(
                directory,
                FakeGcloud(
                    generation.contents,
                    certificate_status="PROVISIONING",
                    certificate_domain_status="PROVISIONING",
                ),
            ).certificate_readback()

        self.assertFalse(provisioning.ready)
        self.assertEqual(provisioning.status, "PROVISIONING")
        self.assertEqual(provisioning.domain_status, "PROVISIONING")

        failures = (
            (
                "PROVISIONING_FAILED",
                "FAILED_NOT_VISIBLE",
                "CERTIFICATE_PROVISIONING_FAILED",
            ),
            (
                "PROVISIONING_FAILED_PERMANENTLY",
                "FAILED_NOT_VISIBLE",
                "CERTIFICATE_PROVISIONING_FAILED_PERMANENTLY",
            ),
            (
                "RENEWAL_FAILED",
                "FAILED_CAA_FORBIDDEN",
                "CERTIFICATE_RENEWAL_FAILED",
            ),
            (
                "PROVISIONING",
                "FAILED_NOT_VISIBLE",
                "CERTIFICATE_DOMAIN_NOT_VISIBLE",
            ),
            (
                "PROVISIONING",
                "FAILED_CAA_FORBIDDEN",
                "CERTIFICATE_DOMAIN_CAA_FORBIDDEN",
            ),
            (
                "PROVISIONING",
                "FAILED_RATE_LIMITED",
                "CERTIFICATE_DOMAIN_RATE_LIMITED",
            ),
        )
        for status, domain_status, blocker in failures:
            with self.subTest(status=status, domain_status=domain_status):
                with tempfile.TemporaryDirectory() as directory:
                    provider = self._provider(
                        directory,
                        FakeGcloud(
                            generation.contents,
                            certificate_status=status,
                            certificate_domain_status=domain_status,
                        ),
                    )
                    with self.assertRaisesRegex(DeploymentProviderError, blocker):
                        provider.certificate_readback()

    def test_oauth_secret_version_accepts_project_number_and_normalizes_reference(
        self,
    ) -> None:
        generation = initial_generation("c" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                generation.contents,
                oauth_secret_project=PROJECT_NUMBER,
            )
            provider = self._provider(directory, fake)

            secret = provider.oauth_secret_version()

        self.assertEqual(
            secret,
            f"projects/{PROJECT}/secrets/app-platform-edge-oauth/versions/1",
        )

    def test_oauth_secret_version_rejects_another_project(self) -> None:
        generation = initial_generation("c" * 40)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                generation.contents,
                oauth_secret_project="999999999999",
            )
            provider = self._provider(directory, fake)

            with self.assertRaisesRegex(
                DeploymentProviderError,
                "OAUTH_SECRET_VERSION_READBACK_INVALID",
            ):
                provider.oauth_secret_version()

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
            f"us-west1-docker.pkg.dev/{FIXTURES_PROJECT_ID}/"
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
            f"{FIXTURES_PROJECT_ID}/app-platform-images/fixture:source-"
            + ("f" * 40)
            + ",_SOURCE_REVISION="
            + ("f" * 40),
            builds[0].argv,
        )

    def test_fixture_build_reports_local_config_type_failure_exactly(self) -> None:
        generation = initial_generation("d" * 40)
        diagnostic = (
            b"interpreting cloudbuild.yaml as build config: "
            b"Expected type <class 'str'> for field value, found 0"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "infrastructure/images/fixture/cloudbuild.yaml"
            config.parent.mkdir(parents=True)
            config.write_text("steps: []\n", encoding="utf-8")
            fake = FakeGcloud(generation.contents, build_stderr=diagnostic)
            provider = self._provider(directory, fake)

            with self.assertRaisesRegex(
                DeploymentProviderError,
                "^FIXTURE_IMAGE_BUILD_CONFIG_INVALID$",
            ):
                provider.publish_fixture_image("f" * 40)

    def test_fixture_build_failure_persists_private_diagnostics(self) -> None:
        generation = initial_generation("d" * 40)
        stdout = b"remote build identifier\n"
        stderr = b"client_secret=must-remain-private\nremote build failed\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "infrastructure/images/fixture/cloudbuild.yaml"
            config.parent.mkdir(parents=True)
            config.write_text("steps: []\n", encoding="utf-8")
            state = root / ".platform-operator"
            state.mkdir(mode=0o700)
            fake = FakeGcloud(
                generation.contents,
                build_stdout=stdout,
                build_stderr=stderr,
            )
            executable = root / "gcloud"
            executable.write_bytes(b"binary")
            executable.chmod(0o700)
            configuration = root / "cloud-sdk"
            configuration.mkdir(mode=0o700)
            provider = GcloudDeploymentProvider(
                executable=executable,
                cloud_sdk_configuration=configuration,
                working_root=root,
                runner=fake,
                fixture_project_id=FIXTURES_PROJECT_ID,
                private_state_root=state,
            )

            with self.assertRaisesRegex(
                DeploymentProviderError,
                "^FIXTURE_IMAGE_BUILD_FAILED$",
            ) as raised:
                provider.publish_fixture_image("f" * 40)

            diagnostic_path = Path(raised.exception.diagnostic["diagnostic_path"])
            stdout_path = Path(
                raised.exception.diagnostic["diagnostic_stdout_path"]
            )
            event = diagnostic_path.parent
            manifest = json.loads(
                (event / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(diagnostic_path.read_bytes(), stderr)
            self.assertEqual(stdout_path.read_bytes(), stdout)
            self.assertEqual(stat.S_IMODE(event.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(diagnostic_path.stat().st_mode), 0o600)
            self.assertEqual(manifest["operation"], "cloud-build")
            self.assertEqual(manifest["phase"], "fixture-image")
            self.assertNotIn(
                "must-remain-private",
                json.dumps(raised.exception.diagnostic),
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

    def test_closed_runner_allows_only_read_only_member_iam_commands(self) -> None:
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
            safe = (
                ProviderCommandRequest(
                    (
                        str(executable),
                        "iam",
                        "roles",
                        "describe",
                        "appPlatformMemberReader",
                        f"--project={PROJECT}",
                        "--quiet",
                    ),
                    root,
                    environment,
                ),
                ProviderCommandRequest(
                    (
                        str(executable),
                        "projects",
                        "get-iam-policy",
                        PROJECT,
                        f"--project={PROJECT}",
                        "--quiet",
                    ),
                    root,
                    environment,
                ),
            )

            for request in safe:
                with self.subTest(argv=request.argv):
                    runner.validate(request)


if __name__ == "__main__":
    unittest.main()
