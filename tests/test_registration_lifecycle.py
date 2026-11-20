"""Whole-generation AP-M9-W7 registration and activation tests."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import unittest

from contracts.lifecycle import lifecycle_digest
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    AttachmentTargetReadback,
    GenerationActivationReadback,
    GenerationPublicationReadback,
    IntegrationBundleRequest,
    LifecycleChangeRequest,
    OperatorInterrupted,
    PlatformIntegrationState,
    RegistrationGenerationProposal,
    RegistrationEntry,
    RegistrationIntent,
)


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
            journal_digest="sha256:" + ("3" * 64),
            generation=4,
            hostname="apps-staging.comfforts.com",
            oauth_client_id="1234567890-appsplatform.apps.googleusercontent.com",
            edge_caller_reference=EDGE_CALLER,
            qualification_status="unqualified",
        )

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        del environment
        return self.state


class FakeAttachmentReader:
    def __init__(self) -> None:
        self.targets: dict[str, AttachmentTargetReadback] = {}

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback:
        del environment
        return self.targets[resource_reference]


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

    def _bundle(self, application_id: str, access_mode: str) -> dict[str, object]:
        result = self.lifecycle.outputs(
            IntegrationBundleRequest(
                environment="staging",
                application_id=application_id,
                access_mode=access_mode,
                route_intent=f"/{application_id}",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation=4,
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
    ) -> dict[str, object]:
        application_id = str(bundle["application_id"])
        resource_reference = (
            "urn:comfforts:app-platform:gcp:cloud-run:455651441682:"
            f"us-west1:{application_id}{suffix}"
        )
        identity = bundle["identity"]
        assert isinstance(identity, dict)
        attachment = {
            "contract_version": 1,
            "document_kind": "application-attachment-bundle",
            "environment": "staging",
            "application_id": application_id,
            "attachment_revision": revision,
            "platform_integration_bundle_digest": lifecycle_digest(
                bundle,
                "platform-integration-bundle",
            ),
            "application_source_revision": "b" * 40,
            "target": {
                "owner_application_id": application_id,
                "adapter_kind": "gcp-cloud-run-v1",
                "resource_reference": resource_reference,
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
        )
        return attachment

    @staticmethod
    def _intent(
        *,
        restricted_members: tuple[tuple[str, str], ...] = (),
    ) -> RegistrationIntent:
        return RegistrationIntent(
            catalogue_visibility="listed",
            catalogue_title="Fixture application",
            catalogue_summary="Synthetic qualification application",
            attachment_id="primary",
            mount_path="/",
            forwarding_mode="strip_application_prefix",
            restricted_members=restricted_members,
        )

    def test_new_application_stages_then_activates_two_complete_generations(self) -> None:
        bundle = self._bundle("fixture-authenticated", "authenticated")
        attachment = self._attachment(bundle)

        result = self.lifecycle.register(bundle, attachment, self._intent())

        self.assertEqual(result.outcome, "activated")
        self.assertEqual(result.blockers, ())
        self.assertEqual(len(self.generations.publications), 2)
        staged, active = self.generations.publications
        self.assertEqual(staged.registration_set["generation"], 1)
        self.assertEqual(
            staged.registration_set["registrations"][0]["lifecycle"],
            "staged",
        )
        self.assertEqual(active.registration_set["generation"], 2)
        self.assertEqual(
            active.registration_set["registrations"][0]["lifecycle"],
            "active",
        )
        self.assertEqual(
            active.registration_set["previous_generation_digest"],
            staged.generation_digest,
        )
        self.assertEqual(
            [proposal.generation_digest for proposal in self.generations.publications],
            self.generations.activations,
        )
        self.assertEqual(len(self.terminal.prompts), 2)
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

    def test_fixture_suite_activates_one_complete_generation_with_one_review(self) -> None:
        entries = []
        for application_id, access_mode in (
            ("fixture-public", "public"),
            ("fixture-authenticated", "authenticated"),
            ("fixture-restricted", "restricted"),
        ):
            bundle = self._bundle(application_id, access_mode)
            attachment = self._attachment(bundle)
            members = (
                (("https://accounts.google.com", "synthetic-subject"),)
                if access_mode == "restricted"
                else ()
            )
            entries.append(
                RegistrationEntry(
                    bundle,
                    attachment,
                    self._intent(restricted_members=members),
                )
            )

        result = self.lifecycle.register_complete(tuple(entries))

        self.assertEqual(result.outcome, "activated")
        self.assertEqual(len(self.generations.publications), 2)
        staged, active = self.generations.publications
        self.assertTrue(
            all(
                item["lifecycle"] == "staged"
                for item in staged.registration_set["registrations"]
            )
        )
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
        self.assertEqual(
            active.registration_set["previous_generation_digest"],
            staged.generation_digest,
        )
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
            self._intent(),
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
                route_intent="/fixture-restricted",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation=4,
            )
        ).bundle
        assert restricted_bundle is not None
        restricted_attachment = self._attachment(restricted_bundle)
        members = (("https://accounts.google.com", "synthetic-subject"),)
        restricted = restricted_lifecycle.register(
            restricted_bundle,
            restricted_attachment,
            self._intent(restricted_members=members),
        )
        self.assertEqual(restricted.outcome, "activated")
        registration = restricted_generations.current_proposal.registration_set[
            "registrations"
        ][0]
        self.assertEqual(
            registration["admission"],
            {
                "mode": "restricted",
                "members": [
                    {
                        "issuer": "https://accounts.google.com",
                        "subject": "synthetic-subject",
                    }
                ],
            },
        )
        self.assertNotIn("members", repr(restricted_bundle))

    def test_replacement_publishes_one_successor_without_patching_current(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        first_attachment = self._attachment(bundle)
        first = self.lifecycle.register(bundle, first_attachment, self._intent())
        self.assertEqual(first.outcome, "activated")
        original = copy.deepcopy(self.generations.current_proposal.registration_set)
        replacement = self._attachment(bundle, revision=2, suffix="-v2")

        result = self.lifecycle.register(bundle, replacement, self._intent())

        self.assertEqual(result.outcome, "activated")
        self.assertEqual(len(self.generations.publications), 3)
        successor = self.generations.publications[-1]
        self.assertEqual(successor.registration_set["generation"], 3)
        self.assertEqual(original["generation"], 2)
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
        cancelled = self.lifecycle.register(bundle, attachment, self._intent())
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
        mismatch = lifecycle.register(bundle, attachment, self._intent())
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
        failed_activation = lifecycle.register(bundle, attachment, self._intent())
        self.assertEqual(failed_activation.outcome, "blocked")
        self.assertEqual(
            failed_activation.blockers,
            ("GENERATION_ACTIVATION_MISMATCH",),
        )

    def test_interrupted_confirmation_resumes_exact_create_only_publication(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        attachment = self._attachment(bundle)
        self.terminal.confirmations = [OperatorInterrupted(), True, True]

        interrupted = self.lifecycle.register(bundle, attachment, self._intent())
        resumed = self.lifecycle.register(bundle, attachment, self._intent())

        self.assertEqual(interrupted.outcome, "interrupted")
        self.assertEqual(
            interrupted.blockers,
            ("GENERATION_ACTIVATION_INTERRUPTED",),
        )
        self.assertEqual(resumed.outcome, "activated")
        self.assertEqual(len(self.generations.history), 2)
        self.assertEqual(len(self.generations.publications), 3)
        self.assertEqual(
            self.generations.publications[0].generation_digest,
            self.generations.publications[1].generation_digest,
        )

    def test_registration_requires_complete_restricted_policy_and_generation_control(self) -> None:
        restricted = self._bundle("fixture-restricted", "restricted")
        attachment = self._attachment(restricted)
        invalid_policy = self.lifecycle.register(
            restricted,
            attachment,
            self._intent(),
        )
        unarmed = ApplicationIntegrationLifecycle(
            self.platform,
            attachment_reader=self.attachments,
            terminal=self.terminal,
        ).register(
            self._bundle("fixture-public", "public"),
            self._attachment(self._bundle("fixture-public", "public")),
            self._intent(),
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
            self._intent(),
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
        reactivated = self.lifecycle.register(bundle, replacement, self._intent())

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

    def test_retirement_is_terminal_and_preserves_identifier_and_route(self) -> None:
        bundle = self._bundle("fixture-authenticated", "authenticated")
        attachment = self._attachment(bundle)
        registered = self.lifecycle.register(bundle, attachment, self._intent())
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
            self.lifecycle.register(bundle, attachment, self._intent()).blockers,
            ("APPLICATION_RETIRED",),
        )

    def test_lifecycle_change_rejects_unknown_stale_and_wrong_source(self) -> None:
        bundle = self._bundle("fixture-public", "public")
        attachment = self._attachment(bundle)
        registered = self.lifecycle.register(bundle, attachment, self._intent())
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
        registered = self.lifecycle.register(bundle, attachment, self._intent())
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
