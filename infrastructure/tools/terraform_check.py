"""Validate the AP-M7 Terraform foundation offline in a disposable copy."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from infrastructure.tools import terraform_setup


PROJECT_ROOT = terraform_setup.PROJECT_ROOT
TERRAFORM_SOURCE = PROJECT_ROOT / "infrastructure" / "terraform"
CONFIG_SOURCE = PROJECT_ROOT / "infrastructure" / "config"

def _run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
    )
    combined_output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or re.search(
        r"(?im)^\s*warning:", combined_output
    ):
        rendered = " ".join(command)
        raise RuntimeError(
            f"command failed or warned in {cwd}: {rendered}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
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


def _write_offline_cli_configuration(destination: Path) -> Path:
    destination.write_text(
        "provider_installation {\n"
        "  filesystem_mirror {\n"
        f"    path = {json.dumps(str(terraform_setup.MIRROR_ROOT.resolve()))}\n"
        f'    include = ["{terraform_setup.GOOGLE_PROVIDER_SOURCE}"]\n'
        "  }\n"
        "}\n"
        "disable_checkpoint = true\n",
        encoding="utf-8",
    )
    return destination


def _environment(data_directory: Path, cli_config: Path) -> dict[str, str]:
    isolated_home = data_directory.parent / "home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    return {
        "CHECKPOINT_DISABLE": "1",
        "GCE_METADATA_HOST": "127.0.0.1:1",
        "HOME": str(isolated_home),
        "HTTP_PROXY": "http://127.0.0.1:1",
        "HTTPS_PROXY": "http://127.0.0.1:1",
        "NO_PROXY": "",
        "PATH": os.environ.get("PATH", ""),
        "TF_CLI_CONFIG_FILE": str(cli_config),
        "TF_DATA_DIR": str(data_directory),
        "TF_IN_AUTOMATION": "1",
        "TMPDIR": os.environ.get("TMPDIR", tempfile.gettempdir()),
        "XDG_CONFIG_HOME": str(isolated_home / ".config"),
    }


def _plan_only_test_files(root: Path) -> tuple[Path, ...]:
    test_directory = root / "tests"
    test_files = tuple(sorted(test_directory.glob("*.tftest.hcl")))
    if not test_files:
        raise RuntimeError(f"Terraform root has no mocked plan tests: {root}")

    for test_file in test_files:
        contents = test_file.read_text(encoding="utf-8")
        run_count = len(re.findall(r'(?m)^\s*run\s+"[^"]+"\s*\{', contents))
        plan_count = len(re.findall(r"(?m)^\s*command\s*=\s*plan\s*$", contents))
        if re.search(r"(?m)^\s*command\s*=\s*apply\s*$", contents):
            raise RuntimeError(f"apply-mode Terraform test is prohibited: {test_file}")
        if run_count == 0 or plan_count != run_count:
            raise RuntimeError(
                f"every Terraform test run must declare command = plan: {test_file}"
            )
        if not re.search(r'(?m)^\s*mock_provider\s+"google"\s*\{', contents):
            raise RuntimeError(f"Terraform test must mock the Google provider: {test_file}")

    return test_files


def validate_foundation() -> tuple[str, ...]:
    """Format, initialize, validate, and run plan-only mocked tests offline."""

    manifest = _manifest()
    _verify_local_dependencies(manifest)

    with tempfile.TemporaryDirectory(prefix="apps-platform-terraform-") as temporary_name:
        temporary = Path(temporary_name)
        copied_infrastructure = temporary / "infrastructure"
        copied = copied_infrastructure / "terraform"
        shutil.copytree(TERRAFORM_SOURCE, copied)
        shutil.copytree(CONFIG_SOURCE, copied_infrastructure / "config")
        offline_cli_config = _write_offline_cli_configuration(
            temporary / "offline.tfrc"
        )
        formatting_environment = _environment(
            temporary / "format-data", offline_cli_config
        )
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
            environment = _environment(
                temporary / "data" / str(index), offline_cli_config
            )
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
            _plan_only_test_files(copied_root)
            _run(
                [
                    str(terraform_setup.TERRAFORM),
                    "test",
                    "-no-color",
                    "-test-directory=tests",
                ],
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
