# App Platform repository layout

Version 2.3 | Status: canonical dedicated repository; AP-M9-W9 fixture lifecycle mechanics
implemented; no backend, provider, DNS, deployment, or Live operation performed

Paths are relative to the dedicated repository root. A path records ownership; it does not grant
permission to create a resource or perform an external action.

## Implemented layout

| Path | Owner |
| --- | --- |
| `AGENTS.md` | engineering workflow, authority routing, and safety rules |
| `.github/workflows/` | credential-free repository checks |
| `README.md`, `GLOSSARY.md` | product entry point and canonical vocabulary |
| `docs/` | current requirements, decisions, design, plans, evaluation, and runbooks |
| `docs/history/` | superseded delivery records with no action authority |
| `prompts/` | bounded next-task entry points subordinate to current documents |
| `contracts/` | Version 1 public schemas, compiler, vectors, and bounded loading |
| `contracts/lifecycle/` | AP-M9 profiles and lifecycle-document schemas, vectors, digests, and cross-document validation |
| `fixtures/` | deterministic in-process Fixture platform and synthetic applications |
| `edge/` | network Shared Edge and production-adapter implementation |
| `integrations/` | inactive application-adoption drafts |
| `infrastructure/tools/` | credential-free dependency setup and static validation |
| `infrastructure/config/` | AP-M7 non-secret configuration contracts and deterministic validation |
| `infrastructure/config/profiles/` | small reviewed staging and disabled-production environment profiles |
| `infrastructure/operator/` | linear Python preflight, preparation, local-only active-operation cancellation, exact-plan deployment, application integration, atomic progress, status, resume, external-effect adapters, and thin CLI |
| `infrastructure/backend/` | AP-M9-W5 backend rendering, lineage, operation authority, plan policy, and fake command integration |
| `infrastructure/terraform/bootstrap/` | state-bucket owner root with closed bootstrap phase output |
| `infrastructure/terraform/platform/` | phased foundation and Shared Edge configuration on one Platform State lineage |
| `infrastructure/terraform/fixtures/*/` | independent synthetic Application State roots |
| `infrastructure/terraform/modules/` | internal AP-M7 Terraform modules |
| `infrastructure/workflows/` | inert AP-M7 workflow-design artifacts, not executable workflows |
| `tests/` | governance, contract, Fixture, runtime, and static infrastructure checks |
| `Makefile` | repository-local setup and deterministic verification interface |
| `pyproject.toml`, `uv.lock` | direct dependencies and frozen resolution |
| `.gitignore` | generated, secret, state, plan, cache, and build exclusions |

AP-M9-W2 removed the retired AP-M8 operator-manifest files and their active consumers. The factual
delivery record remains under `docs/history/`, and the implementation remains recoverable from Git
history. It is not a current operator input.

AP-M9-W3 added only deterministic, credential-free repository interfaces. It created no operator
command, approval, progress, bundle instance, provider resource, state, deployment, or evidence.

AP-M9-W4 added credential-free `platform-prepare` and `platform-status`, exact local approval
binding, private generated operator state under the ignored `.platform-operator/` path, and
resumable progress exercised through deterministic fakes. It added no executable
deploy target, credential, provider request, backend operation, Terraform plan or apply, DNS
action, platform resource, bundle instance, deployment, or Live evidence.

AP-M9-W5 added exact staging backend declarations, canonical
plan policy, Version 2 phased Platform State configuration, closed phase outputs, mocked Terraform
plans, and a deterministic injected command fake. It added no production command adapter, deploy
target, identity, credential, backend operation, saved plan, state, provider request, DNS action,
resource, deployment, or Live evidence.

AP-M9-W6 added immutable stage contexts, exact private-plan binding, plan/action confirmation,
policy and readback gates, same-process OAuth and Squarespace checkpoints, bounded DNS/TLS polling,
interruption-safe resume, a shell-free non-fake Terraform subprocess boundary, deterministic
command/transcript fakes, and the digest-bound `platform-deploy` target. The repository slice did
not invoke that adapter or create a credential, saved plan, state, backend, identity, image,
provider resource, OAuth client, secret version, DNS record, certificate, deployment, or Live
evidence. The default local construction remains unarmed until the later qualification and safe-
destruction package closes the external-action gate.

