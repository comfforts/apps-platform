"""AP-M9-W4 interactive lifecycle behavior through the public operator seam."""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from infrastructure.operator import (
    DiscoverySnapshot,
    GitSnapshot,
    LifecycleOperator,
    OperatorInterrupted,
    OperatorAdapters,
    StageExecution,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.cli import main as operator_main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FakeGit:
    revision: str = "a" * 40
    clean: bool = True

    def inspect(self) -> GitSnapshot:
        return GitSnapshot(
            repository="comfforts/apps-platform",
            revision=self.revision,
            branch="main",
            clean=self.clean,
            main_revision=self.revision,
            origin_main_revision=self.revision,
        )


@dataclass
class FakeDiscovery:
    name: str
    facts: tuple[tuple[str, str], ...]
    blockers: tuple[str, ...] = ()
    calls: int = 0

    def inspect(self, profile: dict[str, object]) -> DiscoverySnapshot:
        self.calls += 1
        return DiscoverySnapshot(self.name, self.facts, self.blockers)


@dataclass
class FakeTerraform:
    blockers: tuple[str, ...] = ()
    calls: int = 0

    def inspect(self) -> DiscoverySnapshot:
        self.calls += 1
        return DiscoverySnapshot(
            "terraform",
            (("terraform_version", "1.17.2"), ("provider_version", "8.11.0")),
            self.blockers,
        )


@dataclass
class FakeTerminal:
    approvals: list[bool]
    prompts: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def confirm(self, prompt: str) -> bool:
        self.prompts.append(prompt)
        return self.approvals.pop(0)

    def write(self, message: str) -> None:
        self.messages.append(message)


@dataclass(frozen=True)
class FixedClock:
    def now(self) -> str:
        return "2026-11-19T18:00:00Z"


@dataclass
class FakeExecutor:
    scripted: list[StageExecution | BaseException] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def execute(
        self,
        stage: dict[str, object],
        inputs: tuple[tuple[str, str], ...],
    ) -> StageExecution:
        stage_id = str(stage["stage_id"])
        self.calls.append(stage_id)
        if self.scripted:
            selected = self.scripted.pop(0)
            if isinstance(selected, BaseException):
                raise selected
            return selected
        checkpoint = stage["manual_checkpoint"]
        acknowledgement = {
            "external-dns": "provider-verified",
            "provider-console": "operator-attested",
        }.get(checkpoint, "not-required")
        return StageExecution(
            outcome="succeeded",
            outputs=tuple(
                (str(name), f"observed-{name}") for name in stage["produces"]
            ),
            plan_digest=None,
            manual_acknowledgement=acknowledgement,
        )


class OperatorLifecycleTest(unittest.TestCase):
    def _operator(
        self,
        state_root: Path,
        *,
        git: FakeGit | None = None,
        terminal: FakeTerminal | None = None,
        github: FakeDiscovery | None = None,
        gcp: FakeDiscovery | None = None,
        terraform: FakeTerraform | None = None,
        dns: FakeDiscovery | None = None,
        executor: FakeExecutor | None = None,
    ) -> tuple[LifecycleOperator, FakeTerminal]:
        selected_terminal = terminal or FakeTerminal([True])
        adapters = OperatorAdapters(
            git=git or FakeGit(),
            github=github
            or FakeDiscovery(
                "github",
                (("repository", "comfforts/apps-platform"),),
            ),
            gcp=gcp
            or FakeDiscovery(
                "gcp",
                (
                    ("project_id", "comfforts-platform-non-prod"),
                    ("project_number", "455651441682"),
                    ("region", "us-west1"),
                ),
            ),
            terraform=terraform or FakeTerraform(),
            dns=dns
            or FakeDiscovery(
                "dns",
                (
                    ("provider_class", "squarespace-v1"),
                    ("hostname", "apps-staging.comfforts.com"),
                ),
            ),
            terminal=selected_terminal,
            filesystem=LocalFilesystem(PROJECT_ROOT, state_root),
            clock=FixedClock(),
            executor=executor,
        )
        return LifecycleOperator(adapters), selected_terminal

    def test_first_preparation_emits_one_complete_specification_and_explicit_approval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operator, terminal = self._operator(Path(directory))

            result = operator.prepare("staging")

            self.assertEqual(result.outcome, "prepared")
            self.assertTrue(result.complete)
            self.assertTrue(result.approved)
            self.assertEqual(result.blockers, ())
            self.assertEqual(
                result.specification_digest,
                "sha256:a362f9836014acbac6b07d19873a1f4dab6434eefd39ba5eafa53b796557beea",
            )
            assert result.specification is not None
            self.assertEqual(result.specification["environment"], "staging")
            self.assertEqual(result.specification["operation"], "deploy")
            self.assertEqual(
                [stage["stage_id"] for stage in result.specification["stages"]],
                [
                    "preflight",
                    "bootstrap",
                    "foundation",
                    "image-publish",
                    "oauth-configuration",
                    "shared-edge",
                    "external-dns",
                    "tls-readiness",
                    "readback",
                ],
            )
            self.assertEqual(len(terminal.prompts), 1)
            self.assertIn(result.specification_digest, terminal.prompts[0])
            self.assertNotIn("secret", terminal.prompts[0].lower())

    def test_no_change_reuses_the_exact_approved_specification_without_reprompting(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = FakeTerminal([True])
            operator, _ = self._operator(Path(directory), terminal=terminal)
            first = operator.prepare("staging")

            second = operator.prepare("staging")

            self.assertEqual(second.outcome, "unchanged")
            self.assertEqual(second.specification_digest, first.specification_digest)
            self.assertTrue(second.approved)
            self.assertEqual(len(terminal.prompts), 1)

    def test_approval_is_separate_from_completeness_and_cancellation_is_truthful(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operator, _ = self._operator(
                Path(directory),
                terminal=FakeTerminal([False]),
            )

            result = operator.prepare("staging")

            self.assertEqual(result.outcome, "cancelled")
            self.assertTrue(result.complete)
            self.assertFalse(result.approved)
            self.assertIsNotNone(result.specification_digest)

    def test_preparation_fails_closed_before_approval_when_source_or_discovery_is_invalid(
        self,
    ) -> None:
        cases = {
            "dirty source": (FakeGit(clean=False), FakeTerraform(), "SOURCE_NOT_CLEAN"),
            "missing tool": (
                FakeGit(),
                FakeTerraform(("PINNED_TOOL_UNAVAILABLE",)),
                "PINNED_TOOL_UNAVAILABLE",
            ),
        }
        for label, (git, terraform, blocker) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                terminal = FakeTerminal([])
                operator, _ = self._operator(
                    Path(directory),
                    git=git,
                    terraform=terraform,
                    terminal=terminal,
                )

                result = operator.prepare("staging")

                self.assertEqual(result.outcome, "blocked")
                self.assertFalse(result.complete)
                self.assertFalse(result.approved)
                self.assertIn(blocker, result.blockers)
                self.assertEqual(terminal.prompts, [])

    def test_production_preparation_preserves_the_ownership_transfer_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = FakeTerminal([])
            operator, _ = self._operator(Path(directory), terminal=terminal)

            result = operator.prepare("production")

            self.assertEqual(result.outcome, "blocked")
            self.assertEqual(result.blockers, ("OWNERSHIP_TRANSFER_REQUIRED",))
            self.assertIsNone(result.specification)
            self.assertIsNone(result.specification_digest)
            self.assertEqual(terminal.prompts, [])

    def test_changed_source_requires_a_new_specification_and_fresh_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            git = FakeGit()
            terminal = FakeTerminal([True, True])
            operator, _ = self._operator(
                Path(directory),
                git=git,
                terminal=terminal,
            )
            first = operator.prepare("staging")
            git.revision = "b" * 40

            second = operator.prepare("staging")

            self.assertEqual(second.outcome, "prepared")
            self.assertNotEqual(second.specification_digest, first.specification_digest)
            self.assertTrue(second.approved)
            self.assertEqual(len(terminal.prompts), 2)

    def test_interrupted_execution_resumes_after_the_last_closed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor = FakeExecutor(
                [
                    StageExecution(
                        outcome="succeeded",
                        outputs=(("preflight-attestation", "verified"),),
                    ),
                    OperatorInterrupted(),
                ]
            )
            operator, _ = self._operator(Path(directory), executor=executor)
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            interrupted = operator.execute(
                "staging",
                prepared.specification_digest,
            )
            status_after_interruption = operator.status("staging")

            self.assertEqual(interrupted.outcome, "interrupted")
            self.assertEqual(
                status_after_interruption.environment_status["lifecycle_state"],
                "deploying",
            )
            self.assertEqual(
                status_after_interruption.environment_status["last_closed_stage"],
                "preflight",
            )

            resumed = operator.execute("staging", prepared.specification_digest)

            self.assertEqual(resumed.outcome, "succeeded")
            self.assertEqual(executor.calls.count("preflight"), 1)
            self.assertEqual(executor.calls.count("bootstrap"), 2)
            self.assertEqual(
                operator.status("staging").environment_status["lifecycle_state"],
                "deployed",
            )

    def test_waiting_failure_and_cancellation_remain_truthful(self) -> None:
        cases = {
            "waiting": "waiting",
            "failed": "failed",
            "cancelled": "cancelled",
        }
        for outcome, expected_state in cases.items():
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                executor = FakeExecutor([StageExecution(outcome=outcome)])
                operator, _ = self._operator(Path(directory), executor=executor)
                prepared = operator.prepare("staging")
                assert prepared.specification_digest is not None

                result = operator.execute("staging", prepared.specification_digest)
                status = operator.status("staging")

                self.assertEqual(result.outcome, outcome)
                self.assertEqual(
                    status.environment_status["lifecycle_state"],
                    expected_state,
                )
                self.assertIsNone(status.environment_status["last_closed_stage"])

    def test_changed_scope_conflicts_with_an_unclosed_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            git = FakeGit()
            executor = FakeExecutor([StageExecution(outcome="waiting")])
            terminal = FakeTerminal([True])
            operator, _ = self._operator(
                Path(directory),
                git=git,
                executor=executor,
                terminal=terminal,
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None
            operator.execute("staging", prepared.specification_digest)
            git.revision = "b" * 40

            conflict = operator.prepare("staging")

            self.assertEqual(conflict.outcome, "blocked")
            self.assertEqual(conflict.blockers, ("ACTIVE_JOURNAL_CONFLICT",))
            self.assertEqual(len(terminal.prompts), 1)

    def test_execution_rejects_stale_or_missing_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            git = FakeGit()
            executor = FakeExecutor()
            operator, _ = self._operator(
                Path(directory),
                git=git,
                executor=executor,
                terminal=FakeTerminal([False]),
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            unapproved = operator.execute("staging", prepared.specification_digest)
            git.revision = "b" * 40
            stale = operator.execute("staging", prepared.specification_digest)

            self.assertEqual(unapproved.outcome, "blocked")
            self.assertIn("SPECIFICATION_NOT_APPROVED", unapproved.blockers)
            self.assertEqual(stale.outcome, "blocked")
            self.assertIn("SOURCE_REVISION_MISMATCH", stale.blockers)
            self.assertEqual(executor.calls, [])

    def test_prohibited_stage_output_fails_without_reaching_the_terminal_or_journal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = FakeTerminal([True])
            executor = FakeExecutor(
                [
                    StageExecution(
                        outcome="succeeded",
                        outputs=(("preflight-attestation", "ya29.private-token"),),
                    )
                ]
            )
            operator, _ = self._operator(
                Path(directory),
                terminal=terminal,
                executor=executor,
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            result = operator.execute("staging", prepared.specification_digest)

            self.assertEqual(result.outcome, "failed")
            self.assertIn("PROHIBITED_STAGE_OUTPUT", result.blockers)
            transcript = "\n".join([*terminal.prompts, *terminal.messages])
            self.assertNotIn("ya29.", transcript)
            self.assertNotIn("private-token", transcript)

    def test_status_is_read_only_and_production_reports_its_profile_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            operator, _ = self._operator(state_root, terminal=FakeTerminal([]))
            before = sorted(path.relative_to(state_root) for path in state_root.rglob("*"))

            staging = operator.status("staging")
            production = operator.status("production")
            after = sorted(path.relative_to(state_root) for path in state_root.rglob("*"))

            self.assertEqual(staging.environment_status["lifecycle_state"], "absent")
            self.assertEqual(
                production.environment_status["lifecycle_state"], "blocked"
            )
            self.assertEqual(
                production.environment_status["blockers"],
                ["OWNERSHIP_TRANSFER_REQUIRED"],
            )
            self.assertEqual(after, before)

    def test_cli_exposes_only_prepare_and_status_with_canonical_safe_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operator, _ = self._operator(Path(directory))

            prepare_stdout = io.StringIO()
            with mock.patch("sys.stdout", prepare_stdout):
                prepare_code = operator_main(
                    ["prepare", "--environment", "staging"],
                    operator_factory=lambda _: operator,
                )
            prepared = json.loads(prepare_stdout.getvalue().splitlines()[-1])

            status_stdout = io.StringIO()
            with mock.patch("sys.stdout", status_stdout):
                status_code = operator_main(
                    ["status", "--environment", "staging"],
                    operator_factory=lambda _: operator,
                )
            status = json.loads(status_stdout.getvalue())

            self.assertEqual(prepare_code, 0)
            self.assertEqual(prepared["outcome"], "prepared")
            self.assertTrue(prepared["approved"])
            self.assertRegex(prepared["specification_digest"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(status_code, 0)
            self.assertEqual(status["lifecycle_state"], "absent")

            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit):
                    operator_main(
                        ["deploy", "--environment", "staging"],
                        operator_factory=lambda _: operator,
                    )
            self.assertIn("invalid choice", stderr.getvalue())

    def test_make_targets_are_shallow_and_private_state_is_ignored(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("platform-prepare:", makefile)
        self.assertIn("platform-status:", makefile)
        self.assertIn("-m infrastructure.operator prepare", makefile)
        self.assertIn("-m infrastructure.operator status", makefile)
        self.assertNotIn("platform-deploy:", makefile)
        self.assertIn(".platform-operator/", gitignore)

    def test_local_filesystem_does_not_create_state_during_read_only_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "not-created"
            operator, _ = self._operator(
                state_root,
                terminal=FakeTerminal([]),
            )

            operator.status("staging")

            self.assertFalse(state_root.exists())


if __name__ == "__main__":
    unittest.main()
