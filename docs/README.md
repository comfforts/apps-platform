# App Platform documentation

Version 1.42 | Status: AP-M9-W9 candidate-qualified under Version 1; ADR-015 accepted,
ADR-016 proposed, and AP-M9-W10 Slices 1-6 implemented with no Live Version 2 operation

This directory is the design authority for Comfforts App Platform. Contract (`C`) and Fixture
(`F`) evidence, the locally tested network runtime, and statically verified Terraform exist. W9
also produced Candidate Source Live (`L`) evidence for the named staging revision and bindings;
Accepted Source Live evidence and Application Adoption (`A`) evidence do not yet exist. Repository
implementation alone does not imply a credential, backend, provider, DNS, deployment, or
application-adoption action.

## Reading order

Read these documents completely, in order, before modifying the platform:

1. [Project overview](../README.md) — current product boundary and status.
2. [Domain glossary](../GLOSSARY.md) — canonical terms.
3. [Product requirements](01_product_requirements.md) — AP-PR-001 through AP-PR-012 and AP-QR-001
   through AP-QR-009.
4. [Architecture decision index](adr/README.md) — routes ADR-001 through proposed ADR-016 to their
   current canonical records and separates decision status from realization evidence.
5. [System design](03_system_design.md) — interfaces, ownership, lifecycle, and provider design.
6. [Threat model](06_threat_model.md) — trust zones, threats, controls, and evidence classes.
7. [Implementation plan index](plans/README.md) — routes delivery identifiers to their current
   canonical milestone or work-package plan and preserves the AP-M3 through AP-M8 origin record.
8. [AP-M9 milestone plan](plans/ap_m9/000-m9_interactive_platform_lifecycle.md) — milestone outcome,
   boundaries, ordered work packages, acceptance criteria, and trace.
9. [AP-M9-W10 delivery plan](plans/ap_m9/w10_platform_member_directory.md) — current baseline,
   scope controls, operator interface, functional-slice map, effort signals, and completion gate.
10. [Evaluation strategy](05_evaluation_strategy.md) — AP-EVAL-M9 gates and claim boundaries.
11. [Contract index](../contracts/README.md) — public machine interfaces.
12. [Repository layout](repository_layout.md) — capability placement and transition rules.
13. [Runbook index](runbooks/README.md) — subordinate operator procedures.
14. [Environment lifecycle runbook](runbooks/environment_lifecycle.md) — operator procedure for
    staging and production preparation, deployment, inspection, qualification, recovery, and
    destruction.
15. [Repository extraction runbook](runbooks/repository_extraction.md) and
    [handoff](repository_extraction_handoff.md) — completed canonical repository transition
    procedure and evidence.
16. [Prompt index](../prompts/README.md) — bounded next-task entry points.

The material under [`docs/history/`](history/README.md) preserves superseded delivery evidence. It
is not part of the active instruction path and cannot authorize an operation.

## Backlog

The [App Platform backlog](07_back_log.md) records deferred product and maintenance proposals. A
backlog entry is not current authority and cannot authorize implementation or an external
operation. Promote an item through the requirements, decisions, design, threat, evaluation, and
delivery authorities before beginning it.

## Milestone status

| Milestone | Status | Evidence boundary |
| --- | --- | --- |
| AP-M3 | complete | Version 1 contracts and deterministic compilation |
| AP-M4 | complete | in-process Fixture qualification |
| AP-M5 | complete | infrastructure and Live-qualification planning |
| AP-M6 | complete | network runtime tested with fakes and loopback |
| AP-M7 | complete | static Terraform and inert workflow templates |
| AP-M8 | historical | W1/W2 merged; no real manifest accepted; W3-W12 never started |
| AP-M9 | W9 candidate-qualified; W10 Slices 1-5 merged to its integration branch and Slice 6 implemented on its ordered branch | operator-driven environment and application lifecycle |

AP-M9 replaces the withdrawn standalone Live-qualification milestone and supersedes the unexecuted
AP-M8-W3 through AP-M8-W12 plan. AP-M8-W1/W2 remain factual records of merged work. AP-M9 does not
retroactively turn them into deployment evidence.

## Active AP-M9 sequence

Milestones and work packages are planning containers rather than automatic branch boundaries.
Decompose substantial work into ordered, independently reviewable functional slices. The default
is to start a slice from updated clean `main` and merge its pull request before beginning the next
slice. W10 is an explicitly planned atomic integration exception: `feat/platform-member-directory`
starts from clean `main`, every W10 slice starts from and targets the latest clean integration
branch, and no partial W10 implementation merges to `main`. After all slices merge, the exact
integration revision is candidate-qualified and frozen before one cumulative pull request targets
`main`. Historical packages W1 through W9 retain the delivery shape under which they were
completed.

1. **AP-M9-W1 — governance rebaseline (merged):** define the product lifecycle, authority,
   architecture, threat controls, plan, evaluation, documentation routing, and historical
   boundary.
2. **AP-M9-W2 — retired manifest cleanup (implemented):** remove the operator-manifest schema,
   validator, synthetic example, command, tests, and obsolete active guidance without changing
   AP-M7 assets.
3. **AP-M9-W3 — lifecycle contracts and profiles (implemented, then simplified):** small
   staging/production profiles and the cross-owner integration, attachment, and qualification
   contracts. Preparation, status, and resume progress are private implementation state.
4. **AP-M9-W4 — interactive lifecycle core (implemented, then simplified):** credential-free
   preparation and status, exact operation approval, atomic progress, redaction, truthful failure
   state, and resumable deterministic execution behind external-effect seams.
5. **AP-M9-W5 — deployable Terraform (implemented):** phased bootstrap, foundation, and Shared
   Edge configuration; exact backend declarations; canonical plan
   policy; closed outputs; mocked plans; and deterministic command fakes.
