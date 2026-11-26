# App Platform AP-M9-W10 Candidate Source qualification

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after all seven AP-M9-W10 functional-slice pull requests have merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, the
exact integration revision is clean and pushed, and its pull-request checks and credential-free
`make check` gate pass. Slices 1 through 7 implement the Version 2 contracts and migration,
isolated Platform Member Directory infrastructure, Shared Edge enforcement, bounded member
lifecycle, complete application handoff, operator documentation, and cleanup-safe qualification
support. No slice branch performed a Live Version 2 operation.

Read `AGENTS.md`, follow the complete order in `docs/README.md`, and read
`docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md` as the milestone plan,
`docs/plans/ap_m9/w10_platform_member_directory.md` as the completed implementation package, and
`docs/runbooks/environment_lifecycle.md#candidate-staging-verification` as the exact operator
procedure. State this AP-M9-W10 Candidate Source operation and its authority: AP-PR-004 through
AP-PR-006, AP-PR-008, AP-PR-010, and AP-PR-011; AP-QR-001, AP-QR-002, AP-QR-004, and AP-QR-006
through AP-QR-009; ADR-003, ADR-004, ADR-006, ADR-008, ADR-012, ADR-014, and ADR-015;
AP-EVAL-M9-01 through AP-EVAL-M9-09; and AP-TM-004 through AP-TM-011, AP-TM-013, and AP-TM-014.

Before any authenticated or external operation, inspect the branch, working tree, remotes, exact
relationship to `origin/feat/platform-member-directory`, and whether current `origin/main` is an
ancestor. Report a mismatch and stop. Do not pull, reset, switch, commit, push, mutate staging, or
change repository settings without the applicable owner direction. Run the credential-free
repository gate and report its exact result. A tracked change after qualification invalidates the
result.

Wait for explicit owner direction before invoking the Candidate Source sequence. When directed,
follow the runbook without reordering or combining its boundaries:

1. Run preflight and deployment checking from the exact Candidate Source revision.
2. Bootstrap or read back the fixture project, deploy Version 2 platform state, and verify the
   directory is remotely empty for first migration or already at the reviewed owner-only baseline
   for a rerun.
3. Bootstrap the owner only when the directory has never been initialized. Retain the returned
   opaque owner reference privately; do not record identity claims or member data.
4. Connect the fixture project and complete the Version 2 handoff, inspection, registration, and
   status sequence for public `none`, authenticated `required`, and restricted `required`.
5. Run `platform-qualify` with
   `OWNER_MEMBER_REFERENCE=<reviewed-owner-member-reference>`. Keep the process open through every
   separately confirmed routing, temporary-member, rollback, and restoration action.
6. Require the final owner-only member baseline, intended complete Registration Generation, all
   fixture routes, source binding, and redacted Candidate evidence to read back exactly.

Qualification must reuse the existing member service to add and allow one distinct member,
suspend and deny, reactivate and allow, remove and deny, then restore the reviewed owner-only
baseline. Every browser invocation requires operator confirmation. The admission callback returns
only the application identifier, one-use challenge, and coarse decision. Evidence must exclude
member references, identities, assertions, cookies, authorization material, browser state, raw
provider payloads, Terraform state, saved plans, and application payloads. A cleanup or baseline
restoration blocker stops the operation; do not begin rollback or claim qualification.

On success, report the exact source revision, Registration Generation and digest, evidence digest
and private path, final member baseline state, commands, warnings, and limitations required by the
evaluation strategy. Freeze the qualified integration revision before its cumulative pull request
to `main`. Any defect or tracked correction requires a semantically named fix branch targeting the
integration branch, a full repository gate, merge, and complete Candidate Source rerun.

Do not treat Candidate Source as Accepted Source, mutate production, adopt Finance Assistant or
another real application, implement ADR-016 recovery, or broaden the member-directory product.
AP-M9-W11 owns the first Accepted Source staging operation only after the frozen qualified
integration branch merges to protected `main`.
