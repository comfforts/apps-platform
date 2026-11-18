output "platform_reference_set" {
  description = "Minimal typed non-secret Platform State references for Fixture Application roots."
  value = {
    fixture_applications = {
      reference_kind        = "platform"
      state_owner           = "platform"
      owner_id              = "app-platform"
      project_number        = var.platform_configuration.project_number
      region                = var.platform_configuration.region
      platform_issuer       = "https://${var.platform_configuration.qualification_hostname}/_platform"
      public_key_reference  = "https://${var.platform_configuration.qualification_hostname}/.well-known/jwks.json"
      edge_caller_principal = module.platform_foundation.edge_caller_principal
    }
  }

  precondition {
    condition = (
      module.platform_foundation.policy_summary.identities.separated &&
      !module.platform_foundation.policy_summary.identities.service_account_keys
    )
    error_message = "platform references require separate keyless edge runtime and caller identities."
  }
}
