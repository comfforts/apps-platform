# AP-M9 · Operator-driven environment lifecycle

Version 0.11 | Status: AP-M9-W1 through AP-M9-W9 implemented and W9 candidate-qualified; all seven
AP-M9-W10 slices and candidate-readiness corrections are integrated; Version 2 Candidate Source
qualification passed at revision `d8fdb8afb2048e87b591ae400d7807a38784fd5c`; one final
post-reconciliation exact-revision rerun and freeze remain

This document is the canonical milestone plan for AP-M9 and its ordered work packages. Use the
[implementation plan index](../README.md) for plan routing. AP-M9-W10 has a separate
[work-package plan](w10_platform_member_directory.md) whose implementation detail overrides only
the W10 summary here.

Requirements: AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009

Decisions: ADR-001 through ADR-015

Design: [App Platform system design](../../03_system_design.md)

Threats: [App Platform threat model](../../06_threat_model.md)

Evaluation: [App Platform evaluation strategy](../../05_evaluation_strategy.md)

## Authority status

AP-M9-W1 is merged and establishes the active operator-lifecycle authority. It supersedes the
unexecuted AP-M8-W3 through AP-M8-W12 packages and the previously proposed standalone AP-M9
Live-qualification milestone. The old proposal produced no implementation, provider resource,
evidence bundle, or qualification result. AP-M8-W1/W2 remain historical merged work; AP-M9-W2
removed their retired manifest implementation from the active tree, AP-M9-W3 implemented lifecycle
contracts and profiles, AP-M9-W4 implemented the credential-free interactive core, AP-M9-W5
implemented the deployable Terraform lifecycle, AP-M9-W6 implemented interactive deployment
mechanics, AP-M9-W7 implemented the application integration lifecycle, and AP-M9-W8 implemented
qualification and safe-destruction mechanics without running an external operation. AP-M9-W9
implemented the missing Fixture Application deployment lifecycle and staging-only Candidate Source
admission, then candidate-qualified the three-fixture cross-project staging topology under the
Version 1 identity model.

An AP-M9 functional slice normally begins from updated clean `main`, uses a functionality-oriented
branch and pull request, passes `make check`, and merges before the next ordered slice starts.
Milestones and work packages remain planning containers; a substantial package may require
multiple slices. W10 is the explicit atomic exception: its slices target the
`feat/platform-member-directory` integration branch so the Version 1/Version 2 transition reaches
`main` only as one completed, candidate-qualified feature.
Repository implementation does not initiate an external operation. For ordinary reversible staging
creation or update, the owner's deliberate invocation of the named command plus its same-process
specification and plan confirmations authorizes the execution; no duplicate out-of-band approval is
required. Destruction, purge, ownership transfer, production cutover, and scope expansion retain
separately named approval.

## Outcome

AP-M9 delivers one Python operator product that prepares, deploys, inspects, integrates, qualifies,
and safely destroys an isolated Platform Environment. It deploys and qualifies staging with
synthetic Fixture Applications, generates versioned application handoffs, supports reversible
detachment and terminal retirement, and prepares production ownership transfer without changing
the existing Finance-owned production deployment.

The implemented W9 operator interface is:

```text
platform-preflight       platform-preflight-check  platform-prepare
platform-cancel          platform-deploy-check     platform-deploy       platform-status
fixture-project-bootstrap platform-connect-project application-handoff-check platform-outputs
platform-register        platform-detach           platform-retire       platform-qualify
platform-destroy         fixture-handoff           fixture-status        fixture-destroy
```

W10 extends that interface with the separately confirmed `platform-member-bootstrap-owner`, the
read-only browser-bound `platform-member-identify`, `platform-member-status`,
`platform-member-add`, `platform-member-suspend`,
`platform-member-reactivate`, and `platform-member-remove` operations. They administer only the
remote member directory and do not deploy the platform, compile a Registration Generation, or
deploy an application.

The local wizard remains active through OAuth and Squarespace work and continues after Enter.
Rerunning is interruption recovery only. Generated execution facts are private progress rather than
operator-authored manifest fields.

## Scope and boundaries

AP-M9 includes:

- the governance clean break and removal of the retired manifest path;
- small non-secret staging and disabled production Environment Profiles;
- one closed destructive specification plus Platform Integration Bundle, Application Attachment
  Bundle, and Qualification Evidence contracts; deployment preparation, status, and progress stay
  private;
