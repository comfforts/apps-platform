# App Platform engineering instructions

These instructions govern work in the dedicated App Platform repository. The security,
source-control, secret-handling, and destructive-action guardrails in this file apply to every
change in the repository.

## Before modifying the platform

1. Read [docs/README.md](docs/README.md) completely and follow its task-specific reading order.
2. Read [product requirements](docs/01_product_requirements.md) and
   [accepted architecture decisions](docs/02_architecture_decision_records.md). Map every planned
   behavior to their identifiers and constraints.
3. Read [GLOSSARY.md](GLOSSARY.md) for canonical platform terms and
   [docs/repository_layout.md](docs/repository_layout.md) before placing files.
4. Before changing platform interfaces or planning their consumers, read the
   [system design](docs/03_system_design.md), [threat model](docs/06_threat_model.md), and
   [contract index](contracts/README.md). Use the plan and evaluation authority for the active
   milestone; when either is absent, propose it and wait for approval before implementation.
5. Inspect `git status` and preserve unrelated changes.
6. State the platform slice and every `AP-PR-*`, `AP-QR-*`, `ADR-*`, plan, and evaluation identifier
   that owns the change. Treat an absent downstream authority as unresolved rather than inferred.
7. Stop for direction when an authority is absent or the requested work would change an active
   application, cloud resource, DNS record, credential, or Terraform state outside the approved
   slice.

## Authority boundary

- App Platform documentation is authoritative only for this project.
- Parent Finance Assistant specifications do not define platform behavior.
- Application integration drafts are inactive inputs until the consuming application adopts them
  through its own requirements and release process.
- Version 1 schemas and the reference compiler provide Contract evidence; the deterministic
  in-process harness provides Fixture evidence. Provider runtime, Terraform, deployment, Live, and
  Adoption claims require their later authorities and evidence gates.
- AP-M5 selects infrastructure and Live-qualification planning boundaries only. It authorizes no
  provider runtime, Terraform configuration, workflow mutation, credential, cloud action, DNS
  change, deployment, or Live claim.
- AP-M6 authorizes only repository implementation of the networked Shared Edge and production
  adapter logic tested through deterministic fakes and process-local loopback. It authorizes no
  Terraform, external network, credential lookup, provider call, cloud or repository mutation,
  deployment, Live claim, or Application Adoption.
- AP-M7 authorizes only reviewed Terraform configuration, non-executable workflow templates, and
  credential-free static verification under its named work packages and AP-EVAL-M7. It authorizes
  no backend initialization, authenticated plan or apply, credential or federation configuration,
  provider call, repository-setting change, cloud or DNS mutation, deployment, Live claim, or
  Application Adoption.
- AP-M8-W1/W2 are historical merged work. AP-M8-W3 through AP-M8-W12 are superseded and must not
  be resumed. The historical manifest implementation remains only until AP-M9-W2 removes it.
- AP-M9-W1 authorizes governance and documentation rebaselining only. Each later AP-M9 package
  requires its predecessor to be merged and its own approved authority. Until the relevant package
  is implemented and invoked, AP-M9 authorizes no repository-setting change, federation or IAM
  binding, credential use, backend operation, authenticated plan or apply, provider call, OAuth
  client, image publication, DNS or traffic change, deployment, destructive action, Live claim, or
  Application Adoption.
- Keep platform implementation, contracts, tests, prompts, and evidence inside this dedicated
  canonical repository. Extraction does not make Finance Assistant authority applicable here. The
  completed source-repository cleanup does not transfer Finance Assistant requirements, behavior,
  infrastructure, state, or application-adoption authority into this project.

## Branch and review workflow

- Start each approved slice from an updated, clean `main` on a dedicated feature branch.
- Keep one bounded slice per pull request. Merge it before starting the next documented slice.
- Use small coherent commits that remain independently reviewable. When the owner requests
  commit-by-commit review, leave each change uncommitted until approval.
- Keep later-slice implementation out of the current branch even when its directories or interfaces
  are already reserved.
- Run `make check` before handoff and report the actual result. A merged pull request records
  repository progress; it does not by itself qualify runtime or cloud behavior.
- Follow the completed/next sequence in [docs/README.md](docs/README.md); do not infer a new sequence
  from branch names or discussion history.
- Treat the AP-M9 `platform-*` interface as planned until its named work package implements it.
  Never substitute the historical AP-M8 manifest procedure for a missing AP-M9 capability.

## Verification

- Run `make check` from the dedicated repository root.
- Keep `check` credential-free, deterministic, and non-mutating. Cloud plans, applies, DNS changes,
  identity changes, and live qualification require separate explicit operator targets.
- Store no credentials, Terraform state, saved plans, authenticated browser state, or unredacted
  external payloads in Git.
- Update each public contract and all of its consumers together. Record unimplemented behavior as
  planned rather than operational.
