"""Private local readback for least-data application integration bundles."""

from __future__ import annotations

import json
import hashlib
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

    def _current_progress(self, environment: str) -> dict[str, Any]:
        payload = self._filesystem.read_state(
            f"environments/{environment}/current-progress.v1.json"
        )
        if payload is None:
            raise ValueError("current deployment progress is unavailable")
        try:
            progress = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("current deployment progress is invalid") from error
        if (
            not isinstance(progress, dict)
            or progress.get("environment") != environment
            or progress.get("status") != "succeeded"
            or not isinstance(progress.get("completed"), list)
        ):
            raise ValueError("current deployment progress is invalid")
        return progress

    @staticmethod
    def _progress_digest(progress: dict[str, Any]) -> str:
        payload = json.dumps(
            progress,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _outputs(progress: dict[str, Any]) -> dict[str, str]:
        entries = progress.get("completed")
        if not isinstance(entries, list):
            raise ValueError("current deployment progress is invalid")
        outputs: dict[str, str] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("current deployment progress is invalid")
            values = entry.get("outputs")
            if not isinstance(values, list):
                raise ValueError("current deployment progress is invalid")
            for item in values:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("name"), str)
                    or not isinstance(item.get("value"), str)
                ):
                    raise ValueError("current deployment progress is invalid")
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
            ("deployment_progress_digest", status.get("progress_digest")),
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
        progress = self._current_progress(environment)
        if self._progress_digest(progress) != status.get("progress_digest"):
            raise ValueError("deployment progress does not match environment status")
        outputs = self._outputs(progress)
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
            "progress_digest",
        )
        if any(not isinstance(status.get(name), str) for name in required):
            raise ValueError("platform integration state is incomplete")
        return PlatformIntegrationState(
            environment=environment,
            lifecycle_state="deployed",
            profile_digest=str(status["profile_digest"]),
            platform_source_revision=str(status["source_revision"]),
            specification_digest=str(status["specification_digest"]),
            progress_digest=str(status["progress_digest"]),
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
