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

locals {
  edge_service_name = "app-platform-edge"
  edge_revision_binding_digest = sha256(jsonencode({
    source_revision                 = var.platform_configuration.registration_generation.source_revision
    compiler_version                = 1
    registration_generation         = var.platform_configuration.registration_generation.generation
    generation_digest               = var.platform_configuration.registration_generation.generation_digest
    configuration_content_digest    = var.platform_configuration.registration_generation.content_digest
    configuration_object_name       = var.platform_configuration.registration_generation.object_name
    configuration_object_generation = var.platform_configuration.registration_generation.object_generation
    configuration_bucket            = var.platform_configuration.configuration_bucket
    edge_image_digest               = var.platform_configuration.edge_image_digest
    qualification_hostname          = var.platform_configuration.qualification_hostname
    edge_runtime_identity           = "app-platform-edge-runtime"
    oauth_client_id                 = var.platform_configuration.oauth_client_id
    oauth_client_secret_version     = var.platform_configuration.oauth_client_secret_version
    signing_key_version             = var.platform_configuration.signing_key_version
    identity_contract_version       = 1
    attachment_adapter_version      = "gcp-cloud-run-v1"
    platform_configuration_version  = var.platform_configuration.contract_version
  }))
  edge_candidate_revision = "${local.edge_service_name}-g${var.platform_configuration.registration_generation.generation}-${substr(local.edge_revision_binding_digest, 0, 12)}"
}

module "shared_edge" {
  source = "../modules/shared-edge"

  edge_configuration = {
    project_id              = var.platform_configuration.project_id
    region                  = var.platform_configuration.region
    qualification_hostname  = var.platform_configuration.qualification_hostname
    labels                  = var.platform_configuration.labels
    service_name            = local.edge_service_name
    candidate_revision      = local.edge_candidate_revision
    runtime_identity_email  = module.platform_foundation.edge_runtime_email
    image_digest            = var.platform_configuration.edge_image_digest
    configuration_bucket    = var.platform_configuration.configuration_bucket
    registration_generation = var.platform_configuration.registration_generation
    binding_versions = {
      compiler               = 1
      identity_contract      = 1
      attachment_adapter     = "gcp-cloud-run-v1"
      platform_configuration = var.platform_configuration.contract_version
    }
    oauth = {
      client_id             = var.platform_configuration.oauth_client_id
      client_secret_version = var.platform_configuration.oauth_client_secret_version
    }
    signing_key_version   = var.platform_configuration.signing_key_version
    attachment_references = [for value in var.fixture_attachment_references : value.reference]
  }
}

module "platform_controls" {
  source = "../modules/platform-controls"

  controls_configuration = {
    project_id                = var.platform_configuration.project_id
    project_number            = var.platform_configuration.project_number
    region                    = var.platform_configuration.region
    log_bucket                = var.platform_configuration.log_bucket
    evidence_bucket           = var.platform_configuration.evidence_bucket
    artifact_repository_id    = split("/", var.platform_configuration.edge_image_digest)[2]
    billing_account_reference = var.platform_configuration.billing_account_reference
    notification_destination  = var.platform_configuration.notification_destination
    owner_principal           = "projectOwner:${var.platform_configuration.project_id}"
    labels                    = var.platform_configuration.labels
    artifact_packages = [
      "fixture-authenticated",
      "fixture-public",
      "fixture-restricted",
      "shared-edge",
    ]
  }
}
