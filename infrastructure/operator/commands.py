"""Closed external-command construction for AP-M9 interactive deployment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
from typing import Protocol

from infrastructure.backend import PhasePlanRequest
from infrastructure.operator.deployment import (
    DeploymentCommandError,
    TerraformPlanArtifact,
)


_ALLOWED_ENVIRONMENT = {
    "CHECKPOINT_DISABLE",
    "CLOUDSDK_CONFIG",
    "HOME",
    "TF_CLI_CONFIG_FILE",
}
_PROHIBITED_TERRAFORM_ARGUMENTS = {
    "force-unlock",
    "import",
    "state",
    "taint",
    "untaint",
    "-force-copy",
    "-lock=false",
    "-migrate-state",
    "-reconfigure",
}
_PROHIBITED_TERRAFORM_PREFIXES = ("-replace=", "-target=")
_SIGNING_KEY_RING_ADDRESS = (
    "module.platform_foundation.google_kms_key_ring.assertion_signing"
)
_APPLY_HTTP_STATUS = re.compile(rb"(?:googleapi:\s*)?Error\s+([1-5][0-9]{2}):")
_APPLY_OPERATION = re.compile(
    rb"Error:\s+Error\s+([A-Za-z][A-Za-z0-9 _-]{0,79}):"
)
_APPLY_RESOURCE_ADDRESS = re.compile(
    rb"(?m)^\s*with\s+([A-Za-z0-9_.\[\]\"-]{1,300}),\s*$"
)
_APPLY_INCONSISTENT_RESOURCE_ADDRESS = re.compile(
    rb"When applying changes to ([A-Za-z0-9_.\[\]\"-]{1,300}),\s+provider\b"
)
_PLAN_PROTECTED_RESOURCE_ADDRESS = re.compile(
    rb"(?m)^Resource ([A-Za-z0-9_.\[\]\"-]{1,300}) has\s*$"
)
_APPLY_SERVICE = re.compile(
    rb"\b([a-z][a-z0-9.-]{1,100}\.googleapis\.com)\b"
)
_APPLY_STATUS_BLOCKERS = {
    "SERVICE_DISABLED": "TERRAFORM_APPLY_SERVICE_DISABLED",
    "UNAUTHENTICATED": "TERRAFORM_APPLY_AUTHENTICATION_FAILED",
    "PERMISSION_DENIED": "TERRAFORM_APPLY_PERMISSION_DENIED",
    "INVALID_ARGUMENT": "TERRAFORM_APPLY_INVALID_ARGUMENT",
    "RESOURCE_EXHAUSTED": "TERRAFORM_APPLY_QUOTA_EXCEEDED",
    "ALREADY_EXISTS": "TERRAFORM_APPLY_CONFLICT",
}
_APPLY_HTTP_BLOCKERS = {
    400: "TERRAFORM_APPLY_INVALID_ARGUMENT",
    401: "TERRAFORM_APPLY_AUTHENTICATION_FAILED",
    403: "TERRAFORM_APPLY_PERMISSION_DENIED",
    409: "TERRAFORM_APPLY_CONFLICT",
    429: "TERRAFORM_APPLY_QUOTA_EXCEEDED",
}
_APPLY_PROVIDER_STATUSES = (
    *_APPLY_STATUS_BLOCKERS,
    "NOT_FOUND",
    "FAILED_PRECONDITION",
)


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """One shell-free command with a complete closed environment."""

    argv: tuple[str, ...]
    cwd: Path
    environment: tuple[tuple[str, str], ...]
    timeout_seconds: int = 900
    authority: str = "ordinary"


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class CommandRunner(Protocol):
    def run(self, request: CommandRequest) -> CommandResult: ...


class ClosedSubprocessRunner:
    """Run only reviewed absolute executables, argv, paths, and environment names."""

    def __init__(self, executables: tuple[Path, ...], working_root: Path) -> None:
        self._executables = {str(path.resolve()) for path in executables}
        self._working_root = working_root.resolve()

    def validate(self, request: CommandRequest) -> None:
        if (
            not request.argv
            or str(Path(request.argv[0]).resolve()) not in self._executables
        ):
            raise ValueError("command executable is outside the approved set")
        cwd = request.cwd.resolve()
        if cwd != self._working_root and self._working_root not in cwd.parents:
            raise ValueError("command working directory escapes the approved root")
        if request.cwd.is_symlink() or not cwd.is_dir():
            raise ValueError("command working directory is not a real directory")
        if not 1 <= request.timeout_seconds <= 3600:
            raise ValueError("command timeout is outside the approved bound")
        names = [name for name, _ in request.environment]
        if len(names) != len(set(names)) or not set(names) <= _ALLOWED_ENVIRONMENT:
            raise ValueError("command environment contains an unapproved name")
        if request.authority not in {
            "ordinary",
            "bootstrap-state-migration",
            "platform-state-read",
            "platform-state-recovery",
            "application-state-read",
        }:
            raise ValueError("command authority is outside the approved set")
        if request.authority == "bootstrap-state-migration":
            expected = (
                str(Path(request.argv[0]).resolve()),
                "init",
                "-input=false",
                "-lockfile=readonly",
                "-migrate-state",
                "-force-copy",
                "-backend-config=bucket=comfforts-ap-stg-455651441682-platform-state",
                "-backend-config=prefix=bootstrap",
            )
            if request.argv != expected:
                raise ValueError("bootstrap migration command is not exact")
        if request.authority in {"platform-state-read", "application-state-read"}:
            expected = (
                str(Path(request.argv[0]).resolve()),
                "state",
                "list",
            )
            if request.argv != expected:
                raise ValueError("state projection command is not exact")
        if request.authority == "platform-state-recovery":
            expected = (
                str(Path(request.argv[0]).resolve()),
                "untaint",
                "-lock=true",
                "-lock-timeout=0s",
                _SIGNING_KEY_RING_ADDRESS,
            )
            if request.argv != expected:
                raise ValueError("platform state recovery command is not exact")
        if Path(request.argv[0]).name == "terraform":
            prohibited = _PROHIBITED_TERRAFORM_ARGUMENTS
            if request.authority == "bootstrap-state-migration":
                prohibited = prohibited - {"-force-copy", "-migrate-state"}
            if request.authority in {"platform-state-read", "application-state-read"}:
                prohibited = prohibited - {"state"}
            if request.authority == "platform-state-recovery":
                prohibited = prohibited - {"untaint"}
            if any(argument in prohibited for argument in request.argv[1:]):
                raise ValueError("prohibited Terraform operation or argument")
            if any(
                argument.startswith(prefix)
                for argument in request.argv[1:]
                for prefix in _PROHIBITED_TERRAFORM_PREFIXES
            ):
                raise ValueError("prohibited Terraform scope expansion")

    def run(self, request: CommandRequest) -> CommandResult:
        self.validate(request)
        completed = subprocess.run(
            list(request.argv),
            cwd=request.cwd,
            env=dict(request.environment),
            check=False,
            capture_output=True,
            timeout=request.timeout_seconds,
        )
        return CommandResult(
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )


class TerraformCliAdapter:
    """Create and apply private exact Terraform plans without retaining raw JSON."""

    def __init__(
        self,
        executable: Path,
        cli_configuration: Path,
        working_root: Path,
        runner: CommandRunner,
        operator_environment: tuple[tuple[str, str], ...] = (),
        private_state_root: Path | None = None,
    ) -> None:
        self._executable = executable.resolve()
        self._cli_configuration = cli_configuration.resolve()
        self._working_root = working_root.resolve()
        self._runner = runner
        self._operator_environment = tuple(sorted(operator_environment))
        self._private_state_root: Path | None = None
        if not self._working_root.is_dir():
            raise ValueError("Terraform working root does not exist")
        if stat.S_IMODE(self._working_root.stat().st_mode) & 0o077:
            raise ValueError("Terraform working root must be private")
        if private_state_root is not None:
            if private_state_root.is_symlink():
                raise ValueError("private operator state root must not be a symlink")
            resolved_state = private_state_root.resolve()
            if (
                not resolved_state.is_dir()
                or stat.S_IMODE(resolved_state.stat().st_mode) & 0o077
                or resolved_state not in self._working_root.parents
            ):
                raise ValueError("Terraform diagnostics require bounded private state")
            self._private_state_root = resolved_state
        if not self._executable.is_file() or not self._cli_configuration.is_file():
            raise ValueError("pinned Terraform executable and CLI configuration are required")
        names = [name for name, _ in self._operator_environment]
        if (
            len(names) != len(set(names))
            or not set(names) <= {"CLOUDSDK_CONFIG", "HOME"}
            or any(not value for _, value in self._operator_environment)
        ):
            raise ValueError("operator environment is not a bounded human session")

    def _bounded(self, path: Path, *, file_required: bool) -> Path:
        if path.is_symlink():
            raise ValueError("path is not a real private workspace path")
        resolved = path.resolve()
        if resolved == self._working_root or self._working_root not in resolved.parents:
            raise ValueError("path escapes the private Terraform workspace")
        if file_required and not resolved.is_file():
            raise ValueError("required private Terraform file is missing")
        if resolved.exists() and stat.S_IMODE(resolved.stat().st_mode) & 0o077:
            raise ValueError("Terraform workspace material must be private")
        return resolved

    def _environment(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (
                    ("CHECKPOINT_DISABLE", "1"),
                    ("TF_CLI_CONFIG_FILE", str(self._cli_configuration)),
                    *self._operator_environment,
                )
            )
        )

    @staticmethod
    def _write_private_file(path: Path, contents: bytes) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(contents)
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _ensure_private_diagnostic_directory(self, path: Path) -> Path:
        if self._private_state_root is None or path.is_symlink():
            raise ValueError("private diagnostic directory is not bounded")
        path.mkdir(mode=0o700, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise ValueError("private diagnostic directory is unavailable")
        resolved = path.resolve()
        if (
            resolved == self._private_state_root
            or self._private_state_root not in resolved.parents
        ):
            raise ValueError("private diagnostic directory escapes operator state")
        resolved.chmod(0o700)
        return resolved

    def _capture_failure(
        self,
        request: PhasePlanRequest,
        operation: str,
        result: CommandResult,
    ) -> dict[str, str]:
        if self._private_state_root is None:
            return {}
        if (
            operation not in {"plan", "apply"}
            or re.fullmatch(r"[a-z][a-z0-9-]{1,31}", request.environment) is None
            or re.fullmatch(r"[a-z][a-z0-9-]{1,63}", request.phase) is None
        ):
            return {"diagnostic_capture": "failed"}

        try:
            captured_at = datetime.now(UTC)
            digest = hashlib.sha256()
            digest.update(len(result.stdout).to_bytes(8, "big"))
            digest.update(result.stdout)
            digest.update(len(result.stderr).to_bytes(8, "big"))
            digest.update(result.stderr)
            raw_digest = digest.hexdigest()
            diagnostic_digest = f"sha256:{raw_digest}"
            diagnostics = self._ensure_private_diagnostic_directory(
                self._private_state_root / "diagnostics"
            )
            environment_root = self._ensure_private_diagnostic_directory(
                diagnostics / request.environment
            )
            event_name = (
                captured_at.strftime("%Y%m%dT%H%M%S.%fZ")
                + f"-{operation}-{request.phase}-{raw_digest[:12]}"
            )
            event_root = environment_root / event_name
            event_root.mkdir(mode=0o700)
            event_root.chmod(0o700)

            stdout_path = event_root / "stdout.log"
            stderr_path = event_root / "stderr.log"
            self._write_private_file(stdout_path, result.stdout)
            self._write_private_file(stderr_path, result.stderr)
            manifest = {
                "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
                "diagnostic_digest": diagnostic_digest,
                "diagnostic_version": 1,
                "environment": request.environment,
                "operation": operation,
                "phase": request.phase,
                "stderr": {
                    "bytes": len(result.stderr),
                    "filename": stderr_path.name,
                    "sha256": "sha256:" + hashlib.sha256(result.stderr).hexdigest(),
                },
                "stdout": {
                    "bytes": len(result.stdout),
                    "filename": stdout_path.name,
                    "sha256": "sha256:" + hashlib.sha256(result.stdout).hexdigest(),
                },
            }
            manifest_contents = (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            self._write_private_file(event_root / "manifest.json", manifest_contents)
            return {
                "diagnostic_digest": diagnostic_digest,
                "diagnostic_path": str(stderr_path),
            }
        except (OSError, RuntimeError, ValueError):
            return {"diagnostic_capture": "failed"}

    @staticmethod
    def _apply_failure_code(stderr: bytes) -> str:
        normalized = stderr.lower()
        if all(
            marker in normalized
            for marker in (
                b"revision named",
                b"with different configuration already exists",
            )
        ):
            return "TERRAFORM_APPLY_IMMUTABLE_REVISION_CONFLICT"
        if b"service account" in normalized and b"does not exist" in normalized:
            return "TERRAFORM_APPLY_IDENTITY_PROPAGATION_PENDING"
        if b"notification channel" in normalized and any(
            marker in normalized for marker in (b"not found", b"does not exist")
        ):
            return "TERRAFORM_APPLY_DEPENDENCY_PROPAGATION_PENDING"
        if b"concurrent policy changes" in normalized:
            return "TERRAFORM_APPLY_IAM_CONFLICT"
        if b"provider produced inconsistent result after apply" in normalized:
            return "TERRAFORM_APPLY_PROVIDER_INCONSISTENT_RESULT"
        if b"error acquiring the state lock" in normalized:
            return "TERRAFORM_APPLY_STATE_LOCKED"
        if all(
            marker in normalized
            for marker in (b"has not been used in project", b"it is disabled")
        ):
            return "TERRAFORM_APPLY_SERVICE_DISABLED"
        upper = stderr.upper()
        for status, blocker in _APPLY_STATUS_BLOCKERS.items():
            if status.encode("ascii") in upper:
                return blocker
        http_status = _APPLY_HTTP_STATUS.search(stderr)
        if http_status is not None:
            code = int(http_status.group(1))
            if code in _APPLY_HTTP_BLOCKERS:
                return _APPLY_HTTP_BLOCKERS[code]
        if any(
            marker in normalized
            for marker in (
                b"invalid_grant",
                b"reauth related error",
                b"could not find default credentials",
                b"cannot fetch token",
            )
        ):
            return "TERRAFORM_APPLY_AUTHENTICATION_FAILED"
        if b"quota exceeded" in normalized:
            return "TERRAFORM_APPLY_QUOTA_EXCEEDED"
        if b"permission denied" in normalized:
            return "TERRAFORM_APPLY_PERMISSION_DENIED"
        if any(
            marker in normalized
            for marker in (
                b"failed to instantiate provider",
                b"unrecognized remote plugin message",
                b"plugin did not respond",
            )
        ):
            return "TERRAFORM_APPLY_PLUGIN_FAILED"
        return "TERRAFORM_APPLY_FAILED_UNKNOWN"

    def _apply_failure(
        self,
        request: PhasePlanRequest,
        result: CommandResult,
    ) -> DeploymentCommandError:
        stderr = result.stderr
        blocker = self._apply_failure_code(stderr)
        diagnostic: dict[str, str | int] = {}

        http_status = _APPLY_HTTP_STATUS.search(stderr)
        if http_status is not None:
            diagnostic["http_status"] = int(http_status.group(1))

        operation = _APPLY_OPERATION.search(stderr)
        if operation is not None:
            diagnostic["operation"] = operation.group(1).decode("ascii")

        resource = _APPLY_RESOURCE_ADDRESS.search(stderr)
        if resource is None:
            resource = _APPLY_INCONSISTENT_RESOURCE_ADDRESS.search(stderr)
        if resource is not None:
            diagnostic["resource_address"] = resource.group(1).decode("ascii")

        service = _APPLY_SERVICE.search(stderr)
        if service is not None:
            diagnostic["service"] = service.group(1).decode("ascii")

        upper = stderr.upper()
        for status in _APPLY_PROVIDER_STATUSES:
            if status.encode("ascii") in upper:
                diagnostic["provider_status"] = status
                break
        if (
            blocker == "TERRAFORM_APPLY_SERVICE_DISABLED"
            and "provider_status" not in diagnostic
        ):
            diagnostic["provider_status"] = "SERVICE_DISABLED"

        diagnostic.update(self._capture_failure(request, "apply", result))

        return DeploymentCommandError(blocker, diagnostic=diagnostic)

    @staticmethod
    def _plan_failure(stderr: bytes) -> str:
        normalized = stderr.lower()
        if all(
            marker in normalized
            for marker in (
                b"instance cannot be destroyed",
                _SIGNING_KEY_RING_ADDRESS.encode("ascii"),
                b"lifecycle.prevent_destroy set",
            )
        ):
            return "TERRAFORM_PROTECTED_SIGNING_KEY_RING_TAINTED"
        if all(
            marker in normalized
            for marker in (
                b"instance cannot be destroyed",
                b"lifecycle.prevent_destroy set",
            )
        ):
            return "TERRAFORM_PROTECTED_RESOURCE_DELETE_PROPOSED"
        if b"error acquiring the state lock" in normalized:
            return "TERRAFORM_STATE_LOCKED"
        if any(
            marker in normalized
            for marker in (b"error loading state", b"failed to load state")
        ):
            return "TERRAFORM_STATE_READ_FAILED"
        if b"failed to get existing workspaces" in normalized and any(
            marker in normalized
            for marker in (b"403", b"access denied", b"permission denied")
        ):
            return "TERRAFORM_BACKEND_ACCESS_DENIED"
        if any(
            marker in normalized
            for marker in (
                b"invalid_grant",
                b"reauth related error",
                b"could not find default credentials",
                b"cannot fetch token",
            )
        ):
            return "TERRAFORM_OPERATOR_AUTHENTICATION_FAILED"
        if any(
            marker in normalized
            for marker in (b"quota exceeded", b"resource_exhausted", b"error 429")
        ):
            return "TERRAFORM_PROVIDER_QUOTA_EXCEEDED"
        if any(
            marker in normalized
            for marker in (b"error 403", b"permission_denied", b"permission denied")
        ):
            return "TERRAFORM_PROVIDER_PERMISSION_DENIED"
        if any(
            marker in normalized
            for marker in (
                b"missing required argument",
                b"unsupported argument",
                b"invalid value for input variable",
                b"reference to undeclared",
                b"unsupported block type",
            )
        ):
            return "TERRAFORM_CONFIGURATION_INVALID"
        if any(
            marker in normalized
            for marker in (
                b"failed to load plugin schemas",
                b"failed to instantiate provider",
                b"unrecognized remote plugin message",
            )
        ):
            return "TERRAFORM_PROVIDER_PLUGIN_FAILED"
        return "TERRAFORM_PLAN_FAILED_UNKNOWN"

    def _request(
        self,
        root: Path,
        environment: tuple[tuple[str, str], ...],
        *arguments: str,
        authority: str = "ordinary",
    ) -> CommandRequest:
        return CommandRequest(
            argv=(str(self._executable), *arguments),
            cwd=root,
            environment=environment,
            authority=authority,
        )

    @staticmethod
    def _projection(
        request: PhasePlanRequest,
        raw_plan: bytes,
        *,
        planning_mode: str = "normal",
    ) -> dict[str, object]:
        if len(raw_plan) > 16 * 1024 * 1024:
            raise DeploymentCommandError("TERRAFORM_PLAN_OUTPUT_TOO_LARGE")
        try:
            value = json.loads(raw_plan)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DeploymentCommandError("TERRAFORM_PLAN_OUTPUT_INVALID") from error
        if not isinstance(value, dict):
            raise DeploymentCommandError("TERRAFORM_PLAN_OUTPUT_INVALID")
        if value.get("terraform_version") != "1.17.2":
            raise DeploymentCommandError("TERRAFORM_VERSION_MISMATCH")
        resource_changes = value.get("resource_changes", [])
        if not isinstance(resource_changes, list):
            raise DeploymentCommandError("TERRAFORM_PLAN_OUTPUT_INVALID")
        changes: list[dict[str, object]] = []
        for item in resource_changes:
            if not isinstance(item, dict) or not isinstance(item.get("change"), dict):
                raise DeploymentCommandError("TERRAFORM_PLAN_OUTPUT_INVALID")
            change = item["change"]
            assert isinstance(change, dict)
            actions = change.get("actions")
            if not isinstance(actions, list):
                raise DeploymentCommandError("TERRAFORM_PLAN_OUTPUT_INVALID")
            changes.append(
                {
                    "address": item.get("address"),
                    "resource_type": item.get("type"),
                    "provider_source": item.get("provider_name"),
                    "actions": actions,
                }
            )
        return {
            "environment": request.environment,
            "source_revision": request.source_revision,
            "state_owner": request.state_owner,
            "owner_id": request.owner_id,
            "terraform_root": request.terraform_root,
            "phase": request.phase,
            "planning_mode": planning_mode,
            "provider": {
                "source": "registry.terraform.io/hashicorp/google",
                "service": "google",
                "project_id": request.project_id,
                "configuration": "explicit",
            },
            "changes": changes,
        }

    def create_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        variable_file: Path,
        *,
        bootstrap_remote: bool = False,
        destroy: bool = False,
        refresh_only: bool = False,
    ) -> TerraformPlanArtifact:
        if destroy and refresh_only:
            raise ValueError("destroy and refresh-only planning are mutually exclusive")
        root = self._bounded(terraform_root, file_required=False)
        if not root.is_dir():
            raise ValueError("Terraform root is not a directory")
        variables = self._bounded(variable_file, file_required=True)
        if request.phase != "bootstrap" or bootstrap_remote:
            backend = self._bounded(request.backend_path, file_required=True)
            if backend.parent != root:
                raise ValueError("backend declaration is outside the Terraform root")

        plan_directory = self._working_root / "plans"
        plan_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        plan_directory.chmod(0o700)
        plan_path = plan_directory / (
            f"{request.phase}-{secrets.token_hex(12)}.tfplan"
        )
        if plan_path.exists():
            raise FileExistsError("refusing to replace an existing saved plan")

        plan_environment = self._environment()
        self._initialize(request, root, bootstrap_remote=bootstrap_remote)
        plan_arguments = [
            "plan",
            "-input=false",
            "-lock=true",
            "-lock-timeout=0s",
            "-detailed-exitcode",
        ]
        if destroy:
            plan_arguments.append("-destroy")
        if refresh_only:
            plan_arguments.append("-refresh-only")
        plan_arguments.extend((f"-var-file={variables}", f"-out={plan_path}"))
        planned = self._runner.run(
            self._request(root, plan_environment, *plan_arguments)
        )
        if planned.returncode not in {0, 2}:
            failure = self._plan_failure(planned.stderr)
            diagnostic = self._capture_failure(request, "plan", planned)
            if failure == "TERRAFORM_PROTECTED_RESOURCE_DELETE_PROPOSED":
                resource = _PLAN_PROTECTED_RESOURCE_ADDRESS.search(planned.stderr)
                if resource is not None:
                    diagnostic["resource_address"] = resource.group(1).decode("ascii")
            try:
                plan_path.unlink(missing_ok=True)
            except OSError as error:
                raise DeploymentCommandError(
                    "TERRAFORM_FAILED_PLAN_CLEANUP_FAILED"
                ) from error
            raise DeploymentCommandError(failure, diagnostic=diagnostic)
        if plan_path.is_symlink() or not plan_path.is_file():
            raise DeploymentCommandError("TERRAFORM_PLAN_ARTIFACT_INVALID")
        try:
            plan_path.chmod(0o600)
        except OSError as error:
            raise DeploymentCommandError(
                "TERRAFORM_PLAN_PERMISSIONS_FAILED"
            ) from error
        try:
            saved_plan = self._bounded(plan_path, file_required=True)
        except ValueError as error:
            raise DeploymentCommandError("TERRAFORM_PLAN_ARTIFACT_INVALID") from error
        shown = self._runner.run(
            self._request(
                root,
                self._environment(),
                "show",
                "-json",
                str(saved_plan),
            )
        )
        if shown.returncode != 0:
            raise DeploymentCommandError("TERRAFORM_PLAN_SHOW_FAILED")
        return TerraformPlanArtifact(
            saved_plan,
            self._projection(
                request,
                shown.stdout,
                planning_mode="refresh-only" if refresh_only else "normal",
            ),
        )

    def clear_signing_key_ring_taint(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> None:
        if request.phase != "platform-foundation":
            raise DeploymentCommandError("TERRAFORM_RECOVERY_SCOPE_MISMATCH")
        root = self._bounded(terraform_root, file_required=False)
        if not root.is_dir():
            raise ValueError("Terraform root is not a directory")
        backend = self._bounded(request.backend_path, file_required=True)
        if backend.parent != root:
            raise ValueError("backend declaration is outside the Terraform root")
        self._initialize(request, root)
        recovered = self._runner.run(
            self._request(
                root,
                self._environment(),
                "untaint",
                "-lock=true",
                "-lock-timeout=0s",
                _SIGNING_KEY_RING_ADDRESS,
                authority="platform-state-recovery",
            )
        )
        if recovered.returncode != 0:
            raise DeploymentCommandError("TERRAFORM_STATE_RECOVERY_FAILED")

    def _initialize(
        self,
        request: PhasePlanRequest,
        root: Path,
        *,
        bootstrap_remote: bool = False,
    ) -> None:
        init_arguments = ["init", "-input=false", "-lockfile=readonly"]
        if request.phase == "bootstrap" and not bootstrap_remote:
            init_arguments.append("-backend=false")
        else:
            init_arguments.extend(
                (
                    f"-backend-config=bucket={request.backend_bucket}",
                    f"-backend-config=prefix={request.backend_prefix}",
                )
            )
        initialized = self._runner.run(
            self._request(root, self._environment(), *init_arguments)
        )
        if initialized.returncode != 0:
            raise DeploymentCommandError("TERRAFORM_INIT_FAILED")

    def apply_plan(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        saved_plan: Path,
    ) -> None:
        root = self._bounded(terraform_root, file_required=False)
        if not root.is_dir():
            raise ValueError("Terraform root is not a directory")
        plan = self._bounded(saved_plan, file_required=True)
        applied = self._runner.run(
            self._request(
                root,
                self._environment(),
                "apply",
                "-input=false",
                "-auto-approve",
                "-no-color",
                str(plan),
            )
        )
        if applied.returncode != 0:
            raise self._apply_failure(request, applied)

    def migrate_bootstrap_state(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> None:
        """Move the just-created local bootstrap state into its exact remote lineage."""

        if (
            request.phase != "bootstrap"
            or request.backend_bucket
            != "comfforts-ap-stg-455651441682-platform-state"
            or request.backend_prefix != "bootstrap"
        ):
            raise ValueError("bootstrap state migration scope is not exact")
        root = self._bounded(terraform_root, file_required=False)
        if not root.is_dir():
            raise ValueError("Terraform root is not a directory")
        migrated = self._runner.run(
            self._request(
                root,
                self._environment(),
                "init",
                "-input=false",
                "-lockfile=readonly",
                "-migrate-state",
                "-force-copy",
                f"-backend-config=bucket={request.backend_bucket}",
                f"-backend-config=prefix={request.backend_prefix}",
                authority="bootstrap-state-migration",
            )
        )
        if migrated.returncode != 0:
            raise DeploymentCommandError("BOOTSTRAP_STATE_MIGRATION_FAILED")

    def read_output(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
        output_name: str,
    ) -> object:
        """Read one closed non-secret output from the initialized exact lineage."""

        allowed = {
            "bootstrap": {"bootstrap_phase_output"},
            "platform-foundation": {"foundation_phase_output"},
            "shared-edge": {"shared_edge_phase_output"},
            "fixture-public": {"attachment_reference"},
            "fixture-authenticated": {"attachment_reference"},
            "fixture-restricted": {"attachment_reference"},
        }
        if output_name not in allowed.get(request.phase, set()):
            raise ValueError("Terraform output is outside the approved phase")
        root = self._bounded(terraform_root, file_required=False)
        if not root.is_dir():
            raise ValueError("Terraform root is not a directory")
        observed = self._runner.run(
            self._request(
                root,
                self._environment(),
                "output",
                "-json",
                output_name,
            )
        )
        if observed.returncode != 0:
            raise DeploymentCommandError("TERRAFORM_OUTPUT_READ_FAILED")
        if len(observed.stdout) > 1024 * 1024:
            raise DeploymentCommandError("TERRAFORM_OUTPUT_TOO_LARGE")
        try:
            return json.loads(observed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DeploymentCommandError("TERRAFORM_OUTPUT_INVALID") from error

    def state_empty(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> bool:
        """Read only whether the exact initialized fixture lineage is empty."""

        if not request.phase.startswith("fixture-"):
            raise ValueError("state emptiness readback is allowed only for a fixture root")
        root = self._bounded(terraform_root, file_required=False)
        observed = self._runner.run(
            self._request(
                root,
                self._environment(),
                "state",
                "list",
                authority="application-state-read",
            )
        )
        if observed.returncode != 0:
            raise DeploymentCommandError("TERRAFORM_STATE_READ_FAILED")
        if len(observed.stdout) > 1024 * 1024:
            raise DeploymentCommandError("TERRAFORM_STATE_OUTPUT_TOO_LARGE")
        return not observed.stdout.strip()

    def platform_state_addresses(
        self,
        request: PhasePlanRequest,
        terraform_root: Path,
    ) -> tuple[str, ...]:
        """Project the exact Platform State lineage to addresses only."""

        if (
            request.phase not in {"platform-foundation", "shared-edge"}
            or request.state_owner != "platform"
            or request.owner_id != "app-platform"
            or request.backend_prefix != "platform"
        ):
            raise ValueError("platform state projection scope is not exact")
        root = self._bounded(terraform_root, file_required=False)
        if not root.is_dir():
            raise ValueError("Terraform root is not a directory")
        self._initialize(request, root)
        observed = self._runner.run(
            self._request(
                root,
                self._environment(),
                "state",
                "list",
                authority="platform-state-read",
            )
        )
        if observed.returncode != 0:
            if (
                not observed.stdout.strip()
                and b"no state file was found" in observed.stderr.lower()
            ):
                return ()
            raise DeploymentCommandError("TERRAFORM_STATE_READ_FAILED")
        if len(observed.stdout) > 1024 * 1024:
            raise DeploymentCommandError("TERRAFORM_STATE_OUTPUT_TOO_LARGE")
        try:
            addresses = tuple(
                line.strip()
                for line in observed.stdout.decode("utf-8").splitlines()
                if line.strip()
            )
        except UnicodeDecodeError as error:
            raise DeploymentCommandError("TERRAFORM_STATE_OUTPUT_INVALID") from error
        if len(addresses) != len(set(addresses)):
            raise DeploymentCommandError("TERRAFORM_STATE_OUTPUT_INVALID")
        return tuple(sorted(addresses))


__all__ = (
    "ClosedSubprocessRunner",
    "CommandRequest",
    "CommandResult",
    "CommandRunner",
    "TerraformCliAdapter",
)
