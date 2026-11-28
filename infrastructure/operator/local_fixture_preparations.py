"""Private, inspectable fixture bundle pairs prepared before registration."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import replace
from typing import Any

from contracts.lifecycle import (
    canonical_versioned_lifecycle_bytes,
    validate_versioned_lifecycle_relationships,
    versioned_lifecycle_digest,
)
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationDeployment,
    FixtureDeployRequest,
    FixtureImageReadback,
    FixturePreparation,
)
from infrastructure.operator.integration import RegistrationIntent
from infrastructure.operator.local import LocalFilesystem


_APPLICATION_ID = re.compile(r"[a-z][a-z0-9-]{2,62}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")


def _canonical(value: object) -> bytes:
    """Serialize private preparation metadata to canonical UTF-8 JSON."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    """Return the SHA-256 binding for canonical private preparation metadata."""

    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


class LocalFixturePreparations:
    """Publish and read one exact non-secret fixture registration preparation."""

    def __init__(self, filesystem: LocalFilesystem) -> None:
        """Bind preparation storage to the private atomic operator filesystem."""

        self._filesystem = filesystem

    @staticmethod
    def _handoff_version(request: FixtureDeployRequest) -> int:
        """Select the closed fixture-owned handoff version without inspecting provider state."""

        return 3 if request.application_id == "fixture-multi-attachment" else 2

    @staticmethod
    def _request_value(request: FixtureDeployRequest) -> dict[str, object]:
        """Project every input that distinguishes a reusable preparation."""

        return {
            "application_id": request.application_id,
            "catalogue_visibility": request.catalogue_visibility,
            "environment": request.environment,
            "expected_platform_generation": request.expected_platform_generation,
            "expected_platform_source_revision": (
                request.expected_platform_source_revision
            ),
            "fixture_source_revision": request.fixture_source_revision,
            "source_authority": request.source_authority,
        }

    @classmethod
    def _metadata(
        cls,
        request: FixtureDeployRequest,
        image_reference: str,
        integration_bundle_digest: str,
        attachment_bundle_digest: str,
    ) -> dict[str, object]:
        """Build canonical preparation metadata and its self-binding digest."""

        value = {
            "format_version": 1,
            **cls._request_value(request),
            "attachment_bundle_digest": attachment_bundle_digest,
            "image_reference": image_reference,
            "integration_bundle_digest": integration_bundle_digest,
        }
        value["preparation_digest"] = _digest(value)
        return value

    @staticmethod
    def _current_path(request: FixtureDeployRequest) -> str:
        """Return the private pointer path for one fixture's current preparation."""

        return (
            f"environments/{request.environment}/fixtures/"
            f"{request.application_id}/preparations/current.v1.json"
        )

    @staticmethod
    def _base_path(request: FixtureDeployRequest, preparation_digest: str) -> str:
        """Return the immutable private directory for one preparation digest."""

        return (
            f"environments/{request.environment}/fixtures/"
            f"{request.application_id}/preparations/"
            f"{preparation_digest[7:]}"
        )

    @classmethod
    def _validate_metadata(
        cls,
        value: object,
    ) -> dict[str, object]:
        """Validate current metadata while recognizing legacy records as stale.

        Preparations written before catalogue visibility became an explicit
        input remain valid private history. They cannot be reused because the
        new request projection will not match them, but they must remain
        readable so the operator can safely generate a successor preparation.
        """

        expected = {
            "application_id",
            "attachment_bundle_digest",
            "catalogue_visibility",
            "environment",
            "expected_platform_generation",
            "expected_platform_source_revision",
            "fixture_source_revision",
            "format_version",
            "image_reference",
            "integration_bundle_digest",
            "preparation_digest",
            "source_authority",
        }
        legacy_expected = expected - {"catalogue_visibility"}
        if (
            not isinstance(value, dict)
            or frozenset(value)
            not in {frozenset(expected), frozenset(legacy_expected)}
        ):
            raise ValueError("stored fixture preparation is invalid")
        if (
            value["format_version"] != 1
            or value["environment"] != "staging"
            or not isinstance(value["application_id"], str)
            or _APPLICATION_ID.fullmatch(value["application_id"]) is None
            or (
                "catalogue_visibility" in value
                and value["catalogue_visibility"] not in {"listed", "unlisted"}
            )
            or not isinstance(value["expected_platform_generation"], int)
            or value["expected_platform_generation"] < 1
            or value["source_authority"] not in {"accepted", "candidate"}
            or not isinstance(value["fixture_source_revision"], str)
            or _REVISION.fullmatch(value["fixture_source_revision"]) is None
            or not isinstance(value["expected_platform_source_revision"], str)
            or _REVISION.fullmatch(value["expected_platform_source_revision"]) is None
            or not isinstance(value["image_reference"], str)
            or any(
                not isinstance(value[name], str)
                or _DIGEST.fullmatch(value[name]) is None
                for name in (
                    "attachment_bundle_digest",
                    "integration_bundle_digest",
                    "preparation_digest",
                )
            )
        ):
            raise ValueError("stored fixture preparation is invalid")
        digest_input = {key: item for key, item in value.items() if key != "preparation_digest"}
        if value["preparation_digest"] != _digest(digest_input):
            raise ValueError("stored fixture preparation digest mismatch")
        return value

    @staticmethod
    def _document(payload: bytes | None, kind: str) -> dict[str, Any]:
        """Read one bounded canonical lifecycle document or fail closed."""

        if payload is None or len(payload) > 262_144:
            raise ValueError("stored fixture preparation document is unavailable")
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("stored fixture preparation document is invalid") from error
        if not isinstance(value, dict):
            raise ValueError("stored fixture preparation document is invalid")
        try:
            canonical = canonical_versioned_lifecycle_bytes(value, kind) + b"\n"
        except ValueError as error:
            raise ValueError(
                "stored fixture preparation document is invalid"
            ) from error
        if payload != canonical:
            raise ValueError("stored fixture preparation document is not canonical")
        return value

    def _read_private(self, relative_path: str) -> bytes | None:
        """Read one operator-state file only when its mode remains private."""

        payload = self._filesystem.read_state(relative_path)
        if payload is None:
            return None
        path = self._filesystem.state_path(relative_path)
        if not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError("stored fixture preparation is not private")
        return payload

    @classmethod
    def _matches_request(
        cls,
        metadata: dict[str, object],
        request: FixtureDeployRequest,
    ) -> bool:
        """Compare all request fields that distinguish safe preparation reuse."""

        return all(
            metadata.get(name) == expected
            for name, expected in cls._request_value(request).items()
        )

    def read(self, request: FixtureDeployRequest) -> FixturePreparation | None:
        """Read and validate one complete reusable V2 or V3 private handoff family."""

        payload = self._read_private(self._current_path(request))
        if payload is None:
            return None
        try:
            raw = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("stored fixture preparation is invalid") from error
        metadata = self._validate_metadata(raw)
        if payload != _canonical(metadata) + b"\n":
            raise ValueError("stored fixture preparation is not canonical")
        if not self._matches_request(metadata, request):
            return None

        preparation_digest = str(metadata["preparation_digest"])
        base = self._base_path(request, preparation_digest)
        manifest_payload = self._read_private(f"{base}/preparation.v1.json")
        if manifest_payload != payload:
            raise ValueError("stored fixture preparation manifest mismatch")
        handoff_version = self._handoff_version(request)
        integration_relative = (
            f"{base}/platform-integration-bundle.v{handoff_version}.json"
        )
        attachment_relative = (
            f"{base}/application-attachment-bundle.v{handoff_version}.json"
        )
        intent_relative = f"{base}/registration-intent.v{handoff_version}.json"
        integration = self._document(
            self._read_private(integration_relative),
            "platform-integration-bundle",
        )
        attachment = self._document(
            self._read_private(attachment_relative),
            "application-attachment-bundle",
        )
        intent_payload = self._read_private(intent_relative)
        if intent_payload is None:
            return None
        intent_value = self._document(intent_payload, "registration-intent")
        if (
            versioned_lifecycle_digest(integration, "platform-integration-bundle")
            != metadata["integration_bundle_digest"]
            or versioned_lifecycle_digest(
                attachment,
                "application-attachment-bundle",
            )
            != metadata["attachment_bundle_digest"]
            or validate_versioned_lifecycle_relationships(
                integration_bundle=integration,
                attachment_bundle=attachment,
                registration_intent=intent_value,
            )
            or integration.get("environment") != request.environment
            or integration.get("application_id") != request.application_id
            or integration.get("generation")
            != request.expected_platform_generation
            or integration.get("platform_source_revision")
            != request.expected_platform_source_revision
            or integration.get("platform_source_authority")
            != request.source_authority
            or attachment.get("application_source_revision")
            != request.fixture_source_revision
        ):
            raise ValueError("stored fixture preparation binding mismatch")
        image = FixtureImageReadback(
            str(metadata["image_reference"]),
            request.fixture_source_revision,
        )
        deployment = FixtureApplicationDeployment(
            request.application_id,
            image.reference,
            attachment,
        )
        return FixturePreparation(
            image=image,
            integration_bundle=integration,
            deployment=deployment,
            integration_bundle_digest=str(metadata["integration_bundle_digest"]),
            attachment_bundle_digest=str(metadata["attachment_bundle_digest"]),
            integration_bundle_path=str(
                self._filesystem.state_path(integration_relative)
            ),
            attachment_bundle_path=str(
                self._filesystem.state_path(attachment_relative)
            ),
            registration_intent_path=str(
                self._filesystem.state_path(intent_relative)
            ),
        )

    def publish(
        self,
        request: FixtureDeployRequest,
        image: FixtureImageReadback,
        integration_bundle: dict[str, Any],
        deployment: FixtureApplicationDeployment,
        intent: RegistrationIntent | None = None,
    ) -> FixturePreparation:
        """Publish one canonical bundle pair, atomically including the required V3 intent."""

        if (
            image.source_revision != request.fixture_source_revision
            or deployment.application_id != request.application_id
            or deployment.image_reference != image.reference
            or integration_bundle.get("environment") != request.environment
            or integration_bundle.get("application_id") != request.application_id
            or integration_bundle.get("generation")
            != request.expected_platform_generation
            or integration_bundle.get("platform_source_revision")
            != request.expected_platform_source_revision
            or integration_bundle.get("platform_source_authority")
            != request.source_authority
            or deployment.attachment_bundle.get("application_source_revision")
            != request.fixture_source_revision
        ):
            raise ValueError("fixture preparation request binding mismatch")
        integration_digest = versioned_lifecycle_digest(
            integration_bundle,
            "platform-integration-bundle",
        )
        attachment_digest = versioned_lifecycle_digest(
            deployment.attachment_bundle,
            "application-attachment-bundle",
        )
        intent_document = intent.document() if intent is not None else None
        handoff_version = self._handoff_version(request)
        if (
            (handoff_version == 3 and intent_document is None)
            or (intent is not None and intent.contract_version != handoff_version)
            or validate_versioned_lifecycle_relationships(
                integration_bundle=integration_bundle,
                attachment_bundle=deployment.attachment_bundle,
                registration_intent=intent_document,
            )
        ):
            raise ValueError("fixture preparation bundle relationship is invalid")
        metadata = self._metadata(
            request,
            image.reference,
            integration_digest,
            attachment_digest,
        )
        preparation_digest = str(metadata["preparation_digest"])
        base = self._base_path(request, preparation_digest)
        integration_relative = (
            f"{base}/platform-integration-bundle.v{handoff_version}.json"
        )
        attachment_relative = (
            f"{base}/application-attachment-bundle.v{handoff_version}.json"
        )
        intent_relative = f"{base}/registration-intent.v{handoff_version}.json"
        self._filesystem.write_state(
            integration_relative,
            canonical_versioned_lifecycle_bytes(
                integration_bundle,
                "platform-integration-bundle",
            )
            + b"\n",
            replace=False,
        )
        self._filesystem.write_state(
            attachment_relative,
            canonical_versioned_lifecycle_bytes(
                deployment.attachment_bundle,
                "application-attachment-bundle",
            )
            + b"\n",
            replace=False,
        )
        if intent_document is not None:
            self._filesystem.write_state(
                intent_relative,
                canonical_versioned_lifecycle_bytes(
                    intent_document,
                    "registration-intent",
                )
                + b"\n",
                replace=False,
            )
        self._filesystem.write_state(
            f"{base}/preparation.v1.json",
            _canonical(metadata) + b"\n",
            replace=False,
        )
        self._filesystem.write_state(
            self._current_path(request),
            _canonical(metadata) + b"\n",
            replace=True,
        )
        return FixturePreparation(
            image=image,
            integration_bundle=integration_bundle,
            deployment=deployment,
            integration_bundle_digest=integration_digest,
            attachment_bundle_digest=attachment_digest,
            integration_bundle_path=str(
                self._filesystem.state_path(integration_relative)
            ),
            attachment_bundle_path=str(
                self._filesystem.state_path(attachment_relative)
            ),
            registration_intent_path=(
                str(self._filesystem.state_path(intent_relative))
                if intent_document is not None
                else None
            ),
        )

    def publish_registration_intent(
        self,
        request: FixtureDeployRequest,
        preparation: FixturePreparation,
        intent: RegistrationIntent,
    ) -> FixturePreparation:
        """Publish a V2 registration intent after its bundle pair is durable."""

        current = self._read_private(self._current_path(request))
        if current is None:
            raise ValueError("fixture preparation is unavailable")
        metadata = self._validate_metadata(json.loads(current))
        base = self._base_path(request, str(metadata["preparation_digest"]))
        handoff_version = self._handoff_version(request)
        relative = f"{base}/registration-intent.v{handoff_version}.json"
        document = intent.document()
        if intent.contract_version != handoff_version:
            raise ValueError("fixture registration intent version is invalid")
        if validate_versioned_lifecycle_relationships(
            integration_bundle=preparation.integration_bundle,
            attachment_bundle=preparation.deployment.attachment_bundle,
            registration_intent=document,
        ):
            raise ValueError("fixture registration intent binding is invalid")
        self._filesystem.write_state(
            relative,
            canonical_versioned_lifecycle_bytes(document, "registration-intent")
            + b"\n",
            replace=False,
        )
        return replace(
            preparation,
            registration_intent_path=str(self._filesystem.state_path(relative)),
        )


__all__ = ("LocalFixturePreparations",)
