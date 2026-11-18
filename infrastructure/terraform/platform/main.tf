module "platform_foundation" {
  source = "../modules/platform-foundation"

  foundation_configuration = {
    project_id              = var.platform_configuration.project_id
    project_number          = var.platform_configuration.project_number
    region                  = var.platform_configuration.region
    qualification_hostname  = var.platform_configuration.qualification_hostname
    configuration_bucket    = var.platform_configuration.configuration_bucket
    labels                  = var.platform_configuration.labels
    registration_generation = var.platform_configuration.registration_generation
    oauth = {
      client_id             = var.platform_configuration.oauth_client_id
      client_secret_version = var.platform_configuration.oauth_client_secret_version
    }
    signing = {
      key_version                = var.platform_configuration.signing_key_version
      manual_rotation_days       = 90
      verification_overlap_hours = 24
      active_version_count       = 1
      overlap_version_count      = 1
    }
    identities = {
      edge_runtime_account_id = "app-platform-edge-runtime"
      edge_caller_account_id  = "app-platform-edge-caller"
    }
    sessions = {
      collection_name           = "platform-sessions"
      expiration_field          = "expires_at"
      absolute_lifetime_seconds = 28800
    }
  }
}
