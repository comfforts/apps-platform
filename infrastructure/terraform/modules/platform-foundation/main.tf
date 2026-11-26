locals {
  destruction_enabled            = contains(["platform-unlock", "retained"], var.destruction_mode)
  retained_only                  = var.destruction_mode == "retained"
  edge_runtime_email             = "${var.foundation_configuration.identities.edge_runtime_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
  edge_runtime_principal         = "serviceAccount:${var.foundation_configuration.identities.edge_runtime_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
  edge_caller_principal          = "serviceAccount:${var.foundation_configuration.identities.edge_caller_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
  edge_caller_service_account_id = "projects/${var.foundation_configuration.project_id}/serviceAccounts/${var.foundation_configuration.identities.edge_caller_account_id}@${var.foundation_configuration.project_id}.iam.gserviceaccount.com"
  platform_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudkms.googleapis.com",
    "compute.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ])
  shared_network_name        = "app-platform-shared"
  application_subnet_name    = "app-platform-applications-${var.foundation_configuration.region}"
  application_subnet_cidr    = "10.20.0.0/24"
  application_router_name    = "app-platform-applications-${var.foundation_configuration.region}-router"
  application_nat_name       = "app-platform-applications-${var.foundation_configuration.region}-nat"
  session_database_reference = "projects/${var.foundation_configuration.project_id}/databases/(default)"
  member_database_reference  = "projects/${var.foundation_configuration.project_id}/databases/${var.foundation_configuration.member_directory.database_name}"
  member_runtime_permissions = toset([
    "datastore.entities.get",
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

resource "google_compute_shared_vpc_host_project" "platform" {
  project = var.foundation_configuration.project_id

  depends_on = [google_project_service.platform]
}

resource "google_compute_network" "shared" {
  project                 = var.foundation_configuration.project_id
  name                    = local.shared_network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_compute_shared_vpc_host_project.platform]
}

resource "google_compute_subnetwork" "applications" {
  project                  = var.foundation_configuration.project_id
  name                     = local.application_subnet_name
  region                   = var.foundation_configuration.region
  network                  = google_compute_network.shared.id
  ip_cidr_range            = local.application_subnet_cidr
  private_ip_google_access = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_compute_router" "applications" {
  count = local.retained_only ? 0 : 1

  project = var.foundation_configuration.project_id
  name    = local.application_router_name
  region  = var.foundation_configuration.region
  network = google_compute_network.shared.id
}

resource "google_compute_router_nat" "applications" {
  count = local.retained_only ? 0 : 1

  project = var.foundation_configuration.project_id
  name    = local.application_nat_name
  router  = google_compute_router.applications[0].name
  region  = google_compute_router.applications[0].region

  type                                = "PUBLIC"
  nat_ip_allocate_option              = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat  = "LIST_OF_SUBNETWORKS"
  endpoint_types                      = ["ENDPOINT_TYPE_VM"]
  enable_dynamic_port_allocation      = false
  enable_endpoint_independent_mapping = true
  min_ports_per_vm                    = 64

  subnetwork {
    name                    = google_compute_subnetwork.applications.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
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

resource "google_project_iam_member" "edge_session_store" {
  count = local.retained_only ? 0 : 1

  project = var.foundation_configuration.project_id
  role    = "roles/datastore.user"
  member  = local.edge_runtime_principal

  condition {
    title       = "app_platform_session_database"
    description = "Confines the Shared Edge session data role to the default Firestore database."
    expression  = "resource.name == '${local.session_database_reference}'"
  }

  depends_on = [
    google_firestore_database.sessions,
    google_service_account.edge_runtime,
  ]
}

resource "google_firestore_database" "member_directory" {
  count = local.retained_only ? 0 : 1

  project     = var.foundation_configuration.project_id
  name        = var.foundation_configuration.member_directory.database_name
  location_id = var.foundation_configuration.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.platform]

  database_edition                  = "STANDARD"
  app_engine_integration_mode       = "DISABLED"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
  delete_protection_state           = local.destruction_enabled ? "DELETE_PROTECTION_DISABLED" : "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = local.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_project_iam_custom_role" "edge_member_directory_reader" {
  count = local.retained_only ? 0 : 1

  project     = var.foundation_configuration.project_id
  role_id     = var.foundation_configuration.member_directory.runtime_role_id
  title       = "App Platform member reader"
  description = "Exact-document read access for Shared Edge member admission."
  permissions = local.member_runtime_permissions
  stage       = "GA"
}

resource "google_project_iam_member" "edge_member_directory_reader" {
  count = local.retained_only ? 0 : 1

  project = var.foundation_configuration.project_id
  role    = google_project_iam_custom_role.edge_member_directory_reader[0].name
  member  = local.edge_runtime_principal

  condition {
    title       = "app_platform_member_database"
    description = "Confines exact member reads to the isolated member directory database."
    expression  = "resource.name == '${local.member_database_reference}'"
  }

  depends_on = [
    google_firestore_database.member_directory,
    google_service_account.edge_runtime,
  ]
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
