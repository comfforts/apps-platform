mock_provider "google" {
  override_during = plan
}

variables {
  fixture_configuration = jsondecode(file("../../../config/examples/fixture-multi-attachment.synthetic.v1.json"))
  platform_reference    = jsondecode(file("../../../config/examples/cross-state-platform.synthetic.v1.json")).reference
}

run "plans_one_application_with_two_targets" {
  command = plan

  assert {
    condition = (
      output.attachment_references.web.owner_id == "fixture-multi-attachment" &&
      output.attachment_references.web.attachment_id == "web" &&
      output.attachment_references.web.resource_reference == "urn:comfforts:app-platform:gcp:cloud-run:123456789012:us-west1:fixture-multi-attachment-web" &&
      output.attachment_references.api.owner_id == "fixture-multi-attachment" &&
      output.attachment_references.api.attachment_id == "api" &&
      output.attachment_references.api.resource_reference == "urn:comfforts:app-platform:gcp:cloud-run:123456789012:us-west1:fixture-multi-attachment-api" &&
      output.attachment_references.web.audience == output.attachment_references.api.audience
    )
    error_message = "fixture-multi-attachment must expose one complete two-target attachment set"
  }

  assert {
    condition = (
      module.web.policy_summary.target_marker == "web" &&
      module.api.policy_summary.target_marker == "api" &&
      module.web.policy_summary.assertion_audience == "urn:comfforts:app-platform:audience:fixture-multi-attachment" &&
      module.api.policy_summary.assertion_audience == module.web.policy_summary.assertion_audience &&
      module.web.policy_summary.ingress == "INGRESS_TRAFFIC_INTERNAL_ONLY" &&
      module.api.policy_summary.ingress == "INGRESS_TRAFFIC_INTERNAL_ONLY" &&
      module.web.policy_summary.vpc_egress == "ALL_TRAFFIC" &&
      module.api.policy_summary.vpc_egress == "ALL_TRAFFIC" &&
      module.web.policy_summary.edge_caller_role == "roles/run.invoker" &&
      module.api.policy_summary.edge_caller_role == "roles/run.invoker" &&
      module.web.policy_summary.runtime_identity_account_id != module.api.policy_summary.runtime_identity_account_id &&
      module.web.policy_summary.configured_labels.application_id == "fixture-multi-attachment" &&
      module.api.policy_summary.configured_labels.application_id == "fixture-multi-attachment"
    )
    error_message = "both targets must retain independent runtime identities and one application policy"
  }
}
