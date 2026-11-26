# App Platform AP-M9-W10 Slice 7 Candidate qualification readiness

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the Slice 6 pull request has merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, and
the integration worktree is clean. Slices 1 through 6 implement the Version 2 contracts and
migration, isolated member-directory infrastructure and IAM, dual-version Shared Edge
enforcement, bounded owner/member lifecycle, complete Version 2 application handoff and atomic
generation activation, plus the reconciled operator procedure. They performed no Live Version 2
operation. This seventh and final ordered AP-M9-W10 functional slice adds the deterministic
qualification support needed to evaluate that complete model on
`evidence/member-admission-candidate-qualification`. The real Candidate Source operation occurs
only after this slice merges to the integration branch and the owner deliberately invokes it.

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

Create `evidence/member-admission-candidate-qualification` from the latest clean
`feat/platform-member-directory`. Its pull request must target that integration branch, not
`main`. Implement only this bounded qualification-readiness slice:

1. Extend the existing qualification path rather than creating a parallel member-administration
   mechanism. Reuse the source-admitted member service, browser confirmations, opaque member
   references, exact predecessor checks, atomic provider transactions, and safe diagnostics.
2. Add deterministic qualification coverage for an explicitly reviewed second member: add and
   allow on `fixture-restricted`, suspend and deny, reactivate and allow, remove and deny, then
   verify restoration of the reviewed owner-only baseline.
3. Prove public Identity Delivery `none` and explicit `optional`, authenticated admission that is
   independent of membership, restricted active-member admission, application-owned feature
   denial, logout and expired-session behavior, visitor-header replacement, directory
   unavailability, stale cache bounds, HTTP/SSE/WebSocket/upload-download paths, and
   cross-application isolation.
4. Preserve the exact retained Version 1 or Version 2 rollback target. Qualification may perform
   only its separately confirmed temporary rollback and restoration, must stop when a prerequisite
   fails, and must never leave the predecessor or a temporary member baseline active silently.
5. Keep evidence least-data and revision-bound. Record only allowlisted coarse results, opaque
   references where explicitly permitted, and digests. Exclude member identities, assertions,
   cookies, authorization material, browser state, raw provider payloads, Terraform state, saved
   plans, and application payloads.
6. Update the design, threat controls, evaluation wording, operator documentation, component
   guides, plan status, prompt, and focused tests made concrete by the qualification implementation.
   Do not implement ADR-016 operator-state recovery or broaden the member-directory product.
7. Run focused deterministic tests and the complete credential-free `make check` gate. At
   pull-request handoff, state that no provider operation occurred on this branch and provide the
   exact owner-invoked post-merge Candidate Source procedure from
   `docs/runbooks/environment_lifecycle.md`.

Do not run Candidate Source staging from the slice branch. After the pull request merges, update
and push the exact clean `feat/platform-member-directory` revision, confirm it still contains
current protected `main`, and wait for explicit owner direction before invoking the documented
Candidate Source sequence. A successful run must bind evidence to that exact revision, restore the
owner-only member baseline and intended Registration Generation, and freeze the integration branch.
Any later tracked change invalidates the qualification and requires another reviewed slice and
complete rerun.

Do not mutate staging, production, DNS, identity, Finance Assistant, or any real application from
this slice branch. Do not perform Accepted Source staging, production, real Application Adoption,
Finance Assistant changes, or operator-state recovery. AP-M9-W11 owns the first Accepted Source
staging operation only after all seven W10 slices merge to the integration branch, the exact
integration revision is candidate-qualified and frozen, and its cumulative pull request merges to
`main`.
