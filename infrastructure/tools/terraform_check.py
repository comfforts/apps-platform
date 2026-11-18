"""Validate the AP-M7 Terraform foundation offline in a disposable copy."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from infrastructure.tools import terraform_setup


PROJECT_ROOT = terraform_setup.PROJECT_ROOT
TERRAFORM_SOURCE = PROJECT_ROOT / "infrastructure" / "terraform"

_CREDENTIAL_VARIABLES = {
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_BACKEND_CREDENTIALS",
    "GOOGLE_CREDENTIALS",
    "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT",
    "GOOGLE_OAUTH_ACCESS_TOKEN",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
}


def _run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        rendered = " ".join(command)
        raise RuntimeError(
            f"command failed in {cwd}: {rendered}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _manifest() -> dict[str, object]:
    if not terraform_setup.MANIFEST.is_file():
        raise RuntimeError("Terraform dependencies are missing; run `make terraform-setup`")
    manifest = json.loads(terraform_setup.MANIFEST.read_text(encoding="utf-8"))
    terraform = manifest.get("terraform")
    provider = manifest.get("google_provider")
    if not isinstance(terraform, dict) or terraform.get("version") != terraform_setup.TERRAFORM_VERSION:
        raise RuntimeError("Terraform setup manifest does not match the approved CLI version")
    if not isinstance(provider, dict) or provider.get("version") != terraform_setup.GOOGLE_PROVIDER_VERSION:
        raise RuntimeError("Terraform setup manifest does not match the approved provider version")
    return manifest


def _verify_local_dependencies(manifest: dict[str, object]) -> None:
    version = subprocess.run(
        [str(terraform_setup.TERRAFORM), "version", "-json"],
        check=True,
        capture_output=True,
        text=True,
    )
    if json.loads(version.stdout).get("terraform_version") != terraform_setup.TERRAFORM_VERSION:
        raise RuntimeError("project-local Terraform binary is not the approved version")
    terraform = manifest["terraform"]
    assert isinstance(terraform, dict)
    if hashlib.sha256(terraform_setup.TERRAFORM.read_bytes()).hexdigest() != terraform.get(
        "binary_sha256"
    ):
        raise RuntimeError("project-local Terraform binary does not match its setup manifest")

    provider = manifest["google_provider"]
    assert isinstance(provider, dict)
    expected_digest = provider.get("sha256")
    packages = sorted(
        terraform_setup.MIRROR_ROOT.rglob(
            f"terraform-provider-google_{terraform_setup.GOOGLE_PROVIDER_VERSION}_*.zip"
        )
    )
    matching = [
        package
        for package in packages
        if hashlib.sha256(package.read_bytes()).hexdigest() == expected_digest
    ]
    if len(matching) != 1:
        raise RuntimeError("offline provider mirror does not match its setup manifest")
    if not terraform_setup.OFFLINE_CLI_CONFIG.is_file():
        raise RuntimeError("offline Terraform CLI configuration is missing")


def _environment(data_directory: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for variable in tuple(environment):
        if variable.startswith(("TF_TOKEN_", "TF_CLI_ARGS")):
            environment.pop(variable)
    for variable in _CREDENTIAL_VARIABLES:
        environment.pop(variable, None)
    environment.pop("TF_PLUGIN_CACHE_DIR", None)
    environment.update(
        {
            "CHECKPOINT_DISABLE": "1",
            "GCE_METADATA_HOST": "127.0.0.1:1",
            "HTTP_PROXY": "http://127.0.0.1:1",
            "HTTPS_PROXY": "http://127.0.0.1:1",
            "NO_PROXY": "",
            "TF_CLI_CONFIG_FILE": str(terraform_setup.OFFLINE_CLI_CONFIG),
            "TF_DATA_DIR": str(data_directory),
            "TF_IN_AUTOMATION": "1",
        }
    )
    return environment


def validate_foundation() -> tuple[str, ...]:
    """Format, initialize without a backend, and validate every root offline."""

    manifest = _manifest()
    _verify_local_dependencies(manifest)

    with tempfile.TemporaryDirectory(prefix="apps-platform-terraform-") as temporary_name:
        temporary = Path(temporary_name)
        copied = temporary / "terraform"
        shutil.copytree(TERRAFORM_SOURCE, copied)
        formatting_environment = _environment(temporary / "format-data")
        _run(
            [
                str(terraform_setup.TERRAFORM),
                "fmt",
                "-check",
                "-recursive",
                "-no-color",
            ],
            cwd=copied,
            environment=formatting_environment,
        )

        validated: list[str] = []
        for index, source_root in enumerate(terraform_setup.ROOTS):
            relative = source_root.relative_to(TERRAFORM_SOURCE)
            copied_root = copied / relative
            environment = _environment(temporary / "data" / str(index))
            _run(
                [
                    str(terraform_setup.TERRAFORM),
                    "init",
                    "-backend=false",
                    "-input=false",
                    "-lockfile=readonly",
                    "-no-color",
                ],
                cwd=copied_root,
                environment=environment,
            )
            _run(
                [str(terraform_setup.TERRAFORM), "validate", "-no-color"],
                cwd=copied_root,
                environment=environment,
            )
            validated.append(relative.as_posix())

        if list(temporary.rglob("*.tfstate")) or list(temporary.rglob("*.tfplan")):
            raise RuntimeError("offline foundation validation created state or a saved plan")

    return tuple(validated)


def main() -> None:
    validated = validate_foundation()
    print(f"Validated {len(validated)} Terraform roots offline: {', '.join(validated)}")


if __name__ == "__main__":
    main()
