# App Platform AP-M9-W6 interactive platform deployment handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W5 deployable-Terraform pull request has merged, local `main`
is current and clean, and the owner approves AP-M9-W6. Create branch
`feat/ap-m9-interactive-platform-deployment`. Inspect the branch, working tree, remotes, and
relationship to `origin/main`; preserve unrelated changes. Do not pull, reset, commit, push, or
perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W6; AP-PR-001 through AP-PR-005 and AP-PR-010; AP-QR-001 through AP-QR-009; ADR-001,
ADR-004 through ADR-011, and ADR-013; AP-EVAL-M9-01 through AP-EVAL-M9-05; and AP-TM-001 through
AP-TM-014. Confirm AP-M9-W5 is merged before modifying anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define generic platform
behavior, Terraform behavior, resource ownership, deployment authority, or a production cutover.

Implement only the interactive platform-deployment repository slice:

1. Compose the W4 lifecycle core and W5 Terraform/backend/identity/plan seams into one staged
   deployment engine for interactive use through `platform-deploy`, without changing
   `platform-prepare` or `platform-status` behavior.
2. Implement preflight; separately scoped backend and operation-identity bootstrap; foundation;
   immutable Shared Edge image publication; the Google OAuth branding/client and direct Secret
   Manager-entry checkpoint; Shared Edge/load-balancer/address creation; the exact Squarespace DNS
   checkpoint; authoritative and recursive DNS verification; post-DNS certificate/HTTPS readiness;
   final state/provider/ownership readback; and status reconciliation.
3. Keep one local process active across every human checkpoint. Display the exact approved values,
   wait for Enter, verify every readable fact, distinguish operator attestation from provider
   verification, and continue. Rerunning is interruption recovery only. Never accept an OAuth
   client secret, credential, token, or other secret payload in a terminal prompt.
4. For every Terraform mutation, create a fresh plan observation in the same execution, apply W5
   canonical policy, display the redacted exact digest and resource/action summary, require the
   named typed confirmation, apply only that saved in-memory/file-private exact plan, then perform
   state and provider readback. A mismatch stops without unlock, state push, import, rollback,
   cleanup, or scope broadening.
5. Add non-fake command adapters only behind the existing injected boundaries and keep all command
   construction closed, argument-based, path-bounded, source-bound, environment-bound, and
   operation-identity-bound. No shell interpolation, ambient provider default, broad owner routine
   apply, service-account key, or persisted credential is permitted.
6. Add deterministic command fakes and transcript tests for first deployment, update, no-change,
   cancellation, manual checkpoint, bounded polling, partial failure, discrepancy, interruption,
   and resume. Prove a closed stage is never repeated and production still returns
   `OWNERSHIP_TRANSFER_REQUIRED` before any command.
7. Update documentation, tests, and the AP-M9-W7 handoff. `platform-outputs`, registration,
   detachment, retirement, qualification, destruction, and application bundle generation remain
   later packages unless needed only as explicit unavailable status.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not authenticate or run a real Terraform init, plan, apply, import, state, force-unlock, backend
migration, provider readback, image publication, browser action, OAuth mutation, Secret Manager
write, DNS lookup/change, certificate operation, or deployment. Do not
create or mutate a credential, identity, IAM binding, backend, Terraform state or saved plan,
provider resource, OAuth client, secret, DNS record, certificate, image, Live evidence, or
Application Adoption. Do not change repository settings, Finance Assistant, `apps.comfforts.com`,
or the inactive Finance integration package.

Use small coherent commits. Do not commit generated backend files, local operator state,
`.terraform/`, credentials, state, saved plans, provider payloads, authenticated artifacts, or
manual-checkpoint browser state.
