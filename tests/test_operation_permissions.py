"""Least-privilege operation identity role-intent tests."""

from __future__ import annotations

import unittest

from infrastructure.backend import (
    EnvironmentUnavailableError,
    compile_identity_bootstrap_plan,
    operation_authorities,
    operation_role_bindings,
)


class OperationPermissionsTest(unittest.TestCase):
    billing_account = "billingAccounts/ABCDEF-123456-7890AB"

    def test_every_non_bootstrap_authority_has_exact_scoped_role_intent(self) -> None:
        authorities = operation_authorities("staging")
        bindings = operation_role_bindings("staging")
        bound = {item.authority_email for item in bindings}

        self.assertEqual(
            bound,
            {
                item.service_account_email
                for item in authorities
                if item.action != "bootstrap"
            },
        )
        self.assertEqual(len(bindings), len(set(bindings)))
        self.assertTrue(all(item.scope for item in bindings))

    def test_backend_roles_are_prefix_scoped_and_never_cross_lineages(self) -> None:
        authorities = {
            item.service_account_email: item
            for item in operation_authorities("staging")
        }
        backend = [
            item
            for item in operation_role_bindings("staging")
            if item.scope_kind == "bucket"
            and item.condition_title is not None
        ]

        self.assertEqual(len(backend), 30)
        for binding in backend:
            authority = authorities[binding.authority_email]
            self.assertEqual(binding.scope, authority.backend_bucket)
            self.assertIn(
                f"/objects/{authority.backend_prefix}/",
                binding.condition_expression or "",
            )
            self.assertIn(
                binding.role,
                {"roles/storage.objectUser", "roles/storage.objectViewer"},
            )

    def test_roles_exclude_basic_admin_key_and_cross_owner_grants(self) -> None:
        bindings = operation_role_bindings("staging")
        prohibited = {
            "roles/editor",
            "roles/iam.serviceAccountKeyAdmin",
            "roles/owner",
            "roles/viewer",
        }

        self.assertTrue(prohibited.isdisjoint(item.role for item in bindings))
        for binding in bindings:
            if "fxpub" in binding.authority_email:
                self.assertNotIn("fixture-authenticated", binding.scope)
                self.assertNotIn("fixture-restricted", binding.scope)
            if "fxauth" in binding.authority_email:
                self.assertNotIn("fixture-public", binding.scope)
                self.assertNotIn("fixture-restricted", binding.scope)
            if "fxrest" in binding.authority_email:
                self.assertNotIn("fixture-public", binding.scope)
                self.assertNotIn("fixture-authenticated", binding.scope)

    def test_platform_mutation_has_only_named_service_administration(self) -> None:
        bindings = [
            item
            for item in operation_role_bindings(
                "staging",
                billing_account_reference=self.billing_account,
            )
            if "platform-apply" in item.authority_email
            and item.scope_kind == "project"
        ]

        self.assertIn(
            "roles/resourcemanager.projectIamAdmin",
            {item.role for item in bindings},
        )
        self.assertIn(
            "roles/serviceusage.serviceUsageConsumer",
            {item.role for item in bindings},
        )
        self.assertNotIn(
            "roles/iam.serviceAccountTokenCreator",
            {item.role for item in bindings},
        )

    def test_billing_scope_is_resolved_not_placeholder_material(self) -> None:
        without_billing = operation_role_bindings("staging")
        with_billing = operation_role_bindings(
            "staging",
            billing_account_reference=self.billing_account,
        )

        self.assertFalse(
            any(item.scope_kind == "billing-account" for item in without_billing)
        )
        self.assertEqual(
            {
                item.scope
                for item in with_billing
                if item.scope_kind == "billing-account"
            },
            {self.billing_account},
        )
        with self.assertRaisesRegex(ValueError, "canonical"):
            operation_role_bindings(
                "staging",
                billing_account_reference="approved-discovered-billing-account",
            )

    def test_identity_bootstrap_is_complete_digest_bound_and_human_only(self) -> None:
        plan = compile_identity_bootstrap_plan(
            "staging",
            operator_principal="user:operator@example.com",
            billing_account_reference=self.billing_account,
        )
        repeated = compile_identity_bootstrap_plan(
            "staging",
            operator_principal="user:operator@example.com",
            billing_account_reference=self.billing_account,
        )

        self.assertEqual(plan, repeated)
        self.assertRegex(plan.digest, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(plan.identities), 31)
        self.assertEqual(len(plan.impersonation_grants), 31)
        self.assertTrue(
            all(
                item.role == "roles/iam.serviceAccountTokenCreator"
                for item in plan.impersonation_grants
            )
        )
        self.assertFalse(
            any(
                item.role == "roles/iam.serviceAccountTokenCreator"
                for item in plan.role_bindings
            )
        )
        with self.assertRaisesRegex(ValueError, "human user"):
            compile_identity_bootstrap_plan(
                "staging",
                operator_principal=(
                    "serviceAccount:operator@comfforts-platform-non-prod."
                    "iam.gserviceaccount.com"
                ),
                billing_account_reference=self.billing_account,
            )

    def test_rollback_is_traffic_and_immutable_configuration_only(self) -> None:
        bindings = [
            item
            for item in operation_role_bindings("staging")
            if "platform-rollback" in item.authority_email
        ]

        self.assertEqual(
            {(item.scope_kind, item.role) for item in bindings},
            {
                ("bucket", "roles/storage.objectUser"),
                ("bucket", "roles/storage.objectViewer"),
                ("cloud-run-service", "roles/run.admin"),
            },
        )

    def test_production_has_no_role_binding_authority(self) -> None:
        with self.assertRaisesRegex(
            EnvironmentUnavailableError,
            "OWNERSHIP_TRANSFER_REQUIRED",
        ):
            operation_role_bindings("production")


if __name__ == "__main__":
    unittest.main()
