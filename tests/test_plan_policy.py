"""AP-M9-W5 canonical Terraform-plan policy checks."""

from __future__ import annotations

from copy import deepcopy
import unittest

from infrastructure.backend import evaluate_plan, plan_policy


SOURCE_REVISION = "1" * 40


def _foundation_observation() -> dict[str, object]:
    return {
        "environment": "staging",
        "source_revision": SOURCE_REVISION,
        "state_owner": "platform",
        "owner_id": "app-platform",
        "terraform_root": "infrastructure/terraform/platform",
        "phase": "platform-foundation",
        "provider": {
            "source": "registry.terraform.io/hashicorp/google",
            "service": "google",
            "project_id": "comfforts-platform-non-prod",
            "configuration": "explicit",
        },
        "changes": [
            {
                "address": "module.platform_controls.google_artifact_registry_repository.images",
                "resource_type": "google_artifact_registry_repository",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["create"],
            },
            {
                "address": "module.platform_foundation.google_storage_bucket.configuration",
                "resource_type": "google_storage_bucket",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["create"],
            },
        ],
    }


def _shared_edge_observation() -> dict[str, object]:
    observation = _foundation_observation()
    observation["phase"] = "shared-edge"
    observation["changes"] = [
        {
            "address": "module.shared_edge[0].google_compute_global_address.edge",
            "resource_type": "google_compute_global_address",
            "provider_source": "registry.terraform.io/hashicorp/google",
            "actions": ["create"],
        },
        {
            "address": (
                "module.platform_foundation."
                "google_storage_bucket.configuration"
            ),
            "resource_type": "google_storage_bucket",
            "provider_source": "registry.terraform.io/hashicorp/google",
            "actions": ["no-op"],
        },
        {
            "address": (
                "module.platform_controls."
                "google_artifact_registry_repository.qualification_images[0]"
            ),
            "resource_type": "google_artifact_registry_repository",
            "provider_source": "registry.terraform.io/hashicorp/google",
            "actions": ["no-op"],
        },
    ]
    return observation


def _foundation_refresh_observation() -> dict[str, object]:
    observation = _foundation_observation()
    observation["planning_mode"] = "refresh-only"
    observation["changes"] = [
        {
            "address": "module.platform_foundation.google_storage_bucket.configuration",
            "resource_type": "google_storage_bucket",
            "provider_source": "registry.terraform.io/hashicorp/google",
            "actions": ["no-op"],
        },
        {
            "address": "module.shared_edge[0].google_compute_global_address.edge",
            "resource_type": "google_compute_global_address",
            "provider_source": "registry.terraform.io/hashicorp/google",
            "actions": ["no-op"],
        },
    ]
    return observation


def _fixture_observation(application_id: str) -> dict[str, object]:
    return {
        "environment": "staging",
        "source_revision": SOURCE_REVISION,
        "state_owner": "application",
        "owner_id": application_id,
        "terraform_root": f"infrastructure/terraform/fixtures/{application_id}",
        "phase": application_id,
        "provider": {
            "source": "registry.terraform.io/hashicorp/google",
            "service": "google",
            "project_id": "comfforts-platform-non-prod",
            "configuration": "explicit",
        },
        "changes": [
            {
                "address": "module.fixture_application.google_service_account.runtime",
                "resource_type": "google_service_account",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["create"],
            },
            {
                "address": "module.fixture_application.google_cloud_run_v2_service.runtime",
                "resource_type": "google_cloud_run_v2_service",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["create"],
            },
            {
                "address": (
                    "module.fixture_application."
                    "google_cloud_run_v2_service_iam_member.edge_invoker"
                ),
                "resource_type": "google_cloud_run_v2_service_iam_member",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["create"],
            },
        ],
    }


