# App Platform repository layout

Status: authoritative canonical dedicated-root layout; all five repository-extraction checkpoints
complete; AP-M7 static Terraform, configuration, and inert workflows implemented and passing the
deterministic repository gate; AP-M8 authority reserves backend preparation and deployment-support
locations only; no backend or provider operation, cloud resource, IAM mutation, build, publication,
deployment, DNS change, or Live qualification performed

The project is organized at the dedicated repository root produced by the history-preserving
subtree extraction. Paths remain project-relative so repository identity does not alter platform
contracts, verification, or ownership boundaries.

## Current layout

| Path | Owner |
| --- | --- |
| `AGENTS.md` | Platform engineering workflow and authority routing |
| `.github/workflows/` | Credential-free dedicated-root checks |
| `.terraform-version` | Exact AP-M7 Terraform CLI version constraint |
| `README.md` | Project overview, operational status, and local entry points |
| `GLOSSARY.md` | Canonical platform vocabulary |
| `docs/` | Platform design authority, runbooks, and evidence indexes |
| `docs/runbooks/` | Subordinate operator procedures requiring their own explicit approvals |
| `docs/runbooks/qualification_deployment.md` | Proposal-only AP-M8 protected-setting, identity, backend, exact deployment sequence, DNS/TLS, and evidence checkpoints; no action authority |
| `prompts/` | Bounded task entry points that link to authoritative documents |
| `integrations/` | Inactive application-adoption inputs with no consuming-app authority |
| `contracts/` | Version 1 schemas, deterministic reference compiler, reviewed contract vectors, and bounded runtime JSON loading |
| `fixtures/` | In-process reference edge, synthetic identity, three independent Fixture Applications with app-owned test state, and reviewed registration generations |
| `edge/` | AP-M6 Shared Edge interface, immutable-generation source adapter, catalogue/routing, Google OIDC/sessions, admission, ES256 assertion/JWKS adapters, independent application verification, strict Cloud Run attachment resolution, bounded HTTP/SSE/WebSocket proxying, read-only status, minimized completion events, and accepted runtime behavior only |
| `tests/` | Behavior-named governance, contract, Fixture, runtime, Terraform, workflow, and qualification checks plus explicitly synthetic fixed test material |
| `pyproject.toml` and `uv.lock` | Direct runtime dependencies and complete frozen transitive resolution |
| `Makefile` | Portable project-local developer and verification interface |
| `.gitignore` | Platform-local generated, secret, state, and build exclusions |
| `infrastructure/tools/` | AP-M7 credential-free local dependency setup and disposable-copy offline validation |
| `infrastructure/config/` | AP-M7-W3 closed Version 1 schemas, synthetic examples, bounded loader, and semantic policy |
| `infrastructure/terraform/{bootstrap,platform,fixtures/*}/versions.tf` | Exact root-local Terraform and provider constraints |
| `infrastructure/terraform/{bootstrap,platform,fixtures/*}/.terraform.lock.hcl` | Identical committed provider selections and signed package checksums |
| `infrastructure/terraform/bootstrap/` | AP-M7-W4 deep bootstrap root, typed configuration interface, and plan-only mocked-provider tests |
| `infrastructure/terraform/modules/state-bucket/` | AP-M7-W4 internal private, versioned, recovery-bounded state-bucket implementation |
| `infrastructure/terraform/fixtures/{fixture-public,fixture-authenticated,fixture-restricted}/` | AP-M7-W5 independent Application State roots, typed interfaces and outputs, and plan-only mocked-provider tests |
| `infrastructure/terraform/modules/fixture-application/` | AP-M7-W5 internal Cloud Run runtime, identity, ingress, scaling, non-secret identity-data, and edge-caller intent implementation |
| `infrastructure/terraform/platform/` | AP-M7-W6 through W8 deep Platform State root, typed configuration and Fixture-reference interfaces, and plan-only mocked-provider tests |
| `infrastructure/terraform/modules/platform-foundation/` | AP-M7-W6 internal configuration-storage, session, edge-identity, signing-key, and access-intent implementation |
| `infrastructure/terraform/modules/shared-edge/` | AP-M7-W7 internal immutable Cloud Run candidate, direct-origin restriction, serverless backend, certificate, HTTPS forwarding, and HTTP redirect implementation |
| `infrastructure/terraform/modules/platform-controls/` | AP-M7-W8 internal regional logging, default-bucket exclusion, private evidence, owner-read, budget-notification, and dry-run artifact-retention intent implementation |
| `infrastructure/workflows/` | AP-M7-W9 parseable but non-executable advisory-plan, apply, rollback, force-unlock, and destroy authority templates |

