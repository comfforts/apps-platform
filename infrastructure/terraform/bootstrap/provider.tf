provider "google" {
  project = var.backend_configuration.project_id
  region  = var.backend_configuration.region
}
