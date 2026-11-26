"""Deterministic member lifecycle authorization, mutation, and privacy tests."""

from __future__ import annotations

import unittest

from infrastructure.member_directory import MemberRecord
from infrastructure.operator.member_lifecycle import (
    DirectoryControl,
    MemberDirectorySnapshot,
    MemberMutation,
    MemberMutationInterrupted,
    MemberPredecessorStale,
    MemberProviderUnavailable,
    MemberReadbackMismatch,
    MemberStateMalformed,
    PlatformMemberLifecycle,
    VerifiedMemberVisitor,
)


OWNER = "pmr1_" + "1" * 64
SECOND = "pmr1_" + "2" * 64


class Terminal:
    """Record safe prompts and make confirmation deterministic."""

    def __init__(self, confirmed: bool = True) -> None:
        self.confirmed = confirmed
        self.messages: list[str] = []

    def ask(self, prompt: str) -> str:
        self.messages.append(prompt)
        return ""

    def confirm(self, prompt: str) -> bool:
        self.messages.append(prompt)
        return self.confirmed

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.messages.extend((prompt, expected))
        return self.confirmed

    def write(self, message: str) -> None:
        self.messages.append(message)

    def pause(self, prompt: str) -> None:
        self.messages.append(prompt)


class Authorizer:
    """Represent source and Cloud Operator admission independently of Visitor."""

    def __init__(self, blockers: tuple[str, ...] = ()) -> None:
        self.blockers = blockers
        self.environments: list[str] = []

    def authorize(self, environment: str) -> tuple[str, ...]:
        self.environments.append(environment)
        return self.blockers


class Browser:
    """Return one operation-bound opaque Visitor reference exactly once per call."""

    def __init__(self, references: list[str]) -> None:
        self.references = references
        self.calls: list[tuple[str, str]] = []
        self.interrupt = False

    def verify(self, environment: str, operation: str) -> VerifiedMemberVisitor:
        self.calls.append((environment, operation))
        if self.interrupt:
            raise MemberMutationInterrupted("interrupted")
        return VerifiedMemberVisitor(
            environment,
            operation,  # type: ignore[arg-type]
            self.references.pop(0),
        )


class Clock:
    """Return increasing deterministic timestamps for persisted metadata."""

    def __init__(self) -> None:
        self.value = 1_700_000_000

    def now(self) -> int:
        self.value += 1
        return self.value


class Provider:
    """In-memory atomic provider fake with explicit failure injection."""

    def __init__(self) -> None:
        self.control: DirectoryControl | None = None
        self.members: dict[str, MemberRecord] = {}
        self.mutations: list[MemberMutation] = []
        self.failure: str | None = None

    def snapshot(
        self,
        reference: str | None,
        *,
        probe_empty: bool,
    ) -> MemberDirectorySnapshot:
        return MemberDirectorySnapshot(
            self.control,
            self.members.get(reference) if reference else None,
            bool(self.members) if probe_empty else None,
            (
                any(item != reference for item in self.members)
                if probe_empty
                else None
            ),
        )

    def read(
        self,
        environment: str,
        member_reference: str | None = None,
        *,
        probe_empty: bool = False,
    ) -> MemberDirectorySnapshot:
        self.assert_environment(environment)
        if self.failure == "unavailable":
            raise MemberProviderUnavailable("unavailable")
        if self.failure == "malformed":
            raise MemberStateMalformed("malformed")
        return self.snapshot(member_reference, probe_empty=probe_empty)

    @staticmethod
    def assert_environment(environment: str) -> None:
        if environment != "staging":
            raise AssertionError("unexpected environment")

    def mutate(self, mutation: MemberMutation) -> MemberDirectorySnapshot:
        self.assert_environment(mutation.environment)
        if self.failure == "stale":
            raise MemberPredecessorStale("stale")
        if self.failure == "interrupted":
            raise MemberMutationInterrupted("interrupted")
        if self.failure == "unavailable":
            raise MemberProviderUnavailable("unavailable")
        current = self.snapshot(
            mutation.member_reference,
            probe_empty=mutation.operation == "bootstrap-owner",
        )
        if current != mutation.predecessor:
            raise MemberPredecessorStale("stale")
        self.mutations.append(mutation)
        cursor = (self.control.mutation_cursor if self.control else 0) + 1
        created_at = self.control.created_at if self.control else mutation.timestamp
        self.control = DirectoryControl(cursor, created_at, mutation.timestamp)
        previous = self.members.get(mutation.member_reference)
        if mutation.operation == "remove":
            self.members.pop(mutation.member_reference, None)
        else:
            self.members[mutation.member_reference] = MemberRecord(
                mutation.member_reference,
                "suspended" if mutation.operation == "suspend" else "active",
                cursor,
                previous.created_at if previous else mutation.timestamp,
                mutation.timestamp,
            )
        readback = self.snapshot(mutation.member_reference, probe_empty=False)
        if self.failure == "readback":
            raise MemberReadbackMismatch("mismatch")
        return readback


