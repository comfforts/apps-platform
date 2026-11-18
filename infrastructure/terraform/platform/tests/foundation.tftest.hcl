mock_provider "google" {
  override_during = plan
}

variables {
  platform_configuration = jsondecode(file("../../config/examples/platform.synthetic.v1.json"))
  fixture_attachment_references = [
    jsondecode(file("../../config/examples/cross-state-attachment-public.synthetic.v1.json")),
    jsondecode(file("../../config/examples/cross-state-attachment.synthetic.v1.json")),
    jsondecode(file("../../config/examples/cross-state-attachment-restricted.synthetic.v1.json")),
  ]
}

run "plans_identity_and_generation_foundation" {
  command = plan

  assert {
    condition = (
      length(output.platform_reference_set) == 1 &&
      output.platform_reference_set.fixture_applications.reference_kind == "platform" &&
      output.platform_reference_set.fixture_applications.state_owner == "platform" &&
      output.platform_reference_set.fixture_applications.owner_id == "app-platform" &&
      output.platform_reference_set.fixture_applications.project_number == "123456789012" &&
      output.platform_reference_set.fixture_applications.region == "us-west1" &&
      output.platform_reference_set.fixture_applications.platform_issuer == "https://apps.example.invalid/_platform" &&
      output.platform_reference_set.fixture_applications.public_key_reference == "https://apps.example.invalid/.well-known/jwks.json" &&
      output.platform_reference_set.fixture_applications.edge_caller_principal == "serviceAccount:app-platform-edge-caller@synthetic-platform.iam.gserviceaccount.com"
    )
    error_message = "platform root must expose exactly one minimal typed Fixture Application reference"
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
      module.platform_foundation.policy_summary.configuration_bucket.configured_labels.environment == "qualification" &&
      module.platform_foundation.policy_summary.configuration_bucket.configured_labels.managed_by == "terraform" &&
      module.platform_foundation.policy_summary.configuration_bucket.configured_labels.state_owner == "platform"
    )
    error_message = "configuration storage must remain private, versioned, retained, labelled, and runtime-readable only"
  }

  assert {
    condition = (
      module.platform_foundation.policy_summary.registration_generation.source_revision == "0000000000000000000000000000000000000000" &&
      module.platform_foundation.policy_summary.registration_generation.generation == 1 &&
      module.platform_foundation.policy_summary.registration_generation.generation_digest == "sha256:0000000000000000000000000000000000000000000000000000000000000000" &&
      module.platform_foundation.policy_summary.registration_generation.content_digest == "sha256:1111111111111111111111111111111111111111111111111111111111111111" &&
      module.platform_foundation.policy_summary.registration_generation.object_name == "generations/1/compiled.json" &&
      module.platform_foundation.policy_summary.registration_generation.object_generation == 1 &&
      module.platform_foundation.policy_summary.registration_generation.immutable_object_shape &&
      module.platform_foundation.policy_summary.registration_generation.object_upload == "deferred" &&
      module.platform_foundation.policy_summary.registration_generation.activation == "deferred"
    )
    error_message = "generation metadata must remain immutable reviewed input without upload or activation"
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
      module.platform_foundation.policy_summary.oauth.client_id == "synthetic-client.apps.example.invalid" &&
      module.platform_foundation.policy_summary.oauth.client_secret_version_ref == "projects/synthetic-platform/secrets/synthetic-oauth-secret/versions/1" &&
      !module.platform_foundation.policy_summary.oauth.secret_value_present &&
      module.platform_foundation.policy_summary.oauth.runtime_reader_role == "roles/secretmanager.secretAccessor" &&
      !module.platform_foundation.policy_summary.application_identity_management &&
      !module.platform_foundation.policy_summary.restricted_membership &&
      module.platform_foundation.policy_summary.compilation == "external-reviewed-input"
    )
    error_message = "edge identities and non-secret OAuth references must remain separated from applications, secret values, and compilation"
  }
}
