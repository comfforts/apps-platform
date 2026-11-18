# App Platform AP-M8 implementation handoff

Continue the separately governed Comfforts App Platform project from its canonical dedicated
repository root.

Current status: AP-M3 supplies Contract (`C`) evidence, AP-M4 supplies deterministic Fixture (`F`)
evidence, AP-M5 supplies accepted infrastructure-planning authority, AP-M6 implements the
networked Shared Edge and production-adapter logic locally through deterministic fakes and
process-local loopback, and AP-M7 implements the approved static Terraform-and-workflow profile.
AP-M8-W1 is complete as a qualification-deployment authority proposal. It defines AP-M8-W1 through
AP-M8-W12 and AP-EVAL-M8-01 through AP-EVAL-M8-10, and its deterministic governance checks pass.

AP-M8-W1 supplies proposal authority only. No repository setting, federation resource, credential,
IAM binding, backend, state, provider resource, image, Registration Generation, DNS record,
deployment, readback, private evidence bundle, Live (`L`) evidence, or Application Adoption (`A`)
evidence was created. Finance Assistant and its inactive Integration Draft remain unchanged and
non-authoritative. AP-M8-W2 through AP-M8-W12 remain unauthorized until their exact prerequisites
and owner checkpoints are satisfied.

Use this handoff only after the AP-M8 authority pull request has merged to `main`, the local `main`
is current and clean, and the owner explicitly accepts the complete AP-M8-W1 authority and requests
AP-M8-W2. If the merge, clean-main state, explicit owner acceptance, requested package, or
deterministic gate is absent or inconsistent, report the conflict and stop. Do not switch, pull,
reset, commit, push, or begin later work without the applicable owner approval.

Before editing:

1. Read and follow `AGENTS.md`, including its security, source-control, secret-handling, and
   destructive-action guardrails. Finance Assistant authority does not define platform behavior.
2. Inspect the working tree, current branch, remotes, and relationship to `origin/main`. Preserve
   unrelated changes and require a dedicated branch for the approved AP-M8-W2 slice.
3. Read `docs/README.md`, `GLOSSARY.md`, `docs/01_product_requirements.md`,
   `docs/02_architecture_decision_records.md`, `docs/03_system_design.md`,
   `docs/04_implementation_plan.md`, `docs/05_evaluation_strategy.md`,
   `docs/06_threat_model.md`, and `docs/repository_layout.md` completely.
4. Read `docs/runbooks/qualification_deployment.md`, `contracts/README.md`,
   `fixtures/registrations/README.md`, `Makefile`, `.gitignore`,
   `infrastructure/config/README.md`, and `infrastructure/workflows/README.md` before changing an
   interface, evidence boundary, operator authority, or repository path.
5. Confirm AP-M8-W1 through AP-M8-W12 and AP-EVAL-M8-01 through AP-EVAL-M8-10 remain present and
   `make check` passes without credentials, backend access, external network, or repository changes.
6. State the AP-M8-W2 slice and every applicable `AP-PR-*`, `AP-QR-*`, `ADR-*`, and `AP-TM-*`
   identifier. Treat a missing operator value or downstream authority as a blocker rather than
   inferring, discovering, or inventing it.
7. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior or infrastructure, and cannot authorize deployment or
   Application Adoption.

Next task: implement AP-M8-W2 only as a bounded, non-secret operator-input manifest and its
deterministic validation. The initial append-only revision records every then-known reviewed value:
the exact protected source, environment and resource names, immutable digests already available,
identity and secret-version references, registration inputs, fixed backend prefixes, and private
evidence destination. Generated facts that do not yet exist—such as image, state-lineage, plan,
configuration-object, or run digests—may enter only through immutable successor revisions that name
their predecessor and receive fresh approval before use. The exact protected-main source revision
is recorded after merge; no commit is required to contain its own future identifier.

Reject a missing, placeholder, secret-bearing, mutable, cross-owner, synthetic-as-live, discovered,
or unapproved value. A missing value stops AP-M8-W2. Do not query a provider, copy Finance Assistant
values, use authenticated discovery, create a credential, or invent a default to complete the
manifest. Leave the implementation uncommitted for owner review when commit-by-commit review is
requested.

Do not begin AP-M8-W3 repository or environment settings, AP-M8-W4 federation or identities,
AP-M8-W5 backend bootstrap or migration, AP-M8-W6 deployment-support implementation, or any later
work package. Do not change repository settings, create federation or identity bindings, initialize
or migrate a backend, run an authenticated provider command, create Terraform state or a saved
plan, call GCP, change DNS or traffic, publish an image, upload or activate a generation, deploy a
resource, collect deployment or Live evidence, begin AP-M9, or change Finance Assistant. Every
later external action retains its own explicit owner checkpoint.

The default verification command remains `make check` from the dedicated repository root. It must
stay credential-free, deterministic, offline, extraction-safe, and non-mutating.