- one focused interactive Python lifecycle with seams only at external effects and deterministic
  fakes at those boundaries;
- deployable bootstrap, platform-foundation, and Shared Edge Terraform phases;
- one short-lived verified human operator session, fresh exact plans or bounded actions, typed
  confirmation, and provider or state readback, with no operation-identity fleet or operator
  impersonation binding;
- interactive OAuth/Secret Manager and external Squarespace DNS checkpoints;
- application registration, detach/reactivate, permanent retirement, and complete-generation
  activation;
- synthetic Fixture Application deployment, Live qualification, evidence, rollback, and safe
  platform destruction; and
- read-only production preparation and a Finance ownership-transfer handoff.

AP-M9 excludes:

- automatic Finance Assistant adoption, script mutation, state import, production cutover, or
  ownership transfer;
- implicit import or replacement of any existing `apps.comfforts.com` resource;
- application runtime, store, provider, secret, principal, or Feature Entitlement ownership;
- a service-account key, long-lived credential, secret payload in a prompt or bundle, routine broad
  owner apply, cross-state read, automatic rollback, automatic cleanup, or destructive recovery;
- a production availability commitment or staging evidence used as production qualification; and
- Python-to-Go migration, which remains a later contract-preserving milestone after the Python
  product is delivered and qualified.

## Work packages

### AP-M9-W1 · Governance rebaseline

Define AP-PR-010 through AP-PR-012, AP-QR-007 through AP-QR-009, ADR-010 through ADR-013, canonical
vocabulary, the AP-M9 design and threat refinements, this plan, AP-EVAL-M9, active reading order,
repository layout, historical status, and deterministic governance checks. Preserve AP-M8-W1/W2 as
history and mark AP-M8-W3 through W12 and the old AP-M9 proposal superseded before execution. This
package changes documentation and tests only and authorizes no external action.

### AP-M9-W2 · Retired manifest-path cleanup

Removed the operator-input-manifest schema, synthetic example, chain loader, command, exports,
manifest-specific tests, obsolete acceptance prompt, and inactive workflow assumptions that served
only the superseded path. Preserved reusable Terraform, runtime, fixture, contract, state, security,
and deterministic verification assets. Git history and the historical status record preserve the
removed implementation.

### AP-M9-W3 · Lifecycle contracts and environment profiles

Implement small closed staging and disabled-production profiles plus versioned contracts for
destructive scope, Platform Integration Bundles, Application Attachment Bundles, and Qualification
Evidence. Preparation, status, and resume progress are private operator state rather than
cross-owner contracts. Canonicalization and digest rules must be deterministic. Profiles
contain stable owner decisions only; generated or discoverable facts, credentials, secrets, state,
plans, and provider payloads are prohibited.

### AP-M9-W4 · Interactive operator core

Implemented the Python operator and thin Make targets for credential-free preparation and status.
The current design keeps seams at Git/provider commands, Terraform, DNS, the console, private
state, and time; validates clean source and tools; discovers non-secret facts; approves one small
operation fingerprint; records atomic progress; reports truthful status; and resumes interrupted
journeys. This package performs no authenticated mutation.

### AP-M9-W5 · Deployable Terraform lifecycle

Implemented bootstrap, platform-foundation, and Shared Edge phases that preserve exclusive
ownership and one platform lineage without placeholder inputs. Added exact staging backend
declarations and a path-bounded renderer, canonical plan policy, production refusal, closed phase
outputs, mocked plans, and deterministic command fakes. The later W8 operator-experience
rebaseline removed the unexecuted 31-identity/impersonation profile in favor of one verified
short-lived human operator session. No authenticated plan, backend operation, provider mutation,
or DNS action occurred in the repository slice.

### AP-M9-W6 · Interactive platform deployment

