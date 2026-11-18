output "bucket_name" {
  description = "Configured non-secret bucket name for root-owned reference construction."
  value       = google_storage_bucket.state.name
}

output "policy_summary" {
  description = "Internal plan-test surface for recovery and access controls."
  value = {
    configured_labels                 = var.bucket_configuration.labels
    uniform_bucket_level_access       = true
    public_access_prevention          = "enforced"
    object_versioning_enabled         = true
    noncurrent_version_retention_days = var.recovery_policy.noncurrent_version_retention_days
    newer_versions_to_retain          = var.recovery_policy.newer_versions_to_retain
    force_destroy                     = false
    deletion_policy                   = "PREVENT"
    iam_binding                       = "deferred"
  }
}
