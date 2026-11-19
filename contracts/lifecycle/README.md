# AP-M9 lifecycle contracts

Version 1 | Status: AP-M9-W3 lifecycle contracts implemented; no operator or provider action

This package owns the closed, non-secret AP-M9 Environment Profile and lifecycle document
interfaces. It is separate from the exact AP-M3 public-contract registry and the AP-M7
infrastructure-configuration registry. Loading or validating any document is credential-free,
non-mutating, and does not authorize an operator action.

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

## Specification and journal

| Schema | Stable identifier | Interface |
| --- | --- | --- |
| `schemas/environment-profile.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:environment-profile:v1` | stable decisions for one isolated environment |
| `schemas/deployment-specification.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:deployment-specification:v1` | exact source, ordered stages, allow-lists, output bindings, checkpoints, readback, stop behavior, and destructive boundary |
| `schemas/execution-journal.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:execution-journal:v1` | machine-generated, append-only, digest-chained execution progress |
| `schemas/environment-status.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:environment-status:v1` | truthful environment progress, blockers, and qualification state |
| `schemas/platform-integration-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1` | application-scoped non-secret platform endpoints, identity values, caller, attachment contract, and qualification status |
| `schemas/application-attachment-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v1` | application-owned target posture bound to an exact integration bundle digest |

Specification validation requires every consumed output to be declared by an earlier stage,
unique stage identifiers, explicit action and resource-type allow-lists, stop-on-failure behavior,
and no destructive scope outside a `destroy` operation. Specification completeness and owner
approval remain separate: this package represents no approval.

Journal relationship validation binds environment, operation, source revision, and specification
digest; limits entries and outputs to declared specification stages; requires every succeeded-stage
output; and proves that a later journal revision preserves every preceding entry and carries the
exact predecessor digest. A journal records a plan digest, never a saved or raw plan.

Environment Status binds the exact profile, source, specification, journal, last closed stage, and
journal outcome. A disabled production status carries `OWNERSHIP_TRANSFER_REQUIRED` without
inventing a source, specification, journal, or generated resource.

An integration bundle contains an OAuth client identifier and application audience only for an
authenticated access mode. A public bundle omits those identity values. No bundle admits an OAuth
client secret, application provider key, credential payload, Terraform state, saved plan, raw
provider response, or platform secret reference. Attachment validation preserves application
ownership and matches the integration bundle's application, environment, adapter, ingress, edge
caller, audience, and digest; it does not transfer target ownership to Platform State.

`test-vectors/valid/` contains one canonical, fully digest-bound synthetic staging chain covering
the five lifecycle documents. The vectors are deterministic contract examples only: their source
revisions, address, plan digest, OAuth identifier, and target reference do not describe deployed
resources or accepted operator input.

This package intentionally exposes no prompt, approval, execution, resume, provider, Terraform,
DNS, credential, or mutation behavior. AP-M9-W4 consumes these documents from the separate deep
operator module; provider and mutation behavior remain later work.