Implemented the multi-stage deployment engine: preflight; backend bootstrap; foundation; image
publication; OAuth branding/client/Secret Manager checkpoint; Shared Edge/load balancer/address;
Squarespace DNS checkpoint; DNS propagation and TLS readiness; readback; stop-on-discrepancy; and
resume. The same process displays exact manual values and waits for Enter. Every Terraform stage
binds a fresh private saved plan to W5 policy, redacted digest/summary, confirmation, same-artifact
apply, and readback. The W8 operator-experience rebaseline makes `platform-deploy` perform
preparation, review, approval, and deployment in one invocation, uses ordinary `y/N` confirmation
for reviewed plans, and reserves typed phrases for irreversible actions. The closed non-fake
subprocess boundary uses absolute executables, argv, bounded paths, and the verified human session
without shell interpolation. Deterministic command fakes and transcript tests cover success, no-change,
cancellation, manual checkpoint, bounded polling, partial failure, discrepancy, interruption, and
resume. W8's external-action safety completion wires the default local deployment construction only
when the pinned toolchain, verified human Cloud SDK session, user Application Default Credentials,
and exact staging project all agree. The pull requests executed no real operation.

### AP-M9-W7 · Platform-side application integration lifecycle

Implemented least-data outputs for public, authenticated, and restricted applications, exact
bundle/current-platform/target-posture validation, complete-generation compilation and create-only
publication, exact typed activation, detachment, replacement attachment/reactivation, and terminal
retirement. Detached and retired routes remain reserved and return distinct generic `503` and `410`
responses; unknown routes remain closed. Interruption resumes only an identical immutable
publication. Provider readback, generation control, and terminal effects remain injected. No
operation read, mutated, or destroyed
Application State, and no external action occurred.

### AP-M9-W8 · Qualification and safe destruction

Implemented process-local networked synthetic Fixture Applications, `platform-qualify`, a strict revision-bound
evidence contract and prohibited-data scan, the closed ten-check profile, failure injection,
reviewed whole-generation rollback, and `platform-destroy`. Added exact local/provider/fixture
readback, least-data accepted handoff records, separate destructive specification compilation,
typed confirmation, post-confirmation reread, ordered stop-on-failure execution, and private
create-only resume state. Destruction refuses active attachments or ownership/inventory mismatch,
never targets Application State, and retains backends, recovery material, and evidence absent
separate purge authority. It also retains the Shared VPC host, application network, and subnet
until separately authorized project disconnection, while removing their billable Cloud NAT and
router during ordinary platform destruction. Guarded shell-free Cloud SDK generation, traffic, attachment, and
readback adapters are deterministic-test covered but were not invoked. W8 also completes the real
staging deployment adapter: exact first-run/recovery bootstrap, provider-service enablement,
digest-pinned and source-allow-listed image build, create-only initial generation, OAuth metadata,
authoritative/recursive DNS, TLS, and final readback. W9 completes the live qualification and
destruction defaults without invoking them.

### AP-M9-W9 · Fixture Application deployment lifecycle — implemented and candidate-qualified

Implement one interactive fixture-application operator over the existing image, bundle, Terraform,
provider, and registration seams. A one-time `fixture-project-bootstrap` creates or repairs a
dedicated fixture application project, required services, private versioned state bucket, and image
repository. `platform-connect-project` attaches that existing project to the platform Shared VPC,
grants its Cloud Run service agent read-only host-network discovery and network-user access only on
the application subnet, reads back the result, and records the non-secret connection without
creating a runtime or route.

For each selected fixture, `platform-outputs` produces one application-project-scoped integration
bundle. `fixture-handoff` consumes that exact bundle, builds or reuses one immutable source-bound
fixture image, plans and applies only its independent Application State root, reads back project,
network, ingress, IAM, audience, and readiness posture, and emits the exact attachment bundle and
registration intent. It stops before registration. After inspection, `platform-register` activates
a complete Registration Generation while preserving other registrations. There is no combined
`fixture-deploy` shortcut. `fixture-status` is read-only and supports suite-wide or selected
readback. `fixture-destroy` requires a prior `platform-detach`, then requires fixture-specific typed
confirmation and destroys only selected fixture Application State. Every mutation uses the verified
human session, fresh exact plans, policy, confirmation, readback, private progress, and safe resume.
Deterministic fakes cover the complete journey. W9 also completes browser-mediated live qualification and multi-stage platform
destruction through traffic disable, external-DNS removal, Shared Edge removal, protection unlock,
destructible-foundation removal, and retained-inventory readback. W9 also binds `accepted` or
`candidate` source authority into specifications, status, bundles, and qualification evidence. A
candidate must be a clean pushed non-main revision containing current `origin/main`, can operate
only on staging, publishes separate candidate evidence, and cannot authorize production or accepted
qualification. Candidate staging at revision
`2fd045f6f720fe122103d42b3ebb6d25f5fbdac8` exercised the three cross-project fixtures, browser and
runtime qualification, restricted-fixture detachment, Application State destruction, redeployment,
and reactivation. Generation 8 was restored active after the qualification rollback exercise. This
is W9 Candidate Qualification, not an accepted staging result.

