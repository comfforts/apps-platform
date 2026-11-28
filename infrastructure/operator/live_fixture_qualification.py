"""Bounded browser and route adapters for plural-fixture qualification."""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import time
from typing import Callable, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from infrastructure.operator._interfaces import OperatorTerminal
from infrastructure.operator.fixture_qualification import (
    FixtureBrowserVerification,
    FixtureQualificationVerification,
)
from infrastructure.operator.live_qualification import QualificationBrowserLauncher


_APPLICATION_ID = "fixture-multi-attachment"
_STAGING_ORIGIN = "https://apps-staging.comfforts.com"


@dataclass(frozen=True, slots=True)
class FixtureQualificationCallbackResult:
    """One coarse, challenge-bound identity and target-marker callback."""

    application_id: str
    identity_present: bool
    target: str


@dataclass(slots=True)
class _FixtureCallbackState:
    """Mutable one-use loopback state retained only until the browser responds."""

    result: FixtureQualificationCallbackResult | None = None


class FixtureQualificationCallback(Protocol):
    """Receive one browser result over a dynamically assigned loopback port."""

    @property
    def port(self) -> int:
        """Return the selected non-privileged loopback port."""

        ...

    def wait(
        self,
        timeout_seconds: float,
    ) -> FixtureQualificationCallbackResult | None:
        """Wait for one valid callback and discard all invalid requests."""

        ...

    def close(self) -> None:
        """Close the listener and discard transient callback state."""

        ...


class _FixtureCallbackServer:
    """Accept one exact fixture identity and target result on loopback."""

    def __init__(self, challenge: str) -> None:
        """Bind a one-use challenge to a random local non-privileged port."""

        self._challenge = challenge
        self._state = _FixtureCallbackState()
        self._server = HTTPServer(("127.0.0.1", 0), self._handler())
        self._server.timeout = 0.25

    @property
    def port(self) -> int:
        """Return the dynamically assigned callback port."""

        return int(self._server.server_address[1])

    def _handler(self):  # type: ignore[no-untyped-def]
        """Build a handler closed to four coarse callback fields."""

        challenge = self._challenge
        state = self._state

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                """Validate one exact callback without logging its challenge."""

                parsed = urlsplit(self.path)
                try:
                    query = parse_qs(
                        parsed.query,
                        keep_blank_values=True,
                        strict_parsing=True,
                        max_num_fields=4,
                    )
                except ValueError:
                    query = {}
                valid = (
                    parsed.path == "/"
                    and not parsed.fragment
                    and set(query)
                    == {
                        "application_id",
                        "challenge",
                        "identity_present",
                        "target",
                    }
                    and query.get("application_id") == [_APPLICATION_ID]
                    and query.get("challenge") == [challenge]
                    and query.get("identity_present") == ["true"]
                    and query.get("target") in (["web"], ["api"])
                    and state.result is None
                )
                if valid:
                    state.result = FixtureQualificationCallbackResult(
                        _APPLICATION_ID,
                        True,
                        str(query["target"][0]),
                    )
                body = b"Fixture qualification callback received.\n"
                self.send_response(200 if valid else 400)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                """Suppress the one-use challenge from process logs."""

                del format, args

        return Handler

    def wait(
        self,
        timeout_seconds: float,
    ) -> FixtureQualificationCallbackResult | None:
        """Serve bounded requests until one valid result arrives or time expires."""

        deadline = time.monotonic() + timeout_seconds
        while self._state.result is None and time.monotonic() < deadline:
            self._server.handle_request()
        return self._state.result

    def close(self) -> None:
        """Close the loopback socket and discard the coarse result."""

        self._server.server_close()
        self._state.result = None


