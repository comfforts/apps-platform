# Operator lifecycle and handoff contracts

Versions 1 through 3 application handoff contracts implemented | Scope: closed, non-secret
environment lifecycle, application handoff, and qualification-evidence documents; validation never
authorizes mutation

Version 1 handoff documents remain readable historical predecessors. Version 2 integration,
attachment, and registration-intent documents are the implemented application-handoff interface
and qualified fixture compatibility path. The ADR-017 Version 3 complete attachment-set schemas,
loader, vectors, and relationship validation are implemented for AP-M9-W12; operator projection,
provider readback, and activation remain later slices.

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

`load_versioned_lifecycle_document(path, expected_kind)` is the explicit compatibility entry point
for a reviewed Version 1, Version 2, or Version 3 handoff kind. Version-aware relationship
validation rejects a mixed-version family and requires a complete Version 3 registration intent.
The original Version 1 loader and relationship validator remain available only for explicit
historical Version 1 consumers.

## Contract inventory

| Schema | Stable identifier | Interface |
| --- | --- | --- |
| `schemas/environment-profile.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:environment-profile:v1` | stable decisions for one isolated environment |
| `schemas/deployment-specification.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:deployment-specification:v1` | separately confirmed destructive scope, ordered steps, and retained-resource boundary |
| `schemas/platform-integration-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1` | application-scoped non-secret platform endpoints, identity values, caller, attachment contract, and qualification status |
| `schemas/application-attachment-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v1` | application-owned target posture bound to an exact integration bundle digest |
| `schemas/qualification-evidence.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:qualification-evidence:v1` | redacted, revision-bound platform and fixture qualification results |
| `schemas/platform-integration-bundle.v2.schema.json` | `urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v2` | active application-scoped handoff with explicit Identity Delivery |
| `schemas/application-attachment-bundle.v2.schema.json` | `urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v2` | Version 2 target posture bound to the exact Version 2 integration bundle |
| `schemas/registration-intent.v2.schema.json` | `urn:comfforts:app-platform:lifecycle:registration-intent:v2` | explicit Admission Mode and Identity Delivery intent without member material |
| `schemas/platform-integration-bundle.v3.schema.json` | `urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v3` | application-scoped complete attachment-set limits and policy |
| `schemas/application-attachment-bundle.v3.schema.json` | `urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v3` | required root target plus optional complete additional targets |
| `schemas/registration-intent.v3.schema.json` | `urn:comfforts:app-platform:lifecycle:registration-intent:v3` | required root binding at `/` plus optional complete additional bindings |

Destructive-specification validation requires unique ordered steps, explicit action and resource
allow-lists, declared prior outputs, stop-on-failure behavior, and an exact deletion boundary.
Completeness and the operator's typed confirmation remain separate; this package grants neither.
Normal deployment preparation, read-only status, and atomic resume progress are private operator
state because they do not cross an ownership boundary.

An integration bundle identifies Accepted Source or Candidate Source and contains an OAuth client
identifier and application audience only when Identity Delivery is `optional` or `required`.
Public `none` omits those identity values. No bundle admits an OAuth client secret, application provider key,
credential payload, Terraform state, saved plan, raw provider response, or platform secret
reference. Attachment validation preserves application ownership and matches the integration
bundle's application, environment, adapter, ingress, edge caller, audience, and digest; it does not
transfer target ownership to Platform State.

Version 2 accepts exactly four Admission Mode/Identity Delivery pairs: public `none`, public
`optional`, authenticated `required`, and restricted `required`. The integration bundle,
attachment bundle, and registration intent must all be Version 2 and describe the same pair; a
mixed family or conflicting value fails closed. A readable Version 1 predecessor may be migrated
only by the operator's complete-generation transition: public becomes `none`, authenticated and
restricted become `required`, and every registration-scoped member is discarded. The contracts do
not enumerate or carry the environment member directory.

Version 3 retains those application-level policy pairs, fixes
`root_attachment_required=true` and `maximum_additional_attachments=15` in the integration bundle,
and preserves the singular target as a required root attachment. The registration intent preserves
its required root ID and forwarding mode and requires mount `/`. The attachment bundle optionally
adds a canonical `additional_attachments` array whose entries contain `attachment_id` and a closed
`target`; the intent optionally adds canonical `additional_attachment_bindings` entries containing
`attachment_id`, `mount_path`, and `forwarding_mode`. Both optional attributes may be absent for a
valid root-only handoff. When present, they contain the exact same additional IDs, include at most
fifteen entries, and cannot repeat the root ID. All targets share the application project, region,
network, owner, caller, Admission Mode, Identity Delivery, and audience. The inert contract seam accepts and
validates a complete same-version family; the current operator still rejects Version 3 before
provider readback or registration. Slice 3 will project a complete family into the existing
Version 2 multi-attachment registration only after every relationship and target passes.

The Version 3 vectors cover one root-only family and one
`fixture-multi-attachment` family with required `web` at `/` and optional `api` at `/api`. The
fixture names demonstrate the relationship only and are not allow-listed by the schemas.

Qualification Evidence binds observations to an exact environment, source authority and revision,
profile, specification, final deployment progress, registration generation, and component and fixture
revisions. It contains only redacted results permitted by its schema. A valid evidence document
records what was evaluated; it does not make an unevaluated environment qualified.

`test-vectors/valid/` contains canonical synthetic examples for Version 1 through Version 3
integration and attachment bundles, Version 2/3 registration intents, and Version 1 qualification
evidence. The vectors are deterministic contract examples only; their source revisions, addresses,
OAuth identifier, and target reference do not describe deployed resources or accepted operator
input.

This package intentionally exposes no prompt, approval, execution, resume, provider, Terraform,
DNS, credential, or mutation behavior. The operator module consumes these documents for
preparation, deployment, status, non-secret application handoff, attachment validation,
qualification, and recovery. Provider adapters and generation control remain separate runtime
responsibilities; schema validation alone is not evidence that any external operation occurred.
