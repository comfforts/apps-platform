# App Platform repository layout

Status: authoritative canonical dedicated-root layout; all five repository-extraction checkpoints
complete; no provider operation or infrastructure implemented

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
packages. AP-M7 may create only the planned Terraform and workflow paths after its detailed plan
and evaluation authority are approved. Live evidence bundles remain in the private provider
evidence store rather than the repository.

## Completed repository-transition boundary

The history-preserving split and dedicated reconciliation retained project history and made paths
root-relative. After the reconciliation pull request merged, the owner explicitly declared
`comfforts/apps-platform` canonical. A separate, recoverable source-repository pull request then
removed the historical `apps-platform/` tree and its path-scoped GitHub Actions wrapper.

The containing repository retains only its own short authority-boundary notes. They are not App
Platform authority. Platform changes occur only in this canonical repository, and the completed
cleanup did not modify Finance Assistant requirements, implementation, infrastructure, state, DNS,
identity, deployment, or access.

## Dedicated-repository rules

- Keep platform code, contracts, documentation, tests, prompts, and evidence at this repository
  root.
- Use project-relative paths and run `make check` from the dedicated repository root.
- Keep Terraform state, credentials, saved plans, caches, and authenticated artifacts outside Git.
- Treat the reviewed [repository extraction runbook](runbooks/repository_extraction.md) and
  [handoff](repository_extraction_handoff.md) as the procedure and evidence for the completed
  transition; any new repository move requires new authority.
- A path move is complete only when every contract consumer, test, command, document, and workflow
  resolves to the new location.
