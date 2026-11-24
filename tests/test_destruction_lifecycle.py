"""AP-M9-W8 confirmed, resumable safe-destruction lifecycle tests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import unittest

from infrastructure.operator import OperatorInterrupted, StageContext, StageExecution
from infrastructure.operator.destruction import (
    DESTRUCTIBLE_PLATFORM_RESOURCES,
    RETAINED_PLATFORM_RESOURCES,
    DestructionLifecycle,
    DestructionRequest,
    DestructionSnapshot,
    DestructionStageClosure,
)


def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


def request() -> DestructionRequest:
    return DestructionRequest(
        environment="staging",
        source_revision="a" * 40,
        profile_digest=_digest("1"),
        deployed_specification_digest=_digest("2"),
        deployment_progress_digest=_digest("3"),
        registration_generation_digest=_digest("4"),
        qualification_evidence_digest=_digest("5"),
    )


def snapshot() -> DestructionSnapshot:
    expected = request()
    return DestructionSnapshot(
        environment=expected.environment,
        lifecycle_state="deployed",
        source_revision=expected.source_revision,
        profile_digest=expected.profile_digest,
        deployed_specification_digest=expected.deployed_specification_digest,
        deployment_progress_digest=expected.deployment_progress_digest,
        registration_generation_digest=expected.registration_generation_digest,
        qualification_evidence_digest=expected.qualification_evidence_digest,
        active_application_ids=(),
        platform_resource_types=DESTRUCTIBLE_PLATFORM_RESOURCES,
        retained_resource_types=RETAINED_PLATFORM_RESOURCES,
        ownership_matches=True,
    )


@dataclass
class FakeReader:
    snapshots: list[DestructionSnapshot] = field(
        default_factory=lambda: [snapshot()]
    )
    calls: int = 0

    def read_current(self, environment: str) -> DestructionSnapshot:
        self.calls += 1
        self.asserted_environment = environment
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]


@dataclass
class FakeTerminal:
    confirmed: bool = True
    interrupt: bool = False
    prompts: list[tuple[str, str]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        self.prompts.append((prompt, expected))
        if self.interrupt:
            raise OperatorInterrupted
        return self.confirmed

    def write(self, message: str) -> None:
        self.messages.append(message)


@dataclass
class FakeControl:
    closures: list[DestructionStageClosure] = field(default_factory=list)
    published: list[tuple[str, str, dict[str, object]]] = field(default_factory=list)
    approved: list[tuple[str, str]] = field(default_factory=list)
    completed: list[tuple[str, str]] = field(default_factory=list)
    publish_result: bool = True
    approve_result: bool = True
    close_result: bool = True
    complete_result: bool = True

    def publish_specification(
        self,
        environment: str,
        digest: str,
        specification: dict[str, object],
    ) -> bool:
        self.published.append((environment, digest, specification))
        return self.publish_result

    def approve_specification(self, environment: str, digest: str) -> bool:
        self.approved.append((environment, digest))
        return self.approve_result

    def closed_stages(
        self,
        environment: str,
        digest: str,
    ) -> tuple[DestructionStageClosure, ...]:
        return tuple(self.closures)

    def close_stage(
        self,
        environment: str,
        digest: str,
        closure: DestructionStageClosure,
    ) -> bool:
        if self.close_result:
            self.closures.append(closure)
        return self.close_result

    def mark_complete(self, environment: str, digest: str) -> bool:
        self.completed.append((environment, digest))
        return self.complete_result


@dataclass
class FakeExecutor:
    scripted: list[StageExecution | BaseException] = field(default_factory=list)
    contexts: list[StageContext] = field(default_factory=list)

    def execute(self, context: StageContext) -> StageExecution:
        self.contexts.append(context)
        if self.scripted:
            result = self.scripted.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        produces = context.stage["produces"]
        assert isinstance(produces, list)
        return StageExecution(
            outcome="succeeded",
            outputs=tuple((str(name), f"observed-{name}") for name in produces),
            manual_acknowledgement=(
                "provider-verified"
                if context.stage["manual_checkpoint"] != "none"
                else "not-required"
            ),
        )


class DestructionLifecycleTest(unittest.TestCase):
    def _lifecycle(
        self,
        *,
        reader: FakeReader | None = None,
        terminal: FakeTerminal | None = None,
        control: FakeControl | None = None,
        executor: FakeExecutor | None = None,
    ) -> tuple[
        DestructionLifecycle,
        FakeReader,
        FakeTerminal,
        FakeControl,
        FakeExecutor,
    ]:
        selected_reader = reader or FakeReader()
        selected_terminal = terminal or FakeTerminal()
        selected_control = control or FakeControl()
        selected_executor = executor or FakeExecutor()
        return (
            DestructionLifecycle(
                selected_reader,
                selected_control,
                selected_terminal,
                selected_executor,
            ),
            selected_reader,
            selected_terminal,
            selected_control,
            selected_executor,
        )

    def test_exact_confirmation_reread_and_ordered_stage_completion(self) -> None:
        lifecycle, reader, terminal, control, executor = self._lifecycle()

        result = lifecycle.destroy(request())

        self.assertEqual(result.outcome, "destroyed")
        self.assertEqual(result.blockers, ())
        self.assertEqual(reader.calls, 2)
        self.assertEqual(len(control.published), 1)
        digest = control.published[0][1]
        self.assertEqual(
            terminal.prompts[0][1],
            f"DESTROY staging PLATFORM {digest}",
        )
        self.assertEqual(control.approved, [("staging", digest)])
        self.assertEqual(control.completed, [("staging", digest)])
        stage_ids = [str(context.stage["stage_id"]) for context in executor.contexts]
        self.assertEqual(
            stage_ids,
            [
                "destruction-preflight",
                "traffic-disable",
                "traffic-drain",
                "external-dns-destroy",
                "edge-destroy",
                "identity-destroy",
                "foundation-destroy",
                "destruction-readback",
            ],
        )
        self.assertEqual(result.last_closed_stage, "destruction-readback")

    def test_current_command_discovers_then_rechecks_exact_bindings(self) -> None:
        lifecycle, reader, _, _, _ = self._lifecycle()

        result = lifecycle.destroy_current("staging")

        self.assertEqual(result.outcome, "destroyed")
        self.assertEqual(reader.calls, 3)

    def test_active_attachment_appearing_after_confirmation_stops_before_stage(self) -> None:
        reader = FakeReader(
            [snapshot(), replace(snapshot(), active_application_ids=("fixture-public",))]
        )
        lifecycle, _, _, control, executor = self._lifecycle(reader=reader)

        result = lifecycle.destroy(request())

        self.assertEqual(result.outcome, "blocked")
        self.assertIn("ACTIVE_APPLICATION_ATTACHMENTS", result.blockers)
        self.assertEqual(control.approved, [])
        self.assertEqual(executor.contexts, [])

    def test_cancel_or_interruption_never_approves_or_executes(self) -> None:
        for label, terminal, expected_outcome, blocker in (
            (
                "cancelled",
                FakeTerminal(confirmed=False),
                "cancelled",
                "DESTRUCTION_NOT_CONFIRMED",
            ),
            (
                "interrupted",
                FakeTerminal(interrupt=True),
                "interrupted",
                "DESTRUCTION_INTERRUPTED",
            ),
        ):
            with self.subTest(label=label):
                lifecycle, _, _, control, executor = self._lifecycle(
                    terminal=terminal
                )
                result = lifecycle.destroy(request())
                self.assertEqual(result.outcome, expected_outcome)
                self.assertEqual(result.blockers, (blocker,))
                self.assertEqual(control.approved, [])
                self.assertEqual(executor.contexts, [])

    def test_partial_failure_stops_and_resume_skips_closed_prefix(self) -> None:
        failure = StageExecution(
            outcome="failed",
            blockers=("PROVIDER_DELETE_FAILED",),
        )
        executor = FakeExecutor(scripted=[
            StageExecution(
                outcome="succeeded",
                outputs=(("destruction-attestation", "observed-attestation"),),
            ),
            failure,
        ])
        control = FakeControl()
        lifecycle, reader, _, _, _ = self._lifecycle(
            executor=executor,
            control=control,
        )

        failed = lifecycle.destroy(request())
        self.assertEqual(failed.outcome, "failed")
        self.assertEqual(failed.last_closed_stage, "destruction-preflight")
        self.assertEqual(failed.blockers, ("PROVIDER_DELETE_FAILED",))

        executor.scripted = []
        reader.snapshots = [
            replace(snapshot(), lifecycle_state="destroying")
        ]
        resumed = lifecycle.destroy(request())
        self.assertEqual(resumed.outcome, "destroyed")
        self.assertEqual(
            [str(item.stage["stage_id"]) for item in executor.contexts].count(
                "destruction-preflight"
            ),
            1,
        )

    def test_invalid_progress_or_output_fails_closed(self) -> None:
        invalid_control = FakeControl(
            closures=[
                DestructionStageClosure(
                    stage_id="traffic-disable",
                    outputs=(("traffic-disabled", "observed"),),
                )
            ]
        )
        lifecycle, _, _, _, executor = self._lifecycle(control=invalid_control)
        invalid_progress = lifecycle.destroy(request())
        self.assertEqual(invalid_progress.outcome, "blocked")
        self.assertEqual(
            invalid_progress.blockers,
            ("DESTRUCTION_PROGRESS_INVALID",),
        )
        self.assertEqual(executor.contexts, [])

        wrong_output = FakeExecutor(
            scripted=[StageExecution(outcome="succeeded", outputs=())]
        )
        lifecycle, _, _, _, _ = self._lifecycle(executor=wrong_output)
        result = lifecycle.destroy(request())
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(
            result.blockers,
            ("DESTRUCTION_STAGE_OUTPUT_MISMATCH",),
        )

    def test_production_destruction_remains_unavailable(self) -> None:
        expected = replace(request(), environment="production")
        current = replace(snapshot(), environment="production")
        lifecycle, _, _, control, executor = self._lifecycle(
            reader=FakeReader([current])
        )

        result = lifecycle.destroy(expected)

        self.assertEqual(result.outcome, "blocked")
        self.assertIn("PRODUCTION_DESTRUCTION_UNAVAILABLE", result.blockers)
        self.assertEqual(control.published, [])
        self.assertEqual(executor.contexts, [])


if __name__ == "__main__":
    unittest.main()
