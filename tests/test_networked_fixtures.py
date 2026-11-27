"""AP-M9-W8 networked Fixture Application runtime tests."""

from __future__ import annotations

import asyncio
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings

import httpx

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
    category=UserWarning,
)
from starlette.testclient import TestClient

from edge.verification import VerificationResult, VerifiedIdentityContext
from fixtures.identity import VERIFIED_IDENTITY_HEADER
from fixtures.networked import (
    NetworkFixtureConfiguration,
    _BoundedJwksFetcher,
    create_environment_app,
    create_network_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeVerifier:
    def __init__(
        self,
        accepted: bool = True,
        rejection_code: str = "assertion_signature_invalid",
    ) -> None:
        self.accepted = accepted
        self.rejection_code = rejection_code
        self.assertions: list[str | None] = []

    async def verify(self, assertion: str | None) -> VerificationResult:
        self.assertions.append(assertion)
        if not self.accepted or assertion is None:
            return VerificationResult(False, self.rejection_code, None)
        return VerificationResult(
            True,
            "identity_verified",
            VerifiedIdentityContext(
                contract_version=2,
                issuer="https://apps-staging.comfforts.com/_platform",
                subject="synthetic-subject",
                audience=(
                    "urn:comfforts:app-platform:audience:fixture-authenticated"
                ),
                issued_at=1_800_000_000,
                expires_at=1_800_000_060,
                correlation_id="synthetic-correlation",
                platform_member=True,
            ),
        )


def configuration(mode: str) -> NetworkFixtureConfiguration:
    return NetworkFixtureConfiguration(
        application_id=f"fixture-{mode}",
        admission_mode=mode,
        platform_issuer="https://apps-staging.comfforts.com/_platform",
        public_key_reference=(
            "https://apps-staging.comfforts.com/.well-known/jwks.json"
        ),
        assertion_audience=(
            None
            if mode == "public"
            else f"urn:comfforts:app-platform:audience:fixture-{mode}"
        ),
    )


class NetworkedFixtureTest(unittest.TestCase):
    def test_jwks_fetch_retries_one_transient_http_failure(self) -> None:
        requests = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal requests
            requests += 1
            if requests == 1:
                return httpx.Response(503, request=request)
            return httpx.Response(
                200,
                json={"keys": [{"kid": "synthetic"}]},
                request=request,
            )

        result = asyncio.run(
            _BoundedJwksFetcher(
                "https://apps-staging.comfforts.com/.well-known/jwks.json",
                transport=httpx.MockTransport(handler),
                retry_delay_seconds=0,
            ).fetch()
        )

        self.assertEqual(result, {"keys": [{"kid": "synthetic"}]})
        self.assertEqual(requests, 2)

    def test_public_fixture_exposes_fixed_probe_surfaces_without_identity(self) -> None:
        app = create_network_fixture(configuration("public"))

        with TestClient(app) as client:
            root = client.get("/")
            api = client.get("/api")
            uploaded = client.post("/upload", content=b"synthetic")
            stream = client.get("/stream")
            failure = client.get("/failure")
            missing = client.get("/unknown")

        self.assertEqual(root.status_code, 200)
        self.assertEqual(
            root.json(),
            {"application_id": "fixture-public", "outcome": "fixture-ready"},
        )
        self.assertEqual(api.status_code, 200)
        self.assertEqual(uploaded.status_code, 204)
        self.assertEqual(stream.status_code, 200)
        self.assertEqual(stream.text, "fixture-stream-1\nfixture-stream-2\n")
        self.assertEqual(failure.status_code, 503)
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn("synthetic", repr(root.headers).lower())

    def test_public_optional_accepts_anonymous_or_verified_platform_identity(self) -> None:
        optional = NetworkFixtureConfiguration(
            application_id="fixture-public",
            admission_mode="public",
            platform_issuer="https://apps-staging.comfforts.com/_platform",
            public_key_reference=(
                "https://apps-staging.comfforts.com/.well-known/jwks.json"
            ),
            assertion_audience=(
                "urn:comfforts:app-platform:audience:fixture-public"
            ),
        )
        verifier = FakeVerifier()
        app = create_network_fixture(optional, verifier=verifier)

        with TestClient(app) as client:
            anonymous = client.get("/")
            verified = client.get(
                "/",
                headers={VERIFIED_IDENTITY_HEADER: "synthetic.assertion.value"},
            )

        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verifier.assertions, ["synthetic.assertion.value"])

    def test_browser_qualification_returns_only_a_loopback_challenge(self) -> None:
        app = create_network_fixture(configuration("public"))
        challenge = "a" * 64

        with TestClient(app) as client:
            accepted = client.get(
                "/qualification/browser",
                params={"callback_port": "43210", "challenge": challenge},
                follow_redirects=False,
            )
            invalid = client.get(
                "/qualification/browser",
                params={"callback_port": "80", "challenge": challenge},
                follow_redirects=False,
            )
            unexpected_delivery = client.get(
                "/qualification/browser",
                params={"callback_port": "43210", "challenge": challenge},
                headers={VERIFIED_IDENTITY_HEADER: "unexpected.delivery"},
                follow_redirects=False,
            )

        self.assertEqual(accepted.status_code, 303)
        self.assertEqual(
            accepted.headers["location"],
            "http://127.0.0.1:43210/?"
            "application_id=fixture-public&challenge="
            + challenge
            + "&identity_present=false",
        )
        self.assertEqual(accepted.headers["cache-control"], "no-store")
        self.assertEqual(invalid.status_code, 400)
        self.assertTrue(
            unexpected_delivery.headers["location"].endswith(
                "&identity_present=true"
            )
        )
        self.assertNotIn("unexpected.delivery", unexpected_delivery.headers["location"])

    def test_browser_qualification_reports_only_verified_identity_presence(self) -> None:
        """Return a coarse marker without exposing the verified identity context."""

        optional = NetworkFixtureConfiguration(
            application_id="fixture-public",
            admission_mode="public",
            platform_issuer="https://apps-staging.comfforts.com/_platform",
            public_key_reference=(
                "https://apps-staging.comfforts.com/.well-known/jwks.json"
            ),
            assertion_audience=(
                "urn:comfforts:app-platform:audience:fixture-public"
            ),
        )
        app = create_network_fixture(optional, verifier=FakeVerifier())
        challenge = "b" * 64

        with TestClient(app) as client:
            response = client.get(
                "/qualification/browser",
                params={"callback_port": "43210", "challenge": challenge},
                headers={VERIFIED_IDENTITY_HEADER: "synthetic.assertion.value"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            response.headers["location"],
            "http://127.0.0.1:43210/?"
            "application_id=fixture-public&challenge="
            + challenge
            + "&identity_present=true",
        )
        self.assertNotIn("synthetic-subject", response.headers["location"])

    def test_protected_fixture_requires_one_independently_verified_assertion(self) -> None:
        verifier = FakeVerifier()
        app = create_network_fixture(
            configuration("authenticated"),
            verifier=verifier,
        )

        with redirect_stderr(io.StringIO()), TestClient(app) as client:
            missing = client.get("/")
            accepted = client.get(
                "/",
                headers={VERIFIED_IDENTITY_HEADER: "synthetic.assertion.value"},
            )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(
            verifier.assertions,
            [None, "synthetic.assertion.value"],
        )
        self.assertNotIn("synthetic-subject", accepted.text)
        self.assertNotIn("assertion", accepted.text.lower())

    def test_rejected_assertion_and_duplicate_identity_header_fail_closed(self) -> None:
        verifier = FakeVerifier(accepted=False)
        app = create_network_fixture(
            configuration("restricted"),
            verifier=verifier,
        )

        with redirect_stderr(io.StringIO()), TestClient(app) as client:
            rejected = client.get(
                "/",
                headers={VERIFIED_IDENTITY_HEADER: "rejected.assertion.value"},
            )
            duplicate = client.get(
                "/",
                headers=[
                    (VERIFIED_IDENTITY_HEADER, "first.assertion.value"),
                    (VERIFIED_IDENTITY_HEADER, "second.assertion.value"),
                ],
            )

        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(duplicate.status_code, 401)
        self.assertEqual(verifier.assertions, ["rejected.assertion.value"])

    def test_identity_rejection_logs_only_the_allowlisted_verifier_code(self) -> None:
        verifier = FakeVerifier(
            accepted=False,
            rejection_code="verification_keys_unavailable",
        )
        app = create_network_fixture(
            configuration("authenticated"),
            verifier=verifier,
        )
        stderr = io.StringIO()

        with redirect_stderr(stderr), TestClient(app) as client:
            response = client.get(
                "/",
                headers={VERIFIED_IDENTITY_HEADER: "sensitive.assertion.value"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            json.loads(stderr.getvalue()),
            {
                "application_id": "fixture-authenticated",
                "diagnostic_code": "verification_keys_unavailable",
                "event": "fixture_identity_rejected",
            },
        )
        self.assertNotIn("sensitive.assertion.value", stderr.getvalue())

    def test_websocket_uses_the_same_admission_boundary(self) -> None:
        public = create_network_fixture(configuration("public"))
        protected = create_network_fixture(
            configuration("authenticated"),
            verifier=FakeVerifier(),
        )

        with TestClient(public) as client:
            with client.websocket_connect("/socket") as socket:
                socket.send_text("synthetic-input")
                self.assertEqual(socket.receive_text(), "fixture-ready")
        with redirect_stderr(io.StringIO()), TestClient(protected) as client:
            with self.assertRaises(Exception):
                with client.websocket_connect("/socket"):
                    pass

    def test_environment_factory_accepts_only_exact_fixture_profiles(self) -> None:
        values = {
            "APP_PLATFORM_APPLICATION_ID": "fixture-authenticated",
            "APP_PLATFORM_ADMISSION_MODE": "authenticated",
            "APP_PLATFORM_ISSUER": (
                "https://apps-staging.comfforts.com/_platform"
            ),
            "APP_PLATFORM_PUBLIC_KEY_REFERENCE": (
                "https://apps-staging.comfforts.com/.well-known/jwks.json"
            ),
            "APP_PLATFORM_ASSERTION_AUDIENCE": (
                "urn:comfforts:app-platform:audience:fixture-authenticated"
            ),
        }
        with mock.patch.dict(os.environ, values, clear=True):
            app = create_environment_app()
        self.assertIsNotNone(app)

        invalid = {**values, "APP_PLATFORM_APPLICATION_ID": "real-application"}
        with mock.patch.dict(os.environ, invalid, clear=True):
            with self.assertRaisesRegex(ValueError, "fixture profile"):
                create_environment_app()

    def test_container_definition_requires_digest_bound_build_and_runtime_images(self) -> None:
        dockerfile = (
            PROJECT_ROOT / "infrastructure/images/fixture/Dockerfile"
        ).read_text(encoding="utf-8")

        self.assertIn("ARG UV_IMAGE", dockerfile)
        self.assertIn("ARG PYTHON_BUILD_IMAGE", dockerfile)
        self.assertIn("ARG PYTHON_RUNTIME_IMAGE", dockerfile)
        self.assertIn("FROM ${UV_IMAGE} AS uv", dockerfile)
        self.assertIn("FROM ${PYTHON_BUILD_IMAGE} AS build", dockerfile)
        self.assertIn("COPY --from=uv /uv /uvx /bin/", dockerfile)
        self.assertIn("FROM ${PYTHON_RUNTIME_IMAGE}", dockerfile)
        self.assertIn("uv sync --frozen", dockerfile)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn(
            "fixtures.networked:create_environment_app",
            dockerfile,
        )
        self.assertNotIn("COPY . ", dockerfile)
        self.assertNotIn("latest", dockerfile.lower())

        cloudbuild = (
            PROJECT_ROOT / "infrastructure/images/fixture/cloudbuild.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("gcr.io/cloud-builders/docker@sha256:", cloudbuild)
        self.assertIn("UV_IMAGE=ghcr.io/astral-sh/uv@sha256:", cloudbuild)
        self.assertIn("PYTHON_BUILD_IMAGE=python@sha256:", cloudbuild)
        self.assertIn("PYTHON_RUNTIME_IMAGE=python@sha256:", cloudbuild)
        self.assertIn("org.opencontainers.image.revision=${_SOURCE_REVISION}", cloudbuild)
        self.assertIn(
            '_SOURCE_REVISION: "0000000000000000000000000000000000000000"',
            cloudbuild,
        )
        self.assertNotIn("latest", cloudbuild.lower())

        upload_allowlist = (PROJECT_ROOT / ".gcloudignore").read_text(
            encoding="utf-8"
        )
        for required in (
            "!fixtures/",
            "!fixtures/*.py",
            "!infrastructure/images/fixture/Dockerfile",
            "!infrastructure/images/fixture/cloudbuild.yaml",
        ):
            self.assertIn(required, upload_allowlist)

    def test_fixture_image_package_set_loads_without_platform_infrastructure(self) -> None:
        """Prove the application image can construct its ASGI app in isolation."""

        with tempfile.TemporaryDirectory() as directory:
            image_root = Path(directory)
            for package in ("contracts", "edge", "fixtures"):
                shutil.copytree(PROJECT_ROOT / package, image_root / package)
            environment = {
                "APP_PLATFORM_APPLICATION_ID": "fixture-public",
                "APP_PLATFORM_ADMISSION_MODE": "public",
                "APP_PLATFORM_ISSUER": (
                    "https://apps-staging.comfforts.com/_platform"
                ),
                "APP_PLATFORM_PUBLIC_KEY_REFERENCE": (
                    "https://apps-staging.comfforts.com/.well-known/jwks.json"
                ),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            result = subprocess.run(
                (
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import sys; "
                        "sys.path.insert(0, '.'); "
                        "from fixtures.networked import create_environment_app; "
                        "assert create_environment_app() is not None"
                    ),
                ),
                cwd=image_root,
                env=environment,
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
