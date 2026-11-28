"""Browser and route adapter tests for plural-fixture qualification."""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

from infrastructure.operator.live_fixture_qualification import (
    FixtureQualificationCallbackResult,
    HttpxFixtureRouteQualification,
    LoopbackFixtureQualification,
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
class Launcher:
    terminal: Terminal
    urls: list[str] = field(default_factory=list)

    def open(self, url: str) -> bool:
        self.urls.append(url)
        self.terminal.events.append("open")
        return True


@dataclass
class CallbackSequence:
    results: list[FixtureQualificationCallbackResult]
    port: int = 43210

    def __call__(self, challenge: str):  # type: ignore[no-untyped-def]
        del challenge
        result = self.results.pop(0)
        selected_port = self.port

        @dataclass
        class Callback:
            closed: bool = False

            @property
            def port(self) -> int:
                return selected_port

            def wait(self, timeout_seconds: float):  # type: ignore[no-untyped-def]
                del timeout_seconds
                return result

            def close(self) -> None:
                self.closed = True

        return Callback()


class LiveFixtureQualificationTest(unittest.TestCase):
    def test_one_login_then_three_routes_prove_web_api_web_markers(self) -> None:
        terminal = Terminal()
        launcher = Launcher(terminal)
        browser = LoopbackFixtureQualification(
            launcher,
            terminal,
            login_timeout_seconds=2,
            callback_timeout_seconds=2,
            challenge_source=lambda: "a" * 64,
            callback_factory=CallbackSequence(
                [
                    FixtureQualificationCallbackResult(
                        "fixture-multi-attachment", True, "web"
                    ),
                    FixtureQualificationCallbackResult(
                        "fixture-multi-attachment", True, "api"
                    ),
                    FixtureQualificationCallbackResult(
                        "fixture-multi-attachment", True, "web"
                    ),
                ]
            ),
        )

        result = browser.verify("staging", "fixture-multi-attachment")

        self.assertTrue(result.verified)
        self.assertEqual(
            (result.root_target, result.api_target, result.apix_target),
            ("web", "api", "web"),
        )
        self.assertEqual(result.identity_checks, 3)
        self.assertEqual(
            terminal.events,
            ["confirm", "open", "confirm", "open", "confirm", "open"],
        )
        first = urlsplit(launcher.urls[0])
        self.assertEqual(first.path, "/_platform/logout")
        return_to = unquote(parse_qs(first.query)["return_to"][0])
        self.assertEqual(
            urlsplit(return_to).path,
            "/fixture-multi-attachment/qualification/browser",
        )
        self.assertEqual(
            urlsplit(launcher.urls[1]).path,
            "/fixture-multi-attachment/api/qualification/browser",
        )
        self.assertEqual(
            urlsplit(launcher.urls[2]).path,
            "/fixture-multi-attachment/apix/qualification/browser",
        )
        self.assertNotIn("cookie", repr(launcher.urls).lower())
        self.assertNotIn("subject", repr(launcher.urls).lower())

    def test_browser_marker_mismatch_fails_before_later_routes(self) -> None:
        terminal = Terminal()
        launcher = Launcher(terminal)
        browser = LoopbackFixtureQualification(
            launcher,
            terminal,
            login_timeout_seconds=2,
            callback_timeout_seconds=2,
            challenge_source=lambda: "b" * 64,
            callback_factory=CallbackSequence(
                [
                    FixtureQualificationCallbackResult(
                        "fixture-multi-attachment", True, "api"
                    )
                ]
            ),
        )

        result = browser.verify("staging", "fixture-multi-attachment")

        self.assertFalse(result.verified)
        self.assertEqual(result.identity_checks, 0)
        self.assertEqual(result.blockers, ("FIXTURE_BROWSER_RESULT_MISMATCH",))
        self.assertEqual(len(launcher.urls), 1)

    def test_route_adapter_requires_exact_login_return_paths(self) -> None:
        paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            return httpx.Response(
                303,
                headers={
                    "location": (
                        "/_platform/login?return_to=" + request.url.path
                    )
                },
                request=request,
            )

        result = HttpxFixtureRouteQualification(
            timeout_seconds=2,
            transport=httpx.MockTransport(handler),
        ).verify("staging", "fixture-multi-attachment")

        self.assertTrue(result.verified)
        self.assertEqual(
            paths,
            [
                "/fixture-multi-attachment",
                "/fixture-multi-attachment/api",
                "/fixture-multi-attachment/apix",
            ],
        )


if __name__ == "__main__":
    unittest.main()
