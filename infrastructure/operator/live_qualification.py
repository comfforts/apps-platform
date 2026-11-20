"""Bounded browser-assisted checks for the live staging identity path."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import secrets
import time
from typing import Callable, Mapping, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser

import httpx
from websockets.sync.client import connect as websocket_connect

from infrastructure.operator.integration import AttachmentTargetReader
from infrastructure.operator.qualification import (
    QualificationProbeOutcome,
    QualificationProbeRequest,
)


_STAGING_ORIGIN = "https://apps-staging.comfforts.com"
_FIXTURE_APPLICATIONS = {
    "fixture-authenticated",
    "fixture-public",
    "fixture-restricted",
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)


class QualificationBrowserLauncher(Protocol):
    def open(self, url: str) -> bool: ...


class QualificationTerminal(Protocol):
    def write(self, message: str) -> None: ...


class QualificationCallback(Protocol):
    @property
    def port(self) -> int: ...

    def wait(self, timeout_seconds: float) -> str | None: ...

    def close(self) -> None: ...


class QualificationLifecycleExercise(Protocol):
    def verify_rollback(self, environment: str, generation_digest: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class QualificationHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class QualificationHttpClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        insecure_http: bool = False,
    ) -> QualificationHttpResponse: ...

    def websocket(self, path: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class SystemBrowserLauncher:
    """Open only a reviewed HTTPS staging URL in the operator's browser."""

    def open(self, url: str) -> bool:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or f"{parsed.scheme}://{parsed.netloc}" != _STAGING_ORIGIN
            or not parsed.path.startswith("/")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("qualification browser URL is outside staging")
        return webbrowser.open(url, new=2, autoraise=True)


@dataclass(frozen=True, slots=True)
class BrowserQualificationResult:
    authenticated: bool
    restricted: bool
    logout: bool


@dataclass(slots=True)
class _CallbackResult:
    application_id: str | None = None


class _CallbackServer:
    """Accept one opaque challenge response on loopback and nothing else."""

    def __init__(self, challenge: str) -> None:
        self._challenge = challenge
        self._result = _CallbackResult()
        self._server = HTTPServer(("127.0.0.1", 0), self._handler())
        self._server.timeout = 0.25

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def _handler(self):  # type: ignore[no-untyped-def]
        challenge = self._challenge
        result = self._result

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlsplit(self.path)
                query = parse_qs(
                    parsed.query,
                    keep_blank_values=True,
                    strict_parsing=True,
                    max_num_fields=2,
                )
                application_values = query.get("application_id", [])
                challenge_values = query.get("challenge", [])
                valid = (
                    parsed.path == "/"
                    and not parsed.fragment
                    and set(query) == {"application_id", "challenge"}
                    and len(application_values) == 1
                    and application_values[0] in _FIXTURE_APPLICATIONS
                    and challenge_values == [challenge]
                )
                if valid:
                    result.application_id = application_values[0]
                body = b"App Platform qualification callback received.\n"
                self.send_response(200 if valid else 400)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        return Handler

    def wait(self, timeout_seconds: float) -> str | None:
        deadline = time.monotonic() + timeout_seconds
        while self._result.application_id is None and time.monotonic() < deadline:
            self._server.handle_request()
        return self._result.application_id

    def close(self) -> None:
        self._server.server_close()


