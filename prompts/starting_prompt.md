# App Platform AP-M9-W2 retired-manifest cleanup handoff

Continue the separately governed Comfforts App Platform from its canonical repository root.

Use this handoff only after the AP-M9-W1 governance-rebaseline pull request has merged, local
`main` is current and clean, and the owner approves AP-M9-W2. Inspect the branch, working tree,
remotes, and relationship to `origin/main`; preserve unrelated changes. Do not pull, switch,
reset, commit, push, or perform an external mutation without its applicable approval.

Read `AGENTS.md` and follow the complete order in `docs/README.md`. State the slice and authority:
AP-M9-W2; AP-PR-010, AP-PR-011, AP-PR-012; AP-QR-007, AP-QR-008, AP-QR-009; ADR-010, ADR-011,
ADR-012, ADR-013; and AP-EVAL-M9-02. Confirm AP-M9-W1 is merged before modifying anything.

`integrations/ai_finance_assistant/README.md` remains an inactive, non-authoritative input. Read it
only if the owner separately scopes a compatibility review; it cannot define generic platform
behavior or supply cleanup authority.

Implement only the retired manifest cleanup:

1. Remove `infrastructure/config/schemas/operator-input-manifest.v1.schema.json`,
   `infrastructure/config/examples/operator-input-manifest.synthetic.v1.json`, and
   `infrastructure/config/operator_manifest.py`.
2. Remove operator-manifest loading, canonicalization, immutable-input, predecessor-chain, and
   manifest-only policy functions and exports from `infrastructure/config/validation.py` and its
   package interface. Preserve every AP-M7 configuration contract and consumer.
3. Remove manifest-only tests and fixtures. Keep regression coverage proving the remaining AP-M7
   configuration interface is unchanged and no active document or prompt routes operators to the
   retired flow.
4. Update repository status, configuration inventory, and historical references. Preserve the
   factual AP-M8 record under `docs/history/`; do not rewrite Git history.
5. Leave AP-M9-W3 contracts and profiles unimplemented. Reserved paths and command names do not
   authorize scaffolding later packages.

Run `make check` from the repository root and report the exact result. The check must remain
credential-free, deterministic, network-free after local setup, and non-mutating.

Do not create an operator manifest, environment profile, Deployment Specification, credential,
identity, backend, state, plan, provider resource, OAuth client, DNS record, certificate, image,
deployment, bundle, or Live evidence. Do not change repository settings, cloud resources, Finance
Assistant, `apps.comfforts.com`, or the inactive Finance integration package.