The fixture handoff persists the canonical integration and attachment bundle pair plus registration
intent in ignored private state, prints their paths and digests for inspection, and stops before
registration. Rerunning it may reuse an exact prepared pair only after full source, project
connection, generation, digest, image, relationship, and provider-posture revalidation.

W9 also removes digest copy-and-paste from the optional platform-preparation flow. Default
`platform-deploy` reads and revalidates the current approved specification and reuses it when its
source, profile, environment, session, project, ownership, tool, provider, approval, and progress
bindings remain exact. Absent, stale, or unapproved intent falls back to normal preparation;
malformed retained state and current blockers stop without evidence replacement. Explicit digest
selection remains supported as a non-default pin.

W9 also preserves a partial or complete Shared Edge when a changed source begins a fresh
deployment. Before foundation planning, the operator projects exact Platform State addresses. An
existing Shared Edge selects a refresh-only foundation plan whose policy admits only `no-op` and
`read` observations; the later normal Shared Edge plan performs the actual reconciliation. This
prevents a new specification from interpreting already recorded edge resources as foundation-stage
deletion targets. Before that later plan, an existing managed-certificate state address keeps the
Shared Edge in its TLS-enabled shape; only a genuine first deployment renders the dark
TLS-disabled phase. DNS and provider certificate readback remain mandatory and independent of the
state-address observation.

W9 also adds `platform-preflight` as the non-publishing readiness path. It runs the same source,
profile, tool, authentication, project, ownership, and discovery checks used before preparation,
reports exact blockers, and stops before specification generation, digest publication, approval,
executor construction, private lifecycle-state writes, or external mutation.

W9 also exposes `platform-preflight-check` and `platform-deploy-check` for uncommitted maintenance.
They retain real profile, session, project, provider, private-record, Terraform-state, rendering,
and plan-policy checks while skipping `SOURCE_NOT_CLEAN` and treating other source findings as
diagnostics. The deployment check uses lock-free ephemeral plans, owns required platform-service
and platform-resource readiness, and reports `ready`, `reconciliation-required`, `incomplete`, or
`blocked`. It cannot approve, apply, execute an action or checkpoint, write operational lifecycle
state, or become deployment or qualification evidence. `platform-deploy` consumes the same result
before approval or mutation, stops on a blocked check, and still creates fresh exact plans for any
reconciliation it executes.

W9 also exposes `application-handoff-check` as the read-only gate immediately before bundle
publication. It consumes platform readiness without decoding deployment stages, then combines fresh
application-project service, Shared VPC and subnet-permission readback with bundle inputs, access
mode, and application identity projection. It reports platform reconciliation separately from
application-project repair and cannot publish a bundle, approve or apply a plan, mutate a provider
resource, or write operational lifecycle state.

W9 completes all-traffic Direct VPC egress for attached application projects with one
platform-owned regional Cloud Router and Public Cloud NAT scoped to the application subnet. The
foundation output and Shared Edge readback bind the exact router, NAT, and egress mode; the bounded
cross-project migration policy permits only their exact inherited creates. This enables protected
fixtures to retrieve the public platform JWKS without granting application ownership of shared
network resources. Fixture rejection logs expose only allowlisted constant verification codes.

W9 finally simplifies the repository implementation without changing the operator command
sequence: it replaces the generic stage graph and append-only journal chain with one fixed readable
deployment workflow and one atomic private progress record; removes intermediate preflight,
service, DNS, and deployment attestations; keeps only cross-owner and final-evidence digests;
consolidates repeated console and waiting seams; and replaces framework-shaped tests with focused
operator-flow, ownership, exact-plan, readback, bundle, fixture, qualification, and destruction
coverage. The Finance Assistant wizard remains the interaction reference for a linear human-run
session, while Apps Platform retains multi-application ownership boundaries and independent state.

The fixed workflow is explicitly versioned when its persisted stage schema changes. The completed
11-stage predecessor remains readable, immutable historical progress; the current 12-stage workflow
starts fresh progress only after the operator confirms current-pointer supersession. It never
synthesizes runtime-activation evidence for the predecessor, never resumes an active predecessor as
the current workflow, and reports invalid retained state through named readback blockers.

