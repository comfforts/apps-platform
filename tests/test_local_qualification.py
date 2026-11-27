"""Exact local qualification readback composition tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator._interfaces import StatusResult
from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.integration import (
    GenerationActivationReadback,
    PlatformIntegrationState,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_handoffs import (
    ApplicationHandoffRecord,
    LocalApplicationHandoffs,
)
from infrastructure.operator.local_qualification import (
    LiveGenerationRollbackExercise,
    LocalQualificationStateReader,
    ProviderQualificationSnapshot,
)
from infrastructure.operator.qualification import (
    ComponentRevision,
    QualificationVerificationResult,
)
from infrastructure.operator.rollback import ReviewedGeneration


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATION_DIGEST = "sha256:" + ("4" * 64)


@dataclass
class FakeStatus:
    conflicts: tuple[str, ...] = ()

    def status(self, environment: str) -> StatusResult:
        return StatusResult(
            {
                "environment": environment,
                "progress_digest": "sha256:" + ("3" * 64),
                "lifecycle_state": "deployed",
                "profile_digest": "sha256:" + ("1" * 64),
                "source_authority": "accepted",
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
    registrations = []
    for application_id, admission_mode, identity_delivery, visibility in (
        ("fixture-authenticated", "authenticated", "required", "listed"),
        ("fixture-public", "public", "optional", "listed"),
        ("fixture-restricted", "restricted", "required", "listed"),
    ):
        audience = (
            f"urn:comfforts:app-platform:audience:{application_id}"
            if identity_delivery != "none"
            else None
        )
        registrations.append(
            {
                "admission": {"mode": admission_mode},
                "application_id": application_id,
                "attachments": [
                    {
                        "attachment_id": "primary",
                        "audience": audience,
                        "owner_application_id": application_id,
                        "resource_reference": (
                            "urn:comfforts:app-platform:gcp:cloud-run:"
                            f"123456789012:us-west1:{application_id}"
                        ),
                    }
                ],
                "catalogue": {
                    "summary": "Synthetic qualification application",
                    "title": application_id.replace("-", " ").title(),
                    "visibility": visibility,
                },
                "identity_delivery": identity_delivery,
                "lifecycle": "active",
                "registration_revision": 1,
                "route_prefix": f"/{application_id}",
            }
        )
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
        self.assertEqual(
            tuple(
                (
                    item.application_id,
                    item.admission_mode,
                    item.identity_delivery,
                    item.catalogue_visibility,
                    item.target_audience,
                )
                for item in current.fixture_policies
            ),
            (
                (
                    "fixture-authenticated",
                    "authenticated",
                    "required",
                    "listed",
                    "urn:comfforts:app-platform:audience:fixture-authenticated",
                ),
                (
                    "fixture-public",
                    "public",
                    "optional",
                    "listed",
                    "urn:comfforts:app-platform:audience:fixture-public",
                ),
                (
                    "fixture-restricted",
                    "restricted",
                    "required",
                    "listed",
                    "urn:comfforts:app-platform:audience:fixture-restricted",
                ),
            ),
        )

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


class LiveGenerationRollbackExerciseTest(unittest.TestCase):
    def test_reviews_predecessor_then_restores_exact_original_generation(self) -> None:
        predecessor_digest = "sha256:" + ("3" * 64)
        original_digest = "sha256:" + ("4" * 64)

        def reviewed(generation: int, digest: str, previous: str | None):
            proposal = RegistrationGenerationProposal(
                environment="staging",
                registration_set={
                    "generation": generation,
                    "previous_generation_digest": previous,
                },
                compiled_configuration={},
                ownership_manifest={},
                generation_digest=digest,
                content_digest="sha256:" + ("5" * 64),
            )
            return ReviewedGeneration(
                f"revision:{generation}",
                proposal,
                "a" * 40,
            )

        predecessor = reviewed(1, predecessor_digest, None)
        original = reviewed(2, original_digest, predecessor_digest)

        class Platform:
            def read_platform(self, environment):  # type: ignore[no-untyped-def]
                return PlatformIntegrationState(
                    environment,
                    "deployed",
                    "sha256:" + ("1" * 64),
                    "a" * 40,
                    "sha256:" + ("2" * 64),
                    "sha256:" + ("6" * 64),
                    2,
                    "apps-staging.comfforts.com",
                    "client.apps.googleusercontent.com",
                    "edge-caller",
                    "unqualified",
                )

        class Generations:
            selected = original

            def current(self, environment):  # type: ignore[no-untyped-def]
                del environment
                return self.selected

            def read_reviewed(self, environment, digest):  # type: ignore[no-untyped-def]
                del environment
                return predecessor if digest == predecessor_digest else original

            def activate(self, environment, reference, digest):  # type: ignore[no-untyped-def]
                del environment, reference
                self.selected = (
                    predecessor if digest == predecessor_digest else original
                )
                return GenerationActivationReadback(True, digest)

        class Terminal:
            def __init__(self) -> None:
                self.confirmations: list[str] = []
                self.messages: list[str] = []

            def write(self, message):  # type: ignore[no-untyped-def]
                self.messages.append(message)

            def confirm(self, prompt):  # type: ignore[no-untyped-def]
                del prompt
                return True

            def confirm_exact(self, prompt, expected):  # type: ignore[no-untyped-def]
                del prompt
                self.confirmations.append(expected)
                return True

        for predecessor_valid in (True, False):
            with self.subTest(predecessor_valid=predecessor_valid):
                generations = Generations()
                terminal = Terminal()
                observed: list[ReviewedGeneration] = []

                def verify_predecessor() -> QualificationVerificationResult:
                    observed.append(generations.selected)
                    return QualificationVerificationResult(
                        predecessor_valid,
                        ()
                        if predecessor_valid
                        else ("LIVE_PREDECESSOR_PUBLIC_NONE_IDENTITY_MISMATCH",),
                    )

                verified = LiveGenerationRollbackExercise(
                    Platform(),
                    generations,
                    terminal,
                    verify_predecessor,
                ).verify_rollback("staging", original_digest)

                self.assertEqual(verified.verified, predecessor_valid)
                self.assertEqual(observed, [predecessor])
                self.assertIs(generations.selected, original)
                self.assertEqual(len(terminal.confirmations), 2)
                transcript = "\n".join(terminal.messages)
                self.assertIn("temporarily", transcript)
                self.assertIn("100 percent", transcript)
                self.assertIn("restore", transcript.lower())
                if not predecessor_valid:
                    self.assertIn("Restoration will continue", transcript)
                    self.assertIn(
                        "LIVE_PREDECESSOR_PUBLIC_NONE_IDENTITY_MISMATCH",
                        transcript,
                    )
                    self.assertEqual(
                        verified.blockers,
                        ("LIVE_PREDECESSOR_PUBLIC_NONE_IDENTITY_MISMATCH",),
                    )


if __name__ == "__main__":
    unittest.main()
