variable "platform_configuration" {
  description = "Complete Version 2 phased non-secret Platform State configuration object."
  type = object({
    contract_version    = number
    configuration_kind  = string
    configuration_class = string
    phase               = string
    destruction_mode    = string
    repository          = string
    environment         = string
    foundation = object({
      project_id                = string
      project_number            = string
      region                    = string
      hostname                  = string
      state_owner               = string
      configuration_bucket      = string
      log_bucket                = string
      evidence_bucket           = string
      artifact_repository_id    = string
      oauth_secret_id           = string
      signing_key_ring_id       = string
      signing_key_id            = string
      billing_account_reference = string
      notification_email        = string
    })
    shared_edge = object({
      edge_image_digest           = string
      oauth_client_id             = string
      oauth_client_secret_version = string
      signing_key_version         = string
      operator_identity = object({
        issuer  = string
        subject = string
      })
      registration_generation = object({
        source_revision   = string
        generation        = number
        generation_digest = string
        content_digest    = string
        object_name       = string
        object_generation = number
      })
      tls_enabled = bool
    })
    labels = object({
      environment = string
      managed_by  = string
      state_owner = string
    })
  })

  validation {
    condition = (
      var.platform_configuration.contract_version == 2 &&
      var.platform_configuration.configuration_kind == "platform" &&
      contains(["operator", "synthetic"], var.platform_configuration.configuration_class) &&
      contains(["foundation", "shared-edge"], var.platform_configuration.phase) &&
      contains(["none", "shared-edge-unlock", "shared-edge-remove", "platform-unlock", "retained"], var.platform_configuration.destruction_mode) &&
      var.platform_configuration.repository == "comfforts/apps-platform" &&
      var.platform_configuration.environment == "staging" &&
      var.platform_configuration.foundation.state_owner == "platform" &&
      (
        contains(["shared-edge-remove", "platform-unlock", "retained"], var.platform_configuration.destruction_mode) ?
        var.platform_configuration.phase == "foundation" && var.platform_configuration.shared_edge == null :
        var.platform_configuration.destruction_mode == "shared-edge-unlock" ?
        var.platform_configuration.phase == "shared-edge" && var.platform_configuration.shared_edge != null :
        var.platform_configuration.phase == "foundation" ?
        var.platform_configuration.shared_edge == null :
        var.platform_configuration.shared_edge != null
      )
    )
    error_message = "platform_configuration must select one complete Version 2 staging phase on the canonical Platform State lineage."
  }

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.platform_configuration.foundation.project_id)) &&
      can(regex("^[1-9][0-9]{5,18}$", var.platform_configuration.foundation.project_number)) &&
      can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$", var.platform_configuration.foundation.region)) &&
      can(regex("^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z][a-z0-9-]{1,62}$", var.platform_configuration.foundation.hostname))
    )
    error_message = "foundation project, region, and hostname must use canonical forms."
  }

  validation {
    condition = (
      alltrue([
        for bucket in [
          var.platform_configuration.foundation.configuration_bucket,
          var.platform_configuration.foundation.log_bucket,
          var.platform_configuration.foundation.evidence_bucket,
        ] : can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", bucket))
      ]) &&
      length(toset([
        var.platform_configuration.foundation.configuration_bucket,
        var.platform_configuration.foundation.log_bucket,
        var.platform_configuration.foundation.evidence_bucket,
      ])) == 3 &&
      alltrue([
        for resource_id in [
          var.platform_configuration.foundation.artifact_repository_id,
          var.platform_configuration.foundation.oauth_secret_id,
          var.platform_configuration.foundation.signing_key_ring_id,
          var.platform_configuration.foundation.signing_key_id,
        ] : can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", resource_id))
      ])
    )
    error_message = "foundation bucket and resource names must be canonical and mutually safe."
  }

  validation {
    condition = (
      can(regex("^billingAccounts/[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.platform_configuration.foundation.billing_account_reference)) &&
      can(regex("^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$", var.platform_configuration.foundation.notification_email))
    )
    error_message = "foundation billing reference and notification email must use canonical forms."
  }

  validation {
    condition = var.platform_configuration.shared_edge == null || try(
      can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]-docker\\.pkg\\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/[a-z][a-z0-9_-]{0,126}/[a-z][a-z0-9._-]{0,126}@sha256:[0-9a-f]{64}$", var.platform_configuration.shared_edge.edge_image_digest)) &&
      startswith(var.platform_configuration.shared_edge.edge_image_digest, "${var.platform_configuration.foundation.region}-docker.pkg.dev/${var.platform_configuration.foundation.project_id}/") &&
      can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{6,254}[A-Za-z0-9]$", var.platform_configuration.shared_edge.oauth_client_id)) &&
      can(regex("^projects/(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[1-9][0-9]{5,18})/secrets/[A-Za-z][A-Za-z0-9_-]{0,254}/versions/[1-9][0-9]{0,18}$", var.platform_configuration.shared_edge.oauth_client_secret_version)) &&
      startswith(var.platform_configuration.shared_edge.oauth_client_secret_version, "projects/${var.platform_configuration.foundation.project_id}/secrets/${var.platform_configuration.foundation.oauth_secret_id}/versions/") &&
      can(regex("^projects/(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[1-9][0-9]{5,18})/locations/[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?/keyRings/[A-Za-z0-9_-]{1,63}/cryptoKeys/[A-Za-z0-9_-]{1,63}/cryptoKeyVersions/[1-9][0-9]{0,18}$", var.platform_configuration.shared_edge.signing_key_version)) &&
      startswith(var.platform_configuration.shared_edge.signing_key_version, "projects/${var.platform_configuration.foundation.project_id}/locations/${var.platform_configuration.foundation.region}/keyRings/${var.platform_configuration.foundation.signing_key_ring_id}/cryptoKeys/${var.platform_configuration.foundation.signing_key_id}/cryptoKeyVersions/") &&
      var.platform_configuration.shared_edge.operator_identity.issuer == "https://accounts.google.com" &&
      can(regex("^[1-9][0-9]{5,63}$", var.platform_configuration.shared_edge.operator_identity.subject)),
      false,
    )
    error_message = "Shared Edge values must be immutable generated references and operator identity bound to the foundation project."
  }

  validation {
    condition = var.platform_configuration.shared_edge == null || try(
      can(regex("^[0-9a-f]{40}$", var.platform_configuration.shared_edge.registration_generation.source_revision)) &&
      var.platform_configuration.shared_edge.registration_generation.generation >= 1 &&
      var.platform_configuration.shared_edge.registration_generation.generation <= 2147483647 &&
      can(regex("^sha256:[0-9a-f]{64}$", var.platform_configuration.shared_edge.registration_generation.generation_digest)) &&
      can(regex("^sha256:[0-9a-f]{64}$", var.platform_configuration.shared_edge.registration_generation.content_digest)) &&
      contains([
        var.platform_configuration.shared_edge.registration_generation.generation == 1 ? "generations/1/compiled.json" : "",
        "generations/${trimprefix(var.platform_configuration.shared_edge.registration_generation.generation_digest, "sha256:")}/compiled-shared-edge.v1.json",
        "environments/${var.platform_configuration.environment}/generations/${var.platform_configuration.shared_edge.registration_generation.generation}/compiled-shared-edge.v1.json",
      ], var.platform_configuration.shared_edge.registration_generation.object_name) &&
      var.platform_configuration.shared_edge.registration_generation.object_generation >= 1 &&
      var.platform_configuration.shared_edge.registration_generation.object_generation <= 9223372036854775807,
      false,
    )
    error_message = "Shared Edge generation must bind exact immutable source, digests, object name, and generation."
  }

  validation {
    condition = (
      var.platform_configuration.labels.environment == "staging" &&
      var.platform_configuration.labels.managed_by == "terraform" &&
      var.platform_configuration.labels.state_owner == "platform"
    )
    error_message = "platform labels must identify the staging environment and Platform State owner."
  }

  validation {
    condition = var.platform_configuration.configuration_class == "synthetic" || (
      var.platform_configuration.foundation.project_id == "comfforts-platform-non-prod" &&
      var.platform_configuration.foundation.project_number == "455651441682" &&
      var.platform_configuration.foundation.region == "us-west1" &&
      var.platform_configuration.foundation.hostname == "apps-staging.comfforts.com" &&
      alltrue([
        for value in concat(
          [
            var.platform_configuration.foundation.configuration_bucket,
            var.platform_configuration.foundation.log_bucket,
            var.platform_configuration.foundation.evidence_bucket,
            var.platform_configuration.foundation.artifact_repository_id,
            var.platform_configuration.foundation.oauth_secret_id,
            var.platform_configuration.foundation.signing_key_ring_id,
            var.platform_configuration.foundation.signing_key_id,
            var.platform_configuration.foundation.notification_email,
          ],
          var.platform_configuration.shared_edge == null ? [] : [
            var.platform_configuration.shared_edge.edge_image_digest,
            var.platform_configuration.shared_edge.oauth_client_id,
            var.platform_configuration.shared_edge.oauth_client_secret_version,
            var.platform_configuration.shared_edge.signing_key_version,
          ],
        ) : !strcontains(lower(value), "synthetic") && !strcontains(lower(value), ".invalid")
      ]) &&
      var.platform_configuration.foundation.billing_account_reference != "billingAccounts/000000-000000-000000"
    )
    error_message = "operator platform configuration must use the reviewed staging scope and cannot select reserved synthetic values."
  }
}
