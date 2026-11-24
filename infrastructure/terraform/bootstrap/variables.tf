variable "backend_configuration" {
  description = "Complete Version 1 non-secret backend configuration object."
  type = object({
    contract_version    = number
    configuration_kind  = string
    configuration_class = string
    project_id          = string
    region              = string
    state_buckets = list(object({
      state_owner    = string
      owner_id       = string
      bucket_name    = string
      backend_prefix = string
    }))
    recovery_policy = object({
      noncurrent_version_retention_days = number
      newer_versions_to_retain          = number
    })
  })

  validation {
    condition = (
      var.backend_configuration.contract_version == 1 &&
      var.backend_configuration.configuration_kind == "backend" &&
      contains(["operator", "synthetic"], var.backend_configuration.configuration_class)
    )
    error_message = "backend_configuration must select the Version 1 backend interface and a known configuration class."
  }

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.backend_configuration.project_id)) &&
      can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$", var.backend_configuration.region))
    )
    error_message = "project_id and region must use their canonical Version 1 forms."
  }

  validation {
    condition = length(var.backend_configuration.state_buckets) == 1 && length(toset([
      for bucket in var.backend_configuration.state_buckets : bucket.bucket_name
      ])) == 1 && alltrue([
      for bucket in var.backend_configuration.state_buckets :
      can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", bucket.bucket_name))
    ])
    error_message = "exactly one canonical platform state bucket name is required."
  }

  validation {
    condition = toset([
      for bucket in var.backend_configuration.state_buckets :
      "${bucket.state_owner}:${bucket.owner_id}:${bucket.backend_prefix}"
      ]) == toset([
      "platform:app-platform:platform",
    ])
    error_message = "the bootstrap root may manage only the platform state bucket."
  }

  validation {
    condition = (
      var.backend_configuration.recovery_policy.noncurrent_version_retention_days >= 90 &&
      var.backend_configuration.recovery_policy.noncurrent_version_retention_days <= 365 &&
      var.backend_configuration.recovery_policy.newer_versions_to_retain >= 20 &&
      var.backend_configuration.recovery_policy.newer_versions_to_retain <= 50
    )
    error_message = "recovery_policy must retain noncurrent state for 90-365 days and 20-50 newer versions."
  }

  validation {
    condition = var.backend_configuration.configuration_class == "synthetic" || (
      !strcontains(var.backend_configuration.project_id, "synthetic") &&
      alltrue([
        for bucket in var.backend_configuration.state_buckets :
        !strcontains(bucket.bucket_name, "synthetic") && !strcontains(bucket.bucket_name, ".invalid")
      ])
    )
    error_message = "operator configuration cannot select reserved synthetic values."
  }
}
