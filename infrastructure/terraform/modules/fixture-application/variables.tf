variable "runtime_configuration" {
  description = "Complete non-secret configuration for one fixture runtime implementation."
  type = object({
    project_id                  = string
    region                      = string
    application_id              = string
    service_name                = string
    runtime_identity_account_id = string
    image_digest                = string
    admission_mode              = string
    assertion_audience          = string
    platform_issuer             = string
    public_key_reference        = string
    labels                      = map(string)
    destruction_enabled         = bool
  })
}

variable "edge_caller_principal" {
  description = "Reviewed non-secret service-account principal allowed to invoke this runtime."
  type        = string
}
