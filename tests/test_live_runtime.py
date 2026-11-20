"""Production Shared Edge composition tests without provider or network access."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import unittest

import google_crc32c
import httpx

from edge.live import (
    LiveClients,
    LiveConfigurationError,
    LiveRuntimeSettings,
    access_oauth_client_secret,
    build_live_app,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _environment() -> dict[str, str]:
    return {
        "APP_PLATFORM_CONFIGURATION_BUCKET": "comfforts-platform-configuration",
        "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST": "sha256:" + "1" * 64,
        "APP_PLATFORM_CONFIGURATION_OBJECT": "generations/1/compiled.json",
        "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION": "17",
        "APP_PLATFORM_EDGE_CALLER_PRINCIPAL": (
            "serviceAccount:app-platform-edge-caller@"
            "comfforts-platform-non-prod.iam.gserviceaccount.com"
        ),
        "APP_PLATFORM_GENERATION_DIGEST": "sha256:" + "2" * 64,
        "APP_PLATFORM_ISSUER": "https://apps-staging.comfforts.com/_platform",
        "APP_PLATFORM_OAUTH_CLIENT_ID": "client.apps.googleusercontent.com",
        "APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION": (
            "projects/comfforts-platform-non-prod/secrets/"
            "app-platform-edge-oauth/versions/3"
        ),
        "APP_PLATFORM_OPERATOR_ISSUER": "https://accounts.google.com",
        "APP_PLATFORM_OPERATOR_SUBJECT": "123456789012345678901",
        "APP_PLATFORM_PROJECT_ID": "comfforts-platform-non-prod",
        "APP_PLATFORM_REGION": "us-west1",
        "APP_PLATFORM_SIGNING_KEY_VERSION": (
            "projects/comfforts-platform-non-prod/locations/us-west1/keyRings/"
            "app-platform/cryptoKeys/edge-signing/cryptoKeyVersions/1"
        ),
        "APP_PLATFORM_SOURCE_REVISION": "a" * 40,
    }


class _Response:
    def __init__(self, payload: bytes, *, crc: int | None = None) -> None:
        self._payload = payload
        self._crc = google_crc32c.value(payload) if crc is None else crc

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "payload": {
                "data": base64.b64encode(self._payload).decode("ascii"),
                "dataCrc32c": str(self._crc),
            }
        }


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.requests: list[tuple[str, int]] = []

    def get(self, url: str, timeout: int) -> _Response:
        self.requests.append((url, timeout))
        return self.response


class LiveRuntimeTest(unittest.TestCase):
    def test_shared_edge_image_starts_only_the_live_factory_as_nonroot(self) -> None:
        dockerfile = (
            PROJECT_ROOT / "infrastructure/images/shared-edge/Dockerfile"
        ).read_text(encoding="utf-8")
        build = (
            PROJECT_ROOT / "infrastructure/images/shared-edge/cloudbuild.yaml"
        ).read_text(encoding="utf-8")

        self.assertIn("ARG UV_IMAGE", dockerfile)
        self.assertIn("ARG PYTHON_BUILD_IMAGE", dockerfile)
        self.assertIn("COPY --from=uv /uv /uvx /bin/", dockerfile)
        self.assertIn("uv sync --frozen --no-dev --no-editable", dockerfile)
        self.assertIn("COPY contracts ./contracts", dockerfile)
        self.assertIn("COPY edge ./edge", dockerfile)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn(
            '"edge.live:create_live_app", "--factory"',
            dockerfile,
        )
        self.assertNotIn("COPY . ", dockerfile)
        self.assertNotIn(".platform-operator", dockerfile)
        self.assertEqual(build.count("@sha256:"), 4)
        self.assertNotIn(":latest", build)
        self.assertIn("--tag=${_IMAGE}", build)
        self.assertIn("source-revision-required", build)

    def test_settings_bind_exact_revision_generation_project_and_operator(self) -> None:
        settings = LiveRuntimeSettings.from_environment(_environment())

        self.assertEqual(settings.project_id, "comfforts-platform-non-prod")
        self.assertEqual(settings.external_origin, "https://apps-staging.comfforts.com")
        self.assertEqual(settings.generation_object_generation, 17)
        self.assertEqual(settings.key_id, "kms-1")
        runtime = settings.runtime_configuration()
        self.assertEqual(runtime.source_revision, "a" * 40)
        self.assertEqual(runtime.generation_digest, "sha256:" + "2" * 64)

    def test_settings_fail_closed_for_missing_or_cross_project_values(self) -> None:
        cases = []
        missing = _environment()
        del missing["APP_PLATFORM_OPERATOR_SUBJECT"]
        cases.append(missing)
        wrong_secret_project = _environment()
        wrong_secret_project["APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION"] = (
            "projects/other-platform/secrets/app-platform-edge-oauth/versions/3"
        )
        cases.append(wrong_secret_project)
        wrong_issuer = _environment()
        wrong_issuer["APP_PLATFORM_OPERATOR_ISSUER"] = "https://issuer.example.invalid"
        cases.append(wrong_issuer)

        for environment in cases:
            with self.subTest(environment=environment), self.assertRaises(
                LiveConfigurationError
            ):
                LiveRuntimeSettings.from_environment(environment)

    def test_secret_access_uses_exact_version_and_crc_without_echoing_payload(self) -> None:
        version = _environment()["APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION"]
        session = _Session(_Response(b"private-oauth-secret"))

        secret = access_oauth_client_secret(version, session)

        self.assertEqual(secret, "private-oauth-secret")
        self.assertEqual(
            session.requests,
            [
                (
                    "https://secretmanager.googleapis.com/v1/"
                    f"{version}:access",
                    20,
                )
            ],
        )
        failing = _Session(_Response(b"private-oauth-secret", crc=1))
        with self.assertRaises(LiveConfigurationError) as captured:
            access_oauth_client_secret(version, failing)
        self.assertEqual(str(captured.exception), "OAUTH_SECRET_ACCESS_FAILED")
        self.assertNotIn("private-oauth-secret", str(captured.exception))

    def test_live_factory_composes_production_adapters_without_io(self) -> None:
        settings = LiveRuntimeSettings.from_environment(_environment())
        http = httpx.AsyncClient()
        try:
            app = build_live_app(
                settings,
                LiveClients(
                    storage=object(),
                    firestore=object(),
                    cloud_run=object(),
                    kms=object(),
                    auth_request=object(),
                    http=http,
                ),
                "private-oauth-secret",
            )
        finally:
            asyncio.run(http.aclose())

        self.assertTrue(callable(app))


if __name__ == "__main__":
    unittest.main()
