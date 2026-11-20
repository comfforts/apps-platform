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
