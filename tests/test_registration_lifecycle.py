"""Whole-generation AP-M9-W7 registration and activation tests."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import unittest

from contracts import compile_registration_set
from contracts.lifecycle import versioned_lifecycle_digest
from infrastructure.operator.integration import (
    ApplicationProjectConnection,
    ApplicationIntegrationLifecycle,
    AttachmentTargetReadback,
    GenerationActivationReadback,
    GenerationPublicationReadback,
    IntegrationBundleRequest,
    LifecycleChangeRequest,
    OperatorInterrupted,
    PlatformIntegrationState,
    RegistrationAttachmentBinding,
    RegistrationGenerationProposal,
    RegistrationEntry,
    RegistrationIntent,
)
from tests.environment import FIXTURES_PROJECT_ID


SOURCE_REVISION = "a" * 40
EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)


class FakePlatformReader:
    def __init__(self) -> None:
        self.state = PlatformIntegrationState(
            environment="staging",
            lifecycle_state="deployed",
            profile_digest="sha256:" + ("1" * 64),
            platform_source_revision=SOURCE_REVISION,
            specification_digest="sha256:" + ("2" * 64),
            progress_digest="sha256:" + ("3" * 64),
            generation=4,
            hostname="apps-staging.comfforts.com",
            oauth_client_id="1234567890-appsplatform.apps.googleusercontent.com",
            edge_caller_reference=EDGE_CALLER,
            qualification_status="unqualified",
        )

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        del environment
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
                "projects/comfforts-platform-non-prod/regions/us-west1/subnetworks/"
                "app-platform-applications-us-west1"
            ),
            egress_mode="all-traffic",
        )


class FakeAttachmentReader:
    def __init__(self) -> None:
        self.targets: dict[str, AttachmentTargetReadback | BaseException] = {}
        self.requests: list[str] = []

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback:
        del environment
        self.requests.append(resource_reference)
        result = self.targets[resource_reference]
        if isinstance(result, BaseException):
            raise result
        return result


class FakeTerminal:
    def __init__(
        self,
        confirmations: list[bool | BaseException] | None = None,
    ) -> None:
        self.confirmations = list(confirmations or [True] * 16)
        self.prompts: list[tuple[str, str]] = []
        self.review_prompts: list[str] = []
        self.messages: list[str] = []

    def write(self, message: str) -> None:
        self.messages.append(message)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.prompts.append((prompt, expected))
        result = self.confirmations.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def confirm(self, prompt: str) -> bool:
        self.review_prompts.append(prompt)
        result = self.confirmations.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class FakeGenerationControl:
    def __init__(self) -> None:
        self.current_proposal: RegistrationGenerationProposal | None = None
        self.publications: list[RegistrationGenerationProposal] = []
        self.activations: list[str] = []
        self.history: dict[str, RegistrationGenerationProposal] = {}
        self.publication_matches = True
        self.activation_matches = True

    def current(self, environment: str) -> RegistrationGenerationProposal | None:
        del environment
        return self.current_proposal

    def publish(
        self,
        proposal: RegistrationGenerationProposal,
    ) -> GenerationPublicationReadback:
        self.publications.append(proposal)
        existing = self.history.get(proposal.generation_digest)
        if existing is not None:
            created = False
        else:
            created = True
            self.history[proposal.generation_digest] = copy.deepcopy(proposal)
        return GenerationPublicationReadback(
            created=created,
            publication_reference=(
                "urn:comfforts:app-platform:generation:"
                f"{proposal.generation_digest[7:]}"
            ),
            generation_digest=(
                proposal.generation_digest
                if self.publication_matches
                else "sha256:" + ("f" * 64)
            ),
            content_digest=proposal.content_digest,
            readback_matches=self.publication_matches,
        )

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback:
        del environment, publication_reference
        self.activations.append(generation_digest)
        if self.activation_matches:
            self.current_proposal = copy.deepcopy(self.history[generation_digest])
        return GenerationActivationReadback(
            activated=self.activation_matches,
            active_generation_digest=(
                generation_digest
                if self.activation_matches
                else "sha256:" + ("e" * 64)
            ),
        )


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class RegistrationLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.platform = FakePlatformReader()
        self.attachments = FakeAttachmentReader()
        self.terminal = FakeTerminal()
        self.generations = FakeGenerationControl()
        self.lifecycle = ApplicationIntegrationLifecycle(
            self.platform,
            attachment_reader=self.attachments,
            generation_control=self.generations,
            terminal=self.terminal,
        )

    def _bundle(
        self,
        application_id: str,
        access_mode: str,
        identity_delivery: str | None = None,
        handoff_version: int = 2,
    ) -> dict[str, object]:
        selected_delivery = identity_delivery or (
            "none" if access_mode == "public" else "required"
        )
        result = self.lifecycle.outputs(
            IntegrationBundleRequest(
                environment="staging",
                application_id=application_id,
                access_mode=access_mode,
                identity_delivery=selected_delivery,
                route_intent=f"/{application_id}",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation=4,
                handoff_version=handoff_version,
            )
        )
        assert result.bundle is not None
        return result.bundle

    def _attachment(
        self,
        bundle: dict[str, object],
        *,
        revision: int = 1,
        suffix: str = "",
        additional: tuple[tuple[str, str], ...] = (),
    ) -> dict[str, object]:
        application_id = str(bundle["application_id"])
        resource_reference = (
            "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
            f"us-west1:{application_id}{suffix}"
        )
        identity = bundle["identity"]
        assert isinstance(identity, dict)
        attachment = {
            "contract_version": bundle["contract_version"],
            "document_kind": "application-attachment-bundle",
            "environment": "staging",
            "application_id": application_id,
            "attachment_revision": revision,
            "platform_integration_bundle_digest": versioned_lifecycle_digest(
                bundle,
                "platform-integration-bundle",
            ),
            "application_source_revision": "b" * 40,
            "target": {
                "owner_application_id": application_id,
                "adapter_kind": "gcp-cloud-run-v1",
                "resource_reference": resource_reference,
                "application_project_id": FIXTURES_PROJECT_ID,
                "network_reference": bundle["network"]["network_reference"],
                "subnetwork_reference": bundle["network"]["subnetwork_reference"],
                "egress_mode": "all-traffic",
                "ingress_mode": "shared_edge_only",
                "caller_grant": EDGE_CALLER,
                "audience": identity["audience"],
            },
        }
        self.attachments.targets[resource_reference] = AttachmentTargetReadback(
            exists=True,
            ready=True,
            owner_application_id=application_id,
            adapter_kind="gcp-cloud-run-v1",
            resource_reference=resource_reference,
            ingress_mode="shared_edge_only",
            caller_grant=EDGE_CALLER,
            audience=identity["audience"],
            application_project_id=FIXTURES_PROJECT_ID,
            network_reference=bundle["network"]["network_reference"],
            subnetwork_reference=bundle["network"]["subnetwork_reference"],
            egress_mode="all-traffic",
        )
        if additional:
            attachment["additional_attachments"] = []
            for attachment_id, additional_suffix in additional:
                additional_target = copy.deepcopy(attachment["target"])
                additional_reference = (
                    "urn:comfforts:app-platform:gcp:cloud-run:123456789012:"
                    f"us-west1:{application_id}{additional_suffix}"
                )
                additional_target["resource_reference"] = additional_reference
                attachment["additional_attachments"].append(
                    {
                        "attachment_id": attachment_id,
                        "target": additional_target,
                    }
                )
                self.attachments.targets[additional_reference] = replace(
                    self.attachments.targets[resource_reference],
                    resource_reference=additional_reference,
                )
        return attachment

    def _intent(
        self,
        bundle: dict[str, object],
        *,
        attachment_id: str = "primary",
        additional: tuple[RegistrationAttachmentBinding, ...] = (),
    ) -> RegistrationIntent:
        return RegistrationIntent(
            application_id=str(bundle["application_id"]),
            access_mode=str(bundle["access_mode"]),
            identity_delivery=str(bundle["identity_delivery"]),
            catalogue_visibility="listed",
            catalogue_title="Fixture application",
            catalogue_summary="Synthetic qualification application",
            attachment_id=attachment_id,
            mount_path="/",
            forwarding_mode="strip_application_prefix",
            contract_version=int(bundle["contract_version"]),
            additional_attachment_bindings=additional,
        )

    def test_new_application_activates_one_complete_generation(self) -> None:
        bundle = self._bundle("fixture-authenticated", "authenticated")
        attachment = self._attachment(bundle)

        result = self.lifecycle.register(bundle, attachment, self._intent(bundle))

        self.assertEqual(result.outcome, "activated")
        self.assertEqual(result.blockers, ())
        self.assertEqual(len(self.generations.publications), 1)
        active = self.generations.publications[0]
        self.assertEqual(active.registration_set["generation"], 1)
        self.assertEqual(
            active.registration_set["registrations"][0]["lifecycle"],
            "active",
        )
        self.assertIsNone(active.registration_set["previous_generation_digest"])
        self.assertEqual(
            [proposal.generation_digest for proposal in self.generations.publications],
            self.generations.activations,
        )
        self.assertEqual(len(self.terminal.prompts), 1)
        for proposal, (_, expected) in zip(
            self.generations.publications,
            self.terminal.prompts,
            strict=True,
        ):
            self.assertEqual(
                expected,
                (
                    "ACTIVATE staging GENERATION "
                    f"{proposal.registration_set['generation']} "
                    f"{proposal.generation_digest}"
                ),
            )
            self.assertEqual(
                proposal.content_digest,
                _canonical_digest(proposal.compiled_configuration),
            )

    def test_v3_root_only_handoff_projects_to_one_v2_attachment(self) -> None:
        bundle = self._bundle(
            "root-only-application",
            "authenticated",
            handoff_version=3,
        )
        attachment = self._attachment(bundle, suffix="-web")
        intent = self._intent(bundle, attachment_id="web")

        result = self.lifecycle.register(bundle, attachment, intent)

        self.assertEqual(result.outcome, "activated")
        current = self.generations.current_proposal
        assert current is not None
        projected = current.registration_set["registrations"][0]["attachments"]
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["contract_version"], 2)
        self.assertEqual(projected[0]["attachment_id"], "web")
        self.assertEqual(projected[0]["mount_path"], "/")

    def test_v3_maximum_attachment_set_reads_and_projects_all_sixteen(self) -> None:
        bundle = self._bundle(
            "maximum-attachment-app",
            "authenticated",
            handoff_version=3,
        )
        additions = tuple(
            (f"api-{index:02d}", f"-api-{index:02d}")
            for index in range(1, 16)
        )
        attachment = self._attachment(
            bundle,
            suffix="-web",
            additional=additions,
        )
        intent = self._intent(
            bundle,
            attachment_id="web",
            additional=tuple(
                RegistrationAttachmentBinding(
                    attachment_id,
                    f"/{attachment_id}",
                    "strip_attachment_mount",
                )
                for attachment_id, _suffix in additions
            ),
        )

        result = self.lifecycle.register(bundle, attachment, intent)

        self.assertEqual(result.outcome, "activated")
        current = self.generations.current_proposal
        assert current is not None
        self.assertEqual(
            len(current.registration_set["registrations"][0]["attachments"]),
            16,
        )
        self.assertEqual(len(self.attachments.requests), 16)

    def test_v3_complete_set_replaces_atomically_and_preserves_other_apps(self) -> None:
        other_bundle = self._bundle("fixture-public", "public")
        other_attachment = self._attachment(other_bundle)
        other_result = self.lifecycle.register(
            other_bundle,
            other_attachment,
            self._intent(other_bundle),
        )
        self.assertEqual(other_result.outcome, "activated")
        original_other = copy.deepcopy(
            self.generations.current_proposal.registration_set["registrations"][0]
        )

        bundle = self._bundle(
            "finance-assistant",
            "authenticated",
            handoff_version=3,
        )
        attachment = self._attachment(
            bundle,
            suffix="-web",
            additional=(("api", "-api"),),
        )
        intent = self._intent(
            bundle,
            attachment_id="web",
            additional=(
                RegistrationAttachmentBinding(
                    "api",
                    "/api",
                    "strip_attachment_mount",
                ),
            ),
        )

        registered = self.lifecycle.register(bundle, attachment, intent)

        self.assertEqual(registered.outcome, "activated")
        current = self.generations.current_proposal
        assert current is not None
        registrations = {
            item["application_id"]: item
            for item in current.registration_set["registrations"]
        }
        self.assertEqual(registrations["fixture-public"], original_other)
        projected = registrations["finance-assistant"]["attachments"]
        self.assertEqual(
            [
                (item["attachment_id"], item["mount_path"])
                for item in projected
            ],
            [("api", "/api"), ("web", "/")],
        )
        self.assertEqual(
            [
                item["attachment_id"]
                for route in current.compiled_configuration["routes"]
                for item in route["attachments"]
            ],
            ["api", "web", "primary"],
        )

        predecessor_digest = registered.generation_digest
        replacement = self._attachment(
            bundle,
            revision=2,
            suffix="-web-v2",
            additional=(("api", "-api-v2"),),
        )
        replaced = self.lifecycle.register(bundle, replacement, intent)

        self.assertEqual(replaced.outcome, "activated")
        self.assertIn(predecessor_digest, self.generations.history)
        predecessor = self.generations.history[str(predecessor_digest)]
        self.assertEqual(
            len(
                next(
                    item
                    for item in predecessor.registration_set["registrations"]
                    if item["application_id"] == "finance-assistant"
                )["attachments"]
            ),
            2,
        )
        current = self.generations.current_proposal
        assert current is not None
        registrations = {
            item["application_id"]: item
            for item in current.registration_set["registrations"]
        }
        self.assertEqual(registrations["fixture-public"], original_other)
        self.assertEqual(
            {
                item["resource_reference"]
                for item in registrations["finance-assistant"]["attachments"]
            },
            {
                replacement["target"]["resource_reference"],
                replacement["additional_attachments"][0]["target"][
                    "resource_reference"
                ],
            },
        )

        status = self.lifecycle.status_applications(
            "staging",
            ("finance-assistant",),
        )
        self.assertEqual(status.outcome, "read")
        self.assertEqual(len(status.applications[0].attachments), 2)
        self.assertTrue(status.applications[0].target_ready)

        assert replaced.generation_digest is not None
        detached = self.lifecycle.detach(
            LifecycleChangeRequest(
                environment="staging",
                application_id="finance-assistant",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation_digest=replaced.generation_digest,
            )
        )
        self.assertEqual(detached.outcome, "activated")
        current = self.generations.current_proposal
        assert current is not None
        detached_registration = next(
            item
            for item in current.registration_set["registrations"]
            if item["application_id"] == "finance-assistant"
        )
        self.assertEqual(detached_registration["lifecycle"], "suspended")
        self.assertEqual(len(detached_registration["attachments"]), 2)
        self.assertFalse(
            any(
                route["application_id"] == "finance-assistant"
                for route in current.compiled_configuration["routes"]
            )
        )

    def test_v3_target_failures_are_aggregated_before_any_publication(self) -> None:
        bundle = self._bundle(
            "finance-assistant",
            "authenticated",
            handoff_version=3,
        )
        attachment = self._attachment(
            bundle,
            suffix="-web",
            additional=(("api", "-api"),),
        )
        intent = self._intent(
            bundle,
            attachment_id="web",
            additional=(
                RegistrationAttachmentBinding(
                    "api",
                    "/api",
                    "strip_attachment_mount",
                ),
            ),
        )
        root_reference = str(attachment["target"]["resource_reference"])
        api_reference = str(
            attachment["additional_attachments"][0]["target"][
                "resource_reference"
            ]
        )
        root_readback = self.attachments.targets[root_reference]
        assert isinstance(root_readback, AttachmentTargetReadback)
        self.attachments.targets[root_reference] = replace(
            root_readback,
            exists=False,
            ready=False,
        )
        self.attachments.targets[api_reference] = RuntimeError(
            "provider payload must remain private"
        )

        result = self.lifecycle.register(bundle, attachment, intent)

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(
            result.blockers,
            ("TARGET_NOT_FOUND", "TARGET_READBACK_FAILED"),
        )
        self.assertEqual(
            [
                (violation.attachment_id, violation.code)
                for violation in result.target_violations
            ],
            [
                ("web", "TARGET_NOT_FOUND"),
                ("api", "TARGET_READBACK_FAILED"),
            ],
        )
        self.assertEqual(
            self.attachments.requests[-2:],
            [root_reference, api_reference],
        )
        self.assertEqual(self.generations.publications, [])
        self.assertEqual(self.generations.activations, [])
        self.assertNotIn("provider payload", repr(result))

    def test_fixture_suite_activates_one_complete_generation_with_one_review(self) -> None:
        entries = []
        for application_id, access_mode in (
            ("fixture-public", "public"),
            ("fixture-authenticated", "authenticated"),
            ("fixture-restricted", "restricted"),
        ):
            bundle = self._bundle(application_id, access_mode)
            attachment = self._attachment(bundle)
            entries.append(
                RegistrationEntry(
                    bundle,
                    attachment,
                    self._intent(bundle),
                )
            )

        result = self.lifecycle.register_complete(tuple(entries))

        self.assertEqual(result.outcome, "activated")
        self.assertEqual(len(self.generations.publications), 1)
        active = self.generations.publications[0]
        registration_set = active.registration_set
        self.assertEqual(
            [item["application_id"] for item in registration_set["registrations"]],
            [
                "fixture-authenticated",
                "fixture-public",
                "fixture-restricted",
            ],
        )
        self.assertTrue(
            all(item["lifecycle"] == "active" for item in registration_set["registrations"])
        )
        self.assertIsNone(active.registration_set["previous_generation_digest"])
        self.assertEqual(self.generations.activations, [active.generation_digest])
        self.assertEqual(len(self.terminal.review_prompts), 1)
        self.assertEqual(self.terminal.prompts, [])

        status = self.lifecycle.status_applications(
            "staging",
            (
                "fixture-public",
                "fixture-authenticated",
                "fixture-restricted",
            ),
        )
        self.assertEqual(status.outcome, "read")
        self.assertEqual(status.generation_digest, result.generation_digest)
        self.assertTrue(all(item.target_ready for item in status.applications))

        publications = len(self.generations.publications)
        repeated = self.lifecycle.register_complete(tuple(entries))
        self.assertEqual(repeated.outcome, "unchanged")
        self.assertEqual(len(self.generations.publications), publications)
        self.assertEqual(len(self.terminal.review_prompts), 1)

    def test_public_and_restricted_admission_are_compiled_without_bundle_members(self) -> None:
        public_bundle = self._bundle("fixture-public", "public")
        public_attachment = self._attachment(public_bundle)
        public = self.lifecycle.register(
            public_bundle,
            public_attachment,
            self._intent(public_bundle),
        )
        self.assertEqual(public.outcome, "activated")
        public_registration = self.generations.current_proposal.registration_set[
            "registrations"
        ][0]
        self.assertEqual(public_registration["admission"], {"mode": "public"})

        restricted_generations = FakeGenerationControl()
        restricted_lifecycle = ApplicationIntegrationLifecycle(
            self.platform,
            attachment_reader=self.attachments,
            generation_control=restricted_generations,
            terminal=FakeTerminal(),
        )
        restricted_bundle = restricted_lifecycle.outputs(
            IntegrationBundleRequest(
                environment="staging",
                application_id="fixture-restricted",
                access_mode="restricted",
                identity_delivery="required",
                route_intent="/fixture-restricted",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation=4,
            )
        ).bundle
        assert restricted_bundle is not None
        restricted_attachment = self._attachment(restricted_bundle)
        restricted = restricted_lifecycle.register(
            restricted_bundle,
            restricted_attachment,
            self._intent(restricted_bundle),
        )
        self.assertEqual(restricted.outcome, "activated")
        registration = restricted_generations.current_proposal.registration_set[
            "registrations"
        ][0]
        self.assertEqual(
            registration["admission"],
            {"mode": "restricted"},
        )
        self.assertNotIn("members", repr(restricted_bundle))

    def test_first_v2_registration_migrates_the_complete_v1_generation(self) -> None:
        v1_set = {
            "contract_version": 1,
            "generation": 1,
            "previous_generation_digest": None,
            "proposal": {
                "source_revision": SOURCE_REVISION,
                "change_summary": "Historical restricted fixture",
            },
            "registrations": [
                {
                    "contract_version": 1,
                    "application_id": "fixture-restricted",
                    "registration_revision": 1,
                    "route_prefix": "/fixture-restricted",
                    "catalogue": {
                        "visibility": "listed",
                        "title": "Restricted fixture",
                        "summary": "Historical Version 1 fixture",
                    },
                    "admission": {
                        "mode": "restricted",
                        "members": [
                            {
                                "issuer": "https://accounts.google.com",
                                "subject": "synthetic-subject",
                            }
                        ],
                    },
                    "lifecycle": "active",
                    "attachments": [
                        {
                            "contract_version": 1,
                            "owner_application_id": "fixture-restricted",
                            "attachment_id": "primary",
                            "adapter_kind": "gcp-cloud-run-v1",
                            "resource_reference": (
                                "urn:comfforts:app-platform:gcp:cloud-run:"
                                "123456789012:us-west1:fixture-restricted"
                            ),
                            "mount_path": "/",
                            "forwarding_mode": "strip_application_prefix",
                            "identity_requirement": "verified",
                            "audience": (
                                "urn:comfforts:app-platform:audience:"
                                "fixture-restricted"
                            ),
                            "ingress_mode": "shared_edge_only",
                        }
                    ],
                }
            ],
        }
        compiled_v1 = compile_registration_set(
            None,
            v1_set,
            {
                "contract_version": 1,
                "enabled_attachment_adapter_kinds": ["gcp-cloud-run-v1"],
            },
        )
        self.assertEqual(compiled_v1.violations, ())
        assert compiled_v1.compiled_configuration is not None
        assert compiled_v1.ownership_manifest is not None
        assert compiled_v1.generation_digest is not None
        self.generations.current_proposal = RegistrationGenerationProposal(
            environment="staging",
            registration_set=v1_set,
            compiled_configuration=compiled_v1.compiled_configuration,
            ownership_manifest=compiled_v1.ownership_manifest,
            generation_digest=compiled_v1.generation_digest,
            content_digest=_canonical_digest(compiled_v1.compiled_configuration),
        )

        bundle = self._bundle("fixture-public", "public", "optional")
        result = self.lifecycle.register(
            bundle,
            self._attachment(bundle),
            self._intent(bundle),
        )

        self.assertEqual(result.outcome, "activated")
        successor = self.generations.current_proposal
        assert successor is not None
        self.assertEqual(successor.registration_set["contract_version"], 2)
        self.assertEqual(successor.registration_set["generation"], 2)
        self.assertEqual(
            successor.registration_set["previous_generation_digest"],
            compiled_v1.generation_digest,
        )
        registrations = {
            item["application_id"]: item
            for item in successor.registration_set["registrations"]
        }
        self.assertEqual(
            registrations["fixture-restricted"]["admission"],
            {"mode": "restricted"},
        )
        self.assertEqual(
            registrations["fixture-restricted"]["identity_delivery"],
            "required",
        )
        self.assertEqual(
            registrations["fixture-public"]["identity_delivery"],
            "optional",
        )
        self.assertNotIn("members", repr(successor.registration_set))

    def test_first_v2_registration_preserves_unchanged_application_revision(self) -> None:
        """Migrate an unchanged V1 registration without inventing an app revision."""

        bundle = self._bundle("fixture-public", "public")
        attachment = self._attachment(bundle)
        intent = self._intent(bundle)
        migrated_shape = self.lifecycle._application_registration(
            bundle,
            attachment,
            intent,
            "active",
            1,
        )
        v1_registration = copy.deepcopy(migrated_shape)
        v1_registration["contract_version"] = 1
        v1_registration.pop("identity_delivery")
        for value in v1_registration["attachments"]:
            value["contract_version"] = 1
        v1_set = {
            "contract_version": 1,
            "generation": 1,
            "previous_generation_digest": None,
            "proposal": {
                "source_revision": SOURCE_REVISION,
                "change_summary": "Historical public fixture",
            },
            "registrations": [v1_registration],
        }
        compiled_v1 = compile_registration_set(
            None,
            v1_set,
            {
                "contract_version": 1,
                "enabled_attachment_adapter_kinds": ["gcp-cloud-run-v1"],
            },
        )
        self.assertEqual(compiled_v1.violations, ())
        assert compiled_v1.compiled_configuration is not None
        assert compiled_v1.ownership_manifest is not None
        assert compiled_v1.generation_digest is not None
        self.generations.current_proposal = RegistrationGenerationProposal(
            environment="staging",
            registration_set=v1_set,
            compiled_configuration=compiled_v1.compiled_configuration,
            ownership_manifest=compiled_v1.ownership_manifest,
            generation_digest=compiled_v1.generation_digest,
            content_digest=_canonical_digest(compiled_v1.compiled_configuration),
        )

        result = self.lifecycle.register(bundle, attachment, intent)

        self.assertEqual(result.outcome, "activated")
        successor = self.generations.current_proposal
        assert successor is not None
        self.assertEqual(successor.registration_set["contract_version"], 2)
        self.assertEqual(successor.registration_set["generation"], 2)
        self.assertEqual(
            successor.registration_set["registrations"][0][
                "registration_revision"
            ],
            1,
        )

    def test_replacement_publishes_one_successor_without_patching_current(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        first_attachment = self._attachment(bundle)
        first = self.lifecycle.register(bundle, first_attachment, self._intent(bundle))
        self.assertEqual(first.outcome, "activated")
        original = copy.deepcopy(self.generations.current_proposal.registration_set)
        replacement = self._attachment(bundle, revision=2, suffix="-v2")

        result = self.lifecycle.register(bundle, replacement, self._intent(bundle))

        self.assertEqual(result.outcome, "activated")
        self.assertEqual(len(self.generations.publications), 2)
        successor = self.generations.publications[-1]
        self.assertEqual(successor.registration_set["generation"], 2)
        self.assertEqual(original["generation"], 1)
        self.assertNotEqual(
            original["registrations"][0]["attachments"][0]["resource_reference"],
            successor.registration_set["registrations"][0]["attachments"][0][
                "resource_reference"
            ],
        )
        self.assertIn(first.generation_digest, self.generations.history)

    def test_confirmation_publication_and_activation_fail_closed(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        attachment = self._attachment(bundle)

        self.terminal.confirmations[0] = False
        cancelled = self.lifecycle.register(bundle, attachment, self._intent(bundle))
        self.assertEqual(cancelled.outcome, "cancelled")
        self.assertEqual(cancelled.blockers, ("GENERATION_NOT_CONFIRMED",))
        self.assertEqual(self.generations.activations, [])

        mismatched_control = FakeGenerationControl()
        mismatched_control.publication_matches = False
        lifecycle = ApplicationIntegrationLifecycle(
            self.platform,
            attachment_reader=self.attachments,
            generation_control=mismatched_control,
            terminal=FakeTerminal(),
        )
        mismatch = lifecycle.register(bundle, attachment, self._intent(bundle))
        self.assertEqual(mismatch.outcome, "blocked")
        self.assertEqual(mismatch.blockers, ("GENERATION_READBACK_MISMATCH",))

        activation_control = FakeGenerationControl()
        activation_control.activation_matches = False
        lifecycle = ApplicationIntegrationLifecycle(
            self.platform,
            attachment_reader=self.attachments,
            generation_control=activation_control,
            terminal=FakeTerminal(),
        )
        failed_activation = lifecycle.register(
            bundle,
            attachment,
            self._intent(bundle),
        )
        self.assertEqual(failed_activation.outcome, "blocked")
        self.assertEqual(
            failed_activation.blockers,
            ("GENERATION_ACTIVATION_MISMATCH",),
        )

    def test_interrupted_confirmation_resumes_exact_create_only_publication(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        attachment = self._attachment(bundle)
        self.terminal.confirmations = [OperatorInterrupted(), True, True]

        interrupted = self.lifecycle.register(
            bundle,
            attachment,
            self._intent(bundle),
        )
        resumed = self.lifecycle.register(bundle, attachment, self._intent(bundle))

        self.assertEqual(interrupted.outcome, "interrupted")
        self.assertEqual(
            interrupted.blockers,
            ("GENERATION_ACTIVATION_INTERRUPTED",),
        )
        self.assertEqual(resumed.outcome, "activated")
        self.assertEqual(len(self.generations.history), 1)
        self.assertEqual(len(self.generations.publications), 2)
        self.assertEqual(
            self.generations.publications[0].generation_digest,
            self.generations.publications[1].generation_digest,
        )

    def test_registration_rejects_a_second_identity_policy_and_unarmed_control(self) -> None:
        restricted = self._bundle("fixture-restricted", "restricted")
        attachment = self._attachment(restricted)
        invalid_policy = self.lifecycle.register(
            restricted,
            attachment,
            replace(self._intent(restricted), identity_delivery="optional"),
        )
        public = self._bundle("fixture-public", "public")
        unarmed = ApplicationIntegrationLifecycle(
            self.platform,
            attachment_reader=self.attachments,
            terminal=self.terminal,
        ).register(
            public,
            self._attachment(public),
            self._intent(public),
        )

        self.assertEqual(invalid_policy.outcome, "blocked")
        self.assertEqual(invalid_policy.blockers, ("REGISTRATION_INTENT_INVALID",))
        self.assertEqual(unarmed.outcome, "blocked")
        self.assertEqual(unarmed.blockers, ("GENERATION_CONTROL_UNAVAILABLE",))

    def test_detach_reserves_route_and_replacement_reactivates_application(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        original_attachment = self._attachment(bundle)
        registered = self.lifecycle.register(
            bundle,
            original_attachment,
            self._intent(bundle),
        )
        assert registered.generation_digest is not None

        detached = self.lifecycle.detach(
            LifecycleChangeRequest(
                environment="staging",
                application_id="fixture-public",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation_digest=registered.generation_digest,
            )
        )

        self.assertEqual(detached.outcome, "activated")
        current = self.generations.current_proposal
        assert current is not None
        registration = current.registration_set["registrations"][0]
        self.assertEqual(registration["lifecycle"], "suspended")
        self.assertEqual(registration["route_prefix"], "/fixture-public")
        self.assertEqual(current.compiled_configuration["catalogue"], [])
        self.assertEqual(current.compiled_configuration["routes"], [])
        self.assertEqual(current.compiled_configuration["admission_policies"], [])

        replacement = self._attachment(bundle, revision=2, suffix="-v2")
        reactivated = self.lifecycle.register(
            bundle,
            replacement,
            self._intent(bundle),
        )

        self.assertEqual(reactivated.outcome, "activated")
        current = self.generations.current_proposal
        assert current is not None
        registration = current.registration_set["registrations"][0]
        self.assertEqual(registration["lifecycle"], "active")
        self.assertEqual(
            registration["attachments"][0]["resource_reference"],
            replacement["target"]["resource_reference"],
        )
        self.assertEqual(len(current.compiled_configuration["routes"]), 1)

    def test_detached_status_accepts_absent_target_but_rejects_wrong_existing_owner(
        self,
    ) -> None:
        bundle = self._bundle("fixture-restricted", "restricted")
        attachment = self._attachment(bundle)
        registered = self.lifecycle.register(
            bundle,
            attachment,
            self._intent(bundle),
        )
        assert registered.generation_digest is not None
        detached = self.lifecycle.detach(
            LifecycleChangeRequest(
                environment="staging",
                application_id="fixture-restricted",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation_digest=registered.generation_digest,
            )
        )
        self.assertEqual(detached.outcome, "activated")
        target = attachment["target"]
        assert isinstance(target, dict)
        reference = str(target["resource_reference"])
        existing = self.attachments.targets[reference]
        self.attachments.targets[reference] = replace(
            existing,
            exists=False,
            ready=False,
            owner_application_id="",
            ingress_mode="unavailable",
            caller_grant="",
            audience=None,
            application_project_id=None,
            network_reference=None,
            subnetwork_reference=None,
            egress_mode=None,
        )

        absent = self.lifecycle.status_applications(
            "staging",
            ("fixture-restricted",),
        )

        self.assertEqual(absent.outcome, "read")
        self.assertEqual(absent.blockers, ())
        self.assertEqual(absent.applications[0].lifecycle, "suspended")
        self.assertFalse(absent.applications[0].target_exists)
        self.assertFalse(absent.applications[0].target_ready)

        self.attachments.targets[reference] = replace(
            existing,
            owner_application_id="other-application",
        )
        wrong_owner = self.lifecycle.status_applications(
            "staging",
            ("fixture-restricted",),
        )

        self.assertEqual(wrong_owner.outcome, "blocked")
        self.assertEqual(
            wrong_owner.blockers,
            ("FIXTURE_TARGET_OWNER_MISMATCH",),
        )

    def test_retirement_is_terminal_and_preserves_identifier_and_route(self) -> None:
        bundle = self._bundle("fixture-authenticated", "authenticated")
        attachment = self._attachment(bundle)
        registered = self.lifecycle.register(bundle, attachment, self._intent(bundle))
        assert registered.generation_digest is not None

        retired = self.lifecycle.retire(
            LifecycleChangeRequest(
                environment="staging",
                application_id="fixture-authenticated",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation_digest=registered.generation_digest,
            )
        )

        self.assertEqual(retired.outcome, "activated")
        current = self.generations.current_proposal
        assert current is not None
        tombstone = current.registration_set["registrations"][0]
        self.assertEqual(tombstone["lifecycle"], "retired")
        self.assertEqual(tombstone["application_id"], "fixture-authenticated")
        self.assertEqual(tombstone["route_prefix"], "/fixture-authenticated")
        self.assertEqual(current.compiled_configuration["routes"], [])
        self.assertEqual(
            self.lifecycle.register(
                bundle,
                attachment,
                self._intent(bundle),
            ).blockers,
            ("APPLICATION_RETIRED",),
        )

    def test_lifecycle_change_rejects_unknown_stale_and_wrong_source(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        attachment = self._attachment(bundle)
        registered = self.lifecycle.register(bundle, attachment, self._intent(bundle))
        assert registered.generation_digest is not None
        base = LifecycleChangeRequest(
            environment="staging",
            application_id="fixture-public",
            expected_platform_source_revision=SOURCE_REVISION,
            expected_generation_digest=registered.generation_digest,
        )

        unknown = self.lifecycle.detach(
            replace(base, application_id="unknown-application")
        )
        stale = self.lifecycle.detach(
            replace(base, expected_generation_digest="sha256:" + ("f" * 64))
        )
        wrong_source = self.lifecycle.detach(
            replace(base, expected_platform_source_revision="c" * 40)
        )

        self.assertEqual(unknown.blockers, ("APPLICATION_NOT_REGISTERED",))
        self.assertEqual(stale.blockers, ("GENERATION_CONFLICT",))
        self.assertEqual(wrong_source.blockers, ("PLATFORM_SOURCE_MISMATCH",))

    def test_repeated_detach_and_retire_are_idempotent_without_new_publication(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        attachment = self._attachment(bundle)
        registered = self.lifecycle.register(bundle, attachment, self._intent(bundle))
        assert registered.generation_digest is not None
        request = LifecycleChangeRequest(
            environment="staging",
            application_id="fixture-public",
            expected_platform_source_revision=SOURCE_REVISION,
            expected_generation_digest=registered.generation_digest,
        )
        detached = self.lifecycle.detach(request)
        assert detached.generation_digest is not None
        publication_count = len(self.generations.publications)

        unchanged_detach = self.lifecycle.detach(
            replace(request, expected_generation_digest=detached.generation_digest)
        )
        retired = self.lifecycle.retire(
            replace(request, expected_generation_digest=detached.generation_digest)
        )
        assert retired.generation_digest is not None
        unchanged_retire = self.lifecycle.retire(
            replace(request, expected_generation_digest=retired.generation_digest)
        )

        self.assertEqual(unchanged_detach.outcome, "unchanged")
        self.assertEqual(len(self.generations.publications), publication_count + 1)
        self.assertEqual(unchanged_retire.outcome, "unchanged")


if __name__ == "__main__":
    unittest.main()
