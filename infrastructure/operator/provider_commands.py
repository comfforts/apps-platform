"""Closed Cloud SDK generation publication and activation commands."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import stat
import subprocess
from typing import Any, Protocol

from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local_generation import (
    GenerationProvider,
    ProviderGenerationActivation,
    ProviderGenerationPublication,
)


_ALLOWED_ENVIRONMENT = {
    "CLOUDSDK_CONFIG",
    "CLOUDSDK_CORE_DISABLE_PROMPTS",
    "CLOUDSDK_PYTHON_SITEPACKAGES",
}
_ALLOWED_COMMANDS = {
    ("run", "revisions", "describe"),
    ("run", "services", "describe"),
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
        impersonation = [
            argument
            for argument in request.argv
            if argument.startswith("--impersonate-service-account=")
        ]
        if len(impersonation) != 1 or not impersonation[0].split("=", 1)[1]:
            raise ValueError("provider command must use one explicit impersonated identity")
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
        region: str,
        service_name: str,
        configuration_bucket: str,
        authority_emails: dict[str, str],
        runner: ProviderCommandRunner,
    ) -> None:
        self._executable = executable.resolve()
        self._cloud_sdk_configuration = cloud_sdk_configuration.resolve()
        self._working_root = working_root.resolve()
        self._project_id = project_id
        self._region = region
        self._service_name = service_name
        self._configuration_bucket = configuration_bucket
        self._authority_emails = dict(authority_emails)
        self._runner = runner
        if not self._executable.is_file():
            raise ValueError("an absolute Cloud SDK executable is required")
        if (
            not self._cloud_sdk_configuration.is_dir()
            or self._cloud_sdk_configuration.is_symlink()
            or stat.S_IMODE(self._cloud_sdk_configuration.stat().st_mode) & 0o077
        ):
            raise ValueError("Cloud SDK configuration must be a real private directory")
        if not self._working_root.is_dir() or self._working_root.is_symlink():
            raise ValueError("provider working root must be a real directory")
        if set(self._authority_emails) != {"apply", "rollback"}:
            raise ValueError("apply and rollback authorities are required")

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

    def _authority(self, authority: str) -> str:
        try:
            return self._authority_emails[authority]
        except KeyError as error:
            raise GenerationProviderError("GENERATION_AUTHORITY_UNAVAILABLE") from error

    def _common(self, authority: str) -> tuple[str, ...]:
        return (
            f"--project={self._project_id}",
            f"--impersonate-service-account={self._authority(authority)}",
            "--quiet",
        )

    def _run_common(
        self,
        code: str,
        *arguments: str,
        authority: str,
        stdin: bytes | None = None,
    ) -> ProviderCommandResult:
        return self._run(
            code,
            *arguments,
            *self._common(authority),
            stdin=stdin,
        )

    def _try_common(
        self,
        *arguments: str,
        authority: str,
        stdin: bytes | None = None,
    ) -> ProviderCommandResult:
        return self._try_run(
            *arguments,
            *self._common(authority),
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

    def _describe_service(self, authority: str) -> dict[str, Any]:
        result = self._run_common(
            "EDGE_SERVICE_READBACK_FAILED",
            "run",
            "services",
            "describe",
            self._service_name,
            f"--region={self._region}",
            "--format=json",
            authority=authority,
        )
        return self._json("EDGE_SERVICE_READBACK_INVALID", result.stdout)

    def _describe_revision(
        self,
        revision_name: str,
        authority: str,
    ) -> dict[str, Any] | None:
        result = self._try_common(
            "run",
            "revisions",
            "describe",
            revision_name,
            f"--region={self._region}",
            "--format=json",
            authority=authority,
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
        authority: str,
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
                authority=authority,
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
            authority=authority,
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
        generation, source_revision = self._generation_values(proposal)
        digest_value = proposal.generation_digest.removeprefix("sha256:")
        if len(digest_value) != 64:
            raise GenerationProviderError("GENERATION_PROPOSAL_INVALID")
        object_name = (
            f"generations/{digest_value}/compiled-shared-edge.v1.json"
        )
        object_uri = f"gs://{self._configuration_bucket}/{object_name}"
        copied = self._try_common(
            "storage",
            "cp",
            "-",
            object_uri,
            "--if-generation-match=0",
            authority="apply",
            stdin=compiled_configuration,
        )
        object_generation = self._object_readback(
            object_uri,
            compiled_configuration,
            "apply",
        )
        service = self._describe_service("apply")
        invariants = self._revision_invariants(service)
        revision_name = f"{self._service_name}-g{generation}-{digest_value[:12]}"
        expected_environment = {
            "APP_PLATFORM_SOURCE_REVISION": source_revision,
            "APP_PLATFORM_REGISTRATION_GENERATION": str(generation),
            "APP_PLATFORM_GENERATION_DIGEST": proposal.generation_digest,
            "APP_PLATFORM_CONFIGURATION_BUCKET": self._configuration_bucket,
            "APP_PLATFORM_CONFIGURATION_OBJECT": object_name,
            "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION": str(object_generation),
            "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST": proposal.content_digest,
        }
        existing = self._describe_revision(revision_name, "apply")
        created = False
        if existing is None:
            suffix = revision_name.removeprefix(f"{self._service_name}-")
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
                f"--update-env-vars={bindings}",
                "--format=json",
                authority="apply",
            )
            created = True
            existing = self._describe_revision(revision_name, "apply")
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
        selected_authority = self._authority(authority)
        del selected_authority
        revision = self._describe_revision(revision_name, authority)
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
            authority=authority,
        )
        service = self._describe_service(authority)
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


__all__ = (
    "ClosedGcloudRunner",
    "GcloudGenerationProvider",
    "GenerationProviderError",
    "ProviderCommandRequest",
    "ProviderCommandResult",
    "ProviderCommandRunner",
)
