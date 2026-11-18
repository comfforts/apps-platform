locals {
  signing_key_parts  = split("/", var.foundation_configuration.signing.key_version)
  oauth_secret_parts = split("/", var.foundation_configuration.oauth.client_secret_version)

  signing_key_ring_name = local.signing_key_parts[5]
  signing_key_name      = local.signing_key_parts[7]
  oauth_secret_id       = join("/", slice(local.oauth_secret_parts, 0, 4))

  edge_runtime_principal = "serviceAccount:${var.foundation_configuration.identities.edge_runtime_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
  edge_caller_principal  = "serviceAccount:${var.foundation_configuration.identities.edge_caller_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
}

resource "google_storage_bucket" "configuration" {
  project  = var.foundation_configuration.project_id
  name     = var.foundation_configuration.configuration_bucket
  location = upper(var.foundation_configuration.region)
  labels   = var.foundation_configuration.labels

  storage_class               = "STANDARD"
  force_destroy               = false
  deletion_policy             = "PREVENT"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  retention_policy {
    retention_period = 86400
    is_locked        = false
  }
}

resource "google_service_account" "edge_runtime" {
  project      = var.foundation_configuration.project_id
  account_id   = var.foundation_configuration.identities.edge_runtime_account_id
  display_name = "App Platform edge runtime"
  description  = "Platform-owned Shared Edge runtime identity."

  deletion_policy = "PREVENT"
}

resource "google_service_account" "edge_caller" {
  project      = var.foundation_configuration.project_id
  account_id   = var.foundation_configuration.identities.edge_caller_account_id
  display_name = "App Platform edge caller"
  description  = "Platform-owned caller identity for Fixture Application invocation."

  deletion_policy = "PREVENT"
}

resource "google_storage_bucket_iam_member" "edge_configuration_reader" {
  bucket = google_storage_bucket.configuration.name
  role   = "roles/storage.objectViewer"
  member = local.edge_runtime_principal
}

resource "google_firestore_database" "sessions" {
  project     = var.foundation_configuration.project_id
  name        = "(default)"
  location_id = var.foundation_configuration.region
  type        = "FIRESTORE_NATIVE"

  database_edition                  = "STANDARD"
  app_engine_integration_mode       = "DISABLED"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
  delete_protection_state           = "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = "PREVENT"
}

resource "google_firestore_field" "session_expiration" {
  project    = var.foundation_configuration.project_id
  database   = google_firestore_database.sessions.name
  collection = var.foundation_configuration.sessions.collection_name
  field      = var.foundation_configuration.sessions.expiration_field

  ttl_config {}
  index_config {}

  deletion_policy = "PREVENT"
}

resource "google_kms_key_ring" "assertion_signing" {
  project  = var.foundation_configuration.project_id
  location = var.foundation_configuration.region
  name     = local.signing_key_ring_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "assertion_signing" {
  name     = local.signing_key_name
  key_ring = google_kms_key_ring.assertion_signing.id
  labels   = var.foundation_configuration.labels
  purpose  = "ASYMMETRIC_SIGN"

  skip_initial_version_creation = false
  deletion_policy               = "PREVENT"

  version_template {
    algorithm        = "EC_SIGN_P256_SHA256"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key_iam_member" "edge_signer" {
  crypto_key_id = google_kms_crypto_key.assertion_signing.id
  role          = "roles/cloudkms.signerVerifier"
  member        = local.edge_runtime_principal
}

resource "google_secret_manager_secret_iam_member" "edge_oauth_secret_reader" {
  project   = var.foundation_configuration.project_id
  secret_id = local.oauth_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.edge_runtime_principal
}
