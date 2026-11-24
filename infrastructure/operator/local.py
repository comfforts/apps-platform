"""Local, path-bounded filesystem implementation for operator state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit
import webbrowser

from infrastructure.config.project_identity import fixtures_project_id
from infrastructure.operator._core import LifecycleOperator
from infrastructure.operator._interfaces import (
    DiscoverySnapshot,
    GitSnapshot,
    OperatorAdapters,
    StageExecutor,
)
from infrastructure.operator.diagnostics import capture_private_command_failure
from infrastructure.tools.terraform_setup import (
    GOOGLE_PROVIDER_VERSION,
    MANIFEST,
    MIRROR_ROOT,
    OFFLINE_CLI_CONFIG,
    TERRAFORM,
    TERRAFORM_VERSION,
)

if TYPE_CHECKING:
    from infrastructure.operator.local_deployment import OperatorSessionFacts


_OUTPUT_ASSIGNMENT_RE = re.compile(
    r"(?im)(\b(?:api[_-]?key|authorization|client[_-]?secret|password|"
    r"access[_-]?token|refresh[_-]?token|id[_-]?token|private[_-]?key)\b"
    r"\s*[:=]\s*)(?:Bearer\s+)?"
    r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"
)
_OUTPUT_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_OUTPUT_USERINFO_RE = re.compile(r"(?i)(https?://[^/\s:@]+:)[^@\s/]+@")
_OUTPUT_PROVIDER_VALUE_RE = re.compile(
    r"(?i)\b(?:GOCSPX-|ya29\.|ghp_|github_pat_)[A-Za-z0-9._-]+"
)
_OUTPUT_PEM_RE = re.compile(
    r"(?s)-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?"
    r"-----END [^-\r\n]*PRIVATE KEY-----"
)


def _credential_free_environment() -> dict[str, str]:
    environment = {
        name: os.environ[name]
        for name in ("LANG", "LC_ALL", "LC_CTYPE", "PATH", "TMPDIR")
        if name in os.environ
    }
    environment["CHECKPOINT_DISABLE"] = "1"
    return environment


class LocalFilesystem:
    """Keep private generated operator state separate from committed source."""

    def __init__(self, project_root: Path, state_root: Path) -> None:
        self._project_root = project_root.resolve()
        self._state_root = state_root.resolve()

    @staticmethod
    def _bounded(root: Path, relative_path: str) -> Path:
        candidate = (root / relative_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("path escapes its approved root")
        return candidate

    def project_path(self, relative_path: str) -> Path:
        return self._bounded(self._project_root, relative_path)

    def state_path(self, relative_path: str) -> Path:
        return self._bounded(self._state_root, relative_path)

    def read_state(self, relative_path: str) -> bytes | None:
        path = self.state_path(relative_path)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def write_state(
        self,
        relative_path: str,
        contents: bytes,
        *,
        replace: bool,
    ) -> None:
        path = self.state_path(relative_path)
        self._state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._state_root.chmod(0o700)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        if not replace and path.exists():
            if path.read_bytes() != contents:
                raise FileExistsError(f"refusing to replace immutable state {relative_path}")
            return
        descriptor, temporary_name = tempfile.mkstemp(prefix=".operator-", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(contents)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
            path.chmod(0o600)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise


def _run_git(project_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _try_run_git(project_root: Path, *arguments: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _repository_identity(remote: str) -> str:
    normalized = remote.strip().removesuffix(".git")
    if normalized.startswith("git@github.com:"):
        return normalized.removeprefix("git@github.com:")
    marker = "github.com/"
    if marker in normalized:
        return normalized.split(marker, maxsplit=1)[1]
    return normalized


@dataclass(frozen=True, slots=True)
class LocalGit:
    project_root: Path

    def inspect(self) -> GitSnapshot:
        remote = _run_git(self.project_root, "config", "--get", "remote.origin.url")
        upstream_branch = _try_run_git(
            self.project_root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        )
        upstream_revision = _try_run_git(
            self.project_root,
            "rev-parse",
            "@{upstream}",
        )
        ancestor = subprocess.run(
            [
                "git",
                "-C",
                str(self.project_root),
                "merge-base",
                "--is-ancestor",
                "origin/main",
                "HEAD",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return GitSnapshot(
            repository=_repository_identity(remote),
            revision=_run_git(self.project_root, "rev-parse", "HEAD"),
            branch=_run_git(self.project_root, "branch", "--show-current"),
            clean=not bool(
                _run_git(
                    self.project_root,
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=all",
                )
            ),
            main_revision=_run_git(self.project_root, "rev-parse", "main"),
            origin_main_revision=_run_git(
                self.project_root,
                "rev-parse",
                "origin/main",
            ),
            upstream_branch=upstream_branch,
            upstream_revision=upstream_revision,
            origin_main_ancestor=ancestor.returncode == 0,
        )


@dataclass(frozen=True, slots=True)
class LocalGitHub:
    project_root: Path

    def inspect(self, profile: dict[str, object]) -> DiscoverySnapshot:
        del profile
        remote = _run_git(self.project_root, "config", "--get", "remote.origin.url")
        return DiscoverySnapshot(
            "github",
            (("repository", _repository_identity(remote)),),
        )


class OperatorSessionError(RuntimeError):
    """Precise safe blocker with optional private command diagnostics."""

    def __init__(
        self,
        code: str,
        diagnostic: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.diagnostic = dict(diagnostic or {})


@dataclass(frozen=True, slots=True)
class ProfileGcp:
    executable: Path | None = None
    cloud_sdk_configuration: Path | None = None
    private_state_root: Path | None = None
    environment: str = "staging"

    def _environment(self) -> dict[str, str]:
        environment = {
            name: os.environ[name]
            for name in ("HOME", "LANG", "LC_ALL", "LC_CTYPE", "PATH", "TMPDIR")
            if name in os.environ
        }
        environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
        environment["CLOUDSDK_PYTHON_SITEPACKAGES"] = "0"
        if self.cloud_sdk_configuration is not None:
            environment["CLOUDSDK_CONFIG"] = str(self.cloud_sdk_configuration)
        return environment

    @staticmethod
    def _bytes(value: bytes | str | None) -> bytes:
        if value is None:
            return b""
        return value if isinstance(value, bytes) else value.encode("utf-8")

    def _diagnostic(
        self,
        phase: str,
        stdout: bytes | str | None,
        stderr: bytes | str | None,
    ) -> dict[str, str]:
        return capture_private_command_failure(
            self.private_state_root,
            environment=self.environment,
            operation="gcloud-read",
            phase=phase,
            stdout=self._bytes(stdout),
            stderr=self._bytes(stderr),
        )

    def _read(
        self,
        *arguments: str,
        phase: str,
        failure_code: str,
        timeout_code: str,
    ) -> str:
        if self.executable is None:
            raise OperatorSessionError("GCLOUD_EXECUTABLE_UNAVAILABLE")
        for attempt in range(2):
            try:
                completed = subprocess.run(
                    [str(self.executable), *arguments],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=self._environment(),
                )
            except subprocess.TimeoutExpired as error:
                if attempt == 0:
                    continue
                raise OperatorSessionError(
                    timeout_code,
                    self._diagnostic(phase, error.stdout, error.stderr),
                ) from error
            except (OSError, subprocess.SubprocessError) as error:
                if attempt == 0:
                    continue
                raise OperatorSessionError(
                    failure_code,
                    self._diagnostic(phase, None, str(error)),
                ) from error
            value = completed.stdout.strip()
            if completed.returncode == 0 and value:
                return value
            if attempt == 0:
                continue
            raise OperatorSessionError(
                failure_code,
                self._diagnostic(
                    phase,
                    completed.stdout,
                    completed.stderr,
                ),
            )
        raise AssertionError("bounded gcloud read loop did not return")

    def _discovery_read(
        self,
        *arguments: str,
        phase: str,
        failure_code: str,
        timeout_code: str,
    ) -> tuple[str | None, str | None]:
        try:
            return (
                self._read(
                    *arguments,
                    phase=phase,
                    failure_code=failure_code,
                    timeout_code=timeout_code,
                ),
                None,
            )
        except OperatorSessionError as error:
            return None, str(error)

    def inspect(self, profile: dict[str, object]) -> DiscoverySnapshot:
        active_account, account_blocker = self._discovery_read(
            "auth",
            "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
            phase="active-account",
            failure_code="OPERATOR_ACTIVE_ACCOUNT_READBACK_FAILED",
            timeout_code="OPERATOR_ACTIVE_ACCOUNT_READBACK_TIMEOUT",
        )
        active_project, project_blocker = self._discovery_read(
            "config",
            "get-value",
            "project",
            phase="active-project",
            failure_code="OPERATOR_PROJECT_READBACK_FAILED",
            timeout_code="OPERATOR_PROJECT_READBACK_TIMEOUT",
        )
        application_default, adc_blocker = self._discovery_read(
            "auth",
            "application-default",
            "print-access-token",
            phase="application-default-credentials",
            failure_code="OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_UNAVAILABLE",
            timeout_code="OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_TIMEOUT",
        )
        blockers = [
            blocker
            for blocker in (account_blocker, project_blocker, adc_blocker)
            if blocker is not None
        ]
        if active_project is not None and active_project != profile.get("project_id"):
            blockers.append("OPERATOR_PROJECT_MISMATCH")
        return DiscoverySnapshot(
            "gcp",
            (
                ("active_account", active_account or "unavailable"),
                (
                    "application_default_credentials",
                    "ready" if application_default is not None else "unavailable",
                ),
                ("project_id", active_project or "unavailable"),
                ("project_number", str(profile.get("project_number", ""))),
                ("region", str(profile.get("region", ""))),
            ),
            tuple(sorted(set(blockers))),
        )

    def require_operator_session(
        self,
        profile: dict[str, object],
    ) -> OperatorSessionFacts:
        """Read one exact verified session with one retry per read-only command."""

        from infrastructure.operator.local_deployment import OperatorSessionFacts

        active_account = self._read(
            "auth",
            "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
            phase="active-account",
            failure_code="OPERATOR_ACTIVE_ACCOUNT_READBACK_FAILED",
            timeout_code="OPERATOR_ACTIVE_ACCOUNT_READBACK_TIMEOUT",
        )
        active_project = self._read(
            "config",
            "get-value",
            "project",
            phase="active-project",
            failure_code="OPERATOR_PROJECT_READBACK_FAILED",
            timeout_code="OPERATOR_PROJECT_READBACK_TIMEOUT",
        )
        if active_project != profile.get("project_id"):
            raise OperatorSessionError("OPERATOR_PROJECT_MISMATCH")
        billing_account = self._read(
            "billing",
            "projects",
            "describe",
            str(profile.get("project_id", "")),
            "--format=value(billingAccountName)",
            phase="billing-readback",
            failure_code="OPERATOR_BILLING_READBACK_FAILED",
            timeout_code="OPERATOR_BILLING_READBACK_TIMEOUT",
        )
        identity_token = self._read(
            "auth",
            "print-identity-token",
            phase="identity-token",
            failure_code="OPERATOR_IDENTITY_TOKEN_FAILED",
            timeout_code="OPERATOR_IDENTITY_TOKEN_TIMEOUT",
        )
        try:
            segments = identity_token.split(".")
            if len(segments) != 3:
                raise ValueError("identity token is not a JWT")
            encoded = segments[1] + "=" * (-len(segments[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
            if (
                not isinstance(claims, dict)
                or claims.get("iss") != "https://accounts.google.com"
                or claims.get("email") != active_account
                or not isinstance(claims.get("sub"), str)
            ):
                raise ValueError("identity token claims are invalid")
            return OperatorSessionFacts(
                active_account=active_account,
                billing_account_reference=billing_account,
                operator_issuer="https://accounts.google.com",
                operator_subject=claims["sub"],
            )
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise OperatorSessionError("OPERATOR_IDENTITY_TOKEN_INVALID") from error

    def operator_session(
        self,
        profile: dict[str, object],
    ) -> OperatorSessionFacts | None:
        """Derive immutable session facts without persisting the identity token."""

        try:
            return self.require_operator_session(profile)
        except OperatorSessionError:
            return None

    def require_application_default(self) -> None:
        self._read(
            "auth",
            "application-default",
            "print-access-token",
            phase="application-default-credentials",
            failure_code="OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_UNAVAILABLE",
            timeout_code="OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_TIMEOUT",
        )

    def application_default_ready(self) -> bool:
        """Verify Terraform-compatible user ADC without retaining its access token."""
        try:
            self.require_application_default()
        except OperatorSessionError:
            return False
        return True


@dataclass(frozen=True, slots=True)
class ProfileDns:
    executable: Path | None = None

    def inspect(self, profile: dict[str, object]) -> DiscoverySnapshot:
        return DiscoverySnapshot(
            "dns",
            (
                ("provider_class", str(profile["dns_provider_class"])),
                ("hostname", str(profile["hostname"])),
            ),
            ()
            if self.executable is not None and self.executable.is_file()
            else ("DNS_TOOL_UNAVAILABLE",),
        )


@dataclass(frozen=True, slots=True)
class PinnedTerraform:
    """Verify only the ignored, checksum-bound local AP-M7 toolchain."""

    def inspect(self) -> DiscoverySnapshot:
        if not TERRAFORM.is_file() or not MANIFEST.is_file():
            return DiscoverySnapshot(
                "terraform",
                (),
                ("PINNED_TOOL_UNAVAILABLE",),
            )
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            observed = subprocess.run(
                [str(TERRAFORM), "version", "-json"],
                check=True,
                capture_output=True,
                text=True,
                env=_credential_free_environment(),
            )
            version = json.loads(observed.stdout).get("terraform_version")
            terraform_record = manifest.get("terraform", {})
            provider_record = manifest.get("google_provider", {})
            binary_digest = hashlib.sha256(TERRAFORM.read_bytes()).hexdigest()
            provider_packages = sorted(
                MIRROR_ROOT.rglob(
                    f"terraform-provider-google_{GOOGLE_PROVIDER_VERSION}_*.zip"
                )
            )
            valid = (
                version == TERRAFORM_VERSION
                and terraform_record.get("version") == TERRAFORM_VERSION
                and terraform_record.get("binary_sha256") == binary_digest
                and provider_record.get("version") == GOOGLE_PROVIDER_VERSION
                and len(provider_packages) == 1
                and provider_record.get("sha256")
                == hashlib.sha256(provider_packages[0].read_bytes()).hexdigest()
            )
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            valid = False
        if not valid:
            return DiscoverySnapshot(
                "terraform",
                (),
                ("PINNED_TOOL_INVALID",),
            )
        return DiscoverySnapshot(
            "terraform",
            (
                ("terraform_version", TERRAFORM_VERSION),
                ("provider_version", GOOGLE_PROVIDER_VERSION),
            ),
        )


@dataclass(frozen=True, slots=True)
class ConsoleTerminal:
    @staticmethod
    def _redact_sensitive(message: str) -> str:
        """Mask recognizable credential values before writing operator output."""

        redacted = _OUTPUT_PEM_RE.sub("[REDACTED PRIVATE KEY]", message)
        redacted = _OUTPUT_USERINFO_RE.sub(r"\1[REDACTED]@", redacted)
        redacted = _OUTPUT_BEARER_RE.sub("Bearer [REDACTED]", redacted)
        redacted = _OUTPUT_PROVIDER_VALUE_RE.sub("[REDACTED]", redacted)
        return _OUTPUT_ASSIGNMENT_RE.sub(r"\1[REDACTED]", redacted)

    def ask(self, prompt: str) -> str:
        return input(prompt)

    def confirm(self, prompt: str) -> bool:
        return input(prompt).strip().lower() in {"y", "yes"}

    def write(self, message: str) -> None:
        print(self._redact_sensitive(message), file=sys.stderr)
        print(file=sys.stderr)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        return input(prompt) == expected

    def pause(self, prompt: str) -> None:
        input(prompt)


def _report_private_command_diagnostic(
    terminal: ConsoleTerminal,
    title: str,
    error: OperatorSessionError,
) -> None:
    if not error.diagnostic:
        return
    terminal.write(
        title
        + "\n"
        + json.dumps(
            {"blocker": str(error), **error.diagnostic},
            indent=2,
            sort_keys=True,
        )
    )
    if "diagnostic_path" in error.diagnostic:
        terminal.write(
            "Private command diagnostics may contain sensitive provider data. "
            "Inspect locally; do not commit or share them unredacted."
        )


@dataclass(frozen=True, slots=True)
class _VerifiedGcpSession:
    executable: Path
    configuration: Path
    state_root: Path
    facts: OperatorSessionFacts


def _verified_gcp_session(
    gcp: ProfileGcp,
    state_root: Path,
    terminal: ConsoleTerminal,
) -> _VerifiedGcpSession:
    executable = gcp.executable
    configuration = gcp.cloud_sdk_configuration
    if executable is None or not executable.is_file():
        raise RuntimeError("GCLOUD_EXECUTABLE_UNAVAILABLE")
    if (
        configuration is None
        or not configuration.is_dir()
        or configuration.is_symlink()
    ):
        raise RuntimeError("CLOUD_SDK_CONFIGURATION_UNAVAILABLE")
    try:
        if state_root.is_symlink():
            raise ValueError("operator state root is a symlink")
        resolved_state = state_root.resolve()
        resolved_state.mkdir(mode=0o700, parents=True, exist_ok=True)
        resolved_state.chmod(0o700)
    except (OSError, RuntimeError, ValueError) as error:
        raise RuntimeError("OPERATOR_STATE_DIRECTORY_UNAVAILABLE") from error
    checked = ProfileGcp(
        executable,
        configuration,
        private_state_root=resolved_state,
    )
    try:
        facts = checked.require_operator_session(
            {
                "project_id": "comfforts-platform-non-prod",
                "project_number": "455651441682",
                "region": "us-west1",
            }
        )
        checked.require_application_default()
    except OperatorSessionError as error:
        _report_private_command_diagnostic(
            terminal,
            "OPERATOR SESSION ERROR",
            error,
        )
        raise RuntimeError(str(error)) from error
    return _VerifiedGcpSession(
        executable,
        configuration,
        resolved_state,
        facts,
    )


@dataclass(frozen=True, slots=True)
class SystemClock:
    def now(self) -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SystemWaiter:
    def wait(self, seconds: int) -> None:
        time.sleep(seconds)


@dataclass(frozen=True, slots=True)
class SystemConsolePageLauncher:
    """Open only the reviewed staging OAuth console surfaces."""

    def open(self, url: str) -> bool:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, strict_parsing=True)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "console.cloud.google.com"
            or parsed.path
            not in {
                "/auth/branding",
                "/auth/clients",
                "/security/secret-manager/secret/app-platform-edge-oauth/versions",
            }
            or query != {"project": ["comfforts-platform-non-prod"]}
            or parsed.fragment
        ):
            raise ValueError("checkpoint console URL is outside the staging allow-list")
        return webbrowser.open(url, new=2, autoraise=True)


@dataclass(frozen=True, slots=True)
class _DeploymentExecutorResult:
    executor: StageExecutor | None
    blockers: tuple[str, ...] = ()


def _local_deployment_executor(
    project_root: Path,
    state_root: Path,
    gcp: ProfileGcp,
    terminal: ConsoleTerminal,
) -> _DeploymentExecutorResult:
    """Arm real staging commands only when every local human-session seam exists."""

    from infrastructure.operator.commands import (
        ClosedSubprocessRunner,
        TerraformCliAdapter,
    )
    from infrastructure.operator.deployment import DeploymentExecutor
    from infrastructure.operator.deployment_dns import ClosedDigRunner, DigDnsReadback
    from infrastructure.operator.deployment_provider import (
        ClosedDeploymentGcloudRunner,
        GcloudDeploymentProvider,
    )
    from infrastructure.operator.local_deployment import DeploymentConfigurationRenderer
    from infrastructure.operator.local_deployment_commands import LocalDeploymentCommands

    gcloud = gcp.executable
    configuration = gcp.cloud_sdk_configuration
    dig_name = shutil.which("dig")
    blockers: list[str] = []
    if gcloud is None or not gcloud.is_file():
        blockers.append("GCLOUD_EXECUTABLE_UNAVAILABLE")
    if (
        configuration is None
        or not configuration.is_dir()
        or configuration.is_symlink()
    ):
        blockers.append("CLOUD_SDK_CONFIGURATION_UNAVAILABLE")
    if dig_name is None or not Path(dig_name).is_file():
        blockers.append("DNS_EXECUTABLE_UNAVAILABLE")
    if not TERRAFORM.is_file():
        blockers.append("TERRAFORM_EXECUTABLE_UNAVAILABLE")
    if not OFFLINE_CLI_CONFIG.is_file():
        blockers.append("TERRAFORM_CLI_CONFIGURATION_UNAVAILABLE")
    if blockers:
        return _DeploymentExecutorResult(None, tuple(sorted(blockers)))

    try:
        verified = _verified_gcp_session(gcp, state_root, terminal)
        gcloud = verified.executable
        configuration = verified.configuration
        resolved_state = verified.state_root
        session = verified.facts
        working_root = resolved_state / "work/deployment"
        working_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        working_root.chmod(0o700)
    except RuntimeError as error:
        return _DeploymentExecutorResult(None, (str(error),))
    except (OSError, ValueError):
        return _DeploymentExecutorResult(None, ("OPERATOR_STATE_DIRECTORY_UNAVAILABLE",))

    try:
        terraform_runner = ClosedSubprocessRunner((TERRAFORM,), working_root)
        terraform = TerraformCliAdapter(
            TERRAFORM,
            OFFLINE_CLI_CONFIG,
            working_root,
            terraform_runner,
            operator_environment=(
                ("CLOUDSDK_CONFIG", str(configuration)),
                ("HOME", str(Path.home().resolve())),
            ),
            private_state_root=resolved_state,
        )
    except (OSError, RuntimeError, ValueError):
        return _DeploymentExecutorResult(
            None,
            ("TERRAFORM_COMMAND_ADAPTER_UNAVAILABLE",),
        )

    try:
        provider = GcloudDeploymentProvider(
            executable=gcloud,
            cloud_sdk_configuration=configuration,
            working_root=project_root,
            runner=ClosedDeploymentGcloudRunner(
                gcloud,
                project_root,
                configuration,
            ),
            fixture_project_id=fixtures_project_id(),
            private_state_root=resolved_state,
        )
    except (OSError, RuntimeError, ValueError):
        return _DeploymentExecutorResult(
            None,
            ("GCLOUD_COMMAND_ADAPTER_UNAVAILABLE",),
        )

    generation_provider = _local_generation_provider(
        project_root,
        resolved_state,
    )
    if generation_provider is None:
        return _DeploymentExecutorResult(
            None,
            ("GENERATION_COMMAND_ADAPTER_UNAVAILABLE",),
        )
    from infrastructure.operator.local_generation import (
        LocalRegistrationGenerationControl,
    )

    generation_control = LocalRegistrationGenerationControl(
        LocalFilesystem(project_root, resolved_state),
        generation_provider,
    )

    try:
        dig = Path(dig_name).resolve()
        dns = DigDnsReadback(
            dig,
            project_root,
            ClosedDigRunner(dig, project_root),
        )
    except (OSError, RuntimeError, ValueError):
        return _DeploymentExecutorResult(
            None,
            ("DNS_COMMAND_ADAPTER_UNAVAILABLE",),
        )

    try:
        commands = LocalDeploymentCommands(
            DeploymentConfigurationRenderer(
                project_root,
                working_root,
                session,
            ),
            terraform,
            provider,
            dns,
            session,
            runtime_provider=generation_provider,
            runtime_recorder=generation_control,
        )
        return _DeploymentExecutorResult(
            DeploymentExecutor(
                working_root,
                terminal,
                commands,
                waiter=SystemWaiter(),
                checkpoint_page_launcher=SystemConsolePageLauncher(),
            )
        )
    except (OSError, RuntimeError, ValueError):
        return _DeploymentExecutorResult(
            None,
            ("DEPLOYMENT_EXECUTOR_CONSTRUCTION_FAILED",),
        )


def build_local_operator(
    project_root: Path,
    state_root: Path,
    source_authority: str = "accepted",
    *,
    arm_executor: bool = True,
) -> LifecycleOperator:
    """Construct the local operator around the active human Cloud SDK session."""

    resolved_project = project_root.resolve()
    executable_name = shutil.which("gcloud")
    dig_name = shutil.which("dig")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    cloud_sdk_configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    gcp = ProfileGcp(
        Path(executable_name).resolve() if executable_name else None,
        cloud_sdk_configuration,
    )
    terminal = ConsoleTerminal()
    execution = (
        _local_deployment_executor(
            resolved_project,
            state_root,
            gcp,
            terminal,
        )
        if arm_executor
        else _DeploymentExecutorResult(None)
    )
    filesystem = LocalFilesystem(resolved_project, state_root)
    active_source_reader = None
    generation_provider = _local_generation_provider(resolved_project, state_root)
    if generation_provider is not None:
        from infrastructure.operator.local_generation import (
            LocalRegistrationGenerationControl,
        )

        active_source_reader = LocalRegistrationGenerationControl(
            filesystem,
            generation_provider,
        )
    return LifecycleOperator(
        OperatorAdapters(
            git=LocalGit(resolved_project),
            github=LocalGitHub(resolved_project),
            gcp=gcp,
            terraform=PinnedTerraform(),
            dns=ProfileDns(
                Path(dig_name).resolve() if dig_name else None
            ),
            terminal=terminal,
            filesystem=filesystem,
            clock=SystemClock(),
            executor=execution.executor,
            execution_blockers=execution.blockers,
        ),
        source_authority=source_authority,
        active_source_reader=active_source_reader,
    )


def _local_generation_provider(
    project_root: Path,
    state_root: Path,
):
    """Build the closed provider boundary only from explicit private local state."""

    from infrastructure.operator.provider_commands import (
        ClosedGcloudRunner,
        GcloudGenerationProvider,
    )
    from infrastructure.operator.local_project_connections import (
        LocalProjectConnectionStore,
    )

    executable_name = shutil.which("gcloud")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    cloud_sdk_configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    if executable_name is None or not cloud_sdk_configuration.is_dir():
        return None
    if cloud_sdk_configuration.is_symlink():
        return None
    executable = Path(executable_name).resolve()
    runner = ClosedGcloudRunner(
        executable,
        project_root,
        cloud_sdk_configuration,
    )
    return GcloudGenerationProvider(
        executable=executable,
        cloud_sdk_configuration=cloud_sdk_configuration,
        working_root=project_root,
        project_id="comfforts-platform-non-prod",
        project_number="455651441682",
        region="us-west1",
        service_name="app-platform-edge",
        configuration_bucket="comfforts-ap-stg-455651441682-configuration",
        runner=runner,
        project_connections=LocalProjectConnectionStore(
            LocalFilesystem(project_root, state_root)
        ),
    )


def build_local_integration(
    project_root: Path,
    state_root: Path,
    source_authority: str = "accepted",
):
    """Construct local handoff reads and conditionally arm provider mutation."""

    from infrastructure.operator.integration import ApplicationIntegrationLifecycle
    from infrastructure.operator.local_generation import (
        LocalRegistrationGenerationControl,
    )
    from infrastructure.operator.local_integration import (
        LocalPlatformIntegrationReader,
    )
    from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
    from infrastructure.operator.local_project_connections import (
        LocalProjectConnectionStore,
    )

    resolved_project = project_root.resolve()
    filesystem = LocalFilesystem(resolved_project, state_root)
    operator = build_local_operator(
        resolved_project,
        state_root,
        source_authority,
    )
    provider = _local_generation_provider(resolved_project, state_root)
    generations = LocalRegistrationGenerationControl(filesystem, provider)
    return ApplicationIntegrationLifecycle(
        LocalPlatformIntegrationReader(
            filesystem,
            operator,
            generations,
            initial_generation_binder=generations,
        ),
        attachment_reader=provider,
        generation_control=generations if provider is not None else None,
        project_connections=LocalProjectConnectionStore(filesystem),
        terminal=ConsoleTerminal(),
    )


def build_local_fixture_operator(
    project_root: Path,
    state_root: Path,
    source_authority: str = "accepted",
):
    """Construct the complete fixture operator only from the verified human session."""

    from infrastructure.operator.commands import (
        ClosedSubprocessRunner,
        TerraformCliAdapter,
    )
    from infrastructure.operator.deployment import DeploymentExecutor
    from infrastructure.operator.deployment_provider import (
        ClosedDeploymentGcloudRunner,
        GcloudDeploymentProvider,
    )
    from infrastructure.operator.fixture_lifecycle import FixtureSuiteLifecycle
    from infrastructure.operator.integration import ApplicationIntegrationLifecycle
    from infrastructure.operator.local_fixture_deployment import (
        FixtureConfigurationRenderer,
        LocalFixtureDeploymentCommands,
    )
    from infrastructure.operator.local_fixture_lifecycle import (
        LocalFixtureLifecycleCommands,
        LocalFixtureOperator,
    )
    from infrastructure.operator.local_fixture_preparations import (
        LocalFixturePreparations,
    )
    from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
    from infrastructure.operator.local_generation import (
        LocalRegistrationGenerationControl,
    )
    from infrastructure.operator.local_integration import (
        LocalPlatformIntegrationReader,
    )
    from infrastructure.operator.local_project_connections import (
        LocalProjectConnectionStore,
    )

    resolved_project = project_root.resolve()
    terminal = ConsoleTerminal()
    executable_name = shutil.which("gcloud")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    if not TERRAFORM.is_file():
        raise RuntimeError("TERRAFORM_EXECUTABLE_UNAVAILABLE")
    if not OFFLINE_CLI_CONFIG.is_file():
        raise RuntimeError("TERRAFORM_CLI_CONFIGURATION_UNAVAILABLE")
    verified = _verified_gcp_session(
        ProfileGcp(
            Path(executable_name).resolve() if executable_name else None,
            configuration,
        ),
        state_root,
        terminal,
    )
    gcloud = verified.executable
    configuration = verified.configuration
    resolved_state = verified.state_root
    session = verified.facts
    working_root = resolved_state / "work/fixtures"
    working_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    working_root.chmod(0o700)

    terraform = TerraformCliAdapter(
        TERRAFORM,
        OFFLINE_CLI_CONFIG,
        working_root,
        ClosedSubprocessRunner((TERRAFORM,), working_root),
        operator_environment=(
            ("CLOUDSDK_CONFIG", str(configuration)),
            ("HOME", str(Path.home().resolve())),
        ),
        private_state_root=resolved_state,
    )
    image_provider = GcloudDeploymentProvider(
        executable=gcloud,
        cloud_sdk_configuration=configuration,
        working_root=resolved_project,
        runner=ClosedDeploymentGcloudRunner(
            gcloud,
            resolved_project,
            configuration,
        ),
        fixture_project_id=fixtures_project_id(),
        private_state_root=resolved_state,
    )
    generation_provider = _local_generation_provider(resolved_project, resolved_state)
    if generation_provider is None:
        raise RuntimeError("GCLOUD_COMMAND_ADAPTER_UNAVAILABLE")
    filesystem = LocalFilesystem(resolved_project, resolved_state)
    generations = LocalRegistrationGenerationControl(
        filesystem,
        generation_provider,
    )
    platform = LocalPlatformIntegrationReader(
        filesystem,
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
        initial_generation_binder=generations,
    )
    integration = ApplicationIntegrationLifecycle(
        platform,
        attachment_reader=generation_provider,
        generation_control=generations,
        project_connections=LocalProjectConnectionStore(filesystem),
        terminal=terminal,
    )
    fixture_terraform_commands = LocalFixtureDeploymentCommands(
        FixtureConfigurationRenderer(resolved_project, working_root),
        terraform,
        generation_provider,
    )
    executor = DeploymentExecutor(
        working_root,
        terminal,
        fixture_terraform_commands,  # type: ignore[arg-type]
    )
    lifecycle = FixtureSuiteLifecycle(
        LocalFixtureLifecycleCommands(
            integration,
            image_provider,
            executor,
            (session.operator_issuer, session.operator_subject),
            LocalApplicationHandoffs(filesystem),
            terminal,
            LocalFixturePreparations(filesystem),
        ),
        terminal=terminal,
    )
    return LocalFixtureOperator(
        LocalGit(resolved_project),
        platform,
        lifecycle,
        LocalApplicationHandoffs(filesystem),
        source_authority=source_authority,
    )


def build_local_project_lifecycle(
    project_root: Path,
    state_root: Path,
    source_authority: str = "accepted",
):
    """Construct explicit project bootstrap/connection operations."""

    from infrastructure.operator.local_project_connections import (
        GcloudApplicationProjectProvider,
        LocalProjectConnectionStore,
    )
    from infrastructure.operator.project_connections import (
        ApplicationProjectLifecycle,
    )
    from infrastructure.operator.source_authority import source_authority_blockers

    resolved_project = project_root.resolve()
    snapshot = LocalGit(resolved_project).inspect()
    blockers = source_authority_blockers(snapshot, "staging", source_authority)
    if blockers:
        raise RuntimeError(blockers[0])
    terminal = ConsoleTerminal()
    executable_name = shutil.which("gcloud")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    verified = _verified_gcp_session(
        ProfileGcp(
            Path(executable_name).resolve() if executable_name else None,
            configuration,
        ),
        state_root,
        terminal,
    )
    filesystem = LocalFilesystem(resolved_project, verified.state_root)
    return ApplicationProjectLifecycle(
        GcloudApplicationProjectProvider(
            verified.executable,
            verified.configuration,
            resolved_project,
            fixtures_project_id(),
        ),
        LocalProjectConnectionStore(filesystem),
        terminal,
    )


def build_local_fixture_status_operator(
    project_root: Path,
    state_root: Path,
    source_authority: str = "accepted",
):
    """Construct fixture status without arming Terraform or image mutation."""

    from infrastructure.operator.integration import ApplicationIntegrationLifecycle
    from infrastructure.operator.local_fixture_lifecycle import (
        LocalFixtureStatusOperator,
    )
    from infrastructure.operator.local_generation import (
        LocalRegistrationGenerationControl,
    )
    from infrastructure.operator.local_integration import (
        LocalPlatformIntegrationReader,
    )
    from infrastructure.operator.local_project_connections import (
        LocalProjectConnectionStore,
    )
    import httpx

    resolved_project = project_root.resolve()
    resolved_state = state_root.resolve()
    provider = _local_generation_provider(resolved_project, resolved_state)
    if provider is None:
        raise RuntimeError("GCLOUD_COMMAND_ADAPTER_UNAVAILABLE")
    filesystem = LocalFilesystem(resolved_project, resolved_state)
    generations = LocalRegistrationGenerationControl(filesystem, provider)
    platform = LocalPlatformIntegrationReader(
        filesystem,
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
        initial_generation_binder=generations,
    )
    def route_ready(application_id: str) -> bool:
        try:
            with httpx.Client(
                follow_redirects=False,
                timeout=10.0,
                trust_env=False,
            ) as client:
                response = client.get(
                    f"https://apps-staging.comfforts.com/{application_id}"
                )
        except httpx.HTTPError:
            return False
        if 200 <= response.status_code < 300:
            return True
        return (
            300 <= response.status_code < 400
            and bool(response.headers.get("location"))
        )

    return LocalFixtureStatusOperator(
        ApplicationIntegrationLifecycle(
            platform,
            attachment_reader=provider,
            generation_control=generations,
            project_connections=LocalProjectConnectionStore(filesystem),
        ),
        route_ready,
    )


def build_local_qualification(
    project_root: Path,
    state_root: Path,
    source_authority: str = "accepted",
):
    """Construct exact staging qualification only for a verified human session."""

    from infrastructure.operator.live_qualification import (
        HttpxQualificationClient,
        LoopbackBrowserQualification,
        StagingQualificationProbe,
        SystemBrowserLauncher,
    )
    from infrastructure.operator.local_generation import (
        LocalRegistrationGenerationControl,
        LocalReviewedGenerationControl,
    )
    from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
    from infrastructure.operator.local_integration import (
        LocalPlatformIntegrationReader,
    )
    from infrastructure.operator.local_project_connections import (
        GcloudApplicationProjectProvider,
    )
    from infrastructure.operator.local_qualification import (
        LiveGenerationRollbackExercise,
        LocalQualificationStateReader,
    )
    from infrastructure.operator.qualification import (
        QualificationLifecycle,
        QualificationSuiteEvaluator,
    )
    resolved_project = project_root.resolve()
    terminal = ConsoleTerminal()
    executable_name = shutil.which("gcloud")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    verified = _verified_gcp_session(
        ProfileGcp(
            Path(executable_name).resolve() if executable_name else None,
            configuration,
        ),
        state_root,
        terminal,
    )
    resolved_state = verified.state_root
    provider = _local_generation_provider(resolved_project, resolved_state)
    if provider is None:
        raise RuntimeError("GCLOUD_COMMAND_ADAPTER_UNAVAILABLE")

    filesystem = LocalFilesystem(resolved_project, resolved_state)
    generations = LocalRegistrationGenerationControl(filesystem, provider)
    platform = LocalPlatformIntegrationReader(
        filesystem,
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
        initial_generation_binder=generations,
    )
    state_reader = LocalQualificationStateReader(
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
        LocalApplicationHandoffs(filesystem),
        provider,
    )
    fixture_project = GcloudApplicationProjectProvider(
        verified.executable,
        verified.configuration,
        resolved_project,
        fixtures_project_id(),
    ).read_project(fixtures_project_id())
    probe = StagingQualificationProbe(
        HttpxQualificationClient(),
        LoopbackBrowserQualification(SystemBrowserLauncher(), terminal),
        provider,
        LiveGenerationRollbackExercise(
            platform,
            LocalReviewedGenerationControl(generations),
            terminal,
        ),
        fixture_project,
    )
    return QualificationLifecycle(state_reader, QualificationSuiteEvaluator(probe))


def build_local_destruction(
    project_root: Path,
    state_root: Path,
    source_authority: str = "accepted",
):
    """Construct exact safe destruction only for a verified human session."""

    from infrastructure.operator.commands import (
        ClosedSubprocessRunner,
        TerraformCliAdapter,
    )
    from infrastructure.operator.deployment_dns import ClosedDigRunner, DigDnsReadback
    from infrastructure.operator.destruction import DestructionLifecycle
    from infrastructure.operator.local_deployment import DeploymentConfigurationRenderer
    from infrastructure.operator.local_destruction import LocalDestructionControl
    from infrastructure.operator.local_destruction_commands import (
        LocalDestructionExecutor,
        LocalDestructionStateReader,
    )
    from infrastructure.operator.local_generation import (
        LocalRegistrationGenerationControl,
    )

    resolved_project = project_root.resolve()
    terminal = ConsoleTerminal()
    executable_name = shutil.which("gcloud")
    dig_name = shutil.which("dig")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    if not TERRAFORM.is_file():
        raise RuntimeError("TERRAFORM_EXECUTABLE_UNAVAILABLE")
    if not OFFLINE_CLI_CONFIG.is_file():
        raise RuntimeError("TERRAFORM_CLI_CONFIGURATION_UNAVAILABLE")
    verified = _verified_gcp_session(
        ProfileGcp(
            Path(executable_name).resolve() if executable_name else None,
            configuration,
        ),
        state_root,
        terminal,
    )
    configuration = verified.configuration
    resolved_state = verified.state_root
    session = verified.facts
    if dig_name is None:
        raise RuntimeError("DNS_EXECUTABLE_UNAVAILABLE")
    dig = Path(dig_name).resolve()
    if not dig.is_file():
        raise RuntimeError("DNS_EXECUTABLE_UNAVAILABLE")
    provider = _local_generation_provider(resolved_project, resolved_state)
    if provider is None:
        raise RuntimeError("GCLOUD_COMMAND_ADAPTER_UNAVAILABLE")

    working_root = resolved_state / "work/destruction"
    working_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    working_root.chmod(0o700)
    terraform = TerraformCliAdapter(
        TERRAFORM,
        OFFLINE_CLI_CONFIG,
        working_root,
        ClosedSubprocessRunner((TERRAFORM,), working_root),
        operator_environment=(
            ("CLOUDSDK_CONFIG", str(configuration)),
            ("HOME", str(Path.home().resolve())),
        ),
        private_state_root=resolved_state,
    )
    filesystem = LocalFilesystem(resolved_project, resolved_state)
    renderer = DeploymentConfigurationRenderer(
        resolved_project,
        working_root,
        session,
    )
    generations = LocalRegistrationGenerationControl(filesystem, provider)
    dns = DigDnsReadback(
        dig,
        resolved_project,
        ClosedDigRunner(dig, resolved_project),
    )
    status = build_local_operator(
        resolved_project,
        resolved_state,
        source_authority,
    )
    return DestructionLifecycle(
        LocalDestructionStateReader(
            filesystem,
            status,
            generations,
            provider,
            terraform,
            renderer,
            working_root,
        ),
        LocalDestructionControl(filesystem),
        terminal,
        LocalDestructionExecutor(
            filesystem,
            working_root,
            renderer,
            terraform,
            provider,
            dns,
            terminal,
            SystemWaiter(),
        ),
    )
