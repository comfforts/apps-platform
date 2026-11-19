# App Platform AP-M9-W7 application integration lifecycle handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W6 interactive-deployment pull request has merged, local
`main` is current and clean, and the owner approves AP-M9-W7. Create branch
`feat/ap-m9-application-integration-lifecycle`. Inspect the branch, working tree, remotes, and
relationship to `origin/main`; preserve unrelated changes. Do not pull, reset, commit, push, or
perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W7; AP-PR-001 through AP-PR-007, AP-PR-009, AP-PR-011, and AP-PR-012;
AP-QR-001 through AP-QR-009; ADR-001 through ADR-006, ADR-008, ADR-012, and ADR-013; AP-EVAL-M9-01 through
AP-EVAL-M9-06; and AP-TM-001 through AP-TM-014. Confirm AP-M9-W6 is merged before modifying
anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define generic platform
behavior, bundle projection, registration, route lifecycle, deployment, or production cutover.

Implement only the application integration lifecycle repository slice:

1. Implement `platform-outputs` over the existing Platform Integration Bundle contract. Generate
   least-data, non-secret projections for Public, Authenticated, and Restricted applications,
   bound to the exact environment, platform revision, qualification state, route intent, and bundle
   digest. Include an OAuth client identifier only when the consumer interface needs it; never
   include an OAuth client secret, signing authority, restricted-member set, provider payload, or
   backend access.
2. Implement provider target and ownership readback plus Application Attachment Bundle validation.
   An attachment must bind the owning application, bundle digest, immutable target, ingress posture,
   audience, caller grant, and current platform state without reading Application State or assuming
   its deployment succeeded.
3. Implement `platform-register` as complete-generation compilation and activation. Every update
   publishes one immutable whole Registration Generation, verifies create-only publication and
   readback, and changes the active generation only after exact typed confirmation. Never patch a
   live registration in place or construct generation inputs from Terraform remote state.
4. Implement reversible `platform-detach`, replacement attachment/reactivation, and terminal
   `platform-retire`. A detached route remains reserved, is absent from the catalogue, invokes no
   target, and returns the generic temporary-unavailability result. A retired route remains
   reserved and returns the generic permanent-removal result. Unknown routes remain closed. No
   platform operation destroys Application State.
5. Preserve append-only lifecycle/journal binding, exact source and environment checks,
   stop-on-discrepancy behavior, production refusal, and the W6 external-action gate. Add non-fake
   boundaries only behind injected interfaces; repository tests must use deterministic fakes and
   perform no provider, network, browser, state, or credential action.
6. Add deterministic contract, command, transcript, generation, attachment, and route-lifecycle
   tests for Public, Authenticated, Restricted, stale/mismatched bundles, invalid ownership,
   replacement, detach, redeploy/reactivate, retirement, unknown routes, interruption, resume,
   conflict, and prohibited material.
7. Update documentation, tests, and the AP-M9-W8 handoff. Qualification, live fixture deployment,
   rollback, destruction, evidence collection, Finance Assistant adoption, and production cutover
   remain later packages.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not authenticate or run a real Terraform/backend/provider/image/OAuth/Secret Manager/DNS/TLS
operation. Do not deploy an application, publish a real generation, register or detach a live
application, mutate a credential, state, cloud resource, repository setting, Finance Assistant,
`apps.comfforts.com`, or the inactive Finance integration package. Do not claim Live evidence or
Application Adoption. Do not change repository settings.

Use small coherent commits. Do not commit generated bundles containing private operator values,
execution journals, credentials, state, saved plans, provider payloads, browser state, application
data, restricted membership, or manual-checkpoint artifacts.