6. **AP-M9-W6 — interactive platform deployment (implemented):** multi-stage exact-plan execution,
   reviewed action confirmation, human OAuth and external-DNS checkpoints, bounded DNS/TLS
   polling, readback, stop-on-discrepancy, transcript redaction, and interruption-safe resume.
7. **AP-M9-W7 — platform-side application lifecycle (implemented):** least-data bundle generation, exact target
   posture validation, immutable whole-generation registration and activation, reversible
   detachment/reactivation, terminal retirement, and distinct reserved-route responses.
8. **AP-M9-W8 — qualification and safe destruction (implemented):** revision-bound qualification,
   redacted evidence, process-local network fixtures, failure injection, reviewed generation rollback,
   resumable environment destruction that never targets Application State, and guarded real
   shared-platform deployment adapters. It does not deploy a Fixture Application.
9. **AP-M9-W9 — fixture application deployment lifecycle (implemented and candidate-qualified):**
   immutable fixture images and independent roots in a dedicated fixture application project; an
   explicit Shared VPC project-connection boundary; application-project-scoped integration
   bundles; a read-only application handoff readiness check; separate fixture handoff, platform registration, status, detachment, and fixture
   destruction; provider readback; deterministic fake coverage; and staging-only Candidate Source
   admission. The combined `fixture-deploy` shortcut is removed so fixtures exercise the same
   platform/application handoff as an external application.
10. **AP-M9-W10 — Platform Member Directory and explicit Identity Delivery:** implement the
    ADR-015 Version 2 contracts, environment-wide Firestore membership, explicit owner enrollment,
    bounded member lifecycle, public identity opt-in, Shared Edge enforcement, migration, fixtures,
    and Candidate Source qualification through seven ordered functional-slice pull requests into
    `feat/platform-member-directory`. Candidate-qualify and freeze that complete integration
    revision before its cumulative pull request to `main`. It performs no Accepted Source staging
    operation. Slice 1 implements only the inert Version 2 contracts, deterministic Version 1
    migration, and Contract evidence. Slice 2 adds the isolated member database, conditioned
    session/member IAM, closed infrastructure readback, and an unwired exact-key adapter. Slice 3
    adds dual-version Shared Edge loading, exact current-member readback, explicit Version 2
    identity delivery and admission, minimized assertions, and fail-closed runtime behavior.
    Slice 4 adds remote directory status, separate owner bootstrap, browser-bound enrollment,
    explicit-reference suspend/reactivate/remove transitions, atomic monotonic control/member
    updates, exact readback, and shallow Make targets. Slice 5 adds explicit Identity Delivery to
    handoff checks and outputs, emits one complete Version 2 bundle/intent family, migrates a
    readable Version 1 predecessor into one atomic complete Version 2 generation, and updates the
    networked fixtures and independent application verifier. No Slice 5 code was invoked against a
    provider. Slice 6 reconciles the human operator handoff, implemented limitations, and future
    Candidate Source procedure without changing behavior or invoking a provider.
11. **AP-M9-W11 — accepted staging operation:** from merged W10 code, deploy and qualify
    `apps-staging.comfforts.com` with the three synthetic applications and the reviewed member
    baseline. The deliberate command invocation and same-process confirmations authorize ordinary
    staging creation and update; destructive and irreversible boundaries retain separate approval.
12. **AP-M9-W12 — production readiness:** prove the production handoff and stop with
    `OWNERSHIP_TRANSFER_REQUIRED` while Finance Assistant or `apps.comfforts.com` remains
    Finance-owned.

AP-M9-W9 began only after AP-M9-W8 merged. Candidate staging operations exposed and corrected the
same-project fixture gap. The three cross-project fixtures, restricted-fixture detach, destruction,
redeployment, and reactivation, and the complete Candidate Qualification passed at W9 revision
`2fd045f6f720fe122103d42b3ebb6d25f5fbdac8`. That evidence is diagnostic pre-merge evidence, not
Accepted Source qualification. ADR-015 supersedes the per-registration membership assumption, so
AP-M9-W10 implements and candidate-qualifies that accepted boundary before AP-M9-W11 can own the
first Accepted Source staging operation. Production migration and Application Adoption remain
separate owner-controlled work after AP-M9-W12.

## Authority and claim discipline

Conflicts are resolved in this order: requirements, accepted ADRs, system design, public contracts,
implementation plan, evaluation strategy and threat evidence, runbooks and delivery evidence, then
prompts. A later document cannot silently broaden an earlier authority.

Use these status meanings:

- **Planned:** authority or behavior is described but not implemented.
- **Implemented:** repository behavior exists and passes deterministic checks; no live action is
  implied.
- **Qualified:** the named evaluation gate has revision-scoped evidence.
- **Historical evidence:** an immutable record that provides no current action authority.

The App Platform owns only shared platform boundaries. Application data, stores, providers,
secrets, principals, entitlements, runtime deployment, and Application State remain application
owned. Finance Assistant and `apps.comfforts.com` remain unchanged until their own adoption and
ownership-transfer authorities are approved.

## Evidence and secret boundary

Keep credentials, OAuth client secrets, Terraform state, saved plans, authenticated browser state,
provider payloads, and unredacted Live evidence outside Git. The implemented Platform Integration
Bundle and Application Attachment Bundle contracts admit only non-secret handoff values. They do
not authorize bundle generation or application adoption.

Run `make check` from the repository root for the credential-free, deterministic, non-mutating
repository gate. Authenticated plans, applies, DNS changes, identity changes, qualification, and
destruction must use later explicit AP-M9 operator targets and approvals.
