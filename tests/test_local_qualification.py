"""Exact local qualification readback composition tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator._interfaces import StatusResult
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_handoffs import (
    ApplicationHandoffRecord,
    LocalApplicationHandoffs,
)
from infrastructure.operator.local_qualification import (
    LocalQualificationStateReader,
    ProviderQualificationSnapshot,
)
from infrastructure.operator.qualification import ComponentRevision


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATION_DIGEST = "sha256:" + ("4" * 64)


@dataclass
class FakeStatus:
    conflicts: tuple[str, ...] = ()

    def status(self, environment: str) -> StatusResult:
        return StatusResult(
            {
                "environment": environment,
                "journal_digest": "sha256:" + ("3" * 64),
                "lifecycle_state": "deployed",
                "profile_digest": "sha256:" + ("1" * 64),
                "source_revision": "a" * 40,
                "specification_digest": "sha256:" + ("2" * 64),
            },
            self.conflicts,
        )


@dataclass
class FakeGenerations:
    proposal: RegistrationGenerationProposal

    def current(self, environment: str) -> RegistrationGenerationProposal:
        del environment
        return self.proposal


@dataclass
class FakeProvider:
    snapshot: ProviderQualificationSnapshot

    def read_current(self, environment: str) -> ProviderQualificationSnapshot:
        del environment
        return self.snapshot


def _proposal() -> RegistrationGenerationProposal:
    registrations = [
        {
            "application_id": application_id,
            "lifecycle": "active",
            "registration_revision": 1,
        }
        for application_id in (
            "fixture-authenticated",
            "fixture-public",
            "fixture-restricted",
        )
    ]
    return RegistrationGenerationProposal(
        environment="staging",
        registration_set={
            "generation": 7,
            "registrations": registrations,
        },
        compiled_configuration={},
        ownership_manifest={},
        generation_digest=GENERATION_DIGEST,
        content_digest="sha256:" + ("5" * 64),
    )


class LocalQualificationStateReaderTest(unittest.TestCase):
    def _reader(
        self,
        directory: str,
        *,
        generations: FakeGenerations | None = None,
        provider: FakeProvider | None = None,
    ) -> LocalQualificationStateReader:
        filesystem = LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
        handoffs = LocalApplicationHandoffs(filesystem)
        for index, application_id in enumerate(
            (
                "fixture-authenticated",
                "fixture-public",
                "fixture-restricted",
            ),
            start=1,
        ):
            handoffs.record(
                ApplicationHandoffRecord(
                    environment="staging",
                    application_id=application_id,
                    application_source_revision=f"{index}" * 40,
                    integration_bundle_digest="sha256:" + (f"{index}" * 64),
                    attachment_bundle_digest="sha256:" + (f"{index + 3}" * 64),
                    attachment_revision=1,
                    registration_generation=7,
                    registration_generation_digest=GENERATION_DIGEST,
                )
            )
        selected_provider = provider or FakeProvider(
            ProviderQualificationSnapshot(
                environment="staging",
                active_generation_digest=GENERATION_DIGEST,
                component_revisions=(
                    ComponentRevision("shared-edge", "sha256:" + ("9" * 64)),
                ),
            )
        )
        return LocalQualificationStateReader(
            FakeStatus(),
            generations or FakeGenerations(_proposal()),
            handoffs,
            selected_provider,
        )

    def test_composes_exact_environment_generation_provider_and_fixture_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current = self._reader(directory).read_current("staging")

        self.assertEqual(current.registration_generation_digest, GENERATION_DIGEST)
        self.assertEqual(
            tuple(item.application_id for item in current.fixture_revisions),
            (
                "fixture-authenticated",
                "fixture-public",
                "fixture-restricted",
            ),
        )
        self.assertEqual(current.component_revisions[0].name, "shared-edge")

    def test_missing_fixture_or_provider_generation_mismatch_fails_closed(self) -> None:
        missing = _proposal()
        missing.registration_set["registrations"].pop()
        wrong_provider = FakeProvider(
            ProviderQualificationSnapshot(
                environment="staging",
                active_generation_digest="sha256:" + ("f" * 64),
                component_revisions=(
                    ComponentRevision("shared-edge", "sha256:" + ("9" * 64)),
                ),
            )
        )
        cases = (
            {"generations": FakeGenerations(missing)},
            {"provider": wrong_provider},
        )
        for values in cases:
            with self.subTest(values=values), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    self._reader(directory, **values).read_current("staging")


if __name__ == "__main__":
    unittest.main()
