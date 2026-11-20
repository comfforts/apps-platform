"""Concrete composition of fixture bundles, image, Terraform, and registration."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from contracts.lifecycle import validate_lifecycle_document
from infrastructure.operator._interfaces import StageContext, StageExecution
from infrastructure.operator._interfaces import GitAdapter
from infrastructure.operator.deployment_provider import DeploymentProviderError
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationDeployment,
    FixtureApplicationStatus,
    FixtureApplicationDeployRequest,
    FixtureBundleRequest,
    FixtureCommandError,
    FixtureImageReadback,
    FixtureImageRequest,
    FixtureRegistrationReadback,
    FixtureRegistrationRequest,
    FixtureStatusResult,
)
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    IntegrationBundleRequest,
    RegistrationEntry,
    RegistrationIntent,
    PlatformIntegrationReader,
)
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs


_RESTRICTED_MEMBER = ("https://accounts.google.com", "synthetic-subject")


class FixtureImageProvider(Protocol):
    def publish_fixture_image(self, source_revision: str) -> str: ...

    def read_fixture_image(self, source_revision: str) -> str | None: ...


class FixtureTerraformExecutor(Protocol):
    def execute(self, context: StageContext) -> StageExecution: ...


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _status(
    integration: ApplicationIntegrationLifecycle,
    environment: str,
) -> FixtureStatusResult:
    readback = integration.status_applications(
        environment,
        (
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
        ),
    )
    return FixtureStatusResult(
        outcome=readback.outcome,
        registration_generation=readback.generation,
        registration_generation_digest=readback.generation_digest,
        applications=tuple(
            FixtureApplicationStatus(
                item.application_id,
                item.lifecycle,
                item.target_exists,
                item.target_ready,
            )
            for item in readback.applications
        ),
        blockers=readback.blockers,
    )


class LocalFixtureLifecycleCommands:
    """Provide one shallow fixture lifecycle over reviewed deep modules."""

    def __init__(
        self,
        integration: ApplicationIntegrationLifecycle,
        image_provider: FixtureImageProvider,
        terraform_executor: FixtureTerraformExecutor,
        handoffs: LocalApplicationHandoffs | None = None,
    ) -> None:
        self._integration = integration
        self._image_provider = image_provider
        self._terraform_executor = terraform_executor
        self._handoffs = handoffs

    def integration_bundle(self, request: FixtureBundleRequest) -> dict[str, Any]:
        result = self._integration.outputs(
            IntegrationBundleRequest(
                environment=request.environment,
                application_id=request.application_id,
                access_mode=request.access_mode,
                route_intent=request.route_intent,
                expected_platform_source_revision=(
                    request.expected_platform_source_revision
                ),
                expected_generation=request.expected_platform_generation,
            )
        )
        if result.outcome != "generated" or result.bundle is None:
            raise FixtureCommandError(
                result.blockers[0] if result.blockers else "INTEGRATION_BUNDLE_FAILED"
            )
        return result.bundle

    def build_image(self, request: FixtureImageRequest) -> FixtureImageReadback:
        try:
            reference = self._image_provider.publish_fixture_image(
                request.source_revision
            )
            observed = self._image_provider.read_fixture_image(request.source_revision)
        except DeploymentProviderError as error:
            raise FixtureCommandError(str(error) or "FIXTURE_IMAGE_FAILED") from error
        if observed != reference:
            raise FixtureCommandError("FIXTURE_IMAGE_READBACK_MISMATCH")
        return FixtureImageReadback(reference, request.source_revision)

    @staticmethod
    def _stage(request: FixtureApplicationDeployRequest) -> StageContext:
        specification_digest = _digest(
            {
                "application_id": request.application_id,
                "environment": request.environment,
                "fixture_source_revision": request.source_revision,
                "image_reference": request.image.reference,
                "integration_bundle": request.integration_bundle,
            }
        )
        return StageContext(
            environment=request.environment,
            source_revision=request.source_revision,
            specification_digest=specification_digest,
            stage={
                "stage_id": request.application_id,
                "actions": ["create", "read", "update"],
                "resource_types": [
                    "google_service_account",
                    "google_cloud_run_v2_service",
                    "google_cloud_run_v2_service_iam_member",
                ],
                "consumes": [
                    "fixture-image-reference",
                    "platform-integration-bundle",
                ],
                "produces": ["attachment-reference"],
                "manual_checkpoint": "none",
                "readback": "provider-verified",
            },
            inputs=(
                ("fixture-image-reference", request.image.reference),
                (
                    "platform-integration-bundle",
                    _canonical(request.integration_bundle),
                ),
            ),
        )

    def deploy_application(
        self,
        request: FixtureApplicationDeployRequest,
    ) -> FixtureApplicationDeployment:
        execution = self._terraform_executor.execute(self._stage(request))
        if execution.outcome != "succeeded":
            raise FixtureCommandError(
                execution.blockers[0] if execution.blockers else "FIXTURE_DEPLOY_FAILED"
            )
        if tuple(name for name, _ in execution.outputs) != ("attachment-reference",):
            raise FixtureCommandError("FIXTURE_READBACK_MISSING")
        try:
            reference = json.loads(execution.outputs[0][1])
            identity = request.integration_bundle["identity"]
            attachment_contract = request.integration_bundle["attachment_contract"]
            if (
                not isinstance(reference, dict)
                or not isinstance(identity, dict)
                or not isinstance(attachment_contract, dict)
            ):
                raise TypeError
            attachment = {
                "contract_version": 1,
                "document_kind": "application-attachment-bundle",
                "environment": request.environment,
                "application_id": request.application_id,
                "attachment_revision": self._attachment_revision(
                    request.integration_bundle,
                    request.source_revision,
                ),
                "platform_integration_bundle_digest": _digest(
                    request.integration_bundle
                ),
                "application_source_revision": request.source_revision,
                "target": {
                    "owner_application_id": reference["owner_id"],
                    "adapter_kind": reference["adapter_kind"],
                    "resource_reference": reference["resource_reference"],
                    "ingress_mode": attachment_contract["ingress_mode"],
                    "caller_grant": identity["edge_caller_reference"],
                    "audience": reference["audience"],
                },
            }
        except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise FixtureCommandError("FIXTURE_READBACK_INVALID") from error
        if validate_lifecycle_document(attachment, "application-attachment-bundle"):
            raise FixtureCommandError("ATTACHMENT_BUNDLE_INVALID")
        validated = self._integration.validate_attachment(
            request.integration_bundle,
            attachment,
        )
        if validated.outcome != "validated":
            raise FixtureCommandError(
                validated.blockers[0]
                if validated.blockers
                else "ATTACHMENT_READBACK_FAILED"
            )
        return FixtureApplicationDeployment(
            request.application_id,
            request.image.reference,
            attachment,
        )

    def _attachment_revision(
        self,
        bundle: dict[str, Any],
        source_revision: str,
    ) -> int:
        if self._handoffs is None:
            return 1
        application_id = str(bundle["application_id"])
        generation = int(bundle["generation"])
        try:
            previous = self._handoffs.latest_for_application(
                str(bundle["environment"]),
                application_id,
                generation,
            )
        except ValueError as error:
            raise FixtureCommandError("APPLICATION_HANDOFF_READBACK_FAILED") from error
        if previous is None:
            return 1
        if (
            previous.application_source_revision == source_revision
            and previous.integration_bundle_digest == _digest(bundle)
        ):
            return previous.attachment_revision
        return previous.attachment_revision + 1

    @staticmethod
    def _intent(application_id: str) -> RegistrationIntent:
        return RegistrationIntent(
            catalogue_visibility="listed",
            catalogue_title={
                "fixture-public": "Public fixture",
                "fixture-authenticated": "Authenticated fixture",
                "fixture-restricted": "Restricted fixture",
            }[application_id],
            catalogue_summary="Synthetic App Platform qualification application",
            attachment_id="primary",
            mount_path="/",
            forwarding_mode="strip_application_prefix",
            restricted_members=(
                (_RESTRICTED_MEMBER,) if application_id == "fixture-restricted" else ()
            ),
        )

    def register(
        self,
        request: FixtureRegistrationRequest,
    ) -> FixtureRegistrationReadback:
        entries = tuple(
            RegistrationEntry(
                bundle,
                deployment.attachment_bundle,
                self._intent(deployment.application_id),
            )
            for bundle, deployment in zip(
                request.integration_bundles,
                request.deployments,
                strict=True,
            )
        )
        result = self._integration.register_complete(entries)
        if (
            result.outcome not in {"activated", "unchanged"}
            or result.generation is None
            or result.generation_digest is None
        ):
            raise FixtureCommandError(
                result.blockers[0] if result.blockers else "FIXTURE_REGISTRATION_FAILED"
            )
        if self._handoffs is not None:
            try:
                for bundle, deployment in zip(
                    request.integration_bundles,
                    request.deployments,
                    strict=True,
                ):
                    record = self._handoffs.from_bundles(
                        bundle,
                        deployment.attachment_bundle,
                        result.generation,
                        result.generation_digest,
                    )
                    if not self._handoffs.record(record):
                        raise ValueError("handoff readback mismatch")
            except (FileExistsError, ValueError) as error:
                raise FixtureCommandError("APPLICATION_HANDOFF_RECORD_FAILED") from error
        return FixtureRegistrationReadback(
            active=True,
            generation=result.generation,
            generation_digest=result.generation_digest,
            application_ids=tuple(
                deployment.application_id for deployment in request.deployments
            ),
        )

    def status(self, environment: str) -> FixtureStatusResult:
        return _status(self._integration, environment)


class LocalFixtureOperator:
    """Resolve repository and platform bindings before one fixture deployment."""

    def __init__(
        self,
        git: GitAdapter,
        platform: PlatformIntegrationReader,
        lifecycle,
    ) -> None:  # type: ignore[no-untyped-def]
        self._git = git
        self._platform = platform
        self._lifecycle = lifecycle

    def deploy(self, environment: str):  # type: ignore[no-untyped-def]
        from infrastructure.operator.fixture_lifecycle import (
            FixtureDeployRequest,
            FixtureDeployResult,
        )

        try:
            source = self._git.inspect()
            platform = self._platform.read_platform(environment)
        except Exception:
            return FixtureDeployResult(
                "blocked",
                None,
                (),
                None,
                None,
                ("FIXTURE_PREFLIGHT_FAILED",),
            )
        blockers = []
        if source.repository != "comfforts/apps-platform":
            blockers.append("SOURCE_REPOSITORY_MISMATCH")
        if not source.clean:
            blockers.append("SOURCE_WORKTREE_DIRTY")
        if source.branch != "main":
            blockers.append("SOURCE_BRANCH_MISMATCH")
        if not (
            source.revision == source.main_revision == source.origin_main_revision
        ):
            blockers.append("SOURCE_REVISION_MISMATCH")
        if platform.environment != environment or platform.lifecycle_state != "deployed":
            blockers.append("PLATFORM_NOT_DEPLOYED")
        if blockers:
            return FixtureDeployResult(
                "blocked",
                None,
                (),
                None,
                None,
                tuple(sorted(set(blockers))),
            )
        return self._lifecycle.deploy(
            FixtureDeployRequest(
                environment=environment,
                fixture_source_revision=source.revision,
                expected_platform_source_revision=(
                    platform.platform_source_revision
                ),
                expected_platform_generation=platform.generation,
            )
        )

    def status(self, environment: str):  # type: ignore[no-untyped-def]
        return self._lifecycle.status(environment)


class LocalFixtureStatusOperator:
    """Expose only the read-only registration/provider reconciliation."""

    def __init__(self, integration: ApplicationIntegrationLifecycle) -> None:
        self._integration = integration

    def status(self, environment: str) -> FixtureStatusResult:
        return _status(self._integration, environment)


__all__ = (
    "FixtureImageProvider",
    "FixtureTerraformExecutor",
    "LocalFixtureOperator",
    "LocalFixtureStatusOperator",
    "LocalFixtureLifecycleCommands",
)
