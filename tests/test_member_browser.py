"""One-use browser member-reference binding without identity export."""

from __future__ import annotations

from dataclasses import dataclass
import unittest

from infrastructure.operator.member_browser import (
    LoopbackMemberVisitorVerifier,
)
from infrastructure.operator.member_lifecycle import (
    MemberMutationInterrupted,
    VerifiedMemberVisitor,
)


REFERENCE = "pmr1_" + "a" * 64
CHALLENGE = "b" * 64


class Terminal:
    """Deterministic terminal that records browser guidance."""

    def __init__(self, confirmed: bool = True) -> None:
        self.confirmed = confirmed
        self.messages: list[str] = []

    def ask(self, prompt: str) -> str:
        return ""

    def confirm(self, prompt: str) -> bool:
        self.messages.append(prompt)
        return self.confirmed

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        return False

    def write(self, message: str) -> None:
        self.messages.append(message)

    def pause(self, prompt: str) -> None:
        self.messages.append(prompt)


class Launcher:
    """Capture the exact reviewed platform URL instead of opening a browser."""

    def __init__(self, opened: bool = True) -> None:
        self.opened = opened
        self.urls: list[str] = []

    def open(self, url: str) -> bool:
        self.urls.append(url)
        return self.opened


@dataclass
class Callback:
    """Return a predetermined least-data callback result."""

    visitor: VerifiedMemberVisitor | None
    port: int = 43123
    closed: bool = False

    def wait(self, timeout_seconds: float) -> VerifiedMemberVisitor | None:
        self.timeout = timeout_seconds
        return self.visitor

    def close(self) -> None:
        self.closed = True


class MemberBrowserTest(unittest.TestCase):
    """Verify confirmation, URL binding, one-use callback, and privacy."""

    def test_verifier_binds_environment_operation_and_loopback_challenge(self) -> None:
        terminal = Terminal()
        launcher = Launcher()
        callback = Callback(VerifiedMemberVisitor("staging", "add", REFERENCE))
        verifier = LoopbackMemberVisitorVerifier(
            launcher,
            terminal,
            {"staging": "https://apps-staging.comfforts.com"},
            challenge_source=lambda: CHALLENGE,
            callback_factory=lambda challenge, environment, operation: callback,
        )
        visitor = verifier.verify("staging", "add")
        self.assertEqual(visitor.member_reference, REFERENCE)
        self.assertTrue(callback.closed)
        self.assertEqual(len(launcher.urls), 1)
        self.assertIn("apps-staging.comfforts.com/_platform/logout", launcher.urls[0])
        self.assertIn("callback_port%3D43123", launcher.urls[0])
        self.assertIn(CHALLENGE, launcher.urls[0])
        transcript = "\n".join(terminal.messages + launcher.urls)
        self.assertNotIn("@", transcript)
        self.assertNotIn("accounts.google.com", transcript)
        self.assertNotIn(REFERENCE, transcript)

    def test_declined_or_failed_browser_never_waits_for_identity(self) -> None:
        callback = Callback(VerifiedMemberVisitor("staging", "add", REFERENCE))
        verifier = LoopbackMemberVisitorVerifier(
            Launcher(),
            Terminal(False),
            {"staging": "https://apps-staging.comfforts.com"},
            challenge_source=lambda: CHALLENGE,
            callback_factory=lambda challenge, environment, operation: callback,
        )
        with self.assertRaises(MemberMutationInterrupted):
            verifier.verify("staging", "add")
        self.assertFalse(callback.closed)

        failed = Callback(None)
        verifier = LoopbackMemberVisitorVerifier(
            Launcher(False),
            Terminal(),
            {"staging": "https://apps-staging.comfforts.com"},
            challenge_source=lambda: CHALLENGE,
            callback_factory=lambda challenge, environment, operation: failed,
        )
        with self.assertRaises(MemberMutationInterrupted):
            verifier.verify("staging", "add")
        self.assertTrue(failed.closed)

if __name__ == "__main__":
    unittest.main()
