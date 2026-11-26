output "foundation_reference" {
  description = "Closed non-secret references created by the foundation phase."
  value = {
    configuration_bucket           = google_storage_bucket.configuration.name
    edge_caller_principal          = local.edge_caller_principal
    edge_caller_service_account_id = local.retained_only ? null : local.edge_caller_service_account_id
    edge_runtime_email             = local.retained_only ? null : local.edge_runtime_email
    oauth_secret_id                = try(google_secret_manager_secret.edge_oauth[0].id, null)
    session_database               = try(google_firestore_database.sessions[0].name, null)
    member_directory = local.retained_only ? null : {
      database_name              = google_firestore_database.member_directory[0].name
      database_reference         = local.member_database_reference
      directory_collection_name  = var.foundation_configuration.member_directory.directory_collection_name
      member_collection_name     = var.foundation_configuration.member_directory.member_collection_name
      document_contract_version  = 1
      member_reference_scheme    = "pmr1-sha256"
      required_composite_indexes = []
      runtime_principal          = local.edge_runtime_principal
      runtime_role               = "projects/${var.foundation_configuration.project_id}/roles/${var.foundation_configuration.member_directory.runtime_role_id}"
      runtime_permissions        = sort(tolist(local.member_runtime_permissions))
      runtime_condition          = "resource.name == '${local.member_database_reference}'"
      runtime_can_enumerate      = false
      runtime_can_mutate         = false
      terraform_manages_members  = false
    }
    signing_key_id               = google_kms_crypto_key.assertion_signing.id
    shared_network_reference     = google_compute_network.shared.id
    application_subnet_reference = google_compute_subnetwork.applications.id
    application_subnet_cidr      = google_compute_subnetwork.applications.ip_cidr_range
    application_egress_mode      = local.retained_only ? null : "all-traffic"
    application_router_name      = try(google_compute_router.applications[0].name, null)
    application_nat_name         = try(google_compute_router_nat.applications[0].name, null)
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
      delete_protection                 = local.destruction_enabled ? "DELETE_PROTECTION_DISABLED" : "DELETE_PROTECTION_ENABLED"
      deletion_policy                   = local.destruction_enabled ? "DELETE" : "PREVENT"
      collection_name                   = var.foundation_configuration.sessions.collection_name
      expiration_field                  = var.foundation_configuration.sessions.expiration_field
      ttl_enabled                       = true
      absolute_lifetime_seconds         = var.foundation_configuration.sessions.absolute_lifetime_seconds
      runtime_data_role                 = "roles/datastore.user"
      runtime_condition                 = "resource.name == '${local.session_database_reference}'"
      asynchronous_ttl_is_authorization = false
    }
    member_directory = {
      database_name              = var.foundation_configuration.member_directory.database_name
      database_reference         = local.member_database_reference
      database_type              = "FIRESTORE_NATIVE"
      database_edition           = "STANDARD"
      app_engine_integration     = "DISABLED"
      pitr                       = "POINT_IN_TIME_RECOVERY_DISABLED"
      backup                     = "disabled"
      delete_protection          = local.destruction_enabled ? "DELETE_PROTECTION_DISABLED" : "DELETE_PROTECTION_ENABLED"
      deletion_policy            = local.destruction_enabled ? "DELETE" : "PREVENT"
      directory_collection_name  = var.foundation_configuration.member_directory.directory_collection_name
      member_collection_name     = var.foundation_configuration.member_directory.member_collection_name
      namespaces_separated       = var.foundation_configuration.member_directory.member_collection_name != var.foundation_configuration.sessions.collection_name
      document_contract_version  = 1
      member_reference_scheme    = "pmr1-sha256"
      required_composite_indexes = []
      runtime_role_id            = var.foundation_configuration.member_directory.runtime_role_id
      runtime_role               = "projects/${var.foundation_configuration.project_id}/roles/${var.foundation_configuration.member_directory.runtime_role_id}"
      runtime_permissions        = sort(tolist(local.member_runtime_permissions))
      runtime_condition          = "resource.name == '${local.member_database_reference}'"
      runtime_can_enumerate      = false
      runtime_can_mutate         = false
      terraform_manages_members  = false
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
      deletion_policy         = local.destruction_enabled ? "DELETE" : "PREVENT"
      service_account_keys    = false
    }
    networking = {
      shared_vpc_host_project = var.foundation_configuration.project_id
      network_name            = local.shared_network_name
      network_reference       = google_compute_network.shared.id
      subnetwork_name         = local.application_subnet_name
      subnetwork_reference    = google_compute_subnetwork.applications.id
      subnetwork_cidr         = local.application_subnet_cidr
      private_google_access   = true
      application_connection  = "explicit-platform-connect-project"
      application_egress_mode = local.retained_only ? null : "all-traffic"
      router_name             = try(google_compute_router.applications[0].name, null)
      nat_name                = try(google_compute_router_nat.applications[0].name, null)
      nat_type                = local.retained_only ? null : "PUBLIC"
      nat_ip_allocation       = local.retained_only ? null : "AUTO_ONLY"
      nat_source              = local.retained_only ? null : "LIST_OF_SUBNETWORKS"
      nat_source_ranges       = local.retained_only ? [] : ["ALL_IP_RANGES"]
      nat_endpoint_types      = local.retained_only ? [] : ["ENDPOINT_TYPE_VM"]
      nat_min_ports_per_vm    = local.retained_only ? null : 64
      nat_log_filter          = local.retained_only ? null : "ERRORS_ONLY"
    }
    oauth = {
      secret_id              = var.foundation_configuration.oauth_secret_id
      secret_container       = "projects/${var.foundation_configuration.project_id}/secrets/${var.foundation_configuration.oauth_secret_id}"
      secret_version_present = false
      secret_value_present   = false
      runtime_reader_role    = "roles/secretmanager.secretAccessor"
      deletion_protection    = !local.destruction_enabled
    }
    application_identity_management = false
    restricted_membership           = false
    registration_generation         = "later-stage-input"
    compilation                     = "external-reviewed-input"
    destruction_mode                = var.destruction_mode
  }
}
