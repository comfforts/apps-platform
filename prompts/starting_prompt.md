# App Platform AP-M9-W10 Slice 3 edge-enforcement handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the Slice 2 pull request has merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, and
the integration worktree is clean. Slice 1 added the inert Version 2 contract family and migration.
Slice 2 added repository implementation for the isolated `app-platform-members` Firestore
database, conditioned default-database session IAM, the exact-read member custom role, closed
Terraform/provider readback, and an unwired deterministic exact-key adapter. Neither slice
activated Version 2, reconciled a provider, or changed live admission. This third of seven ordered
AP-M9-W10 functional slices implements only Shared Edge member enforcement on
`feat/member-directory-edge-enforcement`. Every later slice remains outside this branch.

Read `AGENTS.md`, follow the complete order in `docs/README.md`, and read
`docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md` as the milestone plan and
`docs/plans/ap_m9/w10_platform_member_directory.md` as the current work-package plan. State the
slice and authority: AP-M9-W10; AP-PR-004 through AP-PR-006, AP-PR-008, AP-PR-010, and AP-PR-011;
AP-QR-001, AP-QR-002, AP-QR-004, and AP-QR-006 through AP-QR-009; ADR-003, ADR-004, ADR-006,
ADR-008, ADR-012, ADR-014, and ADR-015; AP-EVAL-M9-01 through AP-EVAL-M9-09; and AP-TM-004
through AP-TM-011, AP-TM-013, and AP-TM-014. Inspect the branch, working tree, remotes,
relationship to `feat/platform-member-directory`, and whether that integration branch contains
`origin/main`. Do not pull, reset, switch, commit, push, mutate an external system, or change
repository settings without the applicable owner direction.

Create `feat/member-directory-edge-enforcement` from the latest clean
`feat/platform-member-directory`. Its pull request must target that integration branch, not
`main`. Implement only this bounded runtime slice:

1. Inventory the active Version 1 Shared Edge identity, routing, assertion, live-client, and
   observability paths; the inert Version 2 contracts; and the Slice 2 member-directory model and
   IAM outputs before changing them.
2. Add a provider-backed exact-current-member lookup adapter for the isolated named database.
   It may derive and read one opaque member reference only. Do not add member enumeration,
   identity search, member mutation, or fallback to the session database.
3. Implement the Version 2 admission matrix behind Version 2 registration/generation inputs:
   public plus `none` stays anonymous; public plus `optional` allows anonymous access and delivers
   identity only after deliberate platform login; authenticated plus `required` needs verified
   identity but not membership; restricted plus `required` needs verified identity and a current
   active member record.
4. Strip visitor-supplied identity headers in every mode. Issue only the minimal Version 2,
   application-audience-bound assertion allowed by the selected Identity Delivery policy. A
   positive member projection may describe only the current visitor; it must not contain the
   directory, another member, email, feature roles, or entitlements.
5. Fail restricted admission closed for absent, suspended, malformed, or unavailable directory
   state without changing public or authenticated behavior. Preserve constant non-sensitive
   diagnostics and the existing application-owned Feature Entitlement boundary.
6. Add deterministic runtime tests for every valid admission/identity-delivery combination,
   exact-key lookup, assertion minimization, audience isolation, header stripping, directory
   failure, and Version 1 compatibility. Do not make Version 2 the active operator deployment path
   or publish a Version 2 application handoff in this slice.
7. Update only documentation needed to describe the implemented runtime result. At pull-request
   handoff, record Slice 3 accurately and point this prompt to Slice 4 without implementing Slice
   4. Run focused deterministic tests and the complete credential-free `make check` gate.

Do not add owner bootstrap or member lifecycle commands, browser enrollment operations, Version 2
bundle publication or application deployment, fixture migration, Candidate Source staging
operations, or qualification evidence. Those belong to later ordered slices and begin only after
this pull request merges.

Keep credentials, OAuth secrets, member identities, signed assertions, browser state, Terraform
state, saved plans, raw provider responses, and application payloads out of Git and retained public
evidence. Do not mutate staging, production, DNS, identity, Finance Assistant, or any real
application. Do not claim W10 implementation, Candidate Source qualification, Accepted Source
staging, production readiness, or Application Adoption.

AP-M9-W11 owns the first Accepted Source staging operation only after all seven W10 slices merge to
the integration branch, the exact integration revision is candidate-qualified and frozen, and its
cumulative pull request merges to `main`.
