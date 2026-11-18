module "fixture_application" {
  source = "../../modules/fixture-application"

  runtime_configuration = {
    project_id                  = var.fixture_configuration.project_id
    region                      = var.fixture_configuration.region
    application_id              = var.fixture_configuration.application_id
    service_name                = var.fixture_configuration.service_name
    runtime_identity_account_id = "${var.fixture_configuration.application_id}-runtime"
    image_digest                = var.fixture_configuration.image_digest
    admission_mode              = var.fixture_configuration.admission_mode
    assertion_audience          = var.fixture_configuration.assertion_audience == null ? "" : var.fixture_configuration.assertion_audience
    platform_issuer             = var.platform_reference.platform_issuer
    public_key_reference        = var.platform_reference.public_key_reference
    labels                      = var.fixture_configuration.labels
  }
  edge_caller_principal = var.platform_reference.edge_caller_principal
}
