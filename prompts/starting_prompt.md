# App Platform AP-M9-W8 qualification and safe destruction handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W7 application-lifecycle pull request has merged, local
`main` is current and clean, and the owner approves AP-M9-W8. Create branch
`feat/ap-m9-qualification-safe-destruction`. Inspect the branch, working tree, remotes, and
relationship to `origin/main`; preserve unrelated changes. Do not pull, reset, commit, push, or
perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W8; AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009; ADR-001 through ADR-013;
AP-EVAL-M9-01 through AP-EVAL-M9-09; and AP-TM-001 through AP-TM-014. Confirm AP-M9-W7 is merged
before modifying anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define qualification,
destruction, evidence, application cleanup, deployment, or production cutover.

Implement only the qualification and safe-destruction repository slice:

1. Implement `platform-qualify` for the exact deployed environment, source revision, specification,
   execution journal, active Registration Generation, component revisions, and synthetic Fixture
   Application revisions. A stale, partial, unqualified, mismatched, or drifted input must fail
   closed rather than reuse an earlier result.
2. Exercise the public, authenticated, and restricted synthetic applications through the same
   integration and attachment lifecycle as every application. Keep each fixture in independent
   Application State and prove that platform actions neither read nor destroy that state.
3. Add a strict versioned, revision-bound, redacted qualification-evidence contract and prohibited-
   data scan. Record only allow-listed digests, coarse results, verified/operator-attested labels,
   limitations, failures, and final status; never retain credentials, secrets, assertions,
   sessions, restricted members, request/response bodies, provider payloads, state, or saved plans.
4. Cover DNS/TLS, catalogue, route and mount behavior, public/authenticated/restricted admission,
   OAuth/session/logout, signed assertion/JWKS verification, caller/IAM posture, direct-origin
   denial, cross-application and failure isolation, streaming and limits, detachment/reactivation,
   retirement, redaction, and truthful unavailable behavior. Deterministic repository tests use
   fakes and process-local loopback only.
5. Implement reviewed complete-generation rollback and failure injection. Rollback must activate an
   already reviewed immutable generation, preserve Application State, require exact confirmation,
   read back the active digest, and never silently reconstruct or patch provider configuration.
6. Implement `platform-destroy` from a separate digest-bound destructive specification. Refuse any
   active attachment or ownership mismatch; show exact platform-owned scope; require environment-
   specific typed confirmation; handle traffic, external DNS, certificate, OAuth, and cache/rollback
   checkpoints in safe order; stop truthfully on partial failure; and never target Application
   State. Retain state backends, recovery material, and evidence unless separately approved purge
   authority exists.
7. Complete the locally unarmed adapter construction only after every preflight, policy, readback,
   redaction, resume, qualification, rollback, and destruction guard is present. No command may use
   ambient credentials, broad owner authority, shell interpolation, mutable plans/images, automatic
   cleanup, or automatic destructive recovery.
8. Add deterministic contract, command, transcript, evidence, qualification, rollback, destruction,
   interruption, resume, conflict, stale-input, partial-failure, and prohibited-material tests.
   Update documentation and the AP-M9-W9 staging-operation handoff without claiming Live evidence.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not authenticate or run a real Terraform/backend/provider/image/OAuth/Secret Manager/DNS/TLS
operation. Do not deploy or destroy a platform or application, publish or roll back a real
generation, collect Live evidence, mutate a credential, state, cloud resource, repository setting,
Finance Assistant, `apps.comfforts.com`, or the inactive Finance integration package. AP-M9-W9 is
the first real staging operation and requires separate owner approvals. Do not claim Application
Adoption or production readiness. Do not change repository settings.

Use small coherent commits. Do not commit credentials, state, saved plans, provider payloads,
browser state, restricted membership, application data, raw traffic, recovery material, private
evidence, or manual-checkpoint artifacts.
