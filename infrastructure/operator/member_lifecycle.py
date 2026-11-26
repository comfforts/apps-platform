"""Platform Member Directory administration behind one bounded service.

The module owns the complete provider-neutral member lifecycle.  It deliberately
does not share the Shared Edge's read-only lookup interface: operator mutations
require a verified Cloud Operator boundary, a one-use browser-derived Visitor
reference, an exact remote predecessor, explicit confirmation, an atomic
control/member update, and exact remote readback.

Only opaque environment-scoped member references cross this interface.  Google
issuer, subject, email, browser state, provider payloads, and member enumeration
remain outside results, prompts, diagnostics, and retained operator state.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Protocol

from infrastructure.member_directory import MemberRecord
from infrastructure.operator._interfaces import OperatorTerminal


_MEMBER_REFERENCE = re.compile(r"pmr1_[0-9a-f]{64}")
_ENVIRONMENT = re.compile(r"[a-z][a-z0-9-]{1,31}")
MemberOperation = Literal["bootstrap-owner", "add", "suspend", "reactivate", "remove"]


class MemberProviderUnavailable(RuntimeError):
    """The remote directory could not complete a bounded provider operation."""


class MemberStateMalformed(RuntimeError):
    """Remote control or member state violates its exact private contract."""


class MemberPredecessorStale(RuntimeError):
    """The remote predecessor changed after review and before mutation."""


class MemberMutationInterrupted(RuntimeError):
    """A provider operation ended without a trustworthy terminal readback."""


class MemberReadbackMismatch(RuntimeError):
    """Provider readback did not equal the exact reviewed successor."""


@dataclass(frozen=True, slots=True)
class DirectoryControl:
    """Exact retained directory-control document used for mutation ordering."""

    mutation_cursor: int
    created_at: int
    updated_at: int

    def __post_init__(self) -> None:
        """Reject non-initialized, non-monotonic, or malformed control state."""

        if (
            isinstance(self.mutation_cursor, bool)
            or not isinstance(self.mutation_cursor, int)
            or self.mutation_cursor < 1
            or isinstance(self.created_at, bool)
            or not isinstance(self.created_at, int)
            or self.created_at < 1
            or isinstance(self.updated_at, bool)
            or not isinstance(self.updated_at, int)
            or self.updated_at < self.created_at
        ):
            raise ValueError("invalid directory control")


@dataclass(frozen=True, slots=True)
class MemberDirectorySnapshot:
    """Bounded remote state for one optional opaque member reference.

    ``members_present`` is populated only for the bootstrap emptiness probe.  It
    is a boolean and never exposes a count, identity, reference, or listing.
    """

    control: DirectoryControl | None
    member: MemberRecord | None = None
    members_present: bool | None = None
    other_members_present: bool | None = None

    def __post_init__(self) -> None:
        """Validate cross-document cursor and initialization invariants."""

        if self.member is not None and self.control is None:
            raise ValueError("member exists without directory control")
        if (
            self.member is not None
            and self.control is not None
            and self.member.mutation_cursor > self.control.mutation_cursor
        ):
            raise ValueError("member cursor exceeds directory cursor")
        if self.members_present not in {None, False, True}:
            raise ValueError("invalid member-presence projection")
        if self.other_members_present not in {None, False, True}:
            raise ValueError("invalid other-member projection")
        if self.other_members_present is True and self.members_present is not True:
            raise ValueError("other-member projection is inconsistent")


@dataclass(frozen=True, slots=True)
class VerifiedMemberVisitor:
    """One-use browser result containing only an opaque member reference."""

    environment: str
    operation: MemberOperation
    member_reference: str

    def __post_init__(self) -> None:
        """Validate the exact browser binding without accepting identity claims."""

        if _ENVIRONMENT.fullmatch(self.environment) is None:
            raise ValueError("invalid verified visitor environment")
        if self.operation not in {
            "bootstrap-owner",
            "add",
            "suspend",
            "reactivate",
            "remove",
        }:
            raise ValueError("invalid verified visitor operation")
        if _MEMBER_REFERENCE.fullmatch(self.member_reference) is None:
            raise ValueError("invalid verified visitor member reference")


@dataclass(frozen=True, slots=True)
class MemberMutation:
    """Exact reviewed transaction request bound to its remote predecessor."""

    environment: str
    operation: MemberOperation
    member_reference: str
    predecessor: MemberDirectorySnapshot
    timestamp: int

    def __post_init__(self) -> None:
        """Reject unbounded mutation input before it reaches a provider."""

        if _ENVIRONMENT.fullmatch(self.environment) is None:
            raise ValueError("invalid member mutation environment")
        if _MEMBER_REFERENCE.fullmatch(self.member_reference) is None:
            raise ValueError("invalid member mutation reference")
        if not isinstance(self.predecessor, MemberDirectorySnapshot):
            raise TypeError("member mutation predecessor is not validated")
        if (
            isinstance(self.timestamp, bool)
            or not isinstance(self.timestamp, int)
            or self.timestamp < 1
        ):
            raise ValueError("invalid member mutation timestamp")


@dataclass(frozen=True, slots=True)
class MemberLifecycleResult:
    """Least-data result shared by status and mutation entry points."""

    outcome: str
    directory_state: Literal["never-initialized", "ready", "unreadable"]
    member_reference: str | None = None
    member_lifecycle: Literal["absent", "active", "suspended"] | None = None
    mutation_cursor: int | None = None
    blockers: tuple[str, ...] = ()


class MemberDirectoryProvider(Protocol):
    """Remote authority for bounded reads and one atomic member transaction."""

    def read(
        self,
        environment: str,
        member_reference: str | None = None,
        *,
        probe_empty: bool = False,
    ) -> MemberDirectorySnapshot:
        """Read control plus one exact member, optionally probing only emptiness."""

    def mutate(self, mutation: MemberMutation) -> MemberDirectorySnapshot:
        """Apply one compare-and-set transaction and return exact readback."""


class MemberVisitorVerifier(Protocol):
    """One-use browser seam that returns no raw identity material."""

    def verify(
        self,
        environment: str,
        operation: MemberOperation,
    ) -> VerifiedMemberVisitor:
        """Return the visitor reference bound to the environment and operation."""


class MemberOperationAuthorizer(Protocol):
    """Verify source and Cloud Operator authority before remote directory access."""

    def authorize(self, environment: str) -> tuple[str, ...]:
        """Return stable blockers or an empty tuple for the selected environment."""


class MemberClock(Protocol):
    """Supply integer UTC seconds for persisted private operation metadata."""

    def now(self) -> int:
        """Return the current positive Unix timestamp."""


class PlatformMemberLifecycle:
    """Administer one environment directory without exposing provider machinery.

    The public methods form the complete lifecycle.  They centralize source and
    Cloud Operator authorization, browser binding, transition validation,
    confirmation, compare-and-set mutation, idempotency, and exact readback so
    the CLI and Make targets remain shallow.
    """

    def __init__(
        self,
        provider: MemberDirectoryProvider,
        visitor: MemberVisitorVerifier,
        authorizer: MemberOperationAuthorizer,
        terminal: OperatorTerminal,
        clock: MemberClock,
    ) -> None:
        """Bind explicit dependencies without reading local or remote state."""

        self._provider = provider
        self._visitor = visitor
        self._authorizer = authorizer
        self._terminal = terminal
        self._clock = clock

    @staticmethod
    def _validate_environment(environment: str) -> None:
        """Reject invalid environment input before authority or provider access."""

        if not isinstance(environment, str) or _ENVIRONMENT.fullmatch(environment) is None:
            raise ValueError("invalid member environment")

    @staticmethod
    def _validate_reference(member_reference: str) -> None:
        """Reject raw identities and malformed opaque references at the boundary."""

        if (
            not isinstance(member_reference, str)
            or _MEMBER_REFERENCE.fullmatch(member_reference) is None
        ):
            raise ValueError("invalid member reference")

    @staticmethod
    def _state(snapshot: MemberDirectorySnapshot) -> str:
        """Project coarse directory state without member enumeration."""

        return "never-initialized" if snapshot.control is None else "ready"

    @staticmethod
    def _lifecycle(snapshot: MemberDirectorySnapshot) -> str:
        """Project only the selected member's lifecycle or absence."""

        return "absent" if snapshot.member is None else snapshot.member.lifecycle

    def _authorized(self, environment: str) -> MemberLifecycleResult | None:
        """Apply source/operator authorization before every provider operation."""

        blockers = self._authorizer.authorize(environment)
        if blockers:
            return MemberLifecycleResult("blocked", "unreadable", blockers=blockers)
        return None

    def _read(
        self,
        environment: str,
        member_reference: str | None = None,
        *,
        probe_empty: bool = False,
    ) -> MemberDirectorySnapshot | MemberLifecycleResult:
        """Normalize provider failure classes into stable least-data results."""

        try:
            return self._provider.read(
                environment,
                member_reference,
                probe_empty=probe_empty,
            )
        except MemberStateMalformed:
            return MemberLifecycleResult(
                "malformed",
                "unreadable",
                member_reference=member_reference,
                blockers=("MEMBER_DIRECTORY_MALFORMED",),
            )
        except MemberProviderUnavailable:
            return MemberLifecycleResult(
                "provider-unavailable",
                "unreadable",
                member_reference=member_reference,
                blockers=("MEMBER_DIRECTORY_PROVIDER_UNAVAILABLE",),
            )

    def status(
        self,
        environment: str,
        member_reference: str | None = None,
    ) -> MemberLifecycleResult:
        """Read coarse directory state or one explicitly requested member only."""

        self._validate_environment(environment)
        if member_reference is not None:
            self._validate_reference(member_reference)
        blocked = self._authorized(environment)
        if blocked is not None:
            return blocked
        snapshot = self._read(environment, member_reference)
        if isinstance(snapshot, MemberLifecycleResult):
            return snapshot
        return MemberLifecycleResult(
            "read",
            self._state(snapshot),  # type: ignore[arg-type]
            member_reference=member_reference,
            member_lifecycle=(
                self._lifecycle(snapshot) if member_reference is not None else None
            ),  # type: ignore[arg-type]
            mutation_cursor=(
                snapshot.control.mutation_cursor if snapshot.control is not None else None
            ),
        )

    def owner_only_baseline(
        self,
        environment: str,
        owner_member_reference: str,
    ) -> MemberLifecycleResult:
        """Verify one reviewed active owner and no other remote member record.

        Qualification uses this bounded projection before and after its temporary
        second-member exercise.  The provider returns only booleans for member
        presence, so the check neither enumerates the directory nor exposes an
        identity or an unreviewed member reference.
        """

        self._validate_environment(environment)
        self._validate_reference(owner_member_reference)
        blocked = self._authorized(environment)
        if blocked is not None:
            return blocked
        snapshot = self._read(
            environment,
            owner_member_reference,
            probe_empty=True,
        )
        if isinstance(snapshot, MemberLifecycleResult):
            return snapshot
        baseline_ready = (
            snapshot.control is not None
            and snapshot.member is not None
            and snapshot.member.lifecycle == "active"
            and snapshot.members_present is True
            and snapshot.other_members_present is False
        )
        if not baseline_ready:
            return MemberLifecycleResult(
                "conflicting",
                self._state(snapshot),
                owner_member_reference,
                self._lifecycle(snapshot),
                snapshot.control.mutation_cursor if snapshot.control else None,
                ("MEMBER_OWNER_BASELINE_MISMATCH",),
            )
        return MemberLifecycleResult(
            "baseline-ready",
            "ready",
            owner_member_reference,
            "active",
            snapshot.control.mutation_cursor,
        )

    @staticmethod
    def _transition_blocker(
        operation: MemberOperation,
        snapshot: MemberDirectorySnapshot,
    ) -> str | None:
        """Return a stable blocker for an incompatible current lifecycle."""

        lifecycle = "absent" if snapshot.member is None else snapshot.member.lifecycle
        allowed = {
            "add": {"absent", "active"},
            "suspend": {"active", "suspended"},
            "reactivate": {"suspended", "active"},
            "remove": {"active", "suspended", "absent"},
        }
        if operation == "bootstrap-owner":
            return None
        return None if lifecycle in allowed[operation] else "MEMBER_LIFECYCLE_CONFLICT"

    @staticmethod
    def _already_desired(
        operation: MemberOperation,
        snapshot: MemberDirectorySnapshot,
    ) -> bool:
        """Recognize only an exact terminal state that makes retry idempotent."""

        lifecycle = "absent" if snapshot.member is None else snapshot.member.lifecycle
        if operation == "bootstrap-owner":
            return (
                snapshot.control is not None
                and snapshot.control.mutation_cursor == 1
                and snapshot.member is not None
                and snapshot.member.lifecycle == "active"
                and snapshot.member.mutation_cursor == 1
                and snapshot.member.created_at == snapshot.control.created_at
                and snapshot.member.updated_at == snapshot.control.updated_at
                and snapshot.members_present is True
                and snapshot.other_members_present is False
            )
        return lifecycle == {
            "add": "active",
            "suspend": "suspended",
            "reactivate": "active",
            "remove": "absent",
        }[operation]

    def _confirm(
        self,
        environment: str,
        operation: MemberOperation,
        member_reference: str,
        snapshot: MemberDirectorySnapshot,
    ) -> bool:
        """Display the exact non-sensitive predecessor and requested successor."""

        cursor = snapshot.control.mutation_cursor if snapshot.control else 0
        current = self._lifecycle(snapshot)
        successor = {
            "bootstrap-owner": "active initial owner",
            "add": "active member",
            "suspend": "suspended member",
            "reactivate": "active member",
            "remove": "absent member",
        }[operation]
        self._terminal.write(
            "Reviewed Platform Member Directory action:\n"
            f"  Environment: {environment}\n"
            f"  Operation: {operation}\n"
            f"  Member reference: {member_reference}\n"
            f"  Remote predecessor cursor: {cursor}\n"
            f"  Current member state: {current}\n"
            f"  Requested member state: {successor}"
        )
        if operation == "remove":
            expected = (
                f"REMOVE {environment} MEMBER {member_reference} CURSOR {cursor}"
            )
            self._terminal.write(
                "Removal deletes this member document while retaining initialized "
                "directory control. Type the exact phrase shown by the next prompt."
            )
            return self._terminal.confirm_exact(
                f"Type '{expected}' to remove this platform member: ",
                expected,
            )
        return self._terminal.confirm(
            "Apply this exact remote member-directory action? [y/N] "
        )

    def _operation(
        self,
        environment: str,
        operation: MemberOperation,
        member_reference: str | None = None,
    ) -> MemberLifecycleResult:
        """Run one authorized, browser-bound, compare-and-set lifecycle change."""

        self._validate_environment(environment)
        if member_reference is not None:
            self._validate_reference(member_reference)
        blocked = self._authorized(environment)
        if blocked is not None:
            return blocked

        target = member_reference
        if target is None:
            try:
                verified = self._visitor.verify(environment, operation)
            except (KeyboardInterrupt, MemberMutationInterrupted):
                return MemberLifecycleResult(
                    "interrupted",
                    "unreadable",
                    blockers=("MEMBER_OPERATION_INTERRUPTED",),
                )
            except Exception:
                return MemberLifecycleResult(
                    "blocked",
                    "unreadable",
                    blockers=("MEMBER_VISITOR_VERIFICATION_FAILED",),
                )
            if verified.environment != environment or verified.operation != operation:
                return MemberLifecycleResult(
                    "conflicting",
                    "unreadable",
                    blockers=("MEMBER_VISITOR_BINDING_MISMATCH",),
                )
            target = verified.member_reference

        snapshot = self._read(
            environment,
            target,
            probe_empty=operation == "bootstrap-owner",
        )
        if isinstance(snapshot, MemberLifecycleResult):
            return snapshot
        if operation == "bootstrap-owner":
            if snapshot.control is not None:
                if self._already_desired(operation, snapshot):
                    return MemberLifecycleResult(
                        "unchanged",
                        "ready",
                        target,
                        "active",
                        snapshot.control.mutation_cursor,
                    )
                return MemberLifecycleResult(
                    "conflicting",
                    "ready",
                    target,
                    self._lifecycle(snapshot),  # type: ignore[arg-type]
                    snapshot.control.mutation_cursor,
                    ("MEMBER_DIRECTORY_ALREADY_INITIALIZED",),
                )
            if snapshot.members_present:
                return MemberLifecycleResult(
                    "conflicting",
                    "never-initialized",
                    target,
                    self._lifecycle(snapshot),  # type: ignore[arg-type]
                    blockers=("MEMBER_BOOTSTRAP_DIRECTORY_NOT_EMPTY",),
                )
        else:
            if snapshot.control is None:
                return MemberLifecycleResult(
                    "conflicting",
                    "never-initialized",
                    target,
                    self._lifecycle(snapshot),  # type: ignore[arg-type]
                    blockers=("MEMBER_DIRECTORY_NOT_INITIALIZED",),
                )
            transition_blocker = self._transition_blocker(operation, snapshot)
            if transition_blocker is not None:
                return MemberLifecycleResult(
                    "conflicting",
                    "ready",
                    target,
                    self._lifecycle(snapshot),  # type: ignore[arg-type]
                    snapshot.control.mutation_cursor,
                    (transition_blocker,),
                )
            if self._already_desired(operation, snapshot):
                return MemberLifecycleResult(
                    "unchanged",
                    "ready",
                    target,
                    self._lifecycle(snapshot),  # type: ignore[arg-type]
                    snapshot.control.mutation_cursor,
                )

        try:
            if not self._confirm(environment, operation, target, snapshot):
                return MemberLifecycleResult(
                    "cancelled",
                    self._state(snapshot),  # type: ignore[arg-type]
                    target,
                    self._lifecycle(snapshot),  # type: ignore[arg-type]
                    snapshot.control.mutation_cursor if snapshot.control else None,
                    ("MEMBER_ACTION_NOT_CONFIRMED",),
                )
            timestamp = self._clock.now()
            successor = self._provider.mutate(
                MemberMutation(
                    environment,
                    operation,
                    target,
                    snapshot,
                    timestamp,
                )
            )
        except (KeyboardInterrupt, MemberMutationInterrupted):
            return MemberLifecycleResult(
                "interrupted",
                self._state(snapshot),  # type: ignore[arg-type]
                target,
                self._lifecycle(snapshot),  # type: ignore[arg-type]
                snapshot.control.mutation_cursor if snapshot.control else None,
                ("MEMBER_OPERATION_INTERRUPTED",),
            )
        except MemberPredecessorStale:
            return MemberLifecycleResult(
                "stale",
                "unreadable",
                target,
                blockers=("MEMBER_PREDECESSOR_STALE",),
            )
        except MemberStateMalformed:
            return MemberLifecycleResult(
                "malformed",
                "unreadable",
                target,
                blockers=("MEMBER_DIRECTORY_MALFORMED",),
            )
        except MemberReadbackMismatch:
            return MemberLifecycleResult(
                "conflicting",
                "unreadable",
                target,
                blockers=("MEMBER_READBACK_MISMATCH",),
            )
        except MemberProviderUnavailable:
            return MemberLifecycleResult(
                "provider-unavailable",
                "unreadable",
                target,
                blockers=("MEMBER_DIRECTORY_PROVIDER_UNAVAILABLE",),
            )

        return MemberLifecycleResult(
            {
                "bootstrap-owner": "bootstrapped",
                "add": "added",
                "suspend": "suspended",
                "reactivate": "reactivated",
                "remove": "removed",
            }[operation],
            self._state(successor),  # type: ignore[arg-type]
            target,
            self._lifecycle(successor),  # type: ignore[arg-type]
            successor.control.mutation_cursor if successor.control else None,
        )

    def bootstrap_owner(self, environment: str) -> MemberLifecycleResult:
        """Create the one exact first active member in a never-used directory."""

        return self._operation(environment, "bootstrap-owner")

    def add(self, environment: str) -> MemberLifecycleResult:
        """Add the one Google Visitor verified by the current browser flow."""

        return self._operation(environment, "add")

    def suspend(self, environment: str, member_reference: str) -> MemberLifecycleResult:
        """Suspend one exact verified member without removing its record."""

        return self._operation(environment, "suspend", member_reference)

    def reactivate(self, environment: str, member_reference: str) -> MemberLifecycleResult:
        """Reactivate one exact verified suspended member."""

        return self._operation(environment, "reactivate", member_reference)

    def remove(self, environment: str, member_reference: str) -> MemberLifecycleResult:
        """Delete one exact verified member while retaining initialized control."""

        return self._operation(environment, "remove", member_reference)


__all__ = (
    "DirectoryControl",
    "MemberClock",
    "MemberDirectoryProvider",
    "MemberDirectorySnapshot",
    "MemberLifecycleResult",
    "MemberMutation",
    "MemberMutationInterrupted",
    "MemberOperation",
    "MemberOperationAuthorizer",
    "MemberPredecessorStale",
    "MemberProviderUnavailable",
    "MemberReadbackMismatch",
    "MemberStateMalformed",
    "MemberVisitorVerifier",
    "PlatformMemberLifecycle",
    "VerifiedMemberVisitor",
)
