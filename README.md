# Comfforts App Platform

Comfforts App Platform is the shared entry point for independently owned applications under a
Comfforts hostname. It gives a human operator one interactive lifecycle for creating and inspecting
the shared edge, handing platform values to applications, registering their deployed attachments,
qualifying the complete environment, and safely removing platform-owned resources.

The platform coordinates only what must be shared: hostname-level networking, TLS, catalogue,
routing, admission, platform identity, application registration, and environment lifecycle. Each
application keeps control of its runtime, data, stores, providers, secrets, principals, feature
authorization, deployment, and Terraform state.

The product is designed for two isolated environments:

- staging at `apps-staging.comfforts.com`; and
- production at `apps.comfforts.com` after its existing ownership is explicitly transferred.

## What the platform owns

| Platform-owned | Application-owned |
| --- | --- |
| Shared hostname edge, address, load balancing, and TLS | Application runtime and ingress-compatible attachment |
| Root catalogue and application route reservations | Application data, stores, queues, and providers |
| Google OAuth client, platform sessions, Platform Member Directory, and assertion signing | Application users, principals, account linking, and feature entitlements |
| Admission before a request reaches an application | Authorization after the application receives a request |
| Registration Generations and platform configuration | Application releases and Application State |
| Platform Integration Bundles | Application Attachment Bundles |
| Platform State, qualification evidence, and safe platform destruction | Application deployment, recovery, and destruction |

A reference may cross this boundary; ownership does not. The platform does not read an
application's Terraform backend, and a platform destroy never destroys Application State.

## Application categories

The platform does not assign one mutually exclusive application type. Each Application
Registration combines independent admission, catalogue, lifecycle, and ownership classifications.
Changing one does not silently change the others.

### Admission mode

Admission mode decides who may reach the application through the Shared Edge:

| Mode | Who can reach the application | Identity delivered to the application |
| --- | --- | --- |
| `public` | Anonymous visitors; authentication is not required | Explicitly `none` or `optional`; optional delivery occurs only after the visitor chooses platform login and has a valid Platform Session |
| `authenticated` | Any identity successfully authenticated by the configured platform identity provider | Required short-lived signed assertion scoped to that application |
| `restricted` | Only authenticated identities with an active entry in the environment's Platform Member Directory | Required application-scoped signed assertion after current membership succeeds |

`public` describes only the platform's admission decision. A public application may remain fully
anonymous, or its Application Owner may add application-owned authentication, including a separate
OAuth client. That authentication, its client and secret, its sessions, and the resulting
application identity remain outside platform ownership. Adding it does not change the registration
to `authenticated` and does not turn an application-issued identity into Verified Identity Context.
If the application instead declares optional Platform Identity, it may offer the platform login
flow and must verify the resulting assertion by the same rules described below. An unrelated
ambient Platform Session does not override an Identity Delivery policy of `none`.

Applications registered as `authenticated` or `restricted` rely on platform admission for their
platform-route visitor identity. After admission, each application must independently verify the
platform assertion's signature, issuer, application-specific audience, time bounds, and contract
version before deriving an Application Principal. It receives neither the platform OAuth client
secret nor the identity provider's original token. A `restricted` application additionally
benefits from the Shared Edge's current Platform Member Directory lookup, but still performs the
same assertion verification as an `authenticated` application.

Membership is platform-wide within one environment, not a member list in each registration. An
environment with only its explicitly enrolled Platform Owner is owner-only for every restricted
route. Email is not a membership or ownership key. Admission decides whether a request may reach
the application; the application still decides its own users, principals, data access, roles,
provider rights, and feature entitlements.

Platform deployment creates the directory infrastructure but does not enroll the active Cloud
Operator automatically. The Platform Owner is enrolled through a separate confirmed operation, and
later membership changes do not redeploy an application or activate a Registration Generation.
Only the current visitor's minimal signed context may cross an application boundary; the directory
and other members never do.

> **Implementation status:** ADR-015 accepts this model. AP-M9-W10 Slices 1 through 7 implement
> the Version 2 contracts and migration, isolated directory infrastructure and IAM, and
> deterministic dual-version Shared Edge enforcement plus separately confirmed owner enrollment
> and bounded member lifecycle commands, Version 2 application handoffs, fixture consumption, and
> atomic complete-generation activation. Qualification readiness reuses those same member
> operations, verifies current-request restricted decisions, restores the reviewed owner-only
> baseline, and blocks rollback on any mismatch. All repository slices and candidate-readiness
> corrections are integrated; exact-revision Candidate Source qualification remains. The
> deployed W9 candidate and Version 1 contracts remain predecessor evidence and are not Accepted
> Source qualification for this model.

### Catalogue visibility

Catalogue visibility is independent of admission:

| Visibility | Root catalogue behavior |
| --- | --- |
| `listed` | An active application appears in the root catalogue with its safe title, summary, route, and admission label |
| `unlisted` | The application is omitted from the catalogue but its route and admission policy still work |

