"""Closed provider-command tests for immutable registration generations."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator.integration import (
    ApplicationProjectConnection,
    RegistrationGenerationProposal,
)
from infrastructure.operator.provider_commands import (
    ClosedGcloudRunner,
    GcloudGenerationProvider,
    GenerationProviderError,
    ProviderCommandRequest,
    ProviderCommandResult,
)
from tests.environment import FIXTURES_PROJECT_ID


PROJECT_ID = "comfforts-platform-non-prod"
REGION = "us-west1"
SERVICE = "app-platform-edge"
BUCKET = "comfforts-ap-stg-455651441682-configuration"
GENERATION_DIGEST = "sha256:" + ("a" * 64)
CONTENT_DIGEST = "sha256:" + ("b" * 64)
SOURCE_REVISION = "c" * 40
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def proposal() -> RegistrationGenerationProposal:
    compiled = {
        "contract_version": 1,
        "generation": 7,
        "generation_digest": GENERATION_DIGEST,
        "routes": [],
    }
    return RegistrationGenerationProposal(
        environment="staging",
        registration_set={
            "contract_version": 1,
            "generation": 7,
            "proposal": {"source_revision": SOURCE_REVISION},
            "registrations": [],
        },
        compiled_configuration=compiled,
        ownership_manifest={
            "contract_version": 1,
            "generation": 7,
            "resources": [],
        },
        generation_digest=GENERATION_DIGEST,
        content_digest=CONTENT_DIGEST,
    )


@dataclass
class FakeGcloud:
    compiled: bytes
    requests: list[ProviderCommandRequest] = field(default_factory=list)
    object_created: bool = False
    revision_created: bool = False
    active: bool = False
    corrupt_revision: bool = False
    active_source_revision: str = SOURCE_REVISION
    active_image_digest: str = "d" * 64
    service_template_image_digest: str = "d" * 64
    candidate_environment: dict[str, str] | None = None
    candidate_image: str | None = None
    candidate_service_account: str | None = None
    configuration_object_name: str | None = None

    @property
    def revision_name(self) -> str:
        return f"{SERVICE}-g7-{GENERATION_DIGEST[7:19]}"

    def _service(self, traffic: list[dict[str, object]]) -> bytes:
        return _canonical(
            {
                "metadata": {"name": SERVICE},
                "spec": {
                    "template": {
                        "spec": {
                            "serviceAccountName": (
                                f"app-platform-edge-runtime@{PROJECT_ID}."
                                "iam.gserviceaccount.com"
                            ),
                            "containers": [
                                {
                                    "image": (
                                        f"{REGION}-docker.pkg.dev/{PROJECT_ID}/"
                                        "app-platform/shared-edge@sha256:"
                                        + self.service_template_image_digest
                                    )
                                }
                            ],
                        }
                    }
                },
                "status": {"traffic": traffic},
            }
        )

    def _revision(self, revision_name: str) -> bytes:
        object_name = self.configuration_object_name or (
            "environments/staging/generations/7/compiled-shared-edge.v1.json"
        )
        digest = "sha256:" + ("f" * 64) if self.corrupt_revision else GENERATION_DIGEST
        environment = {
            "APP_PLATFORM_CONFIGURATION_BUCKET": BUCKET,
            "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST": CONTENT_DIGEST,
            "APP_PLATFORM_CONFIGURATION_OBJECT": object_name,
            "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION": "42",
            "APP_PLATFORM_GENERATION_DIGEST": digest,
            "APP_PLATFORM_REGISTRATION_GENERATION": "7",
            "APP_PLATFORM_SOURCE_REVISION": SOURCE_REVISION,
            "APP_PLATFORM_IDENTITY_CLIENT_ID": "client.apps.googleusercontent.com",
            "APP_PLATFORM_SIGNING_KEY_VERSION": (
                f"projects/{PROJECT_ID}/locations/{REGION}/keyRings/platform/"
                "cryptoKeys/edge/cryptoKeyVersions/1"
            ),
        }
        image_digest = self.service_template_image_digest
        service_account = (
            f"app-platform-edge-runtime@{PROJECT_ID}.iam.gserviceaccount.com"
        )
        if revision_name == f"{SERVICE}-initial":
            environment["APP_PLATFORM_SOURCE_REVISION"] = (
                self.active_source_revision
            )
            image_digest = self.active_image_digest
        elif self.candidate_environment is not None:
            environment = dict(self.candidate_environment)
            image_digest = self.candidate_image or image_digest
            service_account = self.candidate_service_account or service_account
        return _canonical(
            {
                "metadata": {"name": revision_name},
                "spec": {
                    "serviceAccountName": service_account,
                    "containers": [
                        {
                            "image": (
                                f"{REGION}-docker.pkg.dev/{PROJECT_ID}/"
                                "app-platform/shared-edge@sha256:" + image_digest
                            ),
                            "env": [
                                {"name": name, "value": value}
                                for name, value in sorted(environment.items())
                            ],
                        }
                    ],
                },
            }
        )

    def run(self, request: ProviderCommandRequest) -> ProviderCommandResult:
        self.requests.append(request)
        arguments = request.argv[1:]
        if arguments[:2] == ("storage", "cp"):
            self.assert_closed(request)
            if self.object_created:
                return ProviderCommandResult(1, b"", b"already exists: secret-token")
            self.object_created = True
            if request.stdin != self.compiled:
                return ProviderCommandResult(1, b"", b"wrong input: secret-token")
            return ProviderCommandResult(0, b"", b"")
        if arguments[:3] == ("storage", "objects", "describe"):
            return ProviderCommandResult(0, b'{"generation":"42"}', b"")
        if arguments[:2] == ("storage", "cat"):
            return ProviderCommandResult(0, self.compiled, b"")
        if arguments[:3] == ("run", "services", "describe"):
            traffic = (
                [{"revisionName": self.revision_name, "percent": 100}]
                if self.active
                else [{"revisionName": f"{SERVICE}-initial", "percent": 100}]
            )
            return ProviderCommandResult(0, self._service(traffic), b"")
        if arguments[:3] == ("run", "revisions", "describe"):
            revision_name = arguments[3]
            if (
                revision_name != f"{SERVICE}-initial"
                and not self.revision_created
            ):
                return ProviderCommandResult(1, b"", b"not found: secret-token")
            return ProviderCommandResult(
                0,
                self._revision(revision_name),
                b"",
            )
        if arguments[:3] == ("run", "services", "update"):
            bindings = next(
                (
                    item.split("=", maxsplit=1)[1]
                    for item in arguments
                    if item.startswith("--set-env-vars=")
                    or item.startswith("--update-env-vars=")
                ),
                "",
            )
            if bindings:
                self.candidate_environment = dict(
                    item.split("=", maxsplit=1)
                    for item in bindings.split(",")
                )
            self.candidate_image = next(
                (
                    item.rsplit("@sha256:", maxsplit=1)[1]
                    for item in arguments
                    if item.startswith("--image=")
                ),
                None,
            )
            self.candidate_service_account = next(
                (
                    item.split("=", maxsplit=1)[1]
                    for item in arguments
                    if item.startswith("--service-account=")
                ),
                None,
            )
            self.revision_created = True
            return ProviderCommandResult(0, b"{}", b"")
        if arguments[:3] == ("run", "services", "update-traffic"):
            self.active = True
            return ProviderCommandResult(0, b"{}", b"")
        return ProviderCommandResult(2, b"", b"unexpected: secret-token")

    @staticmethod
    def assert_closed(request: ProviderCommandRequest) -> None:
        names = {name for name, _ in request.environment}
        if names != {
            "CLOUDSDK_CONFIG",
            "CLOUDSDK_CORE_DISABLE_PROMPTS",
            "CLOUDSDK_PYTHON_SITEPACKAGES",
        }:
            raise AssertionError("provider environment is not closed")


class GenerationProviderCommandsTest(unittest.TestCase):
    def _provider(
        self,
        directory: str,
        fake: FakeGcloud,
    ) -> GcloudGenerationProvider:
        root = Path(directory)
        executable = root / "gcloud"
        executable.write_bytes(b"#!/bin/sh\nexit 1\n")
        executable.chmod(0o700)
        configuration = root / "cloud-sdk"
        configuration.mkdir(mode=0o700)
        class Connections:
            @staticmethod
            def read_project_number(
                environment: str,
                project_number: str,
            ) -> ApplicationProjectConnection:
                return ApplicationProjectConnection(
                    environment=environment,
                    project_id=FIXTURES_PROJECT_ID,
                    project_number=project_number,
                    host_project_id=PROJECT_ID,
                    host_project_number="455651441682",
                    region=REGION,
                    network_reference=(
                        f"projects/{PROJECT_ID}/global/networks/app-platform-shared"
                    ),
                    subnetwork_reference=(
                        f"projects/{PROJECT_ID}/regions/{REGION}/subnetworks/"
                        f"app-platform-applications-{REGION}"
                    ),
                    egress_mode="all-traffic",
                )

        return GcloudGenerationProvider(
            executable=executable,
            cloud_sdk_configuration=configuration,
            working_root=root,
            project_id=PROJECT_ID,
            project_number="455651441682",
            region=REGION,
            service_name=SERVICE,
            configuration_bucket=BUCKET,
            runner=fake,
            project_connections=Connections(),
        )

    def test_stage_uses_create_only_object_and_no_traffic_revision(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(compiled)
            provider = self._provider(directory, fake)

            result = provider.stage(proposal(), compiled)

        self.assertTrue(result.created)
        self.assertTrue(result.readback_matches)
        self.assertEqual(result.object_generation, 42)
        mutation = next(
            request
            for request in fake.requests
            if request.argv[1:4] == ("run", "services", "update")
        )
        self.assertIn("--no-traffic", mutation.argv)
        self.assertFalse(
            any(
                argument.startswith("--impersonate-service-account=")
                for argument in mutation.argv
            )
        )
        upload = next(
            request
            for request in fake.requests
            if request.argv[1:3] == ("storage", "cp")
        )
        self.assertEqual(upload.stdin, compiled)
        self.assertIn("--if-generation-match=0", upload.argv)
        self.assertIn(
            f"gs://{BUCKET}/environments/staging/generations/7/"
            "compiled-shared-edge.v1.json",
            upload.argv,
        )
        self.assertNotIn("HOME", dict(upload.environment))
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", dict(upload.environment))

    def test_stage_preserves_active_runtime_instead_of_staged_service_template(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        active_source = "e" * 40
        active_image = "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                compiled,
                active_source_revision=active_source,
                active_image_digest=active_image,
                service_template_image_digest="d" * 64,
            )
            provider = self._provider(directory, fake)

            provider.stage(proposal(), compiled)

        mutation = next(
            request
            for request in fake.requests
            if request.argv[1:4] == ("run", "services", "update")
        )
        self.assertIn(
            f"--image={REGION}-docker.pkg.dev/{PROJECT_ID}/"
            f"app-platform/shared-edge@sha256:{active_image}",
            mutation.argv,
        )
        self.assertIn(
            f"--service-account=app-platform-edge-runtime@{PROJECT_ID}."
            "iam.gserviceaccount.com",
            mutation.argv,
        )
        bindings = next(
            item for item in mutation.argv if item.startswith("--set-env-vars=")
        )
        self.assertIn(
            f"APP_PLATFORM_SOURCE_REVISION={active_source}",
            bindings,
        )
        self.assertNotIn("--update-env-vars=", " ".join(mutation.argv))

    def test_stage_resumes_only_when_existing_object_and_revision_match(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                compiled,
                object_created=True,
                revision_created=True,
            )
            provider = self._provider(directory, fake)

            result = provider.stage(proposal(), compiled)

        self.assertFalse(result.created)
        self.assertFalse(
            any(
                request.argv[1:4] == ("run", "services", "update")
                for request in fake.requests
            )
        )

    def test_activation_moves_exact_traffic_in_verified_operator_session(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                compiled,
                object_created=True,
                revision_created=True,
            )
            provider = self._provider(directory, fake)

            apply = provider.activate(
                "staging",
                fake.revision_name,
                GENERATION_DIGEST,
                "apply",
            )
            rollback = provider.activate(
                "staging",
                fake.revision_name,
                GENERATION_DIGEST,
                "rollback",
            )

        self.assertTrue(apply.activated)
        self.assertTrue(rollback.activated)
        traffic_requests = [
            request
            for request in fake.requests
            if request.argv[1:4] == ("run", "services", "update-traffic")
        ]
        self.assertTrue(
            all(
                not any(
                    argument.startswith("--impersonate-service-account=")
                    for argument in request.argv
                )
                for request in traffic_requests
            )
        )
        self.assertIn(
            f"--to-revisions={fake.revision_name}=100",
            traffic_requests[0].argv,
        )

    def test_revision_binding_mismatch_fails_without_leaking_raw_output(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                compiled,
                object_created=True,
                revision_created=True,
                corrupt_revision=True,
            )
            provider = self._provider(directory, fake)

            with self.assertRaises(GenerationProviderError) as caught:
                provider.stage(proposal(), compiled)

        self.assertNotIn("secret-token", str(caught.exception))
        self.assertEqual(
            str(caught.exception),
            "GENERATION_REVISION_BINDING_MISMATCH",
        )

    def test_qualification_readback_uses_exact_project_and_traffic(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                compiled,
                object_created=True,
                revision_created=True,
                active=True,
            )
            provider = self._provider(directory, fake)

            current = provider.read_current("staging")

        self.assertEqual(current.active_generation_digest, GENERATION_DIGEST)
        self.assertEqual(
            {item.name for item in current.component_revisions},
            {
                "oauth-client",
                "registration-configuration",
                "shared-edge-image",
                "shared-edge-revision",
                "signing-key-version",
            },
        )
        self.assertTrue(
            all(f"--project={PROJECT_ID}" in request.argv for request in fake.requests)
        )
        self.assertTrue(
            all(
                not any(
                    argument.startswith("--impersonate-service-account=")
                    for argument in request.argv
                )
                for request in fake.requests
            )
        )

    def test_reads_exact_active_generation_binding_without_mutation(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                compiled,
                object_created=True,
                revision_created=True,
                active=True,
                configuration_object_name=(
                    f"generations/{GENERATION_DIGEST[7:]}/"
                    "compiled-shared-edge.v1.json"
                ),
            )
            provider = self._provider(directory, fake)

            binding = provider.read_active_binding("staging")

        self.assertEqual(binding.environment, "staging")
        self.assertEqual(binding.revision_name, fake.revision_name)
        self.assertEqual(binding.platform_source_revision, SOURCE_REVISION)
        self.assertEqual(
            binding.image_reference,
            f"{REGION}-docker.pkg.dev/{PROJECT_ID}/app-platform/"
            "shared-edge@sha256:" + "d" * 64,
        )
        self.assertEqual(binding.generation, 7)
        self.assertEqual(binding.generation_digest, GENERATION_DIGEST)
        self.assertEqual(binding.content_digest, CONTENT_DIGEST)
        self.assertEqual(
            binding.object_name,
            f"generations/{GENERATION_DIGEST[7:]}/compiled-shared-edge.v1.json",
        )
        self.assertEqual(binding.object_generation, 42)
        self.assertFalse(
            any(
                request.argv[1:4]
                in {
                    ("run", "services", "update"),
                    ("run", "services", "update-traffic"),
                }
                for request in fake.requests
            )
        )

    def test_reads_one_exact_candidate_revision_binding_without_activation(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeGcloud(
                compiled,
                object_created=True,
                revision_created=True,
                active=False,
            )
            provider = self._provider(directory, fake)

            binding = provider.read_revision_binding(
                "staging",
                fake.revision_name,
            )

        self.assertEqual(binding.revision_name, fake.revision_name)
        self.assertEqual(binding.platform_source_revision, SOURCE_REVISION)
        self.assertEqual(binding.generation_digest, GENERATION_DIGEST)
        self.assertFalse(
            any(
                request.argv[1:4] == ("run", "services", "update-traffic")
                for request in fake.requests
            )
        )

    def test_closed_runner_rejects_credential_override_and_unreviewed_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "gcloud"
            executable.write_bytes(b"#!/bin/sh\nexit 1\n")
            executable.chmod(0o700)
            runner = ClosedGcloudRunner(executable, root, root)
            environment = (
                ("CLOUDSDK_CONFIG", str(root)),
                ("CLOUDSDK_CORE_DISABLE_PROMPTS", "1"),
                ("CLOUDSDK_PYTHON_SITEPACKAGES", "0"),
            )

            with self.assertRaises(ValueError):
                runner.validate(
                    ProviderCommandRequest(
                        argv=(
                            str(executable),
                            "auth",
                            "login",
                            "--impersonate-service-account=test@example.com",
                        ),
                        cwd=root,
                        environment=environment,
                    )
                )
            with self.assertRaises(ValueError):
                runner.validate(
                    ProviderCommandRequest(
                        argv=(
                            str(executable),
                            "run",
                            "services",
                            "describe",
                            SERVICE,
                            "--impersonate-service-account=test@example.com",
                            "--credential-file-override=/tmp/key.json",
                        ),
                        cwd=root,
                        environment=environment,
                    )
                )

    def test_attachment_readback_verifies_owner_ingress_audience_and_caller(self) -> None:
        compiled = _canonical(proposal().compiled_configuration)
        fixture_labels = json.loads(
            (
                PROJECT_ROOT
                / "infrastructure/config/examples/"
                "fixture-authenticated.synthetic.v1.json"
            ).read_bytes()
        )["labels"]

        class AttachmentGcloud(FakeGcloud):
            target_environment = str(fixture_labels["environment"])

            def run(self, request: ProviderCommandRequest) -> ProviderCommandResult:
                arguments = request.argv[1:]
                self.requests.append(request)
                if arguments[:3] == ("run", "services", "describe"):
                    return ProviderCommandResult(
                        0,
                        _canonical(
                            {
                                "metadata": {
                                    "annotations": {
                                        "run.googleapis.com/ingress": "internal"
                                    },
                                    "labels": {
                                        "application_id": "fixture-authenticated",
                                        "environment": self.target_environment,
                                        "state_owner": "application",
                                    },
                                    "name": "fixture-authenticated",
                                },
                                "spec": {
                                    "template": {
                                        "metadata": {
                                            "annotations": {
                                                "run.googleapis.com/network-interfaces": (
                                                    '[{"network":"projects/'
                                                    + PROJECT_ID
                                                    + '/global/networks/app-platform-shared",'
                                                    '"subnetwork":"projects/'
                                                    + PROJECT_ID
                                                    + '/regions/us-west1/subnetworks/'
                                                    'app-platform-applications-us-west1"}]'
                                                ),
                                                "run.googleapis.com/vpc-access-egress": (
                                                    "all-traffic"
                                                ),
                                            }
                                        },
                                        "spec": {
                                            "containers": [
                                                {
                                                    "env": [
                                                        {
                                                            "name": (
                                                                "APP_PLATFORM_ASSERTION_AUDIENCE"
                                                            ),
                                                            "value": (
                                                                "urn:comfforts:app-platform:"
                                                                "audience:fixture-authenticated"
                                                            ),
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                },
                                "status": {
                                    "conditions": [
                                        {"status": "True", "type": "Ready"}
                                    ]
                                },
                            }
                        ),
                        b"",
                    )
                if arguments[:3] == ("run", "services", "get-iam-policy"):
                    return ProviderCommandResult(
                        0,
                        _canonical(
                            {
                                "bindings": [
                                    {
                                        "members": [
                                            "serviceAccount:"
                                            "app-platform-edge-caller@"
                                            f"{PROJECT_ID}.iam.gserviceaccount.com"
                                        ],
                                        "role": "roles/run.invoker",
                                    }
                                ]
                            }
                        ),
                        b"",
                    )
                return ProviderCommandResult(2, b"", b"unexpected")

        reference = (
            "urn:comfforts:app-platform:gcp:cloud-run:"
            "123456789012:us-west1:fixture-authenticated"
        )
        with tempfile.TemporaryDirectory() as directory:
            fake = AttachmentGcloud(compiled)
            provider = self._provider(directory, fake)

            target = provider.read_target("staging", reference)

        self.assertTrue(target.exists)
        self.assertTrue(target.ready)
        self.assertEqual(target.owner_application_id, "fixture-authenticated")
        self.assertEqual(target.ingress_mode, "shared_edge_only")
        self.assertEqual(
            target.audience,
            "urn:comfforts:app-platform:audience:fixture-authenticated",
        )
        self.assertIn("app-platform-edge-caller", target.caller_grant)
        self.assertEqual(target.application_project_id, FIXTURES_PROJECT_ID)
        self.assertEqual(
            target.network_reference,
            f"projects/{PROJECT_ID}/global/networks/app-platform-shared",
        )
        self.assertEqual(
            target.subnetwork_reference,
            (
                f"projects/{PROJECT_ID}/regions/us-west1/subnetworks/"
                "app-platform-applications-us-west1"
            ),
        )
        self.assertEqual(target.egress_mode, "all-traffic")
        self.assertEqual(target.blockers, ())

        fake.target_environment = "staging"
        mismatched = provider.read_target("staging", reference)

        self.assertEqual(
            mismatched.blockers,
            ("TARGET_ENVIRONMENT_LABEL_MISMATCH",),
        )


if __name__ == "__main__":
    unittest.main()
