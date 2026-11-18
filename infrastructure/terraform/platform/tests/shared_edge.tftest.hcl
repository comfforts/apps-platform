mock_provider "google" {
  override_during = plan
}

variables {
  platform_configuration = jsondecode(file("../../config/examples/platform.synthetic.v1.json"))
  fixture_attachment_references = [
    jsondecode(file("../../config/examples/cross-state-attachment-public.synthetic.v1.json")),
    jsondecode(file("../../config/examples/cross-state-attachment.synthetic.v1.json")),
    jsondecode(file("../../config/examples/cross-state-attachment-restricted.synthetic.v1.json")),
  ]
}

run "plans_one_immutable_shared_edge_and_hostname_forwarder" {
  command = plan

  assert {
    condition = (
      module.shared_edge.policy_summary.service_name == "app-platform-edge" &&
      startswith(module.shared_edge.policy_summary.candidate_revision, "app-platform-edge-g1-") &&
      length(module.shared_edge.policy_summary.candidate_revision) == 33 &&
      module.shared_edge.policy_summary.immutable_image_digest == "us-west1-docker.pkg.dev/synthetic-platform/synthetic-images/shared-edge@sha256:0000000000000000000000000000000000000000000000000000000000000000" &&
      module.shared_edge.policy_summary.registration_generation.source_revision == "0000000000000000000000000000000000000000" &&
      module.shared_edge.policy_summary.registration_generation.generation == 1 &&
      module.shared_edge.policy_summary.registration_generation.generation_digest == "sha256:0000000000000000000000000000000000000000000000000000000000000000" &&
      module.shared_edge.policy_summary.registration_generation.content_digest == "sha256:1111111111111111111111111111111111111111111111111111111111111111" &&
      module.shared_edge.policy_summary.registration_generation.object_name == "generations/1/compiled.json" &&
      module.shared_edge.policy_summary.registration_generation.object_generation == 1
    )
    error_message = "the edge revision must bind the immutable source, image, generation, and configuration object inputs"
  }

  assert {
    condition = (
      module.shared_edge.policy_summary.binding_versions.compiler == 1 &&
      module.shared_edge.policy_summary.binding_versions.identity_contract == 1 &&
      module.shared_edge.policy_summary.binding_versions.attachment_adapter == "gcp-cloud-run-v1" &&
      module.shared_edge.policy_summary.binding_versions.platform_configuration == 1 &&
      module.shared_edge.policy_summary.configuration_bucket == "synthetic-platform-configuration"
    )
    error_message = "the candidate must bind the approved compiler, identity, attachment, and platform configuration versions"
  }

  assert {
    condition = (
      length(module.shared_edge.policy_summary.attachment_references) == 3 &&
      toset([for value in module.shared_edge.policy_summary.attachment_references : value.application_id]) == toset([
        "fixture-public",
        "fixture-authenticated",
        "fixture-restricted",
      ]) &&
      alltrue([
        for value in module.shared_edge.policy_summary.attachment_references :
        value.state_owner == "application" &&
        value.owner_id == value.application_id &&
        value.attachment_id == "primary" &&
        value.adapter_kind == "gcp-cloud-run-v1" &&
        startswith(value.resource_reference, "urn:comfforts:app-platform:gcp:cloud-run:123456789012:us-west1:")
      ])
    )
    error_message = "the platform root must consume exactly three typed application-owned attachment references as data"
  }

  assert {
    condition = (
      module.shared_edge.policy_summary.runtime.region == "us-west1" &&
      module.shared_edge.policy_summary.runtime.ingress == "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" &&
      module.shared_edge.policy_summary.runtime.default_uri_disabled &&
      !module.shared_edge.policy_summary.runtime.invoker_iam_disabled &&
      module.shared_edge.policy_summary.runtime.invoker_role == "roles/run.invoker" &&
      module.shared_edge.policy_summary.runtime.invoker_member == "allUsers" &&
      !module.shared_edge.policy_summary.runtime.public_direct_origin &&
      module.shared_edge.policy_summary.runtime.minimum_instances == 0 &&
      module.shared_edge.policy_summary.runtime.maximum_instances == 2 &&
      module.shared_edge.policy_summary.runtime.cpu == "1" &&
      module.shared_edge.policy_summary.runtime.memory == "512Mi" &&
      module.shared_edge.policy_summary.runtime.concurrency == 20 &&
      module.shared_edge.policy_summary.runtime.provider_timeout_seconds == 3600 &&
      module.shared_edge.policy_summary.runtime.runtime_stream_limit_seconds == 3300 &&
      module.shared_edge.policy_summary.runtime.deletion_protection &&
      module.shared_edge.policy_summary.runtime.traffic_type == "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION" &&
      module.shared_edge.policy_summary.runtime.traffic_revision == module.shared_edge.policy_summary.candidate_revision &&
      module.shared_edge.policy_summary.runtime.traffic_percent == 100
    )
    error_message = "the edge runtime must preserve the approved bounded profile, closed origin, and explicit 100-percent candidate"
  }

  assert {
    condition = (
      module.shared_edge.policy_summary.forwarding.hostname == "apps.example.invalid" &&
      module.shared_edge.policy_summary.forwarding.address_scope == "global" &&
      module.shared_edge.policy_summary.forwarding.address_type == "EXTERNAL" &&
      module.shared_edge.policy_summary.forwarding.ip_version == "IPV4" &&
      module.shared_edge.policy_summary.forwarding.network_tier == "PREMIUM" &&
      module.shared_edge.policy_summary.forwarding.load_balancing_scheme == "EXTERNAL_MANAGED" &&
      module.shared_edge.policy_summary.forwarding.managed_certificate &&
      module.shared_edge.policy_summary.forwarding.http_to_https_redirect &&
      module.shared_edge.policy_summary.forwarding.serverless_backend_count == 1 &&
      module.shared_edge.policy_summary.forwarding.https_url_map_count == 1 &&
      module.shared_edge.policy_summary.forwarding.application_prefix_routes == 0 &&
      !module.shared_edge.policy_summary.forwarding.cdn &&
      !module.shared_edge.policy_summary.forwarding.waf &&
      !module.shared_edge.policy_summary.forwarding.dns_record
    )
    error_message = "forwarding must use one global hostname-level HTTPS load balancer with redirect and no registration-derived provider routes"
  }

  assert {
    condition = (
      !module.shared_edge.policy_summary.application_runtime_management &&
      !module.shared_edge.policy_summary.attachment_discovery &&
      !module.shared_edge.policy_summary.arbitrary_target_url
    )
    error_message = "Platform State must not manage, discover, or accept arbitrary URLs for application-owned runtimes"
  }
}