AP-M9-W7 added least-data integration-bundle generation, exact application attachment and target-
posture validation, immutable whole-generation compilation/publication/activation, reversible
detach and replacement/reactivation, terminal retirement, distinct detached/retired route
responses, interruption-safe activation resume, and shallow `platform-outputs`, `platform-register`,
`platform-detach`, and `platform-retire` targets. The repository slice created no bundle for a real
application, provider publication, active generation, application mutation, deployment, or Live
evidence and never read or destroyed Application State.

AP-M9-W8 added the qualification-evidence contract and canonical vector, exact current-revision
readback, the closed ten-check suite, process-local networked Fixture Application runtime, failure injection,
reviewed whole-generation rollback, safe-destruction compilation/orchestration, private create-only
destruction progress, least-data fixture handoff records, guarded Cloud SDK generation and target
adapters, the production Shared Edge composition, its non-root image entry point, and
`platform-qualify`/`platform-destroy`. W9 replaces the former live-entry implementation gates with
verified-session qualification and exact retained-resource destruction adapters; neither W8 nor W9
performed a provider request, image build, generation activation, rollback, qualification, or destruction.

AP-M9-W9 adds the executable Fixture Application owner lifecycle over the existing image and three
independent Terraform roots. It introduces shallow `fixture-project-bootstrap`,
`platform-connect-project`, `fixture-handoff`, `fixture-status`, and `fixture-destroy` targets over
the deep operator module. The fixture project owns one private state bucket with independent root
prefixes and attaches to the platform Shared VPC. Platform outputs, fixture handoff, and platform
registration remain separate so the fixtures exercise the same cross-owner boundary as an external
application. The package also includes private pre-registration bundle inspection and exact reuse,
provider posture readback, registration generations that preserve other applications, suite-wide
or selected status, automatic prepared-specification reuse, and a non-publishing
`platform-preflight` readiness target with deterministic fake coverage, plus live qualification and
safe platform-destruction adapter completion. Candidate staging operation is implementation
feedback, not accepted AP-M9 qualification.

## AP-M9 capability locations

The implemented profile, lifecycle-contract, operator/deployment/integration, backend, and
Terraform locations are listed above. The locations below describe later module seams; their
absence is expected until the named AP-M9 package implements them.

| Path | Intended owner |
| --- | --- |
| `infrastructure/images/` | reproducible non-root Shared Edge and synthetic Fixture images |
| `registrations/` | future reviewed provider-backed Registration Sets |
| `registrations/qualification/` | provider-backed synthetic qualification registrations |
| `infrastructure/evidence/` | redacted operation and qualification evidence tooling |
| `artifacts/` | optional secret-free reviewed indexes and digests only |
| root `Makefile` | shallow `platform-*` operator targets over the lifecycle module |

AP-M9 keeps one deep lifecycle module behind a small operator interface. Provider, Terraform, DNS,
OAuth, filesystem, and console code are adapters at real side-effect boundaries; orchestration and
policy stay testable without credentials or network access.

## Placement and ownership rules

- Keep platform code, contracts, documents, tests, prompts, and secret-free historical indexes in
  this repository.
- Keep Terraform state, saved plans, credentials, secret values, provider responses, private
  deployment progress, and private Live evidence outside Git.
- Keep Platform State and every Application State in independent lineages. Never use
  `terraform_remote_state` as an integration contract.
- Exchange only versioned, non-secret Platform Integration Bundles and Application Attachment
  Bundles across the platform/application boundary.
- Keep application-specific migration plans and adoption authority in the consuming application's
  repository.
- Update a public contract and all repository consumers in the same bounded slice.
- Do not create a reserved path merely because this document names it.

## Completed repository transition

The history-preserving extraction, dedicated-repository controls, reconciliation merge, canonical
authority declaration, and source-repository cleanup are complete. `comfforts/apps-platform` is the
sole App Platform authority. The containing Finance Assistant repository retains its own authority
and no Finance requirement, state, deployment, or credential transferred during extraction.

The reviewed [extraction runbook](runbooks/repository_extraction.md) and
[handoff](repository_extraction_handoff.md) are the evidence for that completed transition. A new
repository move would require new authority.
