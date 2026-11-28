"""Install the exact AP-M7 Terraform toolchain into an ignored local cache."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = PROJECT_ROOT / ".cache" / "terraform"
BIN_ROOT = CACHE_ROOT / "bin"
TERRAFORM = BIN_ROOT / "terraform"
MIRROR_ROOT = CACHE_ROOT / "provider-mirror"
SETUP_CLI_CONFIG = CACHE_ROOT / "setup.tfrc"
OFFLINE_CLI_CONFIG = CACHE_ROOT / "offline.tfrc"
MANIFEST = CACHE_ROOT / "manifest.json"

TERRAFORM_VERSION = "1.17.2"
GOOGLE_PROVIDER_VERSION = "8.11.0"
GOOGLE_PROVIDER_SOURCE = "registry.terraform.io/hashicorp/google"
LOCK_PLATFORMS = ("darwin_arm64", "linux_amd64")
PLATFORM_ARCHIVES = {
    ("Darwin", "arm64"): (
        "darwin_arm64",
        "da0c7ef278a911347862758e7573a5907365e66485c2637cf5c217c5e227992e",
    ),
    ("Linux", "x86_64"): (
        "linux_amd64",
        "e6f16b2f0b137ee5729caa8c4e79a3bae4ee261acd198a1fcfa8584a6296605b",
    ),
}
ROOTS = (
    PROJECT_ROOT / "infrastructure" / "terraform" / "bootstrap",
    PROJECT_ROOT / "infrastructure" / "terraform" / "platform",
    PROJECT_ROOT
    / "infrastructure"
    / "terraform"
    / "fixtures"
    / "fixture-public",
    PROJECT_ROOT
    / "infrastructure"
    / "terraform"
    / "fixtures"
    / "fixture-authenticated",
    PROJECT_ROOT
    / "infrastructure"
    / "terraform"
    / "fixtures"
    / "fixture-multi-attachment",
    PROJECT_ROOT
    / "infrastructure"
    / "terraform"
    / "fixtures"
    / "fixture-restricted",
)

_CREDENTIAL_VARIABLES = {
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_BACKEND_CREDENTIALS",
    "GOOGLE_CREDENTIALS",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
}


def _platform() -> tuple[str, str]:
    key = (platform.system(), platform.machine())
    if key not in PLATFORM_ARCHIVES:
        supported = ", ".join(f"{system}/{machine}" for system, machine in PLATFORM_ARCHIVES)
        raise RuntimeError(f"unsupported setup platform {key[0]}/{key[1]}; expected {supported}")
    return PLATFORM_ARCHIVES[key]


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "comfforts-ap-m7-setup"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS URL
        return response.read()


def _write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _install_terraform() -> tuple[str, str, str]:
    terraform_platform, expected_digest = _platform()
    archive_name = f"terraform_{TERRAFORM_VERSION}_{terraform_platform}.zip"
    archive_url = f"https://releases.hashicorp.com/terraform/{TERRAFORM_VERSION}/{archive_name}"

    if TERRAFORM.is_file() and MANIFEST.is_file():
        observed = subprocess.run(
            [str(TERRAFORM), "version", "-json"],
            check=True,
            capture_output=True,
            text=True,
        )
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        recorded = manifest.get("terraform")
        binary_digest = hashlib.sha256(TERRAFORM.read_bytes()).hexdigest()
        if (
            json.loads(observed.stdout).get("terraform_version") == TERRAFORM_VERSION
            and isinstance(recorded, dict)
            and recorded.get("archive_sha256") == expected_digest
            and recorded.get("binary_sha256") == binary_digest
            and recorded.get("platform") == terraform_platform
        ):
            return terraform_platform, expected_digest, binary_digest

    payload = _download(archive_url)
    observed_digest = hashlib.sha256(payload).hexdigest()
    if observed_digest != expected_digest:
        raise RuntimeError(
            f"Terraform archive checksum mismatch: expected {expected_digest}, "
            f"observed {observed_digest}"
        )

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if Path(name).name == "terraform"]
        if names != ["terraform"]:
            raise RuntimeError(f"unexpected Terraform archive members: {archive.namelist()}")
        binary = archive.read("terraform")

    BIN_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=BIN_ROOT, delete=False) as temporary:
        temporary.write(binary)
        temporary_path = Path(temporary.name)
    temporary_path.chmod(
        stat.S_IRUSR
        | stat.S_IWUSR
        | stat.S_IXUSR
        | stat.S_IRGRP
        | stat.S_IXGRP
        | stat.S_IROTH
        | stat.S_IXOTH
    )
    temporary_path.replace(TERRAFORM)
    return terraform_platform, expected_digest, hashlib.sha256(binary).hexdigest()


def _lock_hashes() -> set[str]:
    locks = [root / ".terraform.lock.hcl" for root in ROOTS]
    missing = [lock.relative_to(PROJECT_ROOT).as_posix() for lock in locks if not lock.is_file()]
    if missing:
        raise RuntimeError(f"missing committed provider lock files: {', '.join(missing)}")

    lock_contents = [lock.read_text(encoding="utf-8") for lock in locks]
    if any(contents != lock_contents[0] for contents in lock_contents[1:]):
        raise RuntimeError("root provider lock files are not identical")

    contents = lock_contents[0]
    expected_fragments = (
        f'provider "{GOOGLE_PROVIDER_SOURCE}"',
        f'version     = "{GOOGLE_PROVIDER_VERSION}"',
        f'constraints = "{GOOGLE_PROVIDER_VERSION}"',
    )
    for fragment in expected_fragments:
        if fragment not in contents:
            raise RuntimeError(f"provider lock is missing {fragment!r}")

    hashes = {
        line.strip().removeprefix('"').removesuffix('",').removeprefix("zh:")
        for line in contents.splitlines()
        if line.strip().startswith('"zh:')
    }
    if not hashes:
        raise RuntimeError("provider lock contains no signed package checksums")
    return hashes


def _terraform_environment(cli_config: Path) -> dict[str, str]:
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
            "TF_CLI_CONFIG_FILE": str(cli_config),
            "TF_IN_AUTOMATION": "1",
        }
    )
    return environment


def _populate_provider_mirror(terraform_platform: str) -> str:
    signed_hashes = _lock_hashes()
    _write_text(
        SETUP_CLI_CONFIG,
        "provider_installation {\n"
        "  direct {\n"
        f'    include = ["{GOOGLE_PROVIDER_SOURCE}"]\n'
        "  }\n"
        "}\n"
        "disable_checkpoint = true\n",
    )

    if MIRROR_ROOT.exists():
        shutil.rmtree(MIRROR_ROOT)
    MIRROR_ROOT.mkdir(parents=True)
    with tempfile.TemporaryDirectory(
        prefix="apps-platform-provider-selection-"
    ) as selection_name:
        selection_root = Path(selection_name)
        shutil.copy2(ROOTS[0] / "versions.tf", selection_root / "versions.tf")
        shutil.copy2(
            ROOTS[0] / ".terraform.lock.hcl",
            selection_root / ".terraform.lock.hcl",
        )
        subprocess.run(
            [
                str(TERRAFORM),
                "providers",
                "mirror",
                f"-platform={terraform_platform}",
                str(MIRROR_ROOT),
            ],
            cwd=selection_root,
            env=_terraform_environment(SETUP_CLI_CONFIG),
            check=True,
        )

    packages = sorted(
        MIRROR_ROOT.rglob(
            f"terraform-provider-google_{GOOGLE_PROVIDER_VERSION}_{terraform_platform}.zip"
        )
    )
    if len(packages) != 1:
        relative = [path.relative_to(MIRROR_ROOT).as_posix() for path in packages]
        raise RuntimeError(f"expected one mirrored provider package, observed {relative}")
    provider_digest = hashlib.sha256(packages[0].read_bytes()).hexdigest()
    if provider_digest not in signed_hashes:
        raise RuntimeError("mirrored provider package does not match the committed signed lock")

    _write_text(
        OFFLINE_CLI_CONFIG,
        "provider_installation {\n"
        "  filesystem_mirror {\n"
        f"    path = {json.dumps(str(MIRROR_ROOT.resolve()))}\n"
        f'    include = ["{GOOGLE_PROVIDER_SOURCE}"]\n'
        "  }\n"
        "}\n"
        "disable_checkpoint = true\n",
    )
    return provider_digest


def setup(*, tool_only: bool = False) -> None:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    terraform_platform, terraform_archive_digest, terraform_binary_digest = _install_terraform()
    if tool_only:
        print(f"Terraform {TERRAFORM_VERSION} installed for {terraform_platform}")
        return

    provider_digest = _populate_provider_mirror(terraform_platform)
    manifest = {
        "google_provider": {
            "sha256": provider_digest,
            "source": GOOGLE_PROVIDER_SOURCE,
            "version": GOOGLE_PROVIDER_VERSION,
        },
        "lock_platforms": list(LOCK_PLATFORMS),
        "terraform": {
            "archive_sha256": terraform_archive_digest,
            "binary_sha256": terraform_binary_digest,
            "platform": terraform_platform,
            "version": TERRAFORM_VERSION,
        },
    }
    _write_text(MANIFEST, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        f"Terraform {TERRAFORM_VERSION} and {GOOGLE_PROVIDER_SOURCE} "
        f"{GOOGLE_PROVIDER_VERSION} synchronized for {terraform_platform}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tool-only",
        action="store_true",
        help="install the pinned Terraform CLI without populating the provider mirror",
    )
    arguments = parser.parse_args()
    setup(tool_only=arguments.tool_only)


if __name__ == "__main__":
    main()
