"""Networked synthetic Fixture Application used only for AP-M9 qualification."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
import re
import sys
import time
from typing import Protocol
from urllib.parse import urlencode, urlsplit

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from edge.verification import (
    ApplicationIdentityVerifier,
    HttpJwksFetcher,
    VerificationResult,
)
from fixtures.identity import VERIFIED_IDENTITY_HEADER


_FIXTURE_MODES = {
    "fixture-authenticated": "authenticated",
    "fixture-public": "public",
    "fixture-restricted": "restricted",
}
_QUALIFICATION_CHALLENGE = re.compile(r"[0-9a-f]{64}")
_SAFE_IDENTITY_DIAGNOSTICS = {
    "assertion_key_unknown": "assertion_key_unknown",
    "assertion_malformed": "assertion_malformed",
    "assertion_missing": "assertion_missing",
    "assertion_signature_invalid": "assertion_signature_invalid",
    "identity_audience_invalid": "identity_audience_invalid",
    "identity_clock_invalid": "identity_clock_invalid",
    "identity_contract_invalid": "identity_contract_invalid",
    "identity_expired": "identity_expired",
    "identity_issuer_invalid": "identity_issuer_invalid",
    "identity_lifetime_invalid": "identity_lifetime_invalid",
    "identity_not_yet_valid": "identity_not_yet_valid",
    "verification_keys_unavailable": "verification_keys_unavailable",
}


def _write_identity_rejection(application_id: str, code: str) -> None:
    safe_code = _SAFE_IDENTITY_DIAGNOSTICS.get(
        code,
        "identity_verification_rejected",
    )
    event = json.dumps(
        {
            "application_id": application_id,
            "diagnostic_code": safe_code,
            "event": "fixture_identity_rejected",
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    sys.stderr.write(event + "\n")


class NetworkIdentityVerifier(Protocol):
    async def verify(self, assertion: str | None) -> VerificationResult: ...


@dataclass(frozen=True, slots=True)
class NetworkFixtureConfiguration:
    """Exact non-secret runtime configuration for one fixture image instance."""

    application_id: str
    admission_mode: str
    platform_issuer: str
    public_key_reference: str
    assertion_audience: str | None

    def __post_init__(self) -> None:
        if _FIXTURE_MODES.get(self.application_id) != self.admission_mode:
            raise ValueError("application and admission mode must select one fixture profile")
        issuer = urlsplit(self.platform_issuer)
        if (
            issuer.scheme != "https"
            or not issuer.netloc
            or issuer.path != "/_platform"
            or issuer.query
            or issuer.fragment
            or issuer.username is not None
            or issuer.password is not None
        ):
            raise ValueError("platform issuer must be the exact HTTPS platform issuer")
        expected_keys = (
            f"{issuer.scheme}://{issuer.netloc}/.well-known/jwks.json"
        )
        if self.public_key_reference != expected_keys:
            raise ValueError("public key reference must match the platform issuer")
        expected_audience = (
            "urn:comfforts:app-platform:audience:"
            f"{self.application_id}"
        )
        if (
            self.admission_mode == "public"
            and self.assertion_audience not in {None, expected_audience}
        ) or (
            self.admission_mode != "public"
            and self.assertion_audience != expected_audience
        ):
            raise ValueError("assertion audience must match the fixture profile")

    @classmethod
    def from_environment(cls) -> NetworkFixtureConfiguration:
        required = (
            "APP_PLATFORM_APPLICATION_ID",
            "APP_PLATFORM_ADMISSION_MODE",
            "APP_PLATFORM_ISSUER",
            "APP_PLATFORM_PUBLIC_KEY_REFERENCE",
        )
        try:
            values = {name: os.environ[name] for name in required}
        except KeyError as error:
            raise ValueError("network fixture environment is incomplete") from error
        return cls(
            application_id=values["APP_PLATFORM_APPLICATION_ID"],
            admission_mode=values["APP_PLATFORM_ADMISSION_MODE"],
            platform_issuer=values["APP_PLATFORM_ISSUER"],
            public_key_reference=values["APP_PLATFORM_PUBLIC_KEY_REFERENCE"],
            assertion_audience=os.environ.get("APP_PLATFORM_ASSERTION_AUDIENCE"),
        )


@dataclass(frozen=True, slots=True)
class _SystemAssertionClock:
    def now(self) -> int:
        return int(time.time())


@dataclass(frozen=True, slots=True)
class _BoundedJwksFetcher:
    jwks_url: str
    transport: httpx.AsyncBaseTransport | None = None
    retry_delay_seconds: float = 0.25

    def __post_init__(self) -> None:
        if not 0 <= self.retry_delay_seconds <= 1:
            raise ValueError("JWKS retry delay is outside the bounded range")

    async def fetch(self) -> dict[str, object]:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(
                    follow_redirects=False,
                    timeout=httpx.Timeout(5.0),
                    transport=self.transport,
                ) as client:
                    return await HttpJwksFetcher(client, self.jwks_url).fetch()
            except httpx.HTTPError:
                if attempt == 1:
                    raise
                await asyncio.sleep(self.retry_delay_seconds)
        raise AssertionError("bounded JWKS retry exhausted unexpectedly")


def _fixed_response(application_id: str, outcome: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"application_id": application_id, "outcome": outcome},
        status_code=status,
    )


def create_network_fixture(
    configuration: NetworkFixtureConfiguration,
    *,
    verifier: NetworkIdentityVerifier | None = None,
) -> Starlette:
    """Create one networked fixture without provider or Platform State access."""

    identity_required = configuration.admission_mode != "public"
    identity_enabled = configuration.assertion_audience is not None
    if identity_enabled and verifier is None:
        raise ValueError("identity-enabled fixture requires an identity verifier")
    if not identity_enabled and verifier is not None:
        raise ValueError("identity-disabled fixture cannot receive an identity verifier")

    async def admitted(headers: object) -> bool:
        if not identity_enabled:
            return True
        getlist = getattr(headers, "getlist", None)
        if not callable(getlist):
            return False
        assertions = getlist(VERIFIED_IDENTITY_HEADER)
        if len(assertions) > 1:
            return False
        assertion = assertions[0] if assertions else None
        if assertion is None and not identity_required:
            return True
        assert verifier is not None
        result = await verifier.verify(assertion)
        if not result.accepted or result.identity is None:
            _write_identity_rejection(configuration.application_id, result.code)
            return False
        return True

    async def health(request: Request) -> Response:
        del request
        return _fixed_response(configuration.application_id, "healthy", 200)

    async def http_probe(request: Request) -> Response:
        if not await admitted(request.headers):
            return _fixed_response(
                configuration.application_id,
                "identity-denied",
                401,
            )
        path = request.path_params.get("path", "")
        if path == "qualification/browser" and request.method == "GET":
            challenge_values = request.query_params.getlist("challenge")
            port_values = request.query_params.getlist("callback_port")
            if (
                len(challenge_values) != 1
                or len(port_values) != 1
                or _QUALIFICATION_CHALLENGE.fullmatch(challenge_values[0]) is None
            ):
                return _fixed_response(
                    configuration.application_id,
                    "qualification-challenge-invalid",
                    400,
                )
            try:
                callback_port = int(port_values[0])
            except ValueError:
                callback_port = 0
            if not 1024 <= callback_port <= 65535:
                return _fixed_response(
                    configuration.application_id,
                    "qualification-challenge-invalid",
                    400,
                )
            location = "http://127.0.0.1:" + str(callback_port) + "/?" + urlencode(
                {
                    "application_id": configuration.application_id,
                    "challenge": challenge_values[0],
                }
            )
            return RedirectResponse(
                location,
                status_code=303,
                headers={"Cache-Control": "no-store"},
            )
        if path in {"", "api"} and request.method == "GET":
            return _fixed_response(
                configuration.application_id,
                "fixture-ready",
                200,
            )
        if path == "upload" and request.method == "POST":
            async for _ in request.stream():
                pass
            return Response(status_code=204)
        if path == "stream" and request.method == "GET":
            async def body():
                yield b"fixture-stream-1\n"
                yield b"fixture-stream-2\n"

            return StreamingResponse(body(), media_type="text/plain")
        if path == "failure" and request.method == "GET":
            return _fixed_response(
                configuration.application_id,
                "synthetic-failure",
                503,
            )
        return _fixed_response(configuration.application_id, "not-found", 404)

    async def websocket_probe(websocket: WebSocket) -> None:
        if not await admitted(websocket.headers):
            await websocket.close(code=4401, reason="identity denied")
            return
        await websocket.accept()
        await websocket.receive_text()
        await websocket.send_text("fixture-ready")
        await websocket.close(code=1000)

    return Starlette(
        routes=[
            Route("/healthz", health, methods=["GET"]),
            WebSocketRoute("/socket", websocket_probe),
            Route(
                "/{path:path}",
                http_probe,
                methods=["GET", "POST"],
            ),
        ]
    )


def create_environment_app() -> Starlette:
    """Uvicorn factory for one exact environment-selected fixture profile."""

    configuration = NetworkFixtureConfiguration.from_environment()
    verifier: NetworkIdentityVerifier | None = None
    if configuration.assertion_audience is not None:
        verifier = ApplicationIdentityVerifier(
            expected_issuer=configuration.platform_issuer,
            expected_audience=configuration.assertion_audience,
            key_fetcher=_BoundedJwksFetcher(configuration.public_key_reference),
            clock=_SystemAssertionClock(),
        )
    return create_network_fixture(configuration, verifier=verifier)


__all__ = (
    "NetworkFixtureConfiguration",
    "NetworkIdentityVerifier",
    "create_environment_app",
    "create_network_fixture",
)
