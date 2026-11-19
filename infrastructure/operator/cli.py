"""Thin command-line shell over the AP-M9 lifecycle module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from contracts import load_json_document
from contracts.lifecycle import (
    canonical_lifecycle_bytes,
    load_lifecycle_document,
)
from infrastructure.operator._core import LifecycleOperator
from infrastructure.operator.destruction import DestructionLifecycle
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    IntegrationBundleRequest,
    LifecycleChangeRequest,
    RegistrationIntent,
)
from infrastructure.operator.local import LocalFilesystem, build_local_operator
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.qualification import QualificationLifecycle


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DIRECTORY = PROJECT_ROOT / ".platform-operator"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apps-platform-operator")
    parser.add_argument(
        "operation",
        choices=(
            "deploy",
            "detach",
            "outputs",
            "prepare",
            "qualify",
            "register",
            "retire",
            "status",
            "destroy",
        ),
        help="platform lifecycle operation",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("production", "staging"),
    )
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=DEFAULT_STATE_DIRECTORY,
        help="private ignored directory for generated lifecycle state",
    )
    parser.add_argument(
        "--specification-digest",
        help="exact approved deployment specification digest",
    )
    parser.add_argument("--application-id")
    parser.add_argument(
        "--access-mode",
        choices=("authenticated", "public", "restricted"),
    )
    parser.add_argument("--route-intent")
    parser.add_argument("--platform-source-revision")
    parser.add_argument("--platform-generation", type=int)
    parser.add_argument("--generation-digest")
    parser.add_argument("--integration-bundle", type=Path)
    parser.add_argument("--attachment-bundle", type=Path)
    parser.add_argument("--registration-intent", type=Path)
    return parser


def _default_factory(state_directory: Path) -> LifecycleOperator:
    return build_local_operator(PROJECT_ROOT, state_directory)


def _default_integration_factory(
    state_directory: Path,
) -> ApplicationIntegrationLifecycle:
    del state_directory
    raise RuntimeError("APPLICATION_INTEGRATION_ADAPTER_UNAVAILABLE")


def _default_qualification_factory(
    state_directory: Path,
) -> QualificationLifecycle:
    del state_directory
    raise RuntimeError("QUALIFICATION_ADAPTER_UNAVAILABLE")


def _default_destruction_factory(
    state_directory: Path,
) -> DestructionLifecycle:
    del state_directory
    raise RuntimeError("DESTRUCTION_ADAPTER_UNAVAILABLE")


def _required(arguments: argparse.Namespace, name: str) -> object:
    value = getattr(arguments, name)
    if value is None:
        option = name.replace("_", "-")
        raise SystemExit(f"{arguments.operation} requires --{option}")
    return value


def _load_input(path: Path, kind: str) -> dict[str, object]:
    loaded = load_lifecycle_document(path, kind)
    if loaded.violations or loaded.value is None:
        raise ValueError(f"invalid {kind}")
    return loaded.value


def _load_registration_intent(path: Path) -> RegistrationIntent:
    loaded = load_json_document(path, max_bytes=65_536)
    if loaded.violations or not isinstance(loaded.value, dict):
        raise ValueError("invalid registration intent")
    value = loaded.value
    expected = {
        "attachment_id",
        "catalogue_summary",
        "catalogue_title",
        "catalogue_visibility",
        "forwarding_mode",
        "mount_path",
        "restricted_members",
    }
    if set(value) != expected or not isinstance(value["restricted_members"], list):
        raise ValueError("invalid registration intent")
    members: list[tuple[str, str]] = []
    for member in value["restricted_members"]:
        if not isinstance(member, dict) or set(member) != {"issuer", "subject"}:
            raise ValueError("invalid registration intent")
        issuer = member["issuer"]
        subject = member["subject"]
        if not isinstance(issuer, str) or not isinstance(subject, str):
            raise ValueError("invalid registration intent")
        members.append((issuer, subject))
    string_fields = expected - {"restricted_members"}
    if any(not isinstance(value[field], str) for field in string_fields):
        raise ValueError("invalid registration intent")
    return RegistrationIntent(
        catalogue_visibility=value["catalogue_visibility"],
        catalogue_title=value["catalogue_title"],
        catalogue_summary=value["catalogue_summary"],
        attachment_id=value["attachment_id"],
        mount_path=value["mount_path"],
        forwarding_mode=value["forwarding_mode"],
        restricted_members=tuple(members),
    )


def _print(value: dict[str, object]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def main(
    argv: Sequence[str] | None = None,
    *,
    operator_factory: Callable[[Path], LifecycleOperator] = _default_factory,
    integration_factory: Callable[
        [Path], ApplicationIntegrationLifecycle
    ] = _default_integration_factory,
    qualification_factory: Callable[
        [Path], QualificationLifecycle
    ] = _default_qualification_factory,
    destruction_factory: Callable[
        [Path], DestructionLifecycle
    ] = _default_destruction_factory,
) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.operation in {"prepare", "deploy", "status"}:
        operator = operator_factory(arguments.state_directory)
    elif arguments.operation in {"detach", "outputs", "register", "retire"}:
        try:
            integration = integration_factory(arguments.state_directory)
        except RuntimeError as error:
            _print(
                {
                    "blockers": [str(error)],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2
    elif arguments.operation == "qualify":
        try:
            qualification = qualification_factory(arguments.state_directory)
        except RuntimeError as error:
            _print(
                {
                    "blockers": [str(error)],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2
    else:
        try:
            destruction = destruction_factory(arguments.state_directory)
        except RuntimeError as error:
            _print(
                {
                    "blockers": [str(error)],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2

    if arguments.operation == "prepare":
        result = operator.prepare(arguments.environment)
        _print(
            {
                "approved": result.approved,
                "blockers": list(result.blockers),
                "complete": result.complete,
                "environment": arguments.environment,
                "outcome": result.outcome,
                "specification_digest": result.specification_digest,
            }
        )
        return 0 if result.outcome in {"prepared", "unchanged"} else 2

    if arguments.operation == "deploy":
        if arguments.specification_digest is None:
            raise SystemExit("deploy requires --specification-digest")
        result = operator.execute(
            arguments.environment,
            arguments.specification_digest,
        )
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "journal_digest": result.journal_digest,
                "outcome": result.outcome,
                "specification_digest": arguments.specification_digest,
            }
        )
        return 0 if result.outcome in {"succeeded", "unchanged"} else 2

    if arguments.operation == "qualify":
        result = qualification.qualify_current(arguments.environment)
        evidence_path: str | None = None
        if result.evidence is not None and result.evidence_digest is not None:
            evidence_path = (
                f"environments/{arguments.environment}/qualification/evidence/"
                f"{result.evidence_digest[7:]}.v1.json"
            )
            filesystem = LocalFilesystem(
                PROJECT_ROOT,
                arguments.state_directory,
            )
            try:
                filesystem.write_state(
                    evidence_path,
                    canonical_lifecycle_bytes(
                        result.evidence,
                        "qualification-evidence",
                    )
                    + b"\n",
                    replace=False,
                )
                pointer = {
                    "evidence_digest": result.evidence_digest,
                    "outcome": result.outcome,
                }
                filesystem.write_state(
                    (
                        f"environments/{arguments.environment}/qualification/"
                        "current-evidence.v1.json"
                    ),
                    json.dumps(
                        pointer,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n",
                    replace=True,
                )
            except (FileExistsError, ValueError):
                _print(
                    {
                        "blockers": ["QUALIFICATION_EVIDENCE_PUBLICATION_FAILED"],
                        "environment": arguments.environment,
                        "outcome": "blocked",
                    }
                )
                return 2
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "evidence_digest": result.evidence_digest,
                "evidence_path": evidence_path,
                "outcome": result.outcome,
            }
        )
        return 0 if result.outcome == "qualified" else 2

    if arguments.operation == "destroy":
        result = destruction.destroy_current(arguments.environment)
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "last_closed_stage": result.last_closed_stage,
                "outcome": result.outcome,
                "specification_digest": result.specification_digest,
            }
        )
        return 0 if result.outcome == "destroyed" else 2

    if arguments.operation == "outputs":
        result = integration.outputs(
            IntegrationBundleRequest(
                environment=arguments.environment,
                application_id=str(_required(arguments, "application_id")),
                access_mode=str(_required(arguments, "access_mode")),
                route_intent=str(_required(arguments, "route_intent")),
                expected_platform_source_revision=str(
                    _required(arguments, "platform_source_revision")
                ),
                expected_generation=int(
                    _required(arguments, "platform_generation")
                ),
            )
        )
        output_path: str | None = None
        if result.bundle is not None and result.bundle_digest is not None:
            output_path = (
                f"environments/{arguments.environment}/bundles/"
                f"{result.bundle['application_id']}/"
                f"{result.bundle_digest[7:]}.v1.json"
            )
            try:
                LocalFilesystem(
                    PROJECT_ROOT,
                    arguments.state_directory,
                ).write_state(
                    output_path,
                    canonical_lifecycle_bytes(
                        result.bundle,
                        "platform-integration-bundle",
                    )
                    + b"\n",
                    replace=False,
                )
            except FileExistsError:
                _print(
                    {
                        "blockers": ["INTEGRATION_BUNDLE_PUBLICATION_CONFLICT"],
                        "bundle_digest": result.bundle_digest,
                        "bundle_path": output_path,
                        "environment": arguments.environment,
                        "outcome": "blocked",
                    }
                )
                return 2
        _print(
            {
                "blockers": list(result.blockers),
                "bundle_digest": result.bundle_digest,
                "bundle_path": output_path,
                "environment": arguments.environment,
                "outcome": result.outcome,
            }
        )
        return 0 if result.outcome == "generated" else 2

    if arguments.operation == "register":
        try:
            integration_bundle = _load_input(
                Path(_required(arguments, "integration_bundle")),
                "platform-integration-bundle",
            )
            attachment_bundle = _load_input(
                Path(_required(arguments, "attachment_bundle")),
                "application-attachment-bundle",
            )
            intent = _load_registration_intent(
                Path(_required(arguments, "registration_intent"))
            )
        except ValueError:
            _print(
                {
                    "blockers": ["INTEGRATION_INPUT_INVALID"],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2
        result = integration.register(
            integration_bundle,
            attachment_bundle,
            intent,
        )
        if (
            result.outcome in {"activated", "unchanged"}
            and result.generation_digest is not None
        ):
            try:
                handoffs = LocalApplicationHandoffs(
                    LocalFilesystem(PROJECT_ROOT, arguments.state_directory)
                )
                handoff = handoffs.from_bundles(
                    integration_bundle,
                    attachment_bundle,
                    result.generation_digest,
                )
                if not handoffs.record(handoff):
                    raise ValueError("handoff record readback mismatch")
            except (FileExistsError, ValueError):
                _print(
                    {
                        "blockers": ["APPLICATION_HANDOFF_RECORD_FAILED"],
                        "environment": arguments.environment,
                        "generation": result.generation,
                        "generation_digest": result.generation_digest,
                        "outcome": "blocked",
                    }
                )
                return 2
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "generation": result.generation,
                "generation_digest": result.generation_digest,
                "outcome": result.outcome,
            }
        )
        return 0 if result.outcome in {"activated", "unchanged"} else 2
    if arguments.operation in {"detach", "retire"}:
        request = LifecycleChangeRequest(
            environment=arguments.environment,
            application_id=str(_required(arguments, "application_id")),
            expected_platform_source_revision=str(
                _required(arguments, "platform_source_revision")
            ),
            expected_generation_digest=str(
                _required(arguments, "generation_digest")
            ),
        )
        result = (
            integration.detach(request)
            if arguments.operation == "detach"
            else integration.retire(request)
        )
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "generation": result.generation,
                "generation_digest": result.generation_digest,
                "outcome": result.outcome,
            }
        )
        return 0 if result.outcome in {"activated", "unchanged"} else 2

    status = operator.status(arguments.environment)
    _print(status.environment_status)
    return 0 if not status.conflicts else 2
