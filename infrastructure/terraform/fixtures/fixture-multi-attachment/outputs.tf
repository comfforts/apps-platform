output "attachment_references" {
  description = "Complete typed attachment set owned by fixture-multi-attachment Application State."
  value = {
    api = {
      reference_kind     = "attachment"
      state_owner        = "application"
      owner_id           = var.fixture_configuration.application_id
      application_id     = var.fixture_configuration.application_id
      attachment_id      = "api"
      adapter_kind       = "gcp-cloud-run-v1"
      resource_reference = "urn:comfforts:app-platform:gcp:cloud-run:${var.fixture_configuration.project_number}:${var.fixture_configuration.region}:${module.api.service_name}"
      audience           = var.fixture_configuration.assertion_audience
    }
    web = {
      reference_kind     = "attachment"
      state_owner        = "application"
      owner_id           = var.fixture_configuration.application_id
      application_id     = var.fixture_configuration.application_id
      attachment_id      = "web"
      adapter_kind       = "gcp-cloud-run-v1"
      resource_reference = "urn:comfforts:app-platform:gcp:cloud-run:${var.fixture_configuration.project_number}:${var.fixture_configuration.region}:${module.web.service_name}"
      audience           = var.fixture_configuration.assertion_audience
    }
  }

  precondition {
    condition = (
      var.fixture_configuration.application_id == "fixture-multi-attachment" &&
      module.web.service_name == "fixture-multi-attachment-web" &&
      module.api.service_name == "fixture-multi-attachment-api"
    )
    error_message = "attachment_references cannot transfer fixture-multi-attachment ownership."
  }
}
