"""AP-M9-W4 interactive lifecycle behavior through the public operator seam."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator import (
    DiscoverySnapshot,
    GitSnapshot,
    LifecycleOperator,
    OperatorAdapters,
)
from infrastructure.operator.local import LocalFilesystem


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


if __name__ == "__main__":
    unittest.main()
