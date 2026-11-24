"""Private exact command diagnostics shared by operator adapters."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat


_NAME = re.compile(r"[a-z][a-z0-9-]{1,63}")


def _private_directory(state_root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise ValueError("private diagnostic directory is not bounded")
    path.mkdir(mode=0o700, exist_ok=True)
    resolved = path.resolve()
    if (
        not resolved.is_dir()
        or resolved == state_root
        or state_root not in resolved.parents
    ):
        raise ValueError("private diagnostic directory escapes operator state")
    resolved.chmod(0o700)
    return resolved


def _private_file(path: Path, contents: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(contents)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def capture_private_command_failure(
    private_state_root: Path | None,
    *,
    environment: str,
    operation: str,
    phase: str,
    stdout: bytes,
    stderr: bytes,
) -> dict[str, str]:
    """Persist raw failed-command streams only inside bounded private state."""

    if private_state_root is None:
        return {}
    if any(_NAME.fullmatch(value) is None for value in (environment, operation, phase)):
        return {"diagnostic_capture": "failed"}
    try:
        state_root = private_state_root.resolve()
        if (
            private_state_root.is_symlink()
            or not state_root.is_dir()
            or stat.S_IMODE(state_root.stat().st_mode) & 0o077
        ):
            raise ValueError("private operator state root is unavailable")
        captured_at = datetime.now(UTC)
        digest = hashlib.sha256()
        digest.update(len(stdout).to_bytes(8, "big"))
        digest.update(stdout)
        digest.update(len(stderr).to_bytes(8, "big"))
        digest.update(stderr)
        raw_digest = digest.hexdigest()
        diagnostic_digest = f"sha256:{raw_digest}"
        diagnostics = _private_directory(state_root, state_root / "diagnostics")
        environment_root = _private_directory(
            state_root,
            diagnostics / environment,
        )
        event_name = (
            captured_at.strftime("%Y%m%dT%H%M%S.%fZ")
            + f"-{operation}-{phase}-{raw_digest[:12]}"
        )
        event_root = environment_root / event_name
        event_root.mkdir(mode=0o700)
        event_root.chmod(0o700)

        stdout_path = event_root / "stdout.log"
        stderr_path = event_root / "stderr.log"
        _private_file(stdout_path, stdout)
        _private_file(stderr_path, stderr)
        manifest = {
            "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
            "diagnostic_digest": diagnostic_digest,
            "diagnostic_version": 1,
            "environment": environment,
            "operation": operation,
            "phase": phase,
            "stderr": {
                "bytes": len(stderr),
                "filename": stderr_path.name,
                "sha256": "sha256:" + hashlib.sha256(stderr).hexdigest(),
            },
            "stdout": {
                "bytes": len(stdout),
                "filename": stdout_path.name,
                "sha256": "sha256:" + hashlib.sha256(stdout).hexdigest(),
            },
        }
        _private_file(
            event_root / "manifest.json",
            (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8"),
        )
        return {
            "diagnostic_digest": diagnostic_digest,
            "diagnostic_path": str(stderr_path),
            "diagnostic_stdout_path": str(stdout_path),
        }
    except (OSError, RuntimeError, ValueError):
        return {"diagnostic_capture": "failed"}


__all__ = ["capture_private_command_failure"]
