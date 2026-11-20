output "foundation_reference" {
  description = "Closed non-secret references created by the foundation phase."
  value = {
    configuration_bucket  = google_storage_bucket.configuration.name
    edge_caller_principal = local.edge_caller_principal
    edge_runtime_email    = google_service_account.edge_runtime.email
    oauth_secret_id       = google_secret_manager_secret.edge_oauth.id
    session_database      = google_firestore_database.sessions.name
    signing_key_id        = google_kms_crypto_key.assertion_signing.id
  }
}

output "policy_summary" {
  description = "Internal mocked-plan surface for foundation controls."
  value = {
    enabled_services = sort(tolist(local.platform_services))
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
      key_ring_id                 = var.foundation_configuration.signing_key_ring_id
      key_id                      = var.foundation_configuration.signing_key_id
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
      secret_id              = var.foundation_configuration.oauth_secret_id
      secret_container       = "projects/${var.foundation_configuration.project_id}/secrets/${var.foundation_configuration.oauth_secret_id}"
      secret_version_present = false
      secret_value_present   = false
      runtime_reader_role    = "roles/secretmanager.secretAccessor"
      deletion_protection    = true
    }
    application_identity_management = false
    restricted_membership           = false
    registration_generation         = "later-stage-input"
    compilation                     = "external-reviewed-input"
  }
}
