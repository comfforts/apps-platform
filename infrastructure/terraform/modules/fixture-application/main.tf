resource "google_service_account" "runtime" {
  project      = var.runtime_configuration.project_id
  account_id   = var.runtime_configuration.runtime_identity_account_id
  display_name = "${var.runtime_configuration.application_id} runtime"
  description  = "Application-owned qualification runtime identity for ${var.runtime_configuration.application_id}."

  deletion_policy = var.runtime_configuration.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_cloud_run_v2_service" "runtime" {
  project  = var.runtime_configuration.project_id
  location = var.runtime_configuration.region
  name     = var.runtime_configuration.service_name
  labels   = var.runtime_configuration.labels

  deletion_protection  = !var.runtime_configuration.destruction_enabled
  ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  invoker_iam_disabled = false

  template {
    service_account                  = google_service_account.runtime.email
    max_instance_request_concurrency = 10

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.runtime_configuration.image_digest

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = false
      }

      env {
        name  = "APP_PLATFORM_APPLICATION_ID"
        value = var.runtime_configuration.application_id
      }

      env {
        name  = "APP_PLATFORM_ADMISSION_MODE"
        value = var.runtime_configuration.admission_mode
      }

      env {
        name  = "APP_PLATFORM_ISSUER"
        value = var.runtime_configuration.platform_issuer
      }

      env {
        name  = "APP_PLATFORM_PUBLIC_KEY_REFERENCE"
        value = var.runtime_configuration.public_key_reference
      }

      dynamic "env" {
        for_each = var.runtime_configuration.assertion_audience == "" ? [] : [var.runtime_configuration.assertion_audience]

        content {
          name  = "APP_PLATFORM_ASSERTION_AUDIENCE"
          value = env.value
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "edge_invoker" {
  project  = var.runtime_configuration.project_id
  location = var.runtime_configuration.region
  name     = google_cloud_run_v2_service.runtime.name
  role     = "roles/run.invoker"
  member   = var.edge_caller_principal
}