An unlisted route is not a secret route and does not weaken authentication or restricted
membership. Any admission mode may be listed or unlisted.

### Lifecycle state

Lifecycle state controls whether the application is routable and whether it can return later:

| State | Behavior |
| --- | --- |
| `active` | The route is enabled and catalogue visibility and admission are enforced |
| `suspended` / detached | The route and identifier remain reserved, no target is invoked, and the platform returns a temporary `503`; a replacement attachment may reactivate it |
| `retired` | The route and identifier remain as a terminal tombstone, no target is invoked, and the platform returns `410`; it cannot reactivate |

Registration compiles a complete active candidate generation before changing the active-generation
pointer. Candidate publication is an internal deployment step, not an application lifecycle state.
Until atomic activation succeeds, a new application remains absent and an existing application
continues through the preceding generation.

Detachment is the operator-facing reversible maintenance action that produces the suspended state.
Retirement is permanent and is not used for a temporary outage, deployment test, or application
replacement.

### Fixture and adopted applications

A Fixture Application is a repository-owned synthetic application used to qualify platform
behavior. Its runtime, images, and independent Terraform roots live in the dedicated fixture
application project, not the platform project. That project attaches to the platform Shared VPC as
a service project; all-traffic Direct VPC egress uses the platform-owned application-subnet Cloud
NAT while ingress and Cloud Run invocation remain restricted. It exchanges the same project-scoped
integration and attachment bundles as a real application. A real application remains outside platform authority until its Application
Owner connects its project, adopts the platform contracts, and performs its own deployment and
release process.

The included fixture suite demonstrates the three admission modes:

| Fixture | Admission | Catalogue | What it demonstrates |
| --- | --- | --- | --- |
| `fixture-public` | Public | Listed | Anonymous routing plus explicit no-identity and optional-Platform-Identity behavior |
| `fixture-authenticated` | Authenticated | Unlisted | Platform login, verified identity delivery, and application assertion verification |
| `fixture-restricted` | Restricted | Listed | Platform-wide member allow/deny while application-owned feature authorization remains separate |

These fixtures are qualification assets, not templates that force a real application into the same
visibility or product behavior. All initial provider-backed attachments use the same Cloud Run
attachment contract regardless of admission mode.

## How the platform works

The environment and application lifecycles meet through two non-secret, digest-bound bundles:

```text
Platform Operator
    |
    | platform-deploy
    v
Shared Edge + identity + DNS/TLS intent
    |
    | application-handoff-check -> platform-outputs
    v
Platform Integration Bundle
    |
    | consumed by the Application Owner
    v
application deploys its own runtime and state
    |
    | returns an Application Attachment Bundle
    v
platform-register -> immutable Registration Generation -> routed application
```

That is the contract sequence for every application, including repository-owned fixtures. The
platform first connects the application project. `application-handoff-check` then performs a
read-only rehearsal of the platform Terraform boundaries and verifies the application project's
required services, Shared VPC connection, platform-owned application-subnet egress, bundle inputs,
and access-mode prerequisites.
`platform-outputs` creates the project- and application-scoped Platform Integration Bundle only
after those checks are ready. The application deployment consumes that bundle and returns an
Application Attachment Bundle. Only `platform-register` can activate the route.

For fixtures, `fixture-handoff` is the application-owned middle of that sequence. It builds and
deploys one selected fixture in the dedicated fixture project, validates its live target, writes
the canonical bundle pair and registration intent beneath `.platform-operator/`, prints their
paths and digests, and stops. It never registers or routes the fixture. There is intentionally no
combined `fixture-deploy` command: keeping `platform-outputs`, fixture runtime deployment, and
`platform-register` visible proves the same ownership handoff required by an external application.

Environment operation follows this lifecycle:

```text
preflight (optional readiness check; no lifecycle state)
   |
   v
prepare -> approve -> deploy -> status -> outputs -> qualify -> destroy
                                      |
                                      v
                 application deploy -> register -> detach/reactivate or retire
```

`platform-deploy` is the normal entry point. In one interactive process it performs read-only
platform readiness checking, stops before approval if that check is blocked, performs preparation,
displays one complete Deployment Specification, requests approval, creates and shows fresh exact
Terraform plans, applies only confirmed plans, pauses for Google OAuth and Squarespace DNS work,
verifies readable results, and atomically records private resume progress. A readiness result of
`reconciliation-required` or `incomplete` does not authorize a mutation; it tells deployment which
fresh exact stage plans must still be reviewed.

`platform-preflight` is the optional readiness-only command. Use it to find missing tools or
authentication, a wrong project, an ownership conflict, source drift, or another current blocker.
It prints the selected operation and scope, profile path and digest, complete Git source snapshot,
and each bounded non-secret GitHub, GCP, Terraform, and DNS discovery result. A blocked check pairs
its stable machine code with plain-language guidance. It creates no specification, digest,
approval, progress record, plan, private deployment working state, or external mutation.
It is not a required predecessor to `platform-deploy`.