def lifecycle(
    provider: Provider,
    references: list[str],
    *,
    terminal: Terminal | None = None,
    authorizer: Authorizer | None = None,
) -> tuple[PlatformMemberLifecycle, Browser, Terminal]:
    browser = Browser(references)
    selected_terminal = terminal or Terminal()
    return (
        PlatformMemberLifecycle(
            provider,
            browser,
            authorizer or Authorizer(),
            selected_terminal,
            Clock(),
        ),
        browser,
        selected_terminal,
    )


class PlatformMemberLifecycleTest(unittest.TestCase):
    """Cover the complete provider-neutral member administration journey."""

    def test_status_is_coarse_or_exact_and_never_lists_members(self) -> None:
        provider = Provider()
        service, _, _ = lifecycle(provider, [])
        coarse = service.status("staging")
        self.assertEqual(coarse.directory_state, "never-initialized")
        self.assertIsNone(coarse.member_lifecycle)

        provider.control = DirectoryControl(2, 100, 200)
        provider.members[OWNER] = MemberRecord(OWNER, "active", 1, 100, 100)
        provider.members[SECOND] = MemberRecord(SECOND, "suspended", 2, 150, 200)
        exact = service.status("staging", SECOND)
        self.assertEqual(exact.member_lifecycle, "suspended")
        self.assertEqual(exact.member_reference, SECOND)
        self.assertNotIn(OWNER, repr(exact))

    def test_bootstrap_separates_cloud_operator_and_verified_visitor(self) -> None:
        provider = Provider()
        authorizer = Authorizer()
        service, browser, terminal = lifecycle(
            provider,
            [OWNER],
            authorizer=authorizer,
        )
        result = service.bootstrap_owner("staging")
        self.assertEqual(result.outcome, "bootstrapped")
        self.assertEqual(result.member_reference, OWNER)
        self.assertEqual(result.mutation_cursor, 1)
        self.assertEqual(browser.calls, [("staging", "bootstrap-owner")])
        self.assertEqual(authorizer.environments, ["staging"])
        self.assertEqual(provider.members[OWNER].lifecycle, "active")
        transcript = "\n".join(terminal.messages)
        self.assertIn(OWNER, transcript)
        self.assertNotIn("owner@example.com", transcript)
        self.assertNotIn("accounts.google.com", transcript)

    def test_bootstrap_refuses_nonempty_and_previously_initialized_directory(self) -> None:
        provider = Provider()
        provider.members[SECOND] = MemberRecord(SECOND, "active", 1, 100, 100)
        service, _, _ = lifecycle(provider, [OWNER])
        nonempty = service.bootstrap_owner("staging")
        self.assertEqual(nonempty.outcome, "conflicting")
        self.assertEqual(nonempty.blockers, ("MEMBER_BOOTSTRAP_DIRECTORY_NOT_EMPTY",))

        provider.members.clear()
        provider.control = DirectoryControl(4, 100, 400)
        service, _, _ = lifecycle(provider, [OWNER])
        initialized = service.bootstrap_owner("staging")
        self.assertEqual(
            initialized.blockers,
            ("MEMBER_DIRECTORY_ALREADY_INITIALIZED",),
        )

    def test_exact_bootstrap_retry_is_idempotent(self) -> None:
        provider = Provider()
        provider.control = DirectoryControl(1, 100, 100)
        provider.members[OWNER] = MemberRecord(OWNER, "active", 1, 100, 100)
        service, _, _ = lifecycle(provider, [OWNER])
        result = service.bootstrap_owner("staging")
        self.assertEqual(result.outcome, "unchanged")
        self.assertEqual(provider.mutations, [])

    def test_complete_lifecycle_uses_monotonic_atomic_cursors(self) -> None:
        provider = Provider()
        service, browser, _ = lifecycle(
            provider,
            [OWNER, SECOND],
        )
        self.assertEqual(service.bootstrap_owner("staging").mutation_cursor, 1)
        self.assertEqual(service.add("staging").mutation_cursor, 2)
        self.assertEqual(service.suspend("staging", SECOND).mutation_cursor, 3)
        self.assertEqual(service.reactivate("staging", SECOND).mutation_cursor, 4)
        removed = service.remove("staging", SECOND)
        self.assertEqual(removed.mutation_cursor, 5)
        self.assertEqual(removed.member_lifecycle, "absent")
        self.assertNotIn(SECOND, provider.members)
        self.assertEqual(
            [call[1] for call in browser.calls],
            ["bootstrap-owner", "add"],
        )
        self.assertEqual(
            [mutation.predecessor.control.mutation_cursor if mutation.predecessor.control else 0
             for mutation in provider.mutations],
            [0, 1, 2, 3, 4],
        )

    def test_incompatible_transition_fails_closed_without_reopening_browser(self) -> None:
        provider = Provider()
        provider.control = DirectoryControl(2, 100, 200)
        provider.members[SECOND] = MemberRecord(SECOND, "suspended", 2, 150, 200)
        service, _, _ = lifecycle(provider, [SECOND])
        conflict = service.add("staging")
        self.assertEqual(conflict.blockers, ("MEMBER_LIFECYCLE_CONFLICT",))

        service, browser, _ = lifecycle(provider, [])
        result = service.reactivate("staging", SECOND)
        self.assertEqual(result.outcome, "reactivated")
        self.assertEqual(browser.calls, [])

    def test_decline_interruption_stale_and_provider_failures_are_explicit(self) -> None:
        cases = {
            "stale": ("stale", "MEMBER_PREDECESSOR_STALE"),
            "interrupted": ("interrupted", "MEMBER_OPERATION_INTERRUPTED"),
            "unavailable": (
                "provider-unavailable",
                "MEMBER_DIRECTORY_PROVIDER_UNAVAILABLE",
            ),
            "readback": ("conflicting", "MEMBER_READBACK_MISMATCH"),
        }
        for failure, (outcome, blocker) in cases.items():
            with self.subTest(failure=failure):
                provider = Provider()
                provider.control = DirectoryControl(1, 100, 100)
                provider.failure = failure
                service, _, _ = lifecycle(provider, [SECOND])
                result = service.add("staging")
                self.assertEqual(result.outcome, outcome)
                self.assertEqual(result.blockers, (blocker,))

        provider = Provider()
        provider.control = DirectoryControl(1, 100, 100)
        service, _, _ = lifecycle(provider, [SECOND], terminal=Terminal(False))
        declined = service.add("staging")
        self.assertEqual(declined.outcome, "cancelled")
        self.assertEqual(provider.mutations, [])

    def test_source_or_cloud_operator_blocker_prevents_browser_and_provider(self) -> None:
        provider = Provider()
        service, browser, _ = lifecycle(
            provider,
            [OWNER],
            authorizer=Authorizer(("SOURCE_NOT_CURRENT",)),
        )
        result = service.bootstrap_owner("staging")
        self.assertEqual(result.blockers, ("SOURCE_NOT_CURRENT",))
        self.assertEqual(browser.calls, [])
        self.assertEqual(provider.mutations, [])


if __name__ == "__main__":
    unittest.main()
