# App Platform AP-M9-W12 real-application staging adoption

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the staging platform and cross-project fixtures have qualified from
Accepted Source and the documentation sequence that makes AP-M9-W12 next has merged to protected
`main`. The accepted platform/fixture result is bound to
`b43333756b509d0f35cb82938a13f6abc459f7c4`. It does not qualify a real application, authorize
platform destruction, or authorize production work.

Read `AGENTS.md`, follow the complete order in `docs/README.md`, and read:

- `docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md`;
- `docs/plans/ap_m9/w12_real_application_staging_adoption.md`;
- `docs/runbooks/application_adoption.md`;
- `docs/runbooks/environment_lifecycle.md`;
- `docs/05_evaluation_strategy.md`; and
- `docs/06_threat_model.md`.

State the AP-M9-W12 platform slice and its authority: AP-PR-001 through AP-PR-012; AP-QR-001
through AP-QR-009; ADR-001 through ADR-015 and ADR-017; AP-EVAL-M9-02, AP-EVAL-M9-06,
AP-EVAL-M9-07, and AP-EVAL-M9-10; and AP-TM-001 through AP-TM-014.

Before editing, inspect the working tree, branch, remotes, and exact relationship to `origin/main`.
For Apps Platform Slices 1 through 5, start a functionality-oriented branch from the latest clean
`feat/real-application-staging-adoption` integration branch and target that integration branch.
Require the integration branch to retain exact clean `main` ancestry. Report a mismatch and stop.
Do not pull, reset, switch branches, commit, push, change repository settings, invoke an
authenticated provider command, or mutate staging without the applicable owner direction.

Keep the platform work application-neutral until the Platform Owner names one application and the
Application Owner confirms matching adoption authority in that application's repository. A likely
application or discussion history is not authority. Do not import another repository's
requirements, credentials, state, plans, or implementation into Apps Platform.

The first implementation slice replaced the fixture-only Cloud Run target-readback assumption
with environment-derived, validated target posture. For the selected staging profile, it accepts
exactly `environment=qualification` candidates and `environment=staging` releases for both fixture
and real application projects; project ownership must not select the label. Reject missing or
other labels with the stable blocker. Treat either valid label as posture rather than evidence, and
require real-application Candidate Qualification before Accepted Source staging release
qualification. Trace the expectation through provider readback, handoff validation, tests,
operator messages, and documentation. Preserve exact application-project, Shared VPC, ingress,
edge-caller IAM, audience, readiness, and state-ownership checks. Add no generic
`application-deploy` or `application-destroy` command.

The second slice implements the closed Version 3 Platform Integration Bundle, complete
Application Attachment Bundle, and registration-intent schemas, canonical vectors, compatibility
loading, relationship validation, and deterministic tests. Preserve every Version 2 fixture
consumer. Require one root target and a root intent mounted at `/`. Add optional
`additional_attachments` and `additional_attachment_bindings` attributes containing at most fifteen
entries, canonical additional-ID ordering, and exact equality of the optional identifier sets.
Reject mixed versions, root-ID reuse, one optional attribute without the other, duplicate or
ambiguous mounts, stale relationships, and partial sets. Prove omission of both optional attributes
is a valid root-only Version 3 handoff.

The third slice validates and reads back every target independently, aggregates only redacted
ordered failures, projects a fully valid Version 3 handoff into the existing Version 2
multi-attachment Application Registration, and activates only one complete generation. It proves
one target failure causes no publication, traffic change, or partial activation; preserves
longest-segment routing, full-set update, predecessor retention, application-wide detachment, and
unrelated registrations; and reads no Application State.

The next, fourth platform slice must keep all three existing fixture deployments and Version 2 handoffs
unchanged and add `fixture-multi-attachment` as a fourth application. Use authenticated admission,
required Identity Delivery, unlisted catalogue visibility, and one independent Application State
root. Return its frontend Cloud Run service as the required `web` attachment at `/` and its
distinct dummy API Cloud Run service as the optional `api` attachment at `/api` in one complete
Version 3 family. Extend fixture handoff, status, destruction, component documentation, fakes, and
tests without creating a second application or state root for the API target.

The fifth platform slice must add `fixture-qualify` as a fixture-scoped interface separate from
`platform-qualify`. Bind its result to the exact readable Accepted Source platform qualification,
fixture source, complete handoff, both targets, and active Registration Generation. Prove the
authenticated root and `/api` verify the same application identity, `/apix` remains on the root,
direct origins are denied, and either target's invalid or unavailable candidate preserves the prior
complete generation with no publication, fallback, traffic change, or partial activation. Store
separate least-data fixture evidence and status; do not rerun or overwrite platform qualification,
exercise member lifecycle, or claim platform-wide rollback.

Before the cross-owner operation, require all of the following:

1. each Apps Platform environment-label, Version 3 contract, atomic multi-target registration,
   fourth-fixture, and fixture-scoped qualification slice is merged and passes `make check`;
2. the named application repository records its accepted staging adoption, rollback, state,
   identity, and evidence authority;
3. both owners agree on the environment, application identifier, admission mode, Identity
   Delivery, catalogue visibility, route intent, application project, exact platform source
   revision, and active Registration Generation;
4. the platform remains qualified and its project connection/readiness checks pass;
5. the separate fourth-fixture qualification passes against that exact platform result without
   replacing it; and
6. each repository retains authority only for its own resources and private evidence.

Then follow the application-adoption runbook in order: connect or read back the application
project; run `application-handoff-check`; produce and privately inspect the Version 3 Platform
Integration Bundle; let the Application Owner deploy every target through the application's own
workflow and state; receive the Version 3 complete Application Attachment Bundle and registration
intent; validate every target and register one complete Version 2 successor generation; and
qualify every mount, longest-match routing, admission, Identity Delivery, application
authorization, direct-origin denial, target failure isolation, rollback, and ownership boundaries.

Record only least-data evidence with the exact platform revision, application revision, active
generation and digest, and bundle relationship. Leave the selected real application active for
AP-M9-W13 unless its owner explicitly directs otherwise. Do not perform platform destruction,
production preparation or mutation, ownership transfer, DNS cutover, or another application's
adoption in W12.
