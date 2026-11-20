"""Least-data private records for accepted application handoffs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from contracts.lifecycle import lifecycle_digest
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.qualification import FixtureRevision


_APPLICATION_ID = re.compile(r"[a-z][a-z0-9-]{2,62}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ApplicationHandoffRecord:
    environment: str
    application_id: str
    application_source_revision: str
    integration_bundle_digest: str
    attachment_bundle_digest: str
    attachment_revision: int
    registration_generation: int
    registration_generation_digest: str

    @property
    def fixture_revision(self) -> FixtureRevision:
        return FixtureRevision(
            application_id=self.application_id,
            application_source_revision=self.application_source_revision,
            integration_bundle_digest=self.integration_bundle_digest,
            attachment_bundle_digest=self.attachment_bundle_digest,
        )


class LocalApplicationHandoffs:
    """Keep only accepted non-secret bundle bindings, never Application State."""

    def __init__(self, filesystem: LocalFilesystem) -> None:
        self._filesystem = filesystem

    @staticmethod
    def _path(record: ApplicationHandoffRecord) -> str:
        return (
            f"environments/{record.environment}/applications/"
            f"{record.application_id}/handoffs/"
            f"{record.registration_generation_digest[7:]}.v1.json"
        )

    @staticmethod
    def _value(record: ApplicationHandoffRecord) -> dict[str, str]:
        return {
            "application_id": record.application_id,
            "application_source_revision": record.application_source_revision,
            "attachment_bundle_digest": record.attachment_bundle_digest,
            "attachment_revision": record.attachment_revision,
            "environment": record.environment,
            "integration_bundle_digest": record.integration_bundle_digest,
            "registration_generation": record.registration_generation,
            "registration_generation_digest": (
                record.registration_generation_digest
            ),
        }

    @staticmethod
    def _record(value: dict[str, Any]) -> ApplicationHandoffRecord:
        expected = {
            "application_id",
            "application_source_revision",
            "attachment_bundle_digest",
            "attachment_revision",
            "environment",
            "integration_bundle_digest",
            "registration_generation",
            "registration_generation_digest",
        }
        if set(value) != expected:
            raise ValueError("stored application handoff is invalid")
        string_fields = expected - {"attachment_revision", "registration_generation"}
        if any(not isinstance(value[name], str) for name in string_fields) or any(
            not isinstance(value[name], int)
            for name in ("attachment_revision", "registration_generation")
        ):
            raise ValueError("stored application handoff is invalid")
        record = ApplicationHandoffRecord(**value)
        if (
            record.environment != "staging"
            or _APPLICATION_ID.fullmatch(record.application_id) is None
            or _REVISION.fullmatch(record.application_source_revision) is None
            or record.attachment_revision < 1
            or record.registration_generation < 1
            or any(
                _DIGEST.fullmatch(digest) is None
                for digest in (
                    record.attachment_bundle_digest,
                    record.integration_bundle_digest,
                    record.registration_generation_digest,
                )
            )
        ):
            raise ValueError("stored application handoff is invalid")
        return record

    @classmethod
    def from_bundles(
        cls,
        integration_bundle: dict[str, Any],
        attachment_bundle: dict[str, Any],
        generation: int,
        generation_digest: str,
    ) -> ApplicationHandoffRecord:
        try:
            record = ApplicationHandoffRecord(
                environment=str(integration_bundle["environment"]),
                application_id=str(integration_bundle["application_id"]),
                application_source_revision=str(
                    attachment_bundle["application_source_revision"]
                ),
                integration_bundle_digest=lifecycle_digest(
                    integration_bundle,
                    "platform-integration-bundle",
                ),
                attachment_bundle_digest=lifecycle_digest(
                    attachment_bundle,
                    "application-attachment-bundle",
                ),
                attachment_revision=int(attachment_bundle["attachment_revision"]),
                registration_generation=generation,
                registration_generation_digest=generation_digest,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("accepted application handoff is invalid") from error
        if (
            attachment_bundle.get("environment") != record.environment
            or attachment_bundle.get("application_id") != record.application_id
            or attachment_bundle.get("platform_integration_bundle_digest")
            != record.integration_bundle_digest
        ):
            raise ValueError("accepted application handoff binding mismatch")
        return cls._record(cls._value(record))

    def record(self, value: ApplicationHandoffRecord) -> bool:
        record = self._record(self._value(value))
        contents = _canonical(self._value(record)) + b"\n"
        self._filesystem.write_state(
            self._path(record),
            contents,
            replace=False,
        )
        return self._filesystem.read_state(self._path(record)) == contents

    def read(
        self,
        environment: str,
        application_id: str,
        generation_digest: str,
    ) -> ApplicationHandoffRecord | None:
        key = ApplicationHandoffRecord(
            environment=environment,
            application_id=application_id,
            application_source_revision="0" * 40,
            integration_bundle_digest="sha256:" + ("0" * 64),
            attachment_bundle_digest="sha256:" + ("0" * 64),
            attachment_revision=1,
            registration_generation=1,
            registration_generation_digest=generation_digest,
        )
        payload = self._filesystem.read_state(self._path(key))
        if payload is None:
            return None
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("stored application handoff is invalid") from error
        if not isinstance(value, dict):
            raise ValueError("stored application handoff is invalid")
        record = self._record(value)
        if (
            record.environment != environment
            or record.application_id != application_id
            or record.registration_generation_digest != generation_digest
        ):
            raise ValueError("stored application handoff binding mismatch")
        return record

    def latest_for_application(
        self,
        environment: str,
        application_id: str,
        maximum_generation: int,
    ) -> ApplicationHandoffRecord | None:
        if (
            environment != "staging"
            or _APPLICATION_ID.fullmatch(application_id) is None
            or maximum_generation < 1
        ):
            raise ValueError("invalid application handoff lookup")
        directory = self._filesystem.state_path(
            f"environments/{environment}/applications/{application_id}/handoffs"
        )
        if not directory.exists():
            return None
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("stored application handoff directory is invalid")
        records: list[ApplicationHandoffRecord] = []
        for path in sorted(directory.iterdir()):
            if path.is_symlink() or not path.is_file():
                raise ValueError("stored application handoff directory is invalid")
            try:
                value = json.loads(path.read_bytes())
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("stored application handoff is invalid") from error
            if not isinstance(value, dict):
                raise ValueError("stored application handoff is invalid")
            record = self._record(value)
            if (
                record.environment != environment
                or record.application_id != application_id
                or path.name
                != f"{record.registration_generation_digest[7:]}.v1.json"
            ):
                raise ValueError("stored application handoff binding mismatch")
            if record.registration_generation <= maximum_generation:
                records.append(record)
        if not records:
            return None
        records.sort(
            key=lambda item: (
                item.registration_generation,
                item.attachment_revision,
                item.registration_generation_digest,
            )
        )
        latest = records[-1]
        if any(
            item.registration_generation == latest.registration_generation
            and item.attachment_revision == latest.attachment_revision
            and item != latest
            for item in records[:-1]
        ):
            raise ValueError("ambiguous application handoff history")
        return latest


__all__ = (
    "ApplicationHandoffRecord",
    "LocalApplicationHandoffs",
)
