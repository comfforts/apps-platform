"""AP-M7 and AP-M8 versioned infrastructure-configuration contract checks."""

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
    load_operator_manifest_chain,
    validate_configuration,
    validate_operator_manifest_chain,
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
    "operator-input-manifest.synthetic.v1.json": "operator-input-manifest",
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


def _manifest() -> dict[str, object]:
    return _example("operator-input-manifest.synthetic.v1.json")


def _successor(
    predecessor: dict[str, object],
    predecessor_digest: str,
) -> dict[str, object]:
    successor = copy.deepcopy(predecessor)
    successor["revision"] = 2
    successor["predecessor_manifest_digest"] = predecessor_digest
    successor["approval_reference"] = "owner-approval:synthetic-ap-m8-w2-revision-2"
    source = successor["source"]
    assert isinstance(source, dict)
    source["source_revision"] = "1" * 40
    resources = successor["platform_resources"]
    assert isinstance(resources, dict)
    resources["evidence_bundle_prefix"] = (
        f"ap-eval-m8/{'1' * 40}/synthetic-evaluation/"
    )
    successor["generated_facts"] = [
        {
            "fact_kind": "image-digest",
            "target_id": "shared-edge",
            "value": (
                "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
                f"synthetic-platform/shared-edge@sha256:{'a' * 64}"
            ),
        }
    ]
    return successor


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

    def test_operator_manifest_chain_accepts_one_initial_and_one_successor_revision(
        self,
    ) -> None:
        initial = _manifest()
        initial_result = validate_operator_manifest_chain(
            [initial],
            allow_synthetic=True,
        )
        self.assertEqual(initial_result.violations, ())
        self.assertIsNotNone(initial_result.values)
        self.assertEqual(len(initial_result.digests), 1)
        self.assertRegex(initial_result.digests[0], r"^sha256:[0-9a-f]{64}$")

        successor = _successor(initial, initial_result.digests[0])
        chain = validate_operator_manifest_chain(
            [initial, successor],
            allow_synthetic=True,
        )
        self.assertEqual(chain.violations, ())
        self.assertIsNotNone(chain.values)
        self.assertEqual(len(chain.digests), 2)
        self.assertNotEqual(chain.digests[0], chain.digests[1])

    def test_operator_manifest_digest_normalizes_closed_set_like_inputs(self) -> None:
        original = _manifest()
        reordered = copy.deepcopy(original)
        state = reordered["state"]
        assert isinstance(state, dict)
        buckets = state["buckets"]
        lineages = state["lineages"]
        assert isinstance(buckets, list)
        assert isinstance(lineages, list)
        buckets.reverse()
        lineages.reverse()
        registration = reordered["registration_inputs"]
        assert isinstance(registration, dict)
        applications = registration["application_ids"]
        assert isinstance(applications, list)
        applications.reverse()

        first = validate_operator_manifest_chain([original], allow_synthetic=True)
        second = validate_operator_manifest_chain([reordered], allow_synthetic=True)
        self.assertEqual(first.violations, ())
        self.assertEqual(second.violations, ())
        self.assertEqual(first.digests, second.digests)

    def test_operator_manifest_chain_rejects_predecessor_mutation_and_stale_approval(
        self,
    ) -> None:
        initial = _manifest()
        initial_result = validate_operator_manifest_chain(
            [initial],
            allow_synthetic=True,
        )
        successor = _successor(initial, initial_result.digests[0])
        successor["predecessor_manifest_digest"] = f"sha256:{'b' * 64}"
        successor["approval_reference"] = initial["approval_reference"]
        resources = successor["platform_resources"]
        assert isinstance(resources, dict)
        resources["log_bucket"] = "synthetic-replaced-log-bucket"

        violations = validate_operator_manifest_chain(
            [initial, successor],
            allow_synthetic=True,
        ).violations
        codes = _codes(violations)
        self.assertIn(
            ("MANIFEST_CHAIN_INVALID", "/revisions/1/predecessor_manifest_digest"),
            codes,
        )
        self.assertIn(
            ("MANIFEST_CHAIN_INVALID", "/revisions/1/approval_reference"),
            codes,
        )
        self.assertIn(("MANIFEST_CHAIN_INVALID", "/revisions/1"), codes)

    def test_operator_manifest_successor_must_append_and_preserve_generated_facts(
        self,
    ) -> None:
        initial = _manifest()
        initial_result = validate_operator_manifest_chain(
            [initial],
            allow_synthetic=True,
        )
        successor = _successor(initial, initial_result.digests[0])
        accepted = validate_operator_manifest_chain(
            [initial, successor],
            allow_synthetic=True,
        )
        replacement = copy.deepcopy(successor)
        replacement["revision"] = 3
        replacement["predecessor_manifest_digest"] = accepted.digests[1]
        replacement["approval_reference"] = "owner-approval:synthetic-ap-m8-w2-revision-3"
        source = replacement["source"]
        assert isinstance(source, dict)
        source["source_revision"] = "2" * 40
        resources = replacement["platform_resources"]
        assert isinstance(resources, dict)
        resources["evidence_bundle_prefix"] = (
            f"ap-eval-m8/{'2' * 40}/synthetic-evaluation/"
        )
        facts = replacement["generated_facts"]
        assert isinstance(facts, list)
        facts[0] = {
            "fact_kind": "plan-digest",
            "target_id": "platform",
            "value": f"sha256:{'c' * 64}",
        }

        violations = validate_operator_manifest_chain(
            [initial, successor, replacement],
            allow_synthetic=True,
        ).violations
        self.assertIn(
            ("MANIFEST_CHAIN_INVALID", "/revisions/2/generated_facts"),
            _codes(violations),
        )

        no_append = copy.deepcopy(successor)
        no_append["revision"] = 3
        no_append["predecessor_manifest_digest"] = accepted.digests[1]
        no_append["approval_reference"] = "owner-approval:synthetic-ap-m8-w2-revision-3"
        source = no_append["source"]
        assert isinstance(source, dict)
        source["source_revision"] = "2" * 40
        resources = no_append["platform_resources"]
        assert isinstance(resources, dict)
        resources["evidence_bundle_prefix"] = (
            f"ap-eval-m8/{'2' * 40}/synthetic-evaluation/"
        )
        violations = validate_operator_manifest_chain(
            [initial, successor, no_append],
            allow_synthetic=True,
        ).violations
        self.assertIn(
            ("MANIFEST_CHAIN_INVALID", "/revisions/2/generated_facts"),
            _codes(violations),
        )

    def test_operator_manifest_rejects_cross_scope_and_overbroad_authority(self) -> None:
        manifest = _manifest()
        controls = manifest["repository_controls"]
        assert isinstance(controls, dict)
        environments = controls["protected_environments"]
        assert isinstance(environments, dict)
        environments["apply"] = environments["plan"]
        federation = manifest["federation"]
        assert isinstance(federation, dict)
        identities = federation["operation_identities"]
        assert isinstance(identities, list)
        identity = identities[0]
        assert isinstance(identity, dict)
        identity["permissions"] = ["resourcemanager.projects.setIamPolicy"]
        state = manifest["state"]
        assert isinstance(state, dict)
        lineages = state["lineages"]
        assert isinstance(lineages, list)
        lineage = lineages[0]
        assert isinstance(lineage, dict)
        lineage["backend_prefix"] = "platform"

        violations = validate_configuration(
            manifest,
            "operator-input-manifest",
            allow_synthetic=True,
        )
        codes = _codes(violations)
        self.assertIn(
            ("OWNER_CONFLICT", "/repository_controls/protected_environments"),
            codes,
        )
        self.assertIn(
            (
                "CONFIGURATION_POLICY_INVALID",
                "/federation/operation_identities/0/permissions/0",
            ),
            codes,
        )
        self.assertIn(("OWNER_CONFLICT", "/state/lineages"), codes)

    def test_operator_manifest_rejects_placeholder_secret_and_mutable_fact(self) -> None:
        manifest = _manifest()
        manifest["configuration_class"] = "operator"
        manifest["secret_value"] = "must-not-enter-git"
        violations = validate_configuration(manifest, "operator-input-manifest")
        codes = _codes(violations)
        self.assertIn(("FIELD_UNKNOWN", "/secret_value"), codes)
        self.assertIn(("PROHIBITED_MATERIAL", "/secret_value"), codes)
        self.assertIn("CONFIGURATION_POLICY_INVALID", {item.code for item in violations})

        synthetic = _manifest()
        synthetic["revision"] = 2
        synthetic["predecessor_manifest_digest"] = f"sha256:{'a' * 64}"
        synthetic["generated_facts"] = [
            {
                "fact_kind": "image-digest",
                "target_id": "shared-edge",
                "value": "us-west1-docker.pkg.dev/project/repository/shared-edge:latest",
            }
        ]
        violations = validate_configuration(
            synthetic,
            "operator-input-manifest",
            allow_synthetic=True,
        )
        self.assertIn(
            ("CONFIGURATION_POLICY_INVALID", "/generated_facts/0/value"),
            _codes(violations),
        )

    def test_operator_manifest_chain_load_is_bounded_and_non_mutating(self) -> None:
        initial = _manifest()
        initial_result = validate_operator_manifest_chain(
            [initial],
            allow_synthetic=True,
        )
        successor = _successor(initial, initial_result.digests[0])
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = (directory / "1.json", directory / "2.json")
            paths[0].write_text(json.dumps(initial), encoding="utf-8")
            paths[1].write_text(json.dumps(successor), encoding="utf-8")
            before = tuple(path.read_bytes() for path in paths)
            result = load_operator_manifest_chain(paths, allow_synthetic=True)
            after = tuple(path.read_bytes() for path in paths)

        self.assertEqual(result.violations, ())
        self.assertEqual(len(result.digests), 2)
        self.assertEqual(before, after)

    def test_operator_manifest_chain_fails_closed_before_digesting_invalid_values(self) -> None:
        manifest = _manifest()
        manifest["generated_facts"] = {"not", "json"}

        result = validate_operator_manifest_chain(
            [manifest],
            allow_synthetic=True,
        )

        self.assertIsNone(result.values)
        self.assertEqual(result.digests, ())
        self.assertIn(
            ("FIELD_TYPE", "/revisions/0/generated_facts"),
            _codes(result.violations),
        )

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
