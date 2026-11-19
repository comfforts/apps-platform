# App Platform AP-M9-W4 interactive lifecycle core handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W3 lifecycle-contract pull request has merged, local `main`
is current and clean, and the owner approves AP-M9-W4. Inspect the branch, working tree, remotes,
and relationship to `origin/main`; preserve unrelated changes. Do not pull, switch, reset, commit,
push, or perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W4; AP-PR-010, AP-PR-011; AP-QR-003, AP-QR-004, AP-QR-006, AP-QR-007, AP-QR-008,
AP-QR-009; ADR-010, ADR-011, ADR-012, ADR-013; AP-EVAL-M9-01 and AP-EVAL-M9-03; and AP-TM-001
through AP-TM-003 plus AP-TM-007 through AP-TM-014. Confirm AP-M9-W3 is merged before modifying
anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define generic platform
behavior or supply lifecycle authority.

Implement only the interactive lifecycle core:

1. Implement one deep Python lifecycle module under `infrastructure/operator/`. Keep its public
   interface small and put orchestration, preflight, preparation, approval binding, journaling,
   status reconciliation, checkpoint state, redaction, and safe resume behind it.
2. Add credential-free `platform-prepare` and `platform-status` Make targets. Preparation is
   read-only: it selects one committed Environment Profile, validates clean reviewed source and
   pinned tools, discovers non-secret facts through injected adapters, asks only unresolved owner
   decisions, and emits one complete canonical Deployment Specification and digest.
3. Keep completeness separate from approval. Model approval as an explicit owner decision over the
   complete specification digest; an approval cannot fill a missing value, clear a blocker, widen a
   stage, or survive a source, profile, environment, or specification change.
4. Inject Git, GitHub, GCP, Terraform, DNS, terminal, filesystem, and clock adapters at side-effect
   boundaries. Provide deterministic fakes and process-local temporary storage. Default checks must
   use only fakes and must perform no network, credential, provider, repository, or cloud action.
5. Exercise first preparation, no-change, drift, conflict, interruption, cancellation, and resume.
   Prove closed journal stages are not repeated; changed scope requires a new specification and
   approval; waiting and failure remain truthful; terminal output is redacted; and no prompt asks
   for a secret.
6. Update documentation, tests, and the next-slice handoff without changing the W3 contracts except
   when an implementation test proves a contract defect and the owner separately approves that
   contract change.

Preserve AP-M7 configuration, Terraform, runtime, Fixture, workflow-template, security, and
deterministic-verification behavior. Leave AP-M9-W5's deployable Terraform lifecycle, backend
rendering, operation identities, impersonation, real Terraform plans/applies, provider calls,
OAuth, external DNS, and cloud mutation unimplemented.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not create a credential, identity, backend, Terraform state or saved plan, provider resource,
OAuth client, secret, DNS record, certificate, image, deployment, Live evidence, or Application
Adoption. Do not change repository settings, cloud resources, Finance Assistant,
`apps.comfforts.com`, or the inactive Finance integration package.
