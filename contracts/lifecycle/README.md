# AP-M9 lifecycle contracts

Version 1 | Status: AP-M9-W3 environment profiles implemented; no operator or provider action

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

Lifecycle schemas and their relationship validation are added by the remaining AP-M9-W3 commits.
This package intentionally exposes no prompt, approval, execution, resume, provider, Terraform,
DNS, credential, or mutation behavior; those remain AP-M9-W4 and later work.
