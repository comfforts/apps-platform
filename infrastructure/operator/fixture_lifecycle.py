"""Deep Fixture Application deployment lifecycle behind injected commands."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from contracts.lifecycle import (
    validate_versioned_lifecycle_document,
    validate_versioned_lifecycle_relationships,
    versioned_lifecycle_digest,
)
from infrastructure.operator._interfaces import OperatorTerminal


_REVISION = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_REFERENCE = re.compile(
    r"^[a-z][a-z0-9-]{1,61}[a-z0-9]-docker\.pkg\.dev/"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]/"
    r"[a-z][a-z0-9_-]{0,126}/"
    r"[a-z][a-z0-9._-]{0,126}@sha256:[0-9a-f]{64}$"
)


@dataclass(frozen=True, slots=True)
class FixtureDefinition:
    """Stable fixture admission posture and permitted explicit identity behavior."""

    application_id: str
    access_mode: str
    route_intent: str
    identity_deliveries: tuple[str, ...]


_FIXTURES = (
    FixtureDefinition(
        "fixture-public",
        "public",
        "/fixture-public",
        ("none", "optional"),
    ),
    FixtureDefinition(
        "fixture-authenticated",
        "authenticated",
        "/fixture-authenticated",
        ("required",),
    ),
    FixtureDefinition(
        "fixture-restricted",
        "restricted",
        "/fixture-restricted",
        ("required",),
    ),
)
_FIXTURE_BY_ID = {item.application_id: item for item in _FIXTURES}


@dataclass(frozen=True, slots=True)
class FixtureDeployRequest:
    """Exact fixture handoff request including application-owned catalogue intent."""

    environment: str
    application_id: str
    fixture_source_revision: str
    expected_platform_source_revision: str
    expected_platform_generation: int
    catalogue_visibility: str
    source_authority: str = "accepted"
    integration_bundle: dict[str, Any] | None = None
    integration_bundle_path: str | None = None


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
class FixturePreparation:
    image: FixtureImageReadback
    integration_bundle: dict[str, Any]
    deployment: FixtureApplicationDeployment
    integration_bundle_digest: str
    attachment_bundle_digest: str
    integration_bundle_path: str | None = None
    attachment_bundle_path: str | None = None
    registration_intent_path: str | None = None


@dataclass(frozen=True, slots=True)
class FixtureHandoffResult:
    outcome: str
    application_id: str
    image_reference: str | None
    integration_bundle_digest: str | None
    integration_bundle_path: str | None
    attachment_bundle_digest: str | None
    attachment_bundle_path: str | None
    registration_intent_path: str | None = None
    preparation_reused: bool = False
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FixtureApplicationStatus:
    """Registration policy, provider posture, and route readiness for one fixture."""

    application_id: str
    lifecycle: str
    catalogue_visibility: str
    target_exists: bool
    target_ready: bool
    route_ready: bool


@dataclass(frozen=True, slots=True)
class FixtureStatusResult:
    """Read-only status result for all or one selected qualification fixture."""

    outcome: str
    registration_generation: int | None
    registration_generation_digest: str | None
    applications: tuple[FixtureApplicationStatus, ...]
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FixtureDestroyRequest:
    environment: str
    application_id: str
    operator_source_revision: str
    fixture_source_revision: str
    expected_platform_source_revision: str
    expected_platform_generation: int
    expected_registration_generation_digest: str


@dataclass(frozen=True, slots=True)
class FixtureDestroyReadback:
    outcome: str
    application_id: str
    registration_generation: int | None
    registration_generation_digest: str | None
    blockers: tuple[str, ...] = ()


FixtureDestroyResult = FixtureDestroyReadback


class FixtureCommandError(RuntimeError):
    """One safe blocker returned by a Fixture Application command boundary."""


class FixtureCommands(Protocol):
    """Closed side-effect boundary consumed by the fixture lifecycle core."""

    def build_image(self, request: FixtureImageRequest) -> FixtureImageReadback: ...

    def deploy_application(
        self,
        request: FixtureApplicationDeployRequest,
    ) -> FixtureApplicationDeployment: ...

    def prepared_handoff(
        self,
        request: FixtureDeployRequest,
    ) -> FixturePreparation | None: ...

    def record_prepared_handoff(
        self,
        request: FixtureDeployRequest,
        preparation: FixturePreparation,
    ) -> FixturePreparation: ...

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ) -> FixtureStatusResult: ...

    def destroy_application(
        self,
        request: FixtureDestroyRequest,
    ) -> FixtureDestroyReadback: ...


class FixtureSuiteLifecycle:
    """Operate one selected fixture while preserving suite-wide qualification."""

    def __init__(
        self,
        commands: FixtureCommands,
        terminal: OperatorTerminal | None = None,
    ) -> None:
        self._commands = commands
        self._terminal = terminal

    def _announce_stage(self, index: int, total: int, title: str) -> None:
        if self._terminal is not None:
            self._terminal.write(f"▸ Stage {index}/{total} · {title}")

    @staticmethod
    def _handoff_blocked(
        request: FixtureDeployRequest,
        *blockers: str,
    ) -> FixtureHandoffResult:
        return FixtureHandoffResult(
            outcome="blocked",
            application_id=request.application_id,
            image_reference=None,
            integration_bundle_digest=None,
            integration_bundle_path=None,
            attachment_bundle_digest=None,
            attachment_bundle_path=None,
            registration_intent_path=None,
            blockers=tuple(sorted(set(blockers))),
        )

    @staticmethod
    def _definition(
        request: FixtureDeployRequest,
    ) -> tuple[FixtureDefinition | None, str | None]:
        """Validate one closed fixture profile and explicit catalogue choice."""

        if request.environment != "staging":
            return None, "FIXTURE_ENVIRONMENT_UNAVAILABLE"
        definition = _FIXTURE_BY_ID.get(request.application_id)
        if (
            definition is None
            or _REVISION.fullmatch(request.fixture_source_revision) is None
            or _REVISION.fullmatch(request.expected_platform_source_revision) is None
            or request.expected_platform_generation < 1
            or request.catalogue_visibility not in {"listed", "unlisted"}
            or request.source_authority not in {"accepted", "candidate"}
        ):
            return None, "FIXTURE_REQUEST_INVALID"
        return definition, None

    @staticmethod
    def _bundle_matches(
        bundle: dict[str, Any],
        definition: FixtureDefinition,
        request: FixtureDeployRequest,
    ) -> bool:
        return (
            bundle.get("contract_version") == 2
            and not validate_versioned_lifecycle_document(
                bundle,
                "platform-integration-bundle",
            )
            and bundle.get("environment") == request.environment
            and bundle.get("application_id") == definition.application_id
            and bundle.get("access_mode") == definition.access_mode
            and bundle.get("identity_delivery") in definition.identity_deliveries
            and bundle.get("route_intent") == definition.route_intent
            and bundle.get("platform_source_revision")
            == request.expected_platform_source_revision
            and bundle.get("platform_source_authority")
            == request.source_authority
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
        if attachment.get("contract_version") != 2:
            return False, "ATTACHMENT_BUNDLE_VERSION_UNSUPPORTED"
        if validate_versioned_lifecycle_document(
            attachment,
            "application-attachment-bundle",
        ):
            return False, "ATTACHMENT_BUNDLE_INVALID"
        if validate_versioned_lifecycle_relationships(
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

    @classmethod
    def _preparation_matches(
        cls,
        preparation: FixturePreparation,
        definition: FixtureDefinition,
        request: FixtureDeployRequest,
    ) -> tuple[bool, str]:
        if not cls._bundle_matches(
            preparation.integration_bundle,
            definition,
            request,
        ):
            return False, "INTEGRATION_BUNDLE_MISMATCH"
        if (
            _IMAGE_REFERENCE.fullmatch(preparation.image.reference) is None
            or preparation.image.source_revision != request.fixture_source_revision
        ):
            return False, "FIXTURE_IMAGE_SOURCE_MISMATCH"
        matched, blocker = cls._deployment_matches(
            preparation.deployment,
            definition,
            preparation.image,
            preparation.integration_bundle,
            request,
        )
        if not matched:
            return False, blocker
        if (
            preparation.integration_bundle_digest
            != versioned_lifecycle_digest(
                preparation.integration_bundle,
                "platform-integration-bundle",
            )
            or preparation.attachment_bundle_digest
            != versioned_lifecycle_digest(
                preparation.deployment.attachment_bundle,
                "application-attachment-bundle",
            )
        ):
            return False, "FIXTURE_PREPARATION_DIGEST_MISMATCH"
        return True, ""

    def _prepare(
        self,
        request: FixtureDeployRequest,
        definition: FixtureDefinition,
        *,
        total_stages: int,
        preparation_stage_title: str,
        reuse_stage_title: str,
    ) -> tuple[FixturePreparation | None, bool, tuple[str, ...]]:
        self._announce_stage(1, total_stages, "Resolve the Platform Handoff")
        try:
            prepared = self._commands.prepared_handoff(request)
            if prepared is not None:
                matched, blocker = self._preparation_matches(
                    prepared,
                    definition,
                    request,
                )
                if not matched:
                    return None, False, (blocker,)
                self._announce_stage(
                    2,
                    total_stages,
                    reuse_stage_title,
                )
                return prepared, True, ()

            bundle = request.integration_bundle
            if bundle is None:
                return None, False, ("INTEGRATION_BUNDLE_REQUIRED",)
            if not self._bundle_matches(bundle, definition, request):
                return None, False, ("INTEGRATION_BUNDLE_MISMATCH",)

            self._announce_stage(
                2,
                total_stages,
                preparation_stage_title,
            )
            image = self._commands.build_image(
                FixtureImageRequest(
                    environment=request.environment,
                    source_revision=request.fixture_source_revision,
                )
            )
            if _IMAGE_REFERENCE.fullmatch(image.reference) is None:
                return None, False, ("FIXTURE_IMAGE_NOT_IMMUTABLE",)
            if image.source_revision != request.fixture_source_revision:
                return None, False, ("FIXTURE_IMAGE_SOURCE_MISMATCH",)

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
                return None, False, (blocker,)

            generated = FixturePreparation(
                image=image,
                integration_bundle=bundle,
                deployment=deployment,
                integration_bundle_digest=versioned_lifecycle_digest(
                    bundle,
                    "platform-integration-bundle",
                ),
                attachment_bundle_digest=versioned_lifecycle_digest(
                    deployment.attachment_bundle,
                    "application-attachment-bundle",
                ),
            )
            prepared = self._commands.record_prepared_handoff(
                request,
                generated,
            )
            matched, blocker = self._preparation_matches(
                prepared,
                definition,
                request,
            )
            if (
                not matched
                or prepared.image != generated.image
                or prepared.integration_bundle != generated.integration_bundle
                or prepared.deployment != generated.deployment
            ):
                return None, False, (
                    blocker or "FIXTURE_PREPARATION_READBACK_MISMATCH",
                )
            return prepared, False, ()
        except FixtureCommandError as error:
            return None, False, (str(error) or "FIXTURE_COMMAND_FAILED",)
        except ValueError:
            return None, False, ("FIXTURE_PREPARATION_INVALID",)

    def handoff(self, request: FixtureDeployRequest) -> FixtureHandoffResult:
        """Deploy one fixture and expose its bundle pair without registration."""

        definition, blocker = self._definition(request)
        if definition is None:
            return self._handoff_blocked(
                request,
                blocker or "FIXTURE_REQUEST_INVALID",
            )
        preparation, reused, blockers = self._prepare(
            request,
            definition,
            total_stages=2,
            preparation_stage_title="Prepare the Fixture Application Handoff",
            reuse_stage_title="Reuse the Prepared Fixture Application Handoff",
        )
        if preparation is None:
            return self._handoff_blocked(request, *blockers)
        return FixtureHandoffResult(
            outcome="prepared",
            application_id=request.application_id,
            image_reference=preparation.image.reference,
            integration_bundle_digest=preparation.integration_bundle_digest,
            integration_bundle_path=preparation.integration_bundle_path,
            attachment_bundle_digest=preparation.attachment_bundle_digest,
            attachment_bundle_path=preparation.attachment_bundle_path,
            registration_intent_path=preparation.registration_intent_path,
            preparation_reused=reused,
        )

    def status(
        self,
        environment: str,
        application_id: str | None = None,
    ) -> FixtureStatusResult:
        """Read one selected fixture or the complete qualification suite."""

        if environment != "staging":
            return FixtureStatusResult(
                "blocked",
                None,
                None,
                (),
                ("FIXTURE_ENVIRONMENT_UNAVAILABLE",),
            )
        if application_id is not None and application_id not in _FIXTURE_BY_ID:
            return FixtureStatusResult(
                "blocked",
                None,
                None,
                (),
                ("FIXTURE_REQUEST_INVALID",),
            )
        try:
            return self._commands.status(environment, application_id)
        except FixtureCommandError as error:
            return FixtureStatusResult(
                "blocked",
                None,
                None,
                (),
                (str(error) or "FIXTURE_STATUS_FAILED",),
            )

    def destroy(self, request: FixtureDestroyRequest) -> FixtureDestroyResult:
        """Destroy one already detached fixture Application State lineage."""

        if (
            request.environment != "staging"
            or request.application_id
            not in {
                "fixture-public",
                "fixture-authenticated",
                "fixture-restricted",
            }
            or _REVISION.fullmatch(request.operator_source_revision) is None
            or _REVISION.fullmatch(request.fixture_source_revision) is None
            or _REVISION.fullmatch(request.expected_platform_source_revision) is None
            or request.expected_platform_generation < 1
            or re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                request.expected_registration_generation_digest,
            )
            is None
        ):
            return FixtureDestroyResult(
                "blocked",
                request.application_id,
                None,
                None,
                ("FIXTURE_DESTROY_REQUEST_INVALID",),
            )
        try:
            return self._commands.destroy_application(request)
        except FixtureCommandError as error:
            return FixtureDestroyResult(
                "blocked",
                request.application_id,
                None,
                None,
                (str(error) or "FIXTURE_DESTROY_FAILED",),
            )


__all__ = (
    "FixtureApplicationDeployRequest",
    "FixtureApplicationDeployment",
    "FixtureApplicationStatus",
    "FixtureCommandError",
    "FixtureCommands",
    "FixtureDefinition",
    "FixtureDeployRequest",
    "FixtureDestroyReadback",
    "FixtureDestroyRequest",
    "FixtureDestroyResult",
    "FixtureImageReadback",
    "FixtureImageRequest",
    "FixtureHandoffResult",
    "FixturePreparation",
    "FixtureSuiteLifecycle",
    "FixtureStatusResult",
)
