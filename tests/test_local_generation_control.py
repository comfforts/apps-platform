"""AP-M9-W8 private generation history and provider activation tests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator.integration import RegistrationGenerationProposal
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_generation import (
    LocalRegistrationGenerationControl,
    LocalReviewedGenerationControl,
    ProviderGenerationActivation,
    ProviderGenerationBinding,
    ProviderGenerationPublication,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _digest(character: str) -> str:
    return "sha256:" + (character * 64)


def proposal(
    generation: int = 1,
    *,
    previous: str | None = None,
    contract_version: int = 1,
) -> RegistrationGenerationProposal:
    digest = _digest(str(generation))
    return RegistrationGenerationProposal(
        environment="staging",
        registration_set={
            "contract_version": contract_version,
            "generation": generation,
            "previous_generation_digest": previous,
            "proposal": {
                "source_revision": "a" * 40,
                "change_summary": f"Generation {generation}",
            },
            "registrations": [],
        },
        compiled_configuration={
            "contract_version": contract_version,
            "generation": generation,
            "generation_digest": digest,
            "routes": [],
        },
        ownership_manifest={
            "contract_version": 1,
            "generation": generation,
            "resources": [],
        },
        generation_digest=digest,
        content_digest=_digest("f"),
    )


@dataclass
class FakeProvider:
    published: list[tuple[RegistrationGenerationProposal, bytes]] = field(
        default_factory=list
    )
    activations: list[tuple[str, str, str, str]] = field(default_factory=list)
    stage_matches: bool = True
    activation_matches: bool = True
    active_binding: ProviderGenerationBinding | None = None
    bindings: dict[str, ProviderGenerationBinding] = field(default_factory=dict)

    def stage(
        self,
        value: RegistrationGenerationProposal,
        compiled_configuration: bytes,
    ) -> ProviderGenerationPublication:
        self.published.append((value, compiled_configuration))
        generation = value.registration_set["generation"]
        contract_version = value.compiled_configuration["contract_version"]
        revision_name = f"app-platform-edge-g{generation}"
        self.bindings[revision_name] = ProviderGenerationBinding(
            environment=value.environment,
            revision_name=revision_name,
            platform_source_revision=value.registration_set["proposal"][
                "source_revision"
            ],
            image_reference=(
                "us-west1-docker.pkg.dev/example/edge@sha256:" + "8" * 64
            ),
            generation=generation,
            generation_digest=value.generation_digest,
            content_digest=value.content_digest,
            object_name=(
                f"environments/{value.environment}/generations/{generation}/"
                f"compiled-shared-edge.v{contract_version}.json"
            ),
            object_generation=len(self.published),
        )
        return ProviderGenerationPublication(
            created=True,
            object_generation=len(self.published),
            revision_name=revision_name,
            readback_matches=self.stage_matches,
        )

    def activate(
        self,
        environment: str,
        revision_name: str,
        generation_digest: str,
        authority: str,
    ) -> ProviderGenerationActivation:
        self.activations.append(
            (environment, revision_name, generation_digest, authority)
        )
        return ProviderGenerationActivation(
            activated=self.activation_matches,
            active_revision_name=(
                revision_name if self.activation_matches else "wrong-revision"
            ),
            active_generation_digest=generation_digest,
        )

    def read_active_binding(self, environment: str) -> ProviderGenerationBinding:
        if self.active_binding is None or self.active_binding.environment != environment:
            raise RuntimeError("active generation binding is unavailable")
        return self.active_binding

    def read_revision_binding(
        self,
        environment: str,
        revision_name: str,
    ) -> ProviderGenerationBinding:
        """Return one exact synthetic revision or the configured active rebind."""

        if (
            self.active_binding is not None
            and self.active_binding.environment == environment
            and self.active_binding.revision_name == revision_name
        ):
            return self.active_binding
        binding = self.bindings.get(revision_name)
        if binding is None or binding.environment != environment:
            raise RuntimeError("generation binding is unavailable")
        return binding


class LocalGenerationControlTest(unittest.TestCase):
    def _control(
        self,
        directory: str,
        provider: FakeProvider | None = None,
    ) -> tuple[LocalRegistrationGenerationControl, FakeProvider]:
        selected = provider or FakeProvider()
        return (
            LocalRegistrationGenerationControl(
                LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator"),
                selected,
            ),
            selected,
        )

    def test_publication_is_create_only_and_idempotent_for_exact_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control, provider = self._control(directory)

            first = control.publish(proposal())
            second = control.publish(proposal())

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertTrue(first.readback_matches)
        self.assertEqual(first.publication_reference, second.publication_reference)
        self.assertEqual(len(provider.published), 1)
        self.assertEqual(
            provider.published[0][1],
            (
                b'{"contract_version":1,"generation":1,'
                b'"generation_digest":"sha256:' + (b"1" * 64) + b'","routes":[]}'
            ),
        )

    def test_activation_moves_only_to_the_bound_staged_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control, provider = self._control(directory)
            publication = control.publish(proposal())

            activated = control.activate(
                "staging",
                publication.publication_reference,
                proposal().generation_digest,
            )
            current = control.current("staging")

        self.assertTrue(activated.activated)
        self.assertEqual(current, proposal())
        self.assertEqual(
            provider.activations,
            [
                (
                    "staging",
                    "app-platform-edge-g1",
                    proposal().generation_digest,
                    "apply",
                )
            ],
        )

    def test_adopts_exact_deployed_initial_generation_without_provider_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binding = ProviderGenerationBinding(
                environment="staging",
                revision_name="app-platform-edge-initial",
                platform_source_revision="b" * 40,
                image_reference=(
                    "us-west1-docker.pkg.dev/example/edge@sha256:" + "9" * 64
                ),
                generation=1,
                generation_digest=proposal().generation_digest,
                content_digest=proposal().content_digest,
                object_name="generations/1/compiled.json",
                object_generation=41,
            )
            control, provider = self._control(
                directory,
                FakeProvider(active_binding=binding),
            )

            first = control.bind_deployed_initial(
                proposal(),
                object_name="generations/1/compiled.json",
                object_generation=41,
            )
            second = control.bind_deployed_initial(
                proposal(),
                object_name="generations/1/compiled.json",
                object_generation=41,
            )
            active_source = control.active_platform_source_revision("staging")
            current = control.current("staging")

        self.assertEqual(first, proposal())
        self.assertEqual(second, proposal())
        self.assertEqual(current, proposal())
        self.assertEqual(active_source, "b" * 40)
        self.assertEqual(provider.published, [])
        self.assertEqual(provider.activations, [])

    def test_rebinds_current_generation_to_verified_runtime_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control, provider = self._control(directory)
            publication = control.publish(proposal())
            control.activate(
                "staging",
                publication.publication_reference,
                proposal().generation_digest,
            )
            binding = ProviderGenerationBinding(
                environment="staging",
                revision_name="app-platform-edge-g1-current-source",
                platform_source_revision="b" * 40,
                image_reference=(
                    "us-west1-docker.pkg.dev/example/edge@sha256:" + "9" * 64
                ),
                generation=1,
                generation_digest=proposal().generation_digest,
                content_digest=proposal().content_digest,
                object_name="generations/1/compiled.json",
                object_generation=41,
            )
            provider.active_binding = binding

            control.record_active_runtime(binding)
            current = LocalReviewedGenerationControl(control).current("staging")

        assert current is not None
        self.assertEqual(current.proposal, proposal())
        self.assertEqual(current.platform_source_revision, "b" * 40)
        self.assertTrue(
            current.publication_reference.endswith(
                ":revision:app-platform-edge-g1-current-source"
            )
        )
        self.assertEqual(
            control.active_platform_source_revision("staging"),
            "b" * 40,
        )

    def test_rebinds_numbered_generation_to_verified_runtime_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current_proposal = proposal(3, previous=_digest("2"))
            control, provider = self._control(directory)
            publication = control.publish(current_proposal)
            control.activate(
                "staging",
                publication.publication_reference,
                current_proposal.generation_digest,
            )
            binding = ProviderGenerationBinding(
                environment="staging",
                revision_name="app-platform-edge-g3-current-source",
                platform_source_revision="b" * 40,
                image_reference=(
                    "us-west1-docker.pkg.dev/example/edge@sha256:" + "9" * 64
                ),
                generation=3,
                generation_digest=current_proposal.generation_digest,
                content_digest=current_proposal.content_digest,
                object_name=(
                    "environments/staging/generations/3/"
                    "compiled-shared-edge.v1.json"
                ),
                object_generation=43,
            )
            provider.active_binding = binding

            control.record_active_runtime(binding)
            current = LocalReviewedGenerationControl(control).current("staging")

        assert current is not None
        self.assertEqual(current.proposal, current_proposal)
        self.assertEqual(current.platform_source_revision, "b" * 40)
        self.assertTrue(
            current.publication_reference.endswith(
                ":revision:app-platform-edge-g3-current-source"
            )
        )

    def test_version_two_generation_rebinds_and_can_roll_back_to_v1(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control, provider = self._control(directory)
            predecessor = proposal()
            predecessor_publication = control.publish(predecessor)
            control.activate(
                "staging",
                predecessor_publication.publication_reference,
                predecessor.generation_digest,
            )
            successor = proposal(
                2,
                previous=predecessor.generation_digest,
                contract_version=2,
            )
            successor_publication = control.publish(successor)
            control.activate(
                "staging",
                successor_publication.publication_reference,
                successor.generation_digest,
            )
            provider.active_binding = ProviderGenerationBinding(
                environment="staging",
                revision_name="app-platform-edge-g2-v2",
                platform_source_revision="b" * 40,
                image_reference=(
                    "us-west1-docker.pkg.dev/example/edge@sha256:" + "9" * 64
                ),
                generation=2,
                generation_digest=successor.generation_digest,
                content_digest=successor.content_digest,
                object_name=(
                    "environments/staging/generations/2/"
                    "compiled-shared-edge.v2.json"
                ),
                object_generation=44,
            )

            control.record_active_runtime(provider.active_binding)
            reviewed = LocalReviewedGenerationControl(control)
            predecessor_review = reviewed.read_reviewed(
                "staging",
                predecessor.generation_digest,
            )
            assert predecessor_review is not None
            self.assertEqual(
                predecessor_review.platform_source_revision,
                "a" * 40,
            )
            rolled_back = reviewed.activate(
                "staging",
                predecessor_review.publication_reference,
                predecessor.generation_digest,
            )
            current = control.current("staging")

        self.assertTrue(rolled_back.activated)
        assert current is not None
        self.assertEqual(current.registration_set["contract_version"], 1)

    def test_rejects_deployed_initial_generation_binding_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binding = ProviderGenerationBinding(
                environment="staging",
                revision_name="app-platform-edge-initial",
                platform_source_revision="a" * 40,
                image_reference=(
                    "us-west1-docker.pkg.dev/example/edge@sha256:" + "9" * 64
                ),
                generation=1,
                generation_digest=_digest("e"),
                content_digest=proposal().content_digest,
                object_name="generations/1/compiled.json",
                object_generation=41,
            )
            control, _ = self._control(
                directory,
                FakeProvider(active_binding=binding),
            )

            with self.assertRaisesRegex(
                ValueError,
                "deployed initial generation binding mismatch",
            ):
                control.bind_deployed_initial(
                    proposal(),
                    object_name="generations/1/compiled.json",
                    object_generation=41,
                )

        self.assertIsNone(control.current("staging"))

    def test_conflict_or_provider_mismatch_never_advances_current_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control, provider = self._control(directory)
            first = control.publish(proposal())
            conflicting = replace(
                proposal(),
                content_digest=_digest("e"),
            )
            with self.assertRaises(FileExistsError):
                control.publish(conflicting)

            provider.activation_matches = False
            activation = control.activate(
                "staging",
                first.publication_reference,
                proposal().generation_digest,
            )
            current = control.current("staging")

        self.assertFalse(activation.activated)
        self.assertIsNone(current)

    def test_rollback_view_returns_only_retained_reviewed_generations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control, provider = self._control(directory)
            first = control.publish(proposal())
            control.activate(
                "staging",
                first.publication_reference,
                proposal().generation_digest,
            )
            second_proposal = proposal(2, previous=proposal().generation_digest)
            second = control.publish(second_proposal)
            control.activate(
                "staging",
                second.publication_reference,
                second_proposal.generation_digest,
            )
            reviewed = LocalReviewedGenerationControl(control)

            current = reviewed.current("staging")
            predecessor = reviewed.read_reviewed(
                "staging",
                proposal().generation_digest,
            )
            assert predecessor is not None
            rollback = reviewed.activate(
                "staging",
                predecessor.publication_reference,
                predecessor.proposal.generation_digest,
            )

        assert current is not None
        self.assertEqual(current.proposal, second_proposal)
        self.assertEqual(predecessor.proposal, proposal())
        self.assertTrue(rollback.activated)
        self.assertEqual(provider.activations[-1][-1], "rollback")

    def test_terraform_manages_candidate_binding_and_delegates_only_traffic(self) -> None:
        source = (
            PROJECT_ROOT
            / "infrastructure/terraform/modules/shared-edge/main.tf"
        ).read_text(encoding="utf-8")
        lifecycle = source.split("lifecycle {", maxsplit=1)[1].split("}", maxsplit=1)[0]

        self.assertIn("traffic", lifecycle)
        self.assertNotIn("template[0].revision", lifecycle)
        self.assertNotIn("template[0].containers[0].env", lifecycle)
        self.assertNotIn("image", lifecycle)
        self.assertNotIn("service_account", lifecycle)


if __name__ == "__main__":
    unittest.main()