Operational preflight is the default and enforces Accepted or Candidate Source admission. During
local maintenance, run the same real read-only checks without admitting the working tree as an
operational source:

```bash
make platform-preflight-check ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
```

Development preflight deliberately skips `SOURCE_NOT_CLEAN` because inspecting uncommitted changes
is its purpose. It reports other unpushed, stale, or non-main source findings as non-blocking source
diagnostics while continuing to enforce profile, authentication, project, tool, and discovery
checks. Its result distinguishes `ready` for development from `operational_ready`. This mode exists
only for preflight; it cannot prepare, approve, plan, deploy, publish a bundle, qualify, or mutate an
external system.

Before committing or pushing a platform change, run the deeper read-only rehearsal:

```bash
make platform-deploy-check ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
```

It validates retained private specifications and progress, renders the working-tree Terraform,
refreshes real remote state without locking it, and applies the normal plan policy to every stage
whose inputs already exist. It reports stages as `pass`, `would-change`, `manual`, `deferred`, or
`blocked`, and classifies the platform as `ready`, `reconciliation-required`, `incomplete`, or
`blocked`. Platform readiness includes required platform services, Platform State, Shared VPC,
application subnet, Cloud Router, Cloud NAT, Shared Edge, active runtime, TLS, and final readback.
It never approves intent, applies a plan, executes a provider action, changes current progress, or
grants Accepted or Candidate Source authority. `ready` remains a read-only result; apply-time and
manual-checkpoint failures remain possible.

Operator narration is written to standard error. The final compact JSON result remains the only
standard-output record, so a human receives a readable execution trace while automation can parse
stdout without filtering progress messages. Traces never include access tokens, secret values,
raw provider responses, Terraform state, or saved-plan content.

Read-only gcloud account, project, billing, identity-token, and Application Default Credential
checks retry once when the command times out or returns a failure. A persistent failure names the
exact read boundary instead of collapsing every prerequisite into one session error. Failed
session reads and Cloud Build submissions retain their exact command streams only under the
ignored private diagnostics directory and print the local paths and digest; successful or recovered
reads create no diagnostic artifact.

`platform-prepare` is a separate optional specification-review command. It performs the readiness
checks, writes the complete private specification, prints its digest, and requests approval, but
performs no external mutation. A later `platform-deploy` automatically finds that current approved
specification, revalidates its source, profile, environment, session, project, ownership, tools,
and readable provider facts, and reuses it when those bindings remain valid.
The operator does not need to copy its digest. If no current valid approval exists,
`platform-deploy` performs preparation, review, and approval before continuing.

The Shared Edge exposes the catalogue and owns route selection and admission. Applications using
`authenticated` or `restricted` admission independently verify the short-lived,
application-specific platform assertion. Separately, every initial application attachment,
including a public one, accepts traffic only from the Shared Edge rather than through arbitrary
direct origin invocation. Platform admission never grants an application feature entitlement.

The Shared Edge runs under its platform runtime identity but uses short-lived impersonated
credentials for the separate edge-caller identity when it reads an attached Cloud Run service and
invokes it. Each application-owned service grants that caller only Cloud Run Viewer and Invoker on
the exact service. No service-account key is created or stored.

## Repository structure

| Path | Purpose |
| --- | --- |
| [`edge/`](edge/README.md) | Shared Edge runtime, identity, routing, proxy, limits, and provider adapters |
| `contracts/` | Public registration, identity, ownership, lifecycle, and bundle contracts |
| `fixtures/` | Deterministic synthetic applications and registration generations |
| `infrastructure/operator/` | Interactive platform and fixture lifecycle product |
| `infrastructure/terraform/` | Bootstrap, Platform State, and independent fixture roots |
| `infrastructure/config/` | Reviewed non-secret environment and infrastructure profiles |
| `infrastructure/backend/` | Backend rendering, plan policy, and lineage controls |
| `docs/` | Requirements, decisions, design, evaluation, status, history, and runbooks |
| `tests/` | Credential-free deterministic contract, runtime, infrastructure, and operator checks |

The implementation uses Python 3.12 or newer for the runtime and operator, frozen Python
dependencies in `uv.lock`, and checksum-pinned Terraform and provider dependencies installed into
ignored project-local paths.

## Set up the repository

Prerequisites for repository development are Git, Make, `uv`, and a supported Python 3
interpreter. From the repository root:

```bash
uv sync --frozen --python 3.12
make terraform-setup
make check
```

`make terraform-setup` downloads and verifies the pinned Terraform CLI and provider packages into
the ignored local cache. `make check` then runs the complete deterministic gate without a cloud
credential, provider request, external network call, backend operation, or external mutation.

The runtime tests bind only ephemeral process-local loopback listeners. A restricted execution
sandbox must permit localhost binding for the complete gate to pass.

## Prepare for an operator session

