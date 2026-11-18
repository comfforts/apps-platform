variable "project_id" {
  description = "Reviewed project that will own the state bucket."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be one canonical GCP project identifier."
  }
}

variable "location" {
  description = "Reviewed single-region bucket location."
  type        = string

  validation {
    condition     = can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$", var.location))
    error_message = "location must be one canonical lowercase region."
  }
}

variable "bucket_configuration" {
  description = "One explicit globally unique bucket name and root-owned labels."
  type = object({
    bucket_name = string
    labels      = map(string)
  })

  validation {
    condition = can(
      regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", var.bucket_configuration.bucket_name)
    ) && length(var.bucket_configuration.labels) >= 3
    error_message = "bucket_configuration requires one canonical bucket name and root-owned labels."
  }
}

variable "recovery_policy" {
  description = "Bounds for deleting only sufficiently old noncurrent state versions."
  type = object({
    noncurrent_version_retention_days = number
    newer_versions_to_retain          = number
  })

  validation {
    condition = (
      var.recovery_policy.noncurrent_version_retention_days >= 90 &&
      var.recovery_policy.noncurrent_version_retention_days <= 365 &&
      var.recovery_policy.newer_versions_to_retain >= 20 &&
      var.recovery_policy.newer_versions_to_retain <= 50
    )
    error_message = "recovery_policy must retain noncurrent state for 90-365 days and 20-50 newer versions."
  }
}
