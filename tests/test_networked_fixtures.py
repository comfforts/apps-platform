"""AP-M9-W8 networked Fixture Application runtime tests."""

from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest import mock
import warnings

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
    create_environment_app,
    create_network_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeVerifier:
    def __init__(self, accepted: bool = True) -> None:
        self.accepted = accepted
        self.assertions: list[str | None] = []

    async def verify(self, assertion: str | None) -> VerificationResult:
        self.assertions.append(assertion)
        if not self.accepted or assertion is None:
            return VerificationResult(False, "assertion_signature_invalid", None)
        return VerificationResult(
            True,
            "identity_verified",
            VerifiedIdentityContext(
                contract_version=1,
                issuer="https://apps-staging.comfforts.com/_platform",
                subject="synthetic-subject",
                audience=(
                    "urn:comfforts:app-platform:audience:fixture-authenticated"
                ),
                issued_at=1_800_000_000,
                expires_at=1_800_000_060,
                correlation_id="synthetic-correlation",
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

    def test_protected_fixture_requires_one_independently_verified_assertion(self) -> None:
        verifier = FakeVerifier()
        app = create_network_fixture(
            configuration("authenticated"),
            verifier=verifier,
        )

        with TestClient(app) as client:
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

        with TestClient(app) as client:
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
        with TestClient(protected) as client:
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

        self.assertIn("ARG UV_BUILD_IMAGE", dockerfile)
        self.assertIn("ARG PYTHON_RUNTIME_IMAGE", dockerfile)
        self.assertIn("FROM ${UV_BUILD_IMAGE} AS build", dockerfile)
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
        self.assertIn("UV_BUILD_IMAGE=ghcr.io/astral-sh/uv@sha256:", cloudbuild)
        self.assertIn("PYTHON_RUNTIME_IMAGE=python@sha256:", cloudbuild)
        self.assertIn("org.opencontainers.image.revision=${_SOURCE_REVISION}", cloudbuild)
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


if __name__ == "__main__":
    unittest.main()
