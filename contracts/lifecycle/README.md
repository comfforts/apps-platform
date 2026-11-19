# AP-M9 lifecycle contracts

Version 1 | Status: AP-M9-W3 profiles, specifications, and journals implemented; no operator or
provider action

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

Specification validation requires every consumed output to be declared by an earlier stage,
unique stage identifiers, explicit action and resource-type allow-lists, stop-on-failure behavior,
and no destructive scope outside a `destroy` operation. Specification completeness and owner
approval remain separate: this package represents no approval.

Journal relationship validation binds environment, operation, source revision, and specification
digest; limits entries and outputs to declared specification stages; requires every succeeded-stage
output; and proves that a later journal revision preserves every preceding entry and carries the
exact predecessor digest. A journal records a plan digest, never a saved or raw plan.

Environment Status and application handoff schemas are added by the remaining AP-M9-W3 commits.
This package intentionally exposes no prompt, approval, execution, resume, provider, Terraform,
DNS, credential, or mutation behavior; those remain AP-M9-W4 and later work.
