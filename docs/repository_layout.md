# App Platform repository layout

Version 1.5 | Status: canonical dedicated repository; AP-M9-W1 governance rebaseline in review;
no backend, provider, DNS, deployment, or Live operation performed

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
| `fixtures/` | deterministic in-process Fixture platform and synthetic applications |
| `edge/` | network Shared Edge and production-adapter implementation |
| `integrations/` | inactive application-adoption drafts |
| `infrastructure/tools/` | credential-free dependency setup and static validation |
| `infrastructure/config/` | AP-M7 non-secret configuration contracts; also contains the retired AP-M8 operator-manifest implementation pending AP-M9-W2 removal |
| `infrastructure/terraform/bootstrap/` | AP-M7 static state-bucket owner root |
| `infrastructure/terraform/platform/` | AP-M7 static Platform State root |
| `infrastructure/terraform/fixtures/*/` | independent synthetic Application State roots |
| `infrastructure/terraform/modules/` | internal AP-M7 Terraform modules |
| `infrastructure/workflows/` | inert AP-M7 workflow-design artifacts, not executable workflows |
| `tests/` | governance, contract, Fixture, runtime, and static infrastructure checks |
| `Makefile` | repository-local setup and deterministic verification interface |
| `pyproject.toml`, `uv.lock` | direct dependencies and frozen resolution |
| `.gitignore` | generated, secret, state, plan, cache, and build exclusions |

The AP-M8-W2 operator-manifest files remain present only because AP-M9-W1 is a governance slice.
AP-M9-W2 removes them and their active consumers. They are not a current operator input.

## Planned AP-M9 capability locations

These locations describe intended module seams. Their absence is expected until the named AP-M9
package implements them.

| Path | Intended owner |
| --- | --- |
| `infrastructure/config/profiles/` | small reviewed staging and production environment profiles |
| `infrastructure/operator/` | deep interactive Python lifecycle module and bounded adapters |
| `infrastructure/backend/` | deterministic backend rendering and lineage-preserving helpers |
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
