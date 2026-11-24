"""Local gcloud adapter for explicit application-project lifecycle operations."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Sequence

from infrastructure.operator.local import LocalFilesystem
from infrastructure.config.project_identity import fixture_state_bucket
from infrastructure.operator.integration import ApplicationProjectConnection
from infrastructure.operator.project_connections import (
    ApplicationProjectReadback,
    FIXTURE_ARTIFACT_REPOSITORY,
    NETWORK_REFERENCE,
    PLATFORM_PROJECT_ID,
    PLATFORM_PROJECT_NUMBER,
    REGION,
    SUBNETWORK_REFERENCE,
    canonical_connection_bytes,
)


_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
_PROJECT_NUMBER = re.compile(r"[1-9][0-9]{5,18}")
_CONNECTION_FIELDS = {
    "application_project_id",
    "application_project_number",
    "contract_version",
    "document_kind",
    "egress_mode",
    "environment",
    "host_project_id",
    "host_project_number",
    "network_reference",
    "network_viewer_granted",
    "region",
    "subnet_user_granted",
    "subnetwork_reference",
}


class ProjectCommandError(RuntimeError):
    """One safe project-lifecycle command failure."""

    def __init__(self, code: str, command: Sequence[str]) -> None:
        self.command = tuple(command)
        super().__init__(code)


class LocalProjectConnectionStore:
    def __init__(self, filesystem: LocalFilesystem) -> None:
        self._filesystem = filesystem

    def write_connection(self, document: dict[str, object]) -> str:
        environment = str(document["environment"])
        project_id = str(document["application_project_id"])
        relative = (
            f"environments/{environment}/project-connections/"
            f"{project_id}.v1.json"
        )
        self._filesystem.write_state(
            relative,
            canonical_connection_bytes(document),
            replace=True,
        )
        return str(self._filesystem.state_path(relative))

    def read_connection(
        self,
        environment: str,
        project_id: str,
    ) -> ApplicationProjectConnection:
        relative = (
            f"environments/{environment}/project-connections/"
            f"{project_id}.v1.json"
        )
        payload = self._filesystem.read_state(relative)
        if payload is None:
            raise ValueError("APPLICATION_PROJECT_NOT_CONNECTED")
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("APPLICATION_PROJECT_CONNECTION_INVALID") from error
        if (
            not isinstance(value, dict)
            or set(value) != _CONNECTION_FIELDS
            or value.get("contract_version") != 1
            or value.get("document_kind") != "application-project-connection"
            or value.get("environment") != environment
            or value.get("application_project_id") != project_id
            or _PROJECT_ID.fullmatch(project_id) is None
            or not isinstance(value.get("application_project_number"), str)
            or _PROJECT_NUMBER.fullmatch(value["application_project_number"]) is None
            or value.get("host_project_id") != PLATFORM_PROJECT_ID
            or value.get("host_project_number") != PLATFORM_PROJECT_NUMBER
            or value.get("region") != REGION
            or value.get("network_reference") != NETWORK_REFERENCE
            or value.get("subnetwork_reference") != SUBNETWORK_REFERENCE
            or value.get("egress_mode") != "all-traffic"
            or value.get("network_viewer_granted") is not True
            or value.get("subnet_user_granted") is not True
        ):
            raise ValueError("APPLICATION_PROJECT_CONNECTION_INVALID")
        try:
            return ApplicationProjectConnection(
                environment=str(value["environment"]),
                project_id=str(value["application_project_id"]),
                project_number=str(value["application_project_number"]),
                host_project_id=str(value["host_project_id"]),
                host_project_number=str(value["host_project_number"]),
                region=str(value["region"]),
                network_reference=str(value["network_reference"]),
                subnetwork_reference=str(value["subnetwork_reference"]),
                egress_mode=str(value["egress_mode"]),
            )
        except KeyError as error:
            raise ValueError("APPLICATION_PROJECT_CONNECTION_INVALID") from error

    def read_project_number(
        self,
        environment: str,
        project_number: str,
    ) -> ApplicationProjectConnection:
        root = self._filesystem.state_path(
            f"environments/{environment}/project-connections"
        )
        matches: list[ApplicationProjectConnection] = []
        for path in sorted(root.glob("*.v1.json")):
            try:
                connection = self.read_connection(environment, path.name[:-8])
            except (OSError, ValueError):
                continue
            if connection.project_number == project_number:
                matches.append(connection)
        if len(matches) != 1:
            raise ValueError("APPLICATION_PROJECT_NOT_CONNECTED")
        return matches[0]


class GcloudApplicationProjectProvider:
    """Use only explicit project IDs and bounded gcloud project/network commands."""

    def __init__(
        self,
        executable: Path,
        cloud_sdk_configuration: Path,
        working_root: Path,
        fixture_project_id: str,
    ) -> None:
        self._executable = executable.resolve()
        self._configuration = cloud_sdk_configuration.resolve()
        self._working_root = working_root.resolve()
        if _PROJECT_ID.fullmatch(fixture_project_id) is None:
            raise ValueError("fixture project ID must be exact")
        self._fixture_project_id = fixture_project_id
        self._fixture_state_bucket = fixture_state_bucket(fixture_project_id)

    def _run(
        self,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["CLOUDSDK_CONFIG"] = str(self._configuration)
        completed = subprocess.run(
            [str(self._executable), *arguments, "--quiet"],
            cwd=self._working_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if check and completed.returncode != 0:
            raise ProjectCommandError("PROJECT_COMMAND_FAILED", arguments)
        return completed

    def _json(self, *arguments: str) -> object | None:
        completed = self._run(*arguments, "--format=json", check=False)
        if completed.returncode != 0:
            return None
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ProjectCommandError("PROJECT_READBACK_INVALID", arguments) from error

    @staticmethod
    def _parent_reference(value: object) -> str | None:
        if isinstance(value, dict):
            parent_type = value.get("type")
            parent_id = value.get("id")
            if isinstance(parent_type, str) and isinstance(parent_id, str):
                return f"{parent_type}/{parent_id}"
        if isinstance(value, str) and "/" in value:
            return value
        return None

    @staticmethod
    def _bucket_ready(bucket: object, project_number: str | None) -> bool:
        if not isinstance(bucket, dict) or project_number is None:
            return False
        iam = bucket.get("iamConfiguration")
        versioning = bucket.get("versioning")
        lifecycle = bucket.get("lifecycle")
        labels = bucket.get("labels")
        if (
            str(bucket.get("projectNumber")) != project_number
            or bucket.get("location") != REGION.upper()
            or bucket.get("storageClass") != "STANDARD"
            or not isinstance(iam, dict)
            or iam.get("publicAccessPrevention") != "enforced"
            or not isinstance(iam.get("uniformBucketLevelAccess"), dict)
            or iam["uniformBucketLevelAccess"].get("enabled") is not True
            or not isinstance(versioning, dict)
            or versioning.get("enabled") is not True
            or not isinstance(lifecycle, dict)
            or not isinstance(lifecycle.get("rule"), list)
            or not isinstance(labels, dict)
            or labels.get("environment") != "qualification"
            or labels.get("managed_by") != "apps-platform-operator"
            or labels.get("state_owner") != "application"
        ):
            return False
        return any(
            isinstance(rule, dict)
            and isinstance(rule.get("action"), dict)
            and rule["action"].get("type") == "Delete"
            and isinstance(rule.get("condition"), dict)
            and rule["condition"].get("daysSinceNoncurrentTime") == 90
            and rule["condition"].get("numNewerVersions") == 20
            for rule in lifecycle["rule"]
        )

    @staticmethod
    def _repository_ready(repository: object, project_id: str) -> bool:
        if not isinstance(repository, dict):
            return False
        name = repository.get("name")
        labels = repository.get("labels")
        docker = repository.get("dockerConfig")
        return (
            repository.get("format") == "DOCKER"
            and isinstance(name, str)
            and name
            == (
                f"projects/{project_id}/locations/{REGION}/repositories/"
                f"{FIXTURE_ARTIFACT_REPOSITORY}"
            )
            and isinstance(labels, dict)
            and labels.get("environment") == "qualification"
            and labels.get("state_owner") == "application"
            and isinstance(docker, dict)
            and docker.get("immutableTags") is True
        )

    def read_project(self, project_id: str) -> ApplicationProjectReadback:
        project = self._json("projects", "describe", project_id)
        if not isinstance(project, dict):
            return ApplicationProjectReadback(project_id, False)
        raw_project_number = project.get("projectNumber")
        candidate_project_number = (
            str(raw_project_number)
            if isinstance(raw_project_number, (int, str))
            else ""
        )
        project_number = (
            candidate_project_number
            if _PROJECT_NUMBER.fullmatch(candidate_project_number) is not None
            else None
        )
        parent = self._parent_reference(project.get("parent"))

        billing_value = (
            self._json("billing", "projects", "describe", project_id)
            if project_id == self._fixture_project_id
            else None
        )
        billing = (
            billing_value.get("billingAccountName")
            if isinstance(billing_value, dict)
            else None
        )
        fixture_ownership_matches = False
        if project_id == self._fixture_project_id:
            platform = self._json("projects", "describe", PLATFORM_PROJECT_ID)
            platform_billing = self._json(
                "billing", "projects", "describe", PLATFORM_PROJECT_ID
            )
            fixture_ownership_matches = (
                isinstance(platform, dict)
                and isinstance(platform_billing, dict)
                and parent is not None
                and parent == self._parent_reference(platform.get("parent"))
                and isinstance(billing, str)
                and billing == platform_billing.get("billingAccountName")
            )
        services_value = (
            self._json(
                "services", "list", "--enabled", f"--project={project_id}"
            )
            if project_id == self._fixture_project_id
            else None
        )
        services: list[str] = []
        if isinstance(services_value, list):
            for entry in services_value:
                if isinstance(entry, dict):
                    config = entry.get("config")
                    if isinstance(config, dict) and isinstance(config.get("name"), str):
                        services.append(config["name"])

        repository = None
        bucket = None
        if project_id == self._fixture_project_id:
            repository = self._json(
                "artifacts",
                "repositories",
                "describe",
                FIXTURE_ARTIFACT_REPOSITORY,
                f"--location={REGION}",
                f"--project={project_id}",
            )
            bucket = self._json(
                "storage",
                "buckets",
                "describe",
                f"gs://{self._fixture_state_bucket}",
                f"--project={project_id}",
            )
        host = self._json("compute", "shared-vpc", "get-host-project", project_id)
        host_project = None
        if isinstance(host, dict):
            raw_name = host.get("name") or host.get("project")
            if isinstance(raw_name, str):
                host_project = raw_name.rsplit("/", maxsplit=1)[-1]

        member = (
            f"serviceAccount:service-{project_number}@"
            "serverless-robot-prod.iam.gserviceaccount.com"
            if project_number is not None
            else ""
        )
        host_policy = self._json(
            "projects", "get-iam-policy", PLATFORM_PROJECT_ID
        )
        network_viewer_granted = False
        if isinstance(host_policy, dict):
            bindings = host_policy.get("bindings")
            if isinstance(bindings, list):
                network_viewer_granted = any(
                    isinstance(binding, dict)
                    and binding.get("role") == "roles/compute.networkViewer"
                    and member in binding.get("members", [])
                    for binding in bindings
                )
        policy = self._json(
            "compute",
            "networks",
            "subnets",
            "get-iam-policy",
            f"app-platform-applications-{REGION}",
            f"--region={REGION}",
            f"--project={PLATFORM_PROJECT_ID}",
        )
        subnet_granted = False
        if isinstance(policy, dict):
            bindings = policy.get("bindings")
            if isinstance(bindings, list):
                subnet_granted = any(
                    isinstance(binding, dict)
                    and binding.get("role") == "roles/compute.networkUser"
                    and member in binding.get("members", [])
                    for binding in bindings
                )
        return ApplicationProjectReadback(
            project_id=project_id,
            exists=True,
            project_number=project_number,
            parent=parent,
            billing_account_reference=(billing if isinstance(billing, str) else None),
            enabled_services=tuple(sorted(services)),
            state_bucket_ready=self._bucket_ready(bucket, project_number),
            artifact_repository_ready=self._repository_ready(repository, project_id),
            host_project_id=host_project,
            network_viewer_granted=network_viewer_granted,
            subnet_user_granted=subnet_granted,
            fixture_ownership_matches=fixture_ownership_matches,
        )

    def bootstrap_fixture_project(self, project_id: str) -> None:
        if project_id != self._fixture_project_id:
            raise ProjectCommandError("FIXTURE_PROJECT_ID_MISMATCH", ())
        platform = self._json("projects", "describe", PLATFORM_PROJECT_ID)
        billing = self._json("billing", "projects", "describe", PLATFORM_PROJECT_ID)
        if not isinstance(platform, dict) or not isinstance(billing, dict):
            raise ProjectCommandError("PLATFORM_PROJECT_READBACK_FAILED", ())
        parent = platform.get("parent")
        billing_reference = billing.get("billingAccountName")
        if not isinstance(parent, dict) or not isinstance(billing_reference, str):
            raise ProjectCommandError("PLATFORM_PROJECT_OWNERSHIP_INVALID", ())
        current = self._json("projects", "describe", project_id)
        if not isinstance(current, dict):
            parent_type = parent.get("type")
            parent_id = parent.get("id")
            if parent_type not in {"folder", "organization"} or not isinstance(parent_id, str):
                raise ProjectCommandError("PLATFORM_PROJECT_PARENT_INVALID", ())
            flag = "--folder" if parent_type == "folder" else "--organization"
            self._run(
                "projects",
                "create",
                project_id,
                f"{flag}={parent_id}",
                "--name=Comfforts App Fixtures Non-Prod",
            )
        elif self._parent_reference(current.get("parent")) != self._parent_reference(
            parent
        ):
            raise ProjectCommandError("FIXTURE_PROJECT_PARENT_CONFLICT", ())
        self._run(
            "billing",
            "projects",
            "link",
            project_id,
            f"--billing-account={billing_reference.rsplit('/', maxsplit=1)[-1]}",
        )
        self._run(
            "services",
            "enable",
            "artifactregistry.googleapis.com",
            "cloudbuild.googleapis.com",
            "cloudresourcemanager.googleapis.com",
            "compute.googleapis.com",
            "iam.googleapis.com",
            "run.googleapis.com",
            "serviceusage.googleapis.com",
            "storage.googleapis.com",
            f"--project={project_id}",
        )
        if self._json(
            "storage",
            "buckets",
            "describe",
            f"gs://{self._fixture_state_bucket}",
            f"--project={project_id}",
        ) is None:
            self._run(
                "storage",
                "buckets",
                "create",
                f"gs://{self._fixture_state_bucket}",
                f"--project={project_id}",
                f"--location={REGION}",
                "--default-storage-class=STANDARD",
                "--uniform-bucket-level-access",
                "--public-access-prevention",
                (
                    "--labels=environment=qualification,"
                    "managed_by=apps-platform-operator,state_owner=application"
                ),
            )
        lifecycle = {
            "rule": [
                {
                    "action": {"type": "Delete"},
                    "condition": {
                        "daysSinceNoncurrentTime": 90,
                        "numNewerVersions": 20,
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory(
            prefix="apps-platform-fixture-state-"
        ) as temporary:
            lifecycle_path = Path(temporary) / "lifecycle.json"
            lifecycle_path.write_text(
                json.dumps(lifecycle, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            self._run(
                "storage",
                "buckets",
                "update",
                f"gs://{self._fixture_state_bucket}",
                "--default-storage-class=STANDARD",
                "--uniform-bucket-level-access",
                "--public-access-prevention",
                "--versioning",
                f"--lifecycle-file={lifecycle_path}",
                (
                    "--update-labels=environment=qualification,"
                    "managed_by=apps-platform-operator,state_owner=application"
                ),
            )
        if self._json(
            "artifacts",
            "repositories",
            "describe",
            FIXTURE_ARTIFACT_REPOSITORY,
            f"--location={REGION}",
            f"--project={project_id}",
        ) is None:
            self._run(
                "artifacts",
                "repositories",
                "create",
                FIXTURE_ARTIFACT_REPOSITORY,
                "--repository-format=docker",
                f"--location={REGION}",
                f"--project={project_id}",
                "--description=Fixture application images",
                "--immutable-tags",
                "--labels=environment=qualification,state_owner=application",
            )
        self._run(
            "artifacts",
            "repositories",
            "update",
            FIXTURE_ARTIFACT_REPOSITORY,
            f"--location={REGION}",
            f"--project={project_id}",
            "--immutable-tags",
            "--update-labels=environment=qualification,state_owner=application",
        )

    def connect_project(self, project_id: str, project_number: str) -> None:
        readback = self.read_project(project_id)
        if readback.host_project_id is None:
            self._run(
                "compute",
                "shared-vpc",
                "associated-projects",
                "add",
                project_id,
                f"--host-project={PLATFORM_PROJECT_ID}",
            )
        elif readback.host_project_id != PLATFORM_PROJECT_ID:
            raise ProjectCommandError("APPLICATION_PROJECT_NETWORK_OWNER_CONFLICT", ())
        member = (
            f"serviceAccount:service-{project_number}@"
            "serverless-robot-prod.iam.gserviceaccount.com"
        )
        self._run(
            "projects",
            "add-iam-policy-binding",
            PLATFORM_PROJECT_ID,
            "--role=roles/compute.networkViewer",
            f"--member={member}",
        )
        self._run(
            "compute",
            "networks",
            "subnets",
            "add-iam-policy-binding",
            f"app-platform-applications-{REGION}",
            f"--region={REGION}",
            f"--project={PLATFORM_PROJECT_ID}",
            "--role=roles/compute.networkUser",
            f"--member={member}",
        )


__all__ = (
    "GcloudApplicationProjectProvider",
    "LocalProjectConnectionStore",
    "ProjectCommandError",
)
