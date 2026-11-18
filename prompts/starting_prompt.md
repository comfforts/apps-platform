# App Platform Terraform-and-workflow handoff

Continue the separately governed Comfforts App Platform project from its dedicated repository root.

Current status: AP-M3 supplies Contract (`C`) evidence, AP-M4 supplies deterministic Fixture (`F`)
evidence, AP-M5 supplies accepted infrastructure-planning authority, and AP-M6 implements the
networked Shared Edge and production-adapter logic locally through deterministic fakes and process-
local loopback. The complete AP-EVAL-M6 repository gate passes. AP-M7-W1 defines the exact root
interfaces, pinned toolchain, configuration contracts, work packages, and AP-EVAL-M7 static gate.
AP-M7-W2 implements the pinned CLI/provider foundation, committed root locks, local dependency
setup, and disposable-copy offline validation. AP-M7-W3 implements the five closed Version 1 non-
secret configuration schemas, synthetic examples, and bounded deterministic semantic loader.
AP-M7-W4 implements the deep backend-bootstrap root and internal state-bucket module with plan-only
mocked providers. AP-M7-W5 implements one deep internal Fixture Application module and independent
public, authenticated, and restricted roots with runtime identities, internal-only ingress,
edge-caller Invoker intent, bounded scaling, required labels, non-secret platform identity data,
and typed attachment outputs. AP-M7-W6 implements the deep Platform identity and generation
foundation: private versioned configuration storage, immutable generation metadata without upload,
Firestore Native session/TTL settings, separate edge identities, regional software ES256 signing
with manual rotation and overlap intent, version-only OAuth secret references, minimal access
intent, and typed platform outputs. AP-M7-W7 implements one deep internal Shared Edge module and
composes it into Platform State with
an immutable explicit Cloud Run candidate, closed direct-origin posture, bounded runtime profile,
three typed Fixture Application references consumed only as data, one global address and serverless
backend, managed-certificate intent, hostname-only HTTPS forwarding, and HTTP-to-HTTPS redirect.
AP-M7-W8 implements one deep platform-controls module and composes it into Platform State with a
regional seven-day minimized completion-event log bucket and internal sink, `_Default`-bucket
exclusion for Shared Edge revision logs, private 30-day evidence storage, owner-readable access
intent, notification-only USD 20 budget thresholds, dry-run-first Artifact Registry retention,
required-label and exact runtime-cap policy, and prohibited-capability assertions. It uploads no
evidence or image, exports no logs, and performs no automatic budget or cleanup mutation.
AP-M7-W9 implements five JSON-compatible YAML templates under `infrastructure/workflows/` for
advisory plan, exact-main apply, rollback, force-unlock, and destroy. They remain non-executable,
use unresolved operator placeholders, pin actions by full commit SHA, keep default permissions
read-only, grant job-local OIDC permission only for future federation, bind protected main, source,
plan, environment, subject, root, and destructive targets, retain plans only in runner temporary
storage, and record only secret-free outcome metadata.
No backend or provider operation, executable cloud workflow, actual cloud resource or IAM mutation,
generation upload or activation, DNS change, credential, deployment, Application Adoption, or Live
(`L`) evidence is implemented or qualified.

Use this handoff only after the owner accepts and commits AP-M7-W9 on the bounded AP-M7 branch. The
repository extraction handoff records that AP-M6 and the reconciliation pull request merged, the
owner explicitly declared this dedicated repository canonical, and the separately approved source
cleanup completed. If those facts or the AP-M7-W1 through AP-M7-W9 implementation are absent or
inconsistent, the working
tree contains unreviewed changes, or the requested work package is out of order, report that
conflict and stop instead of switching, pulling, resetting, committing, or combining packages
without owner direction.

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
4. Read `docs/04_implementation_plan.md` and `docs/05_evaluation_strategy.md` completely. Use only
   the accepted AP-M7 work packages and AP-EVAL-M7 gates; do not infer later implementation or
   mutation authority.
5. Read `contracts/README.md`, `fixtures/registrations/README.md`, `Makefile`, `.gitignore`, and the
   dedicated-root workflow needed to preserve default-check behavior.
6. State the active AP-M7 work package and every `AP-PR-*`, `AP-QR-*`, `ADR-*`, `AP-TM-*`,
   `AP-M7-W*`, and `AP-EVAL-M7-*` identifier it implements. Treat absent operator inputs or later
   authority as unresolved.
7. Read `integrations/ai_finance_assistant/README.md` and its linked drafts only if the owner
   separately scopes an interface-compatibility or adoption review. They remain non-authoritative,
   cannot define generic platform behavior or infrastructure, and cannot authorize Application
   Adoption.

Next task: implement AP-M7-W10, the complete Terraform-and-workflow qualification gate, as the next
small commit. Complete AP-EVAL-M7-01 through AP-EVAL-M7-10 in behavior-named tests and the default
`make check` dependency chain. Cover formatting, disposable-copy offline initialization with
`-backend=false` and the locked filesystem mirror, validation, plan-only mocked-provider tests,
static resource and workflow policy, configuration examples, history-independent extraction,
prohibited-file scanning, and all prior regressions. The gate must fail on an apply-mode Terraform
test, provider or backend access, implicit download, credential lookup, live operator value,
executable mutation workflow, skipped root, repository change, or false deployed claim. Do not
perform an authenticated plan or apply, add operator values, or begin the AP-M7-W11 status record.
Wait for owner approval before editing the next work package.

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
create state or a saved plan, or claim deployed or Live evidence. AP-M7 stays on its one bounded
branch and pull request, and work packages remain separately reviewable. Static configuration is not
provider or deployment evidence.

Keep the proposal inside the App Platform boundary. Leave Finance Assistant requirements, code,
infrastructure, Terraform state, DNS, identity configuration, deployment, and access unchanged. An
Integration Draft is not Application Adoption.

The default verification command is `make check` from the dedicated repository root. It must
remain credential-free, deterministic, and non-mutating.
