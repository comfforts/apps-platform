"""Private local generation records around an injected provider revision control."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol

from infrastructure.operator.integration import (
    GenerationActivationReadback,
    GenerationPublicationReadback,
    RegistrationGenerationProposal,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.rollback import ReviewedGeneration


@dataclass(frozen=True, slots=True)
class ProviderGenerationPublication:
    created: bool
    object_generation: int
    revision_name: str
    readback_matches: bool


@dataclass(frozen=True, slots=True)
class ProviderGenerationActivation:
    activated: bool
    active_revision_name: str
    active_generation_digest: str


@dataclass(frozen=True, slots=True)
class ProviderGenerationBinding:
    """Exact active provider revision and immutable configuration binding."""

    environment: str
    revision_name: str
    platform_source_revision: str
    image_reference: str
    generation: int
    generation_digest: str
    content_digest: str
    object_name: str
    object_generation: int


class GenerationProvider(Protocol):
    """Create immutable config/revision candidates, then move only traffic."""

    def stage(
        self,
        proposal: RegistrationGenerationProposal,
        compiled_configuration: bytes,
    ) -> ProviderGenerationPublication: ...

    def activate(
        self,
        environment: str,
        revision_name: str,
        generation_digest: str,
        authority: str,
    ) -> ProviderGenerationActivation: ...

    def read_active_binding(
        self,
        environment: str,
    ) -> ProviderGenerationBinding: ...


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


class LocalRegistrationGenerationControl:
    """Keep immutable proposals and the current provider revision binding."""

    def __init__(
        self,
        filesystem: LocalFilesystem,
        provider: GenerationProvider | None,
    ) -> None:
        self._filesystem = filesystem
        self._provider = provider

    @staticmethod
    def _directory(environment: str) -> str:
        return f"environments/{environment}/generations"

    @classmethod
    def _proposal_path(cls, environment: str, digest: str) -> str:
        return f"{cls._directory(environment)}/{digest[7:]}.proposal.v1.json"

    @classmethod
    def _provider_path(cls, environment: str, digest: str) -> str:
        return f"{cls._directory(environment)}/{digest[7:]}.provider.v1.json"

    @classmethod
    def _pointer_path(cls, environment: str) -> str:
        return f"{cls._directory(environment)}/current.v1.json"

    @staticmethod
    def _value(proposal: RegistrationGenerationProposal) -> dict[str, Any]:
        return {
            "compiled_configuration": proposal.compiled_configuration,
            "content_digest": proposal.content_digest,
            "environment": proposal.environment,
            "generation_digest": proposal.generation_digest,
            "ownership_manifest": proposal.ownership_manifest,
            "registration_set": proposal.registration_set,
        }

    @staticmethod
    def _proposal(value: dict[str, Any]) -> RegistrationGenerationProposal:
        expected = {
            "compiled_configuration",
            "content_digest",
            "environment",
            "generation_digest",
            "ownership_manifest",
            "registration_set",
        }
        if set(value) != expected:
            raise ValueError("stored generation proposal has an invalid shape")
        object_fields = (
            "compiled_configuration",
            "ownership_manifest",
            "registration_set",
        )
        string_fields = ("content_digest", "environment", "generation_digest")
        if any(not isinstance(value[field], dict) for field in object_fields) or any(
            not isinstance(value[field], str) for field in string_fields
        ):
            raise ValueError("stored generation proposal has invalid values")
        return RegistrationGenerationProposal(
            environment=value["environment"],
            registration_set=value["registration_set"],
            compiled_configuration=value["compiled_configuration"],
            ownership_manifest=value["ownership_manifest"],
            generation_digest=value["generation_digest"],
            content_digest=value["content_digest"],
        )

    def _read_json(self, path: str) -> dict[str, Any] | None:
        payload = self._filesystem.read_state(path)
        if payload is None:
            return None
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("stored generation state is invalid") from error
        if not isinstance(value, dict):
            raise ValueError("stored generation state is invalid")
        return value

    def read_proposal(
        self,
        environment: str,
        generation_digest: str,
    ) -> RegistrationGenerationProposal | None:
        value = self._read_json(self._proposal_path(environment, generation_digest))
        if value is None:
            return None
        proposal = self._proposal(value)
        if (
            proposal.environment != environment
            or proposal.generation_digest != generation_digest
        ):
            raise ValueError("stored generation proposal binding mismatch")
        return proposal

    def _provider_record(
        self,
        environment: str,
        generation_digest: str,
    ) -> dict[str, Any] | None:
        value = self._read_json(self._provider_path(environment, generation_digest))
        if value is None:
            return None
        if (
            set(value)
            != {"generation_digest", "object_generation", "revision_name"}
            or value.get("generation_digest") != generation_digest
            or not isinstance(value.get("object_generation"), int)
            or not isinstance(value.get("revision_name"), str)
        ):
            raise ValueError("stored provider generation binding mismatch")
        return value

    def current(
        self,
        environment: str,
    ) -> RegistrationGenerationProposal | None:
        pointer = self._read_json(self._pointer_path(environment))
        if pointer is None:
            return None
        if set(pointer) != {"generation_digest", "revision_name"}:
            raise ValueError("stored current generation pointer is invalid")
        digest = pointer.get("generation_digest")
        revision = pointer.get("revision_name")
        if not isinstance(digest, str) or not isinstance(revision, str):
            raise ValueError("stored current generation pointer is invalid")
        provider = self._provider_record(environment, digest)
        if provider is None or provider["revision_name"] != revision:
            raise ValueError("stored current generation pointer is unbound")
        proposal = self.read_proposal(environment, digest)
        if proposal is None:
            raise ValueError("stored current generation proposal is missing")
        return proposal

    def bind_deployed_initial(
        self,
        proposal: RegistrationGenerationProposal,
        *,
        object_name: str,
        object_generation: int,
    ) -> RegistrationGenerationProposal:
        """Adopt the exact active bootstrap generation without provider mutation."""

        try:
            generation = proposal.registration_set["generation"]
            previous = proposal.registration_set["previous_generation_digest"]
            registrations = proposal.registration_set["registrations"]
            source_revision = proposal.registration_set["proposal"]["source_revision"]
            compiled_generation = proposal.compiled_configuration["generation"]
            compiled_digest = proposal.compiled_configuration["generation_digest"]
        except (KeyError, TypeError) as error:
            raise ValueError("deployed initial generation proposal is invalid") from error
        if (
            proposal.environment != "staging"
            or generation != 1
            or compiled_generation != 1
            or previous is not None
            or registrations != []
            or not isinstance(source_revision, str)
            or compiled_digest != proposal.generation_digest
            or object_name != "generations/1/compiled.json"
            or object_generation < 1
        ):
            raise ValueError("deployed initial generation proposal is invalid")
        if self._provider is None:
            raise RuntimeError("generation provider is unavailable")
        active = self._provider.read_active_binding(proposal.environment)
        if (
            active.environment != proposal.environment
            or active.generation != generation
            or active.generation_digest != proposal.generation_digest
            or active.content_digest != proposal.content_digest
            or active.object_name != object_name
            or active.object_generation != object_generation
            or not active.revision_name
        ):
            raise ValueError("deployed initial generation binding mismatch")

        proposal_path = self._proposal_path(
            proposal.environment,
            proposal.generation_digest,
        )
        self._filesystem.write_state(
            proposal_path,
            _canonical(self._value(proposal)) + b"\n",
            replace=False,
        )
        self._filesystem.write_state(
            self._provider_path(
                proposal.environment,
                proposal.generation_digest,
            ),
            _canonical(
                {
                    "generation_digest": proposal.generation_digest,
                    "object_generation": object_generation,
                    "revision_name": active.revision_name,
                }
            )
            + b"\n",
            replace=False,
        )
        self._filesystem.write_state(
            self._pointer_path(proposal.environment),
            _canonical(
                {
                    "generation_digest": proposal.generation_digest,
                    "revision_name": active.revision_name,
                }
            )
            + b"\n",
            replace=False,
        )
        current = self.current(proposal.environment)
        if current != proposal:
            raise ValueError("deployed initial generation binding mismatch")
        return current

    def active_platform_source_revision(self, environment: str) -> str:
        """Read the platform source revision serving all active edge traffic."""

        if self._provider is None:
            raise RuntimeError("generation provider is unavailable")
        active = self._provider.read_active_binding(environment)
        if (
            active.environment != environment
            or len(active.platform_source_revision) != 40
            or any(
                character not in "0123456789abcdef"
                for character in active.platform_source_revision
            )
        ):
            raise ValueError("active platform source binding mismatch")
        return active.platform_source_revision

    def record_active_runtime(self, binding: ProviderGenerationBinding) -> None:
        """Rebind one unchanged generation to its verified current edge revision."""

        pointer = self._read_json(self._pointer_path(binding.environment))
        if pointer is None:
            return
        if set(pointer) != {"generation_digest", "revision_name"}:
            raise ValueError("stored current generation pointer is invalid")
        digest = pointer.get("generation_digest")
        if digest != binding.generation_digest:
            raise ValueError("active runtime generation binding mismatch")
        proposal = self.read_proposal(binding.environment, binding.generation_digest)
        if proposal is None:
            raise ValueError("active runtime generation proposal is missing")
        generation = proposal.registration_set.get("generation")
        contract_version = proposal.compiled_configuration.get("contract_version")
        if contract_version not in {1, 2}:
            raise ValueError("active runtime generation binding mismatch")
        expected_objects = {
            (
                f"environments/{binding.environment}/generations/"
                f"{binding.generation}/"
                f"compiled-shared-edge.v{contract_version}.json"
            ),
            (
                f"generations/{binding.generation_digest[7:]}/"
                f"compiled-shared-edge.v{contract_version}.json"
            ),
        }
        if (
            generation == 1
            and proposal.registration_set.get("previous_generation_digest") is None
        ):
            expected_objects.add("generations/1/compiled.json")
        if (
            generation != binding.generation
            or proposal.content_digest != binding.content_digest
            or binding.object_name not in expected_objects
            or binding.object_generation < 1
            or not binding.revision_name
            or not binding.image_reference
        ):
            raise ValueError("active runtime generation binding mismatch")
        self._filesystem.write_state(
            self._provider_path(binding.environment, binding.generation_digest),
            _canonical(
                {
                    "generation_digest": binding.generation_digest,
                    "object_generation": binding.object_generation,
                    "revision_name": binding.revision_name,
                }
            )
            + b"\n",
            replace=True,
        )
        self._filesystem.write_state(
            self._pointer_path(binding.environment),
            _canonical(
                {
                    "generation_digest": binding.generation_digest,
                    "revision_name": binding.revision_name,
                }
            )
            + b"\n",
            replace=True,
        )

    def publish(
        self,
        proposal: RegistrationGenerationProposal,
    ) -> GenerationPublicationReadback:
        proposal_path = self._proposal_path(
            proposal.environment,
            proposal.generation_digest,
        )
        proposal_contents = _canonical(self._value(proposal)) + b"\n"
        self._filesystem.write_state(
            proposal_path,
            proposal_contents,
            replace=False,
        )
        existing = self._provider_record(
            proposal.environment,
            proposal.generation_digest,
        )
        if existing is not None:
            return GenerationPublicationReadback(
                created=False,
                publication_reference=(
                    "urn:comfforts:app-platform:generation:"
                    f"{proposal.generation_digest[7:]}:"
                    f"revision:{existing['revision_name']}"
                ),
                generation_digest=proposal.generation_digest,
                content_digest=proposal.content_digest,
                readback_matches=True,
            )
        if self._provider is None:
            raise RuntimeError("generation provider is unavailable")
        publication = self._provider.stage(
            proposal,
            _canonical(proposal.compiled_configuration),
        )
        if (
            not publication.readback_matches
            or publication.object_generation < 1
            or not publication.revision_name
        ):
            return GenerationPublicationReadback(
                created=publication.created,
                publication_reference="",
                generation_digest=proposal.generation_digest,
                content_digest=proposal.content_digest,
                readback_matches=False,
            )
        provider_record = {
            "generation_digest": proposal.generation_digest,
            "object_generation": publication.object_generation,
            "revision_name": publication.revision_name,
        }
        self._filesystem.write_state(
            self._provider_path(
                proposal.environment,
                proposal.generation_digest,
            ),
            _canonical(provider_record) + b"\n",
            replace=False,
        )
        return GenerationPublicationReadback(
            created=publication.created,
            publication_reference=(
                "urn:comfforts:app-platform:generation:"
                f"{proposal.generation_digest[7:]}:"
                f"revision:{publication.revision_name}"
            ),
            generation_digest=proposal.generation_digest,
            content_digest=proposal.content_digest,
            readback_matches=True,
        )

    @staticmethod
    def _reference_revision(publication_reference: str) -> str | None:
        marker = ":revision:"
        if marker not in publication_reference:
            return None
        revision = publication_reference.rsplit(marker, maxsplit=1)[1]
        return revision or None

    def _activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
        *,
        authority: str,
    ) -> GenerationActivationReadback:
        provider = self._provider_record(environment, generation_digest)
        revision = self._reference_revision(publication_reference)
        if (
            provider is None
            or revision is None
            or provider["revision_name"] != revision
        ):
            return GenerationActivationReadback(False, generation_digest)
        if self._provider is None:
            raise RuntimeError("generation provider is unavailable")
        readback = self._provider.activate(
            environment,
            revision,
            generation_digest,
            authority,
        )
        if (
            not readback.activated
            or readback.active_revision_name != revision
            or readback.active_generation_digest != generation_digest
        ):
            return GenerationActivationReadback(
                False,
                readback.active_generation_digest,
            )
        self._filesystem.write_state(
            self._pointer_path(environment),
            _canonical(
                {
                    "generation_digest": generation_digest,
                    "revision_name": revision,
                }
            )
            + b"\n",
            replace=True,
        )
        return GenerationActivationReadback(True, generation_digest)

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback:
        return self._activate(
            environment,
            publication_reference,
            generation_digest,
            authority="apply",
        )

    def activate_reviewed(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback:
        return self._activate(
            environment,
            publication_reference,
            generation_digest,
            authority="rollback",
        )

    def reviewed(
        self,
        environment: str,
        generation_digest: str,
    ) -> ReviewedGeneration | None:
        proposal = self.read_proposal(environment, generation_digest)
        provider = self._provider_record(environment, generation_digest)
        if proposal is None or provider is None:
            return None
        return ReviewedGeneration(
            publication_reference=(
                "urn:comfforts:app-platform:generation:"
                f"{generation_digest[7:]}:"
                f"revision:{provider['revision_name']}"
            ),
            proposal=proposal,
        )


class LocalReviewedGenerationControl:
    """Rollback view over the same immutable local/provider generation history."""

    def __init__(self, generations: LocalRegistrationGenerationControl) -> None:
        self._generations = generations

    def current(self, environment: str) -> ReviewedGeneration | None:
        proposal = self._generations.current(environment)
        if proposal is None:
            return None
        return self._generations.reviewed(
            environment,
            proposal.generation_digest,
        )

    def read_reviewed(
        self,
        environment: str,
        generation_digest: str,
    ) -> ReviewedGeneration | None:
        return self._generations.reviewed(environment, generation_digest)

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback:
        return self._generations.activate_reviewed(
            environment,
            publication_reference,
            generation_digest,
        )


__all__ = (
    "GenerationProvider",
    "LocalRegistrationGenerationControl",
    "LocalReviewedGenerationControl",
    "ProviderGenerationActivation",
    "ProviderGenerationBinding",
    "ProviderGenerationPublication",
)
