mock_provider "google" {
  override_during = plan
}

variables {
  platform_configuration = jsondecode(file("../../config/examples/platform-foundation.synthetic.v2.json"))
}

run "plans_identity_and_generation_foundation" {
  command = plan

  assert {
    condition = (
      output.foundation_phase_output.contract_version == 1 &&
      output.foundation_phase_output.output_kind == "platform-foundation" &&
      output.foundation_phase_output.environment == "staging" &&
      output.foundation_phase_output.state_owner == "platform" &&
      output.foundation_phase_output.owner_id == "app-platform" &&
      output.foundation_phase_output.project_number == "123456789012" &&
      output.foundation_phase_output.region == "us-west1" &&
      output.foundation_phase_output.hostname == "apps.example.invalid" &&
      output.foundation_phase_output.foundation.edge_caller_principal == "serviceAccount:app-platform-edge-caller@synthetic-platform.iam.gserviceaccount.com" &&
      output.foundation_phase_output.foundation.application_egress_mode == "all-traffic" &&
      output.foundation_phase_output.foundation.application_router_name == "app-platform-applications-us-west1-router" &&
      output.foundation_phase_output.foundation.application_nat_name == "app-platform-applications-us-west1-nat" &&
      output.shared_edge_phase_output == null
    )
    error_message = "foundation phase must expose only its closed non-secret typed output"
  }

  assert {
    condition = (
      module.platform_foundation.policy_summary.networking.application_egress_mode == "all-traffic" &&
      module.platform_foundation.policy_summary.networking.router_name == "app-platform-applications-us-west1-router" &&
      module.platform_foundation.policy_summary.networking.nat_name == "app-platform-applications-us-west1-nat" &&
      module.platform_foundation.policy_summary.networking.nat_type == "PUBLIC" &&
      module.platform_foundation.policy_summary.networking.nat_ip_allocation == "AUTO_ONLY" &&
      module.platform_foundation.policy_summary.networking.nat_source == "LIST_OF_SUBNETWORKS" &&
      length(module.platform_foundation.policy_summary.networking.nat_source_ranges) == 1 &&
      module.platform_foundation.policy_summary.networking.nat_source_ranges[0] == "ALL_IP_RANGES" &&
      length(module.platform_foundation.policy_summary.networking.nat_endpoint_types) == 1 &&
      module.platform_foundation.policy_summary.networking.nat_endpoint_types[0] == "ENDPOINT_TYPE_VM" &&
      module.platform_foundation.policy_summary.networking.nat_min_ports_per_vm == 64 &&
      module.platform_foundation.policy_summary.networking.nat_log_filter == "ERRORS_ONLY"
    )
    error_message = "application all-traffic egress must use one bounded logged Public NAT on the application subnet"
  }

  assert {
    condition = (
      module.platform_foundation.policy_summary.configuration_bucket.uniform_bucket_level_access &&
      module.platform_foundation.policy_summary.configuration_bucket.public_access_prevention == "enforced" &&
      module.platform_foundation.policy_summary.configuration_bucket.object_versioning_enabled &&
      module.platform_foundation.policy_summary.configuration_bucket.retention_period_seconds == 86400 &&
      !module.platform_foundation.policy_summary.configuration_bucket.force_destroy &&
      module.platform_foundation.policy_summary.configuration_bucket.deletion_policy == "PREVENT" &&
      module.platform_foundation.policy_summary.configuration_bucket.runtime_reader_role == "roles/storage.objectViewer" &&
      module.platform_foundation.policy_summary.configuration_bucket.configured_labels.environment == "staging" &&
      module.platform_foundation.policy_summary.configuration_bucket.configured_labels.managed_by == "terraform" &&
      module.platform_foundation.policy_summary.configuration_bucket.configured_labels.state_owner == "platform"
    )
    error_message = "configuration storage must remain private, versioned, retained, labelled, and runtime-readable only"
  }

  assert {
    condition = (
      module.platform_foundation.policy_summary.sessions.database_type == "FIRESTORE_NATIVE" &&
      module.platform_foundation.policy_summary.sessions.database_edition == "STANDARD" &&
      module.platform_foundation.policy_summary.sessions.app_engine_integration == "DISABLED" &&
      module.platform_foundation.policy_summary.sessions.pitr == "POINT_IN_TIME_RECOVERY_DISABLED" &&
      module.platform_foundation.policy_summary.sessions.backup == "disabled" &&
      module.platform_foundation.policy_summary.sessions.delete_protection == "DELETE_PROTECTION_ENABLED" &&
      module.platform_foundation.policy_summary.sessions.deletion_policy == "PREVENT" &&
      module.platform_foundation.policy_summary.sessions.ttl_enabled &&
      module.platform_foundation.policy_summary.sessions.absolute_lifetime_seconds == 28800 &&
      module.platform_foundation.policy_summary.sessions.runtime_data_role == "roles/datastore.user" &&
      !module.platform_foundation.policy_summary.sessions.asynchronous_ttl_is_authorization
    )
    error_message = "Platform Sessions must retain the eight-hour application expiry and bounded Firestore profile without backup or PITR"
  }

  assert {
    condition = (
      module.platform_foundation.policy_summary.signing.purpose == "ASYMMETRIC_SIGN" &&
      module.platform_foundation.policy_summary.signing.algorithm == "EC_SIGN_P256_SHA256" &&
      module.platform_foundation.policy_summary.signing.protection_level == "SOFTWARE" &&
      module.platform_foundation.policy_summary.signing.region == "us-west1" &&
      module.platform_foundation.policy_summary.signing.key_ring_id == "synthetic-platform" &&
      module.platform_foundation.policy_summary.signing.key_id == "synthetic-edge-signing" &&
      !module.platform_foundation.policy_summary.signing.automatic_rotation &&
      module.platform_foundation.policy_summary.signing.manual_rotation_days == 90 &&
      module.platform_foundation.policy_summary.signing.verification_overlap_hours == 24 &&
      module.platform_foundation.policy_summary.signing.active_version_count == 1 &&
      module.platform_foundation.policy_summary.signing.overlap_version_count == 1 &&
      module.platform_foundation.policy_summary.signing.runtime_signer_role == "roles/cloudkms.signerVerifier" &&
      !module.platform_foundation.policy_summary.signing.private_material_exportable
    )
    error_message = "signing must remain regional software ES256 with manual rotation and bounded verification overlap"
  }

  assert {
    condition = (
      module.platform_foundation.policy_summary.identities.separated &&
      !module.platform_foundation.policy_summary.identities.service_account_keys &&
      module.platform_foundation.policy_summary.identities.deletion_policy == "PREVENT" &&
      module.platform_foundation.policy_summary.oauth.secret_id == "synthetic-oauth-secret" &&
      module.platform_foundation.policy_summary.oauth.secret_container == "projects/synthetic-platform/secrets/synthetic-oauth-secret" &&
      !module.platform_foundation.policy_summary.oauth.secret_version_present &&
      !module.platform_foundation.policy_summary.oauth.secret_value_present &&
      module.platform_foundation.policy_summary.oauth.runtime_reader_role == "roles/secretmanager.secretAccessor" &&
      !module.platform_foundation.policy_summary.application_identity_management &&
      !module.platform_foundation.policy_summary.restricted_membership &&
      module.platform_foundation.policy_summary.compilation == "external-reviewed-input"
    )
    error_message = "edge identities and non-secret OAuth references must remain separated from applications, secret values, and compilation"
  }
}
