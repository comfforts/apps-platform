"""Read-only application handoff readiness checks."""

from __future__ import annotations

from dataclasses import replace
import io
import json
import unittest
from unittest import mock

from infrastructure.operator._interfaces import DeploymentCheckResult, StageCheck
from infrastructure.operator.application_handoff_check import (
    ApplicationHandoffCheck,
    ApplicationHandoffCheckRequest,
)
from infrastructure.operator.cli import _main as operator_main
from infrastructure.operator.integration import IntegrationBundleResult
from infrastructure.operator.project_connections import ApplicationProjectReadback


SOURCE_REVISION = "1" * 40


class FakeDeploymentChecker:
    def __init__(self, result: DeploymentCheckResult) -> None:
        self.result = result

    def deploy_check(self, environment: str) -> DeploymentCheckResult:
        self.environment = environment
        return self.result


class FakeIntegration:
    def __init__(self, result: IntegrationBundleResult) -> None:
        self.result = result
        self.requests = []

    def outputs(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return self.result


class FakeProjectReader:
    def __init__(self, readback: ApplicationProjectReadback) -> None:
        self.readback = readback

    def read_project(self, project_id: str) -> ApplicationProjectReadback:
        self.project_id = project_id
        return self.readback


def deployment_result(
    *,
    platform_ready: bool = True,
    reconciliation_required: bool = False,
    shared_edge: StageCheck | None = None,
    stages: tuple[tuple[str, StageCheck], ...] | None = None,
) -> DeploymentCheckResult:
    return DeploymentCheckResult(
        outcome=(
            "ready"
            if platform_ready
            else (
                "reconciliation-required"
                if reconciliation_required
                else "incomplete"
            )
        ),
        operational_ready=True,
        source_admission_blockers=(),
        stages=stages
        or (
            ("bootstrap-services", StageCheck("pass")),
            ("bootstrap", StageCheck("pass")),
            ("foundation", StageCheck("pass")),
            ("shared-edge", shared_edge or StageCheck("pass")),
        ),
        source_revision=SOURCE_REVISION,
        platform_ready=platform_ready,
        reconciliation_required=reconciliation_required,
    )


def project_readback() -> ApplicationProjectReadback:
    return ApplicationProjectReadback(
        project_id="application-project",
        exists=True,
        project_number="123456789012",
        enabled_services=(
            "cloudresourcemanager.googleapis.com",
            "compute.googleapis.com",
            "iam.googleapis.com",
            "run.googleapis.com",
            "serviceusage.googleapis.com",
        ),
        host_project_id="comfforts-platform-non-prod",
        network_viewer_granted=True,
        subnet_user_granted=True,
    )


def protected_bundle() -> dict[str, object]:
    origin = "https://apps-staging.comfforts.com"
    return {
        "access_mode": "authenticated",
        "identity_delivery": "required",
        "endpoints": {
            "external_origin": origin,
            "issuer": f"{origin}/_platform",
            "jwks_uri": f"{origin}/.well-known/jwks.json",
            "oauth_redirect_uri": f"{origin}/_platform/auth/callback",
        },
        "identity": {
            "oauth_client_id": "client.apps.googleusercontent.com",
            "audience": "urn:comfforts:app-platform:audience:example-app",
            "edge_caller_reference": "serviceAccount:edge@example.invalid",
        },
    }


class ApplicationHandoffCheckTest(unittest.TestCase):
    def request(self) -> ApplicationHandoffCheckRequest:
        return ApplicationHandoffCheckRequest(
            environment="staging",
            application_id="example-app",
            application_project_id="application-project",
            access_mode="authenticated",
            identity_delivery="required",
            route_intent="/example-app",
            platform_source_revision=SOURCE_REVISION,
            platform_generation=5,
        )

    def checker(
        self,
        *,
        deployment: DeploymentCheckResult | None = None,
        project: ApplicationProjectReadback | None = None,
        bundle: dict[str, object] | None = None,
    ) -> ApplicationHandoffCheck:
        return ApplicationHandoffCheck(
            FakeDeploymentChecker(deployment or deployment_result()),
            FakeIntegration(
                IntegrationBundleResult(
                    "generated",
                    bundle or protected_bundle(),
                    "sha256:" + "a" * 64,
                )
            ),
            FakeProjectReader(project or project_readback()),
        )

    def test_ready_requires_exact_plans_project_connection_and_protected_identity(
        self,
    ) -> None:
        result = self.checker().check(self.request())

        self.assertEqual(result.outcome, "ready")
        self.assertTrue(result.ready)
        self.assertEqual(result.blockers, ())
        self.assertEqual(
            dict(result.checks),
            {
                "application-identity-projection": "pass",
                "application-project": "pass",
                "application-services": "pass",
                "bundle-contract": "pass",
                "platform-readiness": "pass",
            },
        )

    def test_blocks_when_platform_terraform_requires_reconciliation(self) -> None:
        result = self.checker(
            deployment=deployment_result(
                platform_ready=False,
                reconciliation_required=True,
                shared_edge=StageCheck(
                    "would-change",
                    summary={
                        "changes": [
                            {
                                "address": (
                                    "module.platform_foundation."
                                    "google_project_iam_member.edge_session_store[0]"
                                ),
                                "actions": ["create"],
                            }
                        ]
                    },
                )
            )
        ).check(self.request())

        self.assertFalse(result.ready)
        self.assertIn("PLATFORM_RECONCILIATION_REQUIRED", result.blockers)
        self.assertEqual(dict(result.checks)["platform-readiness"], "blocked")

    def test_platform_service_reconciliation_is_owned_by_deployment_check(
        self,
    ) -> None:
        result = self.checker(
            deployment=deployment_result(
                platform_ready=False,
                reconciliation_required=True,
                stages=(
                    (
                        "bootstrap-services",
                        StageCheck(
                            "would-change",
                            blockers=("BOOTSTRAP_SERVICES_READBACK_MISMATCH",),
                        ),
                    ),
                    ("bootstrap", StageCheck("pass")),
                    ("foundation", StageCheck("pass")),
                    ("shared-edge", StageCheck("pass")),
                ),
            )
        ).check(self.request())

        self.assertFalse(result.ready)
        self.assertIn("PLATFORM_RECONCILIATION_REQUIRED", result.blockers)
        self.assertEqual(dict(result.checks)["platform-readiness"], "blocked")

    def test_blocks_missing_application_services_and_network_grants(self) -> None:
        project = replace(
            project_readback(),
            enabled_services=("run.googleapis.com",),
            network_viewer_granted=False,
        )

        result = self.checker(project=project).check(self.request())

        self.assertIn("APPLICATION_PROJECT_SERVICES_INCOMPLETE", result.blockers)
        self.assertIn("APPLICATION_PROJECT_CONNECTION_MISMATCH", result.blockers)

    def test_public_mode_requires_no_platform_identity_values(self) -> None:
        public = protected_bundle()
        public["access_mode"] = "public"
        public["identity_delivery"] = "none"
        public["endpoints"] = {
            "external_origin": "https://apps-staging.comfforts.com",
            "issuer": None,
            "jwks_uri": None,
            "oauth_redirect_uri": None,
        }
        public["identity"] = {
            "oauth_client_id": None,
            "audience": None,
            "edge_caller_reference": "serviceAccount:edge@example.invalid",
        }

        result = self.checker(bundle=public).check(
            replace(
                self.request(),
                access_mode="public",
                identity_delivery="none",
            )
        )

        self.assertTrue(result.ready)
        self.assertEqual(
            dict(result.checks)["application-identity-projection"],
            "not-required",
        )

    def test_public_optional_requires_the_explicit_identity_projection(self) -> None:
        optional = protected_bundle()
        optional["access_mode"] = "public"
        optional["identity_delivery"] = "optional"

        result = self.checker(bundle=optional).check(
            replace(
                self.request(),
                access_mode="public",
                identity_delivery="optional",
            )
        )

        self.assertTrue(result.ready)
        self.assertEqual(
            dict(result.checks)["application-identity-projection"],
            "pass",
        )

    def test_protected_mode_rejects_an_invalid_application_identity_projection(
        self,
    ) -> None:
        bundle = protected_bundle()
        bundle["identity"] = {
            "oauth_client_id": "client.apps.googleusercontent.com",
            "audience": "urn:comfforts:app-platform:audience:another-app",
            "edge_caller_reference": "serviceAccount:edge@example.invalid",
        }

        result = self.checker(bundle=bundle).check(self.request())

        self.assertFalse(result.ready)
        self.assertIn("APPLICATION_IDENTITY_PROJECTION_INVALID", result.blockers)

    def test_cli_reports_machine_and_human_readable_ready_result(self) -> None:
        checker = self.checker()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = operator_main(
                [
                    "application-handoff-check",
                    "--environment",
                    "staging",
                    "--source-authority",
                    "candidate",
                    "--application-id",
                    "example-app",
                    "--application-project-id",
                    "application-project",
                    "--access-mode",
                    "authenticated",
                    "--identity-delivery",
                    "required",
                    "--route-intent",
                    "/example-app",
                    "--platform-source-revision",
                    SOURCE_REVISION,
                    "--platform-generation",
                    "5",
                ],
                application_handoff_check_factory=(
                    lambda _path, _authority: checker
                ),
            )

        document = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(document["ready"])
        self.assertEqual(document["outcome"], "ready")
        self.assertIn("Application handoff check passed", stderr.getvalue())
        self.assertIn("No bundle", stderr.getvalue())
        self.assertIn("check mode: working-tree diagnostic", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
