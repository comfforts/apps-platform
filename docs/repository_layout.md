# App Platform repository layout

Version 1.9 | Status: canonical dedicated repository; AP-M9-W5 Terraform lifecycle
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
| `infrastructure/operator/` | deep Python preparation, approval, journal, status, resume, local adapters, and thin credential-free CLI |
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
command, approval, journal, bundle instance, provider resource, state, deployment, or evidence.

AP-M9-W4 added credential-free `platform-prepare` and `platform-status`, exact local approval
binding, private generated operator state under the ignored `.platform-operator/` path, and
resumable journal orchestration exercised through deterministic fakes. It added no executable
deploy target, credential, provider request, backend operation, Terraform plan or apply, DNS
action, platform resource, bundle instance, deployment, or Live evidence.

AP-M9-W5 added exact staging backend declarations, keyless operation-authority profiles, canonical
plan policy, Version 2 phased Platform State configuration, closed phase outputs, mocked Terraform
plans, and a deterministic injected command fake. It added no production command adapter, deploy
target, identity, credential, backend operation, saved plan, state, provider request, DNS action,
resource, deployment, or Live evidence.

## AP-M9 capability locations

The implemented profile, lifecycle-contract, operator-core, backend, and Terraform locations are
listed above. The locations below describe later module seams; their absence is expected until the
named AP-M9 package implements them.

| Path | Intended owner |
| --- | --- |
| `infrastructure/images/` | reproducible Shared Edge and synthetic Fixture images |
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
- Keep Terraform state, saved plans, credentials, secret values, provider responses, execution
  journals containing sensitive data, and private Live evidence outside Git.
- Keep Platform State and every Application State in independent lineages. Never use
  `terraform_remote_state` as an integration contract.
- Exchange only versioned, non-secret Platform Integration Bundles and Application Attachment
  Bundles across the platform/application boundary.
- Keep inactive application-adoption inputs under `integrations/ai_finance_assistant/` outside the
  authority chain until Finance adopts them through its own release authority.
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