Read the [environment lifecycle runbook](docs/runbooks/environment_lifecycle.md) before operating a
Platform Environment. Here, an environment means one isolated staging or production deployment
with its own hostname, cloud project, state, identity, OAuth client, DNS/TLS resources,
registrations, and evidence. A real staging session additionally requires:

- a clean source revision admitted as Accepted Source or staging-only Candidate Source;
- the pinned local Terraform toolchain;
- `gcloud` and `dig` available locally;
- an active human Cloud SDK login for the exact environment project;
- user Application Default Credentials;
- access to the Google OAuth and Secret Manager console surfaces used by the wizard; and
- access to the external Squarespace DNS record for the staging hostname.

Generated specifications, approvals, progress, bundles, plans, and private command results live
beneath the ignored `.platform-operator/` directory. Directories use mode `0700` and private files
use mode `0600`. Do not copy that directory into Git or use it as shared application configuration.
`current-progress.v1.json` remains the resumable working record. Each succeeded, failed, or cancelled
deployment also retains its latest terminal result under
`environments/<environment>/progress/<specification-digest>.final.v1.json`, so an operator can
compare outcomes across specifications without retaining every intermediate stage update.
The workflow named by a specification is versioned independently from that progress-file format.
A completed predecessor workflow remains readable historical evidence after the executable stage
sequence changes; status labels it `historical` and never invents newly added stage results. Before
preparing the current workflow, the wizard explains the difference and asks whether to supersede
only the private current pointers. Declining leaves every pointer and record unchanged. Accepting
retains the predecessor specification and terminal snapshot, then uses fresh current-workflow
progress when deployment begins.

The wizard never asks for an OAuth client secret in the terminal. The operator enters the secret
directly into the approved Secret Manager surface and presses Enter only after completing the exact
manual instruction displayed by the running process.

## Operate a platform environment

### Readiness preflight

Run the readiness-only command whenever you want to resolve prerequisites before an operator
session:

```bash
make platform-preflight ENVIRONMENT=staging
```

It reports `ready` or `blocked` with exact blocker codes. It does not install a missing tool,
change authentication or project selection, resolve ownership, write operator state, or publish a
specification digest. Correct the reported prerequisite and rerun it. The command is optional:
`platform-deploy` performs the same checks before any mutation.

While changing the repository locally, use `make platform-preflight-check` for prerequisite checks
and `make platform-deploy-check` for the complete read-only deployment rehearsal described above.
Both accept a dirty working tree and omit `SOURCE_NOT_CLEAN`. Other source-admission findings remain
visible without treating that tree as operational source.

### Optional specification preparation and review

Run preparation before deployment only when you want to review and approve the complete
specification before the deployment window or with another person:

```bash
make platform-prepare ENVIRONMENT=staging
```

The command reports whether the specification is complete and approved and prints its
`specification_digest`. If the same source, profile, environment, session, project, ownership,
tools, and discovered inputs remain valid, the normal deployment command automatically selects
that exact prepared specification:

```bash
make platform-deploy ENVIRONMENT=staging
```

No digest copy-and-paste is required. If the stored specification is absent, stale, or not approved,
`platform-deploy` prepares, displays, and approves a fresh specification before continuing. A
malformed retained specification or a current source/provider blocker stops the command instead of
silently replacing evidence. `SPECIFICATION_DIGEST=sha256:<digest>` remains available when an
operator deliberately needs to pin an explicit current digest, but it is not part of the normal
prepare-to-deploy sequence. Do not run `platform-prepare` merely as a routine extra step—the
ordinary one-command deployment sequence starts with `platform-deploy`.

If the current pointers still identify a successfully completed predecessor workflow,
`platform-prepare` or the preparation phase of `platform-deploy` prints its source, digest, status,
and stage count before asking a separate `y/N` question. This confirmation changes no cloud
resource. It only permits the new specification to become current; exact plan and action
confirmations still occur later. A running or waiting predecessor is not eligible for this path and
must be continued from its exact source or explicitly closed with `platform-cancel`.

### Accepted staging operation

Accepted Source is the default. It requires a clean current `main` revision. The normal staging
journey begins with two one-time project operations:

```bash
make fixture-project-bootstrap \
  ENVIRONMENT=staging \
  FIXTURES_PROJECT_ID=comfforts-fixtures-nonprod \
  FIXTURES_PROJECT_NAME="Comfforts Fixtures Non-Prod"
make platform-deploy ENVIRONMENT=staging
make platform-connect-project \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod
```

`fixture-project-bootstrap` creates or repairs only the dedicated fixture application project,
its required services, its private versioned state bucket, and its image repository. It is
idempotent and normally runs only once unless that project is deleted. Google Cloud assigns the
project number when the project is created; the bootstrap command reads it back and prints it. The
operator does not configure a fixture project-number variable. `platform-connect-project` reads
that number again and persists it in the private project-connection record used by bundle and
runtime operations. `platform-connect-project`
attaches the application project to the platform Shared VPC and grants its Cloud Run service agent
read-only host-network discovery plus network-user access only on the application subnet. It is
also idempotent. Neither command creates a fixture runtime or route.

