# AP-M9-W10 · Platform Member Directory and explicit Identity Delivery

Status: Slices 1-3 implemented on their named branches without Version 2 runtime activation; the
Slice 3 integration merge, Slices 4 through 7, and Candidate Source qualification remain

Requirements: AP-PR-004 through AP-PR-006, AP-PR-008, AP-PR-010, AP-PR-011,
AP-QR-001, AP-QR-002, AP-QR-004, AP-QR-006 through AP-QR-009

Decisions: ADR-003, ADR-004, ADR-006, ADR-008, ADR-012, ADR-014, ADR-015

Evaluation: AP-EVAL-M9-01 through AP-EVAL-M9-09

Threats: AP-TM-004 through AP-TM-011, AP-TM-013, AP-TM-014

## Delivery outcome

AP-M9-W10 replaces the implemented Version 1 per-registration membership model with one
environment-wide Platform Member Directory and explicit Identity Delivery. It preserves the
existing platform/application ownership boundary and top-level lifecycle while making restricted
admission platform-wide, public identity delivery deliberate, and member administration independent
of Registration Generations and application deployment.

The work package ends with deterministic repository evidence and Candidate Source staging
qualification for the new model. It does not perform the first Accepted Source staging operation;
AP-M9-W11 owns that operation after the complete, candidate-qualified W10 integration branch merges
to `main`.

## Current platform baseline

The implemented platform currently provides:

- one Shared Edge for catalogue, routing, admission, Google OIDC sessions, assertion delivery, and
  platform-owned DNS/TLS and networking;
- immutable complete Registration Generations and separate Platform versus Application State;
- cross-project application attachment through an explicit Shared VPC connection;
- versioned Platform Integration and Application Attachment Bundles;
- interactive platform deployment, application handoff, registration, qualification, detachment,
  retirement, fixture destruction, and platform destruction;
- public, authenticated, and restricted fixture behavior under Version 1 contracts; and
- Candidate Source evidence for the W9 staging topology and fixture lifecycle.

Version 1 nevertheless stores exact issuer-and-subject members in each restricted registration,
implicitly associates identity behavior with Admission Mode, and requires a new Registration
Generation for membership changes. Its candidate evidence remains truthful predecessor evidence
but cannot qualify ADR-015.

## Target behavior

One Firestore Platform Member Directory belongs to each Platform Environment. Platform State owns
the database configuration, required indexes, and least-privilege Shared Edge IAM. Member records
are remote operational data managed through the member lifecycle; they are not Terraform inputs,
Git configuration, registration fields, generation content, bundle member lists, or public
evidence.

Every registration declares Admission Mode and Identity Delivery:

| Admission Mode | Identity Delivery | Target behavior |
| --- | --- | --- |
| `public` | `none` | Anonymous access; no Platform Identity is delivered even when a Platform Session exists. |
| `public` | `optional` | Anonymous access remains available; a visitor may deliberately use platform login and then receive application-bound identity. |
| `authenticated` | `required` | A valid Platform Identity is required; Platform Membership is not required. |
| `restricted` | `required` | A valid Platform Identity and an active environment member record are required. |

The Shared Edge keys membership by verified issuer and immutable subject and delivers only the
current visitor's minimal application-audience-bound context. It never delivers the directory,
another member, an application role, a provider right, or a Feature Entitlement. A public
application's separate OAuth client and identity remain independent; account linking is an
explicit application-owned process.

## Scope controls

### Included

- Version 2 registration, compiled-generation, Platform Integration Bundle, Application Attachment
  Bundle, registration-intent, and Verified Identity Context contracts;
- deterministic Version 1-to-Version 2 migration;
- Firestore directory infrastructure, indexes, runtime IAM, provider readback, and an in-memory
  deterministic adapter;
- Shared Edge membership lookup, explicit Identity Delivery, minimal assertion projection, and
  fail-closed restricted admission;
- explicit Platform Owner bootstrap plus bounded member status, add, suspend, reactivate, and
  remove journeys;
