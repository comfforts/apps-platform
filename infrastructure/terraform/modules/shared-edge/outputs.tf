output "edge_reference" {
  description = "Closed non-secret Shared Edge phase references."
  value = {
    hostname         = var.edge_configuration.qualification_hostname
    reserved_address = google_compute_global_address.edge.address
    service_name     = google_cloud_run_v2_service.edge.name
    tls_enabled      = var.edge_configuration.tls_enabled
  }
}

output "policy_summary" {
  description = "Internal mocked-plan surface for immutable revision and hostname-forwarding controls."
  value = {
    service_name            = var.edge_configuration.service_name
    candidate_revision      = var.edge_configuration.candidate_revision
    runtime_identity_email  = var.edge_configuration.runtime_identity_email
    edge_caller_principal   = var.edge_configuration.edge_caller_principal
    immutable_image_digest  = var.edge_configuration.image_digest
    registration_generation = var.edge_configuration.registration_generation
    binding_versions        = var.edge_configuration.binding_versions
    configuration_bucket    = var.edge_configuration.configuration_bucket
    operator_identity       = var.edge_configuration.operator_identity
    caller_identity = {
      iam_credentials_service = "iamcredentials.googleapis.com"
      runtime_principal       = "serviceAccount:${var.edge_configuration.runtime_identity_email}"
      caller_service_account  = var.edge_configuration.edge_caller_service_account_id
      impersonation_role      = "roles/iam.serviceAccountTokenCreator"
    }
    runtime = {
      region                       = var.edge_configuration.region
      ingress                      = var.destruction_enabled ? "INGRESS_TRAFFIC_INTERNAL_ONLY" : "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
      default_uri_disabled         = true
      invoker_iam_disabled         = false
      invoker_role                 = "roles/run.invoker"
      invoker_member               = "allUsers"
      public_direct_origin         = false
      minimum_instances            = 0
      maximum_instances            = 2
      cpu                          = "1"
      memory                       = "512Mi"
      concurrency                  = 20
      provider_timeout_seconds     = 3600
      runtime_stream_limit_seconds = 3300
      deletion_protection          = !var.destruction_enabled
      deletion_policy              = var.destruction_enabled ? "DELETE" : "PREVENT"
      traffic_type                 = "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"
      traffic_revision             = var.edge_configuration.candidate_revision
      traffic_percent              = 100
    }
    forwarding = {
      hostname                  = var.edge_configuration.qualification_hostname
      address_scope             = "global"
      address_type              = "EXTERNAL"
      ip_version                = "IPV4"
      network_tier              = "PREMIUM"
      load_balancing_scheme     = "EXTERNAL_MANAGED"
      managed_certificate       = var.edge_configuration.tls_enabled
      http_to_https_redirect    = true
      serverless_backend_count  = 1
      https_url_map_count       = var.edge_configuration.tls_enabled ? 1 : 0
      application_prefix_routes = 0
      cdn                       = false
      waf                       = false
      dns_record                = false
    }
    application_runtime_management = false
    attachment_discovery           = false
    application_owned_values       = false
    arbitrary_target_url           = false
  }
}
