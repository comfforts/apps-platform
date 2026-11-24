provider "google" {
  project               = var.platform_configuration.foundation.project_id
  region                = var.platform_configuration.foundation.region
  billing_project       = var.platform_configuration.foundation.project_id
  user_project_override = true
}
