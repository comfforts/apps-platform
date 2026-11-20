# App Platform AP-M9-W9 Fixture Application deployment lifecycle handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W8 qualification-and-safe-destruction pull request has merged,
local `main` is current and clean, and the owner approves AP-M9-W9. Create branch
`feat/ap-m9-fixture-application-deployment`. Inspect the branch, working tree, remotes, and
relationship to `origin/main`; preserve unrelated changes. Do not pull, reset, commit, push, or
perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W9; AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009; ADR-001 through ADR-013;
AP-EVAL-M9-01 through AP-EVAL-M9-09; and AP-TM-001 through AP-TM-014. Confirm AP-M9-W8 is merged
before modifying anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define generic platform
behavior or fixture, application, deployment, state, qualification, destruction, or production
behavior.

Implement only the repository-side Fixture Application deployment lifecycle:

1. First reconcile governance so ordinary reversible staging creation or update is authorized by
   deliberate invocation of the named command plus same-process specification and plan
   confirmations. Retain separate approval for destruction, purge, ownership transfer, production
   cutover, and scope expansion. Move the first staging operation to AP-M9-W10 and production
   readiness to AP-M9-W11.
2. Add shallow `fixture-deploy`, `fixture-status`, and `fixture-destroy` targets over the existing
   deep Python lifecycle module. A fresh operator must not hand-author Terraform variables,
   integration bundles, attachment bundles, registration intent, or provider inventory.
3. Build one immutable, source-bound, non-root Fixture Application image through the existing pinned
   and allow-listed build boundary. Use the same digest for all three synthetic applications and
   reject a mutable image reference or source mismatch.
4. Generate public, authenticated, and restricted Platform Integration Bundles, derive exact
   application inputs, and plan/apply the three existing fixture roots sequentially in independent
   Application State lineages. Every plan is fresh, policy-checked, displayed, confirmed with
   `y/N`, applied as the same artifact, and read back before the next root begins.
5. Generate each Application Attachment Bundle from exact Terraform/provider readback, validate
   owner, ingress, caller grant, audience, and bundle digest, then publish and activate one complete
   Registration Generation. Preserve platform/application state separation throughout.
6. Make `fixture-status` strictly read-only. Make `fixture-destroy` detach before destruction,
   require fixture-specific typed confirmation, reread ownership and active-generation state after
   confirmation, destroy only selected Fixture Application State, and support deterministic
   redeployment/reactivation without releasing its identifier or route.
7. Complete the exact live qualification and safe-destruction adapter wiring required before the
   AP-M9-W10 staging operation, while invoking none of it in this repository slice. No target may
   use ambient credentials, shell interpolation, mutable plans/images, automatic cleanup, or state
   access across an ownership boundary.
8. Add deterministic command, transcript, plan, readback, bundle, registration, status,
   interruption, resume, cancellation, conflict, stale-input, partial-failure, and destruction tests.
   A test must exercise the complete fixture journey through injected fakes; static Terraform or a
   process-local server alone is not deployment-lifecycle evidence.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not authenticate or run a real Terraform/backend/provider/image/OAuth/Secret Manager/DNS/TLS
operation. Do not deploy or destroy a platform or application, publish a real image or generation,
collect Live evidence, mutate a credential, state, cloud resource, repository setting, Finance
Assistant, `apps.comfforts.com`, or the inactive Finance integration package. AP-M9-W10 is the first
real staging operation. Do not claim Application Adoption or production readiness.

Use small coherent commits. Do not commit credentials, state, saved plans, provider payloads,
browser state, restricted membership, application data, raw traffic, recovery material, private
evidence, or manual-checkpoint artifacts.
