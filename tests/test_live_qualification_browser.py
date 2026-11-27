"""Browser-assisted live qualification without cookie or identity export."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

from infrastructure.operator.live_qualification import (
    LoopbackBrowserQualification,
    LoopbackMemberAdmissionQualification,
    QualificationCallbackResult,
    SystemBrowserLauncher,
)


@dataclass
class Terminal:
    confirmations: list[bool] = field(
        default_factory=lambda: [True, True, True, True]
    )
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
    results: list[QualificationCallbackResult]
    selected_port: int = 43000

    def __call__(self, challenge: str):  # type: ignore[no-untyped-def]
        del challenge
        expected = self.results.pop(0)
        selected_port = self.selected_port

        @dataclass
        class Callback:
            @property
            def port(self) -> int:
                return selected_port

            def wait(
                self,
                timeout_seconds: float,
            ) -> QualificationCallbackResult | None:
                del timeout_seconds
                return expected

            def close(self) -> None:
                return None

        return Callback()


@dataclass
class AdmissionCallback:
    matched: bool = True
    selected_port: int = 43001
    closed: bool = False

    @property
    def port(self) -> int:
        return self.selected_port

    def wait(self, timeout_seconds: float) -> bool:
        del timeout_seconds
        return self.matched

    def close(self) -> None:
        self.closed = True


class LiveQualificationBrowserTest(unittest.TestCase):
    def test_four_approved_steps_verify_optional_identity_and_logout(self) -> None:
        terminal = Terminal()
        launcher = CallbackLauncher(terminal)
        qualification = LoopbackBrowserQualification(
            launcher,
            terminal,
            login_timeout_seconds=2,
            callback_timeout_seconds=2,
            challenge_source=lambda: "a" * 64,
            callback_factory=CallbackSequence(
                [
                    QualificationCallbackResult("fixture-authenticated", True),
                    QualificationCallbackResult("fixture-public", True),
                    QualificationCallbackResult("fixture-restricted", True),
                    QualificationCallbackResult("fixture-public", False),
                ]
            ),
        )

        result = qualification.verify()

        self.assertTrue(result.authenticated)
        self.assertTrue(result.public_optional)
        self.assertTrue(result.restricted)
        self.assertTrue(result.logout)
        self.assertIsNone(result.blocker)
        self.assertEqual(len(launcher.urls), 4)
        self.assertEqual(
            terminal.events,
            [
                "confirm",
                "open",
                "confirm",
                "open",
                "confirm",
                "open",
                "confirm",
                "open",
            ],
        )
        self.assertTrue(all("[y/N]" in prompt for prompt in terminal.prompts))
        self.assertTrue(any("1/4" in message for message in terminal.messages))
        self.assertTrue(any("2/4" in message for message in terminal.messages))
        self.assertTrue(any("3/4" in message for message in terminal.messages))
        self.assertTrue(any("4/4" in message for message in terminal.messages))

        first = urlsplit(launcher.urls[0])
        self.assertEqual(first.path, "/_platform/logout")
        first_return = unquote(parse_qs(first.query)["return_to"][0])
        self.assertTrue(first_return.startswith("/fixture-authenticated/qualification/browser?"))
        self.assertEqual(
            urlsplit(launcher.urls[2]).path,
            "/fixture-restricted/qualification/browser",
        )
        fourth = urlsplit(launcher.urls[3])
        self.assertEqual(fourth.path, "/_platform/logout")
        fourth_return = unquote(parse_qs(fourth.query)["return_to"][0])
        self.assertTrue(fourth_return.startswith("/fixture-public/qualification/browser?"))
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
            callback_factory=CallbackSequence(
                [QualificationCallbackResult("fixture-authenticated", True)]
            ),
        )

        result = qualification.verify()

        self.assertTrue(result.authenticated)
        self.assertFalse(result.public_optional)
        self.assertFalse(result.restricted)
        self.assertFalse(result.logout)
        self.assertEqual(
            result.blocker,
            "LIVE_PUBLIC_OPTIONAL_BROWSER_CHECK_NOT_CONFIRMED",
        )
        self.assertEqual(len(launcher.urls), 1)

    def test_predecessor_check_proves_public_none_after_authenticated_session(
        self,
    ) -> None:
        """Differentiate public-none from an anonymous optional-identity request."""

        terminal = Terminal(confirmations=[True, True])
        launcher = CallbackLauncher(terminal)
        qualification = LoopbackBrowserQualification(
            launcher,
            terminal,
            login_timeout_seconds=2,
            callback_timeout_seconds=2,
            challenge_source=lambda: "e" * 64,
            callback_factory=CallbackSequence(
                [
                    QualificationCallbackResult("fixture-authenticated", True),
                    QualificationCallbackResult("fixture-public", False),
                ]
            ),
        )

        self.assertTrue(qualification.verify_public_none())
        self.assertEqual(len(launcher.urls), 2)
        self.assertTrue(any("1/2" in message for message in terminal.messages))
        self.assertTrue(any("2/2" in message for message in terminal.messages))

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
            callback_factory=CallbackSequence(
                [QualificationCallbackResult("fixture-authenticated", True)]
            ),
        ).verify()
        self.assertFalse(result.authenticated)
        self.assertFalse(result.public_optional)
        self.assertFalse(result.restricted)
        self.assertFalse(result.logout)
        self.assertEqual(result.blocker, "LIVE_AUTHENTICATED_BROWSER_CHECK_FAILED")

        with self.assertRaisesRegex(ValueError, "outside staging"):
            SystemBrowserLauncher().open("https://example.com/")

    def test_member_admission_check_is_confirmed_and_returns_only_a_decision(self) -> None:
        terminal = Terminal(confirmations=[True, True])
        launcher = CallbackLauncher(terminal)
        callbacks = [AdmissionCallback(), AdmissionCallback()]
        qualification = LoopbackMemberAdmissionQualification(
            launcher,
            terminal,
            timeout_seconds=2,
            challenge_source=lambda: "d" * 64,
            callback_factory=lambda challenge, application_id, expected: callbacks.pop(0),
        )

        allowed = qualification.verify("fixture-restricted", True)
        denied = qualification.verify("fixture-restricted", False)

        self.assertTrue(allowed)
        self.assertTrue(denied)
        self.assertEqual(len(launcher.urls), 2)
        self.assertTrue(
            all(
                urlsplit(url).path == "/_platform/member/qualification"
                for url in launcher.urls
            )
        )
        queries = [parse_qs(urlsplit(url).query) for url in launcher.urls]
        self.assertEqual(
            [query["application_id"] for query in queries],
            [["fixture-restricted"], ["fixture-restricted"]],
        )
        self.assertTrue(all("admitted" not in query for query in queries))
        self.assertEqual(
            terminal.events,
            ["confirm", "open", "confirm", "open"],
        )
        transcript = repr(terminal.messages + terminal.prompts + launcher.urls)
        self.assertNotIn("pmr1_", transcript)
        self.assertNotIn("cookie", transcript.lower())


if __name__ == "__main__":
    unittest.main()
