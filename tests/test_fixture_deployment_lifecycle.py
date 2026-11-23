"""AP-M9-W9 Fixture Application deployment lifecycle through injected fakes."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tempfile
import unittest

from contracts.lifecycle import lifecycle_digest
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationDeployment,
    FixtureApplicationStatus,
    FixtureCommandError,
    FixtureDeployRequest,
    FixtureDeployResult,
    FixtureDestroyRequest,
    FixtureImageReadback,
    FixturePreparation,
    FixtureRegistrationReadback,
    FixtureStatusResult,
    FixtureSuiteLifecycle,
)
from infrastructure.operator.integration import (
    AttachmentValidationResult,
    IntegrationBundleResult,
    RegistrationLifecycleResult,
    RegistrationApplicationStatus,
    RegistrationStatusResult,
)
from infrastructure.operator.local_fixture_lifecycle import (
    LocalFixtureLifecycleCommands,
)
from infrastructure.operator import StageExecution
from infrastructure.operator import GitSnapshot
from infrastructure.operator.integration import PlatformIntegrationState
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_fixture_lifecycle import LocalFixtureOperator
from infrastructure.operator.local_fixture_preparations import (
    LocalFixturePreparations,
)
from infrastructure.operator.local_integration import PlatformIntegrationReadbackError


SOURCE_REVISION = "a" * 40
PLATFORM_REVISION = "b" * 40
IMAGE_REFERENCE = (
    "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
    "app-platform/fixture@sha256:" + ("1" * 64)
)
PROFILE_DIGEST = "sha256:" + ("2" * 64)
SPECIFICATION_DIGEST = "sha256:" + ("3" * 64)
PROGRESS_DIGEST = "sha256:" + ("4" * 64)
GENERATION_DIGEST = "sha256:" + ("5" * 64)
EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)


def _bundle(application_id: str, access_mode: str, route_intent: str) -> dict[str, object]:
    protected = access_mode != "public"
    origin = "https://apps-staging.comfforts.com"
    return {
        "contract_version": 1,
        "document_kind": "platform-integration-bundle",
        "environment": "staging",
        "application_id": application_id,
        "access_mode": access_mode,
        "route_intent": route_intent,
        "generation": 7,
        "profile_digest": PROFILE_DIGEST,
        "platform_source_authority": "accepted",
        "platform_source_revision": PLATFORM_REVISION,
        "specification_digest": SPECIFICATION_DIGEST,
        "deployment_progress_digest": PROGRESS_DIGEST,
        "endpoints": {
            "external_origin": origin,
            "issuer": f"{origin}/_platform" if protected else None,
            "jwks_uri": f"{origin}/.well-known/jwks.json" if protected else None,
            "oauth_redirect_uri": (
                f"{origin}/_platform/auth/callback" if protected else None
            ),
        },
        "identity": {
            "oauth_client_id": (
                "1234567890-appsplatform.apps.googleusercontent.com"
                if protected
                else None
            ),
            "audience": (
                f"urn:comfforts:app-platform:audience:{application_id}"
                if protected
                else None
            ),
            "edge_caller_reference": EDGE_CALLER,
        },
        "attachment_contract": {
            "adapter_kind": "gcp-cloud-run-v1",
            "ingress_mode": "shared_edge_only",
        },
        "qualification_status": "unqualified",
    }


def _attachment(bundle: dict[str, object]) -> dict[str, object]:
    identity = bundle["identity"]
    assert isinstance(identity, dict)
    application_id = str(bundle["application_id"])
    return {
        "contract_version": 1,
        "document_kind": "application-attachment-bundle",
        "environment": "staging",
        "application_id": application_id,
        "attachment_revision": 1,
        "platform_integration_bundle_digest": lifecycle_digest(
            bundle,
            "platform-integration-bundle",
        ),
        "application_source_revision": SOURCE_REVISION,
        "target": {
            "owner_application_id": application_id,
            "adapter_kind": "gcp-cloud-run-v1",
            "resource_reference": (
                "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
                f"us-west1:{application_id}"
            ),
            "ingress_mode": "shared_edge_only",
            "caller_grant": EDGE_CALLER,
            "audience": identity["audience"],
        },
    }


@dataclass
class FakeFixtureCommands:
    calls: list[str] = field(default_factory=list)
    fail_application: str | None = None
    image_reference: str = IMAGE_REFERENCE
    image_source_revision: str = SOURCE_REVISION
    preparation: FixturePreparation | None = None

    def prepared_handoff(self, request):  # type: ignore[no-untyped-def]
        del request
        self.calls.append("prepared")
        return self.preparation

    def integration_bundle(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(f"bundle:{request.application_id}")
        return _bundle(
            request.application_id,
            request.access_mode,
            request.route_intent,
        )

    def build_image(self, request):  # type: ignore[no-untyped-def]
        self.calls.append("image")
        return FixtureImageReadback(
            reference=self.image_reference,
            source_revision=self.image_source_revision,
        )

    def deploy_application(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(f"deploy:{request.application_id}")
        if request.application_id == self.fail_application:
            raise FixtureCommandError("FIXTURE_PLAN_REFUSED")
        return FixtureApplicationDeployment(
            application_id=request.application_id,
            image_reference=request.image.reference,
            attachment_bundle=_attachment(request.integration_bundle),
        )

    def record_prepared_handoff(
        self,
        request,
        preparation,
    ):  # type: ignore[no-untyped-def]
        del request
        self.calls.append("record")
        self.preparation = FixturePreparation(
            image=preparation.image,
            integration_bundle=preparation.integration_bundle,
            deployment=preparation.deployment,
            integration_bundle_digest=preparation.integration_bundle_digest,
            attachment_bundle_digest=preparation.attachment_bundle_digest,
            integration_bundle_path="/private/platform-integration-bundle.v1.json",
            attachment_bundle_path="/private/application-attachment-bundle.v1.json",
        )
        return self.preparation

    def register(self, request):  # type: ignore[no-untyped-def]
        self.calls.append("register")
        return FixtureRegistrationReadback(
            active=True,
            generation=8,
            generation_digest=GENERATION_DIGEST,
            application_ids=tuple(
                deployment.application_id for deployment in request.deployments
            ),
        )

    def status(self, environment, application_id=None):  # type: ignore[no-untyped-def]
        del environment
        self.calls.append(f"status:{application_id or 'all'}")
        application_ids = (
            (application_id,)
            if application_id is not None
            else (
                "fixture-public",
                "fixture-authenticated",
                "fixture-restricted",
            )
        )
        return FixtureStatusResult(
            "read",
            8,
            GENERATION_DIGEST,
            tuple(
                FixtureApplicationStatus(item, "active", True, True)
                for item in application_ids
            ),
        )


def _request(
    application_id: str = "fixture-authenticated",
) -> FixtureDeployRequest:
    return FixtureDeployRequest(
        environment="staging",
        application_id=application_id,
        fixture_source_revision=SOURCE_REVISION,
        expected_platform_source_revision=PLATFORM_REVISION,
        expected_platform_generation=7,
    )


class FixtureDeploymentLifecycleTest(unittest.TestCase):
    def test_complete_journey_deploys_only_the_selected_fixture(self) -> None:
        commands = FakeFixtureCommands()

        result = FixtureSuiteLifecycle(commands).deploy(_request())

        self.assertEqual(result.outcome, "deployed")
        self.assertEqual(result.blockers, ())
        self.assertEqual(result.image_reference, IMAGE_REFERENCE)
        self.assertEqual(result.registration_generation, 8)
        self.assertEqual(result.registration_generation_digest, GENERATION_DIGEST)
        self.assertEqual(
            result.application_ids,
            ("fixture-authenticated",),
        )
        self.assertEqual(
            commands.calls,
            [
                "prepared",
                "bundle:fixture-authenticated",
                "image",
                "deploy:fixture-authenticated",
                "record",
                "register",
            ],
        )

    def test_handoff_stops_before_registration_and_deploy_reuses_it(self) -> None:
        commands = FakeFixtureCommands()
        lifecycle = FixtureSuiteLifecycle(commands)

        handoff = lifecycle.handoff(_request())

        self.assertEqual(handoff.outcome, "prepared")
        self.assertFalse(handoff.preparation_reused)
        self.assertEqual(
            handoff.integration_bundle_path,
            "/private/platform-integration-bundle.v1.json",
        )
        self.assertEqual(
            handoff.attachment_bundle_path,
            "/private/application-attachment-bundle.v1.json",
        )
        self.assertNotIn("register", commands.calls)

        commands.calls.clear()
        deployed = lifecycle.deploy(_request())

        self.assertEqual(deployed.outcome, "deployed")
        self.assertTrue(deployed.preparation_reused)
        self.assertEqual(commands.calls, ["prepared", "register"])

    def test_mutable_or_source_mismatched_image_stops_before_application_state(self) -> None:
        cases = (
            ("us-west1-docker.pkg.dev/project/repository/fixture:latest", SOURCE_REVISION),
            (IMAGE_REFERENCE, "c" * 40),
        )
        for image_reference, image_source_revision in cases:
            with self.subTest(image_reference=image_reference):
                commands = FakeFixtureCommands(
                    image_reference=image_reference,
                    image_source_revision=image_source_revision,
                )

                result = FixtureSuiteLifecycle(commands).deploy(_request())

                self.assertEqual(result.outcome, "blocked")
                self.assertNotIn("register", commands.calls)
                self.assertFalse(
                    any(call.startswith("deploy:") for call in commands.calls)
                )

    def test_selected_failure_stops_registration_and_safe_retry_reconciles_it(self) -> None:
        commands = FakeFixtureCommands(fail_application="fixture-authenticated")
        lifecycle = FixtureSuiteLifecycle(commands)

        failed = lifecycle.deploy(_request())

        self.assertEqual(failed.outcome, "blocked")
        self.assertEqual(failed.blockers, ("FIXTURE_PLAN_REFUSED",))
        self.assertIn("deploy:fixture-authenticated", commands.calls)
        self.assertNotIn("register", commands.calls)

        commands.fail_application = None
        commands.calls.clear()
        resumed = lifecycle.deploy(_request())

        self.assertEqual(resumed.outcome, "deployed")
        self.assertEqual(commands.calls[-1], "register")

    def test_status_reads_all_fixtures_or_one_selected_fixture(self) -> None:
        commands = FakeFixtureCommands()
        lifecycle = FixtureSuiteLifecycle(commands)

        complete = lifecycle.status("staging")
        selected = lifecycle.status("staging", "fixture-restricted")

        self.assertEqual(len(complete.applications), 3)
        self.assertEqual(
            tuple(item.application_id for item in selected.applications),
            ("fixture-restricted",),
        )
        self.assertEqual(
            commands.calls,
            ["status:all", "status:fixture-restricted"],
        )

        unknown = lifecycle.status("staging", "fixture-unknown")
        self.assertEqual(unknown.outcome, "blocked")
        self.assertEqual(unknown.blockers, ("FIXTURE_REQUEST_INVALID",))


@dataclass
class FakeIntegrationLifecycle:
    registrations: list[tuple[object, object, object]] = field(default_factory=list)

    def outputs(self, request):  # type: ignore[no-untyped-def]
        bundle = _bundle(
            request.application_id,
            request.access_mode,
            request.route_intent,
        )
        return IntegrationBundleResult(
            "generated",
            bundle,
            lifecycle_digest(bundle, "platform-integration-bundle"),
        )

    def validate_attachment(self, bundle, attachment):  # type: ignore[no-untyped-def]
        del bundle
        return AttachmentValidationResult("validated", attachment)

    def register(self, bundle, attachment, intent):  # type: ignore[no-untyped-def]
        self.registrations.append((bundle, attachment, intent))
        return RegistrationLifecycleResult("activated", 8, GENERATION_DIGEST)


@dataclass
class FakeImageProvider:
    references: list[str] = field(default_factory=list)

    def publish_fixture_image(self, source_revision: str) -> str:
        self.references.append(source_revision)
        return IMAGE_REFERENCE

    def read_fixture_image(self, source_revision: str) -> str | None:
        if source_revision not in self.references:
            return None
        return IMAGE_REFERENCE


@dataclass
class FakeFixtureExecutor:
    contexts: list[object] = field(default_factory=list)

    def execute(self, context):  # type: ignore[no-untyped-def]
        self.contexts.append(context)
        bundle = json.loads(dict(context.inputs)["platform-integration-bundle"])
        application_id = str(bundle["application_id"])
        identity = bundle["identity"]
        assert isinstance(identity, dict)
        reference = {
            "reference_kind": "attachment",
            "state_owner": "application",
            "owner_id": application_id,
            "application_id": application_id,
            "attachment_id": "primary",
            "adapter_kind": "gcp-cloud-run-v1",
            "resource_reference": (
                "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
                f"us-west1:{application_id}"
            ),
            "audience": identity["audience"],
        }
        return StageExecution(
            "succeeded",
            (("attachment-reference", json.dumps(reference, sort_keys=True)),),
            "sha256:" + ("6" * 64),
        )


class LocalFixtureLifecycleCompositionTest(unittest.TestCase):
    def test_deep_composition_completes_only_the_selected_fixture(self) -> None:
        integration = FakeIntegrationLifecycle()
        image = FakeImageProvider()
        executor = FakeFixtureExecutor()
        commands = LocalFixtureLifecycleCommands(
            integration,  # type: ignore[arg-type]
            image,
            executor,
            ("https://accounts.google.com", "123456789012345678901"),
        )

        result = FixtureSuiteLifecycle(commands).deploy(_request("fixture-restricted"))

        self.assertEqual(result.outcome, "deployed")
        self.assertEqual(image.references, [SOURCE_REVISION])
        self.assertEqual(
            [context.stage["stage_id"] for context in executor.contexts],
            ["fixture-restricted"],
        )
        self.assertEqual(len(integration.registrations), 1)
        restricted_intent = integration.registrations[0][2]
        self.assertEqual(
            restricted_intent.restricted_members,
            (("https://accounts.google.com", "123456789012345678901"),),
        )

    def test_persisted_handoff_is_reused_without_redeploying_application_state(self) -> None:
        integration = FakeIntegrationLifecycle()
        image = FakeImageProvider()
        executor = FakeFixtureExecutor()
        with tempfile.TemporaryDirectory() as directory:
            preparations = LocalFixturePreparations(
                LocalFilesystem(
                    Path(__file__).resolve().parents[1],
                    Path(directory) / "operator",
                )
            )
            commands = LocalFixtureLifecycleCommands(
                integration,  # type: ignore[arg-type]
                image,
                executor,
                ("https://accounts.google.com", "123456789012345678901"),
                preparations=preparations,
            )
            lifecycle = FixtureSuiteLifecycle(commands)

            handoff = lifecycle.handoff(_request())
            deployed = lifecycle.deploy(_request())

        self.assertEqual(handoff.outcome, "prepared")
        self.assertFalse(handoff.preparation_reused)
        self.assertEqual(deployed.outcome, "deployed")
        self.assertTrue(deployed.preparation_reused)
        self.assertEqual(len(executor.contexts), 1)
        self.assertEqual(image.references, [SOURCE_REVISION])
        self.assertEqual(len(integration.registrations), 1)

    def test_wrong_attachment_owner_fails_before_generation_activation(self) -> None:
        class WrongOwnerCommands(FakeFixtureCommands):
            def deploy_application(self, request):  # type: ignore[no-untyped-def]
                deployment = super().deploy_application(request)
                attachment = dict(deployment.attachment_bundle)
                target = dict(attachment["target"])
                target["owner_application_id"] = "another-application"
                attachment["target"] = target
                return FixtureApplicationDeployment(
                    application_id=deployment.application_id,
                    image_reference=deployment.image_reference,
                    attachment_bundle=attachment,
                )

        commands = WrongOwnerCommands()

        result = FixtureSuiteLifecycle(commands).deploy(_request())

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.blockers, ("ATTACHMENT_BUNDLE_INVALID",))
        self.assertNotIn("register", commands.calls)


class LocalFixtureOperatorTest(unittest.TestCase):
    def test_discovers_exact_clean_main_and_current_platform_binding(self) -> None:
        class Git:
            def inspect(self):  # type: ignore[no-untyped-def]
                return GitSnapshot(
                    repository="comfforts/apps-platform",
                    revision=SOURCE_REVISION,
                    branch="main",
                    clean=True,
                    main_revision=SOURCE_REVISION,
                    origin_main_revision=SOURCE_REVISION,
                )

        class Platform:
            def read_platform(self, environment):  # type: ignore[no-untyped-def]
                return PlatformIntegrationState(
                    environment=environment,
                    lifecycle_state="deployed",
                    profile_digest=PROFILE_DIGEST,
                    platform_source_revision=PLATFORM_REVISION,
                    specification_digest=SPECIFICATION_DIGEST,
                    progress_digest=PROGRESS_DIGEST,
                    generation=7,
                    hostname="apps-staging.comfforts.com",
                    oauth_client_id=(
                        "1234567890-appsplatform.apps.googleusercontent.com"
                    ),
                    edge_caller_reference=EDGE_CALLER,
                    qualification_status="unqualified",
                )

        class Lifecycle:
            request = None

            def deploy(self, request):  # type: ignore[no-untyped-def]
                self.request = request
                return FixtureDeployResult("deployed", IMAGE_REFERENCE, (), 8, GENERATION_DIGEST)

        lifecycle = Lifecycle()
        operator = LocalFixtureOperator(Git(), Platform(), lifecycle)

        result = operator.deploy("staging", "fixture-public")

        self.assertEqual(result.outcome, "deployed")
        self.assertEqual(lifecycle.request.application_id, "fixture-public")
        self.assertEqual(lifecycle.request.fixture_source_revision, SOURCE_REVISION)
        self.assertEqual(
            lifecycle.request.expected_platform_source_revision,
            PLATFORM_REVISION,
        )
        self.assertEqual(lifecycle.request.expected_platform_generation, 7)

    def test_surfaces_exact_platform_generation_recovery_blocker(self) -> None:
        class Git:
            def inspect(self):  # type: ignore[no-untyped-def]
                return GitSnapshot(
                    repository="comfforts/apps-platform",
                    revision=SOURCE_REVISION,
                    branch="main",
                    clean=True,
                    main_revision=SOURCE_REVISION,
                    origin_main_revision=SOURCE_REVISION,
                )

        class Platform:
            def read_platform(self, environment):  # type: ignore[no-untyped-def]
                del environment
                raise PlatformIntegrationReadbackError(
                    "ACTIVE_REGISTRATION_GENERATION_RECOVERY_FAILED"
                )

        class Lifecycle:
            def handoff(self, request):  # type: ignore[no-untyped-def]
                raise AssertionError(f"unexpected handoff request: {request}")

        result = LocalFixtureOperator(Git(), Platform(), Lifecycle()).handoff(
            "staging",
            "fixture-public",
        )

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(
            result.blockers,
            ("ACTIVE_REGISTRATION_GENERATION_RECOVERY_FAILED",),
        )


@dataclass
class FakeDestructionIntegration:
    target_exists: bool = True
    calls: list[str] = field(default_factory=list)

    def detach(self, request):  # type: ignore[no-untyped-def]
        self.calls.append(f"detach:{request.application_id}")
        return RegistrationLifecycleResult("activated", 8, GENERATION_DIGEST)

    def status_applications(self, environment, application_ids):  # type: ignore[no-untyped-def]
        del environment
        self.calls.append("status")
        application_id = application_ids[0]
        return RegistrationStatusResult(
            "read",
            8,
            GENERATION_DIGEST,
            (
                RegistrationApplicationStatus(
                    application_id,
                    "suspended",
                    (
                        "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
                        f"us-west1:{application_id}"
                    ),
                    self.target_exists,
                    self.target_exists,
                ),
            ),
        )

    def outputs(self, request):  # type: ignore[no-untyped-def]
        self.calls.append("bundle")
        bundle = _bundle(
            request.application_id,
            request.access_mode,
            request.route_intent,
        )
        bundle["generation"] = request.expected_generation
        return IntegrationBundleResult(
            "generated",
            bundle,
            lifecycle_digest(bundle, "platform-integration-bundle"),
        )


@dataclass
class FakeDestructionTerminal:
    prompts: list[tuple[str, str]] = field(default_factory=list)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.prompts.append((prompt, expected))
        return True


@dataclass
class FakeDestructionExecutor:
    integration: FakeDestructionIntegration
    contexts: list[object] = field(default_factory=list)

    def execute(self, context):  # type: ignore[no-untyped-def]
        self.contexts.append(context)
        if "delete" in context.stage["actions"]:
            self.integration.target_exists = False
            return StageExecution(
                "succeeded",
                (("fixture-destroyed", context.stage["stage_id"]),),
                "sha256:" + ("9" * 64),
            )
        return StageExecution(
            "succeeded",
            (("attachment-reference", "reviewed"),),
            "sha256:" + ("8" * 64),
        )


class FixtureDestructionLifecycleTest(unittest.TestCase):
    def test_detaches_confirms_rereads_unlocks_and_destroys_selected_state(self) -> None:
        integration = FakeDestructionIntegration()
        terminal = FakeDestructionTerminal()
        executor = FakeDestructionExecutor(integration)
        commands = LocalFixtureLifecycleCommands(
            integration,  # type: ignore[arg-type]
            FakeImageProvider([SOURCE_REVISION]),
            executor,
            ("https://accounts.google.com", "123456789012345678901"),
            terminal=terminal,
        )
        lifecycle = FixtureSuiteLifecycle(commands)

        result = lifecycle.destroy(
            FixtureDestroyRequest(
                environment="staging",
                application_id="fixture-authenticated",
                operator_source_revision="c" * 40,
                fixture_source_revision=SOURCE_REVISION,
                expected_platform_source_revision=PLATFORM_REVISION,
                expected_platform_generation=7,
                expected_registration_generation_digest="sha256:" + ("7" * 64),
            )
        )

        self.assertEqual(result.outcome, "destroyed")
        self.assertEqual(integration.calls[0], "detach:fixture-authenticated")
        self.assertEqual(integration.calls.count("status"), 2)
        self.assertEqual(len(terminal.prompts), 1)
        self.assertEqual(
            terminal.prompts[0][1],
            "DESTROY staging FIXTURE fixture-authenticated APPLICATION STATE",
        )
        self.assertEqual(
            [context.stage["actions"] for context in executor.contexts],
            [["read", "update"], ["delete", "read"]],
        )


if __name__ == "__main__":
    unittest.main()
