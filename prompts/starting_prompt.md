# App Platform AP-M9-W10 Slice 5 application-handoff handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the Slice 4 pull request has merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, and
the integration worktree is clean. Slices 1 through 4 added the inert Version 2 contracts and
migration, isolated member-directory infrastructure and IAM, dual-version Shared Edge enforcement,
and bounded owner/member lifecycle operations. They did not publish or activate a Version 2
application handoff, migrate a fixture, or perform a Live operation. This fifth of seven ordered
AP-M9-W10 functional slices implements only Version 2 application handoffs on
`feat/identity-delivery-application-handoffs`. Every later slice remains outside this branch.

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

Create `feat/identity-delivery-application-handoffs` from the latest clean
`feat/platform-member-directory`. Its pull request must target that integration branch, not
`main`. Implement only this bounded application-handoff slice:

1. Inventory every Version 1 and inert Version 2 handoff, bundle, intent, compiler, registration,
   fixture, CLI, Make, provider-readback, and compatibility consumer before changing it.
2. Add `IDENTITY_DELIVERY=<none|optional|required>` to `application-handoff-check` and
   `platform-outputs`. Enforce only `public/none`, `public/optional`,
   `authenticated/required`, and `restricted/required`; never infer public opt-in from an ambient
   Platform Session.
3. Make Platform Integration Bundle, Application Attachment Bundle, registration intent,
   application handoff checks, fixture handoff, and registration consume and emit one complete
   Version 2 family. Do not accept mixed Version 1/Version 2 inputs or a second independent
   identity-delivery value at registration.
4. Preserve deterministic Version 1 migration: discard every registration-scoped member set,
   map public to `none`, map authenticated and restricted to `required`, and activate only one
   complete immutable Version 2 generation after every consumer validates it.
5. Update the three fixtures and application verification boundary for explicit Identity Delivery.
   Public `none` remains anonymous, public `optional` may receive deliberate platform identity,
   authenticated remains membership-independent, and restricted requires a current active
   platform member. Application Feature Entitlements remain application-owned.
6. Add focused deterministic tests for every valid and invalid Admission Mode/Identity Delivery
   combination, version mismatch, migration, bundles, intents, target posture, fixture behavior,
   complete-generation publication, activation, rollback compatibility, privacy, and rejection of
   member records or lists in public artifacts. Repository checks must not use a real browser,
   provider, credential, or external network.
7. Update only documentation needed to describe the implemented handoff result. At pull-request
   handoff, record Slice 5 accurately and point this prompt to Slice 6 without implementing Slice
   6. Run focused deterministic tests and the complete credential-free `make check` gate.

Do not perform Candidate Source staging operations, add final qualification evidence, implement
operator-state recovery, broaden the member lifecycle, or change a real application. Operator
handoff reconciliation belongs to Slice 6, Candidate qualification readiness and the real
Candidate operation belong to Slice 7, and recovery remains governed by proposed ADR-016.

Keep credentials, OAuth secrets, member identities, signed assertions, browser state, Terraform
state, saved plans, raw provider responses, and application payloads out of Git and retained public
evidence. Do not mutate staging, production, DNS, identity, Finance Assistant, or any real
application. Do not claim W10 completion, Candidate Source qualification, Accepted Source staging,
production readiness, or Application Adoption.

AP-M9-W11 owns the first Accepted Source staging operation only after all seven W10 slices merge to
the integration branch, the exact integration revision is candidate-qualified and frozen, and its
cumulative pull request merges to `main`.
