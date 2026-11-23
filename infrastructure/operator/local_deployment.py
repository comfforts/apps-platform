"""Private deterministic inputs for the human-operated staging deployment."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from contracts import (
    compile_registration_set,
    load_json_bytes,
    validate_contract_instance,
)
from infrastructure.backend import PhasePlanRequest, backend_declarations
from infrastructure.config import validate_configuration
from infrastructure.operator._interfaces import StageContext


_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_SOURCE_REVISION = re.compile(r"[0-9a-f]{40}")
_BILLING_ACCOUNT = re.compile(
    r"billingAccounts/[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}"
)
_EMAIL = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
)
_SUBJECT = re.compile(r"[1-9][0-9]{5,63}")
_PHASE_SOURCES = {
    "bootstrap": "infrastructure/terraform/bootstrap",
    "platform-foundation": "infrastructure/terraform/platform",
    "shared-edge": "infrastructure/terraform/platform",
    "fixture-public": "infrastructure/terraform/fixtures/fixture-public",
    "fixture-authenticated": (
        "infrastructure/terraform/fixtures/fixture-authenticated"
    ),
    "fixture-restricted": "infrastructure/terraform/fixtures/fixture-restricted",
}
_PLATFORM_PHASES = {"bootstrap", "platform-foundation", "shared-edge"}
_FOUNDATION_NAMES = {
    "configuration_bucket": "comfforts-ap-stg-455651441682-configuration",
    "log_bucket": "comfforts-ap-stg-455651441682-logs",
    "evidence_bucket": "comfforts-ap-stg-455651441682-evidence",
    "artifact_repository_id": "app-platform-images",
    "oauth_secret_id": "app-platform-edge-oauth",
    "signing_key_ring_id": "app-platform",
    "signing_key_id": "edge-signing",
}


class LocalDeploymentInputError(RuntimeError):
    """A safe blocker raised before Terraform or provider mutation."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(contents: bytes) -> str:
    return f"sha256:{hashlib.sha256(contents).hexdigest()}"


