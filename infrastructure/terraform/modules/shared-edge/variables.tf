variable "edge_configuration" {
  description = "Complete non-secret Shared Edge revision and hostname-forwarding configuration."
  type = object({
    project_id             = string
    region                 = string
    qualification_hostname = string
    labels                 = map(string)
    service_name           = string
    candidate_revision     = string
    runtime_identity_email = string
    image_digest           = string
    configuration_bucket   = string
    registration_generation = object({
      source_revision   = string
      generation        = number
      generation_digest = string
      content_digest    = string
      object_name       = string
      object_generation = number
    })
    binding_versions = object({
      compiler               = number
      identity_contract      = number
      attachment_adapter     = string
      platform_configuration = number
    })
    oauth = object({
      client_id             = string
      client_secret_version = string
    })
    signing_key_version = string
    tls_enabled         = bool
  })
}
