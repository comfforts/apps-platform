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

from infrastructure.operator._interfaces import OperatorTerminal
from infrastructure.operator.integration import AttachmentTargetReader
from infrastructure.operator.project_connections import (
    ApplicationProjectReadback,
    NETWORK_REFERENCE,
    PLATFORM_PROJECT_ID,
    SUBNETWORK_REFERENCE,
)
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
    blocker: str | None = None


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
        terminal: OperatorTerminal,
        *,
        login_timeout_seconds: float = 300,
        callback_timeout_seconds: float = 30,
        challenge_source: Callable[[], str] | None = None,
        callback_factory: Callable[[str], QualificationCallback] | None = None,
    ) -> None:
        self._launcher = launcher
        self._terminal = terminal
        self._login_timeout = login_timeout_seconds
        self._callback_timeout = callback_timeout_seconds
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

    def _run_browser_step(
        self,
        application_id: str,
        timeout_seconds: float,
        *,
        step_number: int,
        title: str,
        instructions: str,
        blocker_prefix: str,
        clear_session: bool,
    ) -> tuple[bool, str | None]:
        self._terminal.write(
            f"BROWSER CHECK {step_number}/3: {title}\n\n{instructions}"
        )
        try:
            confirmed = self._terminal.confirm(
                f"Open the browser for qualification step {step_number}/3? [y/N] "
            )
        except Exception:
            return False, f"LIVE_{blocker_prefix}_BROWSER_CHECK_FAILED"
        if not confirmed:
            return False, f"LIVE_{blocker_prefix}_BROWSER_CHECK_NOT_CONFIRMED"

        challenge = self._challenge_source()
        if len(challenge) != 64 or any(value not in "0123456789abcdef" for value in challenge):
            raise ValueError("qualification challenge source is invalid")
        callback = self._callback_factory(challenge)
        try:
            url = self._fixture_url(application_id, callback.port, challenge)
            if clear_session:
                return_to = url.removeprefix(_STAGING_ORIGIN)
                url = (
                    f"{_STAGING_ORIGIN}/_platform/logout?"
                    + urlencode({"return_to": return_to})
                )
            try:
                opened = self._launcher.open(url)
            except Exception:
                opened = False
            if not opened:
                return False, f"LIVE_{blocker_prefix}_BROWSER_CHECK_FAILED"
            if callback.wait(timeout_seconds) != application_id:
                return False, f"LIVE_{blocker_prefix}_BROWSER_CHECK_FAILED"
            return True, None
        finally:
            callback.close()

    def verify(self) -> BrowserQualificationResult:
        authenticated, blocker = self._run_browser_step(
            "fixture-authenticated",
            self._login_timeout,
            step_number=1,
            title="Establish the reviewed operator session",
            instructions=(
                "This step first clears any existing Apps Platform session in the "
                "browser, then starts Google sign-in. Select the exact operator "
                "account approved for the restricted staging fixture. Browser "
                "credentials and session state remain only in the browser."
            ),
            blocker_prefix="AUTHENTICATED",
            clear_session=True,
        )
        if not authenticated:
            return BrowserQualificationResult(False, False, False, blocker)

        restricted, blocker = self._run_browser_step(
            "fixture-restricted",
            self._callback_timeout,
            step_number=2,
            title="Verify restricted application admission",
            instructions=(
                "This step reuses the Apps Platform session established in step 1. "
                "It should reach the restricted fixture without another Google "
                "sign-in prompt."
            ),
            blocker_prefix="RESTRICTED",
            clear_session=False,
        )
        if not restricted:
            return BrowserQualificationResult(True, False, False, blocker)

        logged_out, blocker = self._run_browser_step(
            "fixture-public",
            self._callback_timeout,
            step_number=3,
            title="Verify platform logout",
            instructions=(
                "This step asks the Shared Edge to delete and read back the current "
                "Apps Platform session, then returns through the public fixture. "
                "It does not open another sign-in flow."
            ),
            blocker_prefix="LOGOUT",
            clear_session=True,
        )
        return BrowserQualificationResult(True, True, logged_out, blocker)


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
        fixture_project: ApplicationProjectReadback,
    ) -> None:
        self._http = http
        self._browser = browser
        self._targets = targets
        self._lifecycle = lifecycle
        self._fixture_project = fixture_project
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

    @staticmethod
    def _login_redirect_matches(location: str, return_to: str) -> bool:
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
            and query == {"return_to": [return_to]}
        )

    @staticmethod
    def _https_redirect_matches(location: str) -> bool:
        try:
            parsed = urlsplit(location)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname == "apps-staging.comfforts.com"
            and port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and parsed.path == "/"
            and not parsed.query
            and not parsed.fragment
        )

    def _admission_identity(self, check_id: str) -> QualificationProbeOutcome:
        public = self._http.request("GET", "/fixture-public")
        authenticated = self._http.request("GET", "/fixture-authenticated")
        restricted = self._http.request("GET", "/fixture-restricted")
        redirects = (authenticated, restricted)
        routes_valid = (
            public.status_code == 200
            and all(item.status_code == 303 for item in redirects)
            and all(
                self._login_redirect_matches(
                    item.headers.get("location", ""),
                    path,
                )
                for item, path in zip(
                    redirects,
                    ("/fixture-authenticated", "/fixture-restricted"),
                    strict=True,
                )
            )
        )
        if not routes_valid:
            return self._fail(check_id, "LIVE_ADMISSION_IDENTITY_MISMATCH")

        browser = self._browser_checks()
        if browser.blocker is not None:
            return self._fail(check_id, browser.blocker)
        if not browser.authenticated:
            return self._fail(check_id, "LIVE_AUTHENTICATED_BROWSER_CHECK_FAILED")
        if not browser.restricted:
            return self._fail(check_id, "LIVE_RESTRICTED_BROWSER_CHECK_FAILED")
        if not browser.logout:
            return self._fail(check_id, "LIVE_LOGOUT_BROWSER_CHECK_FAILED")
        return self._pass(check_id, browser_flows=3, route_modes=3)

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

    def _target_reference(self, application_id: str) -> str:
        project_number = self._fixture_project.project_number
        if project_number is None:
            raise ValueError("fixture project number is unavailable")
        return (
            "urn:comfforts:app-platform:gcp:cloud-run:"
            f"{project_number}:us-west1:{application_id}"
        )

    def _target_posture(self, request: QualificationProbeRequest) -> bool:
        project = self._fixture_project
        if (
            not project.exists
            or project.project_number is None
            or not project.state_bucket_ready
            or not project.artifact_repository_ready
            or not project.fixture_ownership_matches
            or project.host_project_id != PLATFORM_PROJECT_ID
            or not project.network_viewer_granted
            or not project.subnet_user_granted
        ):
            return False
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
                or target.application_project_id != project.project_id
                or target.network_reference != NETWORK_REFERENCE
                or target.subnetwork_reference != SUBNETWORK_REFERENCE
                or target.egress_mode != "all-traffic"
                or target.blockers
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
            and self._https_redirect_matches(
                redirect.headers.get("location", "")
            )
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
    "SystemBrowserLauncher",
    "StagingQualificationProbe",
)
