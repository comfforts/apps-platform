"""Closed command boundary for AP-M9-W7 application integration operations."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from contracts.lifecycle import lifecycle_digest, load_lifecycle_document
from infrastructure.operator.cli import main
from infrastructure.operator.integration import (
    IntegrationBundleRequest,
    IntegrationBundleResult,
    LifecycleChangeRequest,
    RegistrationIntent,
    RegistrationLifecycleResult,
)
from infrastructure.operator.fixture_lifecycle import (
    FixtureDeployResult,
    FixtureDestroyResult,
    FixtureHandoffResult,
)
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationStatus,
    FixtureStatusResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTORS = PROJECT_ROOT / "contracts/lifecycle/test-vectors/valid"
SOURCE_REVISION = "a" * 40
GENERATION_DIGEST = "sha256:" + ("7" * 64)


class FakeIntegrationLifecycle:
    def __init__(self) -> None:
        self.outputs_requests: list[IntegrationBundleRequest] = []
        self.registrations: list[
            tuple[dict[str, object], dict[str, object], RegistrationIntent]
        ] = []
        self.detaches: list[LifecycleChangeRequest] = []
        self.retirements: list[LifecycleChangeRequest] = []

    def outputs(self, request: IntegrationBundleRequest) -> IntegrationBundleResult:
        self.outputs_requests.append(request)
        bundle = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v1.json"
            ).read_text(encoding="utf-8")
        )
        return IntegrationBundleResult(
            outcome="generated",
            bundle=bundle,
            bundle_digest=lifecycle_digest(
                bundle,
                "platform-integration-bundle",
            ),
        )

    def register(
        self,
        integration_bundle: dict[str, object],
        attachment_bundle: dict[str, object],
        intent: RegistrationIntent,
    ) -> RegistrationLifecycleResult:
        self.registrations.append(
            (integration_bundle, attachment_bundle, intent)
        )
        return RegistrationLifecycleResult(
            outcome="activated",
            generation=7,
            generation_digest=GENERATION_DIGEST,
        )

    def detach(
        self,
        request: LifecycleChangeRequest,
    ) -> RegistrationLifecycleResult:
        self.detaches.append(request)
        return RegistrationLifecycleResult(
            outcome="activated",
            generation=8,
            generation_digest=GENERATION_DIGEST,
        )

    def retire(
        self,
        request: LifecycleChangeRequest,
    ) -> RegistrationLifecycleResult:
        self.retirements.append(request)
        return RegistrationLifecycleResult(
            outcome="activated",
            generation=9,
            generation_digest=GENERATION_DIGEST,
        )


class FakeFixtureOperator:
    def __init__(self) -> None:
        self.environments: list[str] = []
        self.application_ids: list[str | None] = []

    def deploy(self, environment: str, application_id: str) -> FixtureDeployResult:
        self.environments.append(environment)
        self.application_ids.append(application_id)
        return FixtureDeployResult(
            outcome="deployed",
            image_reference=(
                "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
                "app-platform-images/fixture@sha256:" + ("1" * 64)
            ),
            application_ids=(application_id,),
            registration_generation=8,
            registration_generation_digest=GENERATION_DIGEST,
        )

    def handoff(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureHandoffResult:
        self.environments.append(environment)
        self.application_ids.append(application_id)
        return FixtureHandoffResult(
            outcome="prepared",
            application_id=application_id,
            image_reference=(
                "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
                "app-platform-images/fixture@sha256:" + ("1" * 64)
            ),
            integration_bundle_digest="sha256:" + ("2" * 64),
            integration_bundle_path="/private/platform-integration-bundle.v1.json",
            attachment_bundle_digest="sha256:" + ("3" * 64),
            attachment_bundle_path="/private/application-attachment-bundle.v1.json",
        )

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ) -> FixtureStatusResult:
        self.environments.append(environment)
        self.application_ids.append(application_id)
        applications = (
            FixtureApplicationStatus(application_id, "active", True, True),
        ) if application_id is not None else (
            FixtureApplicationStatus("fixture-public", "active", True, True),
            FixtureApplicationStatus(
                "fixture-authenticated", "active", True, True
            ),
            FixtureApplicationStatus("fixture-restricted", "active", True, True),
        )
        return FixtureStatusResult(
            "read",
            8,
            GENERATION_DIGEST,
            applications,
        )

    def destroy(self, environment: str, application_id: str) -> FixtureDestroyResult:
        self.environments.append(environment)
        return FixtureDestroyResult(
            "destroyed",
            application_id,
            9,
            GENERATION_DIGEST,
        )


def _run(
    arguments: list[str],
    lifecycle: FakeIntegrationLifecycle,
) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            arguments,
            integration_factory=lambda _path, _authority: lifecycle,
        )
    return exit_code, json.loads(output.getvalue())


class IntegrationCliTest(unittest.TestCase):
    def test_fixture_handoff_emits_inspectable_paths_without_registration(self) -> None:
        fixture = FakeFixtureOperator()
        output = io.StringIO()

        with redirect_stdout(output):
            code = main(
                [
                    "fixture-handoff",
                    "--environment",
                    "staging",
                    "--application-id",
                    "fixture-authenticated",
                ],
                fixture_factory=lambda _path, _authority: fixture,
            )

        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["outcome"], "prepared")
        self.assertEqual(
            result["integration_bundle_path"],
            "/private/platform-integration-bundle.v1.json",
        )
        self.assertEqual(
            result["attachment_bundle_path"],
            "/private/application-attachment-bundle.v1.json",
        )
        self.assertEqual(fixture.application_ids, ["fixture-authenticated"])

    def test_fixture_deploy_requires_and_selects_one_application(self) -> None:
        fixture = FakeFixtureOperator()
        output = io.StringIO()

        with redirect_stdout(output):
            code = main(
                [
                    "fixture-deploy",
                    "--environment",
                    "staging",
                    "--application-id",
                    "fixture-authenticated",
                ],
                fixture_factory=lambda _path, _authority: fixture,
            )

        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(fixture.environments, ["staging"])
        self.assertEqual(fixture.application_ids, ["fixture-authenticated"])
        self.assertEqual(result["outcome"], "deployed")
        self.assertEqual(
            result["application_ids"],
            ["fixture-authenticated"],
        )

    def test_fixture_deploy_rejects_an_omitted_application(self) -> None:
        fixture = FakeFixtureOperator()

        for application_option in ([], ["--application-id", ""]):
            with self.subTest(application_option=application_option):
                with self.assertRaisesRegex(
                    SystemExit,
                    "fixture-deploy requires --application-id",
                ):
                    main(
                        [
                            "fixture-deploy",
                            "--environment",
                            "staging",
                            *application_option,
                        ],
                        fixture_factory=lambda _path, _authority: fixture,
                    )

    def test_fixture_status_returns_only_read_only_coarse_posture(self) -> None:
        fixture = FakeFixtureOperator()
        output = io.StringIO()

        with redirect_stdout(output):
            code = main(
                ["fixture-status", "--environment", "staging"],
                fixture_status_factory=lambda _path, _authority: fixture,
            )

        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["outcome"], "read")
        self.assertTrue(all(item["target_ready"] for item in result["applications"]))
        serialized = json.dumps(result)
        self.assertNotIn("restricted_members", serialized)
        self.assertNotIn("terraform", serialized.lower())

    def test_fixture_status_optionally_selects_one_application(self) -> None:
        fixture = FakeFixtureOperator()
        output = io.StringIO()

        with redirect_stdout(output):
            code = main(
                [
                    "fixture-status",
                    "--environment",
                    "staging",
                    "--application-id",
                    "fixture-public",
                ],
                fixture_status_factory=lambda _path, _authority: fixture,
            )

        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(fixture.application_ids, ["fixture-public"])
        self.assertEqual(
            [item["application_id"] for item in result["applications"]],
            ["fixture-public"],
        )

    def test_fixture_destroy_selects_one_application_and_emits_coarse_result(self) -> None:
        fixture = FakeFixtureOperator()
        output = io.StringIO()

        with redirect_stdout(output):
            code = main(
                [
                    "fixture-destroy",
                    "--environment",
                    "staging",
                    "--application-id",
                    "fixture-public",
                ],
                fixture_factory=lambda _path, _authority: fixture,
            )

        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["outcome"], "destroyed")
        self.assertEqual(result["application_id"], "fixture-public")

    def test_outputs_writes_one_canonical_create_only_bundle(self) -> None:
        lifecycle = FakeIntegrationLifecycle()
        with tempfile.TemporaryDirectory() as directory:
            state_directory = Path(directory) / "operator"
            arguments = [
                "outputs",
                "--environment",
                "staging",
                "--state-directory",
                str(state_directory),
                "--application-id",
                "fixture-authenticated",
                "--access-mode",
                "authenticated",
                "--route-intent",
                "/fixture-authenticated",
                "--platform-source-revision",
                SOURCE_REVISION,
                "--platform-generation",
                "1",
            ]

            first_code, first = _run(arguments, lifecycle)
            second_code, second = _run(arguments, lifecycle)

            bundle_path = state_directory / str(first["bundle_path"])
            loaded = load_lifecycle_document(
                bundle_path,
                "platform-integration-bundle",
            )

        self.assertEqual((first_code, second_code), (0, 0))
        self.assertEqual(first, second)
        self.assertEqual(first["outcome"], "generated")
        self.assertEqual(loaded.violations, ())
        self.assertEqual(len(lifecycle.outputs_requests), 2)
        self.assertEqual(
            lifecycle.outputs_requests[0].expected_platform_source_revision,
            SOURCE_REVISION,
        )

    def test_register_reads_strict_private_inputs_and_emits_coarse_result(self) -> None:
        lifecycle = FakeIntegrationLifecycle()
        with tempfile.TemporaryDirectory() as directory:
            intent_path = Path(directory) / "registration-intent.json"
            intent_path.write_text(
                json.dumps(
                    {
                        "attachment_id": "primary",
                        "catalogue_summary": "Synthetic qualification application",
                        "catalogue_title": "Fixture application",
                        "catalogue_visibility": "listed",
                        "forwarding_mode": "strip_application_prefix",
                        "mount_path": "/",
                        "restricted_members": [],
                    }
                ),
                encoding="utf-8",
            )
            code, result = _run(
                [
                    "register",
                    "--environment",
                    "staging",
                    "--state-directory",
                    str(Path(directory) / "operator"),
                    "--integration-bundle",
                    str(
                        VECTORS
                        / "platform-integration-bundle.staging.synthetic.v1.json"
                    ),
                    "--attachment-bundle",
                    str(
                        VECTORS
                        / "application-attachment-bundle.staging.synthetic.v1.json"
                    ),
                    "--registration-intent",
                    str(intent_path),
                ],
                lifecycle,
            )
            handoff_path = (
                Path(directory)
                / "operator/environments/staging/applications/"
                "fixture-authenticated/handoffs/"
                f"{GENERATION_DIGEST[7:]}.v1.json"
            )
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(result["outcome"], "activated")
        self.assertEqual(result["generation"], 7)
        self.assertNotIn("restricted_members", json.dumps(result))
        self.assertNotIn("resource_reference", json.dumps(result))
        self.assertEqual(
            handoff["registration_generation_digest"],
            GENERATION_DIGEST,
        )
        self.assertNotIn("restricted_members", handoff)
        self.assertNotIn("target", handoff)
        self.assertEqual(len(lifecycle.registrations), 1)
        self.assertEqual(lifecycle.registrations[0][2].attachment_id, "primary")

    def test_detach_and_retire_preserve_exact_preconditions(self) -> None:
        lifecycle = FakeIntegrationLifecycle()
        base = [
            "--environment",
            "staging",
            "--application-id",
            "fixture-authenticated",
            "--platform-source-revision",
            SOURCE_REVISION,
            "--generation-digest",
            GENERATION_DIGEST,
        ]

        detach_code, detach_result = _run(["detach", *base], lifecycle)
        retire_code, retire_result = _run(["retire", *base], lifecycle)

        self.assertEqual((detach_code, retire_code), (0, 0))
        self.assertEqual(detach_result["generation"], 8)
        self.assertEqual(retire_result["generation"], 9)
        self.assertEqual(
            lifecycle.detaches[0],
            LifecycleChangeRequest(
                environment="staging",
                application_id="fixture-authenticated",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation_digest=GENERATION_DIGEST,
            ),
        )
        self.assertEqual(lifecycle.retirements[0], lifecycle.detaches[0])

    def test_local_adapter_fails_closed_without_deployed_readback(self) -> None:
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as directory, redirect_stdout(output):
            exit_code = main(
                [
                    "outputs",
                    "--environment",
                    "staging",
                    "--state-directory",
                    str(Path(directory) / "operator"),
                    "--application-id",
                    "fixture-public",
                    "--access-mode",
                    "public",
                    "--route-intent",
                    "/fixture-public",
                    "--platform-source-revision",
                    SOURCE_REVISION,
                    "--platform-generation",
                    "1",
                ]
            )

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(
            result["blockers"],
            ["PLATFORM_READBACK_FAILED"],
        )


if __name__ == "__main__":
    unittest.main()
