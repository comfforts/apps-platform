"""Focused command-line coverage for handoff ownership boundaries."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from contracts.lifecycle import versioned_lifecycle_digest
from infrastructure.operator.cli import main
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationStatus,
    FixtureHandoffResult,
    FixtureStatusResult,
)
from infrastructure.operator.integration import (
    IntegrationBundleRequest,
    IntegrationBundleResult,
    RegistrationIntent,
    RegistrationLifecycleResult,
)
from infrastructure.operator.project_connections import ProjectLifecycleResult
from tests.environment import FIXTURES_PROJECT_ID


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTORS = PROJECT_ROOT / "contracts/lifecycle/test-vectors/valid"


def _integration_bundle() -> dict[str, object]:
    return json.loads(
        (VECTORS / "platform-integration-bundle.staging.synthetic.v2.json").read_text()
    )


class Integration:
    def __init__(self) -> None:
        self.output_requests: list[IntegrationBundleRequest] = []
        self.registrations: list[tuple[object, object, RegistrationIntent]] = []

    def outputs(self, request: IntegrationBundleRequest) -> IntegrationBundleResult:
        self.output_requests.append(request)
        bundle = _integration_bundle()
        return IntegrationBundleResult(
            "generated",
            bundle,
            versioned_lifecycle_digest(bundle, "platform-integration-bundle"),
        )

    def register(
        self,
        integration_bundle: dict[str, object],
        attachment_bundle: dict[str, object],
        intent: RegistrationIntent,
    ) -> RegistrationLifecycleResult:
        self.registrations.append((integration_bundle, attachment_bundle, intent))
        return RegistrationLifecycleResult(
            "activated", 3, "sha256:" + ("7" * 64)
        )


class Fixture:
    def __init__(self) -> None:
        self.handoff_arguments: tuple[object, ...] | None = None

    def handoff(
        self,
        environment: str,
        application_id: str,
        catalogue_visibility: str,
        integration_bundle: dict[str, object],
        integration_bundle_path: str,
    ) -> FixtureHandoffResult:
        self.handoff_arguments = (
            environment,
            application_id,
            catalogue_visibility,
            integration_bundle,
            integration_bundle_path,
        )
        return FixtureHandoffResult(
            "prepared",
            application_id,
            f"us-west1-docker.pkg.dev/{FIXTURES_PROJECT_ID}/"
            "app-platform-images/fixture@sha256:" + ("1" * 64),
            "sha256:" + ("2" * 64),
            integration_bundle_path,
            "sha256:" + ("3" * 64),
            "/private/application-attachment-bundle.v2.json",
            "/private/registration-intent.v2.json",
        )

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ) -> FixtureStatusResult:
        selected = application_id or "fixture-public"
        return FixtureStatusResult(
            "read",
            3,
            "sha256:" + ("7" * 64),
            (FixtureApplicationStatus(selected, "active", True, True, True),),
        )


class Projects:
    def bootstrap_fixture(
        self,
        environment: str,
        project_id: str,
    ) -> ProjectLifecycleResult:
        return ProjectLifecycleResult(
            "bootstrapped", project_id, "123456789012"
        )

    def connect(self, environment: str, project_id: str) -> ProjectLifecycleResult:
        return ProjectLifecycleResult(
            "connected",
            project_id,
            "123456789012",
            "/private/connection.v1.json",
        )


class IntegrationCliTest(unittest.TestCase):
    def test_outputs_persists_application_project_scoped_bundle(self) -> None:
        integration = Integration()
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "outputs",
                        "--environment", "staging",
                        "--state-directory", temporary,
                        "--application-id", "fixture-authenticated",
                        "--application-project-id", FIXTURES_PROJECT_ID,
                        "--access-mode", "authenticated",
                        "--identity-delivery", "required",
                        "--route-intent", "/fixture-authenticated",
                        "--platform-source-revision", "a" * 40,
                        "--platform-generation", "1",
                    ],
                    integration_factory=lambda _path, _authority: integration,
                )
            result = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(Path(result["bundle_path"]).is_file())
            self.assertEqual(
                integration.output_requests[0].application_project_id,
                FIXTURES_PROJECT_ID,
            )

    def test_fixture_handoff_consumes_existing_bundle_and_stops(self) -> None:
        fixture = Fixture()
        bundle_path = VECTORS / "platform-integration-bundle.staging.synthetic.v2.json"
        output = io.StringIO()
        diagnostics = io.StringIO()
        with redirect_stdout(output), redirect_stderr(diagnostics):
            code = main(
                [
                    "fixture-handoff",
                    "--environment", "staging",
                    "--application-id", "fixture-authenticated",
                    "--catalogue-visibility", "listed",
                    "--integration-bundle", str(bundle_path),
                ],
                fixture_factory=lambda _path, _authority: fixture,
            )
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(
            result["registration_intent_path"],
            "/private/registration-intent.v2.json",
        )
        self.assertIn("route is inactive", diagnostics.getvalue())
        assert fixture.handoff_arguments is not None
        self.assertEqual(fixture.handoff_arguments[1], "fixture-authenticated")
        self.assertEqual(fixture.handoff_arguments[2], "listed")

    def test_platform_register_is_the_only_route_activation_command(self) -> None:
        integration = Integration()
        with tempfile.TemporaryDirectory() as temporary:
            intent = Path(temporary) / "intent.json"
            intent.write_bytes(
                (
                    VECTORS
                    / "registration-intent.staging.synthetic.v2.json"
                ).read_bytes()
            )
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "register",
                        "--environment", "staging",
                        "--state-directory", temporary,
                        "--integration-bundle",
                        str(
                            VECTORS
                            / "platform-integration-bundle.staging.synthetic.v2.json"
                        ),
                        "--attachment-bundle",
                        str(
                            VECTORS
                            / "application-attachment-bundle.staging.synthetic.v2.json"
                        ),
                        "--registration-intent", str(intent),
                    ],
                    integration_factory=lambda _path, _authority: integration,
                )
        self.assertEqual(code, 0)
        self.assertEqual(len(integration.registrations), 1)

    def test_platform_register_rejects_mixed_handoff_versions(self) -> None:
        integration = Integration()
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "register",
                    "--environment", "staging",
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
                    str(VECTORS / "registration-intent.staging.synthetic.v2.json"),
                ],
                integration_factory=lambda _path, _authority: integration,
            )

        result = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertIn("INTEGRATION_INPUT_INVALID", result["blockers"])
        self.assertEqual(integration.registrations, [])

    def test_status_reports_target_and_route_readiness_separately(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                ["fixture-status", "--environment", "staging", "--application-id", "fixture-public"],
                fixture_status_factory=lambda _path, _authority: Fixture(),
            )
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(result["applications"][0]["target_ready"])
        self.assertTrue(result["applications"][0]["route_ready"])

    def test_project_bootstrap_and_connection_are_explicit_commands(self) -> None:
        for operation, extra, outcome in (
            (
                "fixture-project-bootstrap",
                ["--application-project-id", FIXTURES_PROJECT_ID],
                "bootstrapped",
            ),
            (
                "platform-connect-project",
                ["--application-project-id", FIXTURES_PROJECT_ID],
                "connected",
            ),
        ):
            with self.subTest(operation=operation):
                output = io.StringIO()
                with redirect_stdout(output):
                    code = main(
                        [operation, "--environment", "staging", *extra],
                        project_factory=lambda _path, _authority: Projects(),
                    )
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output.getvalue())["outcome"], outcome)


if __name__ == "__main__":
    unittest.main()
