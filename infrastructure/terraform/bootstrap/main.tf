locals {
  platform_state_bucket = one(var.backend_configuration.state_buckets)
  platform_state_bucket_labels = {
    environment = "staging"
    managed_by  = "terraform"
    state_owner = local.platform_state_bucket.state_owner
  }
}

module "platform_state_bucket" {
  source = "../modules/state-bucket"

  project_id = var.backend_configuration.project_id
  location   = var.backend_configuration.region
  bucket_configuration = {
    bucket_name = local.platform_state_bucket.bucket_name
    labels      = local.platform_state_bucket_labels
  }
  recovery_policy = var.backend_configuration.recovery_policy
}

moved {
  from = module.state_bucket["app-platform"]
  to   = module.platform_state_bucket
}

removed {
  from = module.state_bucket

  lifecycle {
    destroy = false
  }
}
