# App Platform AP-M9-W10 Slice 4 member-lifecycle handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the Slice 3 pull request has merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, and
the integration worktree is clean. Slices 1 through 3 added the inert Version 2 contract and
migration family, isolated member-directory infrastructure and IAM, and dual-version Shared Edge
enforcement with exact current-member lookup. They did not activate Version 2 in the operator
deployment path, mutate a member, publish a Version 2 application handoff, or perform a Live
operation. This fourth of seven ordered AP-M9-W10 functional slices implements only bounded member
lifecycle operations on `feat/platform-member-lifecycle`. Every later slice remains outside this
branch.

Read `AGENTS.md`, follow the complete order in `docs/README.md`, and read
`docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md` as the milestone plan and
`docs/plans/ap_m9/w10_platform_member_directory.md` as the current work-package plan. State this
AP-M9-W10 slice and its authority: AP-PR-004 through AP-PR-006, AP-PR-008, AP-PR-010, and
AP-PR-011; AP-QR-001, AP-QR-002, AP-QR-004, and AP-QR-006 through AP-QR-009; ADR-003, ADR-004,
ADR-006, ADR-008, ADR-012, ADR-014, and ADR-015; AP-EVAL-M9-01 through AP-EVAL-M9-09; and
AP-TM-004 through AP-TM-011, AP-TM-013, and AP-TM-014.
Inspect the branch, working tree, remotes, relationship to `feat/platform-member-directory`, and
whether that integration branch contains `origin/main`. Do not pull, reset, switch, commit, push,
mutate an external system, or change repository settings without the applicable owner direction.

Create `feat/platform-member-lifecycle` from the latest clean
`feat/platform-member-directory`. Its pull request must target that integration branch, not
`main`. Implement only this bounded lifecycle slice:

1. Inventory the private directory-control and member document formats, exact provider readback,
   browser identity boundary, operator command conventions, confirmation flow, diagnostics, and
   current Make surface before changing them.
2. Add the deep operator service for remote directory status and exact owner bootstrap, add,
   suspend, reactivate, and remove transitions. Each mutation must bind one environment, one-use
   verified Google visitor identity, exact remote predecessor, explicit reviewed action, and exact
   readback. Do not use operator-entered email as identity or membership authority.
3. Preserve the distinction between Cloud Operator and Google Visitor. Owner bootstrap must require
   a remotely never-initialized empty directory, refuse a non-empty or previously initialized
   directory, remain separate from `platform-deploy`, and be idempotent only for the exact reviewed
   successful state.
4. Update the directory control document and selected member document atomically with monotonic
   mutation cursors. Define absent, active, suspended, stale, conflicting, interrupted, malformed,
   and provider-unavailable outcomes explicitly and fail closed without leaking member identity or
   raw provider data.
5. Expose shallow `platform-member-status`, `platform-member-bootstrap-owner`,
   `platform-member-add`, `platform-member-suspend`, `platform-member-reactivate`, and
   `platform-member-remove` Make targets over that service. Keep prompts concise, natural-language,
   and explicit about the exact remote mutation before requiring confirmation.
6. Add deterministic provider fakes and tests for authorization, one-use browser binding,
   Cloud-Operator/Visitor separation, remote-empty bootstrap, idempotency, stale predecessor,
   conflict, every lifecycle transition, exact readback, interruption, privacy, and stable
   diagnostics. Do not perform a real browser or provider operation in repository checks.
7. Update only documentation needed to describe the implemented lifecycle result. At pull-request
   handoff, record Slice 4 accurately and point this prompt to Slice 5 without implementing Slice
   5. Run focused deterministic tests and the complete credential-free `make check` gate.

Do not activate Version 2 in the deployment path, publish Version 2 bundles, migrate fixtures,
perform Candidate Source staging operations, add qualification evidence, implement operator-state
recovery, or change a real application. Those belong to later ordered work or ADR-016.

Keep credentials, OAuth secrets, member identities, signed assertions, browser state, Terraform
state, saved plans, raw provider responses, and application payloads out of Git and retained public
evidence. Do not mutate staging, production, DNS, identity, Finance Assistant, or any real
application. Do not claim W10 completion, Candidate Source qualification, Accepted Source staging,
production readiness, or Application Adoption.

AP-M9-W11 owns the first Accepted Source staging operation only after all seven W10 slices merge to
the integration branch, the exact integration revision is candidate-qualified and frozen, and its
cumulative pull request merges to `main`.
