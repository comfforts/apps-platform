output "bootstrap_phase_output" {
  description = "Closed non-secret output for five lineages over four backend buckets."
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
        bucket      = module.state_bucket["app-platform"].bucket_name
        prefix      = "bootstrap"
      }
      platform = {
        state_owner = "platform"
        owner_id    = "app-platform"
        bucket      = module.state_bucket["app-platform"].bucket_name
        prefix      = "platform"
      }
      "fixture-public" = {
        state_owner = "application"
        owner_id    = "fixture-public"
        bucket      = module.state_bucket["fixture-public"].bucket_name
        prefix      = "fixtures/fixture-public"
      }
      "fixture-authenticated" = {
        state_owner = "application"
        owner_id    = "fixture-authenticated"
        bucket      = module.state_bucket["fixture-authenticated"].bucket_name
        prefix      = "fixtures/fixture-authenticated"
      }
      "fixture-restricted" = {
        state_owner = "application"
        owner_id    = "fixture-restricted"
        bucket      = module.state_bucket["fixture-restricted"].bucket_name
        prefix      = "fixtures/fixture-restricted"
      }
    }
  }

  precondition {
    condition     = length(module.state_bucket) == 4
    error_message = "bootstrap_phase_output requires exactly four exclusive backend buckets."
  }

}
