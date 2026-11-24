"""Concrete composition of fixture bundles, image, Terraform, and registration."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Protocol

from contracts.lifecycle import validate_lifecycle_document
from infrastructure.operator._interfaces import StageContext, StageExecution
from infrastructure.operator._interfaces import GitAdapter
from infrastructure.operator._interfaces import OperatorInterrupted, OperatorTerminal
from infrastructure.operator.deployment_provider import DeploymentProviderError
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationDeployment,
    FixtureApplicationStatus,
    FixtureApplicationDeployRequest,
    FixtureCommandError,
    FixtureDeployRequest,
    FixtureImageReadback,
    FixtureImageRequest,
    FixturePreparation,
    FixtureDestroyReadback,
    FixtureDestroyRequest,
    FixtureStatusResult,
)
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    IntegrationBundleRequest,
    RegistrationIntent,
    PlatformIntegrationReader,
)
from infrastructure.operator.source_authority import (
    source_authority_blockers,
    validate_source_authority,
)
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.local_fixture_preparations import (
    LocalFixturePreparations,
)
from infrastructure.operator.local_integration import PlatformIntegrationReadbackError


_GOOGLE_SUBJECT = re.compile(r"[1-9][0-9]{5,63}")


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
    application_id: str | None = None,
    route_readiness: Callable[[str], bool] | None = None,
) -> FixtureStatusResult:
    application_ids = (
        (application_id,)
        if application_id is not None
        else (
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
        )
    )
    readback = integration.status_applications(
        environment,
        application_ids,
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
                (
                    item.lifecycle == "active"
                    and item.target_exists
                    and item.target_ready
                    and route_readiness is not None
                    and route_readiness(item.application_id)
                ),
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
        restricted_member: tuple[str, str],
        handoffs: LocalApplicationHandoffs | None = None,
        terminal: OperatorTerminal | None = None,
        preparations: LocalFixturePreparations | None = None,
    ) -> None:
        if (
            restricted_member[0] != "https://accounts.google.com"
            or _GOOGLE_SUBJECT.fullmatch(restricted_member[1]) is None
        ):
            raise ValueError("restricted fixture member must be the verified operator")
        self._integration = integration
        self._image_provider = image_provider
        self._terraform_executor = terraform_executor
        self._restricted_member = restricted_member
        self._handoffs = handoffs
        self._terminal = terminal
        self._preparations = preparations

    def build_image(self, request: FixtureImageRequest) -> FixtureImageReadback:
        try:
            reference = self._image_provider.publish_fixture_image(
                request.source_revision
            )
            observed = self._image_provider.read_fixture_image(request.source_revision)
        except DeploymentProviderError as error:
            if self._terminal is not None and error.diagnostic:
                self._terminal.write(
                    "FIXTURE IMAGE BUILD ERROR\n"
                    + json.dumps(
                        {"blocker": str(error), **error.diagnostic},
                        indent=2,
                        sort_keys=True,
                    )
                )
                if "diagnostic_path" in error.diagnostic:
                    self._terminal.write(
                        "Private command diagnostics may contain sensitive provider "
                        "data. Inspect locally; do not commit or share them unredacted."
                    )
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
            application_project = request.integration_bundle["application_project"]
            network = request.integration_bundle["network"]
            if (
                not isinstance(reference, dict)
                or not isinstance(identity, dict)
                or not isinstance(attachment_contract, dict)
                or not isinstance(application_project, dict)
                or not isinstance(network, dict)
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
                    "application_project_id": application_project["project_id"],
                    "network_reference": network["network_reference"],
                    "subnetwork_reference": network["subnetwork_reference"],
                    "egress_mode": network["egress_mode"],
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

    def prepared_handoff(
        self,
        request: FixtureDeployRequest,
    ) -> FixturePreparation | None:
        if self._preparations is None:
            return None
        try:
            preparation = self._preparations.read(request)
            if preparation is None:
                return None
            observed_image = self._image_provider.read_fixture_image(
                request.fixture_source_revision
            )
        except (DeploymentProviderError, OSError, ValueError) as error:
            raise FixtureCommandError(
                "FIXTURE_PREPARATION_READBACK_FAILED"
            ) from error
        if observed_image != preparation.image.reference:
            return None
        validation = self._integration.validate_attachment(
            preparation.integration_bundle,
            preparation.deployment.attachment_bundle,
        )
        if validation.outcome != "validated":
            return None
        return preparation

    def record_prepared_handoff(
        self,
        request: FixtureDeployRequest,
        preparation: FixturePreparation,
    ) -> FixturePreparation:
        if self._preparations is None:
            return preparation
        try:
            published = self._preparations.publish(
                request,
                preparation.image,
                preparation.integration_bundle,
                preparation.deployment,
            )
            return self._preparations.publish_registration_intent(
                request,
                published,
                self._intent(request.application_id),
            )
        except (FileExistsError, OSError, ValueError) as error:
            raise FixtureCommandError(
                "FIXTURE_PREPARATION_PUBLICATION_FAILED"
            ) from error

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

    def _intent(self, application_id: str) -> RegistrationIntent:
        return RegistrationIntent(
            catalogue_visibility=(
                "unlisted"
                if application_id == "fixture-authenticated"
                else "listed"
            ),
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
                (self._restricted_member,)
                if application_id == "fixture-restricted"
                else ()
            ),
        )

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ) -> FixtureStatusResult:
        return _status(self._integration, environment, application_id)

    def destroy_application(
        self,
        request: FixtureDestroyRequest,
    ) -> FixtureDestroyReadback:
        if self._terminal is None:
            raise FixtureCommandError("FIXTURE_DESTRUCTION_TERMINAL_UNAVAILABLE")
        detached = self._integration.status_applications(
            request.environment,
            (request.application_id,),
        )
        if (
            detached.outcome != "read"
            or detached.generation is None
            or detached.generation_digest is None
            or detached.generation != request.expected_platform_generation
            or detached.generation_digest
            != request.expected_registration_generation_digest
            or len(detached.applications) != 1
            or detached.applications[0].application_id != request.application_id
            or detached.applications[0].lifecycle != "suspended"
            or not detached.applications[0].target_exists
        ):
            raise FixtureCommandError("FIXTURE_ROUTE_MUST_BE_DETACHED")

        expected = (
            f"DESTROY {request.environment} FIXTURE {request.application_id} "
            "APPLICATION STATE"
        )
        try:
            confirmed = self._terminal.confirm_exact(
                f"Type {expected!r} to destroy only this Fixture Application State: ",
                expected,
            )
        except OperatorInterrupted:
            return FixtureDestroyReadback(
                "interrupted",
                request.application_id,
                detached.generation,
                detached.generation_digest,
                ("FIXTURE_DESTRUCTION_INTERRUPTED",),
            )
        if not confirmed:
            return FixtureDestroyReadback(
                "cancelled",
                request.application_id,
                detached.generation,
                detached.generation_digest,
                ("FIXTURE_DESTRUCTION_NOT_CONFIRMED",),
            )

        reread = self._integration.status_applications(
            request.environment,
            (request.application_id,),
        )
        if (
            reread.outcome != "read"
            or reread.generation != detached.generation
            or reread.generation_digest != detached.generation_digest
            or len(reread.applications) != 1
            or reread.applications[0].application_id != request.application_id
            or reread.applications[0].lifecycle != "suspended"
            or not reread.applications[0].target_exists
        ):
            raise FixtureCommandError("FIXTURE_DESTRUCTION_REREAD_MISMATCH")

        definition = {
            "fixture-public": ("public", "/fixture-public"),
            "fixture-authenticated": (
                "authenticated",
                "/fixture-authenticated",
            ),
            "fixture-restricted": ("restricted", "/fixture-restricted"),
        }[request.application_id]
        bundle_result = self._integration.outputs(
            IntegrationBundleRequest(
                environment=request.environment,
                application_id=request.application_id,
                access_mode=definition[0],
                route_intent=definition[1],
                expected_platform_source_revision=(
                    request.expected_platform_source_revision
                ),
                expected_generation=detached.generation,
            )
        )
        if bundle_result.outcome != "generated" or bundle_result.bundle is None:
            raise FixtureCommandError("FIXTURE_DESTROY_BUNDLE_FAILED")
        try:
            image_reference = self._image_provider.read_fixture_image(
                request.fixture_source_revision
            )
        except DeploymentProviderError as error:
            raise FixtureCommandError("FIXTURE_IMAGE_READBACK_FAILED") from error
        if image_reference is None:
            raise FixtureCommandError("FIXTURE_IMAGE_READBACK_MISSING")
        application_request = FixtureApplicationDeployRequest(
            environment=request.environment,
            application_id=request.application_id,
            access_mode=definition[0],
            source_revision=request.operator_source_revision,
            image=FixtureImageReadback(
                image_reference,
                request.fixture_source_revision,
            ),
            integration_bundle=bundle_result.bundle,
        )
        base = self._stage(application_request)
        unlock = StageContext(
            environment=base.environment,
            source_revision=base.source_revision,
            specification_digest=base.specification_digest,
            stage={
                **base.stage,
                "actions": ["read", "update"],
                "destruction_enabled": True,
            },
            inputs=base.inputs,
        )
        unlocked = self._terraform_executor.execute(unlock)
        if unlocked.outcome != "succeeded":
            raise FixtureCommandError(
                unlocked.blockers[0]
                if unlocked.blockers
                else "FIXTURE_DESTRUCTION_UNLOCK_FAILED"
            )
        destroy = StageContext(
            environment=base.environment,
            source_revision=base.source_revision,
            specification_digest=base.specification_digest,
            stage={
                **base.stage,
                "actions": ["delete", "read"],
                "destruction_enabled": True,
                "produces": ["fixture-destroyed"],
            },
            inputs=base.inputs,
        )
        destroyed = self._terraform_executor.execute(destroy)
        if (
            destroyed.outcome != "succeeded"
            or destroyed.outputs
            != (("fixture-destroyed", request.application_id),)
        ):
            raise FixtureCommandError(
                destroyed.blockers[0]
                if destroyed.blockers
                else "FIXTURE_DESTRUCTION_FAILED"
            )
        final = self._integration.status_applications(
            request.environment,
            (request.application_id,),
        )
        if (
            final.outcome != "read"
            or len(final.applications) != 1
            or final.applications[0].lifecycle != "suspended"
            or final.applications[0].target_exists
        ):
            raise FixtureCommandError("FIXTURE_DESTRUCTION_FINAL_READBACK_MISMATCH")
        return FixtureDestroyReadback(
            "destroyed",
            request.application_id,
            detached.generation,
            detached.generation_digest,
        )


class LocalFixtureOperator:
    """Resolve repository and platform bindings before one fixture deployment."""

    def __init__(
        self,
        git: GitAdapter,
        platform: PlatformIntegrationReader,
        lifecycle,
        handoffs: LocalApplicationHandoffs | None = None,
        *,
        source_authority: str = "accepted",
    ) -> None:  # type: ignore[no-untyped-def]
        self._git = git
        self._platform = platform
        self._lifecycle = lifecycle
        self._handoffs = handoffs
        self._source_authority = validate_source_authority(source_authority)

    def handoff(
        self,
        environment: str,
        application_id: str,
        integration_bundle: dict[str, Any],
        integration_bundle_path: str,
    ):  # type: ignore[no-untyped-def]
        from infrastructure.operator.fixture_lifecycle import (
            FixtureDeployRequest,
            FixtureHandoffResult,
        )

        try:
            source = self._git.inspect()
        except Exception:
            return FixtureHandoffResult(
                "blocked",
                application_id,
                None,
                None,
                None,
                None,
                None,
                blockers=("FIXTURE_SOURCE_READBACK_FAILED",),
            )
        try:
            platform = self._platform.read_platform(environment)
        except PlatformIntegrationReadbackError as error:
            return FixtureHandoffResult(
                "blocked",
                application_id,
                None,
                None,
                None,
                None,
                None,
                blockers=(error.code,),
            )
        except Exception:
            return FixtureHandoffResult(
                "blocked",
                application_id,
                None,
                None,
                None,
                None,
                None,
                blockers=("PLATFORM_INTEGRATION_READBACK_FAILED",),
            )
        blockers = list(
            source_authority_blockers(
                source,
                environment,
                self._source_authority,
            )
        )
        if platform.environment != environment or platform.lifecycle_state != "deployed":
            blockers.append("PLATFORM_NOT_DEPLOYED")
        if blockers:
            return FixtureHandoffResult(
                "blocked",
                application_id,
                None,
                None,
                None,
                None,
                None,
                blockers=tuple(sorted(set(blockers))),
            )
        return self._lifecycle.handoff(
            FixtureDeployRequest(
                environment=environment,
                application_id=application_id,
                fixture_source_revision=source.revision,
                expected_platform_source_revision=(
                    platform.platform_source_revision
                ),
                expected_platform_generation=platform.generation,
                source_authority=self._source_authority,
                integration_bundle=integration_bundle,
                integration_bundle_path=integration_bundle_path,
            )
        )

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ):  # type: ignore[no-untyped-def]
        return self._lifecycle.status(environment, application_id)

    def destroy(self, environment: str, application_id: str):  # type: ignore[no-untyped-def]
        from infrastructure.operator.fixture_lifecycle import (
            FixtureDestroyRequest,
            FixtureDestroyResult,
        )

        try:
            source = self._git.inspect()
            platform = self._platform.read_platform(environment)
            status = self._lifecycle.status(environment, application_id)
        except Exception:
            return FixtureDestroyResult(
                "blocked",
                application_id,
                None,
                None,
                ("FIXTURE_DESTRUCTION_PREFLIGHT_FAILED",),
            )
        if self._handoffs is None:
            return FixtureDestroyResult(
                "blocked",
                application_id,
                None,
                None,
                ("APPLICATION_HANDOFF_READBACK_UNAVAILABLE",),
            )
        selected = next(
            (item for item in status.applications if item.application_id == application_id),
            None,
        )
        if (
            status.outcome != "read"
            or status.registration_generation is None
            or status.registration_generation_digest is None
            or selected is None
        ):
            return FixtureDestroyResult(
                "blocked",
                application_id,
                None,
                None,
                ("FIXTURE_DESTRUCTION_STATUS_MISMATCH",),
            )
        if selected.lifecycle == "suspended" and not selected.target_exists:
            return FixtureDestroyResult(
                "destroyed",
                application_id,
                status.registration_generation,
                status.registration_generation_digest,
            )
        try:
            handoff = self._handoffs.latest_for_application(
                environment,
                application_id,
                status.registration_generation,
            )
        except ValueError:
            handoff = None
        blockers = list(
            source_authority_blockers(
                source,
                environment,
                self._source_authority,
            )
        )
        if platform.lifecycle_state != "deployed":
            blockers.append("PLATFORM_NOT_DEPLOYED")
        if handoff is None:
            blockers.append("APPLICATION_HANDOFF_READBACK_MISSING")
        if blockers:
            return FixtureDestroyResult(
                "blocked",
                application_id,
                status.registration_generation,
                status.registration_generation_digest,
                tuple(sorted(set(blockers))),
            )
        return self._lifecycle.destroy(
            FixtureDestroyRequest(
                environment,
                application_id,
                source.revision,
                handoff.application_source_revision,
                platform.platform_source_revision,
                status.registration_generation,
                status.registration_generation_digest,
            )
        )


class LocalFixtureStatusOperator:
    """Expose only the read-only registration/provider reconciliation."""

    def __init__(
        self,
        integration: ApplicationIntegrationLifecycle,
        route_readiness: Callable[[str], bool],
    ) -> None:
        self._integration = integration
        self._route_readiness = route_readiness

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ) -> FixtureStatusResult:
        return _status(
            self._integration,
            environment,
            application_id,
            self._route_readiness,
        )


__all__ = (
    "FixtureImageProvider",
    "FixtureTerraformExecutor",
    "LocalFixtureOperator",
    "LocalFixtureStatusOperator",
    "LocalFixtureLifecycleCommands",
)
