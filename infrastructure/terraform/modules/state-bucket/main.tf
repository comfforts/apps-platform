resource "google_storage_bucket" "state" {
  project  = var.project_id
  name     = var.bucket_configuration.bucket_name
  location = upper(var.location)

  storage_class               = "STANDARD"
  force_destroy               = false
  deletion_policy             = "PREVENT"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = var.bucket_configuration.labels

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }

    condition {
      days_since_noncurrent_time = var.recovery_policy.noncurrent_version_retention_days
      num_newer_versions         = var.recovery_policy.newer_versions_to_retain
      with_state                 = "ARCHIVED"
      send_age_if_zero           = false
    }
  }
}
