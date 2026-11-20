mock_provider "google" {
  override_during = plan
}

variables {
  platform_configuration = jsondecode(file("../../config/examples/platform-foundation.synthetic.v2.json"))
}

run "plans_bounded_observability_evidence_retention_and_cost_controls" {
  command = plan

  assert {
    condition = (
      module.platform_controls.policy_summary.logging.bucket_id == "synthetic-platform-logs" &&
      module.platform_controls.policy_summary.logging.region == "us-west1" &&
      module.platform_controls.policy_summary.logging.retention_days == 7 &&
      !module.platform_controls.policy_summary.logging.analytics &&
      !module.platform_controls.policy_summary.logging.locked &&
      module.platform_controls.policy_summary.logging.deletion_policy == "PREVENT" &&
      module.platform_controls.policy_summary.logging.internal_destination &&
      !module.platform_controls.policy_summary.logging.external_sink &&
      !module.platform_controls.policy_summary.logging.unique_writer_identity &&
      module.platform_controls.policy_summary.logging.exclusion_count == 3 &&
      module.platform_controls.policy_summary.logging.default_bucket_excluded &&
      module.platform_controls.policy_summary.logging.owner_reader_role == "roles/logging.viewAccessor" &&
      module.platform_controls.policy_summary.logging.owner_principal == "user:owner@example.invalid"
    )
    error_message = "Shared Edge logs must remain regional, owner-readable, internally routed, excluded, and limited to seven days"
  }

  assert {
    condition = (
      toset(module.platform_controls.policy_summary.logging.allowed_fields) == toset([
        "application_id",
        "component",
        "component_version",
        "correlation_id",
        "event_type",
        "event_version",
        "generation_digest",
        "latency_ms",
        "outcome",
        "route_identifier",
        "source_revision",
        "status_class",
      ]) &&
      contains(module.platform_controls.policy_summary.logging.prohibited_fields, "assertion") &&
      contains(module.platform_controls.policy_summary.logging.prohibited_fields, "session") &&
      contains(module.platform_controls.policy_summary.logging.prohibited_fields, "visitor_metadata") &&
      contains(module.platform_controls.policy_summary.logging.prohibited_fields, "request_body") &&
      contains(module.platform_controls.policy_summary.logging.prohibited_fields, "provider_response") &&
      contains(module.platform_controls.policy_summary.logging.prohibited_fields, "terraform_state") &&
      contains(module.platform_controls.policy_summary.logging.prohibited_fields, "saved_plan")
    )
    error_message = "logging intent must preserve the minimized completion-event allow-list and prohibited material exclusions"
  }

  assert {
    condition = (
      module.platform_controls.policy_summary.evidence.bucket_name == "synthetic-platform-evidence" &&
      module.platform_controls.policy_summary.evidence.region == "us-west1" &&
      module.platform_controls.policy_summary.evidence.retention_days == 30 &&
      module.platform_controls.policy_summary.evidence.retention_period_seconds == 2592000 &&
      module.platform_controls.policy_summary.evidence.lifecycle_expiration_days == 30 &&
      module.platform_controls.policy_summary.evidence.uniform_bucket_level_access &&
      module.platform_controls.policy_summary.evidence.public_access_prevention == "enforced" &&
      !module.platform_controls.policy_summary.evidence.force_destroy &&
      module.platform_controls.policy_summary.evidence.deletion_policy == "PREVENT" &&
      module.platform_controls.policy_summary.evidence.owner_reader_role == "roles/storage.objectViewer" &&
      module.platform_controls.policy_summary.evidence.owner_principal == "user:owner@example.invalid" &&
      module.platform_controls.policy_summary.evidence.object_upload == "deferred" &&
      contains(module.platform_controls.policy_summary.evidence.allowed_material, "redacted_provider_readback") &&
      contains(module.platform_controls.policy_summary.evidence.allowed_material, "limitations") &&
      contains(module.platform_controls.policy_summary.evidence.prohibited_fields, "provider_payload")
    )
    error_message = "evidence intent must remain private, redacted, owner-readable, and bounded to 30 days without an AP-M7 upload"
  }

  assert {
    condition = (
      module.platform_controls.policy_summary.budget.billing_account_reference == "billingAccounts/000000-000000-000000" &&
      module.platform_controls.policy_summary.budget.project_number == "123456789012" &&
      module.platform_controls.policy_summary.budget.currency == "USD" &&
      module.platform_controls.policy_summary.budget.monthly_amount == 20 &&
      module.platform_controls.policy_summary.budget.threshold_percents == [50, 80, 100] &&
      module.platform_controls.policy_summary.budget.spend_basis == "CURRENT_SPEND" &&
      module.platform_controls.policy_summary.budget.notification_email == "owner@example.invalid" &&
      !module.platform_controls.policy_summary.budget.implicit_notification &&
      !module.platform_controls.policy_summary.budget.automatic_billing_disablement &&
      !module.platform_controls.policy_summary.budget.automatic_resource_mutation &&
      !module.platform_controls.policy_summary.budget.guaranteed_hard_cap
    )
    error_message = "the project budget must notify the explicit destination at 50, 80, and 100 percent without mutating resources or claiming a hard cap"
  }

  assert {
    condition = (
      module.platform_controls.policy_summary.artifacts.repository_id == "synthetic-images" &&
      module.platform_controls.policy_summary.artifacts.repository_format == "DOCKER" &&
      module.platform_controls.policy_summary.artifacts.region == "us-west1" &&
      module.platform_controls.policy_summary.artifacts.cleanup_dry_run &&
      module.platform_controls.policy_summary.artifacts.retained_roles == ["active", "rollback", "candidate"] &&
      module.platform_controls.policy_summary.artifacts.most_recent_versions_per_service == 3 &&
      toset(module.platform_controls.policy_summary.artifacts.package_name_prefixes) == toset([
        "fixture-authenticated",
        "fixture-public",
        "fixture-restricted",
        "shared-edge",
      ]) &&
      module.platform_controls.policy_summary.artifacts.rollback_window_hours == 24 &&
      module.platform_controls.policy_summary.artifacts.owner_approved_deletion_required &&
      module.platform_controls.policy_summary.artifacts.deletion_policy == "PREVENT" &&
      module.platform_controls.policy_summary.artifacts.image_publication == "deferred"
    )
    error_message = "Artifact Registry cleanup must remain dry-run-first and retain active, rollback, and candidate images for every qualification service"
  }

  assert {
    condition = (
      module.platform_controls.policy_summary.runtime_caps.shared_edge.minimum_instances == 0 &&
      module.platform_controls.policy_summary.runtime_caps.shared_edge.maximum_instances == 2 &&
      module.platform_controls.policy_summary.runtime_caps.shared_edge.cpu == "1" &&
      module.platform_controls.policy_summary.runtime_caps.shared_edge.memory == "512Mi" &&
      module.platform_controls.policy_summary.runtime_caps.shared_edge.concurrency == 20 &&
      module.platform_controls.policy_summary.runtime_caps.fixture_application.minimum_instances == 0 &&
      module.platform_controls.policy_summary.runtime_caps.fixture_application.maximum_instances == 1 &&
      module.platform_controls.policy_summary.runtime_caps.fixture_application.cpu == "1" &&
      module.platform_controls.policy_summary.runtime_caps.fixture_application.memory == "512Mi" &&
      module.platform_controls.policy_summary.runtime_caps.fixture_application.concurrency == 10 &&
      module.platform_controls.policy_summary.runtime_caps.maximum_stream_seconds == 3300 &&
      module.platform_controls.policy_summary.labels.required.environment == "staging" &&
      module.platform_controls.policy_summary.labels.required.managed_by == "terraform" &&
      module.platform_controls.policy_summary.labels.required.state_owner == "platform" &&
      module.platform_controls.policy_summary.labels.application_id_when_applicable
    )
    error_message = "runtime and label policy must retain every approved demo-scale cap"
  }

  assert {
    condition = (
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "always-on-instance") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "automatic-budget-mutation") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "automatic-cleanup-deletion") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "cdn") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "external-log-export") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "firestore-backup") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "firestore-pitr") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "hsm") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "production-replica") &&
      contains(module.platform_controls.policy_summary.prohibited_capabilities, "waf")
    )
    error_message = "the controls policy must explicitly prohibit every unapproved billable or destructive capability"
  }
}
