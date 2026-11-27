"""Shallow CLI coverage for the Platform Member lifecycle commands."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import unittest

from infrastructure.operator.cli import _main
from infrastructure.operator.member_lifecycle import MemberLifecycleResult


REFERENCE = "pmr1_" + "c" * 64


class Members:
    """Record CLI dispatch while returning one least-data service result."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def status(self, environment: str, reference: str | None = None) -> MemberLifecycleResult:
        self.calls.append(("status", environment, reference))
        return MemberLifecycleResult(
            "read",
            "ready",
            reference,
            "active" if reference else None,
            7,
        )

    def identify(self, environment: str) -> MemberLifecycleResult:
        self.calls.append(("identify", environment, None))
        return MemberLifecycleResult("identified", "ready", REFERENCE, "active", 7)

    def bootstrap_owner(self, environment: str) -> MemberLifecycleResult:
        self.calls.append(("bootstrap-owner", environment, None))
        return MemberLifecycleResult("bootstrapped", "ready", REFERENCE, "active", 1)

    def add(self, environment: str) -> MemberLifecycleResult:
        self.calls.append(("add", environment, None))
        return MemberLifecycleResult("added", "ready", REFERENCE, "active", 2)

    def suspend(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("suspend", environment, reference))
        return MemberLifecycleResult("suspended", "ready", reference, "suspended", 3)

    def reactivate(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("reactivate", environment, reference))
        return MemberLifecycleResult("reactivated", "ready", reference, "active", 4)

    def remove(self, environment: str, reference: str) -> MemberLifecycleResult:
        self.calls.append(("remove", environment, reference))
        return MemberLifecycleResult("removed", "ready", reference, "absent", 5)


class MemberCliTest(unittest.TestCase):
    """Prove Make-facing names remain thin dispatch over the deep service."""

    def invoke(self, operation: str, *, reference: bool = False) -> tuple[int, dict[str, object], Members, str]:
        members = Members()
        arguments = [
            operation,
            "--environment",
            "staging",
            "--state-directory",
            "/private/operator",
            "--source-authority",
            "candidate",
        ]
        if reference:
            arguments.extend(("--member-reference", REFERENCE))
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = _main(
                arguments,
                member_factory=lambda state, source: members,  # type: ignore[arg-type]
            )
        return code, json.loads(stdout.getvalue()), members, stderr.getvalue()

    def test_all_seven_commands_dispatch_without_identity_input(self) -> None:
        expected = {
            "platform-member-status": ("status", False),
            "platform-member-identify": ("identify", False),
            "platform-member-bootstrap-owner": ("bootstrap-owner", False),
            "platform-member-add": ("add", False),
            "platform-member-suspend": ("suspend", True),
            "platform-member-reactivate": ("reactivate", True),
            "platform-member-remove": ("remove", True),
        }
        for operation, (method, uses_reference) in expected.items():
            with self.subTest(operation=operation):
                code, result, members, stderr = self.invoke(
                    operation,
                    reference=uses_reference,
                )
                self.assertEqual(code, 0)
                self.assertEqual(members.calls[0][0], method)
                self.assertEqual(result["source_authority"], "candidate")
                self.assertNotIn("email", stdout := json.dumps(result))
                self.assertNotIn("subject", stdout)
                self.assertNotIn("issuer", stdout)
                self.assertIn("fixture selected: none", stderr)

    def test_single_member_status_passes_only_the_requested_reference(self) -> None:
        code, result, members, _ = self.invoke(
            "platform-member-status",
            reference=True,
        )
        self.assertEqual(code, 0)
        self.assertEqual(members.calls, [("status", "staging", REFERENCE)])
        self.assertEqual(result["member_reference"], REFERENCE)


if __name__ == "__main__":
    unittest.main()
