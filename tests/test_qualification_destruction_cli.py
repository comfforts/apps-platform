"""Thin AP-M9-W8 qualify and destroy command tests."""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass, field
import io
import json
from pathlib import Path
import tempfile
import unittest

from contracts.lifecycle import lifecycle_digest, load_lifecycle_document
from infrastructure.operator.cli import main
from infrastructure.operator.destruction import DestructionResult
from infrastructure.operator.qualification import QualificationResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_VECTOR = (
    PROJECT_ROOT
    / "contracts/lifecycle/test-vectors/valid/"
    "qualification-evidence.staging.synthetic.v1.json"
)


@dataclass
class FakeQualification:
    environments: list[str] = field(default_factory=list)

    def qualify_current(self, environment: str) -> QualificationResult:
        self.environments.append(environment)
        evidence = json.loads(EVIDENCE_VECTOR.read_text(encoding="utf-8"))
        return QualificationResult(
            outcome="qualified",
            evidence=evidence,
            evidence_digest=lifecycle_digest(
                evidence,
                "qualification-evidence",
            ),
        )


@dataclass
class FakeDestruction:
    environments: list[str] = field(default_factory=list)

    def destroy_current(self, environment: str) -> DestructionResult:
        self.environments.append(environment)
        return DestructionResult(
            outcome="destroyed",
            specification_digest="sha256:" + ("d" * 64),
            last_closed_stage="destruction-readback",
        )


def _result(arguments: list[str], **factories: object) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    with redirect_stdout(output):
        code = main(arguments, **factories)  # type: ignore[arg-type]
    return code, json.loads(output.getvalue())


class QualificationDestructionCliTest(unittest.TestCase):
    def test_qualify_discovers_current_inputs_and_publishes_canonical_evidence(self) -> None:
        qualification = FakeQualification()
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "operator"
            code, result = _result(
                [
                    "qualify",
                    "--environment",
                    "staging",
                    "--state-directory",
                    str(state_root),
                ],
                qualification_factory=lambda _: qualification,
            )
            evidence_path = state_root / str(result["evidence_path"])
            loaded = load_lifecycle_document(
                evidence_path,
                "qualification-evidence",
            )
            pointer = json.loads(
                (
                    state_root
                    / "environments/staging/qualification/"
                    "current-evidence.v1.json"
                ).read_text(encoding="utf-8")
            )

        self.assertEqual(code, 0)
        self.assertEqual(result["outcome"], "qualified")
        self.assertEqual(qualification.environments, ["staging"])
        self.assertEqual(loaded.violations, ())
        self.assertEqual(loaded.digest, result["evidence_digest"])
        self.assertEqual(pointer["evidence_digest"], result["evidence_digest"])

    def test_destroy_requires_only_environment_and_reports_closed_progress(self) -> None:
        destruction = FakeDestruction()

        code, result = _result(
            ["destroy", "--environment", "staging"],
            destruction_factory=lambda _: destruction,
        )

        self.assertEqual(code, 0)
        self.assertEqual(result["outcome"], "destroyed")
        self.assertEqual(result["last_closed_stage"], "destruction-readback")
        self.assertEqual(destruction.environments, ["staging"])

    def test_live_authority_gates_fail_closed_without_partial_artifacts(self) -> None:
        for operation, blocker in (
            ("qualify", "W9_LIVE_QUALIFICATION_AUTHORITY_REQUIRED"),
            ("destroy", "W9_DESTRUCTION_AUTHORITY_REQUIRED"),
        ):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                state_root = Path(directory) / "operator"
                code, result = _result(
                    [
                        operation,
                        "--environment",
                        "staging",
                        "--state-directory",
                        str(state_root),
                    ]
                )
                self.assertEqual(code, 2)
                self.assertEqual(result["outcome"], "blocked")
                self.assertEqual(result["blockers"], [blocker])
                self.assertFalse(state_root.exists())


if __name__ == "__main__":
    unittest.main()
