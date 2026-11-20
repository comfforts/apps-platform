"""Deep Fixture Application deployment lifecycle behind injected commands."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from contracts.lifecycle import (
    validate_lifecycle_document,
    validate_lifecycle_relationships,
)


_REVISION = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_REFERENCE = re.compile(
    r"^[a-z][a-z0-9-]{1,61}[a-z0-9]-docker\.pkg\.dev/"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"[a-z][a-z0-9_-]{0,126}/"
    r"[a-z][a-z0-9._-]{0,126}@sha256:[0-9a-f]{64}$"
)


@dataclass(frozen=True, slots=True)
class FixtureDefinition:
    application_id: str
    access_mode: str
    route_intent: str


_FIXTURES = (
    FixtureDefinition("fixture-public", "public", "/fixture-public"),
    FixtureDefinition(
        "fixture-authenticated",
        "authenticated",
        "/fixture-authenticated",
    ),
    FixtureDefinition("fixture-restricted", "restricted", "/fixture-restricted"),
)


@dataclass(frozen=True, slots=True)
class FixtureDeployRequest:
    environment: str
    fixture_source_revision: str
    expected_platform_source_revision: str
    expected_platform_generation: int


@dataclass(frozen=True, slots=True)
class FixtureBundleRequest:
    environment: str
    application_id: str
    access_mode: str
    route_intent: str
    expected_platform_source_revision: str
    expected_platform_generation: int


@dataclass(frozen=True, slots=True)
class FixtureImageRequest:
    environment: str
    source_revision: str


@dataclass(frozen=True, slots=True)
class FixtureImageReadback:
    reference: str
    source_revision: str


@dataclass(frozen=True, slots=True)
class FixtureApplicationDeployRequest:
    environment: str
    application_id: str
    access_mode: str
    source_revision: str
    image: FixtureImageReadback
    integration_bundle: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FixtureApplicationDeployment:
    application_id: str
    image_reference: str
    attachment_bundle: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FixtureRegistrationRequest:
    environment: str
    integration_bundles: tuple[dict[str, Any], ...]
    deployments: tuple[FixtureApplicationDeployment, ...]


@dataclass(frozen=True, slots=True)
class FixtureRegistrationReadback:
    active: bool
    generation: int
    generation_digest: str
    application_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FixtureDeployResult:
    outcome: str
    image_reference: str | None
    application_ids: tuple[str, ...]
    registration_generation: int | None
    registration_generation_digest: str | None
    blockers: tuple[str, ...] = ()


class FixtureCommandError(RuntimeError):
    """One safe blocker returned by a Fixture Application command boundary."""


class FixtureCommands(Protocol):
    """Closed side-effect boundary consumed by the fixture lifecycle core."""

    def integration_bundle(
        self,
        request: FixtureBundleRequest,
    ) -> dict[str, Any]: ...

    def build_image(self, request: FixtureImageRequest) -> FixtureImageReadback: ...

    def deploy_application(
        self,
        request: FixtureApplicationDeployRequest,
    ) -> FixtureApplicationDeployment: ...

    def register(
        self,
        request: FixtureRegistrationRequest,
    ) -> FixtureRegistrationReadback: ...


class FixtureSuiteLifecycle:
    """Deploy all three synthetic applications as one fail-closed suite."""

    def __init__(self, commands: FixtureCommands) -> None:
        self._commands = commands

    @staticmethod
    def _blocked(*blockers: str) -> FixtureDeployResult:
        return FixtureDeployResult(
            outcome="blocked",
            image_reference=None,
            application_ids=(),
            registration_generation=None,
            registration_generation_digest=None,
            blockers=tuple(sorted(set(blockers))),
        )

    @staticmethod
    def _bundle_matches(
        bundle: dict[str, Any],
        definition: FixtureDefinition,
        request: FixtureDeployRequest,
    ) -> bool:
        return (
            not validate_lifecycle_document(bundle, "platform-integration-bundle")
            and bundle.get("environment") == request.environment
            and bundle.get("application_id") == definition.application_id
            and bundle.get("access_mode") == definition.access_mode
            and bundle.get("route_intent") == definition.route_intent
            and bundle.get("platform_source_revision")
            == request.expected_platform_source_revision
            and bundle.get("generation") == request.expected_platform_generation
        )

    @staticmethod
    def _deployment_matches(
        deployment: FixtureApplicationDeployment,
        definition: FixtureDefinition,
        image: FixtureImageReadback,
        bundle: dict[str, Any],
        request: FixtureDeployRequest,
    ) -> tuple[bool, str]:
        attachment = deployment.attachment_bundle
        if validate_lifecycle_document(attachment, "application-attachment-bundle"):
            return False, "ATTACHMENT_BUNDLE_INVALID"
        if validate_lifecycle_relationships(
            integration_bundle=bundle,
            attachment_bundle=attachment,
        ):
            return False, "ATTACHMENT_BUNDLE_MISMATCH"
        target = attachment.get("target")
        if (
            deployment.application_id != definition.application_id
            or deployment.image_reference != image.reference
            or attachment.get("environment") != request.environment
            or attachment.get("application_id") != definition.application_id
            or attachment.get("application_source_revision")
            != request.fixture_source_revision
            or not isinstance(target, dict)
            or target.get("owner_application_id") != definition.application_id
        ):
            return False, "FIXTURE_DEPLOYMENT_READBACK_MISMATCH"
        return True, ""

    def deploy(self, request: FixtureDeployRequest) -> FixtureDeployResult:
        """Reconcile the complete fixture suite in deterministic dependency order."""

        if request.environment != "staging":
            return self._blocked("FIXTURE_ENVIRONMENT_UNAVAILABLE")
        if (
            _REVISION.fullmatch(request.fixture_source_revision) is None
            or _REVISION.fullmatch(request.expected_platform_source_revision) is None
            or request.expected_platform_generation < 1
        ):
            return self._blocked("FIXTURE_REQUEST_INVALID")

        bundles: list[dict[str, Any]] = []
        try:
            for definition in _FIXTURES:
                bundle = self._commands.integration_bundle(
                    FixtureBundleRequest(
                        environment=request.environment,
                        application_id=definition.application_id,
                        access_mode=definition.access_mode,
                        route_intent=definition.route_intent,
                        expected_platform_source_revision=(
                            request.expected_platform_source_revision
                        ),
                        expected_platform_generation=(
                            request.expected_platform_generation
                        ),
                    )
                )
                if not self._bundle_matches(bundle, definition, request):
                    return self._blocked("INTEGRATION_BUNDLE_MISMATCH")
                bundles.append(bundle)

            image = self._commands.build_image(
                FixtureImageRequest(
                    environment=request.environment,
                    source_revision=request.fixture_source_revision,
                )
            )
            if _IMAGE_REFERENCE.fullmatch(image.reference) is None:
                return self._blocked("FIXTURE_IMAGE_NOT_IMMUTABLE")
            if image.source_revision != request.fixture_source_revision:
                return self._blocked("FIXTURE_IMAGE_SOURCE_MISMATCH")

            deployments: list[FixtureApplicationDeployment] = []
            for definition, bundle in zip(_FIXTURES, bundles, strict=True):
                deployment = self._commands.deploy_application(
                    FixtureApplicationDeployRequest(
                        environment=request.environment,
                        application_id=definition.application_id,
                        access_mode=definition.access_mode,
                        source_revision=request.fixture_source_revision,
                        image=image,
                        integration_bundle=bundle,
                    )
                )
                matched, blocker = self._deployment_matches(
                    deployment,
                    definition,
                    image,
                    bundle,
                    request,
                )
                if not matched:
                    return self._blocked(blocker)
                deployments.append(deployment)

            registration = self._commands.register(
                FixtureRegistrationRequest(
                    environment=request.environment,
                    integration_bundles=tuple(bundles),
                    deployments=tuple(deployments),
                )
            )
        except FixtureCommandError as error:
            return self._blocked(str(error) or "FIXTURE_COMMAND_FAILED")

        application_ids = tuple(item.application_id for item in deployments)
        if (
            not registration.active
            or registration.generation < 1
            or registration.application_ids != application_ids
            or re.fullmatch(r"sha256:[0-9a-f]{64}", registration.generation_digest)
            is None
        ):
            return self._blocked("FIXTURE_REGISTRATION_READBACK_MISMATCH")
        return FixtureDeployResult(
            outcome="deployed",
            image_reference=image.reference,
            application_ids=application_ids,
            registration_generation=registration.generation,
            registration_generation_digest=registration.generation_digest,
        )


__all__ = (
    "FixtureApplicationDeployRequest",
    "FixtureApplicationDeployment",
    "FixtureBundleRequest",
    "FixtureCommandError",
    "FixtureCommands",
    "FixtureDefinition",
    "FixtureDeployRequest",
    "FixtureDeployResult",
    "FixtureImageReadback",
    "FixtureImageRequest",
    "FixtureRegistrationReadback",
    "FixtureRegistrationRequest",
    "FixtureSuiteLifecycle",
)
