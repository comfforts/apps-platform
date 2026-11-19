"""Deterministic AP-M9-W7 application-integration behavior."""

from __future__ import annotations

import copy
from dataclasses import replace
import unittest

from contracts.lifecycle import (
    lifecycle_digest,
    validate_lifecycle_document,
)
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    IntegrationBundleRequest,
    PlatformIntegrationState,
)


SOURCE_REVISION = "a" * 40
PROFILE_DIGEST = "sha256:" + ("1" * 64)
SPECIFICATION_DIGEST = "sha256:" + ("2" * 64)
JOURNAL_DIGEST = "sha256:" + ("3" * 64)
EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)
OAUTH_CLIENT_ID = "1234567890-appsplatform.apps.googleusercontent.com"


class FakePlatformReader:
    def __init__(self, state: PlatformIntegrationState) -> None:
        self.state = state
        self.requests: list[str] = []

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        self.requests.append(environment)
        return self.state


def _state() -> PlatformIntegrationState:
    return PlatformIntegrationState(
        environment="staging",
        lifecycle_state="deployed",
        profile_digest=PROFILE_DIGEST,
        platform_source_revision=SOURCE_REVISION,
        specification_digest=SPECIFICATION_DIGEST,
        journal_digest=JOURNAL_DIGEST,
        generation=7,
        hostname="apps-staging.comfforts.com",
        oauth_client_id=OAUTH_CLIENT_ID,
        edge_caller_reference=EDGE_CALLER,
        qualification_status="unqualified",
    )


def _request(access_mode: str) -> IntegrationBundleRequest:
    return IntegrationBundleRequest(
        environment="staging",
        application_id=f"fixture-{access_mode}",
        access_mode=access_mode,
        route_intent=f"/fixture-{access_mode}",
        expected_platform_source_revision=SOURCE_REVISION,
        expected_generation=7,
    )


class PlatformOutputsTest(unittest.TestCase):
    def test_public_bundle_is_a_least_data_projection(self) -> None:
        reader = FakePlatformReader(_state())
        lifecycle = ApplicationIntegrationLifecycle(reader)

        result = lifecycle.outputs(_request("public"))

        self.assertEqual(result.outcome, "generated")
        self.assertEqual(result.blockers, ())
        self.assertIsNotNone(result.bundle)
        assert result.bundle is not None
        self.assertEqual(
            validate_lifecycle_document(
                result.bundle,
                "platform-integration-bundle",
            ),
            (),
        )
        self.assertEqual(
            result.bundle_digest,
            lifecycle_digest(result.bundle, "platform-integration-bundle"),
        )
        self.assertEqual(reader.requests, ["staging"])
        self.assertEqual(
            result.bundle["endpoints"],
            {
                "external_origin": "https://apps-staging.comfforts.com",
                "issuer": None,
                "jwks_uri": None,
                "oauth_redirect_uri": None,
            },
        )
        self.assertEqual(
            result.bundle["identity"],
            {
                "oauth_client_id": None,
                "audience": None,
                "edge_caller_reference": EDGE_CALLER,
            },
        )
        serialized = repr(result.bundle).lower()
        for prohibited in (
            "client_secret",
            "restricted_member",
            "terraform",
            "provider_payload",
            "signing",
        ):
            self.assertNotIn(prohibited, serialized)

    def test_protected_bundles_receive_only_shared_identity_inputs(self) -> None:
        lifecycle = ApplicationIntegrationLifecycle(FakePlatformReader(_state()))

        for access_mode in ("authenticated", "restricted"):
            with self.subTest(access_mode=access_mode):
                result = lifecycle.outputs(_request(access_mode))
                self.assertEqual(result.outcome, "generated")
                assert result.bundle is not None
                self.assertEqual(
                    result.bundle["endpoints"],
                    {
                        "external_origin": "https://apps-staging.comfforts.com",
                        "issuer": "https://apps-staging.comfforts.com/_platform",
                        "jwks_uri": (
                            "https://apps-staging.comfforts.com/.well-known/jwks.json"
                        ),
                        "oauth_redirect_uri": (
                            "https://apps-staging.comfforts.com/"
                            "_platform/auth/callback"
                        ),
                    },
                )
                self.assertEqual(
                    result.bundle["identity"],
                    {
                        "oauth_client_id": OAUTH_CLIENT_ID,
                        "audience": (
                            "urn:comfforts:app-platform:audience:"
                            f"fixture-{access_mode}"
                        ),
                        "edge_caller_reference": EDGE_CALLER,
                    },
                )

    def test_bundle_is_bound_to_exact_current_platform_state(self) -> None:
        cases = {
            "wrong environment": (
                _request("public"),
                replace(_state(), environment="production"),
                "PLATFORM_ENVIRONMENT_MISMATCH",
            ),
            "wrong source": (
                replace(
                    _request("public"),
                    expected_platform_source_revision="b" * 40,
                ),
                _state(),
                "PLATFORM_SOURCE_MISMATCH",
            ),
            "wrong generation": (
                replace(_request("public"), expected_generation=8),
                _state(),
                "PLATFORM_GENERATION_MISMATCH",
            ),
            "not deployed": (
                _request("public"),
                replace(_state(), lifecycle_state="waiting"),
                "PLATFORM_NOT_DEPLOYED",
            ),
        }
        for name, (request, state, blocker) in cases.items():
            with self.subTest(name=name):
                result = ApplicationIntegrationLifecycle(
                    FakePlatformReader(state)
                ).outputs(request)
                self.assertEqual(result.outcome, "blocked")
                self.assertEqual(result.blockers, (blocker,))
                self.assertIsNone(result.bundle)
                self.assertIsNone(result.bundle_digest)

    def test_invalid_or_owner_only_request_fails_without_partial_bundle(self) -> None:
        lifecycle = ApplicationIntegrationLifecycle(FakePlatformReader(_state()))
        invalid = copy.copy(_request("public"))
        invalid = IntegrationBundleRequest(
            environment=invalid.environment,
            application_id="Invalid Application",
            access_mode=invalid.access_mode,
            route_intent=invalid.route_intent,
            expected_platform_source_revision=invalid.expected_platform_source_revision,
            expected_generation=invalid.expected_generation,
        )

        malformed = lifecycle.outputs(invalid)
        owner_only = lifecycle.outputs(_request("owner-only"))

        self.assertEqual(malformed.outcome, "blocked")
        self.assertEqual(malformed.blockers, ("INTEGRATION_BUNDLE_INVALID",))
        self.assertIsNone(malformed.bundle)
        self.assertEqual(owner_only.outcome, "blocked")
        self.assertEqual(owner_only.blockers, ("ACCESS_MODE_UNSUPPORTED",))


if __name__ == "__main__":
    unittest.main()
