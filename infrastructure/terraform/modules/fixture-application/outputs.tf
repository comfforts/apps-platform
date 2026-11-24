output "service_name" {
  description = "Configured Cloud Run service name for root-owned attachment construction."
  value       = var.runtime_configuration.service_name
}

output "policy_summary" {
  description = "Internal plan-test surface for runtime isolation and resource controls."
  value = {
    application_id                  = var.runtime_configuration.application_id
    admission_mode                  = var.runtime_configuration.admission_mode
    assertion_audience              = var.runtime_configuration.assertion_audience
    identity_audience_annotation    = try(google_cloud_run_v2_service.runtime.annotations["comfforts.com/identity-audience"], null)
    platform_issuer                 = var.runtime_configuration.platform_issuer
    public_key_reference            = var.runtime_configuration.public_key_reference
    configured_labels               = var.runtime_configuration.labels
    runtime_identity_account_id     = var.runtime_configuration.runtime_identity_account_id
    runtime_identity_deletion       = var.runtime_configuration.destruction_enabled ? "DELETE" : "PREVENT"
    ingress                         = "INGRESS_TRAFFIC_INTERNAL_ONLY"
    network_reference               = var.runtime_configuration.shared_network_reference
    subnetwork_reference            = var.runtime_configuration.application_subnet_reference
    vpc_egress                      = "ALL_TRAFFIC"
    invoker_iam_disabled            = false
    unauthenticated_invocation      = false
    edge_caller_principal           = var.edge_caller_principal
    edge_caller_role                = "roles/run.invoker"
    edge_metadata_reader_role       = "roles/run.viewer"
    minimum_instances               = 0
    maximum_instances               = 1
    cpu                             = "1"
    memory                          = "512Mi"
    concurrency                     = 10
    service_deletion_protection     = !var.runtime_configuration.destruction_enabled
    destruction_enabled             = var.runtime_configuration.destruction_enabled
    immutable_image_digest          = var.runtime_configuration.image_digest
    platform_resource_management    = false
    application_feature_entitlement = false
  }
}
