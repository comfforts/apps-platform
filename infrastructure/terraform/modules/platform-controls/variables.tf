variable "controls_configuration" {
  description = "Complete non-secret observability, evidence, retention, and budget configuration."
  type = object({
    project_id                = string
    project_number            = string
    region                    = string
    log_bucket                = string
    evidence_bucket           = string
    artifact_repository_id    = string
    billing_account_reference = string
    notification_email        = string
    owner_principal           = string
    labels                    = map(string)
    artifact_packages         = list(string)
  })
}

variable "destruction_mode" {
  description = "Exact safe-destruction transition for Platform State controls."
  type        = string

  validation {
    condition     = contains(["none", "shared-edge-unlock", "shared-edge-remove", "platform-unlock", "retained"], var.destruction_mode)
    error_message = "destruction_mode must select one closed platform transition."
  }
}
