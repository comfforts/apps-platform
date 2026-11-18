# App Platform AP-M8 authority handoff

Continue the separately governed Comfforts App Platform project from its canonical dedicated
repository root.

Current status: AP-M3 supplies Contract (`C`) evidence, AP-M4 supplies deterministic Fixture (`F`)
evidence, AP-M5 supplies accepted infrastructure-planning authority, and AP-M6 implements the
networked Shared Edge and production-adapter logic locally through deterministic fakes and process-
local loopback. AP-M7-W1 through AP-M7-W11 implement the approved static Terraform-and-workflow
profile. The complete AP-EVAL-M7 repository gate passes: exact Terraform and provider constraints,
five independent roots, Version 1 non-secret configuration contracts, internal modules, plan-only
mocked-provider tests, inert operator-workflow templates, offline extraction, prohibited-artifact
scanning, and every prior regression gate are covered.

AP-M7 supplies repository implementation evidence only. No backend was initialized; no provider,
repository-setting, federation, credential, IAM, DNS, cloud, deployment, rollback, recovery, or
destroy operation ran; and no Live (`L`) or Application Adoption (`A`) evidence exists. Finance
Assistant and its inactive Integration Draft remain unchanged and non-authoritative.

Use this handoff only after the AP-M7 pull request has merged to `main`, the local `main` is updated
and clean, and the owner explicitly requests an AP-M8 authority proposal. If the merge, clean-main
state, owner direction, or AP-M7 gate is absent or inconsistent, report the conflict and stop. Do
not switch, pull, reset, commit, push, or begin later work without the applicable owner approval.

Before editing:

1. Read and follow `AGENTS.md`, including its security, source-control, secret-handling, and
   destructive-action guardrails. Finance Assistant authority does not define platform behavior.
2. Inspect the working tree, current branch, remotes, and relationship to `origin/main`. Preserve
   unrelated changes and require a dedicated branch for the approved AP-M8 authority slice.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`,
   `docs/04_implementation_plan.md`, `docs/05_evaluation_strategy.md`,
   `docs/06_threat_model.md`, and `docs/repository_layout.md` completely.
4. Read `contracts/README.md`, `fixtures/registrations/README.md`, `Makefile`, `.gitignore`,
   `infrastructure/config/README.md`, and `infrastructure/workflows/README.md` before changing an
   interface, evidence boundary, operator authority, or repository path.
5. Confirm AP-M7-W1 through AP-M7-W11 and AP-EVAL-M7-01 through AP-EVAL-M7-10 remain present and
   `make check` passes without credentials, backend access, external network, or repository changes.
6. State the proposed AP-M8 slice and every applicable `AP-PR-*`, `AP-QR-*`, `ADR-*`, and
   `AP-TM-*` identifier. AP-M8 work-package identifiers and a complete AP-EVAL-M8 are currently
   absent downstream authority; treat them as unresolved rather than inferred.
7. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior or infrastructure, and cannot authorize deployment or
   Application Adoption.

Next task: propose the detailed AP-M8 non-production qualification-deployment authority as a
documentation-and-governance slice. Define bounded work packages, exact operator prerequisites,
protected repository and environment controls, federation and identity boundaries, backend
bootstrap and state-lineage procedure, authenticated plan and apply separation, root ordering,
partial-failure stops, rollback and recovery authority, DNS/TLS checkpoint, readback, evidence
schema, redaction, pass/fail/skip semantics, exact source binding, and AP-EVAL-M8. Keep every real
operator value unresolved. Wait for explicit owner approval of that authority before implementing
it or performing any operator action.

The proposal must preserve separate backend-bootstrap, Platform State, and per-Fixture-Application
State roots; typed non-secret cross-state inputs without `terraform_remote_state`; explicit plan,
apply, rollback, unlock, and destroy authorities; exact source and plan-digest binding; protected
environment review; stop-on-partial-failure behavior; and a clear boundary between deployment
evidence and future AP-M9 Live evidence.

Treat globally unique bucket names, protected workflow subjects and environment, Workload Identity
Federation resources, service accounts and bindings, DNS managed-zone resource, immutable image
digests, OAuth client references, billing and notification references, and the initial Live
Registration Set as unavailable operator inputs. Do not query a provider, copy Finance Assistant
values, create credentials, or invent defaults to complete the proposal.

Do not change repository settings, create federation or identity bindings, initialize or migrate a
backend, run an authenticated provider command, create Terraform state or a saved plan, call GCP,
change DNS or traffic, publish an image, upload or activate a generation, deploy a resource, collect
Live evidence, begin AP-M9, or change Finance Assistant. AP-M8 remains a separate owner-approved
branch and pull request after its authority is accepted.

The default verification command remains `make check` from the dedicated repository root. It must
stay credential-free, deterministic, offline, extraction-safe, and non-mutating.
