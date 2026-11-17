# App Platform repository layout

Status: authoritative dedicated-root layout; initial extraction and repository settings complete;
reconciliation, canonical cutover, and source-repository cleanup pending; no provider operation or
infrastructure implemented

The project is organized at the dedicated repository root produced by the history-preserving
subtree extraction. Paths remain project-relative so repository identity does not alter platform
contracts, verification, or ownership boundaries.

## Current layout

| Path | Owner |
| --- | --- |
| `AGENTS.md` | Platform engineering workflow and authority routing |
| `.github/workflows/` | Credential-free dedicated-root checks |
| `README.md` | Project overview, operational status, and local entry points |
| `GLOSSARY.md` | Canonical platform vocabulary |
| `docs/` | Platform design authority, runbooks, and evidence indexes |
| `docs/runbooks/` | Subordinate operator procedures requiring their own explicit approvals |
| `prompts/` | Bounded task entry points that link to authoritative documents |
| `integrations/` | Inactive application-adoption inputs with no consuming-app authority |
| `contracts/` | Version 1 schemas, deterministic reference compiler, reviewed contract vectors, and bounded runtime JSON loading |
| `fixtures/` | In-process reference edge, synthetic identity, three independent Fixture Applications with app-owned test state, and reviewed registration generations |
| `edge/` | AP-M6 Shared Edge interface, immutable-generation source adapter, catalogue/routing, Google OIDC/sessions, admission, ES256 assertion/JWKS adapters, independent application verification, strict Cloud Run attachment resolution, bounded HTTP/SSE/WebSocket proxying, read-only status, minimized completion events, and accepted runtime behavior only |
| `tests/` | Behavior-named governance, contract, Fixture, and runtime checks plus explicitly synthetic fixed test material |
| `pyproject.toml` and `uv.lock` | Direct runtime dependencies and complete frozen transitive resolution |
| `Makefile` | Portable project-local developer and verification interface |
| `.gitignore` | Platform-local generated, secret, state, and build exclusions |

## Reserved capability locations

These locations may be created only by their approved slice:

| Path | Intended owner |
| --- | --- |
| `registrations/` | Future reviewed Live Registration Sets; Fixture registrations remain under `fixtures/` |
| `infrastructure/terraform/bootstrap/` | Future backend-bootstrap root only |
| `infrastructure/terraform/platform/` | Future Shared Edge Platform State root only |
| `infrastructure/terraform/fixtures/<application-id>/` | Future independently owned Fixture Application State root |
| `infrastructure/terraform/modules/` | Future reusable modules with no environment or state ownership of their own |
| `catalog/` | Root application catalogue implementation |
| `artifacts/` | Secret-free reviewed evidence indexes and digests, never raw Live evidence bundles |

The reservation is not authorization to scaffold empty modules or imply later capabilities. AP-M6
may extend only `edge/` and implementation-owned registration test inputs through its ordered work
packages. AP-M7 may create only the planned Terraform and workflow paths after repository
reconciliation merges and the owner declares the canonical cutover. Live evidence bundles remain
in the private provider evidence store rather than the repository.

## Repository-transition boundary

The source repository may retain only temporary integration files outside this dedicated root:

- short authority-boundary notes in its `AGENTS.md`, `README.md`, documentation index, and
  repository-layout document; and
- its path-scoped GitHub Actions wrapper.

Those files are not dedicated-repository authority. Until the reconciliation pull request merges
and the owner explicitly declares the canonical cutover, the source-repository copy remains
authoritative and platform changes stop in both locations. Removing or replacing that copy and its
CI wrapper is a later, separately approved source-repository change.

## Dedicated-repository rules

- Keep platform code, contracts, documentation, tests, prompts, and evidence at this repository
  root.
- Use project-relative paths and run `make check` from the dedicated repository root.
- Keep Terraform state, credentials, saved plans, caches, and authenticated artifacts outside Git.
- Follow the reviewed [repository extraction runbook](runbooks/repository_extraction.md) before any
  remaining reconciliation, authority-cutover, or source-repository cleanup action.
- A path move is complete only when every contract consumer, test, command, document, and workflow
  resolves to the new location.