- handoff checks, bundle generation, fixtures, qualification, evidence privacy, documentation, and
  focused regression coverage; and
- Candidate Source staging deployment and qualification only after its existing operator authority
  and owner direction are satisfied.

### Excluded

- application users, principals, account links, product roles, provider permissions, or Feature
  Entitlements;
- OAuth test-user administration, IAP accessors, Google Groups, or Cloud Identity groups;
- a generic identity-directory framework or support for a second real membership backend;
- ADR-016 operator-state recovery, fabricated local history, or recovery from an empty private
  journal;
- the W11 Accepted Source staging operation, W12 production readiness, production mutation,
  Finance Assistant changes, or any real Application Adoption; and
- automatic owner enrollment during `platform-deploy` or enrollment from an operator-entered email
  address.

If implementation requires one of these exclusions, a new contract family beyond Version 2, a
second provider, or any functional slice approaching a ninth substantive commit, stop and re-scope
with the owner.

## Contract and data transition

Version 1 remains readable historical input. Migration is deterministic:

- public registrations become Identity Delivery `none`;
- authenticated and restricted registrations become `required`;
- every per-registration member set is discarded rather than copied; and
- public `optional` requires an explicit reviewed registration update.

Slice 1 is an additive, inert compatibility slice. It adds independently versioned Version 2
schemas, canonical loaders, validators, migration, vectors, and Contract evidence alongside the
unchanged active Version 1 family. It does not make any runtime, operator command, fixture, bundle
publisher, or active Registration Generation emit or activate Version 2. Adding those inactive
contracts therefore does not silently change a Version 1 consumer. The active transition occurs
only through one complete Version 2 generation after the infrastructure, runtime, lifecycle, and
handoff consumers in Slices 2 through 5 are implemented. A slice must stop rather than introduce a
partially migrated consumer or mixed Version 1/Version 2 activation.

The implemented Slice 1 result includes a Version 2 Application Attachment schema supporting the
registration and compiled-generation family, plus Version 2 Platform Integration Bundle,
Application Attachment Bundle, and registration-intent lifecycle schemas. Version-aware loaders
read historical Version 1 or inert Version 2 documents through explicit compatibility entry
points. The deterministic translator preserves generation and registration-revision values as a
compatibility representation, removes registration-scoped member data, maps public to `none`, and
maps authenticated and restricted to `required`. The Version 2 compiler remains a pure,
non-publishing test seam. It accepts a Version 1 predecessor only for transition comparison and
binds the successor to the predecessor's existing normalized generation digest. The unchanged
Version 1 State Ownership Manifest continues to describe ownership because Slice 1 changes no
ownership field or meaning.

The migration must not activate a mixed Version 1/Version 2 generation. The new runtime admission
model becomes active only after the directory infrastructure, runtime IAM, Version 2 compiler and
consumers, member lifecycle, rollback behavior, and fixtures are available. An empty directory is
a valid deployed state: public and authenticated routes continue to work, restricted routes deny
all visitors, and restricted qualification remains unavailable.

A member record contains only the stable verified identity key, membership lifecycle state, and
the minimum operation metadata required for idempotency and readback. Email and display name may be
shown transiently during the confirmed browser flow but are not keys, CLI inputs, bundle values,
ordinary status output, assertion fields, or retained evidence. The public operator interface uses
an opaque member reference rather than issuer, subject, or email.

## Proposed operator interface

The exact command spelling is part of this plan and should change only if implementation evidence
shows a concrete usability or safety defect.

| Make target | Purpose | Mutation boundary |
| --- | --- | --- |
| `platform-member-bootstrap-owner` | Enroll the first Platform Owner after verifying the remote directory is empty and completing a separately confirmed Google Visitor flow | Creates exactly one initial member after exact review and confirmation; refuses a non-empty directory |
| `platform-member-status` | Report coarse directory readiness or one opaque member reference and lifecycle state | Read-only; never lists identities or exposes the directory |
| `platform-member-add` | Enroll one additional verified Google Visitor through a separately confirmed browser flow | Creates one member idempotently after exact review and confirmation |
| `platform-member-suspend` | Make one opaque member reference ineligible for restricted admission | Requires exact predecessor, confirmation, and remote readback |
| `platform-member-reactivate` | Restore one suspended opaque member reference | Requires exact predecessor, confirmation, and remote readback |
| `platform-member-remove` | Remove one opaque member reference from active membership | Requires exact predecessor, destructive confirmation, and absence readback |

