# App Platform AP-M9-W10 Slice 2 infrastructure handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the Slice 1 pull request has merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, and
the integration worktree is clean. Slice 1 added an inert Version 2 contract family and
deterministic Version 1 migration; it did not activate Version 2 or create any provider resource.
This second of seven ordered AP-M9-W10 functional slices implements only Platform Member Directory
infrastructure on `feat/platform-member-directory-infrastructure`. Every later slice remains
outside this branch.

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

Create `feat/platform-member-directory-infrastructure` from the latest clean
`feat/platform-member-directory`. Its pull request must target that integration branch, not
`main`. Implement only this bounded infrastructure slice:

1. Inventory the existing Firestore session configuration, Terraform phase ownership, platform
   outputs, plan policy, provider readback, deterministic fakes, and tests before changing them.
2. Add the Platform-owned Firestore member-directory configuration and required indexes with an
   explicit namespace boundary from session data. Keep member records and member identities out of
   Terraform, state inputs, outputs, plans, logs, fixtures, and committed configuration.
3. Add only the least-privilege Shared Edge runtime IAM needed for directory access. Preserve the
   Cloud Operator, Platform Visitor, application, state, and runtime identity boundaries. Reject
   unexpected broader grants through provider readback and plan policy.
4. Add closed non-secret Terraform outputs and provider readback for database identity, namespace,
   indexes, and runtime-access posture. Do not output, list, synthesize, or inspect a member record.
5. Add the smallest deterministic directory adapter seam and in-memory implementation needed by
   later runtime and member-lifecycle slices, without wiring it into the active Shared Edge or
   operator commands.
6. Add mocked-plan, ownership, output, readback, namespace, IAM, and failure tests. Keep the Slice 1
   Version 2 contracts inert and the active Version 1 operator/runtime path unchanged.
7. Update only documentation needed to describe the implemented infrastructure result. At
   pull-request handoff, record Slice 2 accurately and point this prompt to Slice 3 without
   implementing Slice 3. Run focused deterministic tests and the complete credential-free
   `make check` gate.

Do not add Shared Edge membership lookup or admission behavior, member bootstrap or lifecycle
commands, browser flows, Version 2 bundle publication or application deployment, fixture migration,
Candidate Source staging operations, or qualification evidence. Those belong to later ordered
slices and begin only after this pull request merges.

Keep credentials, OAuth secrets, member identities, signed assertions, browser state, Terraform
state, saved plans, raw provider responses, and application payloads out of Git and retained public
evidence. Do not mutate staging, production, DNS, identity, Finance Assistant, or any real
application. Do not claim W10 implementation, Candidate Source qualification, Accepted Source
staging, production readiness, or Application Adoption.

AP-M9-W11 owns the first Accepted Source staging operation only after all seven W10 slices merge to
the integration branch, the exact integration revision is candidate-qualified and frozen, and its
cumulative pull request merges to `main`.
