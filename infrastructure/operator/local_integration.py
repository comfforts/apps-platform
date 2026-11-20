"""Private local readback for least-data application integration bundles."""

from __future__ import annotations

import json
from typing import Any

from contracts.lifecycle import load_lifecycle_document
from infrastructure.operator._interfaces import StatusResult
from infrastructure.operator.integration import (
    PlatformIntegrationState,
    RegistrationGenerationProposal,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_qualification import (
    EnvironmentStatusReader,
    RegistrationGenerationReader,
)


_STAGING_HOSTNAME = "apps-staging.comfforts.com"
_EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)


class LocalPlatformIntegrationReader:
    """Read exact deployed platform facts without opening any Application State."""

    def __init__(
        self,
        filesystem: LocalFilesystem,
        status_reader: EnvironmentStatusReader,
        generations: RegistrationGenerationReader,
    ) -> None:
        self._filesystem = filesystem
        self._status_reader = status_reader
        self._generations = generations

    def _current_journal(self, environment: str) -> dict[str, Any]:
        pointer_payload = self._filesystem.read_state(
            f"environments/{environment}/current-journal.v1.json"
        )
        if pointer_payload is None:
            raise ValueError("current deployment journal is unavailable")
        try:
            pointer = json.loads(pointer_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("current deployment journal pointer is invalid") from error
        if not isinstance(pointer, dict):
            raise ValueError("current deployment journal pointer is invalid")
        digest = pointer.get("journal_digest")
        revision = pointer.get("journal_revision")
        specification_digest = pointer.get("specification_digest")
        if (
            not isinstance(digest, str)
            or not isinstance(revision, int)
            or not isinstance(specification_digest, str)
        ):
            raise ValueError("current deployment journal pointer is invalid")
        path = (
            f"environments/{environment}/journals/"
            f"{specification_digest[7:]}/{revision:08d}.v1.json"
        )
        loaded = load_lifecycle_document(
            self._filesystem.state_path(path),
            "execution-journal",
        )
        if loaded.value is None or loaded.violations or loaded.digest != digest:
            raise ValueError("current deployment journal is invalid")
        return loaded.value

    @staticmethod
    def _outputs(journal: dict[str, Any]) -> dict[str, str]:
        entries = journal.get("entries")
        if not isinstance(entries, list):
            raise ValueError("current deployment journal is invalid")
        outputs: dict[str, str] = {}
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("outcome") != "succeeded":
                continue
            values = entry.get("outputs")
            if not isinstance(values, list):
                raise ValueError("current deployment journal is invalid")
            for item in values:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("name"), str)
                    or not isinstance(item.get("value"), str)
                ):
                    raise ValueError("current deployment journal is invalid")
                outputs[item["name"]] = item["value"]
        return outputs

    def _qualification_status(
        self,
        environment: str,
        status: dict[str, Any],
        generation: RegistrationGenerationProposal,
    ) -> str:
        if status.get("source_authority") != "accepted":
            return "unqualified"
        pointer_payload = self._filesystem.read_state(
            f"environments/{environment}/qualification/current-evidence.v1.json"
        )
        if pointer_payload is None:
            return "unqualified"
        try:
            pointer = json.loads(pointer_payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "unqualified"
        if not isinstance(pointer, dict) or pointer.get("outcome") != "qualified":
            return "unqualified"
        digest = pointer.get("evidence_digest")
        if not isinstance(digest, str):
            return "unqualified"
        path = (
            f"environments/{environment}/qualification/evidence/"
            f"{digest[7:]}.v1.json"
        )
        loaded = load_lifecycle_document(
            self._filesystem.state_path(path),
            "qualification-evidence",
        )
        if loaded.value is None or loaded.violations or loaded.digest != digest:
            return "unqualified"
        evidence = loaded.value
        bindings = (
            ("environment", environment),
            ("source_authority", "accepted"),
            ("source_revision", status.get("source_revision")),
            ("profile_digest", status.get("profile_digest")),
            ("specification_digest", status.get("specification_digest")),
            ("deployment_journal_digest", status.get("journal_digest")),
            (
                "registration_generation_digest",
                generation.generation_digest,
            ),
            ("verdict", "qualified"),
        )
        return (
            "qualified"
            if all(evidence.get(name) == expected for name, expected in bindings)
            else "unqualified"
        )

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        if environment != "staging":
            raise ValueError("platform integration environment is unavailable")
        result: StatusResult = self._status_reader.status(environment)
        status = result.environment_status
        if result.conflicts or status.get("lifecycle_state") != "deployed":
            raise ValueError("platform integration state is not deployed")
        generation = self._generations.current(environment)
        if generation is None:
            raise ValueError("active registration generation is unavailable")
        journal = self._current_journal(environment)
        outputs = self._outputs(journal)
        oauth_client_id = outputs.get("oauth-client-id")
        if not oauth_client_id:
            raise ValueError("OAuth client readback is unavailable")
        generation_number = generation.registration_set.get("generation")
        if not isinstance(generation_number, int):
            raise ValueError("active registration generation is invalid")
        required = (
            "profile_digest",
            "source_authority",
            "source_revision",
            "specification_digest",
            "journal_digest",
        )
        if any(not isinstance(status.get(name), str) for name in required):
            raise ValueError("platform integration state is incomplete")
        return PlatformIntegrationState(
            environment=environment,
            lifecycle_state="deployed",
            profile_digest=str(status["profile_digest"]),
            platform_source_revision=str(status["source_revision"]),
            specification_digest=str(status["specification_digest"]),
            journal_digest=str(status["journal_digest"]),
            generation=generation_number,
            hostname=_STAGING_HOSTNAME,
            oauth_client_id=oauth_client_id,
            edge_caller_reference=_EDGE_CALLER,
            qualification_status=self._qualification_status(
                environment,
                status,
                generation,
            ),
            source_authority=str(status["source_authority"]),
        )


__all__ = ("LocalPlatformIntegrationReader",)
