resource "google_cloud_run_v2_service" "edge" {
  project  = var.edge_configuration.project_id
  location = var.edge_configuration.region
  name     = var.edge_configuration.service_name
  labels   = var.edge_configuration.labels

  deletion_protection  = !var.destruction_enabled
  deletion_policy      = var.destruction_enabled ? "DELETE" : "PREVENT"
  ingress              = var.destruction_enabled ? "INGRESS_TRAFFIC_INTERNAL_ONLY" : "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  default_uri_disabled = true
  invoker_iam_disabled = false

  template {
    revision                         = var.edge_configuration.candidate_revision
    service_account                  = var.edge_configuration.runtime_identity_email
    timeout                          = "3600s"
    max_instance_request_concurrency = 20

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.edge_configuration.image_digest

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = false
      }

      env {
        name  = "APP_PLATFORM_SOURCE_REVISION"
        value = var.edge_configuration.registration_generation.source_revision
      }

      env {
        name  = "APP_PLATFORM_PROJECT_ID"
        value = var.edge_configuration.project_id
      }

      env {
        name  = "APP_PLATFORM_REGION"
        value = var.edge_configuration.region
      }

      env {
        name  = "APP_PLATFORM_COMPILER_VERSION"
        value = tostring(var.edge_configuration.binding_versions.compiler)
      }

      env {
        name  = "APP_PLATFORM_REGISTRATION_GENERATION"
        value = tostring(var.edge_configuration.registration_generation.generation)
      }

      env {
        name  = "APP_PLATFORM_GENERATION_DIGEST"
        value = var.edge_configuration.registration_generation.generation_digest
      }

      env {
        name  = "APP_PLATFORM_CONFIGURATION_BUCKET"
        value = var.edge_configuration.configuration_bucket
      }

      env {
        name  = "APP_PLATFORM_CONFIGURATION_OBJECT"
        value = var.edge_configuration.registration_generation.object_name
      }

      env {
        name  = "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION"
        value = tostring(var.edge_configuration.registration_generation.object_generation)
      }

      env {
        name  = "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST"
        value = var.edge_configuration.registration_generation.content_digest
      }

      env {
        name  = "APP_PLATFORM_IDENTITY_CONTRACT_VERSION"
        value = tostring(var.edge_configuration.binding_versions.identity_contract)
      }

      env {
        name  = "APP_PLATFORM_ATTACHMENT_ADAPTER"
        value = var.edge_configuration.binding_versions.attachment_adapter
      }

      env {
        name  = "APP_PLATFORM_CONFIGURATION_CONTRACT_VERSION"
        value = tostring(var.edge_configuration.binding_versions.platform_configuration)
      }

      env {
        name  = "APP_PLATFORM_ISSUER"
        value = "https://${var.edge_configuration.qualification_hostname}/_platform"
      }

      env {
        name  = "APP_PLATFORM_IDENTITY_CLIENT_ID"
        value = var.edge_configuration.oauth.client_id
      }

      env {
        name  = "APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION"
        value = var.edge_configuration.oauth.client_secret_version
      }

      env {
        name  = "APP_PLATFORM_SIGNING_KEY_VERSION"
        value = var.edge_configuration.signing_key_version
      }

      env {
        name  = "APP_PLATFORM_EDGE_CALLER_PRINCIPAL"
        value = var.edge_configuration.edge_caller_principal
      }

      env {
        name  = "APP_PLATFORM_OPERATOR_ISSUER"
        value = var.edge_configuration.operator_identity.issuer
      }

      env {
        name  = "APP_PLATFORM_OPERATOR_SUBJECT"
        value = var.edge_configuration.operator_identity.subject
      }
    }
  }

  traffic {
    type     = "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"
    revision = var.edge_configuration.candidate_revision
    percent  = 100
  }

  lifecycle {
    ignore_changes = [
      traffic,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "load_balancer_invoker" {
  project  = var.edge_configuration.project_id
  location = var.edge_configuration.region
  name     = google_cloud_run_v2_service.edge.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_compute_region_network_endpoint_group" "edge" {
  project               = var.edge_configuration.project_id
  region                = var.edge_configuration.region
  name                  = "app-platform-edge-neg"
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.edge.name
  }
}

resource "google_compute_backend_service" "edge" {
  project               = var.edge_configuration.project_id
  name                  = "app-platform-edge-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"
  enable_cdn            = false

  backend {
    group = google_compute_region_network_endpoint_group.edge.id
  }
}

resource "google_compute_global_address" "edge" {
  project      = var.edge_configuration.project_id
  name         = "app-platform-edge-address"
  address_type = "EXTERNAL"
  ip_version   = "IPV4"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_compute_managed_ssl_certificate" "edge" {
  count = var.edge_configuration.tls_enabled ? 1 : 0

  project = var.edge_configuration.project_id
  name    = "app-platform-edge-certificate"

  managed {
    domains = [var.edge_configuration.qualification_hostname]
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_compute_url_map" "edge" {
  project         = var.edge_configuration.project_id
  name            = "app-platform-edge"
  default_service = google_compute_backend_service.edge.id

  host_rule {
    hosts        = [var.edge_configuration.qualification_hostname]
    path_matcher = "shared-edge"
  }

  path_matcher {
    name            = "shared-edge"
    default_service = google_compute_backend_service.edge.id
  }
}

resource "google_compute_target_https_proxy" "edge" {
  count = var.edge_configuration.tls_enabled ? 1 : 0

  project          = var.edge_configuration.project_id
  name             = "app-platform-edge-https"
  url_map          = google_compute_url_map.edge.id
  ssl_certificates = [google_compute_managed_ssl_certificate.edge[0].id]
}

resource "google_compute_global_forwarding_rule" "https" {
  count = var.edge_configuration.tls_enabled ? 1 : 0

  project               = var.edge_configuration.project_id
  name                  = "app-platform-edge-https"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.edge.address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.edge[0].id
  network_tier          = "PREMIUM"
}

resource "google_compute_url_map" "http_redirect" {
  project = var.edge_configuration.project_id
  name    = "app-platform-edge-http-redirect"

  default_url_redirect {
    host_redirect          = var.edge_configuration.qualification_hostname
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  project = var.edge_configuration.project_id
  name    = "app-platform-edge-http-redirect"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  project               = var.edge_configuration.project_id
  name                  = "app-platform-edge-http-redirect"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.edge.address
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.http_redirect.id
  network_tier          = "PREMIUM"
}
