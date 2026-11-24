"""AP-M9-W8 safe-destruction specification and policy tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from contracts.lifecycle import validate_lifecycle_document
from infrastructure.operator.destruction import (
    DESTRUCTIBLE_PLATFORM_RESOURCES,
    RETAINED_PLATFORM_RESOURCES,
    DestructionRequest,
    DestructionSnapshot,
    compile_destruction_specification,
)


SOURCE_REVISION = "a" * 40


def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


def request() -> DestructionRequest:
    return DestructionRequest(
        environment="staging",
        source_revision=SOURCE_REVISION,
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


class DestructionSpecificationTest(unittest.TestCase):
    def test_connected_shared_vpc_foundation_is_retained(self) -> None:
        self.assertTrue(
            {
                "application-subnet",
                "shared-network",
                "shared-vpc-host",
            }.issubset(RETAINED_PLATFORM_RESOURCES)
        )

    def test_exact_platform_inventory_compiles_separate_destroy_specification(self) -> None:
        result = compile_destruction_specification(request(), snapshot())

        self.assertEqual(result.outcome, "prepared")
        self.assertEqual(result.blockers, ())
        self.assertRegex(
            result.specification_digest or "",
            r"^sha256:[0-9a-f]{64}$",
        )
        assert result.specification is not None
        self.assertEqual(result.specification["operation"], "destroy")
        boundary = result.specification["destructive_boundary"]
        self.assertEqual(
            set(boundary["resource_types"]),
            set(DESTRUCTIBLE_PLATFORM_RESOURCES),
        )
        self.assertTrue(set(RETAINED_PLATFORM_RESOURCES).isdisjoint(
            boundary["resource_types"]
        ))
        self.assertEqual(
            validate_lifecycle_document(
                result.specification,
                "deployment-specification",
            ),
            (),
        )

    def test_candidate_destruction_remains_bound_to_candidate_authority(self) -> None:
        candidate_request = replace(request(), source_authority="candidate")
        candidate_snapshot = replace(snapshot(), source_authority="candidate")

        result = compile_destruction_specification(
            candidate_request,
            candidate_snapshot,
        )

        self.assertEqual(result.outcome, "prepared")
        assert result.specification is not None
        self.assertEqual(result.specification["source"]["authority"], "candidate")

    def test_active_attachment_ownership_or_inventory_mismatch_blocks_compilation(self) -> None:
        cases = {
            "active": (
                replace(snapshot(), active_application_ids=("fixture-public",)),
                "ACTIVE_APPLICATION_ATTACHMENTS",
            ),
            "ownership": (
                replace(snapshot(), ownership_matches=False),
                "DESTRUCTION_OWNERSHIP_MISMATCH",
            ),
            "missing resource": (
                replace(
                    snapshot(),
                    platform_resource_types=DESTRUCTIBLE_PLATFORM_RESOURCES[:-1],
                ),
                "DESTRUCTION_INVENTORY_MISMATCH",
            ),
            "retained mismatch": (
                replace(snapshot(), retained_resource_types=("state-backend",)),
                "DESTRUCTION_RETAINED_INVENTORY_MISMATCH",
            ),
        }

        for label, (current, blocker) in cases.items():
            with self.subTest(label=label):
                result = compile_destruction_specification(request(), current)
                self.assertEqual(result.outcome, "blocked")
                self.assertIn(blocker, result.blockers)
                self.assertIsNone(result.specification)

    def test_stale_environment_or_revision_binding_blocks_compilation(self) -> None:
        cases = {
            "environment": (
                replace(snapshot(), environment="production"),
                "DESTRUCTION_ENVIRONMENT_MISMATCH",
            ),
            "source": (
                replace(snapshot(), source_revision="f" * 40),
                "DESTRUCTION_SOURCE_MISMATCH",
            ),
            "profile": (
                replace(snapshot(), profile_digest=_digest("f")),
                "DESTRUCTION_PROFILE_MISMATCH",
            ),
            "specification": (
                replace(snapshot(), deployed_specification_digest=_digest("f")),
                "DESTRUCTION_SPECIFICATION_MISMATCH",
            ),
            "progress": (
                replace(snapshot(), deployment_progress_digest=_digest("f")),
                "DESTRUCTION_PROGRESS_MISMATCH",
            ),
            "generation": (
                replace(snapshot(), registration_generation_digest=_digest("f")),
                "DESTRUCTION_GENERATION_MISMATCH",
            ),
            "evidence": (
                replace(snapshot(), qualification_evidence_digest=_digest("f")),
                "DESTRUCTION_EVIDENCE_MISMATCH",
            ),
        }

        for label, (current, blocker) in cases.items():
            with self.subTest(label=label):
                result = compile_destruction_specification(request(), current)
                self.assertEqual(result.outcome, "blocked")
                self.assertIn(blocker, result.blockers)

    def test_contract_rejects_boundary_omission_expansion_and_retained_resources(self) -> None:
        result = compile_destruction_specification(request(), snapshot())
        assert result.specification is not None
        boundary = result.specification["destructive_boundary"]
        assert isinstance(boundary, dict)

        missing = dict(result.specification)
        missing_boundary = dict(boundary)
        missing_boundary["resource_types"] = list(
            DESTRUCTIBLE_PLATFORM_RESOURCES[:-1]
        )
        missing["destructive_boundary"] = missing_boundary

        retained = dict(result.specification)
        retained_boundary = dict(boundary)
        retained_boundary["resource_types"] = [
            *DESTRUCTIBLE_PLATFORM_RESOURCES,
            "state-backend",
        ]
        retained["destructive_boundary"] = retained_boundary

        application = deepcopy(result.specification)
        application_boundary = application["destructive_boundary"]
        assert isinstance(application_boundary, dict)
        application_resources = application_boundary["resource_types"]
        assert isinstance(application_resources, list)
        application_resources.append("application-state")
        stages = application["stages"]
        assert isinstance(stages, list)
        foundation = next(
            stage
            for stage in stages
            if isinstance(stage, dict)
            and stage.get("stage_id") == "foundation-destroy"
        )
        foundation_resources = foundation["resource_types"]
        assert isinstance(foundation_resources, list)
        foundation_resources.append("application-state")

        for label, candidate in (
            ("missing", missing),
            ("retained", retained),
            ("application", application),
        ):
            with self.subTest(label=label):
                violations = validate_lifecycle_document(
                    candidate,
                    "deployment-specification",
                )
                self.assertIn(
                    "DESTRUCTIVE_BOUNDARY_INVALID",
                    {item.code for item in violations},
                )


if __name__ == "__main__":
    unittest.main()
