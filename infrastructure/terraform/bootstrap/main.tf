locals {
  state_buckets = {
    for bucket in var.backend_configuration.state_buckets : bucket.owner_id => bucket
  }
  state_bucket_labels = {
    for owner_id, bucket in local.state_buckets : owner_id => merge(
      {
        environment = "staging"
        managed_by  = "terraform"
        state_owner = bucket.state_owner
      },
      bucket.state_owner == "application" ? {
        application_id = owner_id
      } : {}
    )
  }
}

module "state_bucket" {
  source   = "../modules/state-bucket"
  for_each = local.state_buckets

  project_id = var.backend_configuration.project_id
  location   = var.backend_configuration.region
  bucket_configuration = {
    bucket_name = each.value.bucket_name
    labels      = local.state_bucket_labels[each.key]
  }
  recovery_policy = var.backend_configuration.recovery_policy
}
