# App Platform infrastructure configuration contracts

Version 1.4 | Status: AP-M7 contracts implemented; retired AP-M8 operator-manifest implementation
removed by AP-M9-W2; no accepted operator input or external operation

This directory contains closed, non-secret repository configuration contracts. It is subordinate
to the platform requirements, accepted ADRs, system design, implementation plan, and evaluation
strategy. A schema or synthetic example does not authorize backend initialization, credential
lookup, a provider call, repository-setting change, DNS change, or deployment.

## Active AP-M7 inventory

| Schema | Stable identifier | Interface |
| --- | --- | --- |
| `schemas/backend-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:backend:v1` | four exclusive backend state owners and bounded recovery input |
| `schemas/platform-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:platform:v1` | Shared Edge Platform State non-secret inputs |
| `schemas/fixture-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:fixture:v1` | one independent synthetic Application input |
| `schemas/cross-state-reference.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:cross-state-reference:v1` | typed non-secret references without state reads |
| `schemas/workflow-configuration.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:workflow:v1` | source-bound inert workflow-design input |

`examples/` contains only `configuration_class: synthetic` test material. The loader rejects those
documents unless a caller explicitly selects `allow_synthetic=True`. They are neither defaults nor
deployable operator values.

## Removed AP-M8 interface

AP-M9-W2 removed the retired operator-manifest schema, synthetic example, command, loader,
validator, digest logic, exports, and dedicated tests. The active package exposes only the AP-M7
configuration contracts listed above. Do not recreate or route an operator through the retired
interface. The factual delivery record is in
[`docs/history/ap_m8_manifest_delivery.md`](../../docs/history/ap_m8_manifest_delivery.md).

## Loader interface

`load_configuration_document(path, expected_kind)` loads at most 256 KiB of UTF-8 JSON, rejects
duplicate keys, floating-point values, invalid Unicode scalars, unknown fields, unsupported schema
keywords, and unresolved schema references, then applies deterministic semantic policy. It reads
only the explicit file and local schemas.

`validate_configuration(value, expected_kind)` applies the same schema and policy to an in-memory
value. Violations are stable `contracts.validation.Violation` values ordered by JSON Pointer, code,
and message. No accepted value is returned with a violation.

Semantic policy enforces state-owner separation, exact environment bindings, immutable image and
secret-version references, restricted cross-state exchange, source-bound workflow inputs, and
rejection of credential, secret, state, saved-plan, provider-response, private-key, token,
`.tfstate`, `.tfplan`, and `terraform_remote_state` material.

## Terraform boundary

The AP-M7 bootstrap, platform, and synthetic-application roots duplicate security-critical schema
constraints at their Terraform interfaces. The deterministic gate rejects disagreement. No root
may read another root through `terraform_remote_state`; reviewed non-secret references are the
only exchange shape.

AP-M9-W3 owns new small environment profiles and versioned lifecycle bundles. Do not extend these
AP-M7 contracts to infer that later interface.