class LoopbackBrowserQualification:
    """Verify OAuth/session/restricted/logout without exporting browser state."""

    def __init__(
        self,
        launcher: QualificationBrowserLauncher,
        terminal: QualificationTerminal,
        *,
        login_timeout_seconds: float = 300,
        callback_timeout_seconds: float = 30,
        logout_timeout_seconds: float = 5,
        challenge_source: Callable[[], str] | None = None,
        callback_factory: Callable[[str], QualificationCallback] | None = None,
    ) -> None:
        self._launcher = launcher
        self._terminal = terminal
        self._login_timeout = login_timeout_seconds
        self._callback_timeout = callback_timeout_seconds
        self._logout_timeout = logout_timeout_seconds
        self._challenge_source = challenge_source or (lambda: secrets.token_hex(32))
        self._callback_factory = callback_factory or _CallbackServer

    @staticmethod
    def _fixture_url(application_id: str, port: int, challenge: str) -> str:
        if application_id not in _FIXTURE_APPLICATIONS:
            raise ValueError("unknown qualification fixture")
        return (
            f"{_STAGING_ORIGIN}/{application_id}/qualification/browser?"
            + urlencode(
                {
                    "callback_port": str(port),
                    "challenge": challenge,
                }
            )
        )

    def _open_and_wait(
        self,
        application_id: str,
        timeout_seconds: float,
    ) -> bool:
        challenge = self._challenge_source()
        if len(challenge) != 64 or any(value not in "0123456789abcdef" for value in challenge):
            raise ValueError("qualification challenge source is invalid")
        callback = self._callback_factory(challenge)
        try:
            url = self._fixture_url(application_id, callback.port, challenge)
            if not self._launcher.open(url):
                return False
            return callback.wait(timeout_seconds) == application_id
        finally:
            callback.close()

    def verify(self) -> BrowserQualificationResult:
        self._terminal.write(
            "BROWSER_CHECK Sign in with the reviewed staging operator account; "
            "the session remains only in the browser."
        )
        authenticated = self._open_and_wait(
            "fixture-authenticated",
            self._login_timeout,
        )
        if not authenticated:
            return BrowserQualificationResult(False, False, False)

        restricted = self._open_and_wait(
            "fixture-restricted",
            self._callback_timeout,
        )
        if not restricted:
            return BrowserQualificationResult(True, False, False)

        challenge = self._challenge_source()
        callback = self._callback_factory(challenge)
        try:
            return_to = self._fixture_url(
                "fixture-public",
                callback.port,
                challenge,
            ).removeprefix(_STAGING_ORIGIN)
            logout_url = (
                f"{_STAGING_ORIGIN}/_platform/logout?"
                + urlencode({"return_to": return_to})
            )
            if not self._launcher.open(logout_url):
                return BrowserQualificationResult(True, True, False)
            logout_callback = callback.wait(self._callback_timeout)
        finally:
            callback.close()
        if logout_callback != "fixture-public":
            return BrowserQualificationResult(True, True, False)

        # A removed session must return to Google login rather than reach the
        # protected fixture callback. The operator need not copy a cookie or token.
        logged_out = not self._open_and_wait(
            "fixture-authenticated",
            self._logout_timeout,
        )
        return BrowserQualificationResult(True, True, logged_out)


class HttpxQualificationClient:
    """Exercise only the exact public staging origin without credentials."""

    _PATHS = {
        "/",
        "/.well-known/jwks.json",
        "/fixture-authenticated",
        "/fixture-public",
        "/fixture-public/api",
        "/fixture-public/failure",
        "/fixture-public/socket",
        "/fixture-public/stream",
        "/fixture-public/upload",
        "/fixture-restricted",
    }

    def __init__(self, *, timeout_seconds: float = 20) -> None:
        self._timeout = httpx.Timeout(timeout_seconds)

    @classmethod
    def _url(cls, path: str, *, insecure_http: bool = False) -> str:
        if path not in cls._PATHS:
            raise ValueError("qualification path is outside the approved set")
        scheme = "http" if insecure_http else "https"
        return f"{scheme}://apps-staging.comfforts.com{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        insecure_http: bool = False,
    ) -> QualificationHttpResponse:
        if method not in {"GET", "POST"} or len(body) > 65_536:
            raise ValueError("qualification HTTP request is outside the approved set")
        with httpx.Client(
            follow_redirects=False,
            timeout=self._timeout,
            trust_env=False,
        ) as client:
            response = client.request(
                method,
                self._url(path, insecure_http=insecure_http),
                content=body,
                headers={"User-Agent": "comfforts-app-platform-qualification/1"},
            )
            payload = response.read()
        if len(payload) > 1_048_576:
            raise ValueError("qualification response exceeds the approved bound")
        return QualificationHttpResponse(
            response.status_code,
            dict(response.headers),
            payload,
        )

    def websocket(self, path: str) -> bool:
        url = self._url(path).replace("https://", "wss://", 1)
        try:
            with websocket_connect(
                url,
                open_timeout=20,
                close_timeout=5,
                user_agent_header="comfforts-app-platform-qualification/1",
            ) as socket:
                socket.send("synthetic-qualification")
                return socket.recv(timeout=10) == "fixture-ready"
        except Exception:
            return False


