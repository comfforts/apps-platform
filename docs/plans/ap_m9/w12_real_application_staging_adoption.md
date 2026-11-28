# AP-M9-W12 · First real-application staging adoption qualification

Version 0.8 | Status: in progress after Accepted Source staging platform and fixture qualification
completed at `b43333756b509d0f35cb82938a13f6abc459f7c4`; Slices 1–5 implement target-stage validation,
ADR-017 Version 3 contracts, atomic multi-target registration projection, and the fourth fixture
application plus its separate qualification interface; no fourth-fixture Candidate or Accepted
qualification has run, later slices remain planned, no real application is selected, and no
external operation is authorized by this plan

Requirements: AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009

Decisions: ADR-001 through ADR-015; ADR-017

Evaluation: AP-EVAL-M9-02, AP-EVAL-M9-06, AP-EVAL-M9-07, AP-EVAL-M9-10

Threats: AP-TM-001 through AP-TM-014

## Delivery outcome

AP-M9-W12 qualifies one named, independently owned application on the already qualified staging
Platform Environment. The application consumes one Version 3 Platform Integration Bundle, deploys
and reads back one required root target plus zero through fifteen optional additional targets
through its own repository, returns one complete Version 3 Application Attachment Bundle and one
complete Version 3 registration intent, and is registered through one complete immutable Version
2 Registration Generation. The handoff and generation versions are independent interfaces:
Version 3 represents the optional plural cross-owner exchange, while the existing Version 2
Application Registration already represents multiple attachments.

Before that real-application handoff, W12 adds and separately qualifies one fourth
`fixture-multi-attachment` application. It uses authenticated admission, required Identity
Delivery, unlisted catalogue visibility, a frontend root Cloud Run service at `/`, and a distinct
dummy API Cloud Run service at `/api`. The fixture result is separate from `platform-qualify` and
does not change the existing three fixtures or their Accepted Source evidence.

A frontend/backend application remains one Registered Application. A representative shape uses
the required root target as the `web` attachment at mount `/` and adds an optional `api` attachment
at mount `/api`; longest segment-bounded mount selection sends the more specific subpath to the
backend. The selected application owns the actual identifiers and mounts. Apps Platform must not
hard-code Finance Assistant names, services, or routes.

The resulting evidence proves only that named application's staging adoption against the named
platform revision, complete attachment set, and environment. It does not make Apps Platform the
application's deployer, state owner, user store, feature-authorization service, or migration
authority. It does not qualify a second application, production, platform destruction, or
application destruction.

The real application follows two staging gates. Its Candidate Source targets first carry
`environment=qualification` and must pass revision-bound Candidate Qualification before merge.
After that exact candidate is accepted, the Application Owner reconciles the release targets with
`environment=staging`, and the Accepted Source adoption gate repeats the complete target and route
qualification. Fixture and real projects may use either label in the corresponding lifecycle
stage; project identity never selects the label. A label is provider posture only and cannot stand
in for either evidence record.

## Selection and joint-authority gate

This plan is application-neutral. Finance Assistant is a likely candidate, but discussion history
does not select it. Before application-specific work begins, record all of the following:

1. the Platform Owner names the application, staging application project, stable `application_id`,
   route, Admission Mode, Identity Delivery, catalogue visibility, required root attachment ID,
   and any additional attachment IDs and mount paths;
2. the application repository accepts its own adoption requirements, architecture, implementation,
   state, deployment, rollback, and evidence plan, including every returned target;
3. both repositories name the Version 3 application-handoff family and the existing Version 2
   registration-generation projection;
4. every attachment uses the same application project, region, Shared VPC connection, owner,
   edge-caller identity, Admission Mode, Identity Delivery, and application audience;
5. the application remains the sole owner of its runtimes, images, secrets, data, Terraform state,
   Application Principal mapping, permissions, and destruction; and
6. the platform remains the sole owner of the Shared VPC connection, Platform Integration Bundle,
   registration validation, Shared Edge route, admission, and Platform State; and
