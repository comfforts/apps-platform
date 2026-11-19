# App Platform AP-M9-W3 lifecycle-contracts and profiles handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W2 retired-manifest cleanup pull request has merged, local
`main` is current and clean, and the owner approves AP-M9-W3. Inspect the branch, working tree,
remotes, and relationship to `origin/main`; preserve unrelated changes. Do not pull, switch,
reset, commit, push, or perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W3; AP-PR-010, AP-PR-011, AP-PR-012; AP-QR-003, AP-QR-004, AP-QR-006, AP-QR-007,
AP-QR-008, AP-QR-009; ADR-010, ADR-011, ADR-012, ADR-013; AP-EVAL-M9-01 and AP-EVAL-M9-02; and
AP-TM-001 through AP-TM-003 plus AP-TM-007 through AP-TM-014. Confirm AP-M9-W2 is merged before
modifying anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define generic platform
behavior or supply lifecycle-contract authority.

Implement only lifecycle contracts and environment profiles:

1. Add small, closed, committed non-secret profiles for staging and disabled production. Profiles
   contain stable owner decisions only. Keep generated or discoverable facts, credentials, secrets,
   Terraform state or plans, provider payloads, mutable references, and placeholders out.
2. Add closed, versioned contracts for the Deployment Specification, Execution Journal,
   Environment Status, Platform Integration Bundle, and Application Attachment Bundle. Keep staging
   and production values isolated and preserve platform/application ownership boundaries.
3. Implement deterministic canonicalization, digest binding, bounded local loading, ordered
   violations, and cross-document validation required by AP-EVAL-M9-02. A journal cannot authorize
   work outside its parent specification, and an attachment must bind the exact integration-bundle
   digest.
4. Add synthetic examples and deterministic tests for accepted values and fail-closed rejection of
   unknown fields, prohibited material, stale digests, cross-environment values, non-canonical
   bytes, and incomplete stage-output bindings.
5. Update the contract/configuration inventories, repository status, and next-slice handoff without
   reviving the AP-M8 manifest interface.

Preserve AP-M7 configuration, Terraform, runtime, Fixture, workflow-template, security, and
deterministic-verification behavior. Leave AP-M9-W4's interactive operator module, adapters,
`platform-*` Make targets, prompts, approval UI, execution, and resume behavior unimplemented.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not create a credential, identity, backend, Terraform state or saved plan, provider resource,
OAuth client, secret, DNS record, certificate, image, deployment, Live evidence, or Application
Adoption. Do not change repository settings, cloud resources, Finance Assistant,
`apps.comfforts.com`, or the inactive Finance integration package.
