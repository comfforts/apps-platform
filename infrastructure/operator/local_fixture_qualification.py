"""Local composition seams for fixture-scoped multi-attachment qualification."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from contracts.lifecycle import (
    load_lifecycle_document,
    load_versioned_lifecycle_document,
    validate_versioned_lifecycle_relationships,
    versioned_lifecycle_digest,
)
from infrastructure.operator._interfaces import GitAdapter
from infrastructure.operator.fixture_qualification import (
    FixtureQualificationPublication,
    FixtureQualificationReadback,
    FixtureQualificationTarget,
    FixtureQualificationVerification,
)
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    AttachmentTargetReader,
    GenerationActivationReadback,
    GenerationPublicationReadback,
    PlatformIntegrationReader,
    RegistrationGenerationControl,
    RegistrationGenerationProposal,
    RegistrationIntent,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_fixture_preparations import (
    LocalFixturePreparations,
)
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.local_qualification import RegistrationGenerationReader
from infrastructure.operator.source_authority import (
    source_authority_blockers,
    validate_source_authority,
)


_APPLICATION_ID = "fixture-multi-attachment"
_DIGEST_PREFIX = "sha256:"


def _canonical(value: object) -> bytes:
    """Serialize one private result or status deterministically."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    """Return a canonical SHA-256 digest for a private result or status."""

    return _DIGEST_PREFIX + hashlib.sha256(_canonical(value)).hexdigest()


class LocalFixtureQualificationStateReader:
    """Join Accepted platform evidence, V3 handoff, and active V2 registration.

    The reader opens only repository-owned private operator records and injected
    Git/generation seams.  It never reads Terraform or Application State, never
    mutates a provider, and fails closed unless the fourth fixture's complete
    handoff is the exact active registration projection.
    """

    def __init__(
        self,
        filesystem: LocalFilesystem,
        git: GitAdapter,
        generations: RegistrationGenerationReader,
        preparations: LocalFixturePreparations,
        handoffs: LocalApplicationHandoffs,
        source_authority: str,
    ) -> None:
        """Bind private state and source-admission readers for one authority."""

        self._filesystem = filesystem
        self._git = git
        self._generations = generations
        self._preparations = preparations
        self._handoffs = handoffs
        self._source_authority = validate_source_authority(source_authority)

    def _accepted_platform_qualification(
        self,
        environment: str,
    ) -> tuple[str, dict[str, Any]]:
        """Load the exact current Accepted Source platform qualification result."""

        pointer_payload = self._filesystem.read_state(
            f"environments/{environment}/qualification/current-evidence.v1.json"
        )
        if pointer_payload is None:
            raise ValueError("accepted platform qualification is unavailable")
        try:
            pointer = json.loads(pointer_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("accepted platform qualification is invalid") from error
        if (
            not isinstance(pointer, dict)
            or set(pointer) != {"evidence_digest", "outcome"}
            or pointer.get("outcome") != "qualified"
            or not isinstance(pointer.get("evidence_digest"), str)
        ):
            raise ValueError("accepted platform qualification is invalid")
        digest = str(pointer["evidence_digest"])
        if not digest.startswith(_DIGEST_PREFIX) or len(digest) != 71:
            raise ValueError("accepted platform qualification digest is invalid")
        path = self._filesystem.state_path(
            f"environments/{environment}/qualification/evidence/"
            f"{digest[7:]}.v1.json"
        )
        loaded = load_lifecycle_document(path, "qualification-evidence")
        if (
            loaded.value is None
            or loaded.violations
            or loaded.digest != digest
            or loaded.value.get("environment") != environment
            or loaded.value.get("source_authority") != "accepted"
            or loaded.value.get("verdict") != "qualified"
            or not isinstance(loaded.value.get("source_revision"), str)
        ):
            raise ValueError("accepted platform qualification binding is invalid")
        return digest, loaded.value

    @staticmethod
    def _intent(path: str | None) -> RegistrationIntent:
        """Load one canonical prepared intent from its private absolute path."""

        if path is None:
            raise ValueError("fixture registration intent is unavailable")
        loaded = load_versioned_lifecycle_document(
            Path(path),
            "registration-intent",
            max_bytes=65_536,
        )
        if loaded.value is None or loaded.violations:
            raise ValueError("fixture registration intent is invalid")
        return RegistrationIntent.from_document(loaded.value)

    @staticmethod
    def _targets(
        attachment: dict[str, Any],
        intent: RegistrationIntent,
    ) -> tuple[FixtureQualificationTarget, ...]:
        """Project the root and optional targets into exact reviewed bindings."""

        root = attachment.get("target")
        additional = attachment.get("additional_attachments")
        if not isinstance(root, dict) or not isinstance(additional, list):
            raise ValueError("fixture attachment set is incomplete")
        targets_by_id: dict[str, dict[str, Any]] = {intent.attachment_id: root}
        for entry in additional:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("attachment_id"), str)
                or not isinstance(entry.get("target"), dict)
            ):
                raise ValueError("fixture attachment set is invalid")
            targets_by_id[str(entry["attachment_id"])] = entry["target"]
        bindings = (
            (intent.attachment_id, intent.mount_path),
            *(
                (item.attachment_id, item.mount_path)
                for item in intent.additional_attachment_bindings
            ),
        )
        if set(targets_by_id) != {item[0] for item in bindings}:
            raise ValueError("fixture attachment set does not match its intent")
        result: list[FixtureQualificationTarget] = []
        for attachment_id, mount_path in bindings:
            target = targets_by_id[attachment_id]
            reference = target.get("resource_reference")
            audience = target.get("audience")
            if not isinstance(reference, str) or not isinstance(audience, str):
                raise ValueError("fixture target binding is invalid")
            result.append(
                FixtureQualificationTarget(
                    attachment_id,
                    mount_path,
                    reference,
                    audience,
                )
            )
        return tuple(sorted(result))

    @staticmethod
    def _registration_matches(
        registration: dict[str, Any],
        targets: tuple[FixtureQualificationTarget, ...],
        intent: RegistrationIntent,
    ) -> bool:
        """Compare the active V2 registration with the complete prepared V3 family."""

        attachments = registration.get("attachments")
        if not isinstance(attachments, list):
            return False
        active_by_id = {
            item.get("attachment_id"): item
            for item in attachments
            if isinstance(item, dict)
            and isinstance(item.get("attachment_id"), str)
        }
        bindings = {
            intent.attachment_id: (
                intent.mount_path,
                intent.forwarding_mode,
            ),
            **{
                item.attachment_id: (item.mount_path, item.forwarding_mode)
                for item in intent.additional_attachment_bindings
            },
        }
        return (
            registration.get("application_id") == _APPLICATION_ID
            and registration.get("lifecycle") == "active"
            and registration.get("route_prefix") == f"/{_APPLICATION_ID}"
            and registration.get("admission") == {"mode": "authenticated"}
            and registration.get("identity_delivery") == "required"
            and set(active_by_id) == {item.attachment_id for item in targets}
            and all(
                active_by_id[item.attachment_id].get("owner_application_id")
                == _APPLICATION_ID
                and active_by_id[item.attachment_id].get("resource_reference")
                == item.resource_reference
                and active_by_id[item.attachment_id].get("audience")
                == item.audience
                and active_by_id[item.attachment_id].get("mount_path")
                == bindings[item.attachment_id][0]
                and active_by_id[item.attachment_id].get("forwarding_mode")
                == bindings[item.attachment_id][1]
                for item in targets
            )
        )

    def read_current(
        self,
        environment: str,
        application_id: str,
    ) -> FixtureQualificationReadback:
        """Read and validate the current plural-fixture qualification binding."""

        if environment != "staging" or application_id != _APPLICATION_ID:
            raise ValueError("fixture qualification selection is unavailable")
        source = self._git.inspect()
        blockers = source_authority_blockers(
            source,
            environment,
            self._source_authority,
        )
        if blockers:
            raise ValueError("fixture qualification source is not admitted")
        platform_digest, platform_evidence = (
            self._accepted_platform_qualification(environment)
        )
        current = self._generations.current(environment)
        if (
            current is None
            or current.environment != environment
            or current.registration_set.get("contract_version") != 2
            or not isinstance(current.registration_set.get("generation"), int)
            or not isinstance(current.registration_set.get("registrations"), list)
        ):
            raise ValueError("active registration generation is unavailable")
        generation = int(current.registration_set["generation"])
        registrations = current.registration_set["registrations"]
        selected = [
            item
            for item in registrations
            if isinstance(item, dict)
            and item.get("application_id") == application_id
        ]
        if len(selected) != 1:
            raise ValueError("fixture registration is not uniquely active")

        prepared = self._preparations.read_current(environment, application_id)
        if prepared is None:
            raise ValueError("fixture preparation is unavailable")
        request, preparation = prepared
        integration = preparation.integration_bundle
        attachment = preparation.deployment.attachment_bundle
        intent = self._intent(preparation.registration_intent_path)
        intent_document = intent.document()
        qualified_platform_source = platform_evidence.get("source_revision")
        platform_source = integration.get("platform_source_revision")
        if (
            request.source_authority != self._source_authority
            or request.fixture_source_revision != source.revision
            or integration.get("contract_version") != 3
            or attachment.get("contract_version") != 3
            or intent.contract_version != 3
            or integration.get("environment") != environment
            or integration.get("application_id") != application_id
            or integration.get("access_mode") != "authenticated"
            or integration.get("identity_delivery") != "required"
            or integration.get("platform_source_authority")
            != self._source_authority
            or not isinstance(qualified_platform_source, str)
            or not isinstance(platform_source, str)
            or request.expected_platform_source_revision != platform_source
            or attachment.get("application_source_revision") != source.revision
            or validate_versioned_lifecycle_relationships(
                integration_bundle=integration,
                attachment_bundle=attachment,
                registration_intent=intent_document,
            )
        ):
            raise ValueError("fixture handoff binding is invalid")
        integration_digest = versioned_lifecycle_digest(
            integration,
            "platform-integration-bundle",
        )
        attachment_digest = versioned_lifecycle_digest(
            attachment,
            "application-attachment-bundle",
        )
        if (
            integration_digest != preparation.integration_bundle_digest
            or attachment_digest != preparation.attachment_bundle_digest
        ):
            raise ValueError("fixture handoff digest is invalid")
        handoff = self._handoffs.latest_for_application(
            environment,
            application_id,
            generation,
        )
        if (
            handoff is None
            or handoff.application_source_revision != source.revision
            or handoff.integration_bundle_digest != integration_digest
            or handoff.attachment_bundle_digest != attachment_digest
        ):
            raise ValueError("accepted fixture handoff is unavailable")
        targets = self._targets(attachment, intent)
        if not self._registration_matches(selected[0], targets, intent):
            raise ValueError("active fixture registration does not match the handoff")
        return FixtureQualificationReadback(
            environment=environment,
            application_id=application_id,
            source_authority=self._source_authority,
            platform_qualification_digest=platform_digest,
            platform_source_revision=platform_source,
            fixture_source_revision=source.revision,
            integration_bundle_digest=integration_digest,
            attachment_bundle_digest=attachment_digest,
            registration_generation=generation,
            registration_generation_digest=current.generation_digest,
            targets=targets,
            integration_bundle=copy.deepcopy(integration),
            attachment_bundle=copy.deepcopy(attachment),
            registration_intent=copy.deepcopy(intent_document),
        )


class LocalFixtureAttachmentVerifier:
    """Verify the complete attachment family through existing provider readback."""

    def __init__(
        self,
        integration: ApplicationIntegrationLifecycle,
        targets: AttachmentTargetReader,
    ) -> None:
        """Bind the atomic handoff validator and exact target reader."""

        self._integration = integration
        self._targets = targets

    def verify_attachment_set(
        self,
        current: FixtureQualificationReadback,
    ) -> FixtureQualificationVerification:
        """Validate both V3 targets together without a generation mutation seam."""

        intent = RegistrationIntent.from_document(current.registration_intent)
        result = self._integration.validate_attachment(
            current.integration_bundle,
            current.attachment_bundle,
            intent,
        )
        if result.outcome != "validated":
            return FixtureQualificationVerification(
                False,
                {
                    "result": "mismatch",
                    "target_count": len(current.targets),
                    "violation_count": len(result.target_violations),
                },
                ("FIXTURE_ATTACHMENT_POSTURE_MISMATCH",),
            )
        return FixtureQualificationVerification(
            True,
            {"result": "verified", "target_count": len(current.targets)},
        )

    def verify_direct_origin_denial(
        self,
        current: FixtureQualificationReadback,
    ) -> FixtureQualificationVerification:
        """Read internal ingress and sole edge-caller IAM posture for both targets."""

        declared: dict[str, dict[str, Any]] = {}
        intent = RegistrationIntent.from_document(current.registration_intent)
        root = current.attachment_bundle["target"]
        assert isinstance(root, dict)
        declared[intent.attachment_id] = root
        for item in current.attachment_bundle.get("additional_attachments", []):
            assert isinstance(item, dict) and isinstance(item.get("target"), dict)
            declared[str(item["attachment_id"])] = item["target"]
        denied = 0
        for target in current.targets:
            expected = declared[target.attachment_id]
            readback = self._targets.read_target(
                current.environment,
                target.resource_reference,
            )
            if (
                not readback.exists
                or not readback.ready
                or readback.resource_reference != target.resource_reference
                or readback.ingress_mode != "shared_edge_only"
                or readback.caller_grant != expected.get("caller_grant")
                or readback.blockers
            ):
                return FixtureQualificationVerification(
                    False,
                    {"denied_targets": denied, "result": "mismatch"},
                    ("FIXTURE_DIRECT_ORIGIN_DENIAL_MISMATCH",),
                )
            denied += 1
        return FixtureQualificationVerification(
            True,
            {"denied_targets": denied, "result": "verified"},
        )


class _MutationGuard(RegistrationGenerationControl):
    """Fail if rejected-candidate validation reaches any generation operation."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def current(self, environment: str) -> RegistrationGenerationProposal | None:
        """Reject even a generation read because target validation must fail first."""

        del environment
        self.calls.append("current")
        raise AssertionError("failed target reached generation control")

    def publish(
        self,
        proposal: RegistrationGenerationProposal,
    ) -> GenerationPublicationReadback:
        """Reject any attempted immutable publication."""

        del proposal
        self.calls.append("publish")
        raise AssertionError("failed target reached publication")

    def activate(
        self,
        environment: str,
        publication_reference: str,
        generation_digest: str,
    ) -> GenerationActivationReadback:
        """Reject any attempted active-pointer or traffic change."""

        del environment, publication_reference, generation_digest
        self.calls.append("activate")
        raise AssertionError("failed target reached activation")