def _private_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, name = tempfile.mkstemp(prefix=".deployment-", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        path.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _object(value: str, code: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise LocalDeploymentInputError(code) from error
    if not isinstance(parsed, dict):
        raise LocalDeploymentInputError(code)
    return parsed


@dataclass(frozen=True, slots=True)
class OperatorSessionFacts:
    """Provider facts derived from the already verified active human session."""

    active_account: str
    billing_account_reference: str
    operator_issuer: str
    operator_subject: str

    def __post_init__(self) -> None:
        if (
            _EMAIL.fullmatch(self.active_account) is None
            or _BILLING_ACCOUNT.fullmatch(self.billing_account_reference) is None
            or self.operator_issuer != "https://accounts.google.com"
            or _SUBJECT.fullmatch(self.operator_subject) is None
        ):
            raise ValueError("invalid verified operator session facts")


@dataclass(frozen=True, slots=True)
class InitialGeneration:
    """Closed first Registration Generation and its immutable object binding."""

    registration_set: dict[str, Any]
    compiled_configuration: dict[str, Any]
    ownership_manifest: dict[str, Any]
    generation_digest: str
    content_digest: str
    object_name: str
    contents: bytes

    def reference(self, object_generation: int) -> str:
        if object_generation < 1:
            raise ValueError("object generation must be positive")
        return _canonical(
            {
                "content_digest": self.content_digest,
                "generation": 1,
                "generation_digest": self.generation_digest,
                "object_generation": object_generation,
                "object_name": self.object_name,
            }
        ).decode("utf-8")


def existing_initial_generation_reference(
    contents: bytes,
    object_generation: int,
) -> str:
    """Validate and bind an existing immutable empty Registration Generation."""

    if object_generation < 1:
        raise LocalDeploymentInputError("INITIAL_GENERATION_READBACK_INVALID")
    loaded = load_json_bytes(contents, max_bytes=1_048_576)
    configuration = loaded.value
    if (
        loaded.violations
        or not isinstance(configuration, dict)
        or validate_contract_instance(
            configuration,
            "urn:comfforts:app-platform:schema:compiled-shared-edge:v1",
        )
        or configuration.get("generation") != 1
        or configuration.get("previous_generation_digest") is not None
        or configuration.get("application_states") != []
        or configuration.get("catalogue") != []
        or configuration.get("routes") != []
        or configuration.get("admission_policies") != []
        or configuration.get("reserved_paths")
        != ["/", "/.well-known", "/_platform"]
        or configuration.get("identity_delivery")
        != {
            "context_contract_version": 1,
            "header_name": "X-Comfforts-Verified-Identity",
        }
        or not isinstance(configuration.get("generation_digest"), str)
        or _DIGEST.fullmatch(str(configuration["generation_digest"])) is None
    ):
        raise LocalDeploymentInputError("INITIAL_GENERATION_READBACK_INVALID")
    return _canonical(
        {
            "content_digest": _digest(contents),
            "generation": 1,
            "generation_digest": configuration["generation_digest"],
            "object_generation": object_generation,
            "object_name": "generations/1/compiled.json",
        }
    ).decode("utf-8")


def initial_generation(source_revision: str) -> InitialGeneration:
    """Compile the deterministic empty generation served before application registration."""

    if _SOURCE_REVISION.fullmatch(source_revision) is None:
        raise ValueError("source revision must be a full Git object identifier")
    registration_set = {
        "contract_version": 1,
        "generation": 1,
        "previous_generation_digest": None,
        "proposal": {
            "source_revision": source_revision,
            "change_summary": "Initialize the closed App Platform catalogue",
        },
        "registrations": [],
    }
    result = compile_registration_set(
        None,
        registration_set,
        {
            "contract_version": 1,
            "enabled_attachment_adapter_kinds": ["gcp-cloud-run-v1"],
        },
    )
    if (
        result.violations
        or result.compiled_configuration is None
        or result.ownership_manifest is None
        or result.generation_digest is None
    ):
        raise LocalDeploymentInputError("INITIAL_GENERATION_INVALID")
    contents = _canonical(result.compiled_configuration)
    return InitialGeneration(
        registration_set=registration_set,
        compiled_configuration=result.compiled_configuration,
        ownership_manifest=result.ownership_manifest,
        generation_digest=result.generation_digest,
        content_digest=_digest(contents),
        object_name="generations/1/compiled.json",
        contents=contents,
    )


class PrivateTerraformWorkspace:
    """Copy only reviewed Terraform source into one mode-private working tree."""

    def __init__(self, project_root: Path, working_root: Path) -> None:
        self._project_root = project_root.resolve()
        self._working_root = working_root.resolve()
        self._working_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._working_root.chmod(0o700)
        if self._working_root.is_symlink() or self._project_root == self._working_root:
            raise ValueError("deployment workspace is not isolated")

    @staticmethod
    def _copy(source: Path, destination: Path) -> None:
        if source.is_symlink() or not source.is_file():
            raise LocalDeploymentInputError("TERRAFORM_SOURCE_INVALID")
        contents = source.read_bytes()
        if destination.exists() and destination.read_bytes() == contents:
            destination.chmod(0o600)
            return
        _private_write(destination, contents)

    def _copy_directory(self, source: Path, destination: Path) -> None:
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.chmod(0o700)
        for path in sorted(source.iterdir()):
            if path.is_symlink():
                raise LocalDeploymentInputError("TERRAFORM_SOURCE_INVALID")
            if path.is_dir():
                self._copy_directory(path, destination / path.name)
            elif path.suffix == ".tf" or path.name == ".terraform.lock.hcl":
                self._copy(path, destination / path.name)

    def prepare_phase(self, phase: str) -> Path:
        try:
            relative_source = _PHASE_SOURCES[phase]
        except KeyError as error:
            raise LocalDeploymentInputError("TERRAFORM_PHASE_UNAVAILABLE") from error
        source = self._project_root / relative_source
        destination = self._working_root / phase
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.chmod(0o700)
        for path in sorted(source.iterdir()):
            if path.name == "backend.tf":
                continue
            if path.is_file() and (
                path.suffix == ".tf" or path.name == ".terraform.lock.hcl"
            ):
                self._copy(path, destination / path.name)
        modules = self._project_root / "infrastructure/terraform/modules"
        relative_modules = Path(os.path.relpath(modules, start=source))
        module_destination = (destination / relative_modules).resolve()
        workspace_boundary = self._working_root.parent.resolve()
        if (
            module_destination == workspace_boundary
            or workspace_boundary not in module_destination.parents
        ):
            raise LocalDeploymentInputError("TERRAFORM_SOURCE_INVALID")
        self._copy_directory(modules, module_destination)
        return destination


@dataclass(frozen=True, slots=True)
class RenderedTerraformInput:
    terraform_root: Path
    variable_file: Path
    configuration_digest: str


def render_private_terraform_input(
    terraform_root: Path,
    variables: dict[str, Any],
) -> RenderedTerraformInput:
    """Write one canonical, mode-private variable file in an isolated root."""

    contents = _canonical(variables) + b"\n"
    variable_file = terraform_root / "terraform.tfvars.json"
    _private_write(variable_file, contents)
    return RenderedTerraformInput(
        terraform_root,
        variable_file,
        _digest(contents),
    )


class DeploymentConfigurationRenderer:
    """Derive complete Terraform phase values without an operator manifest."""

    def __init__(
        self,
        project_root: Path,
        working_root: Path,
        session: OperatorSessionFacts,
    ) -> None:
        self._workspace = PrivateTerraformWorkspace(project_root, working_root)
        self._working_root = working_root.resolve()
        self._session = session

    @staticmethod
    def _inputs(context: StageContext) -> dict[str, str]:
        return dict(context.inputs)

    def _backend(self) -> dict[str, Any]:
        declarations = backend_declarations("staging")
        unique: dict[str, dict[str, str]] = {}
        for declaration in declarations:
            unique.setdefault(
                declaration.owner_id,
                {
                    "state_owner": declaration.state_owner,
                    "owner_id": declaration.owner_id,
                    "bucket_name": declaration.bucket,
                    "backend_prefix": (
                        "platform"
                        if declaration.owner_id == "app-platform"
                        else declaration.prefix
                    ),
                },
            )
        return {
            "contract_version": 1,
            "configuration_kind": "backend",
            "configuration_class": "operator",
            "project_id": "comfforts-platform-non-prod",
            "region": "us-west1",
            "state_buckets": [unique[name] for name in sorted(unique)],
            "recovery_policy": {
                "noncurrent_version_retention_days": 90,
                "newer_versions_to_retain": 20,
            },
        }

    def _foundation(self) -> dict[str, Any]:
        return {
            "project_id": "comfforts-platform-non-prod",
            "project_number": "455651441682",
            "region": "us-west1",
            "hostname": "apps-staging.comfforts.com",
            "state_owner": "platform",
            **_FOUNDATION_NAMES,
            "billing_account_reference": self._session.billing_account_reference,
            "notification_email": self._session.active_account,
        }

    def _platform(
        self,
        context: StageContext,
        phase: str,
        *,
        preserve_shared_edge_tls: bool = False,
    ) -> dict[str, Any]:
        shared_edge: dict[str, Any] | None = None
        if phase == "shared-edge":
            inputs = self._inputs(context)
            try:
                foundation_reference = _object(
                    inputs["foundation.foundation-reference"],
                    "FOUNDATION_REFERENCE_INVALID",
                )
                generation = _object(
                    inputs["generation-publish.registration-generation-reference"],
                    "REGISTRATION_GENERATION_REFERENCE_INVALID",
                )
                signing_key_version = foundation_reference["signing_key_version"]
                shared_edge = {
                    "edge_image_digest": inputs[
                        "image-publish.shared-edge-image-digest"
                    ],
                    "oauth_client_id": inputs[
                        "oauth-configuration.oauth-client-id"
                    ],
                    "oauth_client_secret_version": inputs[
                        "oauth-configuration.oauth-secret-version"
                    ],
                    "signing_key_version": signing_key_version,
                    "operator_identity": {
                        "issuer": self._session.operator_issuer,
                        "subject": self._session.operator_subject,
                    },
                    "registration_generation": {
                        "source_revision": context.source_revision,
                        **generation,
                    },
                    "tls_enabled": (
                        context.stage["stage_id"] == "tls-readiness"
                        or preserve_shared_edge_tls
                    ),
                }
            except (KeyError, TypeError) as error:
                raise LocalDeploymentInputError(
                    "SHARED_EDGE_INPUT_INCOMPLETE"
                ) from error
        return {
            "contract_version": 2,
            "configuration_kind": "platform",
            "configuration_class": "operator",
            "phase": "foundation" if phase == "platform-foundation" else "shared-edge",
            "destruction_mode": "none",
            "repository": "comfforts/apps-platform",
            "environment": "staging",
            "foundation": self._foundation(),
            "shared_edge": shared_edge,
            "labels": {
                "environment": "staging",
                "managed_by": "terraform",
                "state_owner": "platform",
            },
        }

    def render_transition(
        self,
        request: PhasePlanRequest,
        destruction_mode: str,
        deployed_outputs: dict[str, str],
    ) -> RenderedTerraformInput:
        """Render one closed Platform State destruction transition."""

        allowed = {
            "none": "platform-foundation",
            "shared-edge-unlock": "shared-edge",
            "shared-edge-remove": "shared-edge",
            "platform-unlock": "platform-foundation",
            "retained": "platform-foundation",
        }
        if (
            request.environment != "staging"
            or allowed.get(destruction_mode) != request.phase
            or request.state_owner != "platform"
            or request.owner_id != "app-platform"
        ):
            raise LocalDeploymentInputError("DESTRUCTION_TRANSITION_INVALID")
        root = self._workspace.prepare_phase(request.phase)
        if request.backend_path.resolve() != (root / "backend.tf").resolve():
            raise LocalDeploymentInputError("TERRAFORM_BACKEND_PATH_MISMATCH")

        shared_edge: dict[str, Any] | None = None
        phase = "foundation"
        if destruction_mode == "shared-edge-unlock":
            phase = "shared-edge"
            try:
                foundation = _object(
                    deployed_outputs["foundation-reference"],
                    "FOUNDATION_REFERENCE_INVALID",
                )
                generation = _object(
                    deployed_outputs["registration-generation-reference"],
                    "REGISTRATION_GENERATION_REFERENCE_INVALID",
                )
                signing_key_version = foundation["signing_key_version"]
                shared_edge = {
                    "edge_image_digest": deployed_outputs["shared-edge-image-digest"],
                    "oauth_client_id": deployed_outputs["oauth-client-id"],
                    "oauth_client_secret_version": deployed_outputs[
                        "oauth-secret-version"
                    ],
                    "signing_key_version": signing_key_version,
                    "operator_identity": {
                        "issuer": self._session.operator_issuer,
                        "subject": self._session.operator_subject,
                    },
                    "registration_generation": {
                        "source_revision": request.source_revision,
                        **generation,
                    },
                    "tls_enabled": True,
                }
            except (KeyError, TypeError) as error:
                raise LocalDeploymentInputError(
                    "DESTRUCTION_DEPLOYMENT_BINDING_INCOMPLETE"
                ) from error
        configuration = {
            "contract_version": 2,
            "configuration_kind": "platform",
            "configuration_class": "operator",
            "phase": phase,
            "destruction_mode": destruction_mode,
            "repository": "comfforts/apps-platform",
            "environment": "staging",
            "foundation": self._foundation(),
            "shared_edge": shared_edge,
            "labels": {
                "environment": "staging",
                "managed_by": "terraform",
                "state_owner": "platform",
            },
        }
        if validate_configuration(configuration, "platform"):
            raise LocalDeploymentInputError("TERRAFORM_CONFIGURATION_INVALID")
        return render_private_terraform_input(
            root,
            {"platform_configuration": configuration},
        )

    def render(
        self,
        context: StageContext,
        request: PhasePlanRequest,
        *,
        preserve_shared_edge_tls: bool = False,
    ) -> RenderedTerraformInput:
        if context.environment != "staging" or request.environment != "staging":
            raise LocalDeploymentInputError("OWNERSHIP_TRANSFER_REQUIRED")
        if (
            request.source_revision != context.source_revision
            or request.phase not in _PLATFORM_PHASES
            or (
                preserve_shared_edge_tls
                and (
                    request.phase != "shared-edge"
                    or context.stage.get("stage_id") != "shared-edge"
                )
            )
        ):
            raise LocalDeploymentInputError("TERRAFORM_CONTEXT_MISMATCH")
        root = self._workspace.prepare_phase(request.phase)
        if request.backend_path.resolve() != (root / "backend.tf").resolve():
            raise LocalDeploymentInputError("TERRAFORM_BACKEND_PATH_MISMATCH")

        if request.phase == "bootstrap":
            kind = "backend"
            variable_name = "backend_configuration"
            configuration = self._backend()
        else:
            kind = "platform"
            variable_name = "platform_configuration"
            configuration = self._platform(
                context,
                request.phase,
                preserve_shared_edge_tls=preserve_shared_edge_tls,
            )
        violations = validate_configuration(configuration, kind)
        if violations:
            raise LocalDeploymentInputError("TERRAFORM_CONFIGURATION_INVALID")
        return render_private_terraform_input(
            root,
            {variable_name: configuration},
        )


__all__ = (
    "DeploymentConfigurationRenderer",
    "InitialGeneration",
    "LocalDeploymentInputError",
    "OperatorSessionFacts",
    "PrivateTerraformWorkspace",
    "RenderedTerraformInput",
    "initial_generation",
    "render_private_terraform_input",
)
