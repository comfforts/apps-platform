"""Private create-only persistence for one exact destruction operation."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from contracts.lifecycle import (
    canonical_lifecycle_bytes,
    lifecycle_digest,
    validate_lifecycle_document,
)
from infrastructure.operator.destruction import DestructionStageClosure
from infrastructure.operator.local import LocalFilesystem


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_STAGE = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


class LocalDestructionControl:
    """Retain exact local destructive authority and append-only progress."""

    def __init__(self, filesystem: LocalFilesystem) -> None:
        self._filesystem = filesystem

    @staticmethod
    def _root(environment: str, digest: str) -> str:
        if environment != "staging" or _DIGEST.fullmatch(digest) is None:
            raise ValueError("invalid destruction authority binding")
        return f"environments/{environment}/destruction/{digest[7:]}"

    @classmethod
    def _specification_path(cls, environment: str, digest: str) -> str:
        return f"{cls._root(environment, digest)}/specification.v1.json"

    @classmethod
    def _approval_path(cls, environment: str, digest: str) -> str:
        return f"{cls._root(environment, digest)}/approval.v1.json"

    @classmethod
    def _progress_directory(cls, environment: str, digest: str) -> str:
        return f"{cls._root(environment, digest)}/progress"

    @classmethod
    def _completion_path(cls, environment: str, digest: str) -> str:
        return f"{cls._root(environment, digest)}/complete.v1.json"

    def _read_json(self, relative_path: str) -> dict[str, Any] | None:
        payload = self._filesystem.read_state(relative_path)
        if payload is None:
            return None
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("stored destruction state is invalid") from error
        if not isinstance(value, dict):
            raise ValueError("stored destruction state is invalid")
        return value

    def _stored_specification(
        self,
        environment: str,
        digest: str,
    ) -> dict[str, Any] | None:
        path = self._specification_path(environment, digest)
        payload = self._filesystem.read_state(path)
        if payload is None:
            return None
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if (
            not isinstance(value, dict)
            or validate_lifecycle_document(value, "deployment-specification")
            or lifecycle_digest(value, "deployment-specification") != digest
            or value.get("environment") != environment
            or value.get("operation") != "destroy"
        ):
            return None
        return value

    def _specification_matches(self, environment: str, digest: str) -> bool:
        return self._stored_specification(environment, digest) is not None

    def publish_specification(
        self,
        environment: str,
        digest: str,
        specification: dict[str, object],
    ) -> bool:
        if (
            validate_lifecycle_document(specification, "deployment-specification")
            or lifecycle_digest(specification, "deployment-specification") != digest
            or specification.get("environment") != environment
            or specification.get("operation") != "destroy"
        ):
            return False
        self._filesystem.write_state(
            self._specification_path(environment, digest),
            canonical_lifecycle_bytes(specification, "deployment-specification")
            + b"\n",
            replace=False,
        )
        return self._specification_matches(environment, digest)

    def approve_specification(self, environment: str, digest: str) -> bool:
        if not self._specification_matches(environment, digest):
            return False
        value = {
            "approved": True,
            "environment": environment,
            "specification_digest": digest,
        }
        self._filesystem.write_state(
            self._approval_path(environment, digest),
            _canonical(value) + b"\n",
            replace=False,
        )
        return self._read_json(self._approval_path(environment, digest)) == value

    def closed_stages(
        self,
        environment: str,
        digest: str,
    ) -> tuple[DestructionStageClosure, ...]:
        if not self._specification_matches(environment, digest):
            return ()
        directory = self._filesystem.state_path(
            self._progress_directory(environment, digest)
        )
        if not directory.exists():
            return ()
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("stored destruction progress is invalid")
        values: list[DestructionStageClosure] = []
        for expected_sequence, path in enumerate(sorted(directory.iterdir()), start=1):
            if path.is_symlink() or not path.is_file():
                raise ValueError("stored destruction progress is invalid")
            try:
                value = json.loads(path.read_bytes())
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("stored destruction progress is invalid") from error
            if (
                not isinstance(value, dict)
                or set(value) != {"outputs", "sequence", "stage_id"}
                or value.get("sequence") != expected_sequence
                or not isinstance(value.get("stage_id"), str)
                or _STAGE.fullmatch(value["stage_id"]) is None
                or not isinstance(value.get("outputs"), list)
            ):
                raise ValueError("stored destruction progress is invalid")
            expected_name = f"{expected_sequence:08d}-{value['stage_id']}.v1.json"
            if path.name != expected_name:
                raise ValueError("stored destruction progress is invalid")
            outputs: list[tuple[str, str]] = []
            for item in value["outputs"]:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"name", "value"}
                    or not isinstance(item["name"], str)
                    or not isinstance(item["value"], str)
                ):
                    raise ValueError("stored destruction progress is invalid")
                outputs.append((item["name"], item["value"]))
            values.append(
                DestructionStageClosure(
                    stage_id=value["stage_id"],
                    outputs=tuple(outputs),
                )
            )
        return tuple(values)

    def close_stage(
        self,
        environment: str,
        digest: str,
        closure: DestructionStageClosure,
    ) -> bool:
        if (
            (specification := self._stored_specification(environment, digest)) is None
            or self._read_json(self._approval_path(environment, digest))
            != {
                "approved": True,
                "environment": environment,
                "specification_digest": digest,
            }
            or _STAGE.fullmatch(closure.stage_id) is None
        ):
            return False
        existing = self.closed_stages(environment, digest)
        sequence = len(existing) + 1
        stages = specification.get("stages")
        if not isinstance(stages, list) or sequence > len(stages):
            return False
        stage = stages[sequence - 1]
        if not isinstance(stage, dict) or stage.get("stage_id") != closure.stage_id:
            return False
        produces = stage.get("produces")
        if (
            not isinstance(produces, list)
            or tuple(name for name, _ in closure.outputs) != tuple(produces)
        ):
            return False
        value = {
            "outputs": [
                {"name": name, "value": output}
                for name, output in closure.outputs
            ],
            "sequence": sequence,
            "stage_id": closure.stage_id,
        }
        self._filesystem.write_state(
            (
                f"{self._progress_directory(environment, digest)}/"
                f"{sequence:08d}-{closure.stage_id}.v1.json"
            ),
            _canonical(value) + b"\n",
            replace=False,
        )
        return self.closed_stages(environment, digest) == (*existing, closure)

    def mark_complete(self, environment: str, digest: str) -> bool:
        specification = self._stored_specification(environment, digest)
        if specification is None:
            return False
        stages = specification.get("stages")
        closed = self.closed_stages(environment, digest)
        if (
            not isinstance(stages, list)
            or tuple(item.stage_id for item in closed)
            != tuple(
                stage.get("stage_id")
                for stage in stages
                if isinstance(stage, dict)
            )
        ):
            return False
        value = {
            "complete": True,
            "environment": environment,
            "specification_digest": digest,
        }
        self._filesystem.write_state(
            self._completion_path(environment, digest),
            _canonical(value) + b"\n",
            replace=False,
        )
        return self._read_json(self._completion_path(environment, digest)) == value


__all__ = ("LocalDestructionControl",)
