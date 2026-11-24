"""Closed Cloud SDK generation publication and activation commands."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Protocol

from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.integration import AttachmentTargetReadback
from infrastructure.operator.integration import ApplicationProjectConnectionReader
from infrastructure.operator.local_generation import (
    GenerationProvider,
    ProviderGenerationActivation,
    ProviderGenerationBinding,
    ProviderGenerationPublication,
)
from infrastructure.operator.local_qualification import (
    ProviderQualificationSnapshot,
)
from infrastructure.operator.qualification import ComponentRevision


_ALLOWED_ENVIRONMENT = {
    "CLOUDSDK_CONFIG",
    "CLOUDSDK_CORE_DISABLE_PROMPTS",
    "CLOUDSDK_PYTHON_SITEPACKAGES",
}
_ALLOWED_COMMANDS = {
    ("run", "revisions", "describe"),
    ("run", "services", "describe"),
    ("run", "services", "get-iam-policy"),
    ("run", "services", "update"),
    ("run", "services", "update-traffic"),
    ("storage", "cat"),
    ("storage", "cp"),
    ("storage", "objects", "describe"),
}
_PROHIBITED_ARGUMENT_PREFIXES = (
    "--access-token-file=",
    "--account=",
    "--billing-project=",
    "--configuration=",
    "--credential-file-override=",
)
_MAX_INPUT_BYTES = 16 * 1024 * 1024
_MAX_JSON_BYTES = 4 * 1024 * 1024


class GenerationProviderError(RuntimeError):
    """Coarse provider failure that never includes raw provider output."""


@dataclass(frozen=True, slots=True)
class ProviderCommandRequest:
    """One shell-free Cloud SDK command with a complete closed environment."""

    argv: tuple[str, ...]
    cwd: Path
    environment: tuple[tuple[str, str], ...]
    stdin: bytes | None = None
    timeout_seconds: int = 300


@dataclass(frozen=True, slots=True)
class ProviderCommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class ProviderCommandRunner(Protocol):
    def run(self, request: ProviderCommandRequest) -> ProviderCommandResult: ...


class ClosedGcloudRunner:
    """Run only the reviewed Cloud SDK command families without a shell."""

    def __init__(
        self,
        executable: Path,
        working_root: Path,
        cloud_sdk_configuration: Path,
    ) -> None:
        self._executable = executable.resolve()
        self._working_root = working_root.resolve()
        self._cloud_sdk_configuration = cloud_sdk_configuration.resolve()

    def validate(self, request: ProviderCommandRequest) -> None:
        if len(request.argv) < 3 or Path(request.argv[0]).resolve() != self._executable:
            raise ValueError("provider command is outside the approved set")
        if not any(
            request.argv[1 : 1 + len(command)] == command
            for command in _ALLOWED_COMMANDS
        ):
            raise ValueError("provider command is outside the approved set")
        cwd = request.cwd.resolve()
        if cwd != self._working_root and self._working_root not in cwd.parents:
            raise ValueError("provider command working directory escapes its root")
        if request.cwd.is_symlink() or not cwd.is_dir():
            raise ValueError("provider command working directory is not real")
        if not 1 <= request.timeout_seconds <= 900:
            raise ValueError("provider command timeout is outside the approved bound")
        names = [name for name, _ in request.environment]
        if len(names) != len(set(names)) or set(names) != _ALLOWED_ENVIRONMENT:
            raise ValueError("provider command environment is not closed")
        environment = dict(request.environment)
        if environment["CLOUDSDK_CONFIG"] != str(self._cloud_sdk_configuration):
            raise ValueError("provider command uses an unapproved Cloud SDK configuration")
        if any(
            argument.startswith("--impersonate-service-account=")
            for argument in request.argv
        ):
            raise ValueError("provider command cannot switch the verified human session")
        if any(
            argument == "--async"
            or argument.startswith(_PROHIBITED_ARGUMENT_PREFIXES)
            for argument in request.argv[1:]
        ):
            raise ValueError("provider command contains a prohibited argument")
        if request.stdin is not None:
            if request.argv[1:3] != ("storage", "cp"):
                raise ValueError("provider input is allowed only for object creation")
            if len(request.stdin) > _MAX_INPUT_BYTES:
                raise ValueError("provider input exceeds the approved bound")

    def run(self, request: ProviderCommandRequest) -> ProviderCommandResult:
        self.validate(request)
        completed = subprocess.run(
            list(request.argv),
            cwd=request.cwd,
            env=dict(request.environment),
            input=request.stdin,
            check=False,
            capture_output=True,
            timeout=request.timeout_seconds,
        )
        return ProviderCommandResult(
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )


class GcloudGenerationProvider(GenerationProvider):
    """Publish exact compiled generations and move only reviewed edge traffic."""

    def __init__(
        self,
        *,
        executable: Path,
        cloud_sdk_configuration: Path,
        working_root: Path,
        project_id: str,
        project_number: str,
        region: str,
        service_name: str,
        configuration_bucket: str,
        runner: ProviderCommandRunner,
        project_connections: ApplicationProjectConnectionReader | None = None,
    ) -> None:
        self._executable = executable.resolve()
        self._cloud_sdk_configuration = cloud_sdk_configuration.resolve()
        self._working_root = working_root.resolve()
        self._project_id = project_id
        self._project_number = project_number
        self._region = region
        self._service_name = service_name
        self._configuration_bucket = configuration_bucket
        self._runner = runner
        self._project_connections = project_connections
        if not self._executable.is_file():
            raise ValueError("an absolute Cloud SDK executable is required")
        if (
            not self._cloud_sdk_configuration.is_dir()
            or self._cloud_sdk_configuration.is_symlink()
        ):
            raise ValueError("Cloud SDK configuration must be a real directory")
        if not self._working_root.is_dir() or self._working_root.is_symlink():
            raise ValueError("provider working root must be a real directory")
        if not self._project_number.isdigit():
            raise ValueError("canonical provider project number is required")

    def _environment(self) -> tuple[tuple[str, str], ...]:
        return (
            ("CLOUDSDK_CONFIG", str(self._cloud_sdk_configuration)),
            ("CLOUDSDK_CORE_DISABLE_PROMPTS", "1"),
            ("CLOUDSDK_PYTHON_SITEPACKAGES", "0"),
        )

    def _request(
        self,
        *arguments: str,
        stdin: bytes | None = None,
    ) -> ProviderCommandRequest:
        return ProviderCommandRequest(
            argv=(str(self._executable), *arguments),
            cwd=self._working_root,
            environment=self._environment(),
            stdin=stdin,
        )

    def _run(
        self,
        code: str,
        *arguments: str,
        stdin: bytes | None = None,
    ) -> ProviderCommandResult:
        try:
            result = self._runner.run(self._request(*arguments, stdin=stdin))
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise GenerationProviderError(code) from error
        if result.returncode != 0:
            raise GenerationProviderError(code)
        return result

    def _try_run(
        self,
        *arguments: str,
        stdin: bytes | None = None,
    ) -> ProviderCommandResult:
        try:
            return self._runner.run(self._request(*arguments, stdin=stdin))
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise GenerationProviderError("PROVIDER_COMMAND_REJECTED") from error

    @staticmethod
    def _json(code: str, payload: bytes) -> dict[str, Any]:
        if len(payload) > _MAX_JSON_BYTES:
            raise GenerationProviderError(code)
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GenerationProviderError(code) from error
        if not isinstance(value, dict):
            raise GenerationProviderError(code)
        return value

    def _common(self) -> tuple[str, ...]:
        return (
            f"--project={self._project_id}",
            "--quiet",
        )

    def _run_common(
        self,
        code: str,
        *arguments: str,
        stdin: bytes | None = None,
    ) -> ProviderCommandResult:
        return self._run(
            code,
            *arguments,
            *self._common(),
            stdin=stdin,
        )

    def _try_common(
        self,
        *arguments: str,
        stdin: bytes | None = None,
    ) -> ProviderCommandResult:
        return self._try_run(
            *arguments,
            *self._common(),
            stdin=stdin,
        )

    @staticmethod
    def _revision_environment(revision: dict[str, Any]) -> dict[str, str]:
        try:
            containers = revision["spec"]["containers"]
            values = containers[0]["env"]
        except (KeyError, IndexError, TypeError) as error:
            raise GenerationProviderError("GENERATION_REVISION_READBACK_INVALID") from error
        if not isinstance(values, list):
            raise GenerationProviderError("GENERATION_REVISION_READBACK_INVALID")
        result: dict[str, str] = {}
        for item in values:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("value"), str)
            ):
                raise GenerationProviderError("GENERATION_REVISION_READBACK_INVALID")
            result[item["name"]] = item["value"]
        return result

    @staticmethod
    def _revision_invariants(value: dict[str, Any]) -> tuple[str, str]:
        try:
            template = value["spec"]["template"]["spec"]
            return template["serviceAccountName"], template["containers"][0]["image"]
        except (KeyError, IndexError, TypeError) as error:
            raise GenerationProviderError("EDGE_SERVICE_READBACK_INVALID") from error

    @staticmethod
    def _revision_values(value: dict[str, Any]) -> tuple[str, str]:
        try:
            spec = value["spec"]
            return spec["serviceAccountName"], spec["containers"][0]["image"]
        except (KeyError, IndexError, TypeError) as error:
            raise GenerationProviderError("GENERATION_REVISION_READBACK_INVALID") from error

    def _describe_service(self) -> dict[str, Any]:
        return self._describe_named_service(self._service_name)

    def _describe_named_service(
        self,
        service_name: str,
    ) -> dict[str, Any]:
        result = self._run_common(
            "EDGE_SERVICE_READBACK_FAILED",
            "run",
            "services",
            "describe",
            service_name,
            f"--region={self._region}",
            "--format=json",
        )
        return self._json("EDGE_SERVICE_READBACK_INVALID", result.stdout)

    def _try_describe_named_service(
        self,
        service_name: str,
    ) -> dict[str, Any] | None:
        result = self._try_common(
            "run",
            "services",
            "describe",
            service_name,
            f"--region={self._region}",
            "--format=json",
        )
        if result.returncode != 0:
            return None
        return self._json("ATTACHMENT_TARGET_READBACK_INVALID", result.stdout)

    def _describe_revision(
        self,
        revision_name: str,
    ) -> dict[str, Any] | None:
        result = self._try_common(
            "run",
            "revisions",
            "describe",
            revision_name,
            f"--region={self._region}",
            "--format=json",
        )
        if result.returncode != 0:
            return None
        return self._json("GENERATION_REVISION_READBACK_INVALID", result.stdout)

    def _verify_revision(
        self,
        revision: dict[str, Any],
        *,
        revision_name: str,
        expected_invariants: tuple[str, str],
        expected_environment: dict[str, str],
    ) -> None:
        if revision.get("metadata", {}).get("name") != revision_name:
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")
        if self._revision_values(revision) != expected_invariants:
            raise GenerationProviderError("GENERATION_REVISION_INVARIANT_MISMATCH")
        observed = self._revision_environment(revision)
        if any(observed.get(name) != value for name, value in expected_environment.items()):
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")

    def _object_readback(
        self,
        object_uri: str,
        compiled_configuration: bytes,
    ) -> int:
        metadata = self._json(
            "GENERATION_OBJECT_READBACK_INVALID",
            self._run_common(
                "GENERATION_OBJECT_READBACK_FAILED",
                "storage",
                "objects",
                "describe",
                object_uri,
                "--format=json",
            ).stdout,
        )
        try:
            generation = int(metadata["generation"])
        except (KeyError, TypeError, ValueError) as error:
            raise GenerationProviderError("GENERATION_OBJECT_READBACK_INVALID") from error
        if generation < 1:
            raise GenerationProviderError("GENERATION_OBJECT_READBACK_INVALID")
        contents = self._run_common(
            "GENERATION_OBJECT_CONTENT_READBACK_FAILED",
            "storage",
            "cat",
            f"{object_uri}#{generation}",
        ).stdout
        if contents != compiled_configuration:
            raise GenerationProviderError("GENERATION_OBJECT_CONTENT_MISMATCH")
        return generation

    @staticmethod
    def _generation_values(
        proposal: RegistrationGenerationProposal,
    ) -> tuple[int, str]:
        try:
            generation = proposal.registration_set["generation"]
            source_revision = proposal.registration_set["proposal"]["source_revision"]
        except (KeyError, TypeError) as error:
            raise GenerationProviderError("GENERATION_PROPOSAL_INVALID") from error
        if not isinstance(generation, int) or generation < 1:
            raise GenerationProviderError("GENERATION_PROPOSAL_INVALID")
        if not isinstance(source_revision, str) or not source_revision:
            raise GenerationProviderError("GENERATION_PROPOSAL_INVALID")
        return generation, source_revision

    def stage(
        self,
        proposal: RegistrationGenerationProposal,
        compiled_configuration: bytes,
    ) -> ProviderGenerationPublication:
        if proposal.environment != "staging":
            raise GenerationProviderError("GENERATION_ENVIRONMENT_UNAVAILABLE")
        generation, _ = self._generation_values(proposal)
        digest_value = proposal.generation_digest.removeprefix("sha256:")
        if len(digest_value) != 64:
            raise GenerationProviderError("GENERATION_PROPOSAL_INVALID")
        object_name = (
            f"environments/{proposal.environment}/generations/{generation}/"
            "compiled-shared-edge.v1.json"
        )
        object_uri = f"gs://{self._configuration_bucket}/{object_name}"
        copied = self._try_common(
            "storage",
            "cp",
            "-",
            object_uri,
            "--if-generation-match=0",
            stdin=compiled_configuration,
        )
        object_generation = self._object_readback(
            object_uri,
            compiled_configuration,
        )
        _, active_revision = self._active_revision(proposal.environment)
        invariants = self._revision_values(active_revision)
        active_environment = self._revision_environment(active_revision)
        active_platform_source = active_environment.get(
            "APP_PLATFORM_SOURCE_REVISION"
        )
        if not isinstance(active_platform_source, str) or not active_platform_source:
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")
        revision_name = f"{self._service_name}-g{generation}-{digest_value[:12]}"
        expected_environment = {
            **active_environment,
            "APP_PLATFORM_SOURCE_REVISION": active_platform_source,
            "APP_PLATFORM_REGISTRATION_GENERATION": str(generation),
            "APP_PLATFORM_GENERATION_DIGEST": proposal.generation_digest,
            "APP_PLATFORM_CONFIGURATION_BUCKET": self._configuration_bucket,
            "APP_PLATFORM_CONFIGURATION_OBJECT": object_name,
            "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION": str(object_generation),
            "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST": proposal.content_digest,
        }
        existing = self._describe_revision(revision_name)
        created = False
        if existing is None:
            suffix = revision_name.removeprefix(f"{self._service_name}-")
            if any(
                "," in name or "=" in name or "," in value
                for name, value in expected_environment.items()
            ):
                raise GenerationProviderError(
                    "GENERATION_REVISION_BINDING_MISMATCH"
                )
            bindings = ",".join(
                f"{name}={value}"
                for name, value in sorted(expected_environment.items())
            )
            self._run_common(
                "GENERATION_REVISION_STAGE_FAILED",
                "run",
                "services",
                "update",
                self._service_name,
                f"--region={self._region}",
                "--no-traffic",
                f"--revision-suffix={suffix}",
                f"--image={invariants[1]}",
                f"--service-account={invariants[0]}",
                f"--set-env-vars={bindings}",
                "--format=json",
            )
            created = True
            existing = self._describe_revision(revision_name)
        if existing is None:
            raise GenerationProviderError("GENERATION_REVISION_READBACK_MISSING")
        self._verify_revision(
            existing,
            revision_name=revision_name,
            expected_invariants=invariants,
            expected_environment=expected_environment,
        )
        return ProviderGenerationPublication(
            created=created or copied.returncode == 0,
            object_generation=object_generation,
            revision_name=revision_name,
            readback_matches=True,
        )

    def activate(
        self,
        environment: str,
        revision_name: str,
        generation_digest: str,
        authority: str,
    ) -> ProviderGenerationActivation:
        if environment != "staging":
            raise GenerationProviderError("GENERATION_ENVIRONMENT_UNAVAILABLE")
        if authority not in {"apply", "rollback"}:
            raise GenerationProviderError("GENERATION_ACTION_UNAVAILABLE")
        revision = self._describe_revision(revision_name)
        if revision is None:
            raise GenerationProviderError("GENERATION_REVISION_READBACK_MISSING")
        observed_environment = self._revision_environment(revision)
        if observed_environment.get("APP_PLATFORM_GENERATION_DIGEST") != generation_digest:
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")
        self._run_common(
            "GENERATION_TRAFFIC_UPDATE_FAILED",
            "run",
            "services",
            "update-traffic",
            self._service_name,
            f"--region={self._region}",
            f"--to-revisions={revision_name}=100",
            "--format=json",
        )
        service = self._describe_service()
        traffic = service.get("status", {}).get("traffic")
        if not isinstance(traffic, list):
            raise GenerationProviderError("GENERATION_TRAFFIC_READBACK_INVALID")
        active = [
            (item.get("revisionName"), item.get("percent"))
            for item in traffic
            if isinstance(item, dict)
            and isinstance(item.get("percent"), int)
            and item["percent"] > 0
        ]
        if active != [(revision_name, 100)]:
            raise GenerationProviderError("GENERATION_TRAFFIC_READBACK_MISMATCH")
        return ProviderGenerationActivation(
            activated=True,
            active_revision_name=revision_name,
            active_generation_digest=generation_digest,
        )

    def _active_revision(self, environment: str) -> tuple[str, dict[str, Any]]:
        if environment != "staging":
            raise GenerationProviderError("GENERATION_ENVIRONMENT_UNAVAILABLE")
        service = self._describe_service()
        traffic = service.get("status", {}).get("traffic")
        if not isinstance(traffic, list):
            raise GenerationProviderError("GENERATION_TRAFFIC_READBACK_INVALID")
        active = [
            (item.get("revisionName"), item.get("percent"))
            for item in traffic
            if isinstance(item, dict)
            and isinstance(item.get("revisionName"), str)
            and isinstance(item.get("percent"), int)
            and item["percent"] > 0
        ]
        if len(active) != 1 or active[0][1] != 100:
            raise GenerationProviderError("GENERATION_TRAFFIC_READBACK_MISMATCH")
        revision_name = str(active[0][0])
        revision = self._describe_revision(revision_name)
        if revision is None:
            raise GenerationProviderError("GENERATION_REVISION_READBACK_MISSING")
        if revision.get("metadata", {}).get("name") != revision_name:
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")
        return revision_name, revision

    def _revision_binding(
        self,
        environment: str,
        revision_name: str,
        revision: dict[str, Any],
    ) -> ProviderGenerationBinding:
        values = self._revision_environment(revision)
        required = {
            "APP_PLATFORM_CONFIGURATION_BUCKET",
            "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST",
            "APP_PLATFORM_CONFIGURATION_OBJECT",
            "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION",
            "APP_PLATFORM_GENERATION_DIGEST",
            "APP_PLATFORM_REGISTRATION_GENERATION",
            "APP_PLATFORM_SOURCE_REVISION",
        }
        if not required <= set(values):
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")
        try:
            generation = int(values["APP_PLATFORM_REGISTRATION_GENERATION"])
            object_generation = int(
                values["APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION"]
            )
        except ValueError as error:
            raise GenerationProviderError(
                "GENERATION_REVISION_BINDING_MISMATCH"
            ) from error
        source_revision = values["APP_PLATFORM_SOURCE_REVISION"]
        generation_digest = values["APP_PLATFORM_GENERATION_DIGEST"]
        content_digest = values["APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST"]
        object_name = values["APP_PLATFORM_CONFIGURATION_OBJECT"]
        if (
            values["APP_PLATFORM_CONFIGURATION_BUCKET"]
            != self._configuration_bucket
            or generation < 1
            or object_generation < 1
            or len(source_revision) != 40
            or any(character not in "0123456789abcdef" for character in source_revision)
            or not generation_digest.startswith("sha256:")
            or len(generation_digest) != 71
            or not content_digest.startswith("sha256:")
            or len(content_digest) != 71
            or not object_name
        ):
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")
        _, image_reference = self._revision_values(revision)
        return ProviderGenerationBinding(
            environment=environment,
            revision_name=revision_name,
            platform_source_revision=source_revision,
            image_reference=image_reference,
            generation=generation,
            generation_digest=generation_digest,
            content_digest=content_digest,
            object_name=object_name,
            object_generation=object_generation,
        )

    def read_revision_binding(
        self,
        environment: str,
        revision_name: str,
    ) -> ProviderGenerationBinding:
        """Read one exact staged edge revision without moving traffic."""

        if environment != "staging":
            raise GenerationProviderError("GENERATION_ENVIRONMENT_UNAVAILABLE")
        revision = self._describe_revision(revision_name)
        if revision is None:
            raise GenerationProviderError("GENERATION_REVISION_READBACK_MISSING")
        return self._revision_binding(environment, revision_name, revision)

    def read_active_binding(self, environment: str) -> ProviderGenerationBinding:
        """Read the exact active revision binding without changing provider state."""

        revision_name, revision = self._active_revision(environment)
        return self._revision_binding(environment, revision_name, revision)

    @staticmethod
    def _component_digest(value: object) -> str:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def read_current(self, environment: str) -> ProviderQualificationSnapshot:
        """Read the one active revision and its closed component bindings."""

        revision_name, revision = self._active_revision(environment)
        values = self._revision_environment(revision)
        required = {
            "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST",
            "APP_PLATFORM_GENERATION_DIGEST",
            "APP_PLATFORM_IDENTITY_CLIENT_ID",
            "APP_PLATFORM_SIGNING_KEY_VERSION",
        }
        if not required <= set(values):
            raise GenerationProviderError("GENERATION_REVISION_BINDING_MISMATCH")
        _, image = self._revision_values(revision)
        marker = "@sha256:"
        if marker not in image:
            raise GenerationProviderError("GENERATION_REVISION_INVARIANT_MISMATCH")
        image_digest = "sha256:" + image.rsplit(marker, maxsplit=1)[1]
        if len(image_digest) != 71:
            raise GenerationProviderError("GENERATION_REVISION_INVARIANT_MISMATCH")
        components = (
            ComponentRevision("oauth-client", self._component_digest(
                values["APP_PLATFORM_IDENTITY_CLIENT_ID"]
            )),
            ComponentRevision(
                "registration-configuration",
                values["APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST"],
            ),
            ComponentRevision(
                "shared-edge-image",
                image_digest,
            ),
            ComponentRevision(
                "shared-edge-revision",
                self._component_digest(
                    {
                        "environment": values,
                        "revision_name": revision_name,
                    }
                ),
            ),
            ComponentRevision(
                "signing-key-version",
                self._component_digest(
                    values["APP_PLATFORM_SIGNING_KEY_VERSION"]
                ),
            ),
        )
        return ProviderQualificationSnapshot(
            environment=environment,
            active_generation_digest=values["APP_PLATFORM_GENERATION_DIGEST"],
            component_revisions=tuple(sorted(components)),
        )

    def shared_edge_ingress(self, environment: str) -> str:
        """Read only the closed Shared Edge ingress posture."""

        if environment != "staging":
            raise GenerationProviderError("GENERATION_ENVIRONMENT_UNAVAILABLE")
        service = self._describe_service()
        annotations = service.get("metadata", {}).get("annotations", {})
        if not isinstance(annotations, dict):
            raise GenerationProviderError("EDGE_SERVICE_READBACK_INVALID")
        ingress = annotations.get("run.googleapis.com/ingress")
        if ingress not in {"internal", "internal-and-cloud-load-balancing"}:
            raise GenerationProviderError("EDGE_SERVICE_READBACK_INVALID")
        return str(ingress)

    def shared_edge_exists(self, environment: str) -> bool:
        """Read whether the exact platform-owned Shared Edge service exists."""

        if environment != "staging":
            raise GenerationProviderError("GENERATION_ENVIRONMENT_UNAVAILABLE")
        return self._try_describe_named_service(self._service_name) is not None

    @staticmethod
    def _service_environment(service: dict[str, Any]) -> dict[str, str]:
        try:
            template = service["spec"]["template"]
            containers = template.get("containers")
            if containers is None:
                containers = template["spec"]["containers"]
            values = containers[0]["env"]
        except (KeyError, IndexError, TypeError) as error:
            raise GenerationProviderError("ATTACHMENT_TARGET_READBACK_INVALID") from error
        if not isinstance(values, list):
            raise GenerationProviderError("ATTACHMENT_TARGET_READBACK_INVALID")
        result: dict[str, str] = {}
        for item in values:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("value"), str)
            ):
                raise GenerationProviderError("ATTACHMENT_TARGET_READBACK_INVALID")
            result[item["name"]] = item["value"]
        return result

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback:
        """Read one exact Cloud Run attachment and its edge-caller IAM grant."""

        prefix = "urn:comfforts:app-platform:gcp:cloud-run:"
        parts = resource_reference.removeprefix(prefix).split(":")
        if (
            environment != "staging"
            or not resource_reference.startswith(prefix)
            or len(parts) != 3
            or self._project_connections is None
        ):
            raise GenerationProviderError("ATTACHMENT_REFERENCE_INVALID")
        project_number, region, service_name = parts
        try:
            connection = self._project_connections.read_project_number(
                environment,
                project_number,
            )
        except (OSError, ValueError) as error:
            raise GenerationProviderError("APPLICATION_PROJECT_NOT_CONNECTED") from error
        if (
            connection.project_number != project_number
            or connection.region != region
            or region != self._region
            or not service_name
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                for character in service_name
            )
        ):
            raise GenerationProviderError("ATTACHMENT_REFERENCE_INVALID")
        service_result = self._try_run(
            "run",
            "services",
            "describe",
            service_name,
            f"--region={region}",
            "--format=json",
            f"--project={connection.project_id}",
            "--quiet",
        )
        service = (
            None
            if service_result.returncode != 0
            else self._json("ATTACHMENT_TARGET_READBACK_INVALID", service_result.stdout)
        )
        if service is None:
            return AttachmentTargetReadback(
                exists=False,
                ready=False,
                owner_application_id="",
                adapter_kind="gcp-cloud-run-v1",
                resource_reference=resource_reference,
                ingress_mode="unavailable",
                caller_grant="",
                audience=None,
            )
        metadata = service.get("metadata")
        status = service.get("status")
        if not isinstance(metadata, dict) or not isinstance(status, dict):
            raise GenerationProviderError("ATTACHMENT_TARGET_READBACK_INVALID")
        labels = metadata.get("labels", {})
        annotations = metadata.get("annotations", {})
        conditions = status.get("conditions", [])
        if (
            not isinstance(labels, dict)
            or not isinstance(annotations, dict)
            or not isinstance(conditions, list)
        ):
            raise GenerationProviderError("ATTACHMENT_TARGET_READBACK_INVALID")
        environment_values = self._service_environment(service)
        identity_audience = annotations.get("comfforts.com/identity-audience")
        if identity_audience is not None and not isinstance(identity_audience, str):
            raise GenerationProviderError("ATTACHMENT_TARGET_READBACK_INVALID")
        ready = any(
            isinstance(item, dict)
            and item.get("type") == "Ready"
            and item.get("status") == "True"
            for item in conditions
        )
        label_blockers: list[str] = []
        if labels.get("state_owner") != "application":
            label_blockers.append("TARGET_STATE_OWNER_LABEL_MISMATCH")
        if labels.get("environment") != "qualification":
            label_blockers.append("TARGET_ENVIRONMENT_LABEL_MISMATCH")
        if identity_audience != environment_values.get(
            "APP_PLATFORM_ASSERTION_AUDIENCE"
        ):
            label_blockers.append("TARGET_IDENTITY_AUDIENCE_MISMATCH")
        owner_application_id = labels.get("application_id")
        if (
            not isinstance(owner_application_id, str)
            or not owner_application_id
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                for character in owner_application_id
            )
        ):
            label_blockers.append("TARGET_APPLICATION_LABEL_MISMATCH")
        provider_ingress = annotations.get("run.googleapis.com/ingress")
        if provider_ingress is None:
            provider_ingress = service.get("ingress")
        ingress = (
            "shared_edge_only"
            if provider_ingress in {"internal", "INGRESS_TRAFFIC_INTERNAL_ONLY"}
            else "unverified"
        )
        template = service.get("spec", {}).get("template", {})
        template_annotations = (
            template.get("metadata", {}).get("annotations", {})
            if isinstance(template, dict)
            else {}
        )
        network_reference = None
        subnetwork_reference = None
        egress_mode = None
        if isinstance(template_annotations, dict):
            raw_interfaces = template_annotations.get(
                "run.googleapis.com/network-interfaces"
            )
            if isinstance(raw_interfaces, str):
                try:
                    interfaces = json.loads(raw_interfaces)
                except json.JSONDecodeError:
                    interfaces = None
                if isinstance(interfaces, list) and len(interfaces) == 1:
                    interface = interfaces[0]
                    if isinstance(interface, dict):
                        network_reference = interface.get("network")
                        subnetwork_reference = interface.get("subnetwork")
            if template_annotations.get("run.googleapis.com/vpc-access-egress") == "all-traffic":
                egress_mode = "all-traffic"
        vpc_access = template.get("vpcAccess") if isinstance(template, dict) else None
        if isinstance(vpc_access, dict):
            interfaces = vpc_access.get("networkInterfaces")
            if isinstance(interfaces, list) and len(interfaces) == 1:
                interface = interfaces[0]
                if isinstance(interface, dict):
                    network_reference = interface.get("network")
                    subnetwork_reference = interface.get("subnetwork")
            if vpc_access.get("egress") == "ALL_TRAFFIC":
                egress_mode = "all-traffic"
        policy = self._json(
            "ATTACHMENT_IAM_READBACK_INVALID",
            self._run(
                "ATTACHMENT_IAM_READBACK_FAILED",
                "run",
                "services",
                "get-iam-policy",
                service_name,
                f"--region={self._region}",
                "--format=json",
                f"--project={connection.project_id}",
                "--quiet",
            ).stdout,
        )
        bindings = policy.get("bindings")
        if not isinstance(bindings, list):
            raise GenerationProviderError("ATTACHMENT_IAM_READBACK_INVALID")
        expected_caller = (
            "serviceAccount:app-platform-edge-caller@"
            f"{self._project_id}.iam.gserviceaccount.com"
        )
        caller_grant = ""
        public_invoker = False
        for binding in bindings:
            if not isinstance(binding, dict) or binding.get("role") != "roles/run.invoker":
                continue
            members = binding.get("members")
            if not isinstance(members, list):
                raise GenerationProviderError("ATTACHMENT_IAM_READBACK_INVALID")
            if expected_caller in members:
                caller_grant = expected_caller
            if "allUsers" in members or "allAuthenticatedUsers" in members:
                public_invoker = True
        if public_invoker:
            ingress = "unverified"
        return AttachmentTargetReadback(
            exists=True,
            ready=ready,
            owner_application_id=(
                owner_application_id
                if isinstance(owner_application_id, str)
                else ""
            ),
            adapter_kind="gcp-cloud-run-v1",
            resource_reference=resource_reference,
            ingress_mode=ingress,
            caller_grant=caller_grant,
            audience=identity_audience,
            application_project_id=connection.project_id,
            network_reference=network_reference,
            subnetwork_reference=subnetwork_reference,
            egress_mode=egress_mode,
            blockers=tuple(sorted(label_blockers)),
        )


__all__ = (
    "ClosedGcloudRunner",
    "GcloudGenerationProvider",
    "GenerationProviderError",
    "ProviderCommandRequest",
    "ProviderCommandResult",
    "ProviderCommandRunner",
)
