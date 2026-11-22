locals {
  destruction_enabled    = contains(["platform-unlock", "retained"], var.destruction_mode)
  retained_only          = var.destruction_mode == "retained"
  edge_resource_filter   = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"app-platform-edge\""
  edge_completion_filter = "${local.edge_resource_filter} AND jsonPayload.event_version=1 AND jsonPayload.event_type=\"request_completion\" AND jsonPayload.component=\"shared-edge\""
}

resource "google_logging_project_bucket_config" "edge" {
  count = local.retained_only ? 0 : 1

  project          = var.controls_configuration.project_id
  location         = var.controls_configuration.region
  bucket_id        = var.controls_configuration.log_bucket
  description      = "Minimized App Platform Shared Edge completion events."
  retention_days   = 7
  enable_analytics = false
  locked           = false
  deletion_policy  = local.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_logging_project_sink" "edge" {
  count = local.retained_only ? 0 : 1

  project     = var.controls_configuration.project_id
  name        = "app-platform-edge-completions"
  description = "Routes minimized Shared Edge completion events to the regional platform log bucket."
  destination = "logging.googleapis.com/projects/${var.controls_configuration.project_id}/locations/${var.controls_configuration.region}/buckets/${google_logging_project_bucket_config.edge[0].bucket_id}"
  filter      = local.edge_completion_filter

  # Keep the writer-identity request at the provider default. For a Logging bucket in
  # this same project, the API omits an actual writer identity while the provider
  # records its default request value; forcing false creates a permanent plan diff.
  disabled        = false
  deletion_policy = local.destruction_enabled ? "DELETE" : "PREVENT"

  exclusions {
    name        = "identity-and-visitor-data"
    description = "Drop a completion event if identity, session, or visitor metadata is present."
    filter      = "jsonPayload.assertion:* OR jsonPayload.session:* OR jsonPayload.session_id:* OR jsonPayload.restricted_members:* OR jsonPayload.issuer:* OR jsonPayload.subject:* OR jsonPayload.email:* OR httpRequest.remoteIp:* OR httpRequest.userAgent:*"
    disabled    = false
  }

  exclusions {
    name        = "payload-and-application-data"
    description = "Drop a completion event if request, response, stream, or application payload data is present."
    filter      = "jsonPayload.request_body:* OR jsonPayload.response_body:* OR jsonPayload.query:* OR jsonPayload.raw_path:* OR jsonPayload.application_data:* OR jsonPayload.stream_chunk:*"
    disabled    = false
  }

  exclusions {
    name        = "provider-secret-and-state-data"
    description = "Drop a completion event if provider, credential, secret, state, or plan material is present."
    filter      = "jsonPayload.provider_payload:* OR jsonPayload.provider_response:* OR jsonPayload.credential:* OR jsonPayload.secret:* OR jsonPayload.terraform_state:* OR jsonPayload.saved_plan:*"
    disabled    = false
  }
}

resource "google_logging_project_exclusion" "edge_from_default" {
  project     = var.controls_configuration.project_id
  name        = "app-platform-edge-from-default"
  description = "Prevents Shared Edge runtime logs from bypassing the dedicated seven-day bucket policy."
  filter      = local.edge_resource_filter
  disabled    = false

  depends_on = [google_logging_project_sink.edge]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_iam_member" "log_owner_reader" {
  count = local.retained_only ? 0 : 1

  project = var.controls_configuration.project_id
  role    = "roles/logging.viewAccessor"
  member  = var.controls_configuration.owner_principal
}

resource "google_storage_bucket" "evidence" {
  project  = var.controls_configuration.project_id
  name     = var.controls_configuration.evidence_bucket
  location = upper(var.controls_configuration.region)
  labels   = var.controls_configuration.labels

  storage_class               = "STANDARD"
  force_destroy               = false
  deletion_policy             = "PREVENT"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  retention_policy {
    retention_period = 2592000
    is_locked        = false
  }

  lifecycle_rule {
    condition {
      age = 30
    }

    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "evidence_owner_reader" {
  bucket = google_storage_bucket.evidence.name
  role   = "roles/storage.objectViewer"
  member = var.controls_configuration.owner_principal
}

resource "google_monitoring_notification_channel" "budget_email" {
  count = local.retained_only ? 0 : 1

  project      = var.controls_configuration.project_id
  display_name = "App Platform qualification budget owner"
  type         = "email"
  labels = {
    email_address = var.controls_configuration.notification_email
  }

  enabled         = true
  deletion_policy = local.destruction_enabled ? "DELETE" : "PREVENT"
}

resource "google_billing_budget" "qualification" {
  count = local.retained_only ? 0 : 1

  billing_account = var.controls_configuration.billing_account_reference
  display_name    = "App Platform qualification monthly budget"
  ownership_scope = "BILLING_ACCOUNT"
  deletion_policy = local.destruction_enabled ? "DELETE" : "PREVENT"

  budget_filter {
    projects = ["projects/${var.controls_configuration.project_number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = "20"
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.budget_email[0].id]
    disable_default_iam_recipients   = true
    enable_project_level_recipients  = false
  }
}

resource "google_artifact_registry_repository" "qualification_images" {
  count = local.retained_only ? 0 : 1

  project       = var.controls_configuration.project_id
  location      = var.controls_configuration.region
  repository_id = var.controls_configuration.artifact_repository_id
  description   = "Digest-selected images for App Platform qualification."
  format        = "DOCKER"
  mode          = "STANDARD_REPOSITORY"
  labels        = var.controls_configuration.labels

  cleanup_policy_dry_run = true
  deletion_policy        = local.destruction_enabled ? "DELETE" : "PREVENT"

  docker_config {
    immutable_tags = true
  }

  cleanup_policies {
    id     = "retain-generation-roles"
    action = "KEEP"

    condition {
      tag_state    = "TAGGED"
      tag_prefixes = ["active", "rollback", "candidate"]
    }
  }

  cleanup_policies {
    id     = "retain-three-per-service"
    action = "KEEP"

    most_recent_versions {
      package_name_prefixes = var.controls_configuration.artifact_packages
      keep_count            = 3
    }
  }

  cleanup_policies {
    id     = "delete-unretained-after-rollback-window"
    action = "DELETE"

    condition {
      tag_state  = "ANY"
      older_than = "1d"
    }
  }
}
