"""One-use browser verification for Platform Member lifecycle operations.

The browser visits the Shared Edge, clears any ambient Platform Session, and
completes the existing Google OIDC flow.  The edge returns only an opaque,
environment-scoped member reference to a process-local callback.  This module
never receives Google claims, email, credentials, provider tokens, or cookies.
"""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
import re
import secrets
import time
from typing import Callable, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit

from infrastructure.operator._interfaces import OperatorTerminal
from infrastructure.operator.member_lifecycle import (
    MemberMutationInterrupted,
    MemberOperation,
    VerifiedMemberVisitor,
)


_MEMBER_REFERENCE = re.compile(r"pmr1_[0-9a-f]{64}")
_ORIGIN = re.compile(r"https://[a-z0-9.-]+")
_VERIFY_PATH = "/_platform/member/verify"
_LOGOUT_PATH = "/_platform/logout"


class MemberBrowserLauncher(Protocol):
    """Open one reviewed HTTPS platform URL in the operator's browser."""

    def open(self, url: str) -> bool:
        """Return whether the browser accepted the exact URL."""


class MemberCallback(Protocol):
    """Receive one browser result on process-local loopback only."""

    @property
    def port(self) -> int:
        """Return the dynamically assigned loopback port."""

    def wait(self, timeout_seconds: float) -> VerifiedMemberVisitor | None:
        """Wait for the exact one-use callback or return no verified visitor."""

    def close(self) -> None:
        """Close the loopback listener and discard transient callback state."""


@dataclass(slots=True)
class _CallbackResult:
    """Mutable process-local result shared with the HTTP handler."""

    visitor: VerifiedMemberVisitor | None = None


class LoopbackMemberCallback:
    """Validate one challenge-bound member callback on ``127.0.0.1``."""

    def __init__(
        self,
        challenge: str,
        environment: str,
        operation: MemberOperation,
    ) -> None:
        """Bind an ephemeral listener without exposing it beyond loopback."""

        self._challenge = challenge
        self._environment = environment
        self._operation = operation
        self._result = _CallbackResult()
        self._server = HTTPServer(
            ("127.0.0.1", 0),
            self._handler(),
            bind_and_activate=True,
        )

    @property
    def port(self) -> int:
        """Return the assigned non-privileged loopback port."""

        return int(self._server.server_address[1])

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        """Create a handler closed over only the expected one-use bindings."""

        callback = self

        class Handler(BaseHTTPRequestHandler):
            """Accept one exact query and never log browser request data."""

            def do_GET(self) -> None:  # noqa: N802
                """Validate the callback and retain only the opaque reference."""

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
                expected_keys = {
                    "challenge",
                    "environment",
                    "member_reference",
                    "operation",
                }
                reference_values = query.get("member_reference", [])
                valid = (
                    parsed.path == "/"
                    and not parsed.fragment
                    and set(query) == expected_keys
                    and query.get("challenge") == [callback._challenge]
                    and query.get("environment") == [callback._environment]
                    and query.get("operation") == [callback._operation]
                    and len(reference_values) == 1
                    and _MEMBER_REFERENCE.fullmatch(reference_values[0]) is not None
                    and callback._result.visitor is None
                )
                if valid:
                    callback._result.visitor = VerifiedMemberVisitor(
                        callback._environment,
                        callback._operation,
                        reference_values[0],
                    )
                body = (
                    b"App Platform member verification received. Return to the terminal.\n"
                    if valid
                    else b"Invalid member verification response.\n"
                )
                self.send_response(200 if valid else 400)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                """Suppress callback URLs because they contain one-use challenge data."""

                del format, args

        return Handler

    def wait(self, timeout_seconds: float) -> VerifiedMemberVisitor | None:
        """Serve callbacks until one valid result arrives or the deadline expires."""

        deadline = time.monotonic() + timeout_seconds
        while self._result.visitor is None and time.monotonic() < deadline:
            self._server.timeout = min(0.25, max(0.0, deadline - time.monotonic()))
            self._server.handle_request()
        return self._result.visitor

    def close(self) -> None:
        """Close the socket and erase the retained transient result reference."""

        self._server.server_close()
        self._result.visitor = None


class LoopbackMemberVisitorVerifier:
    """Run one confirmed platform login and consume its opaque callback once."""

    def __init__(
        self,
        launcher: MemberBrowserLauncher,
        terminal: OperatorTerminal,
        origins: dict[str, str],
        *,
        timeout_seconds: float = 300,
        challenge_source: Callable[[], str] | None = None,
        callback_factory: (
            Callable[[str, str, MemberOperation], MemberCallback] | None
        ) = None,
    ) -> None:
        """Bind explicit browser, terminal, origin, entropy, and callback seams."""

        if not origins or any(
            _ORIGIN.fullmatch(origin) is None or origin.endswith("/")
            for origin in origins.values()
        ):
            raise ValueError("invalid member verification origins")
        self._launcher = launcher
        self._terminal = terminal
        self._origins = dict(origins)
        self._timeout = timeout_seconds
        self._challenge_source = challenge_source or (lambda: secrets.token_hex(32))
        self._callback_factory = callback_factory or LoopbackMemberCallback

    def verify(
        self,
        environment: str,
        operation: MemberOperation,
    ) -> VerifiedMemberVisitor:
        """Return one verified opaque reference or fail without identity output."""

        origin = self._origins.get(environment)
        if origin is None:
            raise ValueError("member verification environment is unavailable")
        self._terminal.write(
            "PLATFORM MEMBER IDENTITY VERIFICATION\n"
            f"  Environment: {environment}\n"
            f"  Operation: {operation}\n\n"
            "The browser will clear any existing Apps Platform session and ask "
            "you to select the exact Google Visitor identity bound to this member "
            "action. The Cloud Operator account and Visitor identity are separate. "
            "No email, identity claim, credential, or browser state returns to the terminal."
        )
        if not self._terminal.confirm(
            "Open the browser for this one-use member verification? [y/N] "
        ):
            raise MemberMutationInterrupted("member browser verification declined")
        challenge = self._challenge_source()
        if not re.fullmatch(r"[0-9a-f]{64}", challenge):
            raise ValueError("member challenge source is invalid")
        callback = self._callback_factory(challenge, environment, operation)
        try:
            verification_path = _VERIFY_PATH + "?" + urlencode(
                {
                    "callback_port": str(callback.port),
                    "challenge": challenge,
                    "operation": operation,
                }
            )
            url = origin + _LOGOUT_PATH + "?" + urlencode(
                {"return_to": verification_path}
            )
            if not self._launcher.open(url):
                raise MemberMutationInterrupted("member browser could not open")
            visitor = callback.wait(self._timeout)
            if visitor is None:
                raise MemberMutationInterrupted("member browser callback timed out")
            return visitor
        finally:
            callback.close()


__all__ = (
    "LoopbackMemberCallback",
    "LoopbackMemberVisitorVerifier",
    "MemberBrowserLauncher",
    "MemberCallback",
)
