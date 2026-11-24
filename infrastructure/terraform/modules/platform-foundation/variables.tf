variable "foundation_configuration" {
  description = "Complete non-secret implementation input for the Platform State foundation."
  type = object({
    project_id           = string
    project_number       = string
    region               = string
    hostname             = string
    configuration_bucket = string
    oauth_secret_id      = string
    signing_key_ring_id  = string
    signing_key_id       = string
    labels               = map(string)
    signing = object({
      manual_rotation_days       = number
      verification_overlap_hours = number
      active_version_count       = number
      overlap_version_count      = number
    })
    identities = object({
      edge_runtime_account_id = string
      edge_caller_account_id  = string
    })
    sessions = object({
      collection_name           = string
      expiration_field          = string
      absolute_lifetime_seconds = number
    })
  })
}

variable "destruction_mode" {
  description = "Exact safe-destruction transition for Platform State resources."
  type        = string

  validation {
    condition     = contains(["none", "shared-edge-unlock", "shared-edge-remove", "platform-unlock", "retained"], var.destruction_mode)
    error_message = "destruction_mode must select one closed platform transition."
  }
}