For each selected fixture, use the full platform/application handoff. This example shows the
public fixture; use the corresponding application ID, admission mode, and route for the other two:

```bash
make platform-status ENVIRONMENT=staging

make application-handoff-check \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod \
  APPLICATION_ID=fixture-public \
  ACCESS_MODE=public \
  IDENTITY_DELIVERY=none \
  ROUTE_INTENT=/fixture-public \
  PLATFORM_SOURCE_REVISION=<active-platform-revision> \
  PLATFORM_GENERATION=<active-registration-generation>

make platform-outputs \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod \
  APPLICATION_ID=fixture-public \
  ACCESS_MODE=public \
  IDENTITY_DELIVERY=none \
  ROUTE_INTENT=/fixture-public \
  PLATFORM_SOURCE_REVISION=<active-platform-revision> \
  PLATFORM_GENERATION=<active-registration-generation>

make fixture-handoff \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-public \
  CATALOGUE_VISIBILITY=listed \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v2.json

# Inspect the three paths printed by fixture-handoff without editing them.
make platform-register \
  ENVIRONMENT=staging \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v2.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.v2.json \
  REGISTRATION_INTENT=/private/path/registration-intent.v2.json

make fixture-status ENVIRONMENT=staging APPLICATION_ID=fixture-public
```

The status result reports the active registration's `catalogue_visibility` (`listed` or
`unlisted`) beside lifecycle, target, and route readiness; it does not infer visibility from the
catalogue page.

Repeat that application-scoped sequence for `fixture-authenticated` with
`ACCESS_MODE=authenticated IDENTITY_DELIVERY=required` and for `fixture-restricted` with
`ACCESS_MODE=restricted IDENTITY_DELIVERY=required`. Public applications may instead select
`IDENTITY_DELIVERY=optional` through the same explicit handoff. No command infers public identity
delivery from an ambient Platform Session. After the required fixtures are active, run
`platform-qualify` and `platform-status`.

`platform-qualify` is not wholly read-only and requires
`OWNER_MEMBER_REFERENCE=<reviewed-opaque-owner-reference>`. It first verifies source, provider,
DNS/TLS, routing, identity, isolation, transport, and redaction. It then uses the existing member
service to verify the owner-only baseline; add a separately verified second member; prove
allow/suspend-and-deny/reactivate-and-allow/remove-and-deny decisions on the next request; and
verify the owner-only baseline again. A failed step attempts removal reconciliation and reports a
restoration-required blocker if the final baseline is not exact. The owner reference and temporary
member reference are not written to qualification evidence.

Only when every prerequisite passes does qualification offer the live rollback exercise. The
terminal explains that the exercise temporarily
moves 100 percent of staging traffic to the reviewed predecessor, asks for exact rollback
confirmation, verifies the change, then asks for exact restoration confirmation and verifies that
the original generation is again serving all traffic. While the predecessor is active, two
separately confirmed browser checks first establish a Platform Session and then prove that the
predecessor's public `none` policy withholds Platform Identity. Restoration is still attempted if
that proof fails. Keep the command running through every browser and generation confirmation. If
any earlier check fails, rollback is recorded as blocked and traffic is not changed.

The active-generation routing identity check uses exactly four browser actions, and the command
asks `y/N` immediately before each one. The first clears any existing Apps Platform session and
asks the operator to sign in with the exact reviewed staging account. The second reuses that
session to prove optional identity delivery to the public fixture. The third verifies restricted
admission. The fourth logs out, verifies server-side session deletion, and returns through the
public fixture with identity absent and without starting another login. Declining a browser action
stops qualification with a blocker naming the unconfirmed step; the command never opens the next
tab on its own.

The temporary-member exercise has its own separately confirmed browser actions. Member `add`
performs the normal one-use Visitor verification. Each of the four post-transition checks then
asks before opening the browser and returns only the coarse current decision for
`fixture-restricted` to loopback. Cookies, identity claims, directory records, and provider
payloads remain in their owning boundaries.

A repository revision change alone does not require another `platform-deploy`. Fixture commands
validate their own current source independently, then consume the provider-verified active
platform revision and Registration Generation recorded in the Platform Integration Bundle. Run
`platform-deploy` first only when platform-owned runtime, Terraform, configuration, identity,
networking, DNS/TLS, or another shared resource must change. An accepted qualification still
requires the platform itself to have been deployed and qualified from Accepted Source.

When a platform runtime update is requested, `platform-deploy` preserves the active Registration
Generation, stages a source-bound Shared Edge revision, verifies its exact image and configuration
binding, moves traffic to that revision, and verifies the active binding again. This keeps every
currently registered route on the same catalogue while the edge implementation changes. External
application revisions remain independent and do not require a platform redeployment.