class _MutationTerminal:
    """Reject confirmation/output paths unreachable after target failure."""

    def write(self, message: str) -> None:
        """Reject generation output because validation must stop earlier."""

        del message
        raise AssertionError("failed target reached terminal output")

    def confirm_exact(self, prompt: str, expected: str) -> bool:
        """Reject activation confirmation because no proposal may exist."""

        del prompt, expected
        raise AssertionError("failed target reached confirmation")


class LocalFailedTargetQualification:
    """Prove either missing target blocks before publication or traffic change."""

    def __init__(
        self,
        platform: PlatformIntegrationReader,
        targets: AttachmentTargetReader,
        generations: RegistrationGenerationReader,
    ) -> None:
        """Bind read-only platform, target, and active-generation readers."""

        self._platform = platform
        self._targets = targets
        self._generations = generations

    @staticmethod
    def _missing_candidate(
        current: FixtureQualificationReadback,
        attachment_id: str,
    ) -> dict[str, Any]:
        """Return a private clone selecting one deterministic absent service."""

        candidate = copy.deepcopy(current.attachment_bundle)
        if attachment_id == "web":
            target = candidate["target"]
        else:
            target = next(
                item["target"]
                for item in candidate["additional_attachments"]
                if item["attachment_id"] == attachment_id
            )
        assert isinstance(target, dict)
        reference = target["resource_reference"]
        assert isinstance(reference, str)
        target["resource_reference"] = reference + "-missing"
        return candidate

    def verify(
        self,
        current: FixtureQualificationReadback,
    ) -> FixtureQualificationVerification:
        """Reject root and API candidates while the active digest remains exact."""

        before = self._generations.current(current.environment)
        if (
            before is None
            or before.generation_digest
            != current.registration_generation_digest
        ):
            return FixtureQualificationVerification(
                False,
                {"result": "active-generation-mismatch"},
                ("FIXTURE_FAILED_TARGET_BASELINE_MISMATCH",),
            )
        rejected = 0
        for attachment_id in ("web", "api"):
            guard = _MutationGuard()
            integration = ApplicationIntegrationLifecycle(
                self._platform,
                attachment_reader=self._targets,
                generation_control=guard,
                terminal=_MutationTerminal(),  # type: ignore[arg-type]
            )
            result = integration.register(
                current.integration_bundle,
                self._missing_candidate(current, attachment_id),
                RegistrationIntent.from_document(current.registration_intent),
            )
            matching = [
                item
                for item in result.target_violations
                if item.attachment_id == attachment_id
                and item.code == "TARGET_NOT_FOUND"
            ]
            if result.outcome != "blocked" or not matching or guard.calls:
                return FixtureQualificationVerification(
                    False,
                    {
                        "mutation_seam_calls": len(guard.calls),
                        "rejected_candidates": rejected,
                        "result": "mismatch",
                    },
                    ("FIXTURE_FAILED_TARGET_ATOMICITY_MISMATCH",),
                )
            rejected += 1
        after = self._generations.current(current.environment)
        preserved = (
            after is not None
            and after.generation_digest == before.generation_digest
            and after.registration_set == before.registration_set
        )
        if not preserved:
            return FixtureQualificationVerification(
                False,
                {"rejected_candidates": rejected, "result": "traffic-changed"},
                ("FIXTURE_FAILED_TARGET_GENERATION_CHANGED",),
            )
        return FixtureQualificationVerification(
            True,
            {
                "active_generation_preserved": True,
                "activation_attempts": 0,
                "publication_attempts": 0,
                "rejected_candidates": rejected,
                "result": "verified",
            },
        )


