output "foundation_phase_output" {
  description = "Closed non-secret foundation output for later lifecycle stages."
  value = {
    contract_version = 1
    output_kind      = "platform-foundation"
    environment      = var.platform_configuration.environment
    state_owner      = "platform"
    owner_id         = "app-platform"
    project_id       = local.foundation.project_id
    project_number   = local.foundation.project_number
    region           = local.foundation.region
    hostname         = local.foundation.hostname
    foundation       = module.platform_foundation.foundation_reference
    controls         = module.platform_controls.foundation_reference
  }

  precondition {
    condition = (
      module.platform_foundation.policy_summary.identities.separated &&
      !module.platform_foundation.policy_summary.identities.service_account_keys &&
      !module.platform_foundation.policy_summary.oauth.secret_version_present &&
      !module.platform_foundation.policy_summary.oauth.secret_value_present
    )
    error_message = "foundation output requires separate keyless identities and a secret container without secret material."
  }
}

output "shared_edge_phase_output" {
  description = "Closed non-secret Shared Edge output, absent during the foundation phase."
  value = var.platform_configuration.phase == "shared-edge" ? {
    contract_version = 1
    output_kind      = "shared-edge"
    environment      = var.platform_configuration.environment
    state_owner      = "platform"
    owner_id         = "app-platform"
    project_id       = local.foundation.project_id
    region           = local.foundation.region
    edge             = module.shared_edge[0].edge_reference
  } : null
}
