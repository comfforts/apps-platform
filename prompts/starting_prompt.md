# App Platform AP-M8-W2 manifest-acceptance handoff

Continue the separately governed Comfforts App Platform project from its canonical dedicated
repository root.

Current status: AP-M8-W1 is owner-accepted and merged. AP-M8-W2 implements a closed Version 1
non-secret operator-manifest revision schema, bounded local loading, canonical SHA-256 revision
digests, immutable-input comparison, predecessor-chain validation, a read-only command, and
explicitly synthetic regression material. The deterministic repository gate passes for that exact
implementation.

No real operator manifest is committed or accepted. No repository setting, federation resource,
credential, IAM binding, backend, state, provider resource, image, Registration Generation, DNS
record, deployment, readback, private evidence bundle, Live (`L`) evidence, or Application Adoption
(`A`) evidence was created. Finance Assistant and its inactive Integration Draft remain unchanged
and non-authoritative. AP-M8-W3 through AP-M8-W12 remain unauthorized.

Use this handoff only after the AP-M8-W2 pull request has merged to `main`, the local `main` is
current and clean, and the owner explicitly requests the post-merge W2 manifest-acceptance
checkpoint. The owner must supply or explicitly review every exact non-secret value; the operator
does not discover or invent one. If the merge, clean-main state, owner direction, values, or
deterministic gate is absent or inconsistent, report the conflict and stop. Do not switch, pull,
reset, commit, push, or begin later work without the applicable owner approval.

Before creating a real manifest:

1. Read and follow `AGENTS.md`, including its security, source-control, secret-handling, and
   destructive-action guardrails. Finance Assistant authority does not define platform behavior.
2. Inspect the working tree, current branch, remotes, and relationship to `origin/main`. Preserve
   unrelated changes. Record the exact 40-character protected-main merge revision.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`,
   `docs/04_implementation_plan.md`, `docs/05_evaluation_strategy.md`,
   `docs/06_threat_model.md`, and `docs/repository_layout.md` completely.
4. Read `docs/runbooks/qualification_deployment.md`, `infrastructure/config/README.md`,
   `infrastructure/config/schemas/operator-input-manifest.v1.schema.json`, `contracts/README.md`,
   `fixtures/registrations/README.md`, and the validator interface before handling operator inputs.
5. Confirm AP-M8-W1 through AP-M8-W12 and AP-EVAL-M8-01 through AP-EVAL-M8-10 remain present and
   `make check` passes without credentials, backend access, external network, or repository changes.
6. State the post-merge AP-M8-W2 checkpoint and AP-PR-001 through AP-PR-009; AP-QR-001,
   AP-QR-003, AP-QR-004, AP-QR-006; ADR-001 through ADR-009; and AP-TM-007, AP-TM-008,
   AP-TM-010, AP-TM-011, AP-TM-014.
7. Treat `integrations/ai_finance_assistant/README.md` and its linked drafts as inactive,
   non-authoritative inputs. Read them only if the owner separately scopes a compatibility review;
   they cannot define generic platform behavior. Never source an operator-manifest value or
   deployment authority from them.

Next task: create the first real, non-secret manifest revision in an owner-approved private working
directory outside Git. It must bind the exact merged protected-main source and every reviewed
repository, environment, resource-name, workflow, identity, state-lineage, registration, and
evidence-destination input known before external mutation. It must contain no generated fact,
placeholder, synthetic-as-live value, secret, credential, mutable reference, cross-owner value, or
provider-discovered value.

Validate the explicit absolute path with the committed read-only command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m infrastructure.config.operator_manifest \
  /absolute/private/path/revision-1.json
```

The command must return `accepted`, revision count `1`, and one canonical digest. Present the exact
source revision, manifest digest, validation result, remaining unavailable generated facts, and
security boundary to the owner. Wait for explicit owner acceptance of that exact digest. Do not
commit the real manifest, its private path, or its contents. A rejected result or missing value
stops W2; it is not a reason to query GitHub or GCP, copy Finance Assistant values, weaken the
schema, or invent a default.

Do not begin AP-M8-W3 repository or environment settings, AP-M8-W4 federation or identities,
AP-M8-W5 backend bootstrap or migration, AP-M8-W6 deployment-support implementation, or any later
work package. Do not change repository settings, create federation or identity bindings, initialize
or migrate a backend, run an authenticated provider command, create Terraform state or a saved
plan, call GCP, change DNS or traffic, publish an image, upload or activate a generation, deploy a
resource, collect deployment or Live evidence, begin AP-M9, or change Finance Assistant. Every
later external action retains its own explicit owner checkpoint.
