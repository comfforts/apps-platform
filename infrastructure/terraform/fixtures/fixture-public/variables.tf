variable "fixture_configuration" {
  description = "Complete Version 1 non-secret configuration for fixture-public."
  type = object({
    contract_version             = number
    configuration_kind           = string
    configuration_class          = string
    project_id                   = string
    project_number               = string
    region                       = string
    application_id               = string
    state_owner                  = string
    service_name                 = string
    image_digest                 = string
    admission_mode               = string
    assertion_audience           = string
    platform_issuer              = string
    edge_caller_principal        = string
    network_host_project_id      = string
    shared_network_reference     = string
    application_subnet_reference = string
    vpc_egress                   = string
    labels = object({
      environment    = string
      managed_by     = string
      state_owner    = string
      application_id = string
    })
  })

  validation {
    condition = (
      var.fixture_configuration.contract_version == 1 &&
      var.fixture_configuration.configuration_kind == "fixture" &&
      contains(["operator", "synthetic"], var.fixture_configuration.configuration_class)
    )
    error_message = "fixture_configuration must select the Version 1 fixture interface and a known configuration class."
  }

  validation {
    condition = (
      var.fixture_configuration.application_id == "fixture-public" &&
      var.fixture_configuration.state_owner == "application" &&
      var.fixture_configuration.service_name == "fixture-public" &&
      var.fixture_configuration.admission_mode == "public" &&
      var.fixture_configuration.assertion_audience == null
    )
    error_message = "this root is exclusively bound to the public Fixture Application profile."
  }

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.fixture_configuration.project_id)) &&
      can(regex("^[1-9][0-9]{5,18}$", var.fixture_configuration.project_number)) &&
      can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$", var.fixture_configuration.region)) &&
      can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]$", var.fixture_configuration.application_id)) &&
      can(regex("^[a-z](?:[a-z0-9-]{0,47}[a-z0-9])?$", var.fixture_configuration.service_name))
    )
    error_message = "fixture project, region, application, and service identifiers must use their canonical Version 1 forms."
  }

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{1,61}[a-z0-9]-docker\\.pkg\\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/[a-z][a-z0-9_-]{0,126}/[a-z][a-z0-9._-]{0,126}@sha256:[0-9a-f]{64}$", var.fixture_configuration.image_digest)) &&
      startswith(var.fixture_configuration.image_digest, "${var.fixture_configuration.region}-docker.pkg.dev/${var.fixture_configuration.project_id}/")
    )
    error_message = "fixture image must be an immutable regional Artifact Registry digest in the configured project."
  }

  validation {
    condition = (
      can(regex("^https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~:/?#\\[\\]@!$&'()*+,;=%-]*)?$", var.fixture_configuration.platform_issuer)) &&
      can(regex("^serviceAccount:[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\\.iam\\.gserviceaccount\\.com$", var.fixture_configuration.edge_caller_principal)) &&
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.fixture_configuration.network_host_project_id)) &&
      var.fixture_configuration.vpc_egress == "all-traffic" &&
      startswith(var.fixture_configuration.shared_network_reference, "projects/${var.fixture_configuration.network_host_project_id}/global/networks/") &&
      startswith(var.fixture_configuration.application_subnet_reference, "projects/${var.fixture_configuration.network_host_project_id}/regions/${var.fixture_configuration.region}/subnetworks/")
    )
    error_message = "platform issuer and edge caller must be canonical non-secret references in the configured project."
  }

  validation {
    condition = (
      var.fixture_configuration.labels.environment == "qualification" &&
      var.fixture_configuration.labels.managed_by == "terraform" &&
      var.fixture_configuration.labels.state_owner == "application" &&
      var.fixture_configuration.labels.application_id == "fixture-public"
    )
    error_message = "fixture labels must identify the qualification environment and exact Application State owner."
  }

  validation {
    condition = var.fixture_configuration.configuration_class == "synthetic" || (
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.fixture_configuration.project_id)) &&
      var.fixture_configuration.project_id != "comfforts-platform-non-prod" &&
      var.fixture_configuration.network_host_project_id == "comfforts-platform-non-prod" &&
      var.fixture_configuration.region == "us-west1" &&
      var.fixture_configuration.platform_issuer == "https://apps-staging.comfforts.com/_platform" &&
      !strcontains(var.fixture_configuration.image_digest, "synthetic") &&
      !strcontains(var.fixture_configuration.edge_caller_principal, "synthetic")
    )
    error_message = "operator fixture configuration must use the reviewed non-production scope and cannot select reserved synthetic values."
  }
}

variable "destruction_enabled" {
  description = "Explicit operator-controlled transition that permits this fixture root to be destroyed."
  type        = bool
  default     = false
}

variable "platform_reference" {
  description = "Typed non-secret Platform State reference consumed as data."
  type = object({
    reference_kind               = string
    state_owner                  = string
    owner_id                     = string
    project_id                   = string
    project_number               = string
    region                       = string
    platform_issuer              = string
    public_key_reference         = string
    edge_caller_principal        = string
    shared_network_reference     = string
    application_subnet_reference = string
  })

  validation {
    condition = (
      var.platform_reference.reference_kind == "platform" &&
      var.platform_reference.state_owner == "platform" &&
      var.platform_reference.owner_id == "app-platform"
    )
    error_message = "platform_reference must identify only the independently owned Platform State."
  }

  validation {
    condition = (
      can(regex("^[1-9][0-9]{5,18}$", var.platform_reference.project_number)) &&
      can(regex("^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])$", var.platform_reference.region)) &&
      can(regex("^https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~:/?#\\[\\]@!$&'()*+,;=%-]*)?$", var.platform_reference.platform_issuer)) &&
      can(regex("^https://[A-Za-z0-9.-]+(?:/[A-Za-z0-9._~:/?#\\[\\]@!$&'()*+,;=%-]*)?$", var.platform_reference.public_key_reference)) &&
      can(regex("^serviceAccount:[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\\.iam\\.gserviceaccount\\.com$", var.platform_reference.edge_caller_principal))
    )
    error_message = "platform_reference fields must use their canonical Version 1 forms."
  }

  validation {
    condition = (
      var.platform_reference.project_id == var.fixture_configuration.network_host_project_id &&
      var.platform_reference.region == var.fixture_configuration.region &&
      var.platform_reference.platform_issuer == var.fixture_configuration.platform_issuer &&
      var.platform_reference.edge_caller_principal == var.fixture_configuration.edge_caller_principal &&
      var.platform_reference.shared_network_reference == var.fixture_configuration.shared_network_reference &&
      var.platform_reference.application_subnet_reference == var.fixture_configuration.application_subnet_reference &&
      endswith(var.platform_reference.platform_issuer, "/_platform") &&
      var.platform_reference.public_key_reference == "${trimsuffix(var.platform_reference.platform_issuer, "/_platform")}/.well-known/jwks.json"
    )
    error_message = "platform_reference must exactly match the fixture's project, region, issuer, caller, and derived public-key reference."
  }
}