class StagingQualificationProbe:
    """Evaluate the closed qualification checks through exact live adapters."""

    def __init__(
        self,
        http: QualificationHttpClient,
        browser: LoopbackBrowserQualification,
        targets: AttachmentTargetReader,
        lifecycle: QualificationLifecycleExercise,
    ) -> None:
        self._http = http
        self._browser = browser
        self._targets = targets
        self._lifecycle = lifecycle
        self._browser_result: BrowserQualificationResult | None = None

    @staticmethod
    def _pass(check_id: str, **facts: object) -> QualificationProbeOutcome:
        return QualificationProbeOutcome(
            "pass",
            {"check_id": check_id, "result": "verified", **facts},
        )

    @staticmethod
    def _fail(check_id: str, blocker: str) -> QualificationProbeOutcome:
        return QualificationProbeOutcome(
            "fail",
            {"check_id": check_id, "result": "mismatch"},
            (blocker,),
        )

    @staticmethod
    def _json(response: QualificationHttpResponse) -> dict[str, object] | None:
        try:
            value = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _browser_checks(self) -> BrowserQualificationResult:
        if self._browser_result is None:
            self._browser_result = self._browser.verify()
        return self._browser_result

    def _admission_identity(self, check_id: str) -> QualificationProbeOutcome:
        public = self._http.request("GET", "/fixture-public")
        authenticated = self._http.request("GET", "/fixture-authenticated")
        restricted = self._http.request("GET", "/fixture-restricted")
        redirects = (authenticated, restricted)
        browser = self._browser_checks()
        valid = (
            public.status_code == 200
            and all(item.status_code == 303 for item in redirects)
            and all(
                item.headers.get("location", "").startswith(
                    "/_platform/auth/login?return_to="
                )
                for item in redirects
            )
            and browser.authenticated
            and browser.restricted
            and browser.logout
        )
        return (
            self._pass(check_id, browser_flows=3, route_modes=3)
            if valid
            else self._fail(check_id, "LIVE_ADMISSION_IDENTITY_MISMATCH")
        )

    def _assertion_jwks(self, check_id: str) -> QualificationProbeOutcome:
        response = self._http.request("GET", "/.well-known/jwks.json")
        value = self._json(response)
        keys = value.get("keys") if value is not None else None
        valid = (
            response.status_code == 200
            and isinstance(keys, list)
            and 1 <= len(keys) <= 3
            and all(
                isinstance(key, dict)
                and key.get("kty") == "EC"
                and isinstance(key.get("kid"), str)
                for key in keys
            )
            and self._browser_checks().authenticated
        )
        return (
            self._pass(check_id, key_count=len(keys) if isinstance(keys, list) else 0)
            if valid
            else self._fail(check_id, "LIVE_ASSERTION_JWKS_MISMATCH")
        )

    @staticmethod
    def _target_reference(application_id: str) -> str:
        return (
            "urn:comfforts:app-platform:gcp:cloud-run:"
            f"455651441682:us-west1:{application_id}"
        )

    def _target_posture(self, request: QualificationProbeRequest) -> bool:
        modes = {
            "fixture-authenticated": "authenticated",
            "fixture-public": "public",
            "fixture-restricted": "restricted",
        }
        for application_id, mode in modes.items():
            reference = self._target_reference(application_id)
            target = self._targets.read_target(request.current.environment, reference)
            expected_audience = (
                None
                if mode == "public"
                else f"urn:comfforts:app-platform:audience:{application_id}"
            )
            if (
                not target.exists
                or not target.ready
                or target.owner_application_id != application_id
                or target.resource_reference != reference
                or target.ingress_mode != "shared_edge_only"
                or target.caller_grant != _EDGE_CALLER
                or target.audience != expected_audience
            ):
                return False
        return True

    def _attachment_posture(
        self,
        check_id: str,
        request: QualificationProbeRequest,
    ) -> QualificationProbeOutcome:
        return (
            self._pass(check_id, targets=3)
            if self._target_posture(request)
            else self._fail(check_id, "LIVE_ATTACHMENT_POSTURE_MISMATCH")
        )

    def _catalogue_routing(self, check_id: str) -> QualificationProbeOutcome:
        catalogue = self._http.request("GET", "/")
        public = self._http.request("GET", "/fixture-public")
        mounted = self._http.request("GET", "/fixture-public/api")
        public_value = self._json(public)
        mounted_value = self._json(mounted)
        valid = (
            catalogue.status_code == 200
            and b"Public fixture" in catalogue.body
            and b"Restricted fixture" in catalogue.body
            and b"Authenticated fixture" not in catalogue.body
            and public.status_code == 200
            and mounted.status_code == 200
            and public_value is not None
            and mounted_value is not None
            and public_value.get("application_id") == "fixture-public"
            and mounted_value.get("application_id") == "fixture-public"
        )
        return (
            self._pass(check_id, catalogue_entries=2, routed_paths=2)
            if valid
            else self._fail(check_id, "LIVE_CATALOGUE_ROUTING_MISMATCH")
        )

    def _dns_tls(self, check_id: str) -> QualificationProbeOutcome:
        redirect = self._http.request("GET", "/", insecure_http=True)
        secure = self._http.request("GET", "/")
        valid = (
            redirect.status_code in {301, 302, 307, 308}
            and redirect.headers.get("location")
            == "https://apps-staging.comfforts.com/"
            and secure.status_code == 200
        )
        return (
            self._pass(check_id, https_status_class=2, redirect_status_class=3)
            if valid
            else self._fail(check_id, "LIVE_DNS_TLS_MISMATCH")
        )

    def _isolation_limits(self, check_id: str) -> QualificationProbeOutcome:
        upload = self._http.request(
            "POST",
            "/fixture-public/upload",
            body=b"synthetic-qualification",
        )
        stream = self._http.request("GET", "/fixture-public/stream")
        failure = self._http.request("GET", "/fixture-public/failure")
        recovered = self._http.request("GET", "/fixture-public")
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = tuple(
                pool.map(
                    lambda _: self._http.request("GET", "/fixture-public").status_code,
                    range(2),
                )
            )
        valid = (
            upload.status_code == 204
            and stream.status_code == 200
            and stream.body == b"fixture-stream-1\nfixture-stream-2\n"
            and failure.status_code == 503
            and recovered.status_code == 200
            and concurrent == (200, 200)
            and self._http.websocket("/fixture-public/socket")
        )
        return (
            self._pass(check_id, concurrency=2, transports=4)
            if valid
            else self._fail(check_id, "LIVE_ISOLATION_LIMIT_MISMATCH")
        )

    def _lifecycle_rollback(
        self,
        check_id: str,
        request: QualificationProbeRequest,
    ) -> QualificationProbeOutcome:
        verified = self._lifecycle.verify_rollback(
            request.current.environment,
            request.current.registration_generation_digest,
        )
        return (
            self._pass(check_id, generation_transitions=2)
            if verified
            else self._fail(check_id, "LIVE_LIFECYCLE_ROLLBACK_MISMATCH")
        )

    def _redaction(self, check_id: str) -> QualificationProbeOutcome:
        response = self._http.request("GET", "/fixture-public")
        material = response.body.lower() + repr(dict(response.headers)).lower().encode()
        prohibited = (
            b"authorization",
            b"cookie",
            b"identity",
            b"secret",
            b"session",
            b"subject",
        )
        return (
            self._pass(check_id, response_count=1)
            if response.status_code == 200 and not any(item in material for item in prohibited)
            else self._fail(check_id, "LIVE_REDACTION_MISMATCH")
        )

    @staticmethod
    def _source_integrity(
        check_id: str,
        request: QualificationProbeRequest,
    ) -> QualificationProbeOutcome:
        current = request.current
        valid = (
            _REVISION.fullmatch(current.source_revision) is not None
            and _DIGEST.fullmatch(current.registration_generation_digest) is not None
            and bool(current.component_revisions)
            and len(current.fixture_revisions) == 3
            and all(_DIGEST.fullmatch(item.digest) for item in current.component_revisions)
            and all(
                _REVISION.fullmatch(item.application_source_revision)
                and _DIGEST.fullmatch(item.integration_bundle_digest)
                and _DIGEST.fullmatch(item.attachment_bundle_digest)
                for item in current.fixture_revisions
            )
        )
        return (
            StagingQualificationProbe._pass(
                check_id,
                component_revisions=len(current.component_revisions),
                fixture_revisions=len(current.fixture_revisions),
            )
            if valid
            else StagingQualificationProbe._fail(
                check_id,
                "LIVE_SOURCE_INTEGRITY_MISMATCH",
            )
        )

    def evaluate(self, request: QualificationProbeRequest) -> QualificationProbeOutcome:
        if request.current.environment != "staging":
            return self._fail(request.check_id, "QUALIFICATION_ENVIRONMENT_UNAVAILABLE")
        try:
            if request.check_id == "admission-identity":
                return self._admission_identity(request.check_id)
            if request.check_id == "assertion-jwks":
                return self._assertion_jwks(request.check_id)
            if request.check_id == "attachment-posture":
                return self._attachment_posture(request.check_id, request)
            if request.check_id == "catalogue-routing":
                return self._catalogue_routing(request.check_id)
            if request.check_id == "direct-origin-denial":
                return (
                    self._pass(request.check_id, targets=3)
                    if self._target_posture(request)
                    else self._fail(request.check_id, "LIVE_DIRECT_ORIGIN_MISMATCH")
                )
            if request.check_id == "dns-tls":
                return self._dns_tls(request.check_id)
            if request.check_id == "isolation-limits":
                return self._isolation_limits(request.check_id)
            if request.check_id == "lifecycle-rollback":
                return self._lifecycle_rollback(request.check_id, request)
            if request.check_id == "redaction":
                return self._redaction(request.check_id)
            if request.check_id == "source-integrity":
                return self._source_integrity(request.check_id, request)
        except Exception:
            return self._fail(request.check_id, "LIVE_QUALIFICATION_COMMAND_FAILED")
        return self._fail(request.check_id, "QUALIFICATION_CHECK_UNAVAILABLE")


__all__ = (
    "BrowserQualificationResult",
    "HttpxQualificationClient",
    "LoopbackBrowserQualification",
    "QualificationHttpClient",
    "QualificationHttpResponse",
    "QualificationLifecycleExercise",
    "QualificationBrowserLauncher",
    "QualificationCallback",
    "QualificationTerminal",
    "SystemBrowserLauncher",
    "StagingQualificationProbe",
)
