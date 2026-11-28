"""Deterministic AP-M9-W7 application-integration behavior."""

from __future__ import annotations

import copy
from dataclasses import replace
import unittest

from contracts.lifecycle import (
    validate_versioned_lifecycle_document,
    versioned_lifecycle_digest,
)
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    ApplicationProjectConnection,
    AttachmentTargetReadback,
    IntegrationBundleRequest,
    PlatformIntegrationState,
    RegistrationAttachmentBinding,
    RegistrationIntent,
)


SOURCE_REVISION = "a" * 40
PROFILE_DIGEST = "sha256:" + ("1" * 64)
SPECIFICATION_DIGEST = "sha256:" + ("2" * 64)
PROGRESS_DIGEST = "sha256:" + ("3" * 64)
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

    def read_connection(
        self,
        environment: str,
        project_id: str,
    ) -> ApplicationProjectConnection:
        return ApplicationProjectConnection(
            environment=environment,
            project_id=project_id,
            project_number="123456789012",
            host_project_id="comfforts-platform-non-prod",
            host_project_number="455651441682",
            region="us-west1",
            network_reference=(
                "projects/comfforts-platform-non-prod/global/networks/"
                "app-platform-shared"
            ),
            subnetwork_reference=(
                "projects/comfforts-platform-non-prod/regions/us-west1/"
                "subnetworks/app-platform-applications-us-west1"
            ),
            egress_mode="all-traffic",
        )


class FakeAttachmentReader:
    def __init__(
        self,
        readback: AttachmentTargetReadback
        | dict[str, AttachmentTargetReadback],
    ) -> None:
        self.readback = readback
        self.requests: list[tuple[str, str]] = []

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback:
        self.requests.append((environment, resource_reference))
        if isinstance(self.readback, dict):
            return self.readback[resource_reference]
        return self.readback


def _state() -> PlatformIntegrationState:
    return PlatformIntegrationState(
        environment="staging",
        lifecycle_state="deployed",
        profile_digest=PROFILE_DIGEST,
        platform_source_revision=SOURCE_REVISION,
        specification_digest=SPECIFICATION_DIGEST,
        progress_digest=PROGRESS_DIGEST,
        generation=7,
        hostname="apps-staging.comfforts.com",
        oauth_client_id=OAUTH_CLIENT_ID,
        edge_caller_reference=EDGE_CALLER,
        qualification_status="unqualified",
    )


def _request(
    access_mode: str,
    identity_delivery: str | None = None,
    handoff_version: int = 2,
) -> IntegrationBundleRequest:
    selected_delivery = identity_delivery or {
        "public": "none",
        "authenticated": "required",
        "restricted": "required",
    }.get(access_mode, "required")
    return IntegrationBundleRequest(
        environment="staging",
        application_id=f"fixture-{access_mode}",
        access_mode=access_mode,
        identity_delivery=selected_delivery,
        route_intent=f"/fixture-{access_mode}",
        expected_platform_source_revision=SOURCE_REVISION,
        expected_generation=7,
        handoff_version=handoff_version,
    )


def _attachment(bundle: dict[str, object]) -> dict[str, object]:
    return {
        "contract_version": bundle["contract_version"],
        "document_kind": "application-attachment-bundle",
        "environment": bundle["environment"],
        "application_id": bundle["application_id"],
        "attachment_revision": 1,
        "platform_integration_bundle_digest": versioned_lifecycle_digest(
            bundle,
            "platform-integration-bundle",
        ),
        "application_source_revision": "b" * 40,
        "target": {
            "owner_application_id": bundle["application_id"],
            "adapter_kind": "gcp-cloud-run-v1",
            "resource_reference": (
                "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
                f"us-west1:{bundle['application_id']}"
            ),
            "ingress_mode": "shared_edge_only",
            "caller_grant": EDGE_CALLER,
            "audience": bundle["identity"]["audience"],
            "application_project_id": bundle["application_project"]["project_id"],
            "network_reference": bundle["network"]["network_reference"],
            "subnetwork_reference": bundle["network"]["subnetwork_reference"],
            "egress_mode": bundle["network"]["egress_mode"],
        },
    }