7. the separate fourth-fixture qualification remains readable and bound to the exact Accepted
   Source platform qualification and active Registration Generation used as adoption prerequisites.

No platform document can authorize the application repository, and no application script can
claim platform qualification or mutate Platform State. An application that needs per-attachment
identity, project, region, or network policy is outside W12 and requires new authority.

## Approved handoff correction

ADR-017 corrects the shallow Version 2 lifecycle seam without changing the qualified core
registration meaning:

- one Version 3 Platform Integration Bundle describes the application-level environment, project,
  network, caller, identity, source, and generation bindings and declares one required root plus at
  most fifteen optional additional attachments;
- one Version 3 Application Attachment Bundle preserves the required singular root `target` and
  adds an optional canonical `additional_attachments` array sorted by stable `attachment_id`; each
  additional entry identifies one exact application-owned Cloud Run target and its returned posture;
- one Version 3 registration intent preserves the required root `attachment_id`, `mount_path`, and
  `forwarding_mode`, requires that mount to be `/`, and adds an optional canonical
  `additional_attachment_bindings` array sorted by `attachment_id`;
- the two optional arrays must both be absent or contain the exact same unique identifier set, the
  root ID must be absent from both, mounts must be unique and unambiguous, and total cardinality
  must remain within the existing 1–16 core limit;
- `platform-register` validates the complete relationship and independently reads back every target
  before it projects the set into the existing Version 2 Application Registration; and
- publication and activation are atomic: one target failure, stale relationship, or posture
  mismatch activates none of the application change and preserves the reviewed predecessor.

Version 2 handoff documents remain readable for the three already qualified single-target
fixtures. One invocation accepts either one complete Version 2 family or one complete Version 3
family; it rejects mixed versions. A root-only Version 3 family is valid when both optional arrays
are absent. Version 3 is mandatory when the application returns an additional attachment. The
operator now accepts an explicitly selected complete Version 3 family, validates and reads every
target, and projects only a fully valid set into one Version 2 generation. Merge and runtime
qualification remain separate evidence states.

An update always returns the required root target. When additional attachments are present, it
returns the complete optional target and binding arrays, including unchanged entries. Removing or
replacing an additional target is an explicit full-optional-set registration change; an absent
optional attribute means a deliberate root-only application, not permission to activate a partial
document. Replaced targets remain available for the accepted rollback-retention window.
`platform-detach` remains an application-wide lifecycle and does not become a per-attachment
operation.

## Integration branch and ordered functional slices

W12 uses one bounded integration-branch exception for the Apps Platform governance and
implementation slices. Create `feat/real-application-staging-adoption` from updated clean `main`
only while local `main`, `origin/main`, and the selected base revision are exact. The initial
`docs/multi-attachment-adoption-handoff` governance slice starts from that clean integration base
and targets the integration branch. Slices 1 through 5 then start from and target the latest clean
`feat/real-application-staging-adoption`, merge in order, and become the base for their successor.
No partial W12 platform implementation targets `main`.

Each slice is independently reviewable and passes focused tests plus `make check`. After Slices 1
through 5 merge, Candidate-qualify the exact complete integration revision, freeze it, and open one
cumulative pull request from `feat/real-application-staging-adoption` to `main`. Any later tracked
change invalidates that qualification and requires the documented Candidate gate to run again.
After the cumulative merge, repeat the fourth-fixture deployment and fixture-scoped qualification
from clean Accepted Source before the application-owned Slice 6 or joint Slice 7 operation begins.
Slice 6 remains in the selected application's repository. Slice 7 starts from updated clean `main`
after both repositories have merged their implementation and is not merged back into the already
closed integration branch. Five to eight coherent commits is a scope signal for each implementation
slice, not a requirement to split an atomic change artificially.

### Slice 1 · Environment-derived real-target readiness

Suggested branch: `fix/real-application-target-readiness`

Pull-request target: `feat/real-application-staging-adoption`

