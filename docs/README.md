# App Platform documentation

Version 1.22 | Status: AP-M9-W8 qualification and safe-destruction lifecycle implemented; AP-M8-W1/W2 retained as
historical evidence; no platform environment is deployed or qualified

This directory is the design authority for Comfforts App Platform. Contract (`C`) and Fixture
(`F`) evidence, the locally tested network runtime, and statically verified Terraform exist. Live
(`L`) and Application Adoption (`A`) evidence do not. Repository implementation does not imply a
credential, backend, provider, DNS, deployment, or application-adoption action.

## Reading order

Read these documents completely, in order, before modifying the platform:

1. [Project overview](../README.md) — current product boundary and status.
2. [Domain glossary](../GLOSSARY.md) — canonical terms.
3. [Product requirements](01_product_requirements.md) — AP-PR-001 through AP-PR-012 and AP-QR-001
   through AP-QR-009.
4. [Architecture decision records](02_architecture_decision_records.md) — ADR-001 through ADR-013.
5. [System design](03_system_design.md) — interfaces, ownership, lifecycle, and provider design.
6. [Threat model](06_threat_model.md) — trust zones, threats, controls, and evidence classes.
7. [Implementation plan](04_implementation_plan.md) — the active AP-M9-W1 through AP-M9-W10
   sequence and historical milestone records.
8. [Evaluation strategy](05_evaluation_strategy.md) — AP-EVAL-M9 gates and claim boundaries.
9. [Contract index](../contracts/README.md) — public machine interfaces.
10. [Repository layout](repository_layout.md) — capability placement and transition rules.
11. [Runbook index](runbooks/README.md) — subordinate operator procedures.
12. [AP-M9 environment lifecycle](runbooks/environment_lifecycle.md) — current human-operated
    lifecycle design, implemented local commands, and unavailable external actions.
13. [Repository extraction runbook](runbooks/repository_extraction.md) and
    [handoff](repository_extraction_handoff.md) — completed canonical repository transition
    procedure and evidence.
14. [Prompt index](../prompts/README.md) — bounded next-task entry points.

The material under [`docs/history/`](history/README.md) preserves superseded delivery evidence. It
is not part of the active instruction path and cannot authorize an operation.

## Milestone status

| Milestone | Status | Evidence boundary |
| --- | --- | --- |
| AP-M3 | complete | Version 1 contracts and deterministic compilation |
| AP-M4 | complete | in-process Fixture qualification |
| AP-M5 | complete | infrastructure and Live-qualification planning |
| AP-M6 | complete | network runtime tested with fakes and loopback |
| AP-M7 | complete | static Terraform and inert workflow templates |
| AP-M8 | historical | W1/W2 merged; no real manifest accepted; W3-W12 never started |
| AP-M9 | W8 implemented | operator-driven environment and application lifecycle |

AP-M9 replaces the withdrawn standalone Live-qualification milestone and supersedes the unexecuted
AP-M8-W3 through AP-M8-W12 plan. AP-M8-W1/W2 remain factual records of merged work. AP-M9 does not
retroactively turn them into deployment evidence.

## Active AP-M9 sequence

Each work package is one bounded branch and pull request. Start it from updated, clean `main`, use
small reviewable commits, merge it, and only then begin the next package.

1. **AP-M9-W1 — governance rebaseline (merged):** define the product lifecycle, authority,
   architecture, threat controls, plan, evaluation, documentation routing, and historical
   boundary.
2. **AP-M9-W2 — retired manifest cleanup (implemented):** remove the operator-manifest schema,
   validator, synthetic example, command, tests, and obsolete active guidance without changing
   AP-M7 assets.
3. **AP-M9-W3 — lifecycle contracts and profiles (implemented):** small staging/production
   profiles, deployment specifications, execution journals, status documents, integration bundles,
   attachment bundles, canonical digests, and cross-document validation.
4. **AP-M9-W4 — interactive lifecycle core (implemented):** credential-free preparation and
   status, exact digest approval, append-only journals, redaction, truthful failure state, and
   resumable deterministic fake execution behind injected adapters.
5. **AP-M9-W5 — deployable Terraform (implemented):** phased bootstrap, foundation, and Shared
   Edge configuration; exact backend declarations; canonical plan
   policy; closed outputs; mocked plans; and deterministic command fakes.
6. **AP-M9-W6 — interactive platform deployment (implemented):** staged exact-plan execution,
   reviewed action confirmation, human OAuth and external-DNS checkpoints, bounded DNS/TLS
   polling, readback, stop-on-discrepancy, transcript redaction, and interruption-safe resume.
7. **AP-M9-W7 — application lifecycle (implemented):** least-data bundle generation, exact target
   posture validation, immutable whole-generation registration and activation, reversible
   detachment/reactivation, terminal retirement, and distinct reserved-route responses.
8. **AP-M9-W8 — qualification and safe destruction (implemented):** revision-bound qualification,
   redacted evidence, synthetic network fixtures, failure injection, reviewed generation rollback,
   resumable environment destruction that never targets Application State, and guarded real
   staging deployment adapters ready for the separately approved first operation.
9. **AP-M9-W9 — staging operation:** deploy and qualify `apps-staging.comfforts.com` with synthetic
   applications under new explicit owner approvals.
10. **AP-M9-W10 — production readiness:** prove the production handoff and stop with
    `OWNERSHIP_TRANSFER_REQUIRED` while Finance Assistant or `apps.comfforts.com` remains
    Finance-owned.

AP-M9-W8 began only after AP-M9-W7 merged. No staging operation is authorized before AP-M9-W8
merges. AP-M9-W9 owns the first real staging operation and requires its own values and approvals.
Production migration and Application Adoption remain separate owner-controlled work after
AP-M9-W10.

## Authority and claim discipline

Conflicts are resolved in this order: requirements, accepted ADRs, system design, public contracts,
implementation plan, evaluation strategy and threat evidence, runbooks and delivery evidence, then
prompts. A later document cannot silently broaden an earlier authority.

Use these status meanings:

- **Planned:** authority or behavior is described but not implemented.
- **Implemented:** repository behavior exists and passes deterministic checks; no live action is
  implied.
- **Qualified:** the named evaluation gate has revision-scoped evidence.
- **Integration draft:** a non-authoritative input awaiting adoption by its consuming application.
- **Historical evidence:** an immutable record that provides no current action authority.

The App Platform owns only shared platform boundaries. Application data, stores, providers,
secrets, principals, entitlements, runtime deployment, and Application State remain application
owned. Finance Assistant and `apps.comfforts.com` remain unchanged until their own adoption and
ownership-transfer authorities are approved.

## Inactive integration inputs

[`integrations/ai_finance_assistant/README.md`](../integrations/ai_finance_assistant/README.md) is
discoverable compatibility material, not part of the platform authority chain. Read it only for an
explicitly scoped compatibility or adoption task. It cannot define generic platform behavior or
activate an application adoption.

## Evidence and secret boundary

Keep credentials, OAuth client secrets, Terraform state, saved plans, authenticated browser state,
provider payloads, and unredacted Live evidence outside Git. The implemented Platform Integration
Bundle and Application Attachment Bundle contracts admit only non-secret handoff values. They do
not authorize bundle generation or application adoption.

Run `make check` from the repository root for the credential-free, deterministic, non-mutating
repository gate. Authenticated plans, applies, DNS changes, identity changes, qualification, and
destruction must use later explicit AP-M9 operator targets and approvals.