### AP-M9-W10 · Platform member directory and explicit identity delivery

Implement ADR-015 without changing the established top-level platform and application lifecycle.
This package introduces a Version 2 registration, compiled-generation, integration-bundle,
attachment-handoff, and verified-identity contract family plus a deterministic Version 1 migration:
public registrations migrate to Identity Delivery `none`; authenticated and restricted
registrations migrate to `required`; every per-registration member set is removed. A public
application may select `optional` only through an explicit reviewed registration update.

Create one Firestore Platform Member Directory per Platform Environment. Platform State owns the
database configuration, required indexes, and least-privilege Shared Edge access; remote member
records remain operational data and never become Terraform input, Git configuration, a Registration
Generation, a bundle member list, or public evidence. The edge resolves an active member by verified
issuer and immutable subject, fails restricted admission closed when the directory is absent or
unreadable, and delivers only the current visitor's minimal application-audience-bound Version 2
context. Public `none` suppresses Platform Identity even when a Platform Session exists; public
`optional` permits but does not require platform login; authenticated and restricted use `required`.

Add a separately confirmed `platform-member-bootstrap-owner` operation that works only against a
remotely empty directory and never infers the Visitor identity from the Cloud Operator. Add bounded
member status, add, suspend, reactivate, and remove operations with exact predecessor checks,
idempotent mutation, explicit confirmation, least-data output, and remote readback. Membership
changes must not compile a Registration Generation or deploy an application. An empty directory is
a valid deployment, but it denies every restricted route and cannot pass restricted qualification.

Update the compiler, edge runtime, operator, fixtures, fakes, contracts, documentation, and focused
deterministic tests together. Candidate Source staging qualification must explicitly bootstrap the
owner, prove a second member's allow/suspend/reactivate/remove lifecycle through
`fixture-restricted`, prove public anonymous and optional-identity behavior, prove authenticated
behavior remains membership-independent, verify application Feature Entitlements remain separate,
and restore the reviewed member baseline. This package produces Candidate Source evidence only. It
does not perform the first Accepted Source operation, change production, or adopt a real
application.

Deliver this package through the seven ordered functional slices defined in the W10 work-package
plan. Create `feat/platform-member-directory` from clean `main`; each slice has its own
functionality-oriented branch and pull request targeting that integration branch, contains one or
more coherent commits, and merges before its successor begins. Candidate-qualify and freeze the
exact complete integration revision before opening its cumulative pull request to `main`.

### AP-M9-W11 · Accepted Source staging deployment and qualification

From Accepted Source on clean protected main, deliberately invoke staging preparation/deployment,
bootstrap or verify the Platform Owner member through the separate member lifecycle, complete the
OAuth and Squarespace checkpoints, deploy/register the Version 2 fixture suite, complete
AP-EVAL-M9, exercise the reviewed member allow/deny baseline, detach and destroy fixture assets,
and perform an owner-approved platform destroy/redeploy rehearsal. Ordinary staging creation and
update use the command's same-process review and confirmations; destructive steps retain their
separate authority. Leave staging deployed and qualified at the accepted revision. Commit only an
approved secret-free evidence index; no credential, secret, member identity, state, plan, raw
provider response, browser state, or application payload enters Git.

### AP-M9-W12 · Production readiness and Finance handoff

Enable only read-only production preparation. Discover existing production ownership, return
`OWNERSHIP_TRANSFER_REQUIRED`, inventory future Platform versus Finance Application State, and
define the application-script change, state transfer or replacement, DNS/traffic cutover, rollback,
and evidence prerequisites. This package changes no production resource. Actual production
deployment is a later joint platform checkpoint plus Finance-owned Application Adoption.

## Ordered delivery and external-action gate

AP-M9-W1 through AP-M9-W12 are ordered planning containers. Substantial work packages are delivered
through separately merged functional slices rather than being forced into one branch. No staging
resource is created merely because W6 contains shared-platform deployment mechanics or W9 contains
Fixture Application deployment mechanics. The clean pushed W9 pull-request revision deliberately
exercised those targets on staging with `SOURCE_AUTHORITY=candidate`; its digest-bound evidence is
Candidate Qualification and cannot satisfy Accepted Source qualification or qualify production.
W10 uses seven ordered functional slices on `feat/platform-member-directory` to replace the Version
1 identity and restricted-membership model without partially changing `main`. After every slice is
merged, the exact complete integration revision is candidate-qualified and frozen, then one
cumulative pull request merges it to `main`. Candidate qualification passed at revision
`d8fdb8afb2048e87b591ae400d7807a38784fd5c`; the documentation reconciliation changes that exact
revision and therefore requires one complete rerun before freeze. W11 begins only after the final
merge to `main` and repeats the complete journey from Accepted Source, producing the first accepted
staging result. W12 follows that result.

