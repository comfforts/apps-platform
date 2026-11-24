mock_provider "google" {
  override_during = plan
}

variables {
  backend_configuration = jsondecode(file("../../config/examples/backend.synthetic.v1.json"))
}

run "plans_one_exclusive_recoverable_platform_backend" {
  command = plan

  assert {
    condition = (
      output.bootstrap_phase_output.contract_version == 1 &&
      output.bootstrap_phase_output.output_kind == "bootstrap" &&
      output.bootstrap_phase_output.environment == "staging" &&
      length(output.bootstrap_phase_output.lineages) == 2
    )
    error_message = "bootstrap must expose one closed typed output with two platform lineages"
  }

  assert {
    condition = alltrue([
      for reference in values(output.bootstrap_phase_output.lineages) :
      contains(["platform", "application"], reference.state_owner)
    ])
    error_message = "bootstrap outputs must remain typed backend references"
  }

  assert {
    condition = (
      module.platform_state_bucket.policy_summary.uniform_bucket_level_access &&
      module.platform_state_bucket.policy_summary.public_access_prevention == "enforced" &&
      module.platform_state_bucket.policy_summary.object_versioning_enabled &&
      module.platform_state_bucket.policy_summary.noncurrent_version_retention_days >= 90 &&
      module.platform_state_bucket.policy_summary.newer_versions_to_retain >= 20 &&
      !module.platform_state_bucket.policy_summary.force_destroy &&
      module.platform_state_bucket.policy_summary.deletion_policy == "PREVENT" &&
      module.platform_state_bucket.policy_summary.iam_binding == "deferred"
    )
    error_message = "every state bucket must retain the complete recovery and non-destruction policy"
  }

  assert {
    condition = toset([
      for reference in values(output.bootstrap_phase_output.lineages) :
      "${reference.state_owner}:${reference.owner_id}:${reference.prefix}"
      ]) == toset([
      "platform:app-platform:bootstrap",
      "platform:app-platform:platform",
    ])
    error_message = "backend access intent must remain exclusive and root-scoped"
  }

  assert {
    condition = (
      module.platform_state_bucket.policy_summary.configured_labels.environment == "staging" &&
      module.platform_state_bucket.policy_summary.configured_labels.managed_by == "terraform" &&
      module.platform_state_bucket.policy_summary.configured_labels.state_owner == "platform" &&
      !contains(keys(module.platform_state_bucket.policy_summary.configured_labels), "application_id")
    )
    error_message = "state bucket labels must identify the exact environment and exclusive owner"
  }
}
