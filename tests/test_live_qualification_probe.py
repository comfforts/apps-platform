"""Exact live qualification probe behavior through deterministic adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import unittest

from infrastructure.operator.integration import AttachmentTargetReadback
from infrastructure.operator.live_qualification import (
    BrowserQualificationResult,
    QualificationHttpResponse,
    StagingQualificationProbe,
)
from infrastructure.operator.qualification import QualificationProbeRequest
from infrastructure.operator.project_connections import (
    ApplicationProjectReadback,
    NETWORK_REFERENCE,
    PLATFORM_PROJECT_ID,
    SUBNETWORK_REFERENCE,
)
from tests.environment import FIXTURES_PROJECT_ID
from tests.test_qualification_suite import readback


@dataclass
class Browser:
    result: BrowserQualificationResult = BrowserQualificationResult(True, True, True)
    calls: int = 0

    def verify(self) -> BrowserQualificationResult:
        self.calls += 1
        return self.result


class Http:
    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes = b"",
        insecure_http: bool = False,
    ) -> QualificationHttpResponse:
        del body
        if insecure_http:
            return QualificationHttpResponse(
                301,
                {"location": "https://apps-staging.comfforts.com/"},
                b"",
            )
        if path in {"/fixture-authenticated", "/fixture-restricted"}:
            return QualificationHttpResponse(
                303,
                {"location": "/_platform/auth/login?return_to=" + path},
                b"",
            )
        if path == "/.well-known/jwks.json":
            return QualificationHttpResponse(
                200,
                {},
                json.dumps({"keys": [{"kid": "kms-1", "kty": "EC"}]}).encode(),
            )
        if path == "/":
            return QualificationHttpResponse(
                200,
                {},
                b"Public fixture Restricted fixture",
            )
        if path == "/fixture-public/upload":
            return QualificationHttpResponse(204, {}, b"")
        if path == "/fixture-public/stream":
            return QualificationHttpResponse(
                200,
                {},
                b"fixture-stream-1\nfixture-stream-2\n",
            )
        if path == "/fixture-public/failure":
            return QualificationHttpResponse(503, {}, b"")
        return QualificationHttpResponse(
            200,
            {},
            json.dumps(
                {"application_id": "fixture-public", "outcome": "fixture-ready"}
            ).encode(),
        )

    def websocket(self, path: str) -> bool:
        return path == "/fixture-public/socket"


class Targets:
    def read_target(self, environment: str, resource_reference: str):  # type: ignore[no-untyped-def]
        application_id = resource_reference.rsplit(":", maxsplit=1)[1]
        return AttachmentTargetReadback(
            True,
            True,
            application_id,
            "gcp-cloud-run-v1",
            resource_reference,
            "shared_edge_only",
            (
                "serviceAccount:app-platform-edge-caller@"
                "comfforts-platform-non-prod.iam.gserviceaccount.com"
            ),
            (
                None
                if application_id == "fixture-public"
                else f"urn:comfforts:app-platform:audience:{application_id}"
            ),
            application_project_id=FIXTURES_PROJECT_ID,
            network_reference=NETWORK_REFERENCE,
            subnetwork_reference=SUBNETWORK_REFERENCE,
            egress_mode="all-traffic",
        )


@dataclass
class Lifecycle:
    verified: bool = True

    def verify_rollback(self, environment: str, generation_digest: str) -> bool:
        return environment == "staging" and bool(generation_digest) and self.verified


class LiveQualificationProbeTest(unittest.TestCase):
    @staticmethod
    def _fixture_project() -> ApplicationProjectReadback:
        return ApplicationProjectReadback(
            project_id=FIXTURES_PROJECT_ID,
            exists=True,
            project_number="123456789012",
            state_bucket_ready=True,
            artifact_repository_ready=True,
            host_project_id=PLATFORM_PROJECT_ID,
            network_viewer_granted=True,
            subnet_user_granted=True,
            fixture_ownership_matches=True,
        )

    @staticmethod
    def _current():  # type: ignore[no-untyped-def]
        current = readback()
        return replace(
            current,
            fixture_revisions=tuple(
                replace(
                    item,
                    attachment_bundle_digest=(
                        "sha256:" + item.attachment_bundle_digest[7:].lower()
                    ),
                )
                for item in current.fixture_revisions
            ),
        )

    def test_all_closed_checks_pass_through_exact_live_adapters(self) -> None:
        browser = Browser()
        current = self._current()
        probe = StagingQualificationProbe(
            Http(),
            browser,
            Targets(),
            Lifecycle(),
            self._fixture_project(),
        )  # type: ignore[arg-type]
        checks = (
            "admission-identity",
            "assertion-jwks",
            "attachment-posture",
            "catalogue-routing",
            "direct-origin-denial",
            "dns-tls",
            "isolation-limits",
            "lifecycle-rollback",
            "redaction",
            "source-integrity",
        )

        results = [
            probe.evaluate(QualificationProbeRequest(check, (), current))
            for check in checks
        ]

        self.assertTrue(all(item.outcome == "pass" for item in results))
        self.assertEqual(browser.calls, 1)
        self.assertTrue(all(not item.blockers for item in results))

    def test_browser_or_provider_mismatch_fails_with_coarse_blocker(self) -> None:
        current = self._current()
        probe = StagingQualificationProbe(
            Http(),
            Browser(BrowserQualificationResult(False, False, False)),
            Targets(),
            Lifecycle(),
            self._fixture_project(),
        )  # type: ignore[arg-type]

        result = probe.evaluate(
            QualificationProbeRequest("admission-identity", (), current)
        )

        self.assertEqual(result.outcome, "fail")
        self.assertEqual(result.blockers, ("LIVE_ADMISSION_IDENTITY_MISMATCH",))
        self.assertNotIn("cookie", repr(result.observation).lower())

    def test_attachment_qualification_requires_live_project_connection(self) -> None:
        probe = StagingQualificationProbe(
            Http(),
            Browser(),
            Targets(),
            Lifecycle(),
            replace(self._fixture_project(), subnet_user_granted=False),
        )  # type: ignore[arg-type]

        result = probe.evaluate(
            QualificationProbeRequest(
                "attachment-posture",
                (),
                self._current(),
            )
        )

        self.assertEqual(result.outcome, "fail")
        self.assertEqual(result.blockers, ("LIVE_ATTACHMENT_POSTURE_MISMATCH",))


if __name__ == "__main__":
    unittest.main()
