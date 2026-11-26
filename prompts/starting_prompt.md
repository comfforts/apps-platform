# App Platform AP-M9-W10 Slice 6 operator-handoff reconciliation

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the Slice 5 pull request has merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, and
the integration worktree is clean. Slices 1 through 5 added Version 2 contracts and migration,
isolated member-directory infrastructure and IAM, dual-version Shared Edge enforcement, bounded
owner/member lifecycle operations, and the complete Version 2 application-handoff and atomic
generation-activation path. They performed no Live Version 2 operation. This sixth of seven
ordered AP-M9-W10 functional slices reconciles only the operator and reviewer documentation on
`docs/identity-delivery-operator-handoff`. Candidate qualification support and every external
operation remain outside this branch.

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

Create `docs/identity-delivery-operator-handoff` from the latest clean
`feat/platform-member-directory`. Its pull request must target that integration branch, not
`main`. Implement only this bounded documentation reconciliation slice:

1. Inventory the implemented Version 2 contracts, infrastructure, edge, member lifecycle,
   application handoff, fixtures, CLI, Make targets, diagnostics, compatibility behavior, tests,
   and actual limitations before changing prose.
2. Reconcile the project README, environment lifecycle runbook, system design, contract indexes,
   component guides, repository layout, W10 plan status, evaluation strategy, threat model, and
   documentation router so a human operator can follow the current lifecycle without reconstructing
   it from milestone identifiers.
3. Document the exact Admission Mode/Identity Delivery combinations, member-directory boundary,
   owner bootstrap and member commands, Version 1 predecessor migration, complete Version 2
   activation, application-side assertion verification, fixture handoff, and rollback compatibility.
4. Give one linear, copyable Candidate Source staging procedure for the later qualification slice,
   but label it as a future owner-invoked operation. Keep Accepted Source staging, production, real
   Application Adoption, and operator recovery explicitly separate.
5. Reconcile stale Version 1 or “inert Version 2” wording only where the implementation has made it
   false. Preserve historical records and do not rewrite predecessor evidence into Version 2
   evidence.
6. Update governance tests needed to keep documentation routing and status deterministic. Add no
   product behavior, provider adapter, qualification implementation, or evidence.
7. At pull-request handoff, record Slice 6 accurately and point this prompt to Slice 7. Run focused
   deterministic documentation/governance tests and the complete credential-free `make check`
   gate.

Do not perform Candidate Source staging operations, add final qualification evidence, implement
operator-state recovery, broaden the member lifecycle, or change a real application. Candidate
qualification readiness and the real Candidate operation belong to Slice 7, and recovery remains
governed by proposed ADR-016.

Keep credentials, OAuth secrets, member identities, signed assertions, browser state, Terraform
state, saved plans, raw provider responses, and application payloads out of Git and retained public
evidence. Do not mutate staging, production, DNS, identity, Finance Assistant, or any real
application. Do not claim W10 completion, Candidate Source qualification, Accepted Source staging,
production readiness, or Application Adoption.

AP-M9-W11 owns the first Accepted Source staging operation only after all seven W10 slices merge to
the integration branch, the exact integration revision is candidate-qualified and frozen, and its
cumulative pull request merges to `main`.
