# App Platform AP-M9-W10 Slice 1 contract handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the delivery-slice governance change has merged to
`feat/platform-member-directory`, that integration branch contains current protected `main`, and
the integration worktree is clean. This is the first of seven ordered AP-M9-W10 functional slices.
It implements only the Version 2 contract family and deterministic Version 1 migration on
`feat/identity-delivery-v2-contracts`. Every later slice remains outside this branch.

AP-M9-W9 Candidate Source evidence remains truthful Version 1 predecessor evidence. It must not be
relabeled as ADR-015 qualification or copied into new evidence. This slice produces Contract
evidence only; later slices own infrastructure, runtime, operator, fixture, and Candidate Source
evidence.

Read `AGENTS.md`, follow the complete order in `docs/README.md`, and read
`docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md` as the milestone plan and
`docs/plans/ap_m9/w10_platform_member_directory.md` as the current work-package plan. State the
slice and authority:
AP-M9-W10; AP-PR-004 through AP-PR-006, AP-PR-008, AP-PR-010, and AP-PR-011; AP-QR-001,
AP-QR-002, AP-QR-004, and AP-QR-006 through AP-QR-009; ADR-003, ADR-004, ADR-006, ADR-008,
ADR-012, ADR-014, and ADR-015; AP-EVAL-M9-01 through AP-EVAL-M9-09; and AP-TM-004 through
AP-TM-011, AP-TM-013, and AP-TM-014. Inspect the branch, working
tree, remotes, relationship to `feat/platform-member-directory`, and whether that integration
branch contains `origin/main`. Do not pull, reset, switch, commit, push, mutate
an external system, or change repository settings without the applicable owner direction.

Create `feat/identity-delivery-v2-contracts` from the latest clean
`feat/platform-member-directory`. Its pull request must target that integration branch, not `main`.
Implement only this bounded contract slice:

This slice is additive and inert. Keep the active Version 1 schemas, consumers, fixtures, runtime,
operator commands, bundle publication, and Registration Generation activation unchanged. Version
2 may be loaded, validated, migrated, serialized, and tested deterministically, but it must not
become active output until the later infrastructure, runtime, lifecycle, and handoff slices have
all implemented their Version 2 consumers and one complete generation can activate atomically.

1. Inventory every Version 1 schema, canonical vector, validator, compiler input/output, loader,
   fixture, and test that consumes registration, compiled-generation, integration-bundle,
   attachment-bundle, registration-intent, or verified-identity data.
2. Add the complete Version 2 registration, compiled-generation, Platform Integration Bundle,
   Application Attachment Bundle, registration-intent, and Verified Identity Context schemas.
   Represent Identity Delivery explicitly as `none`, `optional`, or `required` and validate its
   allowed combinations with Admission Mode.
3. Remove every per-registration member set from Version 2. Keep member identities, records, lists,
   and lifecycle state out of registration, generation, bundle, intent, catalogue, and evidence
   contracts.
4. Implement deterministic Version 1 migration: public becomes `none`; authenticated and
   restricted become `required`; existing member sets are discarded rather than copied; public
   `optional` requires an explicit reviewed Version 2 update.
5. Update canonical serialization, validation, vectors, compatibility loading, and focused tests.
   Version 1 remains readable historical input, while mixed or member-carrying Version 2 output is
   rejected.
6. Update only documentation needed to describe the implemented contract result. At pull-request
   handoff, record Slice 1 accurately and point this prompt to Slice 2 without implementing Slice 2.
7. Run focused deterministic tests while editing and the complete credential-free `make check`
   gate before handoff.

Do not add Firestore resources or IAM, Shared Edge membership lookup, member commands, browser
flows, Version 2 application deployment, fixture migration, Candidate Source staging operations,
or qualification evidence. Those belong to later ordered slices and begin only after this pull
request merges.

Keep credentials, OAuth secrets, member identities, signed assertions, browser state, Terraform
state, saved plans, raw provider responses, and application payloads out of Git and retained public
evidence. Do not mutate production, `apps.comfforts.com`, Finance Assistant, or any real application.
Do not claim W10 implementation, Candidate Source qualification, Accepted Source staging,
production readiness, or Application Adoption. AP-M9-W11 owns the first Accepted Source staging
operation only after all seven W10 slices merge to the integration branch, that exact revision is
candidate-qualified and frozen, and its cumulative pull request merges to `main`; AP-M9-W12 owns
read-only production readiness.