## Proposed AP-M8 capability locations

These paths are authority reservations, not implemented capabilities or permission to create them:

| Path | Intended owner |
| --- | --- |
| `infrastructure/backend/bootstrap-backend.tf.tmpl` | AP-M8-W5 reviewed empty GCS backend declaration for a private temporary bootstrap-root copy only |
| `infrastructure/backend/render_bootstrap_backend.py` | AP-M8-W5 credential-free deterministic renderer that refuses overwrite and emits no value, state, credential, or provider data |
| `edge/production.py` | AP-M8-W6 production composition of only the already accepted Shared Edge adapters |
| `fixtures/runtime.py` | AP-M8-W6 networked synthetic Fixture Application runtime with independent production assertion verification |
| `infrastructure/images/shared-edge/Dockerfile` | AP-M8-W6 pinned non-root Shared Edge image definition; no credential or mutable deployment tag |
| `infrastructure/images/fixture-application/Dockerfile` | AP-M8-W6 pinned non-root reusable synthetic Fixture runtime image definition |
| `infrastructure/config/schemas/platform-configuration.v2.schema.json` | AP-M8-W6 explicit `foundation`/`candidate` Platform State deployment contract preserving one root and lineage |
| `infrastructure/deployment/` | AP-M8-W6 credential-free operation-record and exact workflow-configuration renderers; no operator value, credential, state, plan, or provider payload |
| `registrations/qualification/` | AP-M8-W6 provider-backed initial synthetic Registration Set using reviewed `gcp-cloud-run-v1` references; distinct from AP-M4 Fixture evidence |
| `.github/workflows/ap-m8-<operation>-<target>.yml` | AP-M8-W6 fixed manual operator workflows, one reviewed operation/target/identity/environment per file |

AP-M8-W5 must implement and test the backend files in a repository-only protected-main change
before requesting backend-mutation approval. AP-M8-W6 must separately implement and test the
deployment-support paths before authenticated preflight. Reserved paths never contain a credential,
state, saved plan, provider response, secret, or deployable operator default. Their presence will
not authorize bootstrap, migration, initialization, build, publication, provider access, DNS,
traffic, force-copy, force-unlock, state push, import, apply, or recovery.

## Approved AP-M7 capability locations

These locations may be created only by their approved slice:

| Path | Intended owner |
| --- | --- |
| `registrations/` | Future reviewed Live Registration Sets; Fixture registrations remain under `fixtures/` |
| `infrastructure/config/` | AP-M7-W3 versioned non-secret configuration contracts; implemented with no operator values or Terraform resources |
| `infrastructure/terraform/bootstrap/` | AP-M7-W4 static backend resource owner; implemented without backend initialization or IAM principals |
| `infrastructure/terraform/platform/` | Shared Edge Platform State root; W6 identity/generation foundation, W7 Shared Edge/hostname forwarding, and W8 platform controls implemented |
| `infrastructure/terraform/fixtures/<application-id>/` | Independently owned Fixture Application State roots; W5 resource configuration implemented without a backend or provider operation |
| `infrastructure/terraform/modules/` | Internal state-bucket, Fixture Application, Platform foundation, Shared Edge, and platform-controls modules implemented through W8; later modules remain work-package-owned and own no environment or state |
| `infrastructure/workflows/` | AP-M7-W9 inert operator-workflow templates implemented outside `.github/workflows/`; never executable during AP-M7 |
| `catalog/` | Root application catalogue implementation |
| `artifacts/` | Secret-free reviewed evidence indexes and digests, never raw Live evidence bundles |

The implemented AP-M7 capability locations are not authorization to scaffold empty modules or
infer later capabilities. The W2 foundation, W3 contracts, W4 bootstrap configuration, W5 Fixture
Application roots, W6
Platform foundation, W7 Shared Edge forwarding, W8 platform controls, W9 inert workflows, and W10
qualification gate do not authorize later behavior. AP-M7-W11 records only repository
implementation and a post-merge planning handoff. Executable cloud workflows, credentials, state,
saved plans, provider calls, deployments, and Live evidence remain prohibited. Live evidence
bundles remain in the private provider evidence store rather than the repository.

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