`fixture-handoff` is mutating: it deploys or reconciles only the selected fixture's Application
State, but stops before Registration Generation activation. The inspection boundary is mandatory
for fixtures because the fixture flow deliberately demonstrates the same separate-owner handoff as
a real application. Rerunning the handoff reuses the exact prepared pair only while the source,
project connection, platform generation, image, bundle digests, and live target remain current.
`fixture-status` is suite-wide by default, or narrowed with an optional `APPLICATION_ID`, so an
operator can inspect the whole qualification suite or diagnose one fixture without mutation. Each
application row includes the active registration's `catalogue_visibility` as well as lifecycle,
target, and route readiness.

`platform-deploy` remains active across OAuth and DNS checkpoints. Ordinary reviewed plans use one
`y/N` confirmation. Typed confirmation is reserved for destruction, retirement, ownership
transfer, and other irreversible operations.

The DNS checkpoint first uses `dig` against every authoritative name server plus `1.1.1.1` and
`8.8.8.8`. If the exact address and authoritative TTL are already verified, the wizard says that
no DNS change is required; otherwise it opens Squarespace and asks the operator to add or update
only the displayed record. After Enter, the same readback must pass before the stage closes. The
following managed-certificate readback prints its progress every 30 seconds and waits for up to one
hour. Explicit certificate or domain-validation failures stop immediately; only a genuine
provisioning state waits. If it is still provisioning after the bound, the command returns a
resumable `waiting` result without removing the verified DNS record or platform resources.

If an operation is interrupted, rerun the same command with the same environment and source
authority. The lifecycle validates its private progress and resumes after the last closed stage. A
cancelled operation remains terminal until a same-source, same-specification rerun displays its
last closed stage, open stage, and cancellation blocker and receives a separate `y/N` resume
confirmation. Accepting retries only the open stage and preserves every remaining plan/action
confirmation. Declining leaves the progress record unchanged. A
changed source, specification, environment, or scope cannot resume that exact operation. When the
operator deliberately wants to abandon the old private resume position and reconcile from new
source, run the `platform-cancel` command printed with `ACTIVE_OPERATION_CONFLICT`, review its exact
source, specification, and stage summary, and confirm the cancellation. Cancellation atomically
closes only the private progress record; it does not change Terraform state or cloud resources.
Rerunning cancellation is an unchanged no-op. The next `platform-deploy` prepares fresh intent and
uses fresh plans and provider readback to reconcile resources that already exist. The lifecycle
never automatically unlocks state, pushes state, imports a resource, broadens scope, or hides a
failed readback.

An older completed workflow is history rather than an interruption. It is readable through
`platform-status`, but it is never resumed or rewritten to claim stages that did not exist when it
ran. Use the displayed supersession prompt to start the current workflow. Malformed or
digest-mismatched specification/progress files instead return `SPECIFICATION_READBACK_FAILED` or
`PROGRESS_READBACK_FAILED`; do not edit or delete them to bypass the blocker.

If a partial foundation apply created the protected signing key ring but Terraform marked that
exact instance as tainted, the resumed deployment reads back its immutable live identity and shows
one state-only recovery action. After a separate `y/N` confirmation it clears only the taint marker
and generates a fresh plan. An identity mismatch or declined confirmation stops without changing
state; the lifecycle never disables `prevent_destroy` or replaces the live key ring.

Blocked execution identifies the unavailable boundary rather than reporting only a generic
adapter failure. The result distinguishes the Cloud SDK configuration and executable, operator
identity session, Application Default Credentials, DNS executable and command adapter, pinned
Terraform executable and CLI configuration, Terraform command adapter, and private state
directory. Terraform planning likewise reports a safe category for state locks and reads, backend
access, authentication, provider permissions or quota, configuration, provider-plugin startup, and
unknown diagnostics. Initialization separately identifies unreadable reviewed modules, backend,
authentication, and pinned-provider failures. Apply failures report a specific safe category plus
any bounded resource
address, operation, HTTP status, provider status, and service name that can be extracted without
echoing arbitrary provider text. Human-readable guidance is printed separately; raw Terraform
stderr is never printed or retained outside the ignored private diagnostic boundary. Every
returned blocker first prints its component and safe code to stderr, then appears in the final JSON
result. An unexpected adapter or operator exception is caught at the CLI boundary and reports only
its exception class plus
`OPERATOR_INTERNAL_ERROR`; the exception message is not echoed because it may contain protected
material.

Interactive `ACTION`, `READBACK`, and `PLAN` blocks print their safe structured content as
indented, sorted JSON. Their display formatting does not change canonical digest calculation or
the exact saved plan selected for confirmation and apply.

### Candidate staging verification

A clean pushed pull-request revision containing current `origin/main` may exercise staging before
merge:

