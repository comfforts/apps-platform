"""Focused tests for the human-run platform workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
import base64
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
    OperatorSessionError,
    ProfileGcp,
    SystemConsolePageLauncher,
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
    contexts: list[StageContext] = field(default_factory=list)

    def execute(self, context: StageContext) -> StageExecution:
        stage_id = str(context.stage["stage_id"])
        self.calls.append(stage_id)
        self.contexts.append(context)
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


@dataclass
class FakeActiveSourceReader:
    revision: str

    def active_platform_source_revision(self, environment: str) -> str:
        if environment != "staging":
            raise ValueError("unsupported environment")
        return self.revision


class OperatorLifecycleTest(unittest.TestCase):
    def _operator(
        self,
        state_root: Path,
        *,
        git: FakeGit | None = None,
        terminal: FakeTerminal | None = None,
        blocker: str | None = None,
        executor: FakeExecutor | None = None,
        execution_blockers: tuple[str, ...] = (),
        active_source_reader: FakeActiveSourceReader | None = None,
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
            execution_blockers=execution_blockers,
        )
        return (
            LifecycleOperator(
                adapters,
                active_source_reader=active_source_reader,
            ),
            selected_terminal,
        )

    def test_execution_adapter_reports_its_exact_unavailable_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            operator, terminal = self._operator(
                Path(directory),
                execution_blockers=("OPERATOR_IDENTITY_SESSION_UNAVAILABLE",),
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            result = operator.execute("staging", prepared.specification_digest)

        self.assertEqual(result.outcome, "blocked")
        self.assertEqual(
            result.blockers,
            ("OPERATOR_IDENTITY_SESSION_UNAVAILABLE",),
        )
        self.assertIsNone(result.progress_digest)
        self.assertIn(
            "Readiness blocker OPERATOR_IDENTITY_SESSION_UNAVAILABLE:",
            "\n".join(terminal.messages),
        )

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

    def test_cli_cancel_is_local_machine_readable_and_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = FakeTerminal([True, True])
            operator, _ = self._operator(
                Path(directory),
                terminal=terminal,
                executor=FakeExecutor([StageExecution("waiting")]),
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None
            operator.execute("staging", prepared.specification_digest)

            first_stdout = io.StringIO()
            first_stderr = io.StringIO()
            with mock.patch("sys.stdout", first_stdout), mock.patch(
                "sys.stderr", first_stderr
            ):
                first_code = operator_main(
                    ["cancel", "--environment", "staging"],
                    preflight_factory=lambda _path, _authority: operator,
                )
            repeated_stdout = io.StringIO()
            with mock.patch("sys.stdout", repeated_stdout), mock.patch(
                "sys.stderr", io.StringIO()
            ):
                repeated_code = operator_main(
                    ["cancel", "--environment", "staging"],
                    preflight_factory=lambda _path, _authority: operator,
                )

        first = json.loads(first_stdout.getvalue())
        repeated = json.loads(repeated_stdout.getvalue())
        self.assertEqual(first_code, 0)
        self.assertEqual(first["outcome"], "cancelled")
        self.assertEqual(first["active_stage"], "preflight")
        self.assertEqual(first["specification_digest"], prepared.specification_digest)
        self.assertRegex(first["progress_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(repeated_code, 0)
        self.assertEqual(repeated["outcome"], "unchanged")
        self.assertEqual(len(terminal.prompts), 2)
        self.assertIn("  operation: cancel", first_stderr.getvalue())

    def test_cli_prints_safe_boundary_errors_before_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            blocked, _ = self._operator(
                Path(directory),
                git=FakeGit(clean=False),
                terminal=FakeTerminal([]),
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
                code = operator_main(
                    ["preflight", "--environment", "staging"],
                    preflight_factory=lambda _path, _authority: blocked,
                )
            result = json.loads(stdout.getvalue())

        self.assertEqual(code, 2)
        self.assertEqual(result["blockers"], ["SOURCE_NOT_CLEAN"])
        self.assertIn("Operator error:", stderr.getvalue())
        self.assertIn("  component: source-control", stderr.getvalue())
        self.assertIn("  code: SOURCE_NOT_CLEAN", stderr.getvalue())

    def test_cli_catches_unexpected_errors_without_printing_exception_text(self) -> None:
        def failing_factory(_path: Path, _authority: str) -> LifecycleOperator:
            raise OSError("private provider detail must not be printed")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            code = operator_main(
                ["status", "--environment", "staging"],
                operator_factory=failing_factory,
            )
        result = json.loads(stdout.getvalue())
        transcript = stderr.getvalue()

        self.assertEqual(code, 2)
        self.assertEqual(result["blockers"], ["OPERATOR_INTERNAL_ERROR"])
        self.assertIn("  exception_type: OSError", transcript)
        self.assertNotIn("private provider detail", transcript)

    def test_console_narration_blocks_end_with_an_empty_line(self) -> None:
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            local_adapters.ConsoleTerminal().write("Verified provider readback.")

        self.assertEqual(stderr.getvalue(), "Verified provider readback.\n\n")

    def test_console_narration_redacts_values_without_hiding_safe_guidance(self) -> None:
        message = "\n".join(
            (
                "Never enter the OAuth client secret in this terminal.",
                "client_secret=GOCSPX-private-value",
                "Authorization: Bearer ya29.private-value",
                "Provider URL: https://operator:private-value@example.com/path",
                "-----BEGIN PRIVATE KEY-----",
                "private-key-material",
                "-----END PRIVATE KEY-----",
            )
        )
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            local_adapters.ConsoleTerminal().write(message)

        transcript = stderr.getvalue()
        self.assertIn("Never enter the OAuth client secret", transcript)
        self.assertIn("client_secret=[REDACTED]", transcript)
        self.assertIn("Authorization: [REDACTED]\n", transcript)
        self.assertIn("https://operator:[REDACTED]@example.com/path", transcript)
        self.assertIn("[REDACTED PRIVATE KEY]", transcript)
        self.assertNotIn("GOCSPX-private-value", transcript)
        self.assertNotIn("ya29.private-value", transcript)
        self.assertNotIn("private-key-material", transcript)

    def test_console_page_launcher_opens_only_reviewed_staging_oauth_pages(self) -> None:
        launcher = SystemConsolePageLauncher()
        url = (
            "https://console.cloud.google.com/auth/branding?"
            "project=comfforts-platform-non-prod"
        )
        with mock.patch(
            "infrastructure.operator.local.webbrowser.open",
            return_value=True,
        ) as browser_open:
            self.assertTrue(launcher.open(url))

        browser_open.assert_called_once_with(url, new=2, autoraise=True)
        with self.assertRaisesRegex(ValueError, "outside the staging allow-list"):
            launcher.open(
                "https://console.cloud.google.com/auth/branding?project=other-project"
            )
        with self.assertRaisesRegex(ValueError, "outside the staging allow-list"):
            launcher.open(
                "https://example.com/auth/branding?"
                "project=comfforts-platform-non-prod"
            )
        with self.assertRaisesRegex(ValueError, "outside the staging allow-list"):
            launcher.open(
                "https://operator@console.cloud.google.com/auth/branding?"
                "project=comfforts-platform-non-prod"
            )

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
        self.assertEqual(len(executor.calls), 12)
        tls_context = next(
            context
            for context in executor.contexts
            if context.stage["stage_id"] == "tls-readiness"
        )
        self.assertEqual(
            {name for name, _ in tls_context.inputs},
            {
                "foundation.foundation-reference",
                "image-publish.shared-edge-image-digest",
                "oauth-configuration.oauth-client-id",
                "oauth-configuration.oauth-secret-version",
                "generation-publish.registration-generation-reference",
                "shared-edge.edge-reference",
                "runtime-activation.active-runtime-binding",
            },
        )

    def test_status_observes_distinct_checkout_operation_and_runtime_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            git = FakeGit(revision="a" * 40)
            operator, _ = self._operator(
                Path(directory),
                git=git,
                executor=FakeExecutor(),
                active_source_reader=FakeActiveSourceReader("c" * 40),
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None
            operator.execute("staging", prepared.specification_digest)
            git.revision = "b" * 40

            result = operator.status("staging")
            status = result.environment_status

        self.assertEqual(result.conflicts, ())
        self.assertEqual(status["checkout_source_revision"], "b" * 40)
        self.assertEqual(status["recorded_deployment_source_revision"], "a" * 40)
        self.assertEqual(status["active_runtime_source_revision"], "c" * 40)
        self.assertEqual(
            status["source_diagnostics"],
            [
                "CHECKOUT_DIFFERS_FROM_ACTIVE_RUNTIME",
                "CHECKOUT_DIFFERS_FROM_DEPLOYMENT",
                "DEPLOYMENT_DIFFERS_FROM_ACTIVE_RUNTIME",
            ],
        )
        self.assertEqual(status["blockers"], [])

    def test_operator_stages_are_numbered_and_tls_resume_repeats_stage_six(self) -> None:
        @dataclass
        class FailTlsOnceExecutor(FakeExecutor):
            failed_tls: bool = False

            def execute(self, context: StageContext) -> StageExecution:
                if context.stage["stage_id"] == "tls-readiness" and not self.failed_tls:
                    self.calls.append("tls-readiness")
                    self.contexts.append(context)
                    self.failed_tls = True
                    return StageExecution(
                        "failed",
                        blockers=("SHARED_EDGE_INPUT_INCOMPLETE",),
                    )
                return super().execute(context)

        with tempfile.TemporaryDirectory() as directory:
            terminal = FakeTerminal([True])
            executor = FailTlsOnceExecutor()
            operator, _ = self._operator(
                Path(directory),
                terminal=terminal,
                executor=executor,
            )
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None

            failed = operator.execute("staging", prepared.specification_digest)
            first_run_stages = [
                message for message in terminal.messages if message.startswith("▸ Stage")
            ]
            terminal.messages.clear()
            resumed = operator.execute("staging", prepared.specification_digest)
            resumed_stages = [
                message for message in terminal.messages if message.startswith("▸ Stage")
            ]

        self.assertEqual(failed.outcome, "failed")
        self.assertEqual(
            first_run_stages,
            [
                "▸ Stage 1/7 · Verify source, tools, identity, and project",
                "▸ Stage 2/7 · Bootstrap state and platform foundation",
                "▸ Stage 3/7 · Publish the immutable image and initial generation",
                "▸ Stage 4/7 · Configure OAuth",
                "▸ Stage 5/7 · Create the Shared Edge",
                "▸ Stage 6/7 · Configure DNS and TLS",
            ],
        )
        self.assertEqual(resumed.outcome, "succeeded")
        self.assertEqual(
            resumed_stages,
            [
                "▸ Stage 6/7 · Configure DNS and TLS",
                "▸ Stage 7/7 · Verify the deployed platform",
            ],
        )

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

    def test_source_change_requires_explicit_idempotent_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            git = FakeGit()
            terminal = FakeTerminal([True, True, True])
            executor = FakeExecutor(
                [StageExecution("succeeded"), StageExecution("waiting")]
            )
            operator, _ = self._operator(
                state,
                git=git,
                terminal=terminal,
                executor=executor,
            )
            first = operator.prepare("staging")
            assert first.specification_digest is not None
            operator.execute("staging", first.specification_digest)
            git.revision = "b" * 40
            conflict = operator.prepare("staging")
            cancelled = operator.cancel("staging")
            repeated = operator.cancel("staging")
            replacement = operator.prepare("staging")
            terminal_progress = json.loads(
                next(state.rglob("progress/*.final.v1.json")).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(conflict.blockers, ("ACTIVE_OPERATION_CONFLICT",))
        self.assertEqual(cancelled.outcome, "cancelled")
        self.assertEqual(repeated.outcome, "unchanged")
        self.assertEqual(cancelled.progress, terminal_progress)
        self.assertEqual(terminal_progress["status"], "cancelled")
        self.assertEqual(
            [item["stage_id"] for item in terminal_progress["completed"]],
            ["preflight"],
        )
        self.assertEqual(terminal_progress["active_stage"], "bootstrap-services")
        self.assertEqual(replacement.outcome, "prepared")
        self.assertNotEqual(
            replacement.specification_digest,
            first.specification_digest,
        )
        self.assertEqual(executor.calls, ["preflight", "bootstrap-services"])
        self.assertEqual(len(terminal.prompts), 3)
        transcript = "\n".join(terminal.messages)
        self.assertIn("Active deployment conflict", transcript)
        self.assertIn(first.specification_digest, transcript)
        self.assertIn("active stage: bootstrap-services", transcript)
        self.assertIn("make platform-cancel", transcript)

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

    def test_legacy_waiting_progress_adds_hostname_and_preserves_resume_authority(
        self,
    ) -> None:
        @dataclass
        class WaitingTlsExecutor(FakeExecutor):
            def execute(self, context: StageContext) -> StageExecution:
                if context.stage["stage_id"] == "tls-readiness":
                    self.calls.append("tls-readiness")
                    self.contexts.append(context)
                    return StageExecution(
                        "waiting",
                        blockers=(
                            "CERTIFICATE_READINESS_PENDING",
                            "TERRAFORM_READINESS_PENDING",
                        ),
                    )
                return super().execute(context)

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            executor = WaitingTlsExecutor()
            operator, _ = self._operator(state, executor=executor)
            prepared = operator.prepare("staging")
            assert prepared.specification_digest is not None
            result = operator.execute("staging", prepared.specification_digest)
            self.assertEqual(result.outcome, "waiting")

            path = next(state.rglob("current-progress.v1.json"))
            progress = json.loads(path.read_text(encoding="utf-8"))
            shared_edge = next(
                entry
                for entry in progress["completed"]
                if entry["stage_id"] == "shared-edge"
            )
            shared_edge["outputs"] = [
                output
                for output in shared_edge["outputs"]
                if output["name"] != "hostname"
            ]
            edge_reference = next(
                output
                for output in shared_edge["outputs"]
                if output["name"] == "edge-reference"
            )
            edge_reference["value"] = json.dumps(
                {
                    "edge": {"hostname": "apps-staging.comfforts.com"},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            path.write_text(
                json.dumps(progress, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            normalized = operator._load_progress("staging")
            conflict = operator._conflicting_progress(
                "staging",
                "sha256:" + "f" * 64,
            )

        assert normalized is not None
        normalized_edge = next(
            entry
            for entry in normalized["completed"]
            if entry["stage_id"] == "shared-edge"
        )
        self.assertEqual(
            [output["name"] for output in normalized_edge["outputs"]],
            ["edge-reference", "hostname", "reserved-address"],
        )
        self.assertIsNotNone(conflict)

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

    def test_operator_session_retries_transient_billing_timeout(self) -> None:
        claims = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "email": "operator@example.com",
                    "iss": "https://accounts.google.com",
                    "sub": "123456789012345678901",
                }
            ).encode("utf-8")
        ).rstrip(b"=").decode("ascii")
        observed = (
            subprocess.CompletedProcess([], 0, "operator@example.com\n", ""),
            subprocess.CompletedProcess([], 0, "comfforts-platform-non-prod\n", ""),
            subprocess.TimeoutExpired([], 30, stderr="temporary timeout"),
            subprocess.CompletedProcess(
                [],
                0,
                "billingAccounts/ABCDEF-123456-789ABC\n",
                "",
            ),
            subprocess.CompletedProcess([], 0, f"header.{claims}.signature\n", ""),
        )
        profile = {
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
        }
        with mock.patch.object(
            local_adapters.subprocess,
            "run",
            side_effect=observed,
        ) as run:
            session = ProfileGcp(
                Path("/usr/bin/gcloud"),
                Path("/tmp/gcloud"),
            ).require_operator_session(profile)

        self.assertEqual(session.active_account, "operator@example.com")
        self.assertEqual(run.call_count, 5)

    def test_operator_session_reports_persistent_billing_timeout_with_diagnostic(
        self,
    ) -> None:
        profile = {
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration = root / "gcloud"
            configuration.mkdir(mode=0o700)
            state = root / ".platform-operator"
            state.mkdir(mode=0o700)
            observed = (
                subprocess.CompletedProcess([], 0, "operator@example.com\n", ""),
                subprocess.CompletedProcess(
                    [],
                    0,
                    "comfforts-platform-non-prod\n",
                    "",
                ),
                subprocess.TimeoutExpired([], 30, stderr="first timeout"),
                subprocess.TimeoutExpired([], 30, stderr="second timeout"),
            )
            with mock.patch.object(
                local_adapters.subprocess,
                "run",
                side_effect=observed,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^OPERATOR_BILLING_READBACK_TIMEOUT$",
                ) as raised:
                    ProfileGcp(
                        Path("/usr/bin/gcloud"),
                        configuration,
                        private_state_root=state,
                    ).require_operator_session(profile)

            diagnostic_path = Path(raised.exception.diagnostic["diagnostic_path"])
            self.assertIn(
                "second timeout",
                diagnostic_path.read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "second timeout",
                json.dumps(raised.exception.diagnostic),
            )

    def test_application_default_failure_is_exact_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configuration = root / "gcloud"
            configuration.mkdir(mode=0o700)
            state = root / ".platform-operator"
            state.mkdir(mode=0o700)
            failed = subprocess.CompletedProcess(
                [],
                1,
                "",
                "reauthentication required",
            )
            with mock.patch.object(
                local_adapters.subprocess,
                "run",
                side_effect=(failed, failed),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^OPERATOR_APPLICATION_DEFAULT_CREDENTIALS_UNAVAILABLE$",
                ) as raised:
                    ProfileGcp(
                        Path("/usr/bin/gcloud"),
                        configuration,
                        private_state_root=state,
                    ).require_application_default()

            diagnostic_path = Path(raised.exception.diagnostic["diagnostic_path"])
            self.assertIn(
                "reauthentication required",
                diagnostic_path.read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "reauthentication required",
                json.dumps(raised.exception.diagnostic),
            )

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
                mock.patch.object(
                    ProfileGcp,
                    "require_operator_session",
                    return_value=session,
                ),
                mock.patch.object(
                    ProfileGcp,
                    "require_application_default",
                    return_value=None,
                ),
            ):
                operator = build_local_operator(PROJECT_ROOT, state)
                state_mode = state.stat().st_mode & 0o777
                work_mode = (state / "work/deployment").stat().st_mode & 0o777

        self.assertIsNotNone(operator._adapters.executor)
        self.assertEqual(state_mode, 0o700)
        self.assertEqual(work_mode, 0o700)

    def test_local_factory_preserves_precise_operator_session_blocker(self) -> None:
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
                mock.patch.object(
                    ProfileGcp,
                    "require_operator_session",
                    side_effect=OperatorSessionError(
                        "OPERATOR_BILLING_READBACK_TIMEOUT"
                    ),
                ),
            ):
                operator = build_local_operator(PROJECT_ROOT, state)

        self.assertIsNone(operator._adapters.executor)
        self.assertEqual(
            operator._adapters.execution_blockers,
            ("OPERATOR_BILLING_READBACK_TIMEOUT",),
        )


if __name__ == "__main__":
    unittest.main()
