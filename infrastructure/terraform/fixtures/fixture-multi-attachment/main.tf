module "web" {
  source = "../../modules/fixture-application"

  runtime_configuration = {
    project_id                   = var.fixture_configuration.project_id
    region                       = var.fixture_configuration.region
    application_id               = var.fixture_configuration.application_id
    service_name                 = "fixture-multi-attachment-web"
    runtime_identity_account_id  = "fixture-multi-web-runtime"
    image_digest                 = var.fixture_configuration.image_digest
    admission_mode               = var.fixture_configuration.admission_mode
    assertion_audience           = var.fixture_configuration.assertion_audience
    platform_issuer              = var.platform_reference.platform_issuer
    public_key_reference         = var.platform_reference.public_key_reference
    shared_network_reference     = var.platform_reference.shared_network_reference
    application_subnet_reference = var.platform_reference.application_subnet_reference
    labels                       = var.fixture_configuration.labels
    destruction_enabled          = var.destruction_enabled
    target_marker                = "web"
  }
  edge_caller_principal = var.platform_reference.edge_caller_principal
}

module "api" {
  source = "../../modules/fixture-application"

  runtime_configuration = {
    project_id                   = var.fixture_configuration.project_id
    region                       = var.fixture_configuration.region
    application_id               = var.fixture_configuration.application_id
    service_name                 = "fixture-multi-attachment-api"
    runtime_identity_account_id  = "fixture-multi-api-runtime"
    image_digest                 = var.fixture_configuration.image_digest
    admission_mode               = var.fixture_configuration.admission_mode
    assertion_audience           = var.fixture_configuration.assertion_audience
    platform_issuer              = var.platform_reference.platform_issuer
    public_key_reference         = var.platform_reference.public_key_reference
    shared_network_reference     = var.platform_reference.shared_network_reference
    application_subnet_reference = var.platform_reference.application_subnet_reference
    labels                       = var.fixture_configuration.labels
    destruction_enabled          = var.destruction_enabled
    target_marker                = "api"
  }
  edge_caller_principal = var.platform_reference.edge_caller_principal
}
