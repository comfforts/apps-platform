# App Platform infrastructure configuration contracts

Version 1.2 | Status: AP-M7-W3 implemented, AP-M7-W4 through W8 root interfaces consumed,
AP-M7-W9 inert templates bound to the workflow contract, and the AP-M8-W2 operator-manifest
contract and deterministic chain validator implemented; synthetic repository examples only; no
accepted operator manifest, backend operation, provider operation, or deployment

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
| `schemas/operator-input-manifest.v1.schema.json` | `urn:comfforts:app-platform:infrastructure-config:operator-input-manifest:v1` | AP-M8-W2 append-only non-secret operator-input revision; implemented with deterministic chain validation |

`examples/` contains only `configuration_class: synthetic` documents. They use reserved synthetic
names, identities, revisions, and digests to exercise every approved configuration and workflow
shape. They are test material, not defaults or deployable values. The loader rejects them unless a
caller explicitly selects `allow_synthetic=True`; the operator path always leaves that flag false.

## AP-M8-W2 operator-manifest boundary

AP-M8-W2 extends this existing configuration module rather than creating a deployment module. The
repository may contain only the closed Version 1 schema, pure validation implementation, and
explicitly synthetic examples. The accepted operator manifest is created only after this slice
merges so it can bind the exact protected-main revision. It remains in an owner-approved non-Git
location and never becomes a repository example, default, credential source, or deployment input
without its own recorded approval.

One initial revision records every reviewed value known before an external mutation. A fact that
can exist only after a later approved operation enters one immutable successor revision that names
and binds its predecessor. A successor never edits or retroactively completes an earlier revision.
The schema and validator do not discover a value from GitHub, GCP, Terraform state, an environment
variable, Finance Assistant, or another manifest chain.

AP-M8-W2 creates no protected environment, workflow, federation resource, service account, IAM
binding, backend, state, provider resource, image, Registration Generation, DNS record, evidence
bundle, or permission to begin AP-M8-W3.

## Loader interface

`load_configuration_document(path, expected_kind)` loads at most 256 KiB of UTF-8 JSON, rejects
duplicate keys, floating-point values, invalid Unicode scalars, unknown fields, unsupported schema
keywords, and unresolved schema references, then applies deterministic semantic policy. It reads
only the explicit file and local schemas. It reads no environment variable, credential, Terraform
state, provider response, repository setting, or network resource.

`validate_configuration(value, expected_kind)` applies the same schema and policy to an in-memory
value. Violations are stable `contracts.validation.Violation` values ordered by JSON Pointer, code,
and message. No accepted value is returned with a violation.

`load_operator_manifest_chain(paths)` and `validate_operator_manifest_chain(revisions)` expose the
AP-M8-W2 chain interface. They accept revisions in predecessor order and return either the complete
immutable values plus their canonical SHA-256 digests or ordered violations and no trusted digest.
Canonicalization sorts closed set-like inputs while preserving the append-only generated-fact
order. `MANIFEST_CHAIN_INVALID` means revision numbering, predecessor binding, immutable inputs,
fresh approval, or the generated-fact prefix is inconsistent.

The chain interface permits only the source revision, source-bound evidence prefix, approval
reference, predecessor digest, and newly appended generated facts to vary. All repository,
environment, resource, identity, backend, registration, and ownership selections remain immutable
within one manifest chain. The implementation reads only the explicit bounded local documents; it
does not inspect Git, an environment variable, a credential, a repository setting, Terraform, or a
provider.

After this repository slice merges, validate one explicit real chain from a private working
directory by passing every revision in predecessor order:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m infrastructure.config.operator_manifest \
  /absolute/private/path/revision-1.json \
  /absolute/private/path/revision-2.json
```

The command emits only `accepted` plus canonical revision digests, or `rejected` plus ordered code,
pointer, and message fields. It never prints manifest values, follows no path from a document, and
writes no file. There is deliberately no switch that permits synthetic examples on this operator
entry point.

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
- exact AP-M8 non-production source, five protected environment classes, workflow-to-identity
  agreement, operation/environment separation, four state buckets, five state lineages, platform
  resource references, three synthetic qualification applications, and append-only generated
  facts.

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
complete `platform_configuration` object. AP-M7-W9 preserves it and binds five inert templates to
the Version 1 workflow operations without adding a Terraform root or provider resource. The
deterministic gate rejects disagreement. No root may consume another root's backend or
`terraform_remote_state`; reviewed cross-state-reference documents are the only exchange shape.
