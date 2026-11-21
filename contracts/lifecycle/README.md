# Operator lifecycle and handoff contracts

Version 1 | Scope: closed, non-secret environment lifecycle, application handoff, and
qualification-evidence documents; validation never authorizes mutation

This package defines the documents that connect environment preparation, deployment, status,
application handoff, and qualification. It is separate from the platform/application registry in
the parent directory and from the infrastructure-configuration registry. Loading or validating a
document is credential-free and non-mutating; it does not approve or execute an operator action.

## Environment profiles

`infrastructure/config/profiles/` contains exactly two committed profiles:

- `staging.v1.json` fixes the approved non-production project, project number, region, hostname,
  GCP provider class, and external Squarespace DNS class;
- `production.v1.json` fixes only the known production owner decisions and remains disabled with
  `OWNERSHIP_TRANSFER_REQUIRED`.

Profiles contain no generated resource name, repository identifier, image or plan digest, address,
OAuth identifier, secret version, state lineage, provider response, execution outcome, credential,
secret, state, or saved plan. Unknown and cross-environment values fail closed.

## Loader and digest

`load_lifecycle_document(path, expected_kind)` reads only the explicit file and reviewed local
schemas, with a 256-KiB default limit. It rejects duplicate keys, floating-point values, invalid
Unicode scalar values, unknown fields, placeholders, prohibited material, and non-canonical JSON.
A single final LF is accepted as a repository text-file terminator and is excluded from canonical
bytes and the digest. The digest is lowercase SHA-256 over App Platform Canonical JSON Version 1,
prefixed with `sha256:`.

## Contract inventory

| Schema | Stable identifier | Interface |
| --- | --- | --- |
| `schemas/environment-profile.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:environment-profile:v1` | stable decisions for one isolated environment |
| `schemas/deployment-specification.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:deployment-specification:v1` | separately confirmed destructive scope, ordered steps, and retained-resource boundary |
| `schemas/platform-integration-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1` | application-scoped non-secret platform endpoints, identity values, caller, attachment contract, and qualification status |
| `schemas/application-attachment-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v1` | application-owned target posture bound to an exact integration bundle digest |
| `schemas/qualification-evidence.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:qualification-evidence:v1` | redacted, revision-bound platform and fixture qualification results |

Destructive-specification validation requires unique ordered steps, explicit action and resource
allow-lists, declared prior outputs, stop-on-failure behavior, and an exact deletion boundary.
Completeness and the operator's typed confirmation remain separate; this package grants neither.
Normal deployment preparation, read-only status, and atomic resume progress are private operator
state because they do not cross an ownership boundary.

An integration bundle identifies Accepted Source or Candidate Source and contains an OAuth client
identifier and application audience only for an authenticated access mode. A public bundle omits
those identity values. No bundle admits an OAuth client secret, application provider key,
credential payload, Terraform state, saved plan, raw provider response, or platform secret
reference. Attachment validation preserves application ownership and matches the integration
bundle's application, environment, adapter, ingress, edge caller, audience, and digest; it does not
transfer target ownership to Platform State.

Qualification Evidence binds observations to an exact environment, source authority and revision,
profile, specification, final deployment progress, registration generation, and component and fixture
revisions. It contains only redacted results permitted by its schema. A valid evidence document
records what was evaluated; it does not make an unevaluated environment qualified.

`test-vectors/valid/` contains canonical synthetic examples for the integration bundle, attachment
bundle, and qualification evidence. The vectors are deterministic
contract examples only; their source revisions, addresses, OAuth identifier, and target reference
do not describe deployed resources or accepted operator input.

This package intentionally exposes no prompt, approval, execution, resume, provider, Terraform,
DNS, credential, or mutation behavior. The operator module consumes these documents for
preparation, deployment, status, non-secret application handoff, attachment validation,
qualification, and recovery. Provider adapters and generation control remain separate runtime
responsibilities; schema validation alone is not evidence that any external operation occurred.
