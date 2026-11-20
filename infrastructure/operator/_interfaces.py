"""Injected side-effect boundaries for the lifecycle core."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class GitSnapshot:
    """Read-only source facts required before lifecycle preparation."""

    repository: str
    revision: str
    branch: str
    clean: bool
    main_revision: str
    origin_main_revision: str
    upstream_branch: str | None = None
    upstream_revision: str | None = None
    origin_main_ancestor: bool = False


@dataclass(frozen=True, slots=True)
class DiscoverySnapshot:
    """Bounded non-secret facts and fail-closed blockers from one adapter."""

    name: str
    facts: tuple[tuple[str, str], ...]
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PrepareResult:
    """Result of read-only preparation and its separate approval decision."""

    outcome: str
    complete: bool
    approved: bool
    specification: dict[str, Any] | None
    specification_digest: str | None
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StageExecution:
    """One deterministic adapter result for a specification stage."""

    outcome: str
    outputs: tuple[tuple[str, str], ...] = ()
    plan_digest: str | None = None
    manual_acknowledgement: str = "not-required"
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StageContext:
    """Exact approved scope supplied to one injected stage execution."""

    environment: str
    source_revision: str
    specification_digest: str
    stage: Mapping[str, object]
    inputs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class StatusResult:
    """One read-only lifecycle reconciliation result."""

    environment_status: dict[str, Any]
    conflicts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result of deterministic stage orchestration against an injected executor."""

    outcome: str
    journal: dict[str, Any] | None
    journal_digest: str | None
    status: StatusResult
    blockers: tuple[str, ...] = ()


class OperatorInterrupted(Exception):
    """Signal an ordinary process interruption before the current stage closes."""


class GitAdapter(Protocol):
    def inspect(self) -> GitSnapshot: ...


class DiscoveryAdapter(Protocol):
    def inspect(self, profile: dict[str, object]) -> DiscoverySnapshot: ...


class TerraformAdapter(Protocol):
    def inspect(self) -> DiscoverySnapshot: ...


class TerminalAdapter(Protocol):
    def confirm(self, prompt: str) -> bool: ...

    def write(self, message: str) -> None: ...


class FilesystemAdapter(Protocol):
    def project_path(self, relative_path: str) -> Path: ...

    def state_path(self, relative_path: str) -> Path: ...

    def read_state(self, relative_path: str) -> bytes | None: ...

    def write_state(
        self,
        relative_path: str,
        contents: bytes,
        *,
        replace: bool,
    ) -> None: ...


class ClockAdapter(Protocol):
    def now(self) -> str: ...


class StageExecutor(Protocol):
    def execute(self, context: StageContext) -> StageExecution: ...


@dataclass(frozen=True, slots=True)
class OperatorAdapters:
    """All ambient and side-effecting dependencies of the lifecycle core."""

    git: GitAdapter
    github: DiscoveryAdapter
    gcp: DiscoveryAdapter
    terraform: TerraformAdapter
    dns: DiscoveryAdapter
    terminal: TerminalAdapter
    filesystem: FilesystemAdapter
    clock: ClockAdapter
    executor: StageExecutor | None = None
