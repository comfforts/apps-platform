locals {
  foundation  = var.platform_configuration.foundation
  shared_edge = var.platform_configuration.shared_edge

  edge_service_name = "app-platform-edge"
  edge_revision_binding_digest = var.platform_configuration.phase == "shared-edge" ? sha256(jsonencode({
    source_revision                 = local.shared_edge.registration_generation.source_revision
    compiler_version                = 1
    registration_generation         = local.shared_edge.registration_generation.generation
    generation_digest               = local.shared_edge.registration_generation.generation_digest
    configuration_content_digest    = local.shared_edge.registration_generation.content_digest
    configuration_object_name       = local.shared_edge.registration_generation.object_name
    configuration_object_generation = local.shared_edge.registration_generation.object_generation
    configuration_bucket            = local.foundation.configuration_bucket
    edge_image_digest               = local.shared_edge.edge_image_digest
    hostname                        = local.foundation.hostname
    edge_runtime_identity           = "app-platform-edge-runtime"
    oauth_client_id                 = local.shared_edge.oauth_client_id
    oauth_client_secret_version     = local.shared_edge.oauth_client_secret_version
    signing_key_version             = local.shared_edge.signing_key_version
    operator_identity               = local.shared_edge.operator_identity
    identity_contract_version       = 1
    attachment_adapter_version      = "gcp-cloud-run-v1"
    platform_configuration_version  = var.platform_configuration.contract_version
  })) : null
  edge_candidate_revision = var.platform_configuration.phase == "shared-edge" ? "${local.edge_service_name}-g${local.shared_edge.registration_generation.generation}-${substr(local.edge_revision_binding_digest, 0, 12)}" : null
}

moved {
  from = module.platform_foundation.google_project_service.platform["iamcredentials.googleapis.com"]
  to   = module.shared_edge[0].google_project_service.iam_credentials
}

moved {
  from = module.platform_foundation.google_service_account_iam_member.edge_caller_token_creator[0]
  to   = module.shared_edge[0].google_service_account_iam_member.edge_caller_token_creator
}

module "platform_foundation" {
  source = "../modules/platform-foundation"

  destruction_mode = var.platform_configuration.destruction_mode

  foundation_configuration = {
    project_id           = local.foundation.project_id
    project_number       = local.foundation.project_number
    region               = local.foundation.region
    hostname             = local.foundation.hostname
    configuration_bucket = local.foundation.configuration_bucket
    oauth_secret_id      = local.foundation.oauth_secret_id
    signing_key_ring_id  = local.foundation.signing_key_ring_id
    signing_key_id       = local.foundation.signing_key_id
    labels               = var.platform_configuration.labels
    signing = {
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

module "platform_controls" {
  source = "../modules/platform-controls"

  destruction_mode = var.platform_configuration.destruction_mode

  depends_on = [module.platform_foundation]

  controls_configuration = {
    project_id                = local.foundation.project_id
    project_number            = local.foundation.project_number
    region                    = local.foundation.region
    log_bucket                = local.foundation.log_bucket
    evidence_bucket           = local.foundation.evidence_bucket
    artifact_repository_id    = local.foundation.artifact_repository_id
    billing_account_reference = local.foundation.billing_account_reference
    notification_email        = local.foundation.notification_email
    owner_principal           = "user:${local.foundation.notification_email}"
    labels                    = var.platform_configuration.labels
    artifact_packages = [
      "shared-edge",
    ]
  }
}

module "shared_edge" {
  source = "../modules/shared-edge"
  count  = var.platform_configuration.phase == "shared-edge" ? 1 : 0

  depends_on = [module.platform_foundation]

  destruction_enabled = var.platform_configuration.destruction_mode == "shared-edge-unlock"

  edge_configuration = {
    project_id                     = local.foundation.project_id
    project_number                 = local.foundation.project_number
    region                         = local.foundation.region
    qualification_hostname         = local.foundation.hostname
    labels                         = var.platform_configuration.labels
    service_name                   = local.edge_service_name
    candidate_revision             = local.edge_candidate_revision
    runtime_identity_email         = module.platform_foundation.foundation_reference.edge_runtime_email
    edge_caller_principal          = module.platform_foundation.foundation_reference.edge_caller_principal
    edge_caller_service_account_id = module.platform_foundation.foundation_reference.edge_caller_service_account_id
    image_digest                   = local.shared_edge.edge_image_digest
    configuration_bucket           = local.foundation.configuration_bucket
    shared_network_reference       = module.platform_foundation.foundation_reference.shared_network_reference
    application_subnet_reference   = module.platform_foundation.foundation_reference.application_subnet_reference
    registration_generation        = local.shared_edge.registration_generation
    binding_versions = {
      compiler               = 1
      identity_contract      = 1
      attachment_adapter     = "gcp-cloud-run-v1"
      platform_configuration = var.platform_configuration.contract_version
    }
    oauth = {
      client_id             = local.shared_edge.oauth_client_id
      client_secret_version = local.shared_edge.oauth_client_secret_version
    }
    operator_identity   = local.shared_edge.operator_identity
    signing_key_version = local.shared_edge.signing_key_version
    tls_enabled         = local.shared_edge.tls_enabled
  }
}
