"""Browser-assisted live qualification without cookie or identity export."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from urllib.parse import parse_qs, urlsplit

from infrastructure.operator.live_qualification import (
    LoopbackBrowserQualification,
    SystemBrowserLauncher,
)


@dataclass
class Terminal:
    messages: list[str] = field(default_factory=list)

    def write(self, message: str) -> None:
        self.messages.append(message)


@dataclass
class CallbackLauncher:
    logged_in: bool = False
    logged_out: bool = False
    urls: list[str] = field(default_factory=list)

    def open(self, url: str) -> bool:
        self.urls.append(url)
        parsed = urlsplit(url)
        if parsed.path == "/_platform/logout":
            self.logged_in = False
            self.logged_out = True
        else:
            application_id = parsed.path.split("/")[1]
            if application_id == "fixture-authenticated" and not self.logged_in:
                self.logged_in = True
            if self.logged_out and application_id == "fixture-authenticated":
                return True
        return True


@dataclass
class Callback:
    launcher: CallbackLauncher
    selected_port: int

    @property
    def port(self) -> int:
        return self.selected_port

    def wait(self, timeout_seconds: float) -> str | None:
        del timeout_seconds
        selected = urlsplit(self.launcher.urls[-1])
        if selected.path == "/_platform/logout":
            return "fixture-public"
        application_id = selected.path.split("/")[1]
        if self.launcher.logged_out and application_id == "fixture-authenticated":
            return None
        values = parse_qs(selected.query)
        return application_id if int(values["callback_port"][0]) == self.port else None

    def close(self) -> None:
        return None


class LiveQualificationBrowserTest(unittest.TestCase):
    def test_browser_flow_proves_auth_restriction_and_logout_without_cookie_export(self) -> None:
        launcher = CallbackLauncher()
        terminal = Terminal()
        qualification = LoopbackBrowserQualification(
            launcher,
            terminal,
            login_timeout_seconds=2,
            callback_timeout_seconds=2,
            logout_timeout_seconds=0.3,
            challenge_source=lambda: "a" * 64,
            callback_factory=lambda _: Callback(launcher, 43000),
        )

        result = qualification.verify()

        self.assertTrue(result.authenticated)
        self.assertTrue(result.restricted)
        self.assertTrue(result.logout)
        self.assertEqual(len(launcher.urls), 4)
        self.assertNotIn("cookie", repr(launcher.urls).lower())
        self.assertNotIn("subject", repr(launcher.urls).lower())
        self.assertIn("session remains only in the browser", terminal.messages[0])

    def test_invalid_or_unavailable_browser_fails_closed(self) -> None:
        class Unavailable:
            def open(self, url: str) -> bool:
                del url
                return False

        result = LoopbackBrowserQualification(
            Unavailable(),
            Terminal(),
            login_timeout_seconds=0.1,
            challenge_source=lambda: "b" * 64,
            callback_factory=lambda _: Callback(CallbackLauncher(), 43001),
        ).verify()
        self.assertFalse(result.authenticated)
        self.assertFalse(result.restricted)
        self.assertFalse(result.logout)

        with self.assertRaisesRegex(ValueError, "outside staging"):
            SystemBrowserLauncher().open("https://example.com/")


if __name__ == "__main__":
    unittest.main()
