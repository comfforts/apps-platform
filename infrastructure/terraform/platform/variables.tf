variable "platform_configuration" {
  description = "Complete Version 1 non-secret Platform State configuration object."
  type = object({
    contract_version            = number
    configuration_kind          = string
    configuration_class         = string
    repository                  = string
    project_id                  = string
    project_number              = string
    region                      = string
    qualification_hostname      = string
    state_owner                 = string
    configuration_bucket        = string
    log_bucket                  = string
    evidence_bucket             = string
    edge_image_digest           = string
    oauth_client_id             = string
    oauth_client_secret_version = string
    signing_key_version         = string
    managed_zone_resource       = string
    billing_account_reference   = string
    notification_destination    = string
    registration_generation = object({
      source_revision   = string
      generation        = number
      generation_digest = string
      content_digest    = string
      object_name       = string
      object_generation = number
    })
    labels = object({
      environment = string
      managed_by  = string
      state_owner = string
    })
  })

  validation {
    condition = (
      var.platform_configuration.contract_version == 1 &&
      var.platform_configuration.configuration_kind == "platform" &&
      contains(["operator", "synthetic"], var.platform_configuration.configuration_class) &&
      var.platform_configuration.repository == "comfforts/apps-platform" &&
      var.platform_configuration.state_owner == "platform"
    )
    error_message = "platform_configuration must select the Version 1 Platform State interface and canonical repository."
  }

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.platform_configuration.project_id)) &&
      can(regex("^[1-9][0-9]{5,18}$", var.platform_configuration.project_number)) &&
      can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$", var.platform_configuration.region)) &&
      can(regex("^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z][a-z0-9-]{1,62}$", var.platform_configuration.qualification_hostname))
    )
    error_message = "project, region, and qualification hostname must use their canonical Version 1 forms."
  }

  validation {
    condition = (
      alltrue([
        for bucket in [
          var.platform_configuration.configuration_bucket,
          var.platform_configuration.log_bucket,
          var.platform_configuration.evidence_bucket,
        ] : can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", bucket))
      ]) &&
      length(toset([
        var.platform_configuration.configuration_bucket,
        var.platform_configuration.log_bucket,
        var.platform_configuration.evidence_bucket,
      ])) == 3
    )
    error_message = "configuration, log, and evidence buckets must be canonical and mutually distinct."
  }

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]-docker\\.pkg\\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/[a-z][a-z0-9_-]{0,126}/[a-z][a-z0-9._-]{0,126}@sha256:[0-9a-f]{64}$", var.platform_configuration.edge_image_digest)) &&
      startswith(var.platform_configuration.edge_image_digest, "${var.platform_configuration.region}-docker.pkg.dev/${var.platform_configuration.project_id}/")
    )
    error_message = "edge image must be an immutable regional Artifact Registry digest in the configured project."
  }

  validation {
    condition = (
      can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{6,254}[A-Za-z0-9]$", var.platform_configuration.oauth_client_id)) &&
      can(regex("^projects/(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[1-9][0-9]{5,18})/secrets/[A-Za-z][A-Za-z0-9_-]{0,254}/versions/[1-9][0-9]{0,18}$", var.platform_configuration.oauth_client_secret_version)) &&
      startswith(var.platform_configuration.oauth_client_secret_version, "projects/${var.platform_configuration.project_id}/secrets/")
    )
    error_message = "OAuth configuration must contain only a client identifier and a numeric Secret Manager version reference in the configured project."
  }

  validation {
    condition = (
      can(regex("^projects/(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[1-9][0-9]{5,18})/locations/[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?/keyRings/[A-Za-z0-9_-]{1,63}/cryptoKeys/[A-Za-z0-9_-]{1,63}/cryptoKeyVersions/[1-9][0-9]{0,18}$", var.platform_configuration.signing_key_version)) &&
      startswith(var.platform_configuration.signing_key_version, "projects/${var.platform_configuration.project_id}/locations/${var.platform_configuration.region}/")
    )
    error_message = "signing key must be a numeric regional Cloud KMS key-version reference in the configured project."
  }

  validation {
    condition = (
      can(regex("^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/managedZones/[a-z][a-z0-9-]{0,61}[a-z0-9]$", var.platform_configuration.managed_zone_resource)) &&
      startswith(var.platform_configuration.managed_zone_resource, "projects/${var.platform_configuration.project_id}/") &&
      can(regex("^billingAccounts/[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.platform_configuration.billing_account_reference)) &&
      can(regex("^projects/(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[1-9][0-9]{5,18})/notificationChannels/[1-9][0-9]{0,18}$", var.platform_configuration.notification_destination)) &&
      startswith(var.platform_configuration.notification_destination, "projects/${var.platform_configuration.project_id}/")
    )
    error_message = "later-slice DNS, billing, and notification references must remain explicit, canonical, and correctly scoped."
  }

  validation {
    condition = (
      can(regex("^[0-9a-f]{40}$", var.platform_configuration.registration_generation.source_revision)) &&
      var.platform_configuration.registration_generation.generation >= 1 &&
      var.platform_configuration.registration_generation.generation <= 2147483647 &&
      can(regex("^sha256:[0-9a-f]{64}$", var.platform_configuration.registration_generation.generation_digest)) &&
      can(regex("^sha256:[0-9a-f]{64}$", var.platform_configuration.registration_generation.content_digest)) &&
      var.platform_configuration.registration_generation.object_name == "generations/${var.platform_configuration.registration_generation.generation}/compiled.json" &&
      var.platform_configuration.registration_generation.object_generation >= 1 &&
      var.platform_configuration.registration_generation.object_generation <= 9223372036854775807
    )
    error_message = "registration generation must bind immutable source, generation, digest, object name, and object generation values."
  }

  validation {
    condition = (
      var.platform_configuration.labels.environment == "qualification" &&
      var.platform_configuration.labels.managed_by == "terraform" &&
      var.platform_configuration.labels.state_owner == "platform"
    )
    error_message = "platform labels must identify the qualification environment and Platform State owner."
  }

  validation {
    condition = var.platform_configuration.configuration_class == "synthetic" || (
      var.platform_configuration.project_id == "comfforts-platform-non-prod" &&
      var.platform_configuration.project_number == "455651441682" &&
      var.platform_configuration.region == "us-west1" &&
      var.platform_configuration.qualification_hostname == "apps-staging.comfforts.com" &&
      alltrue([
        for value in [
          var.platform_configuration.configuration_bucket,
          var.platform_configuration.log_bucket,
          var.platform_configuration.evidence_bucket,
          var.platform_configuration.edge_image_digest,
          var.platform_configuration.oauth_client_id,
          var.platform_configuration.oauth_client_secret_version,
          var.platform_configuration.signing_key_version,
          var.platform_configuration.managed_zone_resource,
          var.platform_configuration.notification_destination,
        ] : !strcontains(lower(value), "synthetic") && !strcontains(lower(value), ".invalid")
      ]) &&
      var.platform_configuration.registration_generation.source_revision != "0000000000000000000000000000000000000000" &&
      var.platform_configuration.billing_account_reference != "billingAccounts/000000-000000-000000" &&
      length(toset(regexall(".", trimprefix(var.platform_configuration.registration_generation.generation_digest, "sha256:")))) > 1 &&
      length(toset(regexall(".", trimprefix(var.platform_configuration.registration_generation.content_digest, "sha256:")))) > 1
    )
    error_message = "operator platform configuration must use the reviewed non-production scope and cannot select reserved synthetic values."
  }
}
