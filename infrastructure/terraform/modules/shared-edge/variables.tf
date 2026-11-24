variable "edge_configuration" {
  description = "Complete non-secret Shared Edge revision and hostname-forwarding configuration."
  type = object({
    project_id                     = string
    project_number                 = string
    region                         = string
    qualification_hostname         = string
    labels                         = map(string)
    service_name                   = string
    candidate_revision             = string
    runtime_identity_email         = string
    edge_caller_principal          = string
    edge_caller_service_account_id = string
    image_digest                   = string
    configuration_bucket           = string
    shared_network_reference       = string
    application_subnet_reference   = string
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
    operator_identity = object({
      issuer  = string
      subject = string
    })
    tls_enabled = bool
  })
}

variable "destruction_enabled" {
  description = "Disable provider deletion protection only for the exact reviewed edge-unlock plan."
  type        = bool
  default     = false
}
