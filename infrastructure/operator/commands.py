"""Closed external-command construction for AP-M9 interactive deployment."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
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
    "-force-copy",
    "-lock=false",
    "-migrate-state",
    "-reconfigure",
}
_PROHIBITED_TERRAFORM_PREFIXES = ("-replace=", "-target=")


@dataclass(frozen=True, slots=True)
class CommandRequest:
    """One shell-free command with a complete closed environment."""

    argv: tuple[str, ...]
    cwd: Path
    environment: tuple[tuple[str, str], ...]
    timeout_seconds: int = 900


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
        if Path(request.argv[0]).name == "terraform":
            if any(argument in _PROHIBITED_TERRAFORM_ARGUMENTS for argument in request.argv[1:]):
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
    ) -> None:
        self._executable = executable.resolve()
        self._cli_configuration = cli_configuration.resolve()
        self._working_root = working_root.resolve()
        self._runner = runner
        self._operator_environment = tuple(sorted(operator_environment))
        self._plan_sequence = 0
        if not self._working_root.is_dir():
            raise ValueError("Terraform working root does not exist")
        if stat.S_IMODE(self._working_root.stat().st_mode) & 0o077:
            raise ValueError("Terraform working root must be private")
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

    def _request(
        self,
        root: Path,
        environment: tuple[tuple[str, str], ...],
        *arguments: str,
    ) -> CommandRequest:
        return CommandRequest(
            argv=(str(self._executable), *arguments),
            cwd=root,
            environment=environment,
        )

    @staticmethod
    def _projection(
        request: PhasePlanRequest,
        raw_plan: bytes,
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
    ) -> TerraformPlanArtifact:
        root = self._bounded(terraform_root, file_required=False)
        if not root.is_dir():
            raise ValueError("Terraform root is not a directory")
        variables = self._bounded(variable_file, file_required=True)
        if request.phase != "bootstrap":
            backend = self._bounded(request.backend_path, file_required=True)
            if backend.parent != root:
                raise ValueError("backend declaration is outside the Terraform root")

        plan_directory = self._working_root / "plans"
        plan_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        plan_directory.chmod(0o700)
        self._plan_sequence += 1
        plan_path = plan_directory / f"{request.phase}-{self._plan_sequence:04d}.tfplan"
        if plan_path.exists():
            raise FileExistsError("refusing to replace an existing saved plan")

        plan_environment = self._environment()
        init_arguments = ["init", "-input=false", "-lockfile=readonly"]
        if request.phase == "bootstrap":
            init_arguments.append("-backend=false")
        else:
            init_arguments.extend(
                (
                    f"-backend-config=bucket={request.backend_bucket}",
                    f"-backend-config=prefix={request.backend_prefix}",
                )
            )
        initialized = self._runner.run(
            self._request(root, plan_environment, *init_arguments)
        )
        if initialized.returncode != 0:
            raise DeploymentCommandError("TERRAFORM_INIT_FAILED")
        planned = self._runner.run(
            self._request(
                root,
                plan_environment,
                "plan",
                "-input=false",
                "-lock=true",
                "-lock-timeout=0s",
                "-detailed-exitcode",
                f"-var-file={variables}",
                f"-out={plan_path}",
            )
        )
        if planned.returncode not in {0, 2}:
            raise DeploymentCommandError("TERRAFORM_PLAN_FAILED")
        saved_plan = self._bounded(plan_path, file_required=True)
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
            self._projection(request, shown.stdout),
        )

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
                str(plan),
            )
        )
        if applied.returncode != 0:
            raise DeploymentCommandError("TERRAFORM_APPLY_FAILED")


__all__ = (
    "ClosedSubprocessRunner",
    "CommandRequest",
    "CommandResult",
    "CommandRunner",
    "TerraformCliAdapter",
)