class LocalFixtureQualificationEvidence:
    """Publish private fixture results outside the platform qualification tree."""

    def __init__(self, filesystem: LocalFilesystem) -> None:
        """Bind atomic writes to the repository-owned private operator root."""

        self._filesystem = filesystem

    @staticmethod
    def _root(result: dict[str, Any]) -> str:
        """Select the accepted or candidate fixture-only namespace."""

        authority = result.get("source_authority")
        base = "fixture-qualification"
        if authority == "candidate":
            base += "/candidates"
        elif authority != "accepted":
            raise ValueError("fixture qualification source authority is invalid")
        return (
            f"environments/{result['environment']}/{base}/"
            f"{result['application_id']}"
        )

    def publish(
        self,
        result: dict[str, Any],
        result_digest: str,
    ) -> FixtureQualificationPublication:
        """Write immutable result plus replaceable current status and reread both."""

        if (
            result.get("document_kind") != "fixture-qualification-result"
            or result.get("format_version") != 1
            or result.get("environment") != "staging"
            or result.get("application_id") != _APPLICATION_ID
            or result.get("verdict") not in {"failed", "qualified"}
            or result_digest != _digest(result)
        ):
            raise ValueError("fixture qualification result is invalid")
        root = self._root(result)
        result_path = f"{root}/results/{result_digest[7:]}.v1.json"
        outcome = (
            "candidate-qualified"
            if result["verdict"] == "qualified"
            and result["source_authority"] == "candidate"
            else result["verdict"]
        )
        status = {
            "application_id": result["application_id"],
            "document_kind": "fixture-qualification-status",
            "environment": result["environment"],
            "format_version": 1,
            "outcome": outcome,
            "platform_qualification_digest": result[
                "platform_qualification_digest"
            ],
            "registration_generation_digest": result[
                "registration_generation_digest"
            ],
            "result_digest": result_digest,
            "source_authority": result["source_authority"],
        }
        status_path = f"{root}/current-status.v1.json"
        result_payload = _canonical(result) + b"\n"
        status_payload = _canonical(status) + b"\n"
        self._filesystem.write_state(result_path, result_payload, replace=False)
        self._filesystem.write_state(status_path, status_payload, replace=True)
        if (
            self._filesystem.read_state(result_path) != result_payload
            or self._filesystem.read_state(status_path) != status_payload
        ):
            raise OSError("fixture qualification evidence readback mismatch")
        return FixtureQualificationPublication(result_path, status_path)


__all__ = (
    "LocalFailedTargetQualification",
    "LocalFixtureAttachmentVerifier",
    "LocalFixtureQualificationEvidence",
    "LocalFixtureQualificationStateReader",
)