Every target requires `ENVIRONMENT=<name>`. Suspend, reactivate, remove, and single-member status
also require `MEMBER_REFERENCE=<opaque-reference>`. Add and bootstrap obtain issuer and subject only
from the confirmed identity-provider callback; they do not accept an email as identity proof.
Ordinary output may show the opaque reference, lifecycle state, timestamps, and coarse outcome but
never raw identity claims or a member list.

`application-handoff-check` and `platform-outputs` gain
`IDENTITY_DELIVERY=<none|optional|required>`. The validator enforces its allowed combination with
`ACCESS_MODE`. `fixture-handoff` consumes the value from the Integration Bundle, and
`platform-register` consumes it from the reviewed bundle and intent rather than accepting a second
independent CLI value.

Existing commands change only where the new responsibility belongs:

- `platform-preflight-check` and `platform-preflight` verify tools, authentication, project, and
  readable prerequisites but do not require a member;
- `platform-deploy-check` verifies directory infrastructure and runtime IAM readiness without
  reading or listing member identities;
- `platform-deploy` reconciles directory infrastructure and Shared Edge support but never enrolls a
  member;
- `platform-status` reports only coarse directory state such as `empty`, `ready`, or `unreadable`;
  and
- `platform-qualify` uses the same member service and confirmation boundaries to exercise the
  reviewed second-member lifecycle without inventing a separate administration path.

## Operator journeys after W10

### New environment

```text
platform-preflight
    -> platform-deploy
    -> platform-member-status             # remote directory is empty
    -> platform-member-bootstrap-owner    # deliberate visitor identity enrollment
    -> platform-member-status             # owner baseline is readable
    -> application-handoff-check + platform-outputs with IDENTITY_DELIVERY
    -> application deploy or fixture-handoff
    -> platform-register
    -> platform-qualify
    -> platform-status
```

Deployment is successful with an empty directory, but restricted routes deny everyone until owner
bootstrap succeeds. The Cloud Operator and enrolled Google Visitor may be different identities.

### Routine member administration

```text
platform-member-add
    -> restricted access succeeds on the next request
platform-member-suspend
    -> restricted access is denied on the next request
platform-member-reactivate
    -> restricted access succeeds on the next request
platform-member-remove
    -> restricted access is denied on the next request
```

No step in this sequence runs `platform-deploy`, compiles a Registration Generation, republishes a
bundle, or deploys an application. An already admitted streaming connection is not forcibly
terminated; the new state applies to the next request or new connection.

### Candidate migration from the deployed Version 1 staging model

1. Run the read-only platform checks and inspect the Version 1 predecessor state.
2. Deploy Candidate Source directory infrastructure, Version 2 runtime support, and deterministic
   migration without copying per-registration members.
3. Verify the remotely empty directory and deliberately bootstrap the owner.
4. Regenerate Version 2 application-scoped bundles, redeploy or reconcile each fixture attachment,
   and activate one complete Version 2 Registration Generation.
5. Add a second member, prove allow, suspend/deny, reactivate/allow, and remove/deny through
   `fixture-restricted`, then restore the reviewed owner-only baseline.
6. Prove public `none`, public `optional`, authenticated membership-independent admission,
   application-owned feature denial, directory failure, logout, rollback, isolation, and evidence
   privacy.

Candidate evidence is bound to the exact clean pushed `feat/platform-member-directory` revision
after every slice has merged. It cannot replace Accepted Source evidence. Any tracked change after
that run invalidates the qualification and requires it to run again before the cumulative pull
request to `main`. W11 repeats the complete accepted journey after that pull request merges.

## Planned functional slices and effort signals

