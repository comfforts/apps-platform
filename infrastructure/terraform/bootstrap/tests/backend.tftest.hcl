mock_provider "google" {
  override_during = plan
}

variables {
  backend_configuration = jsondecode(file("../../config/examples/backend.synthetic.v1.json"))
}

run "plans_four_exclusive_recoverable_backends" {
  command = plan

  assert {
    condition = (
      output.bootstrap_phase_output.contract_version == 1 &&
      output.bootstrap_phase_output.output_kind == "bootstrap" &&
      output.bootstrap_phase_output.environment == "staging" &&
      length(output.bootstrap_phase_output.lineages) == 5
    )
    error_message = "bootstrap must expose one closed typed output with five lineages"
  }

  assert {
    condition = alltrue([
      for reference in values(output.bootstrap_phase_output.lineages) :
      contains(["platform", "application"], reference.state_owner)
    ])
    error_message = "bootstrap outputs must remain typed backend references"
  }

  assert {
    condition = alltrue([
      for bucket in values(module.state_bucket) :
      bucket.policy_summary.uniform_bucket_level_access &&
      bucket.policy_summary.public_access_prevention == "enforced" &&
      bucket.policy_summary.object_versioning_enabled &&
      bucket.policy_summary.noncurrent_version_retention_days >= 90 &&
      bucket.policy_summary.newer_versions_to_retain >= 20 &&
      !bucket.policy_summary.force_destroy &&
      bucket.policy_summary.deletion_policy == "PREVENT" &&
      bucket.policy_summary.iam_binding == "deferred"
    ])
    error_message = "every state bucket must retain the complete recovery and non-destruction policy"
  }

  assert {
    condition = toset([
      for reference in values(output.bootstrap_phase_output.lineages) :
      "${reference.state_owner}:${reference.owner_id}:${reference.prefix}"
      ]) == toset([
      "platform:app-platform:bootstrap",
      "platform:app-platform:platform",
      "application:fixture-public:fixtures/fixture-public",
      "application:fixture-authenticated:fixtures/fixture-authenticated",
      "application:fixture-restricted:fixtures/fixture-restricted",
    ])
    error_message = "backend access intent must remain exclusive and root-scoped"
  }

  assert {
    condition = alltrue([
      for owner_id, bucket in module.state_bucket :
      bucket.policy_summary.configured_labels.environment == "staging" &&
      bucket.policy_summary.configured_labels.managed_by == "terraform" &&
      bucket.policy_summary.configured_labels.state_owner == (
        owner_id == "app-platform" ? "platform" : "application"
      ) &&
      (
        owner_id == "app-platform" ?
        !contains(keys(bucket.policy_summary.configured_labels), "application_id") :
        bucket.policy_summary.configured_labels.application_id == owner_id
      )
    ])
    error_message = "state bucket labels must identify the exact environment and exclusive owner"
  }
}