Replace the fixture-only `environment=qualification` Cloud Run label assumption with a closed
target-stage policy derived from the selected profile and handoff. The staging profile accepts
exactly `environment=qualification` for a candidate target or `environment=staging` for a staging
release target. Both values are valid for fixture and real application projects; project ownership
must not select the label. A missing or other environment label fails with the stable target-label
blocker, and neither accepted value proves that its corresponding evidence gate passed. Trace
target readback, registration validation, status, operator diagnostics, fakes, tests, and
documentation together. Preserve exact application project, region, Shared VPC, internal ingress,
Direct VPC egress, edge-caller viewer and invoker grants, application owner, audience, and readiness
checks. This slice changes no contract cardinality and invokes no provider operation.

### Slice 2 · Version 3 complete attachment-set contracts

Suggested branch: `feat/complete-attachment-set-contracts`

Pull-request target: `feat/real-application-staging-adoption`

Implementation status: repository behavior implemented on the Slice 2 branch; merge and
qualification remain separate states.

Add the closed Version 3 Platform Integration Bundle, Application Attachment Bundle, and
registration-intent schemas, canonical vectors, compatibility loading, prohibited-data checks,
relationship validation, and deterministic Contract tests. Preserve the original Version 2
entry points and vectors. Prove a required root with no optional attributes and a required root
with fifteen additional attachments pass. Prove a missing root, sixteen additional attachments,
one optional array without the other, duplicate or mismatched additional IDs, reuse of the root ID,
non-root root mount, duplicate or ambiguous mounts, mixed handoff versions, non-canonical ordering,
secrets, and stale digests fail closed. This slice is inert and cannot publish, register, read a
provider, or activate a route.

### Slice 3 · Atomic multi-target registration adapter

Suggested branch: `feat/atomic-multi-target-registration`

Pull-request target: `feat/real-application-staging-adoption`

Implementation status: repository behavior implemented on the Slice 3 branch; merge and
qualification remain separate states.

Teach the application-neutral readiness, output, registration, status, and fake-provider modules
to consume a complete Version 3 family. Read the required root and every additional exact Cloud
Run target through the selected environment adapter, aggregate ordered violations without leaking
provider payloads, and project a valid set into the existing Version 2 Application Registration
and Compiled Shared Edge Configuration. Prove longest segment-bounded mount routing, complete-
generation preservation of other applications, all-or-nothing publication/activation, predecessor
rollback, full-set update, and app-wide detachment. Add no generic `application-deploy` or
`application-destroy` command and read no Application State.

### Slice 4 · Fourth multi-attachment fixture application

Suggested branch: `feat/multi-attachment-fixture`

Pull-request target: `feat/real-application-staging-adoption`

Implementation status: repository behavior implemented on the Slice 4 branch; merge, provider
operation, and qualification remain separate states.

Keep the existing `fixture-public`, `fixture-authenticated`, and `fixture-restricted` deployments,
Version 2 handoffs, and evidence unchanged. Add `fixture-multi-attachment` as a fourth application
with route `/fixture-multi-attachment`, authenticated admission, required Identity Delivery, and
unlisted catalogue visibility. Its required `web` attachment owns the
`fixture-multi-attachment-web` frontend Cloud Run service at `/`; its optional `api` attachment
owns the distinct `fixture-multi-attachment-api` dummy backend Cloud Run service at `/api`.

One new Terraform root at `infrastructure/terraform/fixtures/fixture-multi-attachment` owns both
services in the existing dedicated fixture project and uses the independent
`fixtures/fixture-multi-attachment` state prefix. Extend the fixture image or add a fixture-owned
image only as needed to produce target-specific safe markers and independently verify the same
application audience in both services. Extend handoff, status, destruction, fakes, component
documentation, and deterministic tests together. Emit one complete Version 3 family; do not add a
second application, state root, catalogue entry, audience, or lifecycle for the API target. This
slice implements no provider operation and produces no qualification evidence.

### Slice 5 · Fixture-scoped multi-attachment qualification

