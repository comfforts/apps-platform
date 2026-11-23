"""Private local readback for least-data application integration bundles."""

from __future__ import annotations

import json
import hashlib
from typing import Any, Protocol

from contracts.lifecycle import load_lifecycle_document
from infrastructure.operator._interfaces import StatusResult
from infrastructure.operator.integration import (
    PlatformIntegrationState,
    RegistrationGenerationProposal,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_deployment import initial_generation
from infrastructure.operator.local_qualification import (
    EnvironmentStatusReader,
    RegistrationGenerationReader,
)


_STAGING_HOSTNAME = "apps-staging.comfforts.com"
_EDGE_CALLER = (
    "serviceAccount:app-platform-edge-caller@"
    "comfforts-platform-non-prod.iam.gserviceaccount.com"
)


class PlatformIntegrationReadbackError(RuntimeError):
    """Stable, non-sensitive platform readback blocker for operator output."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InitialGenerationBinder(Protocol):
    def bind_deployed_initial(
        self,
        proposal: RegistrationGenerationProposal,
        *,
        platform_source_revision: str,
        object_name: str,
        object_generation: int,
    ) -> RegistrationGenerationProposal: ...


class LocalPlatformIntegrationReader:
    """Read exact deployed platform facts without opening any Application State."""

    def __init__(
        self,
        filesystem: LocalFilesystem,
        status_reader: EnvironmentStatusReader,
        generations: RegistrationGenerationReader,
        *,
        initial_generation_binder: InitialGenerationBinder | None = None,
    ) -> None:
        self._filesystem = filesystem
        self._status_reader = status_reader
        self._generations = generations
        self._initial_generation_binder = initial_generation_binder

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

    def _bind_initial_generation(
        self,
        environment: str,
        source_revision: str,
        outputs: dict[str, str],
    ) -> RegistrationGenerationProposal:
        binder = self._initial_generation_binder
        if binder is None:
            raise PlatformIntegrationReadbackError(
                "ACTIVE_REGISTRATION_GENERATION_UNAVAILABLE"
            )
        reference_payload = outputs.get("registration-generation-reference")
        try:
            reference = json.loads(reference_payload or "")
        except json.JSONDecodeError as error:
            raise PlatformIntegrationReadbackError(
                "INITIAL_REGISTRATION_GENERATION_REFERENCE_INVALID"
            ) from error
        if (
            not isinstance(reference, dict)
            or set(reference)
            != {
                "content_digest",
                "generation",
                "generation_digest",
                "object_generation",
                "object_name",
            }
            or reference.get("generation") != 1
            or not isinstance(reference.get("content_digest"), str)
            or not isinstance(reference.get("generation_digest"), str)
            or reference.get("object_name") != "generations/1/compiled.json"
            or not isinstance(reference.get("object_generation"), int)
            or reference["object_generation"] < 1
        ):
            raise PlatformIntegrationReadbackError(
                "INITIAL_REGISTRATION_GENERATION_REFERENCE_MISMATCH"
            )
        source_revisions = {source_revision}
        progress_directory = self._filesystem.state_path(
            f"environments/{environment}/progress"
        )
        for path in sorted(progress_directory.glob("*.final.v1.json")):
            try:
                payload = path.read_bytes()
                if len(payload) > 4 * 1024 * 1024:
                    continue
                progress = json.loads(payload)
                if (
                    not isinstance(progress, dict)
                    or progress.get("environment") != environment
                    or not isinstance(progress.get("source_revision"), str)
                    or self._outputs(progress).get(
                        "registration-generation-reference"
                    )
                    != reference_payload
                ):
                    continue
                source_revisions.add(progress["source_revision"])
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                continue
        matches = []
        for candidate_revision in sorted(source_revisions):
            try:
                candidate = initial_generation(candidate_revision)
            except (RuntimeError, ValueError):
                continue
            if (
                candidate.content_digest == reference["content_digest"]
                and candidate.generation_digest == reference["generation_digest"]
                and candidate.object_name == reference["object_name"]
            ):
                matches.append(candidate)
        if len(matches) != 1:
            raise PlatformIntegrationReadbackError(
                "INITIAL_REGISTRATION_GENERATION_HISTORY_UNAVAILABLE"
            )
        expected = matches[0]
        proposal = RegistrationGenerationProposal(
            environment=environment,
            registration_set=expected.registration_set,
            compiled_configuration=expected.compiled_configuration,
            ownership_manifest=expected.ownership_manifest,
            generation_digest=expected.generation_digest,
            content_digest=expected.content_digest,
        )
        try:
            return binder.bind_deployed_initial(
                proposal,
                platform_source_revision=source_revision,
                object_name=expected.object_name,
                object_generation=reference["object_generation"],
            )
        except Exception as error:
            raise PlatformIntegrationReadbackError(
                "ACTIVE_REGISTRATION_GENERATION_RECOVERY_FAILED"
            ) from error

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        if environment != "staging":
            raise ValueError("platform integration environment is unavailable")
        result: StatusResult = self._status_reader.status(environment)
        status = result.environment_status
        if result.conflicts or status.get("lifecycle_state") != "deployed":
            raise ValueError("platform integration state is not deployed")
        progress = self._current_progress(environment)
        if self._progress_digest(progress) != status.get("progress_digest"):
            raise ValueError("deployment progress does not match environment status")
        outputs = self._outputs(progress)
        source_revision = status.get("source_revision")
        if not isinstance(source_revision, str):
            raise ValueError("platform integration state is incomplete")
        generation = self._generations.current(environment)
        if generation is None:
            generation = self._bind_initial_generation(
                environment,
                source_revision,
                outputs,
            )
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


__all__ = (
    "LocalPlatformIntegrationReader",
    "PlatformIntegrationReadbackError",
)
