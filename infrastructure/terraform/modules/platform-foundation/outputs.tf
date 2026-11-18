output "edge_caller_principal" {
  description = "Deterministic non-secret caller principal for typed fixture references."
  value       = local.edge_caller_principal
}

output "policy_summary" {
  description = "Internal plan-test surface for identity, generation, session, and signing controls."
  value = {
    configuration_bucket = {
      configured_name             = var.foundation_configuration.configuration_bucket
      configured_labels           = var.foundation_configuration.labels
      uniform_bucket_level_access = true
      public_access_prevention    = "enforced"
      object_versioning_enabled   = true
      retention_period_seconds    = 86400
      force_destroy               = false
      deletion_policy             = "PREVENT"
      runtime_reader_role         = "roles/storage.objectViewer"
    }
    registration_generation = merge(var.foundation_configuration.registration_generation, {
      immutable_object_shape = true
      object_upload          = "deferred"
      activation             = "deferred"
    })
    sessions = {
      database_type                     = "FIRESTORE_NATIVE"
      database_edition                  = "STANDARD"
      app_engine_integration            = "DISABLED"
      pitr                              = "POINT_IN_TIME_RECOVERY_DISABLED"
      backup                            = "disabled"
      delete_protection                 = "DELETE_PROTECTION_ENABLED"
      deletion_policy                   = "PREVENT"
      collection_name                   = var.foundation_configuration.sessions.collection_name
      expiration_field                  = var.foundation_configuration.sessions.expiration_field
      ttl_enabled                       = true
      absolute_lifetime_seconds         = var.foundation_configuration.sessions.absolute_lifetime_seconds
      asynchronous_ttl_is_authorization = false
    }
    signing = {
      configured_key_version      = var.foundation_configuration.signing.key_version
      purpose                     = "ASYMMETRIC_SIGN"
      algorithm                   = "EC_SIGN_P256_SHA256"
      protection_level            = "SOFTWARE"
      region                      = var.foundation_configuration.region
      automatic_rotation          = false
      manual_rotation_days        = var.foundation_configuration.signing.manual_rotation_days
      verification_overlap_hours  = var.foundation_configuration.signing.verification_overlap_hours
      active_version_count        = var.foundation_configuration.signing.active_version_count
      overlap_version_count       = var.foundation_configuration.signing.overlap_version_count
      runtime_signer_role         = "roles/cloudkms.signerVerifier"
      private_material_exportable = false
    }
    identities = {
      edge_runtime_account_id = var.foundation_configuration.identities.edge_runtime_account_id
      edge_runtime_principal  = local.edge_runtime_principal
      edge_caller_account_id  = var.foundation_configuration.identities.edge_caller_account_id
      edge_caller_principal   = local.edge_caller_principal
      separated               = local.edge_runtime_principal != local.edge_caller_principal
      deletion_policy         = "PREVENT"
      service_account_keys    = false
    }
    oauth = {
      client_id                 = var.foundation_configuration.oauth.client_id
      client_secret_version_ref = var.foundation_configuration.oauth.client_secret_version
      secret_value_present      = false
      runtime_reader_role       = "roles/secretmanager.secretAccessor"
    }
    application_identity_management = false
    restricted_membership           = false
    compilation                     = "external-reviewed-input"
  }
}
