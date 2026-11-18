output "attachment_reference" {
  description = "Typed non-secret gcp-cloud-run-v1 attachment owned by fixture-authenticated Application State."
  value = {
    reference_kind     = "attachment"
    state_owner        = "application"
    owner_id           = var.fixture_configuration.application_id
    application_id     = var.fixture_configuration.application_id
    attachment_id      = "primary"
    adapter_kind       = "gcp-cloud-run-v1"
    resource_reference = "urn:comfforts:app-platform:gcp:cloud-run:${var.fixture_configuration.project_number}:${var.fixture_configuration.region}:${module.fixture_application.service_name}"
    audience           = var.fixture_configuration.assertion_audience
  }

  precondition {
    condition = (
      var.fixture_configuration.application_id == "fixture-authenticated" &&
      module.fixture_application.service_name == "fixture-authenticated"
    )
    error_message = "attachment_reference cannot transfer fixture-authenticated ownership."
  }
}
