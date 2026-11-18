"""AP-M7-W3 versioned infrastructure-configuration contract checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from contracts.validation import ContractSchemaError
from infrastructure.config.validation import (
    EXAMPLE_DIRECTORY,
    SCHEMA_IDS,
    load_configuration_document,
    load_configuration_schemas,
    validate_configuration,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = PROJECT_ROOT / "infrastructure" / "config"
EXAMPLE_KINDS = {
    "backend.synthetic.v1.json": "backend",
    "cross-state-attachment-public.synthetic.v1.json": "cross-state-reference",
    "cross-state-attachment-restricted.synthetic.v1.json": "cross-state-reference",
    "cross-state-attachment.synthetic.v1.json": "cross-state-reference",
    "cross-state-backend.synthetic.v1.json": "cross-state-reference",
    "cross-state-platform.synthetic.v1.json": "cross-state-reference",
    "fixture-authenticated.synthetic.v1.json": "fixture",
    "fixture-public.synthetic.v1.json": "fixture",
    "fixture-restricted.synthetic.v1.json": "fixture",
    "platform.synthetic.v1.json": "platform",
    "workflow-apply.synthetic.v1.json": "workflow",
    "workflow-destroy.synthetic.v1.json": "workflow",
    "workflow-force-unlock.synthetic.v1.json": "workflow",
    "workflow-plan.synthetic.v1.json": "workflow",
    "workflow-rollback.synthetic.v1.json": "workflow",
}


def _example(name: str) -> dict[str, object]:
    value = json.loads((EXAMPLE_DIRECTORY / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _codes(violations: object) -> list[tuple[str, str]]:
    return [(item.code, item.path) for item in violations]  # type: ignore[attr-defined]


class InfrastructureConfigurationTest(unittest.TestCase):
    def test_exact_local_schema_registry_loads_without_remote_resolution(self) -> None:
        registry = load_configuration_schemas()

        self.assertEqual(set(registry), set(SCHEMA_IDS.values()))
        self.assertEqual(
            sorted(path.name for path in (CONFIG_ROOT / "schemas").glob("*.json")),
            sorted(
                (
                    "backend-configuration.v1.schema.json",
                    "cross-state-reference.v1.schema.json",
                    "fixture-configuration.v1.schema.json",
                    "operator-input-manifest.v1.schema.json",
                    "platform-configuration.v1.schema.json",
                    "workflow-configuration.v1.schema.json",
                )
            ),
        )

    def test_schema_profile_rejects_unreviewed_keywords_and_remote_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied = Path(temporary_directory) / "schemas"
            shutil.copytree(CONFIG_ROOT / "schemas", copied)
            target = copied / "backend-configuration.v1.schema.json"
            schema = json.loads(target.read_text(encoding="utf-8"))
            schema["properties"]["project_id"]["format"] = "hostname"
            target.write_text(json.dumps(schema), encoding="utf-8")
            with self.assertRaisesRegex(ContractSchemaError, "unsupported schema keyword"):
                load_configuration_schemas(copied)

            schema["properties"]["project_id"] = {
                "$ref": "https://schemas.example.invalid/project.json"
            }
            target.write_text(json.dumps(schema), encoding="utf-8")
            with self.assertRaisesRegex(ContractSchemaError, "unresolved or remote"):
                load_configuration_schemas(copied)

    def test_every_synthetic_example_is_valid_but_closed_to_operator_selection(self) -> None:
        self.assertEqual(
            sorted(path.name for path in EXAMPLE_DIRECTORY.glob("*.json")),
            sorted(EXAMPLE_KINDS),
        )
        for filename, kind in EXAMPLE_KINDS.items():
            with self.subTest(filename=filename):
                accepted = load_configuration_document(
                    EXAMPLE_DIRECTORY / filename,
                    kind,
                    allow_synthetic=True,
                )
                self.assertEqual(accepted.violations, ())
                self.assertIsNotNone(accepted.value)

                rejected = load_configuration_document(
                    EXAMPLE_DIRECTORY / filename,
                    kind,
                )
                self.assertIsNone(rejected.value)
                self.assertIn(
                    ("SYNTHETIC_CONFIGURATION_PROHIBITED", "/configuration_class"),
                    _codes(rejected.violations),
                )

    def test_duplicate_unknown_and_prohibited_material_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "duplicate.json"
            path.write_text(
                '{"contract_version":1,"contract_version":1}',
                encoding="utf-8",
            )
            result = load_configuration_document(path, "backend", allow_synthetic=True)
            self.assertEqual(_codes(result.violations), [("JSON_DUPLICATE_KEY", "/contract_version")])

        platform = _example("platform.synthetic.v1.json")
        platform["secret_value"] = "do-not-commit"
        violations = validate_configuration(platform, "platform", allow_synthetic=True)
        self.assertIn(("FIELD_UNKNOWN", "/secret_value"), _codes(violations))
        self.assertIn(("PROHIBITED_MATERIAL", "/secret_value"), _codes(violations))

        platform.pop("secret_value")
        platform["oauth_client_id"] = "terraform_remote_state.platform"
        violations = validate_configuration(platform, "platform", allow_synthetic=True)
        self.assertIn(("PROHIBITED_MATERIAL", "/oauth_client_id"), _codes(violations))

    def test_image_and_secret_references_are_immutable_and_versioned(self) -> None:
        fixture = _example("fixture-authenticated.synthetic.v1.json")
        fixture["image_digest"] = "us-west1-docker.pkg.dev/synthetic-platform/repo/app:latest"
        self.assertIn(
            ("FIELD_PATTERN", "/image_digest"),
            _codes(validate_configuration(fixture, "fixture", allow_synthetic=True)),
        )

        platform = _example("platform.synthetic.v1.json")
        platform["oauth_client_secret_version"] = (
            "projects/synthetic-platform/secrets/synthetic-oauth-secret/versions/latest"
        )
        self.assertIn(
            ("FIELD_PATTERN", "/oauth_client_secret_version"),
            _codes(validate_configuration(platform, "platform", allow_synthetic=True)),
        )

    def test_backend_policy_enforces_four_exclusive_state_owners(self) -> None:
        backend = _example("backend.synthetic.v1.json")
        buckets = backend["state_buckets"]
        assert isinstance(buckets, list)
        assert isinstance(buckets[1], dict)
        buckets[1]["owner_id"] = "fixture-restricted"
        buckets[1]["bucket_name"] = "synthetic-platform-state"

        violations = validate_configuration(backend, "backend", allow_synthetic=True)
        self.assertIn(("OWNER_CONFLICT", "/state_buckets"), _codes(violations))
        self.assertIn(("OWNER_CONFLICT", "/state_buckets/1/bucket_name"), _codes(violations))
        self.assertIn(("OWNER_CONFLICT", "/state_buckets/3/owner_id"), _codes(violations))

    def test_fixture_and_cross_state_ownership_remain_application_scoped(self) -> None:
        fixture = _example("fixture-public.synthetic.v1.json")
        fixture["admission_mode"] = "authenticated"
        fixture["service_name"] = "fixture-restricted"
        labels = fixture["labels"]
        assert isinstance(labels, dict)
        labels["application_id"] = "fixture-restricted"
        violations = validate_configuration(fixture, "fixture", allow_synthetic=True)
        self.assertIn(("CONFIGURATION_POLICY_INVALID", "/admission_mode"), _codes(violations))
        self.assertIn(("OWNER_CONFLICT", "/service_name"), _codes(violations))
        self.assertIn(("OWNER_CONFLICT", "/labels/application_id"), _codes(violations))

        reference = _example("cross-state-attachment.synthetic.v1.json")
        attachment = reference["reference"]
        assert isinstance(attachment, dict)
        attachment["owner_id"] = "fixture-restricted"
        attachment["resource_reference"] = (
            "urn:comfforts:app-platform:gcp:cloud-run:123456789012:us-west1:fixture-restricted"
        )
        violations = validate_configuration(
            reference,
            "cross-state-reference",
            allow_synthetic=True,
        )
        self.assertIn(("OWNER_CONFLICT", "/reference/owner_id"), _codes(violations))
        self.assertIn(("OWNER_CONFLICT", "/reference/resource_reference"), _codes(violations))

        attachment["owner_id"] = "fixture-authenticated"
        attachment["resource_reference"] = "https://fixture.example.invalid"
        violations = validate_configuration(
            reference,
            "cross-state-reference",
            allow_synthetic=True,
        )
        self.assertIn(("FIELD_PATTERN", "/reference/resource_reference"), _codes(violations))

        platform_reference = _example("cross-state-platform.synthetic.v1.json")
        platform = platform_reference["reference"]
        assert isinstance(platform, dict)
        platform["public_key_reference"] = (
            "https://other.example.invalid/.well-known/jwks.json"
        )
        violations = validate_configuration(
            platform_reference,
            "cross-state-reference",
            allow_synthetic=True,
        )
        self.assertIn(
            ("CONFIGURATION_POLICY_INVALID", "/reference/public_key_reference"),
            _codes(violations),
        )

    def test_workflow_policy_binds_subject_plan_and_destructive_target(self) -> None:
        workflow = _example("workflow-destroy.synthetic.v1.json")
        workflow["protected_subject"] = (
            "repo:comfforts/other:environment:synthetic-ap-m8"
        )
        workflow["plan_digest"] = None
        destructive = workflow["destructive_target"]
        assert isinstance(destructive, dict)
        destructive["operation"] = "force-unlock"
        destructive["root_target"] = "platform"

        violations = validate_configuration(workflow, "workflow", allow_synthetic=True)
        self.assertIn(
            ("CONFIGURATION_POLICY_INVALID", "/protected_subject"),
            _codes(violations),
        )
        self.assertIn(("CONFIGURATION_POLICY_INVALID", "/plan_digest"), _codes(violations))
        self.assertIn(
            ("CONFIGURATION_POLICY_INVALID", "/destructive_target/operation"),
            _codes(violations),
        )
        self.assertIn(
            ("OWNER_CONFLICT", "/destructive_target/root_target"),
            _codes(violations),
        )

    def test_changing_only_the_class_cannot_make_an_example_operational(self) -> None:
        for filename, kind in EXAMPLE_KINDS.items():
            with self.subTest(filename=filename):
                value = _example(filename)
                value["configuration_class"] = "operator"
                violations = validate_configuration(value, kind)
                self.assertIn("CONFIGURATION_POLICY_INVALID", {item.code for item in violations})

    def test_w8_adds_only_the_approved_platform_and_fixture_resources(self) -> None:
        terraform_root = PROJECT_ROOT / "infrastructure" / "terraform"
        terraform_files = sorted(
            path.relative_to(terraform_root).as_posix()
            for path in terraform_root.rglob("*.tf")
        )
        self.assertEqual(
            terraform_files,
            sorted(
                (
                    "bootstrap/main.tf",
                    "bootstrap/outputs.tf",
                    "bootstrap/variables.tf",
                    "bootstrap/versions.tf",
                    "fixtures/fixture-authenticated/backend.tf",
                    "fixtures/fixture-authenticated/main.tf",
                    "fixtures/fixture-authenticated/outputs.tf",
                    "fixtures/fixture-authenticated/variables.tf",
                    "fixtures/fixture-authenticated/versions.tf",
                    "fixtures/fixture-public/backend.tf",
                    "fixtures/fixture-public/main.tf",
                    "fixtures/fixture-public/outputs.tf",
                    "fixtures/fixture-public/variables.tf",
                    "fixtures/fixture-public/versions.tf",
                    "fixtures/fixture-restricted/backend.tf",
                    "fixtures/fixture-restricted/main.tf",
                    "fixtures/fixture-restricted/outputs.tf",
                    "fixtures/fixture-restricted/variables.tf",
                    "fixtures/fixture-restricted/versions.tf",
                    "modules/fixture-application/main.tf",
                    "modules/fixture-application/outputs.tf",
                    "modules/fixture-application/variables.tf",
                    "modules/platform-foundation/main.tf",
                    "modules/platform-foundation/outputs.tf",
                    "modules/platform-foundation/variables.tf",
                    "modules/platform-controls/main.tf",
                    "modules/platform-controls/outputs.tf",
                    "modules/platform-controls/variables.tf",
                    "modules/shared-edge/main.tf",
                    "modules/shared-edge/outputs.tf",
                    "modules/shared-edge/variables.tf",
                    "modules/state-bucket/main.tf",
                    "modules/state-bucket/outputs.tf",
                    "modules/state-bucket/variables.tf",
                    "platform/backend.tf",
                    "platform/main.tf",
                    "platform/outputs.tf",
                    "platform/variables.tf",
                    "platform/versions.tf",
                )
            ),
        )
        bootstrap = "\n".join(
            (terraform_root / relative_path).read_text(encoding="utf-8")
            for relative_path in terraform_files
            if relative_path.startswith("bootstrap/")
        )
        self.assertNotIn('backend "', bootstrap)

        platform_backend = (terraform_root / "platform/backend.tf").read_text(
            encoding="utf-8"
        )
        self.assertEqual(platform_backend.count('backend "gcs" {}'), 1)
        self.assertNotIn("bucket", platform_backend)
        self.assertNotIn("prefix", platform_backend)

        for application_id in (
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
        ):
            root = terraform_root / "fixtures" / application_id
            backend = (root / "backend.tf").read_text(encoding="utf-8")
            self.assertEqual(backend.count('backend "gcs" {}'), 1)
            self.assertNotIn("bucket", backend)
            self.assertNotIn("prefix", backend)

    def test_configuration_layer_runs_unchanged_from_an_extracted_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            extracted = Path(temporary_directory) / "apps-platform"
            (extracted / "contracts").mkdir(parents=True)
            shutil.copy2(PROJECT_ROOT / "contracts/__init__.py", extracted / "contracts/__init__.py")
            shutil.copy2(PROJECT_ROOT / "contracts/validation.py", extracted / "contracts/validation.py")
            shutil.copytree(CONFIG_ROOT, extracted / "infrastructure/config")
            (extracted / "infrastructure/__init__.py").write_text("", encoding="utf-8")
            before = {
                path.relative_to(extracted): path.read_bytes()
                for path in extracted.rglob("*")
                if path.is_file()
            }
            program = "\n".join(
                (
                    "from pathlib import Path",
                    "from infrastructure.config import load_configuration_document",
                    "path = Path('infrastructure/config/examples/backend.synthetic.v1.json')",
                    "result = load_configuration_document(path, 'backend', allow_synthetic=True)",
                    "assert result.violations == ()",
                )
            )
            completed = subprocess.run(
                [sys.executable, "-c", program],
                cwd=extracted,
                env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(extracted)},
                check=False,
                capture_output=True,
                text=True,
            )
            after = {
                path.relative_to(extracted): path.read_bytes()
                for path in extracted.rglob("*")
                if path.is_file()
            }

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
