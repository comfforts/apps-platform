# App Platform Terraform-and-workflow handoff

Continue the separately governed Comfforts App Platform project from its dedicated repository root.

Current status: AP-M3 supplies Contract (`C`) evidence, AP-M4 supplies deterministic Fixture (`F`)
evidence, AP-M5 supplies accepted infrastructure-planning authority, and AP-M6 implements the
networked Shared Edge and production-adapter logic locally through deterministic fakes and process-
local loopback. The complete AP-EVAL-M6 repository gate passes. No Terraform configuration,
backend, workflow authority, cloud resource, DNS change, credential, deployment, Application
Adoption, or Live (`L`) evidence is implemented or qualified merely because those earlier slices
exist.

Use this handoff only from updated `main` after the AP-M6 and repository-reconciliation pull
requests have merged and the owner has explicitly declared the dedicated repository canonical. If
those conditions are not recorded, the working tree is not clean, or the requested branch already
contains AP-M7 changes, report that conflict and stop instead of switching, pulling, resetting,
committing, or combining slices without owner direction.

Before editing:

1. Read and follow `AGENTS.md` in the App Platform repository root, including its security,
   source-control, secret-handling, and destructive-action guardrails. Finance Assistant authority
   does not define platform behavior.
2. Inspect the working tree, branch, and relationship to `main`. Preserve unrelated changes and
   report any state that conflicts with the incremental delivery sequence instead of resetting,
   pulling, switching, or committing without owner direction.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`,
   `docs/06_threat_model.md`, and `docs/repository_layout.md` completely.
4. Read `docs/04_implementation_plan.md` and `docs/05_evaluation_strategy.md` completely. Treat the
   current AP-M7 text and AP-EVAL-M7 future boundary as inputs to a detailed authority proposal,
   not as sufficient authority to implement Terraform or workflows.
5. Read `contracts/README.md`, `fixtures/registrations/README.md`, `Makefile`, `.gitignore`, and the
   dedicated-root workflow needed to preserve default-check behavior.
6. State the proposed AP-M7 slice and every `AP-PR-*`, `AP-QR-*`, `ADR-*`, `AP-TM-*`, `AP-M7`, and
   `AP-EVAL-M7` identifier it implements. Treat absent detailed work packages, configuration
   contracts, evaluation commands, and acceptance authority as unresolved.
7. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior or infrastructure, and cannot authorize Application
   Adoption.

Next task: propose AP-M7, the smallest Terraform-and-workflow implementation-authority slice. It
must refine the system design, implementation plan, threat controls, repository layout, and
AP-EVAL-M7 before implementation. Identify the exact documents, configuration contracts, Terraform
roots and reusable modules, workflow templates, static policy checks, deterministic tests, small
commits, and acceptance boundary it would add or update. Wait for owner approval before editing.

The proposal must preserve separate backend-bootstrap, Platform State, and per-Fixture-Application
State roots; typed non-secret cross-state inputs without `terraform_remote_state`; explicit plan,
apply, rollback, unlock, and destroy authorities; source-revision binding; extraction-safe workflow
templates; and credential-free formatting, validation, policy, and configuration tests. Reusable
modules must not own environment state or silently embed operator-specific values.

Treat globally unique bucket names, protected workflow subjects and environment, DNS managed-zone
resource, OAuth client references, notification destination, and the initial Live Registration Set
as unresolved operator inputs. The repository identity is fixed as `comfforts/apps-platform`, but
that fact creates no federation or mutation authority. Separate reviewed configuration from
reusable behavior rather than querying a provider or inventing defaults.

Do not initialize a Terraform backend, run an authenticated plan or apply, create or read a
credential, call GCP, modify repository settings, configure identity or DNS, deploy a service,
create state or a saved plan, or claim deployed or Live evidence. AP-M7 belongs on a new bounded
branch and pull request only after AP-M6 and the repository-reconciliation pull requests merge and
the owner declares the canonical cutover. Static configuration is not provider or deployment
evidence.

Keep the proposal inside the App Platform boundary. Leave Finance Assistant requirements, code,
infrastructure, Terraform state, DNS, identity configuration, deployment, and access unchanged. An
Integration Draft is not Application Adoption.

The default verification command is `make check` from the dedicated repository root. It must
remain credential-free, deterministic, and non-mutating.
