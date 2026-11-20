locals {
  operation_root_codes = {
    bootstrap               = "bootstrap"
    platform                = "platform"
    "fixture-public"        = "fxpub"
    "fixture-authenticated" = "fxauth"
    "fixture-restricted"    = "fxrest"
  }
  operation_actions = {
    bootstrap               = ["bootstrap", "plan", "apply", "readback", "rollback", "destroy", "recovery"]
    platform                = ["plan", "apply", "readback", "rollback", "destroy", "recovery"]
    "fixture-public"        = ["plan", "apply", "readback", "rollback", "destroy", "recovery"]
    "fixture-authenticated" = ["plan", "apply", "readback", "rollback", "destroy", "recovery"]
    "fixture-restricted"    = ["plan", "apply", "readback", "rollback", "destroy", "recovery"]
  }
  operation_identities = merge([
    for root, actions in local.operation_actions : {
      for action in actions : "${root}:${action}" => {
        root       = root
        action     = action
        account_id = "ap-stg-${local.operation_root_codes[root]}-${action}"
      }
    }
  ]...)

  platform_read_roles = toset([
    "roles/artifactregistry.reader",
    "roles/billing.viewer",
    "roles/browser",
    "roles/cloudkms.viewer",
    "roles/compute.viewer",
    "roles/datastore.viewer",
    "roles/iam.securityReviewer",
    "roles/iam.serviceAccountViewer",
    "roles/logging.viewer",
    "roles/monitoring.viewer",
    "roles/run.viewer",
    "roles/secretmanager.viewer",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/storage.viewer",
  ])
  platform_mutate_roles = toset([
    "roles/artifactregistry.admin",
    "roles/cloudkms.admin",
    "roles/compute.loadBalancerAdmin",
    "roles/compute.networkAdmin",
    "roles/datastore.owner",
    "roles/iam.serviceAccountAdmin",
    "roles/logging.admin",
    "roles/monitoring.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/storage.admin",
  ])
  fixture_read_roles = toset([
    "roles/browser",
    "roles/iam.serviceAccountViewer",
    "roles/run.viewer",
    "roles/serviceusage.serviceUsageConsumer",
  ])
  fixture_mutate_roles = toset([
    "roles/browser",
    "roles/iam.serviceAccountAdmin",
    "roles/run.admin",
    "roles/serviceusage.serviceUsageConsumer",
  ])
  project_roles_by_operation = merge(
    {
      "bootstrap:plan"     = toset(["roles/storage.viewer"])
      "bootstrap:readback" = toset(["roles/storage.viewer"])
      "bootstrap:apply"    = toset(["roles/storage.admin"])
      "bootstrap:destroy"  = toset(["roles/storage.admin"])
      "bootstrap:rollback" = toset(["roles/storage.admin"])
      "platform:plan"      = local.platform_read_roles
      "platform:readback"  = local.platform_read_roles
      "platform:apply"     = local.platform_mutate_roles
      "platform:destroy"   = local.platform_mutate_roles
    },
    {
      for item in setproduct(
        toset(["fixture-public", "fixture-authenticated", "fixture-restricted"]),
        toset(["plan", "readback"]),
      ) : "${item[0]}:${item[1]}" => local.fixture_read_roles
    },
    {
      for item in setproduct(
        toset(["fixture-public", "fixture-authenticated", "fixture-restricted"]),
        toset(["apply", "destroy"]),
      ) : "${item[0]}:${item[1]}" => local.fixture_mutate_roles
    },
  )
  project_role_bindings = merge([
    for operation, roles in local.project_roles_by_operation : {
      for role in roles : "${operation}:${role}" => {
        operation = operation
        role      = role
      }
    }
  ]...)

  state_lineages = merge(
    {
      bootstrap = {
        bucket = local.state_buckets["app-platform"].bucket_name
        prefix = "bootstrap"
      }
    },
    {
      for owner_id, bucket in local.state_buckets : (
        owner_id == "app-platform" ? "platform" : owner_id
        ) => {
        bucket = bucket.bucket_name
        prefix = bucket.backend_prefix
      }
    },
  )
  backend_role_bindings = merge([
    for operation, identity in local.operation_identities : contains(
      ["apply", "destroy", "plan", "readback", "recovery", "rollback"],
      identity.action,
      ) ? {
      "${operation}:backend" = {
        operation = operation
        bucket    = local.state_lineages[identity.root].bucket
        prefix    = local.state_lineages[identity.root].prefix
        role = identity.action == "readback" ? (
          "roles/storage.objectViewer"
        ) : "roles/storage.objectUser"
      }
    } : {}
  ]...)
}

resource "google_service_account" "operation" {
  for_each = local.operation_identities

  project      = var.backend_configuration.project_id
  account_id   = each.value.account_id
  display_name = "App Platform staging ${each.value.root} ${each.value.action}"
  description  = "Keyless ${each.value.action} identity for the ${each.value.root} root."
}

resource "google_service_account_iam_member" "operator_token_creator" {
  for_each = local.operation_identities

  service_account_id = google_service_account.operation[each.key].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.identity_bootstrap_configuration.operator_principal
}

resource "google_project_iam_member" "operation" {
  for_each = local.project_role_bindings

  project = var.backend_configuration.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.operation[each.value.operation].email}"
}

resource "google_billing_account_iam_member" "platform_costs" {
  for_each = toset(["platform:apply", "platform:destroy"])

  billing_account_id = trimprefix(
    var.identity_bootstrap_configuration.billing_account_reference,
    "billingAccounts/",
  )
  role   = "roles/billing.costsManager"
  member = "serviceAccount:${google_service_account.operation[each.key].email}"
}

resource "google_storage_bucket_iam_member" "backend" {
  for_each = local.backend_role_bindings

  bucket = module.state_bucket[
    contains(
      ["bootstrap", "platform"],
      local.operation_identities[each.value.operation].root,
    ) ?
    "app-platform" : local.operation_identities[each.value.operation].root
  ].bucket_name
  role   = each.value.role
  member = "serviceAccount:${google_service_account.operation[each.value.operation].email}"

  condition {
    title      = "${google_service_account.operation[each.value.operation].account_id}-state-prefix"
    expression = "resource.name.startsWith('projects/_/buckets/${each.value.bucket}/objects/${trimsuffix(each.value.prefix, "/")}/')"
  }
}
