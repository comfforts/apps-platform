"""Focused Fixture Application handoff behavior."""

from __future__ import annotations

from dataclasses import replace
import unittest

from contracts.lifecycle import versioned_lifecycle_digest
from infrastructure.operator._interfaces import GitSnapshot
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationDeployRequest,
    FixtureApplicationDeployment,
    FixtureApplicationStatus,
    FixtureDeployRequest,
    FixtureDestroyReadback,
    FixtureHandoffResult,
    FixtureImageReadback,
    FixtureImageRequest,
    FixturePreparation,
    FixtureStatusResult,
    FixtureSuiteLifecycle,
)
from tests.environment import FIXTURES_PROJECT_ID
from infrastructure.operator.integration import PlatformIntegrationState
from infrastructure.operator.integration import (
    RegistrationApplicationStatus,
    RegistrationStatusResult,
)
from infrastructure.operator.local_fixture_lifecycle import (
    LocalFixtureOperator,
    LocalFixtureStatusOperator,
)


SOURCE = "a" * 40
PLATFORM_SOURCE = "b" * 40
EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)
NETWORK = "projects/comfforts-platform-non-prod/global/networks/app-platform-shared"
SUBNET = (
    "projects/comfforts-platform-non-prod/regions/us-west1/subnetworks/"
    "app-platform-applications-us-west1"
)


def _bundle(application_id: str = "fixture-public") -> dict[str, object]:
    return {
        "contract_version": 2,
        "document_kind": "platform-integration-bundle",
        "environment": "staging",
        "application_id": application_id,
        "access_mode": "public",
        "identity_delivery": "none",
        "route_intent": f"/{application_id}",
        "generation": 2,
        "profile_digest": "sha256:" + ("1" * 64),
        "platform_source_authority": "candidate",
        "platform_source_revision": PLATFORM_SOURCE,
        "specification_digest": "sha256:" + ("2" * 64),
        "deployment_progress_digest": "sha256:" + ("3" * 64),
        "endpoints": {
            "external_origin": "https://apps-staging.comfforts.com",
            "issuer": None,
            "jwks_uri": None,
            "oauth_redirect_uri": None,
        },
        "identity": {
            "oauth_client_id": None,
            "audience": None,
            "edge_caller_reference": EDGE_CALLER,
        },
        "application_project": {
            "project_id": FIXTURES_PROJECT_ID,
            "project_number": "123456789012",
        },
        "network": {
            "host_project_id": "comfforts-platform-non-prod",
            "host_project_number": "455651441682",
            "region": "us-west1",
            "network_reference": NETWORK,
            "subnetwork_reference": SUBNET,
            "egress_mode": "all-traffic",
        },
        "attachment_contract": {
            "adapter_kind": "gcp-cloud-run-v1",
            "ingress_mode": "shared_edge_only",
        },
        "qualification_status": "unqualified",
    }


def _request(bundle: dict[str, object] | None = None) -> FixtureDeployRequest:
    return FixtureDeployRequest(
        environment="staging",
        application_id="fixture-public",
        fixture_source_revision=SOURCE,
        expected_platform_source_revision=PLATFORM_SOURCE,
        expected_platform_generation=2,
        catalogue_visibility="listed",
        source_authority="candidate",
        integration_bundle=bundle,
        integration_bundle_path="/private/platform-integration-bundle.v2.json",
    )


class Terminal:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def write(self, message: str) -> None:
        self.messages.append(message)


class Commands:
    def __init__(self) -> None:
        self.deployments = 0

    def prepared_handoff(self, request: FixtureDeployRequest):  # type: ignore[no-untyped-def]
        return None

    def build_image(self, request: FixtureImageRequest) -> FixtureImageReadback:
        return FixtureImageReadback(
            f"us-west1-docker.pkg.dev/{FIXTURES_PROJECT_ID}/"
            "app-platform-images/fixture@sha256:" + ("4" * 64),
            request.source_revision,
        )

    def deploy_application(
        self,
        request: FixtureApplicationDeployRequest,
    ) -> FixtureApplicationDeployment:
        self.deployments += 1
        bundle = request.integration_bundle
        attachment = {
            "contract_version": 2,
            "document_kind": "application-attachment-bundle",
            "environment": "staging",
            "application_id": request.application_id,
            "attachment_revision": 1,
            "platform_integration_bundle_digest": versioned_lifecycle_digest(
                bundle, "platform-integration-bundle"
            ),
            "application_source_revision": request.source_revision,
            "target": {
                "owner_application_id": request.application_id,
                "adapter_kind": "gcp-cloud-run-v1",
                "resource_reference": (
                    "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
                    f"us-west1:{request.application_id}"
                ),
                "application_project_id": FIXTURES_PROJECT_ID,
                "network_reference": NETWORK,
                "subnetwork_reference": SUBNET,
                "egress_mode": "all-traffic",
                "ingress_mode": "shared_edge_only",
                "caller_grant": EDGE_CALLER,
                "audience": None,
            },
        }
        return FixtureApplicationDeployment(
            request.application_id,
            request.image.reference,
            attachment,
        )

    def record_prepared_handoff(
        self,
        request: FixtureDeployRequest,
        preparation: FixturePreparation,
    ) -> FixturePreparation:
        return replace(
            preparation,
            integration_bundle_path=request.integration_bundle_path,
            attachment_bundle_path="/private/application-attachment-bundle.v2.json",
            registration_intent_path="/private/registration-intent.v2.json",
        )

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ) -> FixtureStatusResult:
        selected = application_id or "fixture-public"
        return FixtureStatusResult(
            "read",
            2,
            "sha256:" + ("5" * 64),
            (
                FixtureApplicationStatus(
                    selected,
                    "active",
                    "listed",
                    True,
                    True,
                    True,
                ),
            ),
        )

    def destroy_application(self, request):  # type: ignore[no-untyped-def]
        return FixtureDestroyReadback("destroyed", request.application_id, 3, "sha256:" + ("6" * 64))


