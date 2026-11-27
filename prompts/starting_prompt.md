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
through AP-QR-009; ADR-001 through ADR-015; AP-EVAL-M9-10; and AP-TM-001 through AP-TM-014.

Before editing, inspect the working tree, branch, remotes, and exact relationship to `origin/main`.
Start from updated clean `main` on a functionality-oriented branch. Report a mismatch and stop.
Do not pull, reset, switch branches, commit, push, change repository settings, invoke an
authenticated provider command, or mutate staging without the applicable owner direction.

Keep the platform work application-neutral until the Platform Owner names one application and the
Application Owner confirms matching adoption authority in that application's repository. A likely
application or discussion history is not authority. Do not import another repository's
requirements, credentials, state, plans, or implementation into Apps Platform.

The first implementation slice must replace the fixture-only Cloud Run target-readback assumption
with environment-derived, validated target posture. Trace the current
`environment=qualification` expectation through provider readback, handoff validation, tests,
operator messages, and documentation. Preserve exact application-project, Shared VPC, ingress,
edge-caller IAM, audience, readiness, and state-ownership checks. Add no generic
`application-deploy` or `application-destroy` command.

Before the cross-owner operation, require all of the following:

1. the Apps Platform correction is merged and passes `make check`;
2. the named application repository records its accepted staging adoption, rollback, state,
   identity, and evidence authority;
3. both owners agree on the environment, application identifier, admission mode, Identity
   Delivery, catalogue visibility, route intent, application project, exact platform source
   revision, and active Registration Generation;
4. the platform remains qualified and its project connection/readiness checks pass; and
5. each repository retains authority only for its own resources and private evidence.

Then follow the application-adoption runbook in order: connect or read back the application
project; run `application-handoff-check`; produce and privately inspect the Version 2 Platform
Integration Bundle; let the Application Owner deploy through the application's own workflow and
state; receive the Version 2 Application Attachment Bundle and registration intent; register one
complete successor generation; and qualify the route, admission, Identity Delivery, application
authorization, direct-origin denial, failure isolation, rollback, and ownership boundaries.

Record only least-data evidence with the exact platform revision, application revision, active
generation and digest, and bundle relationship. Leave the selected real application active for
AP-M9-W13 unless its owner explicitly directs otherwise. Do not perform platform destruction,
production preparation or mutation, ownership transfer, DNS cutover, or another application's
adoption in W12.
