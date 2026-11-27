# AP-M9-W12 · First real-application staging adoption qualification

Status: planned; next AP-M9 work package after Accepted Source staging platform and fixture
qualification completed at `b43333756b509d0f35cb82938a13f6abc459f7c4`; no application is selected
and no external operation is authorized by this plan

Requirements: AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009

Decisions: ADR-001 through ADR-015

Evaluation: AP-EVAL-M9-10

Threats: AP-TM-001 through AP-TM-014

## Delivery outcome

AP-M9-W12 qualifies one named, independently owned application on the already qualified staging
Platform Environment. The application consumes a Version 2 Platform Integration Bundle, deploys
and reads back its own runtime and state through its own repository, returns one exact Application
Attachment Bundle and registration intent, and is registered through one complete immutable
Registration Generation. The resulting evidence proves only that named application's staging
adoption against the named platform revision and environment.

The work does not make Apps Platform the application's deployer, state owner, user store, feature-
authorization service, or migration authority. It does not qualify a second application,
production, platform destruction, or application destruction.

## Selection and joint-authority gate

This plan is application-neutral. Finance Assistant is a likely candidate, but discussion history
does not select it. Before application-specific work begins, record all of the following:

1. the Platform Owner names the application, staging application project, stable `application_id`,
   route, Admission Mode, Identity Delivery, and catalogue visibility;
2. the application repository accepts its own adoption requirements, architecture, implementation,
   state, deployment, rollback, and evidence plan;
3. both repositories name the same Version 2 contract family and cross-owner handoff;
4. the application remains the sole owner of its runtime, image, secrets, data, Terraform state,
   Application Principal mapping, permissions, and destruction; and
5. the platform remains the sole owner of the Shared VPC connection, Platform Integration Bundle,
   registration validation, Shared Edge route, admission, and Platform State.

No platform document can authorize the application repository, and no application script can
claim platform qualification or mutate Platform State.

## Platform readiness work

Before publishing a real-application bundle, replace the fixture-only target assumption documented
in the adoption runbook: provider target readback must validate the selected Platform Environment
instead of requiring the hardcoded `environment=qualification` fixture label. The correction must
remain closed and environment-derived, update every consumer and deterministic test together, and
must not weaken project, region, Shared VPC, ingress, IAM, audience, or owner-label checks.

Review the real application against the current Version 2 interfaces before adding another
abstraction. A concrete incompatibility may justify the smallest platform correction required for
this application-neutral handoff. It does not authorize a generic application deployer, a second
contract family, application-state access, production behavior, or unrelated backlog work.

## Ordered cross-owner journey

After the platform correction and the application-owned adoption implementation merge through
their respective authorities:

1. Read back the Accepted Source staging qualification, active platform source revision,
   Registration Generation, owner-only member baseline, and application-project connection.
2. Connect the existing application project once with `platform-connect-project`; do not create the
   application runtime or route in that step.
3. Run `application-handoff-check` with the exact proposed application and resolve every platform,
   project, network, IAM, service, source, generation, and identity blocker.
4. Run `platform-outputs` with the same values and transfer the exact canonical Version 2 Platform
   Integration Bundle through the application repository's approved private handoff.
5. The Application Owner deploys or reconciles the application runtime and Application State,
   independently verifies Platform Identity where enabled, tests application permissions, and
   returns the exact canonical Application Attachment Bundle and registration intent.
6. The Platform Operator inspects the three-document family, runs `platform-register`, and verifies
   the new complete generation without changing another application.
7. Exercise the selected route's catalogue policy, anonymous or login behavior, admission,
   assertion verification, direct-origin denial, application-owned permission decisions, failure
   isolation, status, and rollback path required by the application adoption plan.
8. Record least-data, revision-scoped AP-EVAL-M9-10 evidence in both repositories under their own
   evidence rules. Leave the real application active for AP-M9-W13 unless its owner explicitly
   selects a different safe handoff state.

The application repository supplies the application deploy, status, rollback, and destroy
commands. Apps Platform supplies no generic `application-deploy` or `application-destroy` target.

## Functional-slice boundary

Begin AP-M9-W12 from updated clean `main` only after this documentation pull request merges. The
first platform slice is the application-neutral target-readback correction on a functionality-
oriented branch such as `feat/real-application-target-readiness`. Keep any named application's
changes in that application's repository and branch convention. A later evidence slice may record
the joint staging result only after both implementations are merged and the exact operation passes.

If the selected application exposes a contract change, new lifecycle, ownership transfer, or work
approaching a ninth substantive commit, stop and create an additional reviewed functional slice.
Do not hide application-specific behavior in the platform correction.

## Completion evidence

AP-M9-W12 completes only when:

- W11 Accepted Source staging platform qualification remains readable and current for the operated
  platform revision;
- the selected application repository records its own accepted adoption authority and exact
  evaluated revision;
- the platform's environment-derived target validation and full credential-free `make check` pass;
- the application project connection, service posture, Version 2 bundle relationships, and active
  complete generation read back exactly;
- the route, applicable login/membership behavior, application-side assertion verification,
  direct-origin denial, and application-owned permission checks pass in staging;
- neither repository claims ownership of the other's state, secrets, deployment, or evidence; and
- AP-EVAL-M9-10 reports the exact platform revision, application revision, generation and bundle
  digests, results, failures, warnings, skips, limitations, and unavailable production and
  destruction claims without prohibited data.

AP-M9-W13 begins only after this result. It owns detachment, retained real-application state,
fixture cleanup, platform destruction/redeployment, reattachment, and requalification.