class FixtureHandoffLifecycleTest(unittest.TestCase):
    def test_handoff_requires_operator_generated_platform_bundle(self) -> None:
        result = FixtureSuiteLifecycle(Commands()).handoff(_request())

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.blockers, ("INTEGRATION_BUNDLE_REQUIRED",))

    def test_handoff_deploys_runtime_and_stops_before_registration(self) -> None:
        terminal = Terminal()
        commands = Commands()
        lifecycle = FixtureSuiteLifecycle(commands, terminal)

        result = lifecycle.handoff(_request(_bundle()))

        self.assertEqual(result.outcome, "prepared")
        self.assertEqual(commands.deployments, 1)
        self.assertEqual(
            result.registration_intent_path,
            "/private/registration-intent.v2.json",
        )
        self.assertFalse(hasattr(lifecycle, "deploy"))
        self.assertEqual(
            terminal.messages,
            [
                "▸ Stage 1/2 · Resolve the Platform Handoff",
                "▸ Stage 2/2 · Prepare the Fixture Application Handoff",
            ],
        )

    def test_status_distinguishes_target_and_route_readiness(self) -> None:
        result = FixtureSuiteLifecycle(Commands()).status(
            "staging", "fixture-public"
        )

        self.assertEqual(result.outcome, "read")
        self.assertTrue(result.applications[0].target_ready)
        self.assertTrue(result.applications[0].route_ready)

    def test_local_status_reads_the_live_route_instead_of_inferring_it(self) -> None:
        class Integration:
            @staticmethod
            def status_applications(
                environment: str,
                application_ids: tuple[str, ...],
            ) -> RegistrationStatusResult:
                return RegistrationStatusResult(
                    "read",
                    2,
                    "sha256:" + ("7" * 64),
                    tuple(
                        RegistrationApplicationStatus(
                            application_id,
                            "active",
                            "listed",
                            "urn:fixture",
                            True,
                            True,
                        )
                        for application_id in application_ids
                    ),
                )

        unavailable = LocalFixtureStatusOperator(  # type: ignore[arg-type]
            Integration(),
            lambda _application_id: False,
        ).status("staging", "fixture-public")
        available = LocalFixtureStatusOperator(  # type: ignore[arg-type]
            Integration(),
            lambda _application_id: True,
        ).status("staging", "fixture-public")

        self.assertFalse(unavailable.applications[0].route_ready)
        self.assertTrue(available.applications[0].route_ready)


class LocalFixtureOperatorTest(unittest.TestCase):
    def test_passes_explicit_bundle_to_fixture_owner_lifecycle(self) -> None:
        class Git:
            def inspect(self) -> GitSnapshot:
                return GitSnapshot(
                    "comfforts/apps-platform",
                    SOURCE,
                    "feat/cross-project-fixtures",
                    True,
                    "c" * 40,
                    "c" * 40,
                    "origin/feat/cross-project-fixtures",
                    SOURCE,
                    True,
                )

        class Platform:
            def read_platform(self, environment: str) -> PlatformIntegrationState:
                return PlatformIntegrationState(
                    environment,
                    "deployed",
                    "sha256:" + ("1" * 64),
                    PLATFORM_SOURCE,
                    "sha256:" + ("2" * 64),
                    "sha256:" + ("3" * 64),
                    2,
                    "apps-staging.comfforts.com",
                    None,
                    EDGE_CALLER,
                    "unqualified",
                    "candidate",
                )

        class Lifecycle:
            request: FixtureDeployRequest | None = None

            def handoff(self, request: FixtureDeployRequest) -> FixtureHandoffResult:
                self.request = request
                return FixtureHandoffResult(
                    "prepared",
                    request.application_id,
                    None,
                    None,
                    request.integration_bundle_path,
                    None,
                    None,
                )

        lifecycle = Lifecycle()
        result = LocalFixtureOperator(
            Git(), Platform(), lifecycle, source_authority="candidate"
        ).handoff(
            "staging",
            "fixture-public",
            "unlisted",
            _bundle(),
            "/private/platform-integration-bundle.v1.json",
        )

        self.assertEqual(result.outcome, "prepared")
        assert lifecycle.request is not None
        self.assertEqual(lifecycle.request.integration_bundle, _bundle())
        self.assertEqual(lifecycle.request.catalogue_visibility, "unlisted")


if __name__ == "__main__":
    unittest.main()
