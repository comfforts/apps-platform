output "backend_reference_set" {
  description = "Four typed non-secret references for the independently owned Terraform roots."
  value = {
    for owner_id, bucket in module.state_bucket : owner_id => {
      reference_kind = "backend"
      state_owner    = local.state_buckets[owner_id].state_owner
      owner_id       = owner_id
      bucket_name    = bucket.bucket_name
      backend_prefix = local.state_buckets[owner_id].backend_prefix
    }
  }

  precondition {
    condition     = length(module.state_bucket) == 4
    error_message = "backend_reference_set requires exactly four exclusive state owners."
  }
}