def _target_readback(attachment: dict[str, object]) -> AttachmentTargetReadback:
    target = attachment["target"]
    assert isinstance(target, dict)
    return AttachmentTargetReadback(
        exists=True,
        ready=True,
        owner_application_id=str(target["owner_application_id"]),
        adapter_kind=str(target["adapter_kind"]),
        resource_reference=str(target["resource_reference"]),
        ingress_mode=str(target["ingress_mode"]),
        caller_grant=str(target["caller_grant"]),
        audience=(str(target["audience"]) if target["audience"] is not None else None),
        application_project_id=str(target["application_project_id"]),
        network_reference=str(target["network_reference"]),
        subnetwork_reference=str(target["subnetwork_reference"]),
        egress_mode=str(target["egress_mode"]),
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
            validate_versioned_lifecycle_document(
                result.bundle,
                "platform-integration-bundle",
            ),
            (),
        )
        self.assertEqual(
            result.bundle_digest,
            versioned_lifecycle_digest(
                result.bundle,
                "platform-integration-bundle",
            ),
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

    def test_public_optional_bundle_explicitly_enables_platform_identity(self) -> None:
        lifecycle = ApplicationIntegrationLifecycle(FakePlatformReader(_state()))

        result = lifecycle.outputs(_request("public", "optional"))

        self.assertEqual(result.outcome, "generated")
        assert result.bundle is not None
        self.assertEqual(result.bundle["identity_delivery"], "optional")
        self.assertEqual(
            result.bundle["identity"]["audience"],
            "urn:comfforts:app-platform:audience:fixture-public",
        )
        self.assertEqual(
            result.bundle["endpoints"]["issuer"],
            "https://apps-staging.comfforts.com/_platform",
        )

    def test_v3_bundle_explicitly_declares_the_complete_attachment_set(self) -> None:
        lifecycle = ApplicationIntegrationLifecycle(FakePlatformReader(_state()))

        result = lifecycle.outputs(_request("authenticated", handoff_version=3))

        self.assertEqual(result.outcome, "generated")
        assert result.bundle is not None
        self.assertEqual(result.bundle["contract_version"], 3)
        self.assertEqual(
            result.bundle["attachment_contract"],
            {
                "adapter_kind": "gcp-cloud-run-v1",
                "ingress_mode": "shared_edge_only",
                "maximum_additional_attachments": 15,
                "root_attachment_required": True,
            },
        )
        self.assertEqual(
            validate_versioned_lifecycle_document(
                result.bundle,
                "platform-integration-bundle",
            ),
            (),
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
            identity_delivery=invalid.identity_delivery,
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

        for access_mode, identity_delivery in (
            ("public", "required"),
            ("authenticated", "none"),
            ("authenticated", "optional"),
            ("restricted", "none"),
            ("restricted", "optional"),
        ):
            with self.subTest(
                access_mode=access_mode,
                identity_delivery=identity_delivery,
            ):
                invalid_pair = lifecycle.outputs(
                    _request(access_mode, identity_delivery)
                )
                self.assertEqual(
                    invalid_pair.blockers,
                    ("IDENTITY_DELIVERY_UNSUPPORTED",),
                )


class AttachmentValidationTest(unittest.TestCase):
    def _lifecycle(
        self,
        attachment: dict[str, object],
        *,
        readback: AttachmentTargetReadback | None = None,
        platform_state: PlatformIntegrationState | None = None,
    ) -> tuple[ApplicationIntegrationLifecycle, FakeAttachmentReader]:
        reader = FakeAttachmentReader(readback or _target_readback(attachment))
        lifecycle = ApplicationIntegrationLifecycle(
            FakePlatformReader(platform_state or _state()),
            attachment_reader=reader,
        )
        return lifecycle, reader

    def test_attachment_validation_binds_contract_owner_and_provider_posture(self) -> None:
        generated = ApplicationIntegrationLifecycle(
            FakePlatformReader(_state())
        ).outputs(_request("authenticated"))
        assert generated.bundle is not None
        attachment = _attachment(generated.bundle)
        lifecycle, reader = self._lifecycle(attachment)

        result = lifecycle.validate_attachment(generated.bundle, attachment)

        self.assertEqual(result.outcome, "validated")
        self.assertEqual(result.blockers, ())
        self.assertEqual(result.attachment_bundle, attachment)
        target = attachment["target"]
        assert isinstance(target, dict)
        self.assertEqual(
            reader.requests,
            [("staging", target["resource_reference"])],
        )

    def test_stale_bundle_and_invalid_owner_fail_before_provider_readback(self) -> None:
        generated = ApplicationIntegrationLifecycle(
            FakePlatformReader(_state())
        ).outputs(_request("authenticated"))
        assert generated.bundle is not None
        attachment = _attachment(generated.bundle)
        lifecycle, reader = self._lifecycle(attachment)

        stale = copy.deepcopy(attachment)
        stale["platform_integration_bundle_digest"] = "sha256:" + ("f" * 64)
        stale_result = lifecycle.validate_attachment(generated.bundle, stale)
        wrong_owner = copy.deepcopy(attachment)
        wrong_owner["target"]["owner_application_id"] = "other-application"
        owner_result = lifecycle.validate_attachment(generated.bundle, wrong_owner)

        self.assertEqual(stale_result.outcome, "blocked")
        self.assertEqual(stale_result.blockers, ("ATTACHMENT_BUNDLE_MISMATCH",))
        self.assertEqual(owner_result.outcome, "blocked")
        self.assertEqual(owner_result.blockers, ("ATTACHMENT_BUNDLE_INVALID",))
        self.assertEqual(reader.requests, [])

    def test_v3_root_and_additional_targets_are_all_read_before_success(self) -> None:
        generated = ApplicationIntegrationLifecycle(
            FakePlatformReader(_state())
        ).outputs(_request("authenticated", handoff_version=3))
        assert generated.bundle is not None
        attachment = _attachment(generated.bundle)
        root_target = attachment["target"]
        assert isinstance(root_target, dict)
        api_target = copy.deepcopy(root_target)
        api_target["resource_reference"] = (
            f"{root_target['resource_reference']}-api"
        )
        attachment["additional_attachments"] = [
            {"attachment_id": "api", "target": api_target}
        ]
        intent = RegistrationIntent(
            application_id=str(generated.bundle["application_id"]),
            access_mode="authenticated",
            identity_delivery="required",
            catalogue_visibility="unlisted",
            catalogue_title="Multiple targets",
            catalogue_summary="Root and API target",
            attachment_id="web",
            mount_path="/",
            forwarding_mode="strip_application_prefix",
            contract_version=3,
            additional_attachment_bindings=(
                RegistrationAttachmentBinding(
                    "api",
                    "/api",
                    "strip_attachment_mount",
                ),
            ),
        )
        reader = FakeAttachmentReader(
            {
                str(root_target["resource_reference"]): _target_readback(attachment),
                str(api_target["resource_reference"]): replace(
                    _target_readback(attachment),
                    resource_reference=str(api_target["resource_reference"]),
                ),
            }
        )
        lifecycle = ApplicationIntegrationLifecycle(
            FakePlatformReader(_state()),
            attachment_reader=reader,
        )

        result = lifecycle.validate_attachment(
            generated.bundle,
            attachment,
            intent,
        )

        self.assertEqual(result.outcome, "validated")
        self.assertEqual(
            reader.requests,
            [
                ("staging", root_target["resource_reference"]),
                ("staging", api_target["resource_reference"]),
            ],
        )

    def test_current_platform_and_target_readback_must_match_exactly(self) -> None:
        generated = ApplicationIntegrationLifecycle(
            FakePlatformReader(_state())
        ).outputs(_request("restricted"))
        assert generated.bundle is not None
        attachment = _attachment(generated.bundle)
        mismatched_target = replace(
            _target_readback(attachment),
            ingress_mode="public",
        )
        lifecycle, _ = self._lifecycle(attachment, readback=mismatched_target)
        target_result = lifecycle.validate_attachment(generated.bundle, attachment)
        stale_platform = replace(_state(), generation=8)
        lifecycle, reader = self._lifecycle(
            attachment,
            platform_state=stale_platform,
        )
        platform_result = lifecycle.validate_attachment(generated.bundle, attachment)

        self.assertEqual(target_result.outcome, "blocked")
        self.assertEqual(target_result.blockers, ("TARGET_INGRESS_MISMATCH",))
        self.assertEqual(platform_result.outcome, "blocked")
        self.assertEqual(platform_result.blockers, ("PLATFORM_STATE_MISMATCH",))
        self.assertEqual(reader.requests, [])

    def test_attachment_cannot_switch_to_another_connected_project(self) -> None:
        generated = ApplicationIntegrationLifecycle(
            FakePlatformReader(_state())
        ).outputs(_request("public"))
        assert generated.bundle is not None
        attachment = _attachment(generated.bundle)
        target = attachment["target"]
        assert isinstance(target, dict)
        target["application_project_id"] = "another-application-project"
        lifecycle, reader = self._lifecycle(attachment)

        result = lifecycle.validate_attachment(generated.bundle, attachment)

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(result.blockers, ("ATTACHMENT_PROJECT_MISMATCH",))
        self.assertEqual(reader.requests, [])

    def test_unavailable_or_unready_target_fails_closed(self) -> None:
        generated = ApplicationIntegrationLifecycle(
            FakePlatformReader(_state())
        ).outputs(_request("public"))
        assert generated.bundle is not None
        attachment = _attachment(generated.bundle)

        for readback, blocker in (
            (replace(_target_readback(attachment), exists=False), "TARGET_NOT_FOUND"),
            (replace(_target_readback(attachment), ready=False), "TARGET_NOT_READY"),
        ):
            with self.subTest(blocker=blocker):
                lifecycle, _ = self._lifecycle(attachment, readback=readback)
                result = lifecycle.validate_attachment(generated.bundle, attachment)
                self.assertEqual(result.outcome, "blocked")
                self.assertEqual(result.blockers, (blocker,))


if __name__ == "__main__":
    unittest.main()