class LoopbackFixtureQualification:
    """Prove one login reaches root/API targets with exact safe markers."""

    def __init__(
        self,
        launcher: QualificationBrowserLauncher,
        terminal: OperatorTerminal,
        *,
        login_timeout_seconds: float = 300,
        callback_timeout_seconds: float = 30,
        challenge_source: Callable[[], str] | None = None,
        callback_factory: Callable[[str], FixtureQualificationCallback] | None = None,
    ) -> None:
        """Bind browser, operator confirmation, entropy, and loopback seams."""

        self._launcher = launcher
        self._terminal = terminal
        self._login_timeout = login_timeout_seconds
        self._callback_timeout = callback_timeout_seconds
        self._challenge_source = challenge_source or (lambda: secrets.token_hex(32))
        self._callback_factory = callback_factory or _FixtureCallbackServer

    @staticmethod
    def _url(path: str, port: int, challenge: str) -> str:
        """Build one of the three closed browser-observation URLs."""

        if path not in {"", "api", "apix"}:
            raise ValueError("fixture qualification path is unavailable")
        prefix = f"/{_APPLICATION_ID}"
        route = f"{prefix}/{path}/qualification/browser" if path else (
            f"{prefix}/qualification/browser"
        )
        return f"{_STAGING_ORIGIN}{route}?" + urlencode(
            {"callback_port": str(port), "challenge": challenge}
        )

    def _step(
        self,
        path: str,
        expected_target: str,
        *,
        index: int,
        clear_session: bool,
    ) -> tuple[str | None, str | None]:
        """Run one confirmed browser route and retain only its safe target marker."""

        self._terminal.write(
            "FIXTURE QUALIFICATION BROWSER CHECK "
            f"{index}/3\n"
            f"  Application: {_APPLICATION_ID}\n"
            f"  Route: /{path if path else ''}\n"
            f"  Expected target: {expected_target}\n\n"
            + (
                "This step clears any existing platform session, then asks for one "
                "reviewed Google sign-in. Browser credentials remain in the browser."
                if clear_session
                else "This step reuses the platform session established by step 1."
            )
        )
        try:
            confirmed = self._terminal.confirm(
                f"Open the browser for fixture qualification step {index}/3? [y/N] "
            )
        except Exception:
            return None, "FIXTURE_BROWSER_CONFIRMATION_FAILED"
        if not confirmed:
            return None, "FIXTURE_BROWSER_CHECK_NOT_CONFIRMED"
        challenge = self._challenge_source()
        if len(challenge) != 64 or any(
            character not in "0123456789abcdef" for character in challenge
        ):
            raise ValueError("fixture qualification challenge is invalid")
        callback = self._callback_factory(challenge)
        try:
            url = self._url(path, callback.port, challenge)
            if clear_session:
                return_to = url.removeprefix(_STAGING_ORIGIN)
                url = f"{_STAGING_ORIGIN}/_platform/logout?" + urlencode(
                    {"return_to": return_to}
                )
            try:
                opened = self._launcher.open(url)
            except Exception:
                opened = False
            if not opened:
                return None, "FIXTURE_BROWSER_OPEN_FAILED"
            observed = callback.wait(
                self._login_timeout if clear_session else self._callback_timeout
            )
            expected = FixtureQualificationCallbackResult(
                _APPLICATION_ID,
                True,
                expected_target,
            )
            if observed != expected:
                return None, "FIXTURE_BROWSER_RESULT_MISMATCH"
            return expected_target, None
        finally:
            callback.close()

    def verify(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureBrowserVerification:
        """Run root, API, and `/apix` observations after exactly one login start."""

        if environment != "staging" or application_id != _APPLICATION_ID:
            return FixtureBrowserVerification(
                False,
                None,
                None,
                None,
                0,
                ("FIXTURE_BROWSER_SELECTION_INVALID",),
            )
        markers: list[str] = []
        for index, (path, expected) in enumerate(
            (("", "web"), ("api", "api"), ("apix", "web")),
            start=1,
        ):
            marker, blocker = self._step(
                path,
                expected,
                index=index,
                clear_session=index == 1,
            )
            if blocker is not None:
                padded = [*markers, *([None] * (3 - len(markers)))]
                return FixtureBrowserVerification(
                    False,
                    padded[0],
                    padded[1],
                    padded[2],
                    len(markers),
                    (blocker,),
                )
            assert marker is not None
            markers.append(marker)
        return FixtureBrowserVerification(
            True,
            markers[0],
            markers[1],
            markers[2],
            3,
        )


class HttpxFixtureRouteQualification:
    """Verify the three protected route entry points without credentials."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Configure one bounded client and optional deterministic test transport."""

        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport

    @staticmethod
    def _login_redirect(location: str, expected_path: str) -> bool:
        """Accept only the exact relative platform-login redirect."""

        try:
            parsed = urlsplit(location)
            query = parse_qs(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
            )
        except ValueError:
            return False
        return (
            not parsed.scheme
            and not parsed.netloc
            and parsed.path == "/_platform/login"
            and not parsed.fragment
            and query == {"return_to": [expected_path]}
        )

    def verify(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureQualificationVerification:
        """Verify root, `/api`, and `/apix` all enter the protected app route."""

        if environment != "staging" or application_id != _APPLICATION_ID:
            return FixtureQualificationVerification(
                False,
                {"result": "selection-invalid"},
                ("FIXTURE_ROUTE_SELECTION_INVALID",),
            )
        paths = (
            f"/{application_id}",
            f"/{application_id}/api",
            f"/{application_id}/apix",
        )
        observed = 0
        try:
            with httpx.Client(
                follow_redirects=False,
                timeout=self._timeout,
                trust_env=False,
                transport=self._transport,
            ) as client:
                for path in paths:
                    response = client.get(
                        _STAGING_ORIGIN + path,
                        headers={
                            "User-Agent": (
                                "comfforts-app-platform-fixture-qualification/1"
                            )
                        },
                    )
                    if response.status_code != 303 or not self._login_redirect(
                        response.headers.get("location", ""),
                        path,
                    ):
                        break
                    observed += 1
        except httpx.HTTPError:
            observed = 0
        valid = observed == len(paths)
        return FixtureQualificationVerification(
            valid,
            {
                "protected_routes": observed,
                "result": "verified" if valid else "mismatch",
            },
            () if valid else ("FIXTURE_ROUTE_SELECTION_MISMATCH",),
        )


__all__ = (
    "FixtureQualificationCallback",
    "FixtureQualificationCallbackResult",
    "HttpxFixtureRouteQualification",
    "LoopbackFixtureQualification",
)