Suggested branch: `feat/fixture-scoped-qualification`

Pull-request target: `feat/real-application-staging-adoption`

Add the shallow `fixture-qualify` target, with `ENVIRONMENT=staging` and
`APPLICATION_ID=fixture-multi-attachment`, over one fixture-scoped qualification module.
Require exact readback of the Accepted Source platform qualification, fourth-fixture source,
Version 3 bundle family, both targets, and active Version 2 Registration Generation. Store its
least-data result and status separately from the platform qualification record. The command must
not invoke `platform-qualify`, change platform qualification status, rerun the three-fixture suite,
exercise Platform Member lifecycle, or claim platform-wide rollback.

Deterministically test the interface with injected provider, browser, route, and evidence adapters.
After the slice merges into the integration branch, a separately authorized Candidate Source
fixture operation deploys and registers the fourth fixture, then proves authenticated login and
verified identity at the root and `/api`, target-specific markers, `/apix` selection of the root,
direct-origin denial for both services, and rejection of a candidate whose root or API target is
invalid or unavailable without publication, traffic change, fallback, or partial activation.
Freeze that exact passing integration revision before the cumulative pull request. After it merges
to `main`, rerun the same operation from clean Accepted Source and require the accepted result
before Slice 6. Either result qualifies only the plural fixture interface under its named Source
Authority; it does not qualify Finance Assistant or any other real application.

### Slice 6 · Selected application-owned adoption implementation

This slice occurs only in the selected application's repository under its own branch convention
and accepted authority. The Application Owner consumes the exact Version 3 integration bundle,
deploys or reconciles every target from its own state, verifies platform assertions when enabled,
tests application permissions, and emits the canonical complete attachment bundle and registration
intent. For a frontend/backend application, both services must independently satisfy the required
network, ingress, IAM, label, readiness, and audience posture. Apps Platform does not implement or
execute this application lifecycle.

Before this slice merges, a separately authorized joint Candidate Source operation uses
`environment=qualification` on every selected target, registers the complete candidate set,
executes the declared real-application checks, records revision-bound Candidate Qualification in
both repositories, and restores the reviewed predecessor. Failure blocks the application merge.
The target label alone is never candidate evidence.

### Slice 7 · Joint staging adoption and evidence

Suggested platform branch: `evidence/multi-attachment-staging-adoption`

Pull-request target: updated clean `main` after the cumulative integration pull request merges

Only after Slices 1 through 6 merge, the separate fourth-fixture qualification and real-application
Candidate Qualification pass, and both owners deliberately authorize the operation, execute the
Accepted Source release journey below. Record the least-data AP-EVAL-M9-10 release result in each
repository under its own evidence rules. A discovered software defect returns to a reviewed fix
slice and requires the candidate and release gates required by the changed revision to rerun; the
evidence slice does not absorb implementation changes or broaden authority.

## Ordered cross-owner journey

After the platform implementation and the candidate-qualified application implementation merge
through their respective authorities and the separate fourth-fixture result remains current:

1. Read back the Accepted Source staging qualification, the separately stored
   `fixture-multi-attachment` qualification, active platform source revision, Version 2
   Registration Generation, owner-only member baseline, and application-project connection.
2. Connect the existing application project once with `platform-connect-project`; do not create an
   application runtime or route in that step.
3. Run `application-handoff-check` with the exact application and complete attachment intent and
   resolve every platform, project, network, IAM, service, source, generation, identity, and
   attachment-bound blocker.
4. Run `platform-outputs` with the same values and transfer the exact canonical Version 3 Platform
   Integration Bundle through the application repository's approved private handoff.
5. The Application Owner deploys or reconciles the Accepted Source application targets and
   Application State with `environment=staging`, independently verifies Platform Identity where
   enabled, tests application permissions, and returns the required root target plus any complete
   optional additional target and binding arrays in the exact canonical Version 3 Application
   Attachment Bundle and registration intent. A fixture or real project may carry this release
   label; the prior Candidate Qualification, not project identity, authorizes this phase.
