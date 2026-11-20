locals {
  allowed_log_fields = [
    "application_id",
    "component",
    "component_version",
    "correlation_id",
    "event_type",
    "event_version",
    "generation_digest",
    "latency_ms",
    "outcome",
    "route_identifier",
    "source_revision",
    "status_class",
  ]
  prohibited_observability_fields = [
    "application_data",
    "assertion",
    "credential",
    "email",
    "issuer_subject",
    "provider_payload",
    "provider_response",
    "query",
    "raw_path",
    "request_body",
    "response_body",
    "restricted_members",
    "saved_plan",
    "secret",
    "session",
    "session_id",
    "source_ip",
    "stream_chunk",
    "terraform_state",
    "user_agent",
    "visitor_metadata",
  ]
}

output "foundation_reference" {
  description = "Closed non-secret control references created by the foundation phase."
  value = {
    artifact_repository = google_artifact_registry_repository.qualification_images.name
    evidence_bucket     = google_storage_bucket.evidence.name
    log_bucket          = google_logging_project_bucket_config.edge.id
  }
}

output "policy_summary" {
  description = "Internal plan-test surface for observability, evidence, retention, labels, and cost controls."
  value = {
    logging = {
      bucket_id               = var.controls_configuration.log_bucket
      region                  = var.controls_configuration.region
      retention_days          = 7
      analytics               = false
      locked                  = false
      deletion_policy         = "PREVENT"
      internal_destination    = true
      external_sink           = false
      unique_writer_identity  = false
      exclusion_count         = 3
      default_bucket_excluded = true
      allowed_fields          = local.allowed_log_fields
      prohibited_fields       = local.prohibited_observability_fields
      owner_reader_role       = "roles/logging.viewAccessor"
      owner_principal         = var.controls_configuration.owner_principal
    }
    evidence = {
      bucket_name                 = var.controls_configuration.evidence_bucket
      region                      = var.controls_configuration.region
      retention_days              = 30
      retention_period_seconds    = 2592000
      lifecycle_expiration_days   = 30
      uniform_bucket_level_access = true
      public_access_prevention    = "enforced"
      force_destroy               = false
      deletion_policy             = "PREVENT"
      owner_reader_role           = "roles/storage.objectViewer"
      owner_principal             = var.controls_configuration.owner_principal
      allowed_material = [
        "commands",
        "evidence_class",
        "failures",
        "generation_digest",
        "image_digest",
        "limitations",
        "plan_digest",
        "redacted_provider_readback",
        "redacted_runtime_readback",
        "results",
        "source_revision",
        "timestamps",
      ]
      prohibited_fields = local.prohibited_observability_fields
      object_upload     = "deferred"
    }
    budget = {
      billing_account_reference     = var.controls_configuration.billing_account_reference
      project_number                = var.controls_configuration.project_number
      currency                      = "USD"
      monthly_amount                = 20
      threshold_percents            = [50, 80, 100]
      spend_basis                   = "CURRENT_SPEND"
      notification_destination      = google_monitoring_notification_channel.budget_email.id
      notification_email            = var.controls_configuration.notification_email
      implicit_notification         = false
      automatic_billing_disablement = false
      automatic_resource_mutation   = false
      guaranteed_hard_cap           = false
    }
    artifacts = {
      repository_id                    = var.controls_configuration.artifact_repository_id
      repository_format                = "DOCKER"
      immutable_tags                   = true
      region                           = var.controls_configuration.region
      cleanup_dry_run                  = true
      retained_roles                   = ["active", "rollback", "candidate"]
      most_recent_versions_per_service = 3
      package_name_prefixes            = var.controls_configuration.artifact_packages
      rollback_window_hours            = 24
      owner_approved_deletion_required = true
      deletion_policy                  = "PREVENT"
      image_publication                = "deferred"
    }
    runtime_caps = {
      shared_edge = {
        minimum_instances = 0
        maximum_instances = 2
        cpu               = "1"
        memory            = "512Mi"
        concurrency       = 20
      }
      fixture_application = {
        minimum_instances = 0
        maximum_instances = 1
        cpu               = "1"
        memory            = "512Mi"
        concurrency       = 10
      }
      maximum_stream_seconds = 3300
    }
    labels = {
      required                       = var.controls_configuration.labels
      application_id_when_applicable = true
    }
    prohibited_capabilities = [
      "always-on-instance",
      "automatic-budget-mutation",
      "automatic-cleanup-deletion",
      "cdn",
      "external-log-export",
      "firestore-backup",
      "firestore-pitr",
      "hsm",
      "production-environment",
      "production-replica",
      "waf",
    ]
  }
}
