"""Local, path-bounded filesystem implementation for operator state."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile


class LocalFilesystem:
    """Keep private generated operator state separate from committed source."""

    def __init__(self, project_root: Path, state_root: Path) -> None:
        self._project_root = project_root.resolve()
        self._state_root = state_root.resolve()
        self._state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._state_root.chmod(0o700)

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