class PlanPolicyTest(unittest.TestCase):
    def test_accepted_summary_is_canonical_redacted_and_order_independent(self) -> None:
        policy = plan_policy(
            "staging",
            "platform-foundation",
            SOURCE_REVISION,
            destructive=False,
        )
        first_observation = _foundation_observation()
        second_observation = deepcopy(first_observation)
        second_observation["changes"] = list(
            reversed(second_observation["changes"])  # type: ignore[arg-type]
        )
        first_observation["raw_plan"] = {"secret": "must-not-survive"}
        first_observation["changes"][0]["before"] = {  # type: ignore[index]
            "provider_payload": "must-not-survive"
        }

        first = evaluate_plan(policy, first_observation)
        second = evaluate_plan(policy, second_observation)

        self.assertTrue(first.accepted)
        self.assertEqual(first.violations, ())
        self.assertEqual(first.plan_digest, second.plan_digest)
        self.assertEqual(first.canonical_summary, second.canonical_summary)
        self.assertEqual(
            [change["resource_type"] for change in first.canonical_summary["changes"]],
            ["google_artifact_registry_repository", "google_storage_bucket"],
        )
        self.assertNotIn("raw_plan", first.canonical_summary)
        self.assertNotIn("before", first.canonical_summary["changes"][0])
        self.assertNotIn("after", first.canonical_summary["changes"][0])

    def test_policy_rejects_every_context_and_scope_mismatch(self) -> None:
        policy = plan_policy(
            "staging",
            "platform-foundation",
            SOURCE_REVISION,
            destructive=False,
        )
        cases = {
            "environment": ("production", "ENVIRONMENT_MISMATCH"),
            "source_revision": ("2" * 40, "SOURCE_MISMATCH"),
            "state_owner": ("application", "OWNER_MISMATCH"),
            "owner_id": ("fixture-public", "OWNER_MISMATCH"),
            "terraform_root": (
                "infrastructure/terraform/bootstrap",
                "ROOT_MISMATCH",
            ),
            "phase": ("shared-edge", "PHASE_MISMATCH"),
        }
        for field, (wrong_value, expected_code) in cases.items():
            with self.subTest(field=field):
                observation = _foundation_observation()
                observation[field] = wrong_value
                result = evaluate_plan(policy, observation)
                self.assertFalse(result.accepted)
                self.assertIn(expected_code, [item.code for item in result.violations])
                self.assertIsNone(result.plan_digest)

    def test_policy_rejects_provider_default_project_and_service_mismatch(self) -> None:
        policy = plan_policy(
            "staging",
            "platform-foundation",
            SOURCE_REVISION,
            destructive=False,
        )
        cases = {
            "configuration": ("ambient", "PROVIDER_DEFAULT_PROHIBITED"),
            "project_id": ("another-project", "PROJECT_MISMATCH"),
            "service": ("aws", "SERVICE_MISMATCH"),
            "source": ("registry.terraform.io/hashicorp/aws", "SERVICE_MISMATCH"),
        }
        for field, (wrong_value, expected_code) in cases.items():
            with self.subTest(field=field):
                observation = _foundation_observation()
                observation["provider"][field] = wrong_value  # type: ignore[index]
                result = evaluate_plan(policy, observation)
                self.assertIn(expected_code, [item.code for item in result.violations])

    def test_policy_rejects_unexpected_resource_action_replacement_and_delete(self) -> None:
        policy = plan_policy(
            "staging",
            "platform-foundation",
            SOURCE_REVISION,
            destructive=False,
        )
        cases = (
            ("google_dns_record_set", ["create"], "RESOURCE_PROHIBITED"),
            ("google_storage_bucket", ["forget"], "ACTION_PROHIBITED"),
            ("google_storage_bucket", ["delete", "create"], "REPLACEMENT_PROHIBITED"),
            ("google_storage_bucket", ["delete"], "DESTRUCTIVE_ACTION_PROHIBITED"),
        )
        for resource_type, actions, expected_code in cases:
            with self.subTest(resource_type=resource_type, actions=actions):
                observation = _foundation_observation()
                observation["changes"] = [
                    {
                        "address": f"module.test.{resource_type}.subject",
                        "resource_type": resource_type,
                        "provider_source": "registry.terraform.io/hashicorp/google",
                        "actions": actions,
                    }
                ]
                result = evaluate_plan(policy, observation)
                self.assertIn(expected_code, [item.code for item in result.violations])

    def test_shared_edge_accepts_exact_inherited_foundation_no_ops(self) -> None:
        policy = plan_policy(
            "staging",
            "shared-edge",
            SOURCE_REVISION,
            destructive=False,
        )

        result = evaluate_plan(policy, _shared_edge_observation())

        self.assertTrue(result.accepted)
        self.assertEqual(result.violations, ())
        self.assertEqual(
            [change["actions"] for change in result.canonical_summary["changes"]],
            [["no-op"], ["create"], ["no-op"]],
        )

    def test_foundation_refresh_accepts_existing_shared_edge_only_as_read_only(
        self,
    ) -> None:
        policy = plan_policy(
            "staging",
            "platform-foundation",
            SOURCE_REVISION,
            destructive=False,
        )

        accepted = evaluate_plan(policy, _foundation_refresh_observation())

        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.violations, ())
        self.assertEqual(accepted.canonical_summary["planning_mode"], "refresh-only")

        for address, resource_type in (
            (
                "module.platform_foundation.google_storage_bucket.configuration",
                "google_storage_bucket",
            ),
            (
                "module.shared_edge[0].google_compute_global_address.edge",
                "google_compute_global_address",
            ),
        ):
            with self.subTest(address=address):
                observation = _foundation_refresh_observation()
                observation["changes"] = [
                    {
                        "address": address,
                        "resource_type": resource_type,
                        "provider_source": "registry.terraform.io/hashicorp/google",
                        "actions": ["update"],
                    }
                ]

                refused = evaluate_plan(policy, observation)

                self.assertFalse(refused.accepted)
                self.assertIn(
                    "REFRESH_ONLY_MUTATION_PROHIBITED",
                    [item.code for item in refused.violations],
                )

    def test_shared_edge_rejects_inherited_mutation_wrong_prefix_and_unknown_type(
        self,
    ) -> None:
        policy = plan_policy(
            "staging",
            "shared-edge",
            SOURCE_REVISION,
            destructive=False,
        )
        cases = (
            (
                "module.platform_foundation.google_storage_bucket.configuration",
                "google_storage_bucket",
                ["update"],
                "INHERITED_RESOURCE_MUTATION_PROHIBITED",
            ),
            (
                "module.shared_edge[0].google_storage_bucket.configuration",
                "google_storage_bucket",
                ["no-op"],
                "RESOURCE_PROHIBITED",
            ),
            (
                "module.platform_foundation.google_dns_record_set.unexpected",
                "google_dns_record_set",
                ["no-op"],
                "RESOURCE_PROHIBITED",
            ),
        )
        for address, resource_type, actions, expected_code in cases:
            with self.subTest(address=address, actions=actions):
                observation = _shared_edge_observation()
                observation["changes"] = [
                    {
                        "address": address,
                        "resource_type": resource_type,
                        "provider_source": "registry.terraform.io/hashicorp/google",
                        "actions": actions,
                    }
                ]

                result = evaluate_plan(policy, observation)

                self.assertFalse(result.accepted)
                self.assertIn(
                    expected_code,
                    [item.code for item in result.violations],
                )

    def test_destroy_policy_allows_only_owned_deletes(self) -> None:
        policy = plan_policy(
            "staging",
            "shared-edge",
            SOURCE_REVISION,
            destructive=True,
        )
        observation = _foundation_observation()
        observation["phase"] = "shared-edge"
        observation["changes"] = [
            {
                "address": "module.shared_edge.google_compute_global_address.edge",
                "resource_type": "google_compute_global_address",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["delete"],
            }
        ]

        result = evaluate_plan(policy, observation)

        self.assertTrue(result.accepted)
        self.assertEqual(result.violations, ())
        self.assertIsNotNone(result.plan_digest)

        observation["changes"][0]["actions"] = ["create"]  # type: ignore[index]
        refused = evaluate_plan(policy, observation)
        self.assertIn("ACTION_PROHIBITED", [item.code for item in refused.violations])

    def test_platform_destroy_policy_never_authorizes_retained_state(self) -> None:
        policy = plan_policy(
            "staging",
            "platform-foundation",
            SOURCE_REVISION,
            destructive=True,
        )
        for address, resource_type in (
            (
                "module.platform_foundation.google_storage_bucket.configuration",
                "google_storage_bucket",
            ),
            (
                "module.platform_foundation.google_kms_crypto_key.assertion_signing",
                "google_kms_crypto_key",
            ),
            (
                "module.platform_controls.google_storage_bucket.evidence",
                "google_storage_bucket",
            ),
        ):
            with self.subTest(address=address):
                observation = _foundation_observation()
                observation["changes"] = [
                    {
                        "address": address,
                        "resource_type": resource_type,
                        "provider_source": "registry.terraform.io/hashicorp/google",
                        "actions": ["delete"],
                    }
                ]
                result = evaluate_plan(policy, observation)
                self.assertIn(
                    "RETAINED_RESOURCE_DELETE_PROHIBITED",
                    [item.code for item in result.violations],
                )

        destructible = _foundation_observation()
        destructible["changes"] = [
            {
                "address": (
                    "module.platform_foundation."
                    "google_secret_manager_secret.edge_oauth[0]"
                ),
                "resource_type": "google_secret_manager_secret",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["delete"],
            }
        ]
        self.assertTrue(evaluate_plan(policy, destructible).accepted)

    def test_fixture_policy_binds_each_independent_application_owner(self) -> None:
        for application_id in (
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
        ):
            with self.subTest(application_id=application_id):
                policy = plan_policy(
                    "staging",
                    application_id,
                    SOURCE_REVISION,
                    destructive=False,
                )
                accepted = evaluate_plan(
                    policy,
                    _fixture_observation(application_id),
                )

                self.assertTrue(accepted.accepted)
                self.assertEqual(policy.state_owner, "application")
                self.assertEqual(policy.owner_id, application_id)

                wrong_owner = _fixture_observation(application_id)
                wrong_owner["owner_id"] = "app-platform"
                refused = evaluate_plan(policy, wrong_owner)
                self.assertIn(
                    "OWNER_MISMATCH",
                    [item.code for item in refused.violations],
                )

    def test_fixture_destroy_policy_allows_only_fixture_resource_deletes(self) -> None:
        application_id = "fixture-public"
        policy = plan_policy(
            "staging",
            application_id,
            SOURCE_REVISION,
            destructive=True,
        )
        observation = _fixture_observation(application_id)
        for change in observation["changes"]:  # type: ignore[union-attr]
            change["actions"] = ["delete"]

        accepted = evaluate_plan(policy, observation)

        self.assertTrue(accepted.accepted)
        observation["changes"].append(  # type: ignore[union-attr]
            {
                "address": "google_storage_bucket.platform",
                "resource_type": "google_storage_bucket",
                "provider_source": "registry.terraform.io/hashicorp/google",
                "actions": ["delete"],
            }
        )
        refused = evaluate_plan(policy, observation)
        self.assertIn("RESOURCE_PROHIBITED", [item.code for item in refused.violations])


if __name__ == "__main__":
    unittest.main()
