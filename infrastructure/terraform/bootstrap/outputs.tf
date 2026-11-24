output "bootstrap_phase_output" {
  description = "Closed non-secret output for two platform lineages over one backend bucket."
  value = {
    contract_version = 1
    output_kind      = "bootstrap"
    environment      = "staging"
    project_id       = var.backend_configuration.project_id
    region           = var.backend_configuration.region
    state_owner      = "platform"
    owner_id         = "app-platform"
    lineages = {
      bootstrap = {
        state_owner = "platform"
        owner_id    = "app-platform"
        bucket      = module.platform_state_bucket.bucket_name
        prefix      = "bootstrap"
      }
      platform = {
        state_owner = "platform"
        owner_id    = "app-platform"
        bucket      = module.platform_state_bucket.bucket_name
        prefix      = "platform"
      }
    }
  }

  precondition {
    condition     = module.platform_state_bucket.bucket_name == local.platform_state_bucket.bucket_name
    error_message = "bootstrap_phase_output requires exactly one platform backend bucket."
  }

}