```bash
git push -u origin HEAD
make fixture-project-bootstrap ENVIRONMENT=staging SOURCE_AUTHORITY=candidate \
  FIXTURES_PROJECT_ID=comfforts-fixtures-nonprod \
  FIXTURES_PROJECT_NAME="Comfforts Fixtures Non-Prod"
make platform-deploy ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-connect-project ENVIRONMENT=staging SOURCE_AUTHORITY=candidate \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod
# For each fixture: application-handoff-check, platform-outputs, fixture-handoff,
# inspect, then platform-register.
make fixture-status ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-qualify ENVIRONMENT=staging SOURCE_AUTHORITY=candidate \
  OWNER_MEMBER_REFERENCE=<reviewed-owner-member-reference>
```

Candidate Source is refused for production. Its specifications, bundles, status, and evidence are
kept separate and cannot qualify the accepted environment. After merge, use the default Accepted
Source. A fixture operation may continue against the unchanged provider-verified staging platform;
repeat `platform-deploy` only when platform-owned desired state must change. Before claiming
accepted qualification, deploy and qualify the platform from clean current `main`.

### Command reference

| Command | Purpose |
| --- | --- |
| `make platform-preflight ENVIRONMENT=<name>` | Report current source, tool, authentication, project, ownership, and provider-readiness blockers without creating lifecycle state |
| `make platform-preflight-check ENVIRONMENT=<name> SOURCE_AUTHORITY=<authority>` | Run the same real prerequisite checks against an uncommitted working tree without granting source authority |
| `make platform-prepare ENVIRONMENT=<name>` | Optionally prepare and review a complete specification without external mutation |
| `make platform-cancel ENVIRONMENT=<name> SOURCE_AUTHORITY=<authority>` | Confirm and close only an active private deployment record so changed source can prepare fresh intent; no Terraform or cloud mutation |
| `make platform-deploy ENVIRONMENT=<name>` | Run platform readiness, stop on an unreadable or invalid check, then reuse or prepare approval and reconcile fresh exact plans, checkpoints, and readback |
| `make platform-deploy-check ENVIRONMENT=<name> SOURCE_AUTHORITY=<authority>` | Classify platform readiness from required services, working-tree state compatibility, provider readback, and lock-free plan policy without mutation |
| `make platform-status ENVIRONMENT=<name>` | Report checkout, recorded deployment, active runtime, execution, and qualification state without mutation |
| `make platform-member-identify ENVIRONMENT=<name>` | Confirm a browser login, recover only that Visitor's opaque member reference, and read its exact lifecycle without listing or mutation |
| `make fixture-project-bootstrap ENVIRONMENT=staging FIXTURES_PROJECT_ID=<project-id> FIXTURES_PROJECT_NAME="<display-name>"` | Idempotently create or repair the selected fixture application project, state bucket, and image repository; read back its provider-assigned project number; create no runtime or route |
| `make platform-connect-project ...` | Attach one existing application project to the platform Shared VPC and record the verified connection; create no runtime or route |
| `make application-handoff-check ...` | Require the platform-ready result, then verify the named application project, its services and Shared VPC grants, bundle inputs, access mode, and application identity projection without mutation |
| `make platform-outputs ...` | Generate one application- and project-scoped Platform Integration Bundle from a verified project connection |
| `make platform-register ...` | Validate an application attachment and activate a complete immutable generation |
| `make platform-detach ...` | Reversibly remove one application from catalogue and routing |
| `make platform-retire ...` | Permanently retire an application while reserving its identifier and route |
| `make platform-qualify ENVIRONMENT=<name> OWNER_MEMBER_REFERENCE=<opaque-reference>` | Evaluate the exact platform and fixture revisions, exercise and clean up one temporary second member, require the reviewed owner-only baseline, then—with explicit rollback and restoration confirmations—exercise the reviewed predecessor only after every prerequisite passes; write redacted evidence without member references |
| `make platform-destroy ENVIRONMENT=<name>` | Compile, confirm, execute, and resume safe platform destruction |
| `make fixture-handoff ENVIRONMENT=staging APPLICATION_ID=<id> CATALOGUE_VISIBILITY=<listed\|unlisted> INTEGRATION_BUNDLE=<path>` | Consume an existing project-scoped bundle, deploy one selected fixture, write its inspectable attachment and explicit catalogue intent, and stop before registration |
| `make fixture-status ENVIRONMENT=staging [APPLICATION_ID=<id>]` | Report active catalogue visibility and reconcile registration, target posture, and live HTTPS route for every fixture by default, or one selected fixture, without mutation |
| `make fixture-destroy ENVIRONMENT=staging APPLICATION_ID=<id>` | After `platform-detach`, destroy only one fixture's Application State |

Production uses a separate profile, state, identity, OAuth client, DNS/TLS resources, evidence, and
destructive authority. Preparation currently stops with `OWNERSHIP_TRANSFER_REQUIRED` while
`apps.comfforts.com` or another requested resource remains under another owner. It does not import
or replace those resources.

## Integrate and manage applications

For an application that is not a repository-owned fixture, the platform and Application Owner
perform separate operations:

1. The Platform Operator connects the existing application project to the environment's Shared
   VPC. This is normally a once-per-environment project operation.
2. The Platform Operator generates a Platform Integration Bundle for that project, application,
   route, access mode, environment, platform revision, and Registration Generation.
