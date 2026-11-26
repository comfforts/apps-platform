"""Deterministic compatibility checks for inert Identity Delivery V2 contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from contracts import (
    compile_registration_set,
    compile_registration_set_v2,
    load_versioned_contract_document,
    migrate_registration_set_v1_to_v2,
    validate_versioned_contract_document,
)
from contracts.lifecycle import (
    load_versioned_lifecycle_document,
    validate_versioned_lifecycle_document,
    validate_versioned_lifecycle_relationships,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VECTORS = ROOT / "contracts" / "test-vectors" / "valid"
LIFECYCLE_VECTORS = ROOT / "contracts" / "lifecycle" / "test-vectors" / "valid"


def _document(directory: Path, name: str) -> dict[str, object]:
    value = json.loads((directory / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _contains_member_data(value: object) -> bool:
    """Return whether a document contains registration-scoped member material."""

    member_keys = {
        "member",
        "member_list",
        "member_records",
        "members",
        "platform_members",
        "restricted_members",
    }
    if isinstance(value, dict):
        return bool(member_keys.intersection(value)) or any(
            _contains_member_data(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_member_data(item) for item in value)
    return False


class IdentityDeliveryContractTest(unittest.TestCase):
    def test_v1_registration_migration_is_exact_deterministic_and_member_free(self) -> None:
        source = _document(CONTRACT_VECTORS, "multi-active-registration-set.v1.json")
        original = copy.deepcopy(source)
        expected = _document(
            CONTRACT_VECTORS,
            "migrated-multi-active-registration-set.v2.json",
        )

        first = migrate_registration_set_v1_to_v2(source)
        second = migrate_registration_set_v1_to_v2(source)

        self.assertEqual(first.violations, ())
        self.assertEqual(first.registration_set, expected)
        self.assertEqual(second, first)
        self.assertEqual(source, original)
        self.assertFalse(_contains_member_data(first.registration_set))

    def test_migration_never_invents_optional_identity_delivery(self) -> None:
        source = _document(CONTRACT_VECTORS, "multi-active-registration-set.v1.json")

        result = migrate_registration_set_v1_to_v2(source)

        assert result.registration_set is not None
        delivery_by_application = {
            item["application_id"]: item["identity_delivery"]
            for item in result.registration_set["registrations"]
        }
        self.assertEqual(
            delivery_by_application,
            {
                "alpha-app": "none",
                "beta-app": "required",
                "gamma-app": "required",
            },
        )

    def test_v2_compiler_matches_reviewed_member_free_vector(self) -> None:
        proposed = _document(
            CONTRACT_VECTORS,
            "migrated-multi-active-registration-set.v2.json",
        )
        configuration = _document(CONTRACT_VECTORS, "platform-configuration.v2.json")
        expected = _document(
            CONTRACT_VECTORS,
            "compiled-migrated-multi-active.v2.json",
        )

        result = compile_registration_set_v2(None, proposed, configuration)

        self.assertEqual(result.violations, ())
        self.assertEqual(result.compiled_configuration, expected)
        self.assertFalse(_contains_member_data(result.compiled_configuration))
        self.assertEqual(result.ownership_manifest["contract_version"], 1)  # type: ignore[index]

    def test_v2_compiler_reads_v1_predecessor_without_rewriting_its_digest(self) -> None:
        previous = _document(CONTRACT_VECTORS, "multi-active-registration-set.v1.json")
        v1_configuration = _document(
            CONTRACT_VECTORS,
            "platform-configuration.v1.json",
        )
        previous_compilation = compile_registration_set(
            None,
            previous,
            v1_configuration,
        )
        assert previous_compilation.generation_digest is not None
        migration = migrate_registration_set_v1_to_v2(previous)
        assert migration.registration_set is not None
        proposed = copy.deepcopy(migration.registration_set)
        proposed["generation"] = 2
        proposed["previous_generation_digest"] = previous_compilation.generation_digest
        proposed["proposal"] = {
            "source_revision": "ccccccc",
            "change_summary": "Represent the reviewed predecessor as Version 2",
        }
        configuration = _document(CONTRACT_VECTORS, "platform-configuration.v2.json")

        result = compile_registration_set_v2(previous, proposed, configuration)

        self.assertEqual(result.violations, ())
        self.assertEqual(
            result.compiled_configuration["previous_generation_digest"],  # type: ignore[index]
            previous_compilation.generation_digest,
        )

    def test_only_reviewed_access_and_identity_delivery_combinations_validate(self) -> None:
        base = _document(
            CONTRACT_VECTORS,
            "migrated-multi-active-registration-set.v2.json",
        )
        alpha = next(
            item for item in base["registrations"] if item["application_id"] == "alpha-app"
        )
        cases = (
            ("public", "none", "none", None, True),
            (
                "public",
                "optional",
                "optional",
                "urn:comfforts:app-platform:audience:alpha-app",
                True,
            ),
            (
                "authenticated",
                "required",
                "verified",
                "urn:comfforts:app-platform:audience:alpha-app",
                True,
            ),
            (
                "restricted",
                "required",
                "verified",
                "urn:comfforts:app-platform:audience:alpha-app",
                True,
            ),
            ("authenticated", "none", "none", None, False),
            ("restricted", "optional", "optional", None, False),
            ("public", "required", "verified", None, False),
        )
        for mode, delivery, requirement, audience, valid in cases:
            with self.subTest(mode=mode, delivery=delivery):
                candidate = copy.deepcopy(base)
                selected = next(
                    item
                    for item in candidate["registrations"]
                    if item["application_id"] == alpha["application_id"]
                )
                selected["admission"] = {"mode": mode}
                selected["identity_delivery"] = delivery
                for attachment in selected["attachments"]:
                    attachment["identity_requirement"] = requirement
                    attachment["audience"] = audience

                violations = validate_versioned_contract_document(
                    candidate,
                    "registration-set",
                )

                self.assertEqual(not violations, valid)

    def test_v2_registration_rejects_member_data_and_mixed_nested_versions(self) -> None:
        base = _document(
            CONTRACT_VECTORS,
            "migrated-multi-active-registration-set.v2.json",
        )
        member_bearing = copy.deepcopy(base)
        member_bearing["registrations"][0]["admission"]["members"] = []
        mixed = copy.deepcopy(base)
        mixed["registrations"][0]["attachments"][0]["contract_version"] = 1

        for candidate in (member_bearing, mixed):
            with self.subTest(candidate=candidate):
                self.assertTrue(
                    validate_versioned_contract_document(candidate, "registration-set")
                )

    def test_verified_identity_context_exposes_only_positive_minimal_membership(self) -> None:
        context = _document(
            CONTRACT_VECTORS,
            "verified-identity-context.member.v2.json",
        )
        self.assertEqual(
            validate_versioned_contract_document(context, "verified-identity-context"),
            (),
        )
        for key, value in (
            ("platform_member", False),
            ("roles", ["owner"]),
            ("email", "member@example.test"),
        ):
            with self.subTest(key=key):
                invalid = copy.deepcopy(context)
                invalid[key] = value
                self.assertTrue(
                    validate_versioned_contract_document(
                        invalid,
                        "verified-identity-context",
                    )
                )

    def test_versioned_contract_loader_reads_historical_v1_and_inert_v2(self) -> None:
        cases = (
            ("multi-active-registration-set.v1.json", 1),
            ("migrated-multi-active-registration-set.v2.json", 2),
        )
        for name, version in cases:
            with self.subTest(name=name):
                loaded = load_versioned_contract_document(
                    CONTRACT_VECTORS / name,
                    "registration-set",
                )
                self.assertEqual(loaded.violations, ())
                self.assertEqual(loaded.contract_version, version)
                self.assertRegex(loaded.digest or "", r"^sha256:[0-9a-f]{64}$")

    def test_v2_lifecycle_handoff_is_exact_and_mixed_versions_fail_closed(self) -> None:
        integration = _document(
            LIFECYCLE_VECTORS,
            "platform-integration-bundle.staging.synthetic.v2.json",
        )
        attachment = _document(
            LIFECYCLE_VECTORS,
            "application-attachment-bundle.staging.synthetic.v2.json",
        )
        intent = _document(
            LIFECYCLE_VECTORS,
            "registration-intent.staging.synthetic.v2.json",
        )

        self.assertEqual(
            validate_versioned_lifecycle_relationships(
                integration_bundle=integration,
                attachment_bundle=attachment,
                registration_intent=intent,
            ),
            (),
        )

        historical_attachment = _document(
            LIFECYCLE_VECTORS,
            "application-attachment-bundle.staging.synthetic.v1.json",
        )
        mixed = validate_versioned_lifecycle_relationships(
            integration_bundle=integration,
            attachment_bundle=historical_attachment,
            registration_intent=intent,
        )
        self.assertIn("CONTRACT_VERSION_MIXED", {item.code for item in mixed})

    def test_v2_handoff_rejects_member_material_and_invalid_delivery(self) -> None:
        integration = _document(
            LIFECYCLE_VECTORS,
            "platform-integration-bundle.staging.synthetic.v2.json",
        )
        member_bearing = copy.deepcopy(integration)
        member_bearing["members"] = []
        invalid_delivery = copy.deepcopy(integration)
        invalid_delivery["identity_delivery"] = "optional"

        self.assertIn(
            "PROHIBITED_MATERIAL",
            {
                item.code
                for item in validate_versioned_lifecycle_document(
                    member_bearing,
                    "platform-integration-bundle",
                )
            },
        )
        self.assertTrue(
            validate_versioned_lifecycle_document(
                invalid_delivery,
                "platform-integration-bundle",
            )
        )

    def test_v2_integration_bundle_accepts_each_reviewed_delivery_combination(self) -> None:
        base = _document(
            LIFECYCLE_VECTORS,
            "platform-integration-bundle.staging.synthetic.v2.json",
        )
        cases = (
            ("public", "none", False, True),
            ("public", "optional", True, True),
            ("authenticated", "required", True, True),
            ("restricted", "required", True, True),
            ("authenticated", "none", False, False),
            ("restricted", "optional", True, False),
            ("public", "required", True, False),
        )
        for access_mode, delivery, identity_enabled, valid in cases:
            with self.subTest(access_mode=access_mode, delivery=delivery):
                candidate = copy.deepcopy(base)
                candidate["access_mode"] = access_mode
                candidate["identity_delivery"] = delivery
                if not identity_enabled:
                    candidate["identity"] = {
                        "oauth_client_id": None,
                        "audience": None,
                        "edge_caller_reference": candidate["identity"][
                            "edge_caller_reference"
                        ],
                    }
                    candidate["endpoints"]["issuer"] = None
                    candidate["endpoints"]["jwks_uri"] = None
                    candidate["endpoints"]["oauth_redirect_uri"] = None

                violations = validate_versioned_lifecycle_document(
                    candidate,
                    "platform-integration-bundle",
                )

                self.assertEqual(not violations, valid)

    def test_versioned_lifecycle_loader_reads_v1_v2_and_registration_intent(self) -> None:
        cases = (
            (
                "platform-integration-bundle.staging.synthetic.v1.json",
                "platform-integration-bundle",
            ),
            (
                "platform-integration-bundle.staging.synthetic.v2.json",
                "platform-integration-bundle",
            ),
            (
                "registration-intent.staging.synthetic.v2.json",
                "registration-intent",
            ),
        )
        for name, kind in cases:
            with self.subTest(name=name):
                loaded = load_versioned_lifecycle_document(
                    LIFECYCLE_VECTORS / name,
                    kind,
                )
                self.assertEqual(loaded.violations, ())
                self.assertRegex(loaded.digest or "", r"^sha256:[0-9a-f]{64}$")

    def test_active_v1_consumers_do_not_import_or_select_v2_contracts(self) -> None:
        active_roots = (ROOT / "edge", ROOT / "fixtures", ROOT / "infrastructure" / "operator")
        prohibited = (
            "compile_registration_set_v2",
            "migrate_registration_set_v1_to_v2",
            "load_versioned_contract_document",
            "load_versioned_lifecycle_document",
            ".v2.schema.json",
        )
        matches: list[str] = []
        for active_root in active_roots:
            for path in active_root.rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                for marker in prohibited:
                    if marker in source:
                        matches.append(f"{path.relative_to(ROOT)}: {marker}")
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
