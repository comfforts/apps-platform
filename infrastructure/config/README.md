# AP-M7 infrastructure configuration contracts

Version 1 | Status: AP-M7-W3 implemented and AP-M7-W4 through W7 root interfaces consumed; synthetic
repository examples only; no operator configuration, backend operation, provider operation, or
deployment

This directory defines the closed, non-secret inputs for later AP-M7 Terraform roots and inert
workflow templates. The schemas and loader are subordinate to the platform requirements, accepted
ADRs, system design, AP-M7 plan, and AP-EVAL-M7. They do not authorize a plan, apply, backend
initialization, credential lookup, cloud action, DNS change, or repository-setting change.

## Inventory

| Schema | Stable identifier | Interface |
| --- | --- | --- |
| `schemas/backend-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:backend:v1` | Four exclusive backend state owners and bounded recovery input |
| `schemas/platform-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:platform:v1` | Shared Edge Platform State non-secret inputs |
| `schemas/fixture-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:fixture:v1` | One independently owned Fixture Application input |
| `schemas/cross-state-reference.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:cross-state-reference:v1` | Typed backend, platform, or attachment reference without state reads |
| `schemas/workflow-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:workflow:v1` | Source-bound plan, apply, rollback, force-unlock, or destroy authority input |

`examples/` contains only `configuration_class: synthetic` documents. They use reserved synthetic
names, identities, revisions, and digests to exercise every approved configuration and workflow
shape. They are test material, not defaults or deployable values. The loader rejects them unless a
caller explicitly selects `allow_synthetic=True`; the operator path always leaves that flag false.

## Loader interface

`load_configuration_document(path, expected_kind)` loads at most 256 KiB of UTF-8 JSON, rejects
duplicate keys, floating-point values, invalid Unicode scalars, unknown fields, unsupported schema
keywords, and unresolved schema references, then applies deterministic semantic policy. It reads
only the explicit file and local schemas. It reads no environment variable, credential, Terraform
state, provider response, repository setting, or network resource.

`validate_configuration(value, expected_kind)` applies the same schema and policy to an in-memory
value. Violations are stable `contracts.validation.Violation` values ordered by JSON Pointer, code,
and message. No accepted value is returned with a violation.

Semantic policy enforces:

- the four exclusive state owners and distinct state buckets;
- the fixed project, number, region, qualification hostname, and repository for operator-class
  inputs;
- the three approved Fixture Application identities and their public, authenticated, or restricted
  profiles;
- exact owner binding for backend, platform issuer/public-key/caller, and `gcp-cloud-run-v1`
  attachment references;
- immutable Artifact Registry image digests, numeric Secret Manager versions, scoped KMS key
  versions, and generation/source digest binding;
- repository-and-environment-bound protected subjects, plan-digest rules, and exact destructive
  root targets; and
- rejection of credential, secret value, restricted-member, state-address, saved-plan, provider-
  response, private-key, token, `.tfstate`, `.tfplan`, and `terraform_remote_state` material.

## Terraform boundary

AP-M7-W4 introduces the bootstrap root's single `backend_configuration` variable together with its
owning implementation and duplicates every applicable security-critical backend schema type and
validation. AP-M7-W5 adds the `fixture_configuration` and typed `platform_reference` inputs to each
independent Fixture Application root, including the non-secret issuer, public-key, audience, and
edge-caller binding. The AP-M7-W6 Platform State root consumes the complete
`platform_configuration` object and exposes only minimal typed platform references. AP-M7-W7 adds
exactly three typed Fixture Application attachment references as a second explicit input and
consumes them only as data; the Shared Edge module performs no application lookup or management.
AP-M7-W8 preserves that agreement while composing the platform-controls module from the same
complete `platform_configuration` object. AP-M7-W9 must preserve it while adding only inert workflow
templates. The deterministic gate rejects disagreement. No root may consume another root's backend
or `terraform_remote_state`; reviewed cross-state-reference documents are the only exchange shape.