3. The Application Owner consumes that bundle and deploys the runtime through its own Application
   State and release authority.
4. The Application Owner returns an Application Attachment Bundle bound to the exact integration-
   bundle digest.
5. The Platform Operator validates the bundle, target, owner, network, ingress, edge-caller grant, audience,
   and current platform state, then activates a complete Registration Generation.

The complete handoff sequence is:

```bash
make platform-status ENVIRONMENT=staging

make platform-connect-project \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=<application-project-id>

make application-handoff-check \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=<application-project-id> \
  APPLICATION_ID=<application-id> \
  ACCESS_MODE=<public|authenticated|restricted> \
  IDENTITY_DELIVERY=<none|optional|required> \
  ROUTE_INTENT=/<route> \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  PLATFORM_GENERATION=<positive-integer>

make platform-outputs \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=<application-project-id> \
  APPLICATION_ID=<application-id> \
  ACCESS_MODE=<public|authenticated|restricted> \
  IDENTITY_DELIVERY=<none|optional|required> \
  ROUTE_INTENT=/<route> \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  PLATFORM_GENERATION=<positive-integer>

# The Application Owner takes the generated Platform Integration Bundle,
# deploys the application through that application's own repository and state,
# and returns the Application Attachment Bundle and registration intent.

make platform-register \
  ENVIRONMENT=staging \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v2.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.v2.json \
  REGISTRATION_INTENT=/private/path/registration-intent.v2.json

make platform-status ENVIRONMENT=staging
```

`platform-connect-project` does not create or manage the application's runtime, state bucket,
image repository, data, or route. There is no App Platform Make target for deploying a real application's runtime. That operation is
intentionally supplied and authorized by the application's own repository. Apps Platform owns the
project connection and the surrounding checks and commands: `application-handoff-check` verifies
that the currently deployed platform and connected project can support the requested admission
mode, `platform-outputs` creates the application-specific handoff, and
`platform-register` validates the returned attachment and activates the new complete Registration
Generation.

The [real-application adoption runbook](docs/runbooks/application_adoption.md) records the full
cross-owner sequence, Cloud Run posture, `application_id` bindings, and the separation between
verified Platform Identity and application-owned permissions. It is a readiness reference, not
current authority to adopt a real application.

The integration bundle contains only values the named application is allowed to consume. It may
contain an OAuth client identifier when required, but never the OAuth client secret, a credential,
Terraform state, another application's value, or an unauthorized secret reference.

Detachment is the normal reversible maintenance state: the application becomes non-routable while
its identifier and route remain reserved, allowing its owner to destroy, replace, and redeploy its
assets before registering a replacement attachment. Retirement is terminal and is not used for a
temporary outage or test cycle.

Before destroying the platform, detach every active application and destroy application-owned
assets through each Application Owner's lifecycle. `platform-destroy` refuses active attachments
and never targets Application State. Backend, recovery, evidence, and the Shared VPC connection
foundation remain protected after ordinary platform destruction. Disconnecting application
projects and purging those retained resources require separate destructive authority.

## Maintain the project

Read [AGENTS.md](AGENTS.md) before changing the repository. It defines the durable branch, review,
safety, and verification workflow. [docs/README.md](docs/README.md) is the project-authority index
and task-specific reading router.

Useful deeper references are:

- [system design](docs/03_system_design.md) for architecture and ownership;
- [implementation plan index](docs/plans/README.md) for delivery status, the AP-M9 milestone plan,
  and the current W10 work-package plan;
- [contract index](contracts/README.md) for public machine interfaces and compatibility;
- [threat model](docs/06_threat_model.md) for trust boundaries and required evidence;
- [repository layout](docs/repository_layout.md) for capability placement;
- [environment lifecycle runbook](docs/runbooks/environment_lifecycle.md) for operator behavior;
  and
- [operator internals](infrastructure/operator/README.md) for implementation details and private
  state behavior.

Use a semantic branch name, keep one bounded slice per pull request, update a public contract and
all consumers together, and run focused tests plus the complete `make check` gate before handoff.
Do not treat a merge, static plan, local fake, or repository test as proof that an external
environment is deployed or qualified.

## Operational readiness

AP-M9-W9 is implemented and candidate-qualified under the predecessor Version 1 membership model.
Candidate staging proved the dedicated fixture project, Shared VPC attachment, all three admission
modes, separate registration, and the restricted-fixture detach, destruction, redeployment, and
reactivation lifecycle. Candidate Source is not Accepted Source qualification. AP-M9-W10 has
integrated all seven repository slices and its candidate-readiness corrections without a Live
Version 2 qualification. The exact clean pushed integration revision must pass Candidate Source
staging qualification and be frozen before the cumulative pull request to `main`.
Production remains blocked on that accepted result, explicit ownership transfer, and application
adoption.

See [the documentation index](docs/README.md) for the current work-package sequence, evidence
boundary, and historical delivery record.
