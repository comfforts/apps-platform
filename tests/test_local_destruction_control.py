"""Private destruction specification and progress persistence tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from infrastructure.operator.destruction import (
    DESTRUCTIBLE_PLATFORM_RESOURCES,
    RETAINED_PLATFORM_RESOURCES,
    DestructionRequest,
    DestructionSnapshot,
    DestructionStageClosure,
    compile_destruction_specification,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_destruction import LocalDestructionControl


PROJECT_ROOT = Path(__file__).resolve().parents[1]

def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


def _specification() -> tuple[dict[str, object], str]:
    request = DestructionRequest(
        environment="staging",
        source_revision="a" * 40,
        profile_digest=_digest("1"),
        deployed_specification_digest=_digest("2"),
        deployment_journal_digest=_digest("3"),
        registration_generation_digest=_digest("4"),
        qualification_evidence_digest=_digest("5"),
    )
    snapshot = DestructionSnapshot(
        environment=request.environment,
        lifecycle_state="deployed",
        source_revision=request.source_revision,
        profile_digest=request.profile_digest,
        deployed_specification_digest=request.deployed_specification_digest,
        deployment_journal_digest=request.deployment_journal_digest,
        registration_generation_digest=request.registration_generation_digest,
        qualification_evidence_digest=request.qualification_evidence_digest,
        active_application_ids=(),
        platform_resource_types=DESTRUCTIBLE_PLATFORM_RESOURCES,
        retained_resource_types=RETAINED_PLATFORM_RESOURCES,
        ownership_matches=True,
    )
    prepared = compile_destruction_specification(request, snapshot)
    assert prepared.specification is not None
    assert prepared.specification_digest is not None
    return prepared.specification, prepared.specification_digest


class LocalDestructionControlTest(unittest.TestCase):
    def _control(self, directory: str) -> LocalDestructionControl:
        return LocalDestructionControl(
            LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
        )

    def test_specification_approval_and_progress_are_create_only(self) -> None:
        specification, digest = _specification()
        stages = specification["stages"]
        assert isinstance(stages, list)
        closures = tuple(
            DestructionStageClosure(
                str(stage["stage_id"]),
                tuple(
                    (str(output), "sha256:" + ("a" * 64))
                    for output in stage["produces"]
                ),
            )
            for stage in stages
            if isinstance(stage, dict)
        )
        with tempfile.TemporaryDirectory() as directory:
            control = self._control(directory)

            self.assertTrue(
                control.publish_specification("staging", digest, specification)
            )
            self.assertTrue(
                control.publish_specification("staging", digest, specification)
            )
            self.assertTrue(control.approve_specification("staging", digest))
            for closure in closures:
                self.assertTrue(
                    control.close_stage("staging", digest, closure)
                )
            self.assertEqual(control.closed_stages("staging", digest), closures)
            self.assertTrue(control.mark_complete("staging", digest))

    def test_conflicting_specification_or_progress_fails_closed(self) -> None:
        specification, digest = _specification()
        with tempfile.TemporaryDirectory() as directory:
            control = self._control(directory)
            self.assertTrue(
                control.publish_specification("staging", digest, specification)
            )
            changed = {**specification, "failure_behavior": "continue"}
            self.assertFalse(
                control.publish_specification("staging", digest, changed)
            )
            self.assertFalse(
                control.close_stage(
                    "staging",
                    digest,
                    DestructionStageClosure(
                        "destruction-preflight",
                        (("destruction-attestation", "unapproved"),),
                    ),
                )
            )

    def test_application_state_has_no_path_in_destruction_storage(self) -> None:
        source = (
            PROJECT_ROOT / "infrastructure/operator/local_destruction.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("application-state", source.lower())
        self.assertNotIn("terraform/fixtures", source)


if __name__ == "__main__":
    unittest.main()
