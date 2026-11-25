# App Platform AP-M9-W10 member directory handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the governance change accepting ADR-015 has merged and protected
`main` is current and clean. AP-M9-W10 implements and candidate-qualifies the Platform Member
Directory and explicit Identity Delivery model. It is not the first Accepted Source operation;
that operation moves to AP-M9-W11.

AP-M9-W9 Candidate Source evidence remains truthful Version 1 predecessor evidence. It must not be
relabeled as ADR-015 qualification or copied into new evidence. W10 must produce fresh Version 2
contract, runtime, operator, fixture, and candidate-qualification evidence.

Read `AGENTS.md`, follow the complete order in `docs/README.md`, and read
`docs/plans/ap_m9_w10_platform_member_directory.md` as the current delivery plan. State the slice and authority:
AP-M9-W10; AP-PR-004 through AP-PR-006, AP-PR-008, AP-PR-010, and AP-PR-011; AP-QR-001,
AP-QR-002, AP-QR-004, and AP-QR-006 through AP-QR-009; ADR-003, ADR-004, ADR-006, ADR-008,
ADR-012, ADR-014, and ADR-015; AP-EVAL-M9-01 through AP-EVAL-M9-09; and AP-TM-004 through
AP-TM-006, AP-TM-008 through AP-TM-010, AP-TM-013, and AP-TM-014. Inspect the branch, working
tree, remotes, and relationship to `origin/main`. Do not pull, reset, switch, commit, push, mutate
an external system, or change repository settings without the applicable owner direction.

Implement the accepted model in a bounded feature branch:

1. Add Version 2 registration, compiled-generation, Platform Integration Bundle, Application
   Attachment Bundle, and Verified Identity Context contracts. Deterministically migrate public
   registrations to Identity Delivery `none`, authenticated and restricted registrations to
   `required`, and remove all per-registration member sets. Permit public `optional` only through
   an explicit reviewed registration update.
2. Add one environment-scoped Firestore Platform Member Directory. Platform State owns database
   configuration, indexes, and least-privilege Shared Edge access. Member records are remote
   operational data, never Terraform input, Git configuration, generation content, bundle data,
   catalogue data, ordinary terminal output, or retained public evidence.
3. Enforce public `none` and `optional`, authenticated `required`, and restricted `required` plus
   active membership. Key members by verified issuer and immutable subject. Deliver only the
   current visitor's minimal application-audience-bound context. Fail restricted admission closed
   when membership is absent, inactive, unreadable, or inconsistent. Preserve application-owned
   principals, users, roles, Feature Entitlements, separate OAuth clients, and explicit account
   linking.
4. Add a separately confirmed `platform-member-bootstrap-owner` operation. It must distinguish the
   Cloud Operator from the Google Visitor, work only against a remotely empty directory, show one
   non-sensitive exact action, create idempotently, and perform remote readback. Missing local
   `.platform-operator` state must never permit bootstrap over a non-empty directory.
5. Add bounded member status, add, suspend, reactivate, and remove operations. Scope every action to
   one environment and exact remote predecessor, require confirmation for mutation, make identical
   retries idempotent, and prove membership changes do not compile a Registration Generation or
   deploy an application.
6. Update the compiler, Shared Edge, operator, fixture applications, in-memory fakes, documentation,
   and focused deterministic tests together. Keep the established top-level Make lifecycle; add
   only the smallest member-specific and Identity Delivery inputs required by ADR-015.
7. Run the complete credential-free `make check` gate. With owner direction for Candidate Source
   staging testing, explicitly bootstrap the owner, add a second member, prove restricted allow,
   suspend/deny, reactivate/allow, remove/deny, public anonymous and optional identity behavior,
   authenticated membership-independent admission, directory failure, and application-owned
   Feature Entitlements. Restore the reviewed member baseline before closing qualification.

Keep credentials, OAuth secrets, member identities, signed assertions, browser state, Terraform
state, saved plans, raw provider responses, and application payloads out of Git and retained public
evidence. Do not mutate production, `apps.comfforts.com`, Finance Assistant, or any real application.
Do not claim Accepted Source staging, production readiness, or Application Adoption. AP-M9-W11 owns
the first Accepted Source staging operation after W10 is merged and candidate-qualified; AP-M9-W12
owns read-only production readiness.