The target is seven ordered, independently reviewable functional slices integrated atomically.
Create `feat/platform-member-directory` once from updated clean `main`. The current governance pull
request and every implementation slice use that integration branch as their base and pull-request
target. After a slice merges, its successor starts from the latest clean integration branch. No
slice targets `main`, and each slice contains one or more coherent commits. If `main` advances,
reconcile it into the integration branch through a
reviewed synchronization before starting the next slice and before final qualification; do not
rewrite published slice or integration history. Percentages express relative implementation
effort. File counts are paths expected to be touched in that slice and overlap across rows. Working
tokens are rough agent-context and reasoning estimates, not repository artifacts or budget
authority.

| Slice | Branch | Reviewable outcome | Expected paths | Working tokens | Relative effort |
| --- | --- | --- | ---: | ---: | ---: |
| 1. Version 2 contracts and migration | `feat/identity-delivery-v2-contracts` | Add the complete Version 2 schema family, deterministic Version 1 migration, canonical validation, vectors, and compatibility tests | 37 actual | 18k-28k | 16% |
| 2. Member-directory infrastructure | `feat/platform-member-directory-infrastructure` | Add the isolated named Firestore database, conditioned session/member IAM, closed outputs/readback, exact plan policy, an unwired exact-key adapter, and deterministic infrastructure tests | 32 actual | 18k-30k | 16% |
| 3. Shared Edge enforcement | `feat/member-directory-edge-enforcement` | Add current-member lookup, public `none`/`optional`, authenticated/restricted behavior, minimal Version 2 assertions, fail-closed handling, and runtime tests | 29 actual | 24k-36k | 20% |
| 4. Member lifecycle operations | `feat/platform-member-lifecycle` | Add owner bootstrap and status/add/suspend/reactivate/remove commands, browser confirmations, opaque references, idempotency, readback, diagnostics, Make targets, and focused tests | 14-22 | 24k-38k | 20% |
| 5. Version 2 application handoffs | `feat/identity-delivery-application-handoffs` | Add Identity Delivery handoff inputs, Version 2 bundle/intent consumers, fixture behavior, migration-safe registration, and application-boundary tests | 10-16 | 14k-24k | 12% |
| 6. Operator handoff reconciliation | `docs/identity-delivery-operator-handoff` | Reconcile README, runbook, design, contracts, plan status, prompt, governance tests, actual limitations, and final qualification procedure without adding behavior | 8-14 | 8k-14k | 4% |
| 7. Candidate qualification readiness | `evidence/member-admission-candidate-qualification` | Complete qualification support for owner bootstrap, second-member lifecycle, public opt-in, authenticated independence, directory failure, rollback, and least-data evidence; after merge, qualify the exact integration revision | 10-18 | 16k-26k | 12% |

Slices 1 and 2 are merged to the integration branch. Slice 3 is implemented on its named branch and
is ready for its integration pull request after its verification gate passes. Slice 4 remains
blocked until that pull request merges to the latest clean `feat/platform-member-directory`; no
member mutation or owner-bootstrap behavior belongs in the Slice 3 branch.

Estimated total: seven slices, about 55-85 unique changed paths, 122k-196k working tokens, and
roughly 7-12 focused implementation days excluding owner review, provider propagation, and waiting
for external checks. These estimates should be revised when a concrete implementation result shows
that the scope is materially smaller or larger; they must never be used to waive a test, combine
independent outcomes, or force an unsafe artificial commit boundary.

## Verification strategy

### Evidence ownership by functional slice

