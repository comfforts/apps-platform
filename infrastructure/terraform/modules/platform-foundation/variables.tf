variable "foundation_configuration" {
  description = "Complete non-secret implementation input for the Platform State foundation."
  type = object({
    project_id             = string
    project_number         = string
    region                 = string
    qualification_hostname = string
    configuration_bucket   = string
    labels                 = map(string)
    registration_generation = object({
      source_revision   = string
      generation        = number
      generation_digest = string
      content_digest    = string
      object_name       = string
      object_generation = number
    })
    oauth = object({
      client_id             = string
      client_secret_version = string
    })
    signing = object({
      key_version                = string
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
