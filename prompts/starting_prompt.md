# App Platform AP-M9-W5 deployable Terraform lifecycle handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W4 interactive-lifecycle pull request has merged, local
`main` is current and clean, and the owner approves AP-M9-W5. Create branch
`feat/ap-m9-deployable-terraform-lifecycle`. Inspect the branch, working tree, remotes, and
relationship to `origin/main`; preserve unrelated changes. Do not pull, reset, commit, push, or
perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W5; AP-PR-001 through AP-PR-005 and AP-PR-010; AP-QR-001 through AP-QR-009; ADR-001,
ADR-004 through ADR-011, and ADR-013; AP-EVAL-M9-01, AP-EVAL-M9-02, and AP-EVAL-M9-04; and
AP-TM-001 through AP-TM-014. Confirm AP-M9-W4 is merged before modifying anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define generic platform
behavior, Terraform behavior, resource ownership, or deployment authority.

Implement only the deployable Terraform lifecycle repository slice:

1. Reshape the AP-M7 static roots into explicit bootstrap, platform-foundation, and Shared Edge
   phases while preserving one Platform State lineage, independent Fixture Application State, and
   every AP-M7 ownership constraint. Remove placeholder-only dependencies from the deployable root
   interfaces without inventing operator values.
2. Implement the deterministic backend renderer and lineage-preserving declarations needed by the
   lifecycle module. Rendering must be path-bounded, canonical, idempotent, and testable in a
   temporary directory. It must not initialize, migrate, read, or write a real backend.
3. Define operation identities and the exact short-lived local impersonation profile for the
   separately scoped bootstrap, plan, apply, readback, rollback, destroy, and recovery authorities.
   No identity, IAM binding, federation resource, credential, token, or service-account key may be
   created in this package.
4. Implement plan canonicalization and policy that binds environment, source, state owner, phase,
   allowed resource/action inventory, and destructive boundary. Reject an unexpected create,
   update, replacement, delete, provider default, owner, project, root, or service before any later
   apply path can consume the plan.
5. Add closed typed outputs for bootstrap, foundation, and Shared Edge phases. Keep every output
   non-secret and prohibit state access, raw plans, provider responses, credential material, or
   application-owned values.
6. Exercise the roots and lifecycle integration with Terraform mocked plans and deterministic
   command fakes. Preserve staging/production isolation and prove production remains disabled by
   `OWNERSHIP_TRANSFER_REQUIRED`.
7. Update documentation, tests, and the AP-M9-W6 handoff. Keep the W4 `platform-prepare` and
   `platform-status` interfaces stable unless an implementation test proves a defect and the owner
   separately approves the interface change.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not authenticate or run a real Terraform init, plan, apply, import, state, force-unlock,
backend migration, provider readback, or DNS lookup. Do not create or mutate a credential,
identity, IAM binding, backend, Terraform state or saved plan, provider resource, OAuth client,
secret, DNS record, certificate, image, deployment, Live evidence, or Application Adoption. Do not
change repository settings, cloud resources, Finance Assistant, `apps.comfforts.com`, or the
inactive Finance integration package.

Use small coherent commits. Do not commit a failing mocked plan, generated backend file, local
operator state, `.terraform/` directory, credential, state, saved plan, provider payload, or
authenticated artifact.
