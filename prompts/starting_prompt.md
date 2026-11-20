# App Platform AP-M9-W10 staging operation handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W9 fixture-application lifecycle pull request has merged and
protected `main` is current and clean. AP-M9-W10 is the first accepted external staging operation.
Any pre-merge Candidate Qualification is non-accepted evidence and must not be promoted. W10 deploys,
qualifies, rehearses approved destruction/redeployment, and leaves `apps-staging.comfforts.com`
deployed and qualified with the three repository-owned Fixture Applications.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W10; AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009; ADR-001 through ADR-013;
AP-EVAL-M9-01 through AP-EVAL-M9-09; and AP-TM-001 through AP-TM-014. Inspect the branch, working
tree, remotes, and relationship to `origin/main`. Stop on any mismatch; do not pull, reset, switch,
commit, push, or change repository settings without its applicable owner direction.

The owner's deliberate instruction to execute W10, or the owner's deliberate invocation of a named
deploy command, authorizes ordinary reversible staging creation/update through that command's
same-process specification and exact-plan confirmations. Do not request a duplicate chat, ticket,
or out-of-band approval. Destruction, purge, ownership transfer, production cutover, and scope
expansion retain separately named approval at their boundary.

Perform the staging journey from exact merged source:

1. Run the complete credential-free `make check` gate and stop on any failure, warning, or skip.
2. Verify the pinned Terraform toolchain, exact staging project, active human Cloud SDK account,
   user Application Default Credentials, `gcloud`, and `dig`. Never create or store a service-account
   key or copy a token, OAuth secret, Terraform state, plan, or provider payload into Git.
3. Run `make platform-deploy ENVIRONMENT=staging`. Keep the interactive wizard in one process.
   Review each displayed specification/action/plan, use its `y/N` gates, complete Google OAuth and
   Squarespace DNS work only at the displayed checkpoint, and press Enter for immediate readback.
   Enter the OAuth client secret only in Secret Manager, never in the terminal.
4. Run `make fixture-deploy ENVIRONMENT=staging`. It must build one immutable source-bound image,
   deploy the public/authenticated/restricted applications sequentially in three independent
   Application State lineages, read back their posture, and activate one complete Registration
   Generation without operator-authored manifests or bundle fields.
5. Run `make fixture-status ENVIRONMENT=staging`, `make platform-status ENVIRONMENT=staging`, and
   `make platform-qualify ENVIRONMENT=staging`. Complete browser checkpoints without exporting
   cookies, sessions, assertions, identity claims, screenshots, or application payloads.
6. Report the exact revision, specification/journal/generation/evidence digests, coarse outcomes,
   and every failed or unavailable AP-EVAL-M9 gate. Do not call staging qualified unless every
   mandatory check passes for those exact bindings.
7. Only after separately named owner approval for the destructive rehearsal, detach and destroy
   each Fixture Application through `fixture-destroy`, then run `platform-destroy`. Verify the
   retained backend, configuration, signing-key, provider-service, recovery, and evidence inventory;
   never target Application State from platform destruction and never issue a blind Terraform
   destroy. Redeploy the platform and fixtures through the same commands and requalify them.
8. Leave staging deployed and qualified at the accepted revision. Commit only an owner-approved,
   secret-free evidence index on a dedicated evidence branch if requested; keep private evidence,
   raw outputs, state, plans, browser state, and checkpoint artifacts outside Git.

Stop on the first discrepancy. Resume only through the existing private journal and identical
immutable bindings. Do not mutate Finance Assistant, `apps.comfforts.com`, production, the inactive
Finance integration package at `integrations/ai_finance_assistant/README.md`, or any real
application. Read that package only if the owner separately scopes a compatibility review; it
remains a non-authoritative input, cannot define generic platform behavior, and cannot define this
operation. Do not claim Application Adoption,
production readiness, or production ownership transfer. AP-M9-W11 owns read-only production
readiness after W10 is accepted.
