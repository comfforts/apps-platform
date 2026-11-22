"""Focused tests for the human-run platform workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from infrastructure.operator import (
    DiscoverySnapshot,
    GitSnapshot,
    LifecycleOperator,
    OperatorInterrupted,
    OperatorAdapters,
    StageContext,
    StageExecution,
)
from infrastructure.operator import local as local_adapters
from infrastructure.operator.cli import main as operator_main
from infrastructure.operator.local import (
    LocalFilesystem,
    ProfileGcp,
    build_local_operator,
)


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

    def inspect(self, profile: dict[str, object]) -> DiscoverySnapshot:
        del profile
        return DiscoverySnapshot(self.name, self.facts, self.blockers)


@dataclass
class FakeTerraform:
    blockers: tuple[str, ...] = ()

    def inspect(self) -> DiscoverySnapshot:
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

    def execute(self, context: StageContext) -> StageExecution:
        stage_id = str(context.stage["stage_id"])
        self.calls.append(stage_id)
        if self.scripted:
            selected = self.scripted.pop(0)
            if isinstance(selected, BaseException):
                raise selected
            return selected
        checkpoint = context.stage["manual_checkpoint"]
        acknowledgement = {
            "external-dns": "provider-verified",
            "provider-console": "operator-attested",
        }.get(checkpoint, "not-required")
        return StageExecution(
            "succeeded",
            tuple(
                (str(name), f"observed-{name}")
                for name in context.stage["produces"]
            ),
            manual_acknowledgement=acknowledgement,
        )


class OperatorLifecycleTest(unittest.TestCase):
    def _operator(
        self,
        state_root: Path,
        *,
        git: FakeGit | None = None,
        terminal: FakeTerminal | None = None,
        blocker: str | None = None,
        executor: FakeExecutor | None = None,
    ) -> tuple[LifecycleOperator, FakeTerminal]:
        selected_terminal = terminal or FakeTerminal([True])
        selected_blockers = (blocker,) if blocker else ()
        adapters = OperatorAdapters(
            git=git or FakeGit(),
            github=FakeDiscovery(
                "github",
                (("repository", "comfforts/apps-platform"),),
            ),
            gcp=FakeDiscovery(
                "gcp",
                (
                    ("project_id", "comfforts-platform-non-prod"),
                    ("project_number", "455651441682"),
                    ("region", "us-west1"),
                ),
                selected_blockers,
            ),
            terraform=FakeTerraform(),
            dns=FakeDiscovery(
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

    def test_preflight_reports_all_readiness_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "operator"
            ready, terminal = self._operator(state, terminal=FakeTerminal([]))
            result = ready.preflight("staging")

            blocked, blocked_terminal = self._operator(
                state,
                terminal=FakeTerminal([]),
                blocker="OPERATOR_PROJECT_MISMATCH",
            )
            blocked_result = blocked.preflight("staging")

        self.assertEqual(result.outcome, "ready")
        self.assertEqual(terminal.prompts, [])
        self.assertFalse(state.exists())
        self.assertEqual(
            blocked_result.blockers,
            ("OPERATOR_PROJECT_MISMATCH",),
        )
        trace = "\n".join(terminal.messages)
        self.assertIn(
            "Environment profile path: infrastructure/config/profiles/staging.v1.json",
            trace,
        )
        self.assertIn("Source snapshot:", trace)
        self.assertIn("  repository: \"comfforts/apps-platform\"", trace)
        self.assertIn("Discovery github: ready", trace)
        self.assertIn("Discovery gcp: ready", trace)
        self.assertIn("Discovery terraform: ready", trace)
        self.assertIn("Discovery dns: ready", trace)
        self.assertIn(
            "Readiness blocker OPERATOR_PROJECT_MISMATCH: ",
            "\n".join(blocked_terminal.messages),
        )

    def test_development_preflight_reports_source_without_enforcing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "operator"
            operator, terminal = self._operator(
                state,
                git=FakeGit(clean=False),
                terminal=FakeTerminal([]),
            )

            development = operator.preflight("staging", mode="development")
            operational = operator.preflight("staging")

        self.assertTrue(development.ready)
        self.assertFalse(development.operational_ready)
        self.assertEqual(development.blockers, ())
        self.assertEqual(
            development.source_admission_blockers,
            ("SOURCE_NOT_CLEAN",),
        )
        self.assertFalse(operational.ready)
        self.assertEqual(operational.blockers, ("SOURCE_NOT_CLEAN",))
        self.assertFalse(state.exists())
        self.assertIn(
            "Development source diagnostic SOURCE_NOT_CLEAN:",
            "\n".join(terminal.messages),
        )

    def test_cli_development_preflight_is_explicit_and_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operator, _ = self._operator(
                Path(directory),
                git=FakeGit(clean=False),
                terminal=FakeTerminal([]),
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
                code = operator_main(
                    [
                        "preflight",
                        "--environment",
                        "staging",
                        "--preflight-mode",
                        "development",
                    ],
                    preflight_factory=lambda _path, _authority: operator,
                )
            result = json.loads(stdout.getvalue())

        self.assertEqual(code, 0)
        self.assertTrue(stdout.getvalue().startswith("{\n  \"blockers\":"))
        self.assertTrue(result["ready"])
        self.assertFalse(result["operational_ready"])
        self.assertEqual(result["preflight_mode"], "development")
        self.assertEqual(
            result["source_admission_blockers"],
            ["SOURCE_NOT_CLEAN"],
        )
        self.assertIn("  preflight mode: development", stderr.getvalue())

    def test_console_narration_blocks_end_with_an_empty_line(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            local_adapters.ConsoleTerminal().write("Verified provider readback.")

        self.assertEqual(stderr.getvalue(), "Verified provider readback.\n\n")

    def test_prepare_approves_small_fingerprint_and_deploy_reuses_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = FakeTerminal([True])
            operator, _ = self._operator(Path(directory), terminal=terminal)
            prepared = operator.prepare("staging")
            reused = operator.current_approved_specification("staging")

        self.assertEqual(prepared.outcome, "prepared")
        self.assertTrue(prepared.approved)
        self.assertRegex(str(prepared.specification_digest), r"^sha256:[0-9a-f]{64}$")
        assert prepared.specification is not None
        self.assertEqual(prepared.specification["workflow"], "platform-deploy-v1")
        self.assertNotIn("stages", prepared.specification)
        assert reused is not None
        self.assertEqual(reused.specification_digest, prepared.specification_digest)
        self.assertEqual(len(terminal.prompts), 1)

    def test_deploy_records_one_atomic_progress_and_truthful_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            executor = FakeExecutor()
            operator, _ = self._operator(state, executor=executor)
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            deployed = operator.execute("staging", prepared.specification_digest)
            unchanged = operator.execute("staging", prepared.specification_digest)
            status = operator.status("staging").environment_status

            progress_files = list(state.rglob("current-progress.v1.json"))
            terminal_progress_files = list(
                state.rglob("progress/*.final.v1.json")
            )
            terminal_progress = (
                json.loads(terminal_progress_files[0].read_text(encoding="utf-8"))
                if terminal_progress_files
                else None
            )
            journal_files = list(state.rglob("journals/*.json"))

        self.assertEqual(deployed.outcome, "succeeded")
        self.assertEqual(unchanged.outcome, "unchanged")
        self.assertEqual(status["lifecycle_state"], "deployed")
        self.assertEqual(status["last_closed_stage"], "readback")
        self.assertRegex(str(status["progress_digest"]), r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(progress_files), 1)
        self.assertEqual(len(terminal_progress_files), 1)
        self.assertEqual(
            terminal_progress_files[0].name,
            prepared.specification_digest[7:] + ".final.v1.json",
        )
        assert terminal_progress is not None
        self.assertEqual(terminal_progress["status"], "succeeded")
        self.assertEqual(terminal_progress["completed"][-1]["stage_id"], "readback")
        self.assertEqual(journal_files, [])
        self.assertEqual(len(executor.calls), 11)

    def test_interruption_resumes_after_last_readback_closed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executor = FakeExecutor(
                [StageExecution("succeeded"), OperatorInterrupted()]
            )
            operator, _ = self._operator(Path(directory), executor=executor)
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            interrupted = operator.execute("staging", prepared.specification_digest)
            resumed = operator.execute("staging", prepared.specification_digest)

        self.assertEqual(interrupted.outcome, "interrupted")
        self.assertEqual(resumed.outcome, "succeeded")
        self.assertEqual(executor.calls.count("preflight"), 1)
        self.assertEqual(executor.calls.count("bootstrap-services"), 2)

    def test_successful_resume_replaces_the_same_specification_terminal_record(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            operator, _ = self._operator(
                state,
                executor=FakeExecutor([StageExecution("failed")]),
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            failed = operator.execute("staging", prepared.specification_digest)
            terminal_path = next(state.rglob("progress/*.final.v1.json"))
            failed_record = json.loads(terminal_path.read_text(encoding="utf-8"))
            resumed = operator.execute("staging", prepared.specification_digest)
            succeeded_record = json.loads(terminal_path.read_text(encoding="utf-8"))
            terminal_record_count = len(
                list(state.rglob("progress/*.final.v1.json"))
            )

        self.assertEqual(failed.outcome, "failed")
        self.assertEqual(failed_record["status"], "failed")
        self.assertEqual(resumed.outcome, "succeeded")
        self.assertEqual(succeeded_record["status"], "succeeded")
        self.assertEqual(terminal_record_count, 1)

    def test_waiting_failure_and_cancellation_are_not_success(self) -> None:
        for outcome in ("waiting", "failed", "cancelled"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                operator, _ = self._operator(
                    Path(directory),
                    executor=FakeExecutor([StageExecution(outcome)]),
                )
                prepared = operator.prepare("staging")
                assert prepared.specification_digest is not None
                result = operator.execute("staging", prepared.specification_digest)
                terminal_progress_files = list(
                    Path(directory).rglob("progress/*.final.v1.json")
                )

                self.assertEqual(result.outcome, outcome)
                self.assertEqual(
                    operator.status("staging").environment_status["lifecycle_state"],
                    outcome,
                )
                self.assertEqual(
                    len(terminal_progress_files),
                    0 if outcome == "waiting" else 1,
                )

    def test_source_change_requires_fresh_intent_and_conflicts_with_open_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            git = FakeGit()
            terminal = FakeTerminal([True, True])
            operator, _ = self._operator(
                Path(directory),
                git=git,
                terminal=terminal,
                executor=FakeExecutor([StageExecution("waiting")]),
            )
            first = operator.prepare("staging")
            assert first.specification_digest is not None
            operator.execute("staging", first.specification_digest)
            git.revision = "b" * 40
            conflict = operator.prepare("staging")

        self.assertEqual(conflict.blockers, ("ACTIVE_OPERATION_CONFLICT",))
        self.assertEqual(len(terminal.prompts), 1)

    def test_failed_operation_allows_fresh_source_intent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            git = FakeGit()
            terminal = FakeTerminal([True, True])
            operator, _ = self._operator(
                Path(directory),
                git=git,
                terminal=terminal,
                executor=FakeExecutor([StageExecution("failed")]),
            )
            first = operator.prepare("staging")
            assert first.specification_digest is not None
            failed = operator.execute("staging", first.specification_digest)

            git.revision = "b" * 40
            replacement = operator.prepare("staging")
            assert replacement.specification_digest is not None
            deployed = operator.execute("staging", replacement.specification_digest)

        self.assertEqual(failed.outcome, "failed")
        self.assertEqual(replacement.outcome, "prepared")
        self.assertNotEqual(
            replacement.specification_digest,
            first.specification_digest,
        )
        self.assertEqual(deployed.outcome, "succeeded")
        self.assertEqual(len(terminal.prompts), 2)

    def test_prohibited_output_and_tampered_progress_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            operator, _ = self._operator(
                state,
                executor=FakeExecutor(
                    [StageExecution("succeeded", (("unexpected", "ya29.private"),))]
                ),
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None
            result = operator.execute("staging", prepared.specification_digest)
            self.assertEqual(result.blockers, ("PROHIBITED_STAGE_OUTPUT",))

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            operator, _ = self._operator(state, executor=FakeExecutor())
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None
            operator.execute("staging", prepared.specification_digest)
            path = next(state.rglob("current-progress.v1.json"))
            progress = json.loads(path.read_text(encoding="utf-8"))
            progress["completed"][0]["stage_id"] = "shared-edge"
            path.write_text(
                json.dumps(progress, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "deployment progress"):
                operator.status("staging")

    def test_production_status_is_read_only_and_ownership_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "not-created"
            operator, _ = self._operator(state, terminal=FakeTerminal([]))
            status = operator.status("production")

        self.assertEqual(status.environment_status["lifecycle_state"], "blocked")
        self.assertEqual(status.conflicts, ("OWNERSHIP_TRANSFER_REQUIRED",))
        self.assertFalse(state.exists())

    def test_cli_exposes_combined_deploy_and_progress_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operator, _ = self._operator(Path(directory), executor=FakeExecutor())
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
                code = operator_main(
                    ["deploy", "--environment", "staging"],
                    operator_factory=lambda _path, _authority: operator,
                )
            result = json.loads(stdout.getvalue())

        self.assertEqual(code, 0)
        self.assertTrue(stdout.getvalue().startswith("{\n  \"blockers\":"))
        self.assertEqual(result["outcome"], "succeeded")
        self.assertRegex(result["progress_digest"], r"^sha256:[0-9a-f]{64}$")
        invocation = stderr.getvalue()
        self.assertIn("Operator invocation:", invocation)
        self.assertIn("  operation: deploy", invocation)
        self.assertIn("  environment: staging", invocation)
        self.assertIn("  source authority: accepted", invocation)
        self.assertIn("  fixture selected: none", invocation)
        self.assertTrue(invocation.startswith("Operator invocation:\n"))
        self.assertTrue(invocation.endswith("\n\n"))

    def test_local_gcp_discovery_blocks_wrong_project_without_retaining_token(self) -> None:
        observed = (
            subprocess.CompletedProcess([], 0, "operator@example.com\n", ""),
            subprocess.CompletedProcess([], 0, "wrong-project\n", ""),
            subprocess.CompletedProcess([], 0, "discarded-access-token\n", ""),
        )
        with mock.patch.object(local_adapters.subprocess, "run", side_effect=observed):
            result = ProfileGcp(Path("/usr/bin/gcloud"), Path("/tmp/gcloud")).inspect(
                {
                    "project_id": "comfforts-platform-non-prod",
                    "project_number": "455651441682",
                    "region": "us-west1",
                }
            )

        self.assertEqual(result.blockers, ("OPERATOR_PROJECT_MISMATCH",))
        self.assertNotIn("discarded-access-token", repr(result))

    def test_local_factory_arms_executor_only_for_complete_private_session(self) -> None:
        from infrastructure.operator.local_deployment import OperatorSessionFacts

        session = OperatorSessionFacts(
            active_account="operator@example.com",
            billing_account_reference="billingAccounts/ABCDEF-123456-789ABC",
            operator_issuer="https://accounts.google.com",
            operator_subject="123456789012345678901",
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            configuration = base / "gcloud"
            configuration.mkdir(mode=0o700)
            state = base / "state"
            with (
                mock.patch.dict(os.environ, {"CLOUDSDK_CONFIG": str(configuration)}),
                mock.patch.object(
                    local_adapters.shutil,
                    "which",
                    side_effect=lambda name: "/usr/bin/true"
                    if name in {"gcloud", "dig"}
                    else None,
                ),
                mock.patch.object(ProfileGcp, "operator_session", return_value=session),
                mock.patch.object(
                    ProfileGcp,
                    "application_default_ready",
                    return_value=True,
                ),
            ):
                operator = build_local_operator(PROJECT_ROOT, state)
                state_mode = state.stat().st_mode & 0o777
                work_mode = (state / "work/deployment").stat().st_mode & 0o777

        self.assertIsNotNone(operator._adapters.executor)
        self.assertEqual(state_mode, 0o700)
        self.assertEqual(work_mode, 0o700)


if __name__ == "__main__":
    unittest.main()
