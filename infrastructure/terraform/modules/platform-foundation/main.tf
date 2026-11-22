locals {
  destruction_enabled    = contains(["platform-unlock", "retained"], var.destruction_mode)
  retained_only          = var.destruction_mode == "retained"
  edge_runtime_principal = "serviceAccount:${var.foundation_configuration.identities.edge_runtime_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
  edge_caller_principal  = "serviceAccount:${var.foundation_configuration.identities.edge_caller_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
  platform_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudkms.googleapis.com",
    "compute.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ])
}

resource "google_project_service" "platform" {
  for_each = local.platform_services

  project = var.foundation_configuration.project_id
  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}

resource "google_storage_bucket" "configuration" {
  project  = var.foundation_configuration.project_id
  name     = var.foundation_configuration.configuration_bucket
  location = upper(var.foundation_configuration.region)
  labels   = var.foundation_configuration.labels

  depends_on = [google_project_service.platform]

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
  count = local.retained_only ? 0 : 1

  project      = var.foundation_configuration.project_id
  account_id   = var.foundation_configuration.identities.edge_runtime_account_id
  display_name = "App Platform edge runtime"
  description  = "Platform-owned Shared Edge runtime identity."

  depends_on = [google_project_service.platform]

  deletion_policy = local.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_service_account" "edge_caller" {
  count = local.retained_only ? 0 : 1

  project      = var.foundation_configuration.project_id
  account_id   = var.foundation_configuration.identities.edge_caller_account_id
  display_name = "App Platform edge caller"
  description  = "Platform-owned caller identity for Fixture Application invocation."

  depends_on = [google_project_service.platform]

  deletion_policy = local.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_storage_bucket_iam_member" "edge_configuration_reader" {
  count = local.retained_only ? 0 : 1

  bucket = google_storage_bucket.configuration.name
  role   = "roles/storage.objectViewer"
  member = local.edge_runtime_principal

  depends_on = [google_service_account.edge_runtime]
}

resource "google_firestore_database" "sessions" {
  count = local.retained_only ? 0 : 1

  project     = var.foundation_configuration.project_id
  name        = "(default)"
  location_id = var.foundation_configuration.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.platform]

  database_edition                  = "STANDARD"
  app_engine_integration_mode       = "DISABLED"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
  delete_protection_state           = local.destruction_enabled ? "DELETE_PROTECTION_DISABLED" : "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = local.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_firestore_field" "session_expiration" {
  count = local.retained_only ? 0 : 1

  project    = var.foundation_configuration.project_id
  database   = google_firestore_database.sessions[0].name
  collection = var.foundation_configuration.sessions.collection_name
  field      = var.foundation_configuration.sessions.expiration_field

  ttl_config {}
  index_config {}

  deletion_policy = local.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_kms_key_ring" "assertion_signing" {
  project  = var.foundation_configuration.project_id
  location = var.foundation_configuration.region
  name     = var.foundation_configuration.signing_key_ring_id

  depends_on = [google_project_service.platform]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "assertion_signing" {
  name     = var.foundation_configuration.signing_key_id
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
  count = local.retained_only ? 0 : 1

  crypto_key_id = google_kms_crypto_key.assertion_signing.id
  role          = "roles/cloudkms.signerVerifier"
  member        = local.edge_runtime_principal

  depends_on = [google_service_account.edge_runtime]
}

resource "google_secret_manager_secret" "edge_oauth" {
  count = local.retained_only ? 0 : 1

  project   = var.foundation_configuration.project_id
  secret_id = var.foundation_configuration.oauth_secret_id
  labels    = var.foundation_configuration.labels

  depends_on = [google_project_service.platform]

  deletion_protection = !local.destruction_enabled

  replication {
    user_managed {
      replicas {
        location = var.foundation_configuration.region
      }
    }
  }
}

resource "google_secret_manager_secret_iam_member" "edge_oauth_secret_reader" {
  count = local.retained_only ? 0 : 1

  project   = var.foundation_configuration.project_id
  secret_id = google_secret_manager_secret.edge_oauth[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.edge_runtime_principal

  depends_on = [google_service_account.edge_runtime]
}