Within W10 the operator first deploys the directory infrastructure, deliberately bootstraps the
owner, exercises member lifecycle, deploys the Version 2 fixtures, and performs candidate
qualification. Within W11 the operator order is preparation and digest approval; shared-platform
deployment; owner-member verification; fixture integration-bundle generation; fixture application
deployment; attachment registration; qualification; fixture detachment and application-owned
cleanup; optional approved platform destroy/redeploy rehearsal; final qualification; and evidence
reconciliation. The first failed or discrepant stage stops every dependent action.

## Acceptance criteria

AP-M9 is accepted only when:

1. AP-M9-W1 through AP-M9-W12 complete in order, their repository changes merge, and the complete
   deterministic gate passes.
2. A fresh operator can deploy staging from reviewed source through one interactive session.
3. OAuth and Squarespace actions use exact same-process Enter checkpoints and truthful readback or
   operator-attested status.
4. Preparation asks only genuine decisions and produces one complete approved specification.
5. Interruption resumes from the last closed stage without repeating a successful mutation.
6. Public, authenticated, and restricted fixtures consume real Version 2 platform bundles, deploy
   in separate Application State, register, route, detach, redeploy, reactivate, and retain terminal
   retirement.
7. Public `none` and `optional` identity delivery, authenticated membership-independent admission,
   restricted active-member admission, owner bootstrap, second-member suspension/reactivation/removal,
   directory failure, and application-owned Feature Entitlements pass deterministic, Candidate
   Source, and Accepted Source staging qualification without exposing member records.
8. AP-EVAL-M9 passes for the exact staging revision with secret-free evidence.
9. Platform destruction refuses unsafe state, changes no application-owned resource, and passes its
   approved staging rehearsal.
10. Production preparation proves staging/production isolation and blocks on current Finance
   ownership rather than importing or mutating it.
11. `make check` remains deterministic, credential-free, network-free, and non-mutating.
12. Finance Assistant, `apps.comfforts.com`, and every real application remain unchanged pending
    their own adoption and production-cutover approvals.

## Trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M9-W1, AP-M9-W2 | AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-013 | AP-TM-007 through AP-TM-014 |
| AP-M9-W3, AP-M9-W4 | AP-PR-010 through AP-PR-012; AP-QR-003, AP-QR-004, AP-QR-006 through AP-QR-009 | ADR-010 through ADR-013 | AP-TM-001 through AP-TM-003, AP-TM-007 through AP-TM-014 |
| AP-M9-W5, AP-M9-W6 | AP-PR-001 through AP-PR-005, AP-PR-010; AP-QR-001 through AP-QR-009 | ADR-001, ADR-004 through ADR-011, ADR-013 | AP-TM-001 through AP-TM-014 |
| AP-M9-W7 | AP-PR-001 through AP-PR-007, AP-PR-009, AP-PR-011, AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-006, ADR-008, ADR-012, ADR-013 | AP-TM-001 through AP-TM-014 |
| AP-M9-W8, AP-M9-W9 | AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-014 | AP-TM-001 through AP-TM-014 |
| AP-M9-W10 | AP-PR-004 through AP-PR-006, AP-PR-008, AP-PR-010, AP-PR-011; AP-QR-001, AP-QR-002, AP-QR-004, AP-QR-006 through AP-QR-009 | ADR-003, ADR-004, ADR-006, ADR-008, ADR-012, ADR-014, ADR-015 | AP-TM-004 through AP-TM-011, AP-TM-013, AP-TM-014 |
| AP-M9-W11 | AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-015 | AP-TM-001 through AP-TM-014 |
| AP-M9-W12 | AP-PR-007, AP-PR-009 through AP-PR-012; AP-QR-001, AP-QR-003 through AP-QR-009 | ADR-001, ADR-002, ADR-004, ADR-007, ADR-010 through ADR-015 | AP-TM-007 through AP-TM-014 |
