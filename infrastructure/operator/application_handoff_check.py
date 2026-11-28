"""Read-only platform readiness checks for one application handoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from infrastructure.operator._interfaces import DeploymentCheckResult, StageCheck
from infrastructure.operator.integration import (
    IntegrationBundleRequest,
    IntegrationBundleResult,
)
from infrastructure.operator.project_connections import (
    ApplicationProjectReadback,
    PLATFORM_PROJECT_ID,
)


_REQUIRED_APPLICATION_SERVICES = frozenset(
    {
        "cloudresourcemanager.googleapis.com",
        "compute.googleapis.com",
        "iam.googleapis.com",
        "run.googleapis.com",
        "serviceusage.googleapis.com",
    }
)
@dataclass(frozen=True, slots=True)
class ApplicationHandoffCheckRequest:
    """Exact application-facing posture to prove without mutating either owner."""

    environment: str
    application_id: str
    application_project_id: str
    access_mode: str
    identity_delivery: str
    route_intent: str
    platform_source_revision: str
    platform_generation: int
    handoff_version: int = 2


@dataclass(frozen=True, slots=True)
class ApplicationHandoffCheckResult:
    """Bounded readiness result that publishes no bundle or lifecycle state."""

    outcome: str
    ready: bool
    blockers: tuple[str, ...]
    checks: tuple[tuple[str, str], ...]
    platform_stages: tuple[tuple[str, StageCheck], ...] = ()
    source_admission_blockers: tuple[str, ...] = ()
    bundle_digest: str | None = None


class DeploymentChecker(Protocol):
    """Read the platform-wide deployment readiness projection."""

    def deploy_check(self, environment: str) -> DeploymentCheckResult:
        """Return one non-mutating environment readiness result."""
        ...


class IntegrationBundleChecker(Protocol):
    """Compile an application-scoped handoff bundle without publishing it."""

    def outputs(self, request: IntegrationBundleRequest) -> IntegrationBundleResult:
        """Return the selected contract version's bounded bundle projection."""
        ...


class ApplicationProjectReader(Protocol):
    """Read bounded project/service/network posture for one application owner."""

    def read_project(self, project_id: str) -> ApplicationProjectReadback:
        """Return the exact named project's non-secret readiness facts."""
        ...


class ApplicationHandoffCheck:
    """Inspect platform and application-project prerequisites without mutation."""

    def __init__(
        self,
        deployment: DeploymentChecker,
        integration: IntegrationBundleChecker,
        projects: ApplicationProjectReader,
    ) -> None:
        """Bind read-only platform, bundle, and project readiness seams."""

        self._deployment = deployment
        self._integration = integration
        self._projects = projects

    @staticmethod
    def _identity_projection_ready(
        access_mode: str,
        identity_delivery: str,
        application_id: str,
        bundle: dict[str, object],
    ) -> tuple[bool, str]:
        """Check the exact least-data identity projection for the requested mode."""

        endpoints = bundle.get("endpoints")
        identity = bundle.get("identity")
        if not isinstance(endpoints, dict) or not isinstance(identity, dict):
            return False, "blocked"
        identity_enabled = identity_delivery in {"optional", "required"}
        origin = endpoints.get("external_origin")
        client_id = identity.get("oauth_client_id")
        if identity_enabled:
            return (
                bundle.get("access_mode") == access_mode
                and bundle.get("identity_delivery") == identity_delivery
                and isinstance(origin, str)
                and bool(origin)
                and endpoints.get("issuer") == f"{origin}/_platform"
                and endpoints.get("jwks_uri") == f"{origin}/.well-known/jwks.json"
                and endpoints.get("oauth_redirect_uri")
                == f"{origin}/_platform/auth/callback"
                and isinstance(client_id, str)
                and bool(client_id)
                and identity.get("audience")
                == f"urn:comfforts:app-platform:audience:{application_id}",
                "pass",
            )
        return (
            bundle.get("access_mode") == "public"
            and bundle.get("identity_delivery") == "none"
            and endpoints.get("issuer") is None
            and endpoints.get("jwks_uri") is None
            and endpoints.get("oauth_redirect_uri") is None
            and client_id is None
            and identity.get("audience") is None,
            "not-required",
        )

    def check(
        self,
        request: ApplicationHandoffCheckRequest,
    ) -> ApplicationHandoffCheckResult:
        """Evaluate all non-mutating handoff prerequisites and aggregate blockers."""

        blockers: list[str] = []
        checks: dict[str, str] = {
            "platform-readiness": "blocked",
            "application-project": "blocked",
            "application-services": "blocked",
            "bundle-contract": "blocked",
            "application-identity-projection": "blocked",
        }

        deployment = self._deployment.deploy_check(request.environment)
        blockers.extend(deployment.blockers)
        if deployment.reconciliation_required:
            blockers.append("PLATFORM_RECONCILIATION_REQUIRED")
        if not deployment.platform_ready and not deployment.reconciliation_required:
            blockers.append("PLATFORM_DEPLOYMENT_CHECK_INCOMPLETE")
        if deployment.platform_ready:
            checks["platform-readiness"] = "pass"

        try:
            project = self._projects.read_project(request.application_project_id)
        except RuntimeError as error:
            blockers.append(str(error) or "APPLICATION_PROJECT_READBACK_FAILED")
            project = ApplicationProjectReadback(
                request.application_project_id,
                False,
            )
        if not project.exists or project.project_number is None:
            blockers.append("APPLICATION_PROJECT_NOT_FOUND")
        else:
            checks["application-project"] = "pass"
        if not _REQUIRED_APPLICATION_SERVICES.issubset(project.enabled_services):
            blockers.append("APPLICATION_PROJECT_SERVICES_INCOMPLETE")
        else:
            checks["application-services"] = "pass"
        if (
            project.host_project_id != PLATFORM_PROJECT_ID
            or not project.network_viewer_granted
            or not project.subnet_user_granted
        ):
            blockers.append("APPLICATION_PROJECT_CONNECTION_MISMATCH")
            checks["application-project"] = "blocked"

        bundle_result = self._integration.outputs(
            IntegrationBundleRequest(
                environment=request.environment,
                application_id=request.application_id,
                access_mode=request.access_mode,
                identity_delivery=request.identity_delivery,
                route_intent=request.route_intent,
                expected_platform_source_revision=request.platform_source_revision,
                expected_generation=request.platform_generation,
                application_project_id=request.application_project_id,
                handoff_version=request.handoff_version,
            )
        )
        blockers.extend(bundle_result.blockers)
        if bundle_result.outcome == "generated" and bundle_result.bundle is not None:
            checks["bundle-contract"] = "pass"
            identity_ready, identity_outcome = self._identity_projection_ready(
                request.access_mode,
                request.identity_delivery,
                request.application_id,
                bundle_result.bundle,
            )
            checks["application-identity-projection"] = identity_outcome
            if not identity_ready:
                blockers.append("APPLICATION_IDENTITY_PROJECTION_INVALID")

        unique_blockers = tuple(sorted(set(blockers)))
        return ApplicationHandoffCheckResult(
            outcome="blocked" if unique_blockers else "ready",
            ready=not unique_blockers,
            blockers=unique_blockers,
            checks=tuple(sorted(checks.items())),
            platform_stages=deployment.stages,
            source_admission_blockers=deployment.source_admission_blockers,
            bundle_digest=bundle_result.bundle_digest,
        )


__all__ = (
    "ApplicationHandoffCheck",
    "ApplicationHandoffCheckRequest",
    "ApplicationHandoffCheckResult",
)
