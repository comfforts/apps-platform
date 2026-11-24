"""Thin command-line shell over the AP-M9 lifecycle module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
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
from infrastructure.operator.local import (
    LocalFilesystem,
    build_local_destruction,
    build_local_fixture_operator,
    build_local_fixture_status_operator,
    build_local_integration,
    build_local_operator,
    build_local_project_lifecycle,
    build_local_qualification,
)
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.output import print_result as _print
from infrastructure.operator.qualification import QualificationLifecycle


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DIRECTORY = PROJECT_ROOT / ".platform-operator"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apps-platform-operator")
    parser.add_argument(
        "operation",
        choices=(
            "cancel",
            "deploy",
            "detach",
            "outputs",
            "preflight",
            "prepare",
            "qualify",
            "register",
            "retire",
            "status",
            "fixture-project-bootstrap",
            "platform-connect-project",
            "destroy",
            "fixture-handoff",
            "fixture-status",
            "fixture-destroy",
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
        "--source-authority",
        choices=("accepted", "candidate"),
        default="accepted",
        help="accepted main or a clean pushed staging candidate",
    )
    parser.add_argument(
        "--preflight-mode",
        choices=("development", "operational"),
        default="operational",
        help="enforce source admission or report it as a development diagnostic",
    )
    parser.add_argument(
        "--specification-digest",
        help=(
            "optional explicit current approved deployment specification digest; "
            "default deploy discovers and reuses one automatically"
        ),
    )
    parser.add_argument("--application-id")
    parser.add_argument("--application-project-id")
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


def _default_factory(
    state_directory: Path,
    source_authority: str,
) -> LifecycleOperator:
    return build_local_operator(PROJECT_ROOT, state_directory, source_authority)


def _default_preflight_factory(
    state_directory: Path,
    source_authority: str,
) -> LifecycleOperator:
    return build_local_operator(
        PROJECT_ROOT,
        state_directory,
        source_authority,
        arm_executor=False,
    )


def _default_integration_factory(
    state_directory: Path,
    source_authority: str,
) -> ApplicationIntegrationLifecycle:
    return build_local_integration(PROJECT_ROOT, state_directory, source_authority)


def _default_qualification_factory(
    state_directory: Path,
    source_authority: str,
) -> QualificationLifecycle:
    return build_local_qualification(PROJECT_ROOT, state_directory, source_authority)


def _default_destruction_factory(
    state_directory: Path,
    source_authority: str,
) -> DestructionLifecycle:
    return build_local_destruction(PROJECT_ROOT, state_directory, source_authority)


def _default_fixture_factory(  # type: ignore[no-untyped-def]
    state_directory: Path,
    source_authority: str,
):
    return build_local_fixture_operator(
        PROJECT_ROOT,
        state_directory,
        source_authority,
    )


def _default_fixture_status_factory(  # type: ignore[no-untyped-def]
    state_directory: Path,
    source_authority: str,
):
    return build_local_fixture_status_operator(
        PROJECT_ROOT,
        state_directory,
        source_authority,
    )


def _default_project_factory(  # type: ignore[no-untyped-def]
    state_directory: Path,
    source_authority: str,
):
    return build_local_project_lifecycle(
        PROJECT_ROOT,
        state_directory,
        source_authority,
    )


def _required(arguments: argparse.Namespace, name: str) -> object:
    value = getattr(arguments, name)
    if value is None or (isinstance(value, str) and not value.strip()):
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


def _trace_invocation(
    arguments: argparse.Namespace,
    selected_fixture: str | None,
) -> None:
    print("Operator invocation:", file=sys.stderr)
    print(f"  operation: {arguments.operation}", file=sys.stderr)
    print(f"  environment: {arguments.environment}", file=sys.stderr)
    print(f"  state directory: {arguments.state_directory}", file=sys.stderr)
    print(f"  source authority: {arguments.source_authority}", file=sys.stderr)
    if arguments.operation == "preflight":
        print(f"  preflight mode: {arguments.preflight_mode}", file=sys.stderr)
    print(
        f"  fixture selected: {selected_fixture or 'none'}",
        file=sys.stderr,
    )
    print(file=sys.stderr)


def _main(
    argv: Sequence[str] | None = None,
    *,
    operator_factory: Callable[[Path, str], LifecycleOperator] = _default_factory,
    preflight_factory: Callable[
        [Path, str], LifecycleOperator
    ] = _default_preflight_factory,
    integration_factory: Callable[
        [Path, str], ApplicationIntegrationLifecycle
    ] = _default_integration_factory,
    qualification_factory: Callable[
        [Path, str], QualificationLifecycle
    ] = _default_qualification_factory,
    destruction_factory: Callable[
        [Path, str], DestructionLifecycle
    ] = _default_destruction_factory,
    fixture_factory: Callable[[Path, str], object] = _default_fixture_factory,
    fixture_status_factory: Callable[[Path, str], object] = _default_fixture_status_factory,
    project_factory: Callable[[Path, str], object] = _default_project_factory,
) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.operation != "preflight" and arguments.preflight_mode != "operational":
        parser.error("--preflight-mode=development is valid only for preflight")
    selected_fixture = (
        str(_required(arguments, "application_id"))
        if arguments.operation
        in {"fixture-handoff", "fixture-destroy"}
        else None
    )
    _trace_invocation(arguments, selected_fixture)
    if arguments.operation in {
        "cancel",
        "deploy",
        "preflight",
        "prepare",
        "status",
    }:
        selected_operator_factory = (
            preflight_factory
            if arguments.operation in {"cancel", "preflight", "status"}
            else operator_factory
        )
        operator = selected_operator_factory(
            arguments.state_directory,
            arguments.source_authority,
        )
    elif arguments.operation in {"detach", "outputs", "register", "retire"}:
        try:
            integration = integration_factory(
                arguments.state_directory,
                arguments.source_authority,
            )
        except RuntimeError as error:
            _print(
                {
                    "blockers": [str(error)],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2
    elif arguments.operation in {
        "fixture-handoff",
        "fixture-destroy",
    }:
        try:
            fixture = fixture_factory(
                arguments.state_directory,
                arguments.source_authority,
            )
        except RuntimeError as error:
            _print(
                {
                    "blockers": [str(error)],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2
    elif arguments.operation in {
        "fixture-project-bootstrap",
        "platform-connect-project",
    }:
        try:
            projects = project_factory(
                arguments.state_directory,
                arguments.source_authority,
            )
        except RuntimeError as error:
            _print(
                {
                    "blockers": [str(error)],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2
    elif arguments.operation == "fixture-status":
        try:
            fixture = fixture_status_factory(
                arguments.state_directory,
                arguments.source_authority,
            )
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
            qualification = qualification_factory(
                arguments.state_directory,
                arguments.source_authority,
            )
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
            destruction = destruction_factory(
                arguments.state_directory,
                arguments.source_authority,
            )
        except RuntimeError as error:
            _print(
                {
                    "blockers": [str(error)],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2

    if arguments.operation == "preflight":
        result = operator.preflight(
            arguments.environment,
            mode=arguments.preflight_mode,
        )
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "outcome": result.outcome,
                "operational_ready": result.operational_ready,
                "preflight_mode": arguments.preflight_mode,
                "ready": result.ready,
                "source_authority": arguments.source_authority,
                "source_admission_blockers": list(
                    result.source_admission_blockers
                ),
            }
        )
        return 0 if result.ready else 2

    if arguments.operation == "prepare":
        result = operator.prepare(arguments.environment)
        _print(
            {
                "approved": result.approved,
                "blockers": list(result.blockers),
                "complete": result.complete,
                "environment": arguments.environment,
                "outcome": result.outcome,
                "source_authority": arguments.source_authority,
                "specification_digest": result.specification_digest,
            }
        )
        return 0 if result.outcome in {"prepared", "unchanged"} else 2

    if arguments.operation == "cancel":
        result = operator.cancel(arguments.environment)
        progress = result.progress or {}
        completed = progress.get("completed", [])
        last_closed_stage = (
            completed[-1]["stage_id"]
            if isinstance(completed, list) and completed
            else None
        )
        _print(
            {
                "active_stage": progress.get("active_stage"),
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "last_closed_stage": last_closed_stage,
                "outcome": result.outcome,
                "progress_digest": result.progress_digest,
                "source_authority": arguments.source_authority,
                "source_revision": progress.get("source_revision"),
                "specification_digest": progress.get("specification_digest"),
            }
        )
        return 0 if result.outcome in {"cancelled", "unchanged"} else 2

    if arguments.operation == "fixture-project-bootstrap":
        project_id = str(_required(arguments, "application_project_id"))
        result = projects.bootstrap_fixture(arguments.environment, project_id)
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "outcome": result.outcome,
                "project_id": result.project_id,
                "project_number": result.project_number,
                "source_authority": arguments.source_authority,
            }
        )
        return 0 if result.outcome in {"bootstrapped", "unchanged"} else 2

    if arguments.operation == "platform-connect-project":
        project_id = str(_required(arguments, "application_project_id"))
        result = projects.connect(arguments.environment, project_id)
        _print(
            {
                "blockers": list(result.blockers),
                "connection_path": result.connection_path,
                "environment": arguments.environment,
                "outcome": result.outcome,
                "project_id": result.project_id,
                "project_number": result.project_number,
                "source_authority": arguments.source_authority,
            }
        )
        return 0 if result.outcome == "connected" else 2

    if arguments.operation == "fixture-handoff":
        integration_bundle_path = Path(
            _required(arguments, "integration_bundle")
        )
        try:
            integration_bundle = _load_input(
                integration_bundle_path,
                "platform-integration-bundle",
            )
        except ValueError:
            _print(
                {
                    "blockers": ["INTEGRATION_BUNDLE_INVALID"],
                    "environment": arguments.environment,
                    "outcome": "blocked",
                }
            )
            return 2
        result = fixture.handoff(
            arguments.environment,
            selected_fixture,
            integration_bundle,
            str(integration_bundle_path.resolve()),
        )
        _print(
            {
                "application_id": result.application_id,
                "attachment_bundle_digest": result.attachment_bundle_digest,
                "attachment_bundle_path": result.attachment_bundle_path,
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "image_reference": result.image_reference,
                "integration_bundle_digest": result.integration_bundle_digest,
                "integration_bundle_path": result.integration_bundle_path,
                "outcome": result.outcome,
                "preparation_reused": result.preparation_reused,
                "registration_intent_path": result.registration_intent_path,
                "source_authority": arguments.source_authority,
            }
        )
        if result.outcome == "prepared":
            print("Fixture handoff prepared successfully.", file=sys.stderr)
            print(f"  Application: {selected_fixture}", file=sys.stderr)
            print(
                f"  Platform integration bundle: {result.integration_bundle_path}",
                file=sys.stderr,
            )
            print(
                f"  Application attachment bundle: {result.attachment_bundle_path}",
                file=sys.stderr,
            )
            print(
                f"  Registration intent: {result.registration_intent_path}",
                file=sys.stderr,
            )
            print(
                "  The fixture runtime exists in the application project, but its route "
                "is inactive. Inspect both bundles, then run platform-register.",
                file=sys.stderr,
            )
            print(file=sys.stderr)
        return 0 if result.outcome == "prepared" else 2

    if arguments.operation == "fixture-status":
        result = fixture.status(
            arguments.environment,
            arguments.application_id,
        )
        _print(
            {
                "applications": [
                    {
                        "application_id": item.application_id,
                        "lifecycle": item.lifecycle,
                        "target_exists": item.target_exists,
                        "target_ready": item.target_ready,
                        "route_ready": item.route_ready,
                    }
                    for item in result.applications
                ],
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "outcome": result.outcome,
                "source_authority": arguments.source_authority,
                "registration_generation": result.registration_generation,
                "registration_generation_digest": (
                    result.registration_generation_digest
                ),
            }
        )
        return 0 if result.outcome == "read" else 2

    if arguments.operation == "fixture-destroy":
        result = fixture.destroy(
            arguments.environment,
            selected_fixture,
        )
        _print(
            {
                "application_id": result.application_id,
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "outcome": result.outcome,
                "source_authority": arguments.source_authority,
                "registration_generation": result.registration_generation,
                "registration_generation_digest": (
                    result.registration_generation_digest
                ),
            }
        )
        return 0 if result.outcome == "destroyed" else 2

    if arguments.operation == "deploy":
        specification_digest = arguments.specification_digest
        if specification_digest is None:
            prepared = operator.current_approved_specification(
                arguments.environment
            )
            if prepared is None:
                prepared = operator.prepare(arguments.environment)
            specification_digest = prepared.specification_digest
            if (
                prepared.outcome not in {"prepared", "unchanged"}
                or not prepared.approved
                or specification_digest is None
            ):
                _print(
                    {
                        "blockers": list(prepared.blockers),
                        "environment": arguments.environment,
                        "outcome": prepared.outcome,
                        "source_authority": arguments.source_authority,
                        "specification_digest": specification_digest,
                    }
                )
                return 2
        result = operator.execute(
            arguments.environment,
            specification_digest,
        )
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "outcome": result.outcome,
                "progress_digest": result.progress_digest,
                "source_authority": arguments.source_authority,
                "specification_digest": specification_digest,
            }
        )
        return 0 if result.outcome in {"succeeded", "unchanged"} else 2

    if arguments.operation == "qualify":
        result = qualification.qualify_current(arguments.environment)
        evidence_path: str | None = None
        if result.evidence is not None and result.evidence_digest is not None:
            qualification_root = (
                "qualification"
                if arguments.source_authority == "accepted"
                else "qualification/candidates"
            )
            evidence_path = (
                f"environments/{arguments.environment}/{qualification_root}/evidence/"
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
                        f"environments/{arguments.environment}/{qualification_root}/"
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
                "source_authority": arguments.source_authority,
            }
        )
        return 0 if result.outcome in {"candidate-qualified", "qualified"} else 2

    if arguments.operation == "destroy":
        result = destruction.destroy_current(arguments.environment)
        _print(
            {
                "blockers": list(result.blockers),
                "environment": arguments.environment,
                "last_closed_stage": result.last_closed_stage,
                "outcome": result.outcome,
                "source_authority": arguments.source_authority,
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
                application_project_id=str(
                    _required(arguments, "application_project_id")
                ),
            )
        )
        output_path: str | None = None
        if result.bundle is not None and result.bundle_digest is not None:
            relative_output_path = (
                f"environments/{arguments.environment}/bundles/"
                f"{result.bundle['application_id']}/"
                f"{result.bundle_digest[7:]}.v1.json"
            )
            filesystem = LocalFilesystem(PROJECT_ROOT, arguments.state_directory)
            output_path = str(filesystem.state_path(relative_output_path))
            try:
                filesystem.write_state(
                    relative_output_path,
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
                "source_authority": arguments.source_authority,
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
            and result.generation is not None
            and result.generation_digest is not None
        ):
            try:
                handoffs = LocalApplicationHandoffs(
                    LocalFilesystem(PROJECT_ROOT, arguments.state_directory)
                )
                handoff = handoffs.from_bundles(
                    integration_bundle,
                    attachment_bundle,
                    int(result.generation),
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
    observed = status.environment_status
    if observed.get("lifecycle_state") != "absent":
        print("Platform status source readback:", file=sys.stderr)
        print(
            f"  current checkout: {observed.get('checkout_source_revision')}",
            file=sys.stderr,
        )
        print(
            "  recorded deployment operation: "
            f"{observed.get('recorded_deployment_source_revision')}",
            file=sys.stderr,
        )
        print(
            f"  active Shared Edge runtime: {observed.get('active_runtime_source_revision')}",
            file=sys.stderr,
        )
        diagnostics = observed.get("source_diagnostics")
        if isinstance(diagnostics, list) and diagnostics:
            print("  source diagnostics:", file=sys.stderr)
            for diagnostic in diagnostics:
                print(f"    - {diagnostic}", file=sys.stderr)
            print(
                "  A revision difference alone is informational. Run "
                "platform-deploy only when platform-owned desired state must "
                "change.",
                file=sys.stderr,
            )
        print(file=sys.stderr)
    _print(status.environment_status)
    return 0 if not status.conflicts else 2


def _option_value(arguments: Sequence[str], option: str, default: str) -> str:
    try:
        index = arguments.index(option)
        value = arguments[index + 1]
    except (IndexError, ValueError):
        return default
    return value if value else default


def main(
    argv: Sequence[str] | None = None,
    *,
    operator_factory: Callable[[Path, str], LifecycleOperator] = _default_factory,
    preflight_factory: Callable[
        [Path, str], LifecycleOperator
    ] = _default_preflight_factory,
    integration_factory: Callable[
        [Path, str], ApplicationIntegrationLifecycle
    ] = _default_integration_factory,
    qualification_factory: Callable[
        [Path, str], QualificationLifecycle
    ] = _default_qualification_factory,
    destruction_factory: Callable[
        [Path, str], DestructionLifecycle
    ] = _default_destruction_factory,
    fixture_factory: Callable[[Path, str], object] = _default_fixture_factory,
    fixture_status_factory: Callable[[Path, str], object] = _default_fixture_status_factory,
    project_factory: Callable[[Path, str], object] = _default_project_factory,
) -> int:
    try:
        return _main(
            argv,
            operator_factory=operator_factory,
            preflight_factory=preflight_factory,
            integration_factory=integration_factory,
            qualification_factory=qualification_factory,
            destruction_factory=destruction_factory,
            fixture_factory=fixture_factory,
            fixture_status_factory=fixture_status_factory,
            project_factory=project_factory,
        )
    except Exception as error:
        arguments = list(argv) if argv is not None else sys.argv[1:]
        operation = arguments[0] if arguments else "unknown"
        environment = _option_value(arguments, "--environment", "unknown")
        source_authority = _option_value(
            arguments,
            "--source-authority",
            "accepted",
        )
        print("Unexpected operator error:", file=sys.stderr)
        print("  component: platform-operator", file=sys.stderr)
        print(f"  operation: {operation}", file=sys.stderr)
        print(f"  exception_type: {type(error).__name__}", file=sys.stderr)
        print("  code: OPERATOR_INTERNAL_ERROR", file=sys.stderr)
        print(file=sys.stderr)
        _print(
            {
                "blockers": ["OPERATOR_INTERNAL_ERROR"],
                "environment": environment,
                "operation": operation,
                "outcome": "failed",
                "source_authority": source_authority,
            }
        )
        return 2
