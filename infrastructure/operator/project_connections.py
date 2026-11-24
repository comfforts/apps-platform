"""Explicit application-project bootstrap and Shared VPC connection lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Protocol

from infrastructure.operator._interfaces import OperatorInterrupted, OperatorTerminal
from infrastructure.config.project_identity import fixture_state_bucket


PLATFORM_PROJECT_ID = "comfforts-platform-non-prod"
PLATFORM_PROJECT_NUMBER = "455651441682"
REGION = "us-west1"
NETWORK_REFERENCE = (
    "projects/comfforts-platform-non-prod/global/networks/app-platform-shared"
)
SUBNETWORK_REFERENCE = (
    "projects/comfforts-platform-non-prod/regions/us-west1/subnetworks/"
    "app-platform-applications-us-west1"
)
FIXTURE_ARTIFACT_REPOSITORY = "app-platform-images"
_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")


@dataclass(frozen=True, slots=True)
class ApplicationProjectReadback:
    project_id: str
    exists: bool
    project_number: str | None = None
    parent: str | None = None
    billing_account_reference: str | None = None
    enabled_services: tuple[str, ...] = ()
    state_bucket_ready: bool = False
    artifact_repository_ready: bool = False
    host_project_id: str | None = None
    network_viewer_granted: bool = False
    subnet_user_granted: bool = False
    fixture_ownership_matches: bool = False


@dataclass(frozen=True, slots=True)
class ProjectLifecycleResult:
    outcome: str
    project_id: str
    project_number: str | None
    connection_path: str | None = None
    blockers: tuple[str, ...] = ()


class ApplicationProjectProvider(Protocol):
    def read_project(self, project_id: str) -> ApplicationProjectReadback: ...

    def bootstrap_fixture_project(self, project_id: str) -> None: ...

    def connect_project(self, project_id: str, project_number: str) -> None: ...


class ProjectConnectionStore(Protocol):
    def write_connection(self, document: dict[str, object]) -> str: ...


_REQUIRED_SERVICES = frozenset(
    {
        "artifactregistry.googleapis.com",
        "cloudbuild.googleapis.com",
        "cloudresourcemanager.googleapis.com",
        "compute.googleapis.com",
        "iam.googleapis.com",
        "run.googleapis.com",
        "serviceusage.googleapis.com",
        "storage.googleapis.com",
    }
)


class ApplicationProjectLifecycle:
    """Keep project creation separate from platform-owned network attachment."""

    def __init__(
        self,
        provider: ApplicationProjectProvider,
        store: ProjectConnectionStore,
        terminal: OperatorTerminal,
    ) -> None:
        self._provider = provider
        self._store = store
        self._terminal = terminal

    @staticmethod
    def _result(
        outcome: str,
        readback: ApplicationProjectReadback,
        *,
        connection_path: str | None = None,
        blockers: tuple[str, ...] = (),
    ) -> ProjectLifecycleResult:
        return ProjectLifecycleResult(
            outcome,
            readback.project_id,
            readback.project_number,
            connection_path,
            blockers,
        )

    @staticmethod
    def _bootstrap_blockers(
        readback: ApplicationProjectReadback,
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        if not readback.exists:
            blockers.append("FIXTURE_PROJECT_NOT_FOUND")
        if readback.project_number is None:
            blockers.append("FIXTURE_PROJECT_NUMBER_UNAVAILABLE")
        if readback.parent is None:
            blockers.append("FIXTURE_PROJECT_PARENT_UNAVAILABLE")
        if readback.billing_account_reference is None:
            blockers.append("FIXTURE_PROJECT_BILLING_UNAVAILABLE")
        if not readback.fixture_ownership_matches:
            blockers.append("FIXTURE_PROJECT_OWNERSHIP_MISMATCH")
        if not _REQUIRED_SERVICES.issubset(readback.enabled_services):
            blockers.append("FIXTURE_PROJECT_SERVICES_INCOMPLETE")
        if not readback.state_bucket_ready:
            blockers.append("FIXTURE_STATE_BUCKET_READBACK_MISMATCH")
        if not readback.artifact_repository_ready:
            blockers.append("FIXTURE_ARTIFACT_REPOSITORY_READBACK_MISMATCH")
        return tuple(blockers)

    @classmethod
    def _bootstrap_ready(cls, readback: ApplicationProjectReadback) -> bool:
        return not cls._bootstrap_blockers(readback)

    def bootstrap_fixture(
        self,
        environment: str,
        project_id: str,
    ) -> ProjectLifecycleResult:
        if environment != "staging":
            return ProjectLifecycleResult(
                "blocked",
                project_id,
                None,
                blockers=("FIXTURE_PROJECT_ENVIRONMENT_UNAVAILABLE",),
            )
        if (
            _PROJECT_ID.fullmatch(project_id) is None
            or project_id == PLATFORM_PROJECT_ID
        ):
            return ProjectLifecycleResult(
                "blocked",
                project_id,
                None,
                blockers=("FIXTURE_PROJECT_ID_INVALID",),
            )
        try:
            before = self._provider.read_project(project_id)
        except RuntimeError as error:
            return ProjectLifecycleResult(
                "blocked",
                project_id,
                None,
                blockers=(str(error) or "FIXTURE_PROJECT_READBACK_FAILED",),
            )
        if self._bootstrap_ready(before):
            self._terminal.write(
                "Fixture project bootstrap is already complete. The project and "
                "its application-owned storage exist; no fixture runtime was created.\n"
                f"Provider-assigned project number: {before.project_number}"
            )
            return self._result("unchanged", before)

        self._terminal.write(
            "FIXTURE PROJECT BOOTSTRAP\n"
            f"Project: {project_id}\n"
            f"State bucket: {fixture_state_bucket(project_id)}\n"
            "This one-time operation creates or repairs the dedicated fixture "
            "application project, links the platform billing account and parent, "
            "enables the required APIs, and creates the fixture state bucket and "
            "Artifact Registry repository. It creates no fixture runtime, route, or "
            "registration."
        )
        try:
            confirmed = self._terminal.confirm(
                "Create or repair the dedicated fixture application project? [y/N] "
            )
        except OperatorInterrupted:
            confirmed = False
        if not confirmed:
            return self._result(
                "cancelled", before, blockers=("FIXTURE_PROJECT_NOT_CONFIRMED",)
            )
        try:
            self._provider.bootstrap_fixture_project(project_id)
            after = self._provider.read_project(project_id)
        except RuntimeError as error:
            return ProjectLifecycleResult(
                "failed",
                project_id,
                before.project_number,
                blockers=(str(error) or "FIXTURE_PROJECT_BOOTSTRAP_FAILED",),
            )
        readback_blockers = self._bootstrap_blockers(after)
        if readback_blockers:
            return self._result(
                "failed",
                after,
                blockers=readback_blockers,
            )
        self._terminal.write(
            "Fixture project bootstrap completed. The project is ready for an "
            "explicit platform-connect-project operation; no application runtime exists.\n"
            f"Provider-assigned project number: {after.project_number}"
        )
        return self._result("bootstrapped", after)

    def connect(self, environment: str, project_id: str) -> ProjectLifecycleResult:
        if environment != "staging":
            return ProjectLifecycleResult(
                "blocked",
                project_id,
                None,
                blockers=("APPLICATION_PROJECT_ENVIRONMENT_UNAVAILABLE",),
            )
        if project_id == PLATFORM_PROJECT_ID:
            return ProjectLifecycleResult(
                "blocked",
                project_id,
                PLATFORM_PROJECT_NUMBER,
                blockers=("APPLICATION_PROJECT_MUST_BE_SEPARATE",),
            )
        try:
            readback = self._provider.read_project(project_id)
        except RuntimeError as error:
            return ProjectLifecycleResult(
                "blocked",
                project_id,
                None,
                blockers=(str(error) or "APPLICATION_PROJECT_READBACK_FAILED",),
            )
        if not readback.exists or readback.project_number is None:
            return self._result(
                "blocked", readback, blockers=("APPLICATION_PROJECT_NOT_FOUND",)
            )
        if readback.host_project_id not in {None, PLATFORM_PROJECT_ID}:
            return self._result(
                "blocked",
                readback,
                blockers=("APPLICATION_PROJECT_NETWORK_OWNER_CONFLICT",),
            )
        if (
            readback.host_project_id != PLATFORM_PROJECT_ID
            or not readback.network_viewer_granted
            or not readback.subnet_user_granted
        ):
            self._terminal.write(
                "CONNECT APPLICATION PROJECT\n"
                f"Application project: {project_id} ({readback.project_number})\n"
                f"Shared VPC host: {PLATFORM_PROJECT_ID}\n"
                f"Application subnet: {SUBNETWORK_REFERENCE}\n"
                "This operation attaches the existing application project as a Shared "
                "VPC service project and grants its Cloud Run service agent read-only "
                "host-network discovery plus permission to use only the application "
                "subnet. It does not create a runtime, route, registration, or "
                "application data."
            )
            try:
                confirmed = self._terminal.confirm(
                    "Connect this application project to the platform network? [y/N] "
                )
            except OperatorInterrupted:
                confirmed = False
            if not confirmed:
                return self._result(
                    "cancelled",
                    readback,
                    blockers=("APPLICATION_PROJECT_CONNECTION_NOT_CONFIRMED",),
                )
            try:
                self._provider.connect_project(project_id, readback.project_number)
                readback = self._provider.read_project(project_id)
            except RuntimeError as error:
                return ProjectLifecycleResult(
                    "failed",
                    project_id,
                    readback.project_number,
                    blockers=(
                        str(error) or "APPLICATION_PROJECT_CONNECTION_FAILED",
                    ),
                )
        if (
            readback.host_project_id != PLATFORM_PROJECT_ID
            or not readback.network_viewer_granted
            or not readback.subnet_user_granted
        ):
            return self._result(
                "failed",
                readback,
                blockers=("APPLICATION_PROJECT_CONNECTION_READBACK_MISMATCH",),
            )

        document: dict[str, object] = {
            "contract_version": 1,
            "document_kind": "application-project-connection",
            "environment": environment,
            "application_project_id": project_id,
            "application_project_number": readback.project_number,
            "host_project_id": PLATFORM_PROJECT_ID,
            "host_project_number": PLATFORM_PROJECT_NUMBER,
            "region": REGION,
            "network_reference": NETWORK_REFERENCE,
            "subnetwork_reference": SUBNETWORK_REFERENCE,
            "egress_mode": "all-traffic",
            "network_viewer_granted": True,
            "subnet_user_granted": True,
        }
        connection_path = self._store.write_connection(document)
        self._terminal.write(
            "Application project connection verified. The project can use the "
            "platform subnet, but no application runtime or route was created.\n"
            f"Connection record: {connection_path}"
        )
        return self._result("connected", readback, connection_path=connection_path)


def canonical_connection_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


__all__ = (
    "ApplicationProjectLifecycle",
    "ApplicationProjectProvider",
    "ApplicationProjectReadback",
    "ProjectConnectionStore",
    "ProjectLifecycleResult",
    "canonical_connection_bytes",
)
