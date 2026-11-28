# App Platform repository layout

Version 2.22 | Status: canonical dedicated repository; ADR-015 implemented and Candidate-qualified
by AP-M9-W10; AP-M9-W11 Accepted Source staging platform and fixture qualification completed at
`b43333756b509d0f35cb82938a13f6abc459f7c4`; AP-M9-W12 target-stage validation, ADR-017 Version 3
contracts, atomic multi-target projection, the fourth fixture application, and its separate
qualification module are implemented, while Live fixture qualification and later slices remain
planned

Paths are relative to the dedicated repository root. A path records ownership; it does not grant
permission to create a resource or perform an external action.

## Implemented layout

| Path | Owner |
| --- | --- |
| `AGENTS.md` | engineering workflow, authority routing, and safety rules |
| `.github/workflows/` | credential-free repository checks |
| `README.md`, `GLOSSARY.md` | product entry point and canonical vocabulary |
| `docs/` | current requirements, decisions, design, plan compatibility routing, evaluation, and runbooks |
| `docs/adr/` | canonical architecture-decision index and individual decision records |
| `docs/plans/` | canonical implementation-plan index, AP-M3 through AP-M8 origin plan, and milestone directories containing `000-` entry points plus substantial work-package plans |
| `docs/history/` | superseded delivery records with no action authority |
| `prompts/` | bounded next-task entry points subordinate to current documents |
| `contracts/` | readable Version 1 predecessors, active Version 2 schemas and compilers, and implemented Version 3 application-handoff contracts |
| `contracts/lifecycle/` | AP-M9 profiles plus readable Version 1, Version 2, and Version 3 handoff schemas, vectors, digests, and cross-document validation |
| [`fixtures/`](../fixtures/README.md) | current networked synthetic applications plus the retained deterministic Version 1 reference harness |
| [`edge/`](../edge/README.md) | network Shared Edge and production-adapter implementation |
| `integrations/` | inactive application-adoption drafts |
| `infrastructure/tools/` | credential-free dependency setup and static validation |
| `infrastructure/config/` | AP-M7 non-secret configuration contracts and deterministic validation |
| `infrastructure/config/profiles/` | small reviewed staging and disabled-production environment profiles |
| [`infrastructure/operator/`](../infrastructure/operator/README.md) | linear Python preflight, preparation, local-only active-operation cancellation, exact-plan deployment, application integration, member lifecycle, cleanup-safe member qualification, atomic progress, status, resume, external-effect adapters, and thin CLI |
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
verified-session qualification and exact retained-resource destruction adapters. W8 repository
implementation did not exercise those adapters. W9 Candidate Source operation subsequently
exercised provider requests, fixture image builds, generation activation, qualification rollback
and restoration, and fixture destruction and recovery for the named staging revision.

AP-M9-W9 adds the executable Fixture Application owner lifecycle over the existing image and three
independent Terraform roots. It introduces shallow `fixture-project-bootstrap`,
`platform-connect-project`, `application-handoff-check`, `fixture-handoff`, `fixture-status`, and
`fixture-destroy` targets over the deep operator module. The read-only handoff check combines
platform-plan, project-service, Shared VPC, bundle-input, and access-mode readback before bundle
publication. The fixture project owns one private state bucket with independent root
prefixes and attaches to the platform Shared VPC. Platform outputs, fixture handoff, and platform
registration remain separate so the fixtures exercise the same cross-owner boundary as an external
application. The package also includes private pre-registration bundle inspection and exact reuse,
provider posture readback, registration generations that preserve other applications, suite-wide
or selected status, automatic prepared-specification reuse, and a non-publishing
`platform-preflight` readiness target with deterministic fake coverage, plus live qualification and
safe platform-destruction adapter completion. Candidate staging operation is implementation
feedback and revision-scoped Live evidence, not Accepted Source AP-M9 qualification.

AP-M9-W12 Slices 1 through 5 keep the existing provider target-reader seam, add explicit V2/V3
handoff selection to readiness and outputs, consume a complete Version 3 family in the deep
application-integration lifecycle, read every target, and atomically project a valid set into the
existing Version 2 compiler. Slice 4 adds the fourth fixture runtime profile, one two-service
Application State root, one complete Version 3 fixture handoff, per-target status, and exact
two-target destruction readback. Slice 5 adds the closed `fixture-qualify` lifecycle, exact private
readback, browser/route/provider/failure seams, and separate fixture result/status storage. Ordered
failures retain only attachment IDs and stable codes. These slices add no generic real-application
deploy/destroy command or Live evidence.

AP-M9-W12 implements a fourth `fixture-multi-attachment` profile and one independent
`infrastructure/terraform/fixtures/fixture-multi-attachment/` root. That root owns both the
frontend and dummy API Cloud Run services and uses the existing fixture project's private state
bucket with the distinct `fixtures/fixture-multi-attachment` prefix. The implemented
`fixture-qualify` target sits over a fixture-scoped qualification module and writes its result and
status separately from `platform-qualify`. The existing three fixture roots, handoffs, and
qualification record remain unchanged. The slice did not invoke a provider or produce Live
qualification evidence; those Candidate and Accepted operations remain separate gates.

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
| root `Makefile` | shallow `platform-*` operator targets plus the implemented W12 `fixture-qualify` target over its fixture-scoped qualification module |
| `infrastructure/operator/` | implemented W12 fixture-scoped qualification module with private evidence and status distinct from platform qualification |

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
- Keep the required Version 3 root attachment plus any complete optional additional target and
  binding sets in the lifecycle-contract and operator modules; project them into the existing
  Version 2 registration family without creating application-specific schemas or a second state
  owner.
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