6. The Platform Operator inspects the three-document family, runs `platform-register`, and verifies
   that every target readback passed before the new complete Version 2 Registration Generation
   became active without changing another application.
7. Exercise every attachment mount, longest-match selection, catalogue policy, anonymous or login
   behavior, admission, assertion verification, direct-origin denial, application-owned permission
   decisions, target-specific failure isolation, complete-generation rollback, and restoration
   required by the application adoption plan.
8. Record least-data, revision-scoped AP-EVAL-M9-10 evidence in both repositories under their own
   evidence rules. Leave the real application active for AP-M9-W13 unless its owner explicitly
   selects a different safe handoff state.

## Verification strategy

The repository-only slices must deterministically verify:

- unchanged Version 1 and Version 2 compatibility behavior and vectors;
- Version 3 required-root, optional-additional schema, canonicalization, relationship, cardinality,
  exact-optional-ID-set, root-ID exclusion, root-mount, and mixed-version rejection;
- the closed, project-independent staging target stages: fixture and real
  `environment=qualification` candidates, fixture and real `environment=staging` releases, and
  deterministic rejection of missing or other labels;
- source-bound Candidate Qualification before the selected real application's Accepted Source
  staging release qualification, with neither target label accepted as evidence by itself;
- independent provider posture validation for every target and no activation after any target
  fails;
- projection of one root-only or root-plus-optionals Version 3 handoff into one valid Version 2
  multi-attachment registration and generation;
- `/` plus a more-specific mount such as `/api`, including segment-boundary and closed-route cases;
- unchanged validity and behavior for the three existing fixtures;
- the fourth fixture's authenticated `web` root plus distinct dummy `api` backend, one Application
  State root, complete Version 3 handoff, `/api` longest-match selection, and `/apix` root selection;
- separate `fixture-qualify` evidence and status that cannot overwrite or broaden
  `platform-qualify`;
- full-set replacement, retained predecessor, app-wide detach, rollback, and preservation of
  unrelated registrations; and
- credential-free, network-free, non-mutating default verification.

The Live adoption gate then verifies the exact selected services, route behavior, identity policy,
ownership, direct-origin denial, failure isolation, rollback, and restoration. A single-target
fixture or mocked multi-target test cannot substitute for the selected application's required Live
evidence.

## Completion evidence

AP-M9-W12 completes only when:

- W11 Accepted Source staging platform qualification remains readable and current for the operated
  platform revision;
- the separately stored `fixture-multi-attachment` qualification passes against that exact
  platform result, its exact fixture source and complete Version 3 handoff, both target-reference
  digests, and the active Registration Generation without rewriting platform qualification status;
- the selected application repository records its own accepted adoption authority and exact
  evaluated revision;
- the selected real application's exact Candidate Source revision passed Candidate Qualification
  with `environment=qualification` targets before merge, and the Accepted Source release repeats
  the complete gate with `environment=staging` targets;
- the platform's environment-derived target validation, Version 3 complete-set implementation,
  focused deterministic tests, and full credential-free `make check` pass;
- the application project connection, the required root and every additional target's service
  posture, Version 3 bundle relationships, Version 2 registration projection, and active complete
  generation read back exactly;
- every declared mount, applicable login or membership behavior, application-side assertion
  verification, direct-origin denial, target failure isolation, application-owned permission
  check, rollback, and restoration pass in staging;
- failure of any one target is shown to preserve the prior complete generation;
- neither repository claims ownership of the other's state, secrets, deployment, or evidence; and
- AP-EVAL-M9-10 reports the exact platform revision, application revision, attachment IDs and
  target-reference digests, active generation and bundle digests, results, failures, warnings,
  skips, limitations, and unavailable production and destruction claims without prohibited data.

AP-M9-W13 begins only after this result. It owns application-wide detachment, retained
real-application state and targets, fixture cleanup, platform destruction and redeployment,
complete-set reattachment, and requalification.