| Slice | Evidence owned by the slice | External-operation boundary |
| --- | --- | --- |
| 1. Version 2 contracts and migration | Deterministic AP-EVAL-M9-02 Contract evidence for schemas, canonical migration, compatibility loading, and rejection vectors | No credential lookup or external operation |
| 2. Member-directory infrastructure | Deterministic and mocked-plan AP-EVAL-M9-04 evidence for database ownership, namespace/IAM posture, closed outputs, and readback | No provider mutation; real reconciliation remains later |
| 3. Shared Edge enforcement | Deterministic AP-EVAL-M9-07 runtime evidence for lookup, admission combinations, minimized assertions, and fail-closed behavior | No deployment or Live claim |
| 4. Member lifecycle operations | Deterministic AP-EVAL-M9-03 and AP-EVAL-M9-07 evidence for bootstrap, lifecycle authorization, idempotency, conflict, privacy, diagnostics, and readback | No real member mutation |
| 5. Version 2 application handoffs | Deterministic AP-EVAL-M9-06 and AP-EVAL-M9-07 evidence for bundles, intents, fixtures, registration, and application boundaries | No real application or platform mutation |
| 6. Operator handoff reconciliation | Governance and documentation evidence that records implemented behavior, limits, commands, and the final qualification procedure | No external operation |
| 7. Candidate qualification readiness | Deterministic qualification-support evidence in its pull request; after merge, applicable AP-EVAL-M9 Live evidence for the exact clean pushed integration revision, including migration, member lifecycle, admission, rollback, privacy, and restored baseline | Owner-invoked Candidate Source staging operations only after the Slice 7 pull request merges |

Each implementation slice updates the design, threat controls, evaluation wording, existing
component documentation, and operator documentation made concrete by that slice. When an owning
component has no documentation, follow `AGENTS.md` and ask the owner before adding a full
current-state component guide. Exact private fields, provider IAM realization, runtime limitations,
and command diagnostics must be documented with the implementation and tests that establish them,
not guessed in an earlier governance slice. After Slice 7 merges, Candidate Source evidence is
bound to the exact integration revision and the branch is frozen. A defect fix or documentation
change requires another slice pull request and a complete qualification rerun. W11 is the first
gate that can qualify the final merged Accepted Source revision.

Each slice runs focused deterministic tests for its changed seam and the complete credential-free
`make check` gate before its pull-request handoff. Before W10 may advance to W11:

1. Version 1 inputs migrate deterministically and cannot activate mixed or member-carrying Version
   2 output.
2. Directory infrastructure and IAM pass mocked plans, ownership policy, closed-output, and readback
   tests without member data in Terraform.
3. Runtime tests cover public `none`, public `optional`, authenticated, restricted active/inactive,
   directory failure, assertion minimization, audience isolation, header stripping, and independent
   Feature Entitlements.
4. Operator tests cover remote-empty bootstrap, non-empty refusal, Cloud Operator/Visitor
   separation, browser decline/failure, idempotency, stale predecessor, suspension, reactivation,
   removal, redaction, and interruption.
5. Handoff and fixture tests cover every valid and invalid Admission Mode/Identity Delivery
   combination and prove no bundle or generation contains member records.
6. `make check` passes credential-free, deterministic, network-free, and non-mutating.
7. Candidate Source staging qualification passes for the exact revision and restores the reviewed
   owner-only baseline. No member identity, assertion, browser state, raw provider response, state,
   or saved plan enters Git or public evidence.

## Slice and W10 completion definition

Each slice pull request is ready for review only when its named outcome is complete, its public
contracts and repository consumers remain consistent, focused tests and `make check` pass, and no
later-slice behavior has entered the branch. W10 is ready to advance to W11 only when:

- all seven functional-slice pull requests are implemented and merged in order to
  `feat/platform-member-directory`, or the owner has first approved and documented an explicit
  replacement slice map;
- every public contract and repository consumer moves together to Version 2;
- the existing operator lifecycle remains linear and understandable without a generic orchestration
  framework;
- Candidate Source qualification records every mandatory result and limitation for the exact
  clean pushed integration revision after all slice pull requests merge;
- the owner-only member baseline is restored after qualification;
- `make check` passes with exact results reported; and
- documentation truthfully distinguishes implementation, Candidate Source qualification, the W11
  Accepted Source operation, W12 production readiness, and later Application Adoption.

After those conditions pass, freeze the integration revision and open one cumulative pull request
from `feat/platform-member-directory` to `main`. A merge records completed W10 repository work but
does not transfer Candidate Source evidence to the resulting Accepted Source revision; W11 still
owns that deployment and qualification.
