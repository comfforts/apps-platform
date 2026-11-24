mock_provider "google" {
  override_during = plan
}

variables {
  fixture_configuration = jsondecode(file("../../../config/examples/fixture-restricted.synthetic.v1.json"))
  platform_reference    = jsondecode(file("../../../config/examples/cross-state-platform.synthetic.v1.json")).reference
}

run "plans_isolated_restricted_fixture" {
  command = plan

  assert {
    condition = (
      output.attachment_reference.reference_kind == "attachment" &&
      output.attachment_reference.state_owner == "application" &&
      output.attachment_reference.owner_id == "fixture-restricted" &&
      output.attachment_reference.application_id == "fixture-restricted" &&
      output.attachment_reference.attachment_id == "primary" &&
      output.attachment_reference.adapter_kind == "gcp-cloud-run-v1" &&
      output.attachment_reference.resource_reference == "urn:comfforts:app-platform:gcp:cloud-run:123456789012:us-west1:fixture-restricted" &&
      output.attachment_reference.audience == "urn:comfforts:app-platform:audience:fixture-restricted"
    )
    error_message = "fixture-restricted must expose one canonical application-owned attachment"
  }

  assert {
    condition = (
      module.fixture_application.policy_summary.ingress == "INGRESS_TRAFFIC_INTERNAL_ONLY" &&
      module.fixture_application.policy_summary.network_reference == "projects/synthetic-platform/global/networks/synthetic-shared" &&
      module.fixture_application.policy_summary.subnetwork_reference == "projects/synthetic-platform/regions/us-west1/subnetworks/synthetic-applications" &&
      module.fixture_application.policy_summary.vpc_egress == "ALL_TRAFFIC" &&
      !module.fixture_application.policy_summary.invoker_iam_disabled &&
      !module.fixture_application.policy_summary.unauthenticated_invocation &&
      module.fixture_application.policy_summary.edge_caller_role == "roles/run.invoker" &&
      module.fixture_application.policy_summary.minimum_instances == 0 &&
      module.fixture_application.policy_summary.maximum_instances == 1 &&
      module.fixture_application.policy_summary.cpu == "1" &&
      module.fixture_application.policy_summary.memory == "512Mi" &&
      module.fixture_application.policy_summary.concurrency == 10 &&
      module.fixture_application.policy_summary.runtime_identity_deletion == "PREVENT" &&
      module.fixture_application.policy_summary.service_deletion_protection &&
      !module.fixture_application.policy_summary.platform_resource_management &&
      !module.fixture_application.policy_summary.application_feature_entitlement
    )
    error_message = "fixture-restricted must retain the complete isolation, scaling, and non-destruction policy"
  }

  assert {
    condition = (
      module.fixture_application.policy_summary.admission_mode == "restricted" &&
      module.fixture_application.policy_summary.assertion_audience == "urn:comfforts:app-platform:audience:fixture-restricted" &&
      module.fixture_application.policy_summary.platform_issuer == "https://apps.example.invalid/_platform" &&
      module.fixture_application.policy_summary.public_key_reference == "https://apps.example.invalid/.well-known/jwks.json" &&
      module.fixture_application.policy_summary.configured_labels.environment == "qualification" &&
      module.fixture_application.policy_summary.configured_labels.managed_by == "terraform" &&
      module.fixture_application.policy_summary.configured_labels.state_owner == "application" &&
      module.fixture_application.policy_summary.configured_labels.application_id == "fixture-restricted"
    )
    error_message = "fixture-restricted must consume only its reviewed non-secret identity data and ownership labels"
  }
}
