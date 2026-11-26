"""Browser-assisted live qualification without cookie or identity export."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

from infrastructure.operator.live_qualification import (
    LoopbackBrowserQualification,
    SystemBrowserLauncher,
)


@dataclass
class Terminal:
    confirmations: list[bool] = field(default_factory=lambda: [True, True, True])
    messages: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    def write(self, message: str) -> None:
        self.messages.append(message)

    def confirm(self, prompt: str) -> bool:
        self.prompts.append(prompt)
        self.events.append("confirm")
        return self.confirmations.pop(0)


@dataclass
class CallbackLauncher:
    terminal: Terminal
    urls: list[str] = field(default_factory=list)

    def open(self, url: str) -> bool:
        self.urls.append(url)
        self.terminal.events.append("open")
        return True


@dataclass
class CallbackSequence:
    application_ids: list[str]
    selected_port: int = 43000

    def __call__(self, challenge: str):  # type: ignore[no-untyped-def]
        del challenge
        expected = self.application_ids.pop(0)
        selected_port = self.selected_port

        @dataclass
        class Callback:
            @property
            def port(self) -> int:
                return selected_port

            def wait(self, timeout_seconds: float) -> str | None:
                del timeout_seconds
                return expected

            def close(self) -> None:
                return None

        return Callback()


class LiveQualificationBrowserTest(unittest.TestCase):
    def test_three_approved_steps_clear_authenticate_restrict_and_logout(self) -> None:
        terminal = Terminal()
        launcher = CallbackLauncher(terminal)
        qualification = LoopbackBrowserQualification(
            launcher,
            terminal,
            login_timeout_seconds=2,
            callback_timeout_seconds=2,
            challenge_source=lambda: "a" * 64,
            callback_factory=CallbackSequence(
                ["fixture-authenticated", "fixture-restricted", "fixture-public"]
            ),
        )

        result = qualification.verify()

        self.assertTrue(result.authenticated)
        self.assertTrue(result.restricted)
        self.assertTrue(result.logout)
        self.assertIsNone(result.blocker)
        self.assertEqual(len(launcher.urls), 3)
        self.assertEqual(
            terminal.events,
            ["confirm", "open", "confirm", "open", "confirm", "open"],
        )
        self.assertTrue(all("[y/N]" in prompt for prompt in terminal.prompts))
        self.assertTrue(any("1/3" in message for message in terminal.messages))
        self.assertTrue(any("2/3" in message for message in terminal.messages))
        self.assertTrue(any("3/3" in message for message in terminal.messages))

        first = urlsplit(launcher.urls[0])
        self.assertEqual(first.path, "/_platform/logout")
        first_return = unquote(parse_qs(first.query)["return_to"][0])
        self.assertTrue(first_return.startswith("/fixture-authenticated/qualification/browser?"))
        self.assertEqual(
            urlsplit(launcher.urls[1]).path,
            "/fixture-restricted/qualification/browser",
        )
        third = urlsplit(launcher.urls[2])
        self.assertEqual(third.path, "/_platform/logout")
        third_return = unquote(parse_qs(third.query)["return_to"][0])
        self.assertTrue(third_return.startswith("/fixture-public/qualification/browser?"))
        self.assertNotIn("cookie", repr(launcher.urls).lower())
        self.assertNotIn("subject", repr(launcher.urls).lower())

    def test_declined_step_stops_before_opening_its_browser(self) -> None:
        terminal = Terminal(confirmations=[True, False])
        launcher = CallbackLauncher(terminal)
        qualification = LoopbackBrowserQualification(
            launcher,
            terminal,
            login_timeout_seconds=2,
            callback_timeout_seconds=2,
            challenge_source=lambda: "b" * 64,
            callback_factory=CallbackSequence(["fixture-authenticated"]),
        )

        result = qualification.verify()

        self.assertTrue(result.authenticated)
        self.assertFalse(result.restricted)
        self.assertFalse(result.logout)
        self.assertEqual(result.blocker, "LIVE_RESTRICTED_BROWSER_CHECK_NOT_CONFIRMED")
        self.assertEqual(len(launcher.urls), 1)

    def test_invalid_or_unavailable_browser_fails_closed(self) -> None:
        class Unavailable:
            def open(self, url: str) -> bool:
                del url
                return False

        result = LoopbackBrowserQualification(
            Unavailable(),
            Terminal(confirmations=[True]),
            login_timeout_seconds=0.1,
            challenge_source=lambda: "c" * 64,
            callback_factory=CallbackSequence(["fixture-authenticated"]),
        ).verify()
        self.assertFalse(result.authenticated)
        self.assertFalse(result.restricted)
        self.assertFalse(result.logout)
        self.assertEqual(result.blocker, "LIVE_AUTHENTICATED_BROWSER_CHECK_FAILED")

        with self.assertRaisesRegex(ValueError, "outside staging"):
            SystemBrowserLauncher().open("https://example.com/")


if __name__ == "__main__":
    unittest.main()
