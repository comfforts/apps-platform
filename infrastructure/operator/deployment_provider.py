"""Closed Google Cloud readback and bounded staging deployment actions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Protocol

from infrastructure.operator.diagnostics import capture_private_command_failure
from infrastructure.operator.local_deployment import (
    InitialGeneration,
    LocalDeploymentInputError,
    existing_initial_generation_reference,
)
from infrastructure.operator.provider_commands import (
    ProviderCommandRequest,
    ProviderCommandResult,
)


_ALLOWED_ENVIRONMENT = {
    "CLOUDSDK_CONFIG",
    "CLOUDSDK_CORE_DISABLE_PROMPTS",
    "CLOUDSDK_PYTHON_SITEPACKAGES",
}
_ALLOWED_COMMANDS = {
    ("artifacts", "docker", "images", "describe"),
    ("builds", "submit"),
    ("compute", "ssl-certificates", "describe"),
    ("kms", "keys", "versions", "list"),
    ("kms", "keyrings", "describe"),
    ("secrets", "versions", "list"),
    ("services", "enable"),
    ("services", "list"),
    ("storage", "cat"),
    ("storage", "buckets", "describe"),
    ("storage", "cp"),
    ("storage", "objects", "describe"),
}
_PROHIBITED_ARGUMENT_PREFIXES = (
    "--access-token-file=",
    "--account=",
    "--billing-project=",
    "--configuration=",
    "--credential-file-override=",
    "--impersonate-service-account=",
)
_BOOTSTRAP_SERVICES = (
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
)
_PROJECT_ID = "comfforts-platform-non-prod"
_PROJECT_NUMBER = "455651441682"
_REGION = "us-west1"
_CONFIGURATION_BUCKET = "comfforts-ap-stg-455651441682-configuration"
_BOOTSTRAP_BUCKET = "comfforts-ap-stg-455651441682-platform-state"
_OAUTH_SECRET = "app-platform-edge-oauth"
_SIGNING_KEY_RING = "app-platform"
_SIGNING_KEY = "edge-signing"
_CERTIFICATE = "app-platform-edge-certificate"
_HOSTNAME = "apps-staging.comfforts.com"
_IMAGE_PACKAGE = (
    f"{_REGION}-docker.pkg.dev/{_PROJECT_ID}/app-platform-images/shared-edge"
)
_PROJECT_ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
_SOURCE_REVISION = re.compile(r"[0-9a-f]{40}")
_VERSION_REFERENCE = re.compile(
    r"projects/comfforts-platform-non-prod/locations/us-west1/keyRings/"
    r"app-platform/cryptoKeys/edge-signing/cryptoKeyVersions/[1-9][0-9]*"
)


class DeploymentProviderError(RuntimeError):
    """Coarse provider failure that never contains raw command output."""

    def __init__(
        self,
        code: str,
        diagnostic: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.diagnostic = dict(diagnostic or {})


class DeploymentProviderRunner(Protocol):
    def run(self, request: ProviderCommandRequest) -> ProviderCommandResult: ...


class ClosedDeploymentGcloudRunner:
    """Run only fixed deployment command families through the human Cloud SDK session."""

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
            raise ValueError("deployment provider command is outside the approved set")
        if not any(
            request.argv[1 : 1 + len(command)] == command
            for command in _ALLOWED_COMMANDS
        ):
            raise ValueError("deployment provider command is outside the approved set")
        cwd = request.cwd.resolve()
        if cwd != self._working_root and self._working_root not in cwd.parents:
            raise ValueError("deployment provider working directory escapes its root")
        if request.cwd.is_symlink() or not cwd.is_dir():
            raise ValueError("deployment provider working directory is not real")
        if not 1 <= request.timeout_seconds <= 900:
            raise ValueError("deployment provider timeout is outside the approved bound")
        names = [name for name, _ in request.environment]
        if len(names) != len(set(names)) or set(names) != _ALLOWED_ENVIRONMENT:
            raise ValueError("deployment provider environment is not closed")
        if dict(request.environment)["CLOUDSDK_CONFIG"] != str(
            self._cloud_sdk_configuration
        ):
            raise ValueError("deployment provider Cloud SDK configuration is not approved")
        if any(
            argument == "--async"
            or argument.startswith(_PROHIBITED_ARGUMENT_PREFIXES)
            for argument in request.argv[1:]
        ):
            raise ValueError("deployment provider command contains a prohibited argument")
        if request.stdin is not None:
            if request.argv[1:3] != ("storage", "cp"):
                raise ValueError("deployment provider input is allowed only for object creation")
            if len(request.stdin) > 16 * 1024 * 1024:
                raise ValueError("deployment provider input exceeds the approved bound")

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


@dataclass(frozen=True, slots=True)
class CertificateReadback:
    reference: str
    status: str
    domain_status: str

    @property
    def ready(self) -> bool:
        return self.status == "ACTIVE" and self.domain_status == "ACTIVE"


class GcloudDeploymentProvider:
    """Perform only the non-Terraform actions needed by the staging deployment."""

    def __init__(
        self,
        *,
        executable: Path,
        cloud_sdk_configuration: Path,
        working_root: Path,
        runner: DeploymentProviderRunner,
        fixture_project_id: str,
        private_state_root: Path | None = None,
    ) -> None:
        self._executable = executable.resolve()
        self._cloud_sdk_configuration = cloud_sdk_configuration.resolve()
        self._working_root = working_root.resolve()
        self._runner = runner
        if (
            _PROJECT_ID_PATTERN.fullmatch(fixture_project_id) is None
            or fixture_project_id == _PROJECT_ID
        ):
            raise ValueError("fixture project ID must be explicit and separate")
        self._fixture_project_id = fixture_project_id
        self._fixture_image_package = (
            f"{_REGION}-docker.pkg.dev/{fixture_project_id}/"
            "app-platform-images/fixture"
        )
        self._private_state_root: Path | None = None
        if not self._executable.is_file():
            raise ValueError("an absolute Cloud SDK executable is required")
        if (
            not self._cloud_sdk_configuration.is_dir()
            or self._cloud_sdk_configuration.is_symlink()
        ):
            raise ValueError("Cloud SDK configuration must be a real directory")
        if not self._working_root.is_dir() or self._working_root.is_symlink():
            raise ValueError("deployment provider working root must be real")
        if private_state_root is not None:
            resolved_state = private_state_root.resolve()
            if (
                private_state_root.is_symlink()
                or not resolved_state.is_dir()
                or stat.S_IMODE(resolved_state.stat().st_mode) & 0o077
            ):
                raise ValueError("deployment diagnostics require private operator state")
            self._private_state_root = resolved_state

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
        timeout_seconds: int = 300,
    ) -> ProviderCommandRequest:
        return ProviderCommandRequest(
            argv=(str(self._executable), *arguments),
            cwd=self._working_root,
            environment=self._environment(),
            stdin=stdin,
            timeout_seconds=timeout_seconds,
        )

    def _try(
        self,
        *arguments: str,
        stdin: bytes | None = None,
        timeout_seconds: int = 300,
    ) -> ProviderCommandResult:
        try:
            return self._runner.run(
                self._request(
                    *arguments,
                    stdin=stdin,
                    timeout_seconds=timeout_seconds,
                )
            )
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise DeploymentProviderError("PROVIDER_COMMAND_REJECTED") from error

    def _run(
        self,
        code: str,
        *arguments: str,
        stdin: bytes | None = None,
        timeout_seconds: int = 300,
    ) -> ProviderCommandResult:
        result = self._try(
            *arguments,
            stdin=stdin,
            timeout_seconds=timeout_seconds,
        )
        if result.returncode != 0:
            raise DeploymentProviderError(code)
        return result

    def _common(self, project_id: str = _PROJECT_ID) -> tuple[str, ...]:
        return (f"--project={project_id}", "--quiet")

    def _run_common(
        self,
        code: str,
        *arguments: str,
        stdin: bytes | None = None,
        timeout_seconds: int = 300,
    ) -> ProviderCommandResult:
        return self._run(
            code,
            *arguments,
            *self._common(),
            stdin=stdin,
            timeout_seconds=timeout_seconds,
        )

    def _run_cloud_build(
        self,
        build_failure_code: str,
        config_failure_code: str,
        phase: str,
        *arguments: str,
        project_id: str = _PROJECT_ID,
    ) -> ProviderCommandResult:
        result = self._try(
            *arguments,
            *self._common(project_id),
            timeout_seconds=900,
        )
        if result.returncode == 0:
            return result
        diagnostic_metadata = capture_private_command_failure(
            self._private_state_root,
            environment="staging",
            operation="cloud-build",
            phase=phase,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        diagnostic = result.stderr[: 64 * 1024]
        if all(
            marker in diagnostic
            for marker in (
                b"interpreting ",
                b" as build config:",
                b"Expected type <class 'str'> for field value",
            )
        ):
            raise DeploymentProviderError(
                config_failure_code,
                diagnostic_metadata,
            )
        raise DeploymentProviderError(build_failure_code, diagnostic_metadata)

    @staticmethod
    def _json(code: str, payload: bytes) -> Any:
        if len(payload) > 4 * 1024 * 1024:
            raise DeploymentProviderError(code)
        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DeploymentProviderError(code) from error

    def enable_bootstrap_services(self) -> None:
        self._run_common(
            "BOOTSTRAP_SERVICE_ENABLE_FAILED",
            "services",
            "enable",
            *_BOOTSTRAP_SERVICES,
        )

    def bootstrap_services_ready(self) -> bool:
        service_filter = " OR ".join(
            f"config.name={service}" for service in _BOOTSTRAP_SERVICES
        )
        result = self._run_common(
            "BOOTSTRAP_SERVICE_READBACK_FAILED",
            "services",
            "list",
            "--enabled",
            f"--filter={service_filter}",
            "--format=value(config.name)",
        )
        enabled_services = set(result.stdout.splitlines())
        return all(service.encode() in enabled_services for service in _BOOTSTRAP_SERVICES)

    def bootstrap_backend_ready(self) -> bool:
        result = self._try(
            "storage",
            "buckets",
            "describe",
            f"gs://{_BOOTSTRAP_BUCKET}",
            "--format=value(name)",
            *self._common(),
        )
        if result.returncode != 0:
            return False
        if result.stdout.strip() != _BOOTSTRAP_BUCKET.encode("ascii"):
            raise DeploymentProviderError("BOOTSTRAP_BACKEND_READBACK_INVALID")
        return True

    def signing_key_ring_identity(self) -> str:
        expected = (
            f"projects/{_PROJECT_ID}/locations/{_REGION}/keyRings/"
            f"{_SIGNING_KEY_RING}"
        )
        try:
            observed = self._run_common(
                "SIGNING_KEY_RING_READBACK_FAILED",
                "kms",
                "keyrings",
                "describe",
                _SIGNING_KEY_RING,
                f"--location={_REGION}",
                "--format=value(name)",
            ).stdout.decode("ascii", errors="strict").strip()
        except UnicodeDecodeError as error:
            raise DeploymentProviderError(
                "SIGNING_KEY_RING_READBACK_INVALID"
            ) from error
        if observed != expected:
            raise DeploymentProviderError("SIGNING_KEY_RING_READBACK_MISMATCH")
        return observed

    def publish_initial_generation(self, generation: InitialGeneration) -> str:
        object_uri = f"gs://{_CONFIGURATION_BUCKET}/{generation.object_name}"
        self._try(
            "storage",
            "cp",
            "-",
            object_uri,
            "--if-generation-match=0",
            *self._common(),
            stdin=generation.contents,
        )
        return self.read_initial_generation()

    def read_initial_generation(self) -> str:
        object_name = "generations/1/compiled.json"
        object_uri = f"gs://{_CONFIGURATION_BUCKET}/{object_name}"
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
        if not isinstance(metadata, dict):
            raise DeploymentProviderError("GENERATION_OBJECT_READBACK_INVALID")
        try:
            object_generation = int(metadata["generation"])
        except (KeyError, TypeError, ValueError) as error:
            raise DeploymentProviderError("GENERATION_OBJECT_READBACK_INVALID") from error
        if object_generation < 1:
            raise DeploymentProviderError("GENERATION_OBJECT_READBACK_INVALID")
        contents = self._run_common(
            "GENERATION_OBJECT_CONTENT_READBACK_FAILED",
            "storage",
            "cat",
            f"{object_uri}#{object_generation}",
        ).stdout
        try:
            return existing_initial_generation_reference(contents, object_generation)
        except LocalDeploymentInputError as error:
            raise DeploymentProviderError(str(error)) from error

    def _read_image(
        self,
        package: str,
        source_revision: str,
        invalid_code: str,
        project_id: str = _PROJECT_ID,
    ) -> str | None:
        if _SOURCE_REVISION.fullmatch(source_revision) is None:
            raise ValueError("source revision must be exact")
        tagged_image = f"{package}:source-{source_revision}"
        result = self._try(
            "artifacts",
            "docker",
            "images",
            "describe",
            tagged_image,
            "--format=value(image_summary.digest)",
            *self._common(project_id),
        )
        if result.returncode != 0:
            return None
        digest = result.stdout.decode("ascii", errors="strict").strip()
        if re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
            raise DeploymentProviderError(invalid_code)
        return f"{package}@{digest}"

    def read_shared_edge_image(self, source_revision: str) -> str | None:
        return self._read_image(
            _IMAGE_PACKAGE,
            source_revision,
            "EDGE_IMAGE_READBACK_INVALID",
        )

    def read_fixture_image(self, source_revision: str) -> str | None:
        return self._read_image(
            self._fixture_image_package,
            source_revision,
            "FIXTURE_IMAGE_READBACK_INVALID",
            self._fixture_project_id,
        )

    def publish_shared_edge_image(self, source_revision: str) -> str:
        existing = self.read_shared_edge_image(source_revision)
        if existing is not None:
            return existing
        config = (
            self._working_root
            / "infrastructure/images/shared-edge/cloudbuild.yaml"
        ).resolve()
        if (
            self._working_root not in config.parents
            or not config.is_file()
            or config.is_symlink()
        ):
            raise DeploymentProviderError("EDGE_IMAGE_BUILD_CONFIG_INVALID")
        tagged_image = f"{_IMAGE_PACKAGE}:source-{source_revision}"
        self._run_cloud_build(
            "EDGE_IMAGE_BUILD_FAILED",
            "EDGE_IMAGE_BUILD_CONFIG_INVALID",
            "shared-edge-image",
            "builds",
            "submit",
            str(self._working_root),
            f"--config={config}",
            f"--substitutions=_IMAGE={tagged_image}",
        )
        observed = self.read_shared_edge_image(source_revision)
        if observed is None:
            raise DeploymentProviderError("EDGE_IMAGE_READBACK_MISSING")
        return observed

    def publish_fixture_image(self, source_revision: str) -> str:
        existing = self.read_fixture_image(source_revision)
        if existing is not None:
            return existing
        config = (
            self._working_root
            / "infrastructure/images/fixture/cloudbuild.yaml"
        ).resolve()
        if (
            self._working_root not in config.parents
            or not config.is_file()
            or config.is_symlink()
        ):
            raise DeploymentProviderError("FIXTURE_IMAGE_BUILD_CONFIG_INVALID")
        tagged_image = f"{self._fixture_image_package}:source-{source_revision}"
        self._run_cloud_build(
            "FIXTURE_IMAGE_BUILD_FAILED",
            "FIXTURE_IMAGE_BUILD_CONFIG_INVALID",
            "fixture-image",
            "builds",
            "submit",
            str(self._working_root),
            f"--config={config}",
            (
                f"--substitutions=_IMAGE={tagged_image},"
                f"_SOURCE_REVISION={source_revision}"
            ),
            project_id=self._fixture_project_id,
        )
        observed = self.read_fixture_image(source_revision)
        if observed is None:
            raise DeploymentProviderError("FIXTURE_IMAGE_READBACK_MISSING")
        return observed

    def active_signing_key_version(self) -> str:
        values = self._json(
            "SIGNING_KEY_VERSION_READBACK_INVALID",
            self._run_common(
                "SIGNING_KEY_VERSION_READBACK_FAILED",
                "kms",
                "keys",
                "versions",
                "list",
                f"--key={_SIGNING_KEY}",
                f"--keyring={_SIGNING_KEY_RING}",
                f"--location={_REGION}",
                "--filter=state:ENABLED",
                "--format=json",
            ).stdout,
        )
        if not isinstance(values, list):
            raise DeploymentProviderError("SIGNING_KEY_VERSION_READBACK_INVALID")
        names = sorted(
            value.get("name")
            for value in values
            if isinstance(value, dict) and isinstance(value.get("name"), str)
        )
        if len(names) != 1 or _VERSION_REFERENCE.fullmatch(names[0]) is None:
            raise DeploymentProviderError("SIGNING_KEY_VERSION_READBACK_INVALID")
        return names[0]

    def oauth_secret_version(self) -> str:
        values = self._json(
            "OAUTH_SECRET_VERSION_READBACK_INVALID",
            self._run_common(
                "OAUTH_SECRET_VERSION_READBACK_FAILED",
                "secrets",
                "versions",
                "list",
                _OAUTH_SECRET,
                "--filter=state:ENABLED",
                "--format=json",
            ).stdout,
        )
        if not isinstance(values, list):
            raise DeploymentProviderError("OAUTH_SECRET_VERSION_READBACK_INVALID")
        names = sorted(
            value.get("name")
            for value in values
            if isinstance(value, dict) and isinstance(value.get("name"), str)
        )
        if len(names) != 1:
            raise DeploymentProviderError("OAUTH_SECRET_VERSION_READBACK_INVALID")
        trusted_prefixes = (
            f"projects/{_PROJECT_ID}/secrets/{_OAUTH_SECRET}/versions/",
            f"projects/{_PROJECT_NUMBER}/secrets/{_OAUTH_SECRET}/versions/",
        )
        version = next(
            (
                names[0].removeprefix(prefix)
                for prefix in trusted_prefixes
                if names[0].startswith(prefix)
            ),
            "",
        )
        if re.fullmatch(r"[1-9][0-9]*", version) is None:
            raise DeploymentProviderError("OAUTH_SECRET_VERSION_READBACK_INVALID")
        return trusted_prefixes[0] + version

    def certificate_readback(self) -> CertificateReadback:
        value = self._json(
            "CERTIFICATE_READBACK_INVALID",
            self._run_common(
                "CERTIFICATE_READBACK_FAILED",
                "compute",
                "ssl-certificates",
                "describe",
                _CERTIFICATE,
                "--global",
                "--format=json",
            ).stdout,
        )
        if not isinstance(value, dict):
            raise DeploymentProviderError("CERTIFICATE_READBACK_INVALID")
        managed = value.get("managed")
        if not isinstance(managed, dict):
            raise DeploymentProviderError("CERTIFICATE_READBACK_INVALID")
        domains = managed.get("domains")
        domain_statuses = managed.get("domainStatus")
        status = managed.get("status")
        reference = value.get("selfLink")
        if (
            domains != [_HOSTNAME]
            or not isinstance(domain_statuses, dict)
            or set(domain_statuses) != {_HOSTNAME}
            or not isinstance(domain_statuses.get(_HOSTNAME), str)
            or not isinstance(status, str)
            or not isinstance(reference, str)
        ):
            raise DeploymentProviderError("CERTIFICATE_READBACK_INVALID")
        domain_status = domain_statuses[_HOSTNAME]
        if status == "PROVISIONING_FAILED":
            raise DeploymentProviderError("CERTIFICATE_PROVISIONING_FAILED")
        if status == "PROVISIONING_FAILED_PERMANENTLY":
            raise DeploymentProviderError(
                "CERTIFICATE_PROVISIONING_FAILED_PERMANENTLY"
            )
        if status == "RENEWAL_FAILED":
            raise DeploymentProviderError("CERTIFICATE_RENEWAL_FAILED")
        domain_failure = {
            "FAILED_NOT_VISIBLE": "CERTIFICATE_DOMAIN_NOT_VISIBLE",
            "FAILED_CAA_CHECKING": "CERTIFICATE_DOMAIN_CAA_CHECK_FAILED",
            "FAILED_CAA_FORBIDDEN": "CERTIFICATE_DOMAIN_CAA_FORBIDDEN",
            "FAILED_RATE_LIMITED": "CERTIFICATE_DOMAIN_RATE_LIMITED",
        }.get(domain_status)
        if domain_failure is not None:
            raise DeploymentProviderError(domain_failure)
        if domain_status.startswith("FAILED_"):
            raise DeploymentProviderError("CERTIFICATE_DOMAIN_VALIDATION_FAILED")
        if (status, domain_status) not in {
            ("ACTIVE", "ACTIVE"),
            ("PROVISIONING", "PROVISIONING"),
        }:
            raise DeploymentProviderError("CERTIFICATE_READBACK_INVALID")
        return CertificateReadback(reference, status, domain_status)


__all__ = (
    "CertificateReadback",
    "ClosedDeploymentGcloudRunner",
    "DeploymentProviderError",
    "DeploymentProviderRunner",
    "GcloudDeploymentProvider",
)
