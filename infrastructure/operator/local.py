"""Local, path-bounded filesystem implementation for operator state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING

from infrastructure.operator._core import LifecycleOperator
from infrastructure.operator._interfaces import (
    DiscoverySnapshot,
    GitSnapshot,
    OperatorAdapters,
)
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


@dataclass(frozen=True, slots=True)
class ProfileGcp:
    executable: Path | None = None
    cloud_sdk_configuration: Path | None = None

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

    def _read(self, *arguments: str) -> str | None:
        if self.executable is None:
            return None
        try:
            completed = subprocess.run(
                [str(self.executable), *arguments],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=self._environment(),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout.strip()

    def inspect(self, profile: dict[str, object]) -> DiscoverySnapshot:
        active_account = self._read(
            "auth",
            "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
        )
        active_project = self._read("config", "get-value", "project")
        application_default_ready = bool(
            self._read("auth", "application-default", "print-access-token")
        )
        blockers: list[str] = []
        if not active_account or not active_project:
            blockers.append("OPERATOR_SESSION_UNAVAILABLE")
        elif active_project != profile.get("project_id"):
            blockers.append("OPERATOR_PROJECT_MISMATCH")
        if not application_default_ready:
            blockers.append("OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_UNAVAILABLE")
        return DiscoverySnapshot(
            "gcp",
            (
                ("active_account", active_account or "unavailable"),
                (
                    "application_default_credentials",
                    "ready" if application_default_ready else "unavailable",
                ),
                ("project_id", active_project or "unavailable"),
                ("project_number", str(profile.get("project_number", ""))),
                ("region", str(profile.get("region", ""))),
            ),
            tuple(blockers),
        )

    def operator_session(
        self,
        profile: dict[str, object],
    ) -> OperatorSessionFacts | None:
        """Derive immutable session facts without persisting the identity token."""

        from infrastructure.operator.local_deployment import OperatorSessionFacts

        active_account = self._read(
            "auth",
            "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
        )
        active_project = self._read("config", "get-value", "project")
        billing_account = self._read(
            "billing",
            "projects",
            "describe",
            str(profile.get("project_id", "")),
            "--format=value(billingAccountName)",
        )
        identity_token = self._read("auth", "print-identity-token")
        if (
            not active_account
            or active_project != profile.get("project_id")
            or not billing_account
            or not identity_token
        ):
            return None
        try:
            segments = identity_token.split(".")
            if len(segments) != 3:
                return None
            encoded = segments[1] + "=" * (-len(segments[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
            if (
                not isinstance(claims, dict)
                or claims.get("iss") != "https://accounts.google.com"
                or claims.get("email") != active_account
                or not isinstance(claims.get("sub"), str)
            ):
                return None
            return OperatorSessionFacts(
                active_account=active_account,
                billing_account_reference=billing_account,
                operator_issuer="https://accounts.google.com",
                operator_subject=claims["sub"],
            )
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            return None

    def application_default_ready(self) -> bool:
        """Verify Terraform-compatible user ADC without retaining its access token."""

        return bool(self._read("auth", "application-default", "print-access-token"))


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
    def ask(self, prompt: str) -> str:
        return input(prompt)

    def confirm(self, prompt: str) -> bool:
        return input(prompt).strip().lower() in {"y", "yes"}

    def write(self, message: str) -> None:
        print(message)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        return input(prompt) == expected

    def pause(self, prompt: str) -> None:
        input(prompt)


@dataclass(frozen=True, slots=True)
class SystemClock:
    def now(self) -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SystemWaiter:
    def wait(self, seconds: int) -> None:
        time.sleep(seconds)


def _local_deployment_executor(
    project_root: Path,
    state_root: Path,
    gcp: ProfileGcp,
    terminal: ConsoleTerminal,
):
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
    session = gcp.operator_session(
        {
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
        }
    )
    if (
        gcloud is None
        or configuration is None
        or dig_name is None
        or session is None
        or not gcp.application_default_ready()
        or not gcloud.is_file()
        or not configuration.is_dir()
        or configuration.is_symlink()
        or not TERRAFORM.is_file()
        or not OFFLINE_CLI_CONFIG.is_file()
    ):
        return None
    try:
        resolved_state = state_root.resolve()
        if state_root.is_symlink():
            return None
        resolved_state.mkdir(mode=0o700, parents=True, exist_ok=True)
        resolved_state.chmod(0o700)
        working_root = resolved_state / "work/deployment"
        working_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        working_root.chmod(0o700)
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
        )
        provider = GcloudDeploymentProvider(
            executable=gcloud,
            cloud_sdk_configuration=configuration,
            working_root=project_root,
            runner=ClosedDeploymentGcloudRunner(
                gcloud,
                project_root,
                configuration,
            ),
        )
        dig = Path(dig_name).resolve()
        dns = DigDnsReadback(
            dig,
            project_root,
            ClosedDigRunner(dig, project_root),
        )
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
        )
        return DeploymentExecutor(
            working_root,
            terminal,
            commands,
            waiter=SystemWaiter(),
        )
    except (OSError, RuntimeError, ValueError):
        return None


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
            filesystem=LocalFilesystem(resolved_project, state_root),
            clock=SystemClock(),
            executor=(
                _local_deployment_executor(
                    resolved_project,
                    state_root,
                    gcp,
                    terminal,
                )
                if arm_executor
                else None
            ),
        ),
        source_authority=source_authority,
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
        LocalPlatformIntegrationReader(filesystem, operator, generations),
        attachment_reader=provider,
        generation_control=generations if provider is not None else None,
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

    resolved_project = project_root.resolve()
    resolved_state = state_root.resolve()
    executable_name = shutil.which("gcloud")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    if executable_name is None:
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    gcloud = Path(executable_name).resolve()
    gcp = ProfileGcp(gcloud, configuration)
    session = gcp.operator_session(
        {
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
        }
    )
    if (
        not gcloud.is_file()
        or not configuration.is_dir()
        or configuration.is_symlink()
        or session is None
        or not gcp.application_default_ready()
        or not TERRAFORM.is_file()
        or not OFFLINE_CLI_CONFIG.is_file()
    ):
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    resolved_state.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved_state.chmod(0o700)
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
    )
    generation_provider = _local_generation_provider(resolved_project, resolved_state)
    if generation_provider is None:
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    filesystem = LocalFilesystem(resolved_project, resolved_state)
    generations = LocalRegistrationGenerationControl(
        filesystem,
        generation_provider,
    )
    platform = LocalPlatformIntegrationReader(
        filesystem,
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
    )
    terminal = ConsoleTerminal()
    integration = ApplicationIntegrationLifecycle(
        platform,
        attachment_reader=generation_provider,
        generation_control=generations,
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
        )
    )
    return LocalFixtureOperator(
        LocalGit(resolved_project),
        platform,
        lifecycle,
        LocalApplicationHandoffs(filesystem),
        source_authority=source_authority,
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

    resolved_project = project_root.resolve()
    resolved_state = state_root.resolve()
    provider = _local_generation_provider(resolved_project, resolved_state)
    if provider is None:
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    filesystem = LocalFilesystem(resolved_project, resolved_state)
    generations = LocalRegistrationGenerationControl(filesystem, provider)
    platform = LocalPlatformIntegrationReader(
        filesystem,
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
    )
    return LocalFixtureStatusOperator(
        ApplicationIntegrationLifecycle(
            platform,
            attachment_reader=provider,
            generation_control=generations,
        )
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
    from infrastructure.operator.local_qualification import (
        LiveGenerationRollbackExercise,
        LocalQualificationStateReader,
    )
    from infrastructure.operator.qualification import (
        QualificationLifecycle,
        QualificationSuiteEvaluator,
    )

    resolved_project = project_root.resolve()
    resolved_state = state_root.resolve()
    executable_name = shutil.which("gcloud")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    if executable_name is None:
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    gcloud = Path(executable_name).resolve()
    gcp = ProfileGcp(gcloud, configuration)
    session = gcp.operator_session(
        {
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
        }
    )
    if (
        not gcloud.is_file()
        or not configuration.is_dir()
        or configuration.is_symlink()
        or session is None
        or not gcp.application_default_ready()
    ):
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    provider = _local_generation_provider(resolved_project, resolved_state)
    if provider is None:
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")

    filesystem = LocalFilesystem(resolved_project, resolved_state)
    generations = LocalRegistrationGenerationControl(filesystem, provider)
    platform = LocalPlatformIntegrationReader(
        filesystem,
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
    )
    terminal = ConsoleTerminal()
    state_reader = LocalQualificationStateReader(
        build_local_operator(resolved_project, resolved_state, source_authority),
        generations,
        LocalApplicationHandoffs(filesystem),
        provider,
    )
    probe = StagingQualificationProbe(
        HttpxQualificationClient(),
        LoopbackBrowserQualification(SystemBrowserLauncher(), terminal),
        provider,
        LiveGenerationRollbackExercise(
            platform,
            LocalReviewedGenerationControl(generations),
            terminal,
        ),
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
    resolved_state = state_root.resolve()
    executable_name = shutil.which("gcloud")
    dig_name = shutil.which("dig")
    configured = os.environ.get("CLOUDSDK_CONFIG")
    configuration = (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".config" / "gcloud"
    ).resolve()
    if executable_name is None or dig_name is None:
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    gcloud = Path(executable_name).resolve()
    dig = Path(dig_name).resolve()
    gcp = ProfileGcp(gcloud, configuration)
    session = gcp.operator_session(
        {
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
        }
    )
    if (
        not gcloud.is_file()
        or not dig.is_file()
        or not configuration.is_dir()
        or configuration.is_symlink()
        or session is None
        or not gcp.application_default_ready()
        or not TERRAFORM.is_file()
        or not OFFLINE_CLI_CONFIG.is_file()
    ):
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")
    provider = _local_generation_provider(resolved_project, resolved_state)
    if provider is None:
        raise RuntimeError("OPERATOR_SESSION_UNAVAILABLE")

    resolved_state.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved_state.chmod(0o700)
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
    )
    filesystem = LocalFilesystem(resolved_project, resolved_state)
    renderer = DeploymentConfigurationRenderer(
        resolved_project,
        working_root,
        session,
    )
    generations = LocalRegistrationGenerationControl(filesystem, provider)
    terminal = ConsoleTerminal()
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
