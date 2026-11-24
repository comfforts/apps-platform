"""AP-M9-W8 reviewed whole-generation rollback tests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import unittest

from infrastructure.operator import OperatorInterrupted
from infrastructure.operator.integration import (
    GenerationActivationReadback,
    PlatformIntegrationState,
    RegistrationGenerationProposal,
)
from infrastructure.operator.rollback import (
    GenerationRollbackLifecycle,
    ReviewedGeneration,
    RollbackRequest,
)


SOURCE_REVISION = "a" * 40
CURRENT_DIGEST = "sha256:" + ("2" * 64)
PREVIOUS_DIGEST = "sha256:" + ("1" * 64)


def proposal(
    generation: int,
    digest: str,
    previous_digest: str | None,
) -> RegistrationGenerationProposal:
    return RegistrationGenerationProposal(
        environment="staging",
        registration_set={
            "contract_version": 1,
            "generation": generation,
            "previous_generation_digest": previous_digest,
            "proposal": {
                "source_revision": SOURCE_REVISION,
                "change_summary": "Synthetic reviewed generation",
            },
            "registrations": [],
        },
        compiled_configuration={"generation": generation},
        ownership_manifest={"generation": generation},
        generation_digest=digest,
        content_digest="sha256:" + (str(generation) * 64),
    )


class FakePlatformReader:
    def __init__(self) -> None:
        self.state = PlatformIntegrationState(
            environment="staging",
            lifecycle_state="deployed",
            profile_digest="sha256:" + ("3" * 64),
            platform_source_revision=SOURCE_REVISION,
            specification_digest="sha256:" + ("4" * 64),
            progress_digest="sha256:" + ("5" * 64),
            generation=2,
            hostname="apps-staging.comfforts.com",
            oauth_client_id="client.apps.googleusercontent.com",
            edge_caller_reference=(
                "serviceAccount:app-platform-edge-caller@"
                "comfforts-platform-non-prod.iam.gserviceaccount.com"
            ),
            qualification_status="unqualified",
        )

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        del environment
        return self.state


class FakeReviewedControl:
    def __init__(self) -> None:
        current = proposal(2, CURRENT_DIGEST, PREVIOUS_DIGEST)
        previous = proposal(1, PREVIOUS_DIGEST, None)
        self.current_value = ReviewedGeneration("publication-current", current)
        self.reviewed = {
            CURRENT_DIGEST: self.current_value,
            PREVIOUS_DIGEST: ReviewedGeneration("publication-previous", previous),
        }
        self.activations: list[tuple[str, str, str]] = []
        self.activation_matches = True

    def current(self, environment: str) -> ReviewedGeneration | None:
        del environment
        return self.current_value

    def read_reviewed(
        self,
        environment: str,
        generation_digest: str,
    ) -> ReviewedGeneration | None:
        del environment
        return self.reviewed.get(generation_digest)

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback:
        self.activations.append(
            (environment, publication_reference, generation_digest)
        )
        return GenerationActivationReadback(
            activated=self.activation_matches,
            active_generation_digest=(
                generation_digest
                if self.activation_matches
                else CURRENT_DIGEST
            ),
        )


@dataclass
class FakeTerminal:
    confirmations: list[bool | BaseException] = field(
        default_factory=lambda: [True]
    )
    prompts: list[tuple[str, str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def write(self, message: str) -> None:
        self.messages.append(message)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.prompts.append((prompt, expected))
        result = self.confirmations.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def rollback_request() -> RollbackRequest:
    return RollbackRequest(
        environment="staging",
        expected_platform_source_revision=SOURCE_REVISION,
        expected_active_generation_digest=CURRENT_DIGEST,
        target_generation_digest=PREVIOUS_DIGEST,
    )


class GenerationRollbackTest(unittest.TestCase):
    def test_rollback_activates_only_the_exact_reviewed_predecessor(self) -> None:
        control = FakeReviewedControl()
        terminal = FakeTerminal()
        lifecycle = GenerationRollbackLifecycle(
            FakePlatformReader(),
            control,
            terminal,
        )

        result = lifecycle.rollback(rollback_request())

        self.assertEqual(result.outcome, "activated")
        self.assertEqual(result.generation, 1)
        self.assertEqual(result.generation_digest, PREVIOUS_DIGEST)
        self.assertEqual(
            control.activations,
            [("staging", "publication-previous", PREVIOUS_DIGEST)],
        )
        self.assertIn(PREVIOUS_DIGEST, terminal.prompts[0][1])

    def test_stale_platform_or_active_generation_fails_before_confirmation(self) -> None:
        platform = FakePlatformReader()
        platform.state = replace(
            platform.state,
            platform_source_revision="f" * 40,
        )
        terminal = FakeTerminal()
        stale_source = GenerationRollbackLifecycle(
            platform,
            FakeReviewedControl(),
            terminal,
        ).rollback(rollback_request())

        request = rollback_request()
        request = replace(
            request,
            expected_active_generation_digest="sha256:" + ("9" * 64),
        )
        stale_generation = GenerationRollbackLifecycle(
            FakePlatformReader(),
            FakeReviewedControl(),
            terminal,
        ).rollback(request)

        self.assertEqual(stale_source.blockers, ("PLATFORM_SOURCE_MISMATCH",))
        self.assertEqual(stale_generation.blockers, ("GENERATION_CONFLICT",))
        self.assertEqual(terminal.prompts, [])

    def test_unknown_or_non_predecessor_generation_is_never_activated(self) -> None:
        unknown = replace(
            rollback_request(),
            target_generation_digest="sha256:" + ("9" * 64),
        )
        unknown_result = GenerationRollbackLifecycle(
            FakePlatformReader(),
            FakeReviewedControl(),
            FakeTerminal(),
        ).rollback(unknown)

        control = FakeReviewedControl()
        unrelated_digest = "sha256:" + ("8" * 64)
        control.reviewed[unrelated_digest] = ReviewedGeneration(
            "publication-unrelated",
            proposal(1, unrelated_digest, None),
        )
        unrelated = replace(
            rollback_request(),
            target_generation_digest=unrelated_digest,
        )
        unrelated_result = GenerationRollbackLifecycle(
            FakePlatformReader(),
            control,
            FakeTerminal(),
        ).rollback(unrelated)

        self.assertEqual(unknown_result.blockers, ("ROLLBACK_TARGET_NOT_FOUND",))
        self.assertEqual(
            unrelated_result.blockers,
            ("ROLLBACK_TARGET_NOT_PREDECESSOR",),
        )
        self.assertEqual(control.activations, [])

    def test_cancellation_interruption_and_readback_mismatch_are_truthful(self) -> None:
        cancelled = GenerationRollbackLifecycle(
            FakePlatformReader(),
            FakeReviewedControl(),
            FakeTerminal([False]),
        ).rollback(rollback_request())
        interrupted = GenerationRollbackLifecycle(
            FakePlatformReader(),
            FakeReviewedControl(),
            FakeTerminal([OperatorInterrupted()]),
        ).rollback(rollback_request())
        control = FakeReviewedControl()
        control.activation_matches = False
        mismatch = GenerationRollbackLifecycle(
            FakePlatformReader(),
            control,
            FakeTerminal(),
        ).rollback(rollback_request())

        self.assertEqual(cancelled.outcome, "cancelled")
        self.assertEqual(cancelled.blockers, ("ROLLBACK_NOT_CONFIRMED",))
        self.assertEqual(interrupted.outcome, "interrupted")
        self.assertEqual(interrupted.blockers, ("ROLLBACK_INTERRUPTED",))
        self.assertEqual(mismatch.outcome, "blocked")
        self.assertEqual(mismatch.blockers, ("ROLLBACK_ACTIVATION_MISMATCH",))
if __name__ == "__main__":
    unittest.main()
