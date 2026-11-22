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
| Google OAuth client, platform sessions, and assertion signing | Application principals and feature entitlements |
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
| `public` | Anonymous visitors; authentication is not required | None for an anonymous visitor; verified identity may be supplied when a valid Platform Session exists |
| `authenticated` | Any identity successfully authenticated by the configured platform identity provider | A short-lived, signed assertion scoped to that application |
| `restricted` | Only authenticated identities in the registration's exact issuer-and-subject membership | The same application-scoped signed assertion after membership succeeds |

`public` describes only the platform's admission decision. A public application may remain fully
anonymous, or its Application Owner may add application-owned authentication, including a separate
OAuth client. That authentication, its client and secret, its sessions, and the resulting
application identity remain outside platform ownership. Adding it does not change the registration
to `authenticated` and does not turn an application-issued identity into Verified Identity Context.
If the application instead consumes the optional platform identity available for a visitor with a
valid Platform Session, it must verify that platform assertion by the same rules described below.

Applications registered as `authenticated` or `restricted` rely on platform admission for their
platform-route visitor identity. After admission, each application must independently verify the
platform assertion's signature, issuer, application-specific audience, time bounds, and contract
version before deriving an Application Principal. It receives neither the platform OAuth client
secret nor the identity provider's original token. A `restricted` application additionally
benefits from the Shared Edge's exact issuer-and-subject membership check, but still performs the
same assertion verification as an `authenticated` application.

Owner-only access is a `restricted` registration containing only the owner's immutable identity.
Email is not a membership or ownership key. Admission decides whether a request may reach the
application; the application still decides its own principals, data access, roles, provider rights,
and feature entitlements.

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
behavior. It deploys through independent Application State and exchanges the same integration and
attachment bundles as a real application. A real application remains outside platform authority
until its Application Owner adopts the platform contracts and performs its own deployment and
release process.

The included fixture suite demonstrates the three admission modes:

| Fixture | Admission | Catalogue | What it demonstrates |
| --- | --- | --- | --- |
| `fixture-public` | Public | Listed | Anonymous routing, subpaths, attachment mounts, and forwarding |
| `fixture-authenticated` | Authenticated | Unlisted | Platform login, verified identity delivery, and application assertion verification |
| `fixture-restricted` | Restricted | Listed | Exact membership admission while application-owned feature authorization remains separate |

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
    | platform-outputs
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

That is the contract sequence for every application. For the repository-owned fixtures,
`fixture-deploy` is a fixture-only orchestration command that performs the complete sequence for one
required `APPLICATION_ID`: it generates that fixture's Platform Integration Bundle, deploys its
independent Application State, receives and validates its Application Attachment Bundle, and
activates a complete immutable Registration Generation while preserving other registrations. The
operator runs it once for each fixture to be deployed and does not run `platform-outputs` or
`platform-register` separately for that fixture.

For an optional inspection stop, `fixture-handoff` performs the same selected-fixture journey only
through validated Application Attachment Bundle generation. It deploys or reconciles that
fixture's Application State, writes both canonical bundles beneath `.platform-operator/`, prints
their paths and digests, and does not register or route the fixture. A later `fixture-deploy` keeps
its normal end-to-end behavior but reuses that prepared pair when the environment, application,
source authority, fixture source, platform source and generation, bundle digests, image, and live
target posture still match. It regenerates and reconciles when any binding has changed.

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
preparation, displays one complete Deployment Specification, requests approval, creates and shows
fresh exact Terraform plans, applies only confirmed plans, pauses for Google OAuth and Squarespace
DNS work, verifies readable results, and atomically records private resume progress.

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
make platform-preflight ENVIRONMENT=staging PREFLIGHT_MODE=development
```

Development preflight reports dirty, unpushed, stale, or non-main source as non-blocking source
diagnostics while continuing to enforce profile, authentication, project, tool, and discovery
checks. Its result distinguishes `ready` for development from `operational_ready`. This mode exists
only for preflight; it cannot prepare, approve, plan, deploy, publish a bundle, qualify, or mutate an
external system.

Operator narration is written to standard error. The final compact JSON result remains the only
standard-output record, so a human receives a readable execution trace while automation can parse
stdout without filtering progress messages. Traces never include access tokens, secret values,
raw provider responses, Terraform state, or saved-plan content.

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

## Repository structure

| Path | Purpose |
| --- | --- |
| `edge/` | Shared Edge runtime, identity, routing, proxy, limits, and provider adapters |
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

### Accepted staging operation

Accepted Source is the default. It requires a clean current `main` revision. The normal staging
journey is:

```bash
make platform-deploy ENVIRONMENT=staging
make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=fixture-public
make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated
make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=fixture-restricted
make fixture-status ENVIRONMENT=staging
make platform-qualify ENVIRONMENT=staging
make platform-status ENVIRONMENT=staging
```

Each `fixture-deploy` includes bundle generation and registration for the selected synthetic
fixture. It invokes the same underlying integration and registration lifecycle used by
`platform-outputs` and `platform-register`; it does not bypass those contracts. The separate Make
targets are used for applications whose deployment is owned outside this repository.
`fixture-status` is suite-wide by default, or narrowed with an optional `APPLICATION_ID` during an
individual deployment or investigation.

To inspect one fixture's generated bundles before registration, insert this optional command before
that fixture's ordinary deploy:

```bash
make fixture-handoff ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated
# Inspect the two paths printed by the command without editing either canonical file.
make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated
```

`fixture-handoff` is mutating: it deploys or reconciles only the selected fixture's Application
State, but stops before Registration Generation activation. If every recorded binding is still
current, the following `fixture-deploy` reports `preparation_reused: true` and proceeds directly to
registration. The normal staging journey does not require this optional inspection command.

`platform-deploy` remains active across OAuth and DNS checkpoints. Ordinary reviewed plans use one
`y/N` confirmation. Typed confirmation is reserved for destruction, retirement, ownership
transfer, and other irreversible operations.

If an operation is interrupted, rerun the same command with the same environment and source
authority. The lifecycle validates its private progress and resumes after the last closed stage. A
changed source, specification, environment, or scope requires new preparation and review. It never
automatically unlocks state, pushes state, imports a resource, broadens scope, or hides a failed
readback.

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
unknown diagnostics. Apply failures report a specific safe category plus any bounded resource
address, operation, HTTP status, provider status, and service name that can be extracted without
echoing arbitrary provider text. Human-readable guidance is printed separately; raw Terraform
stderr is never printed or retained. Every returned blocker first prints its component and safe
code to stderr, then appears in the final JSON result. An unexpected adapter or operator exception
is caught at the CLI boundary and reports only its exception class plus
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
make platform-deploy ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=fixture-public SOURCE_AUTHORITY=candidate
make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated SOURCE_AUTHORITY=candidate
make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=fixture-restricted SOURCE_AUTHORITY=candidate
make fixture-status ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-qualify ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
```

Candidate Source is refused for production. Its specifications, bundles, status, and evidence are
kept separate and cannot qualify the accepted environment. After merge, repeat deployment and
qualification from clean current `main` with the default Accepted Source.

### Command reference

| Command | Purpose |
| --- | --- |
| `make platform-preflight ENVIRONMENT=<name>` | Report current source, tool, authentication, project, ownership, and provider-readiness blockers without creating lifecycle state |
| `make platform-prepare ENVIRONMENT=<name>` | Optionally prepare and review a complete specification without external mutation |
| `make platform-deploy ENVIRONMENT=<name>` | Reuse a fresh current approval or prepare one, then deploy, checkpoint, read back, and safely resume the shared platform |
| `make platform-status ENVIRONMENT=<name>` | Report local desired, execution, and qualification state without mutation |
| `make platform-outputs ...` | Generate one application-scoped Platform Integration Bundle |
| `make platform-register ...` | Validate an application attachment and activate a complete immutable generation |
| `make platform-detach ...` | Reversibly remove one application from catalogue and routing |
| `make platform-retire ...` | Permanently retire an application while reserving its identifier and route |
| `make platform-qualify ENVIRONMENT=<name>` | Evaluate the exact platform and fixture revisions and write redacted evidence |
| `make platform-destroy ENVIRONMENT=<name>` | Compile, confirm, execute, and resume safe platform destruction |
| `make fixture-handoff ENVIRONMENT=staging APPLICATION_ID=<id>` | Deploy one selected fixture, write its inspectable bundle pair, and stop before registration |
| `make fixture-deploy ENVIRONMENT=staging APPLICATION_ID=<id>` | Generate the bundle, build and deploy independent state, validate the attachment, and register one selected fixture |
| `make fixture-status ENVIRONMENT=staging [APPLICATION_ID=<id>]` | Reconcile every fixture by default, or one selected fixture, without mutation |
| `make fixture-destroy ENVIRONMENT=staging APPLICATION_ID=<id>` | Detach and destroy one fixture's Application State |

Production uses a separate profile, state, identity, OAuth client, DNS/TLS resources, evidence, and
destructive authority. Preparation currently stops with `OWNERSHIP_TRANSFER_REQUIRED` while
`apps.comfforts.com` or another requested resource remains under another owner. It does not import
or replace those resources.

## Integrate and manage applications

For an application that is not a repository-owned fixture, the platform and Application Owner
perform separate operations:

1. The Platform Operator generates a Platform Integration Bundle for one application, route,
   access mode, environment, platform revision, and Registration Generation.
2. The Application Owner consumes that bundle and deploys the runtime through its own Application
   State and release authority.
3. The Application Owner returns an Application Attachment Bundle bound to the exact integration-
   bundle digest.
4. The Platform Operator validates the bundle, target, owner, ingress, edge-caller grant, audience,
   and current platform state, then activates a complete Registration Generation.

The complete handoff sequence is:

```bash
make platform-status ENVIRONMENT=staging

make platform-outputs \
  ENVIRONMENT=staging \
  APPLICATION_ID=<application-id> \
  ACCESS_MODE=<public|authenticated|restricted> \
  ROUTE_INTENT=/<route> \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  PLATFORM_GENERATION=<positive-integer>

# The Application Owner takes the generated Platform Integration Bundle,
# deploys the application through that application's own repository and state,
# and returns the Application Attachment Bundle and registration intent.

make platform-register \
  ENVIRONMENT=staging \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.json \
  REGISTRATION_INTENT=/private/path/registration-intent.json

make platform-status ENVIRONMENT=staging
```

There is no App Platform Make target for deploying a real application's runtime. That operation is
intentionally supplied and authorized by the application's own repository. Apps Platform owns the
two surrounding commands: `platform-outputs` creates the application-specific handoff, and
`platform-register` validates the returned attachment and activates the new complete Registration
Generation.

The integration bundle contains only values the named application is allowed to consume. It may
contain an OAuth client identifier when required, but never the OAuth client secret, a credential,
Terraform state, another application's value, or an unauthorized secret reference.

Detachment is the normal reversible maintenance state: the application becomes non-routable while
its identifier and route remain reserved, allowing its owner to destroy, replace, and redeploy its
assets before registering a replacement attachment. Retirement is terminal and is not used for a
temporary outage or test cycle.

Before destroying the platform, detach every active application and destroy application-owned
assets through each Application Owner's lifecycle. `platform-destroy` refuses active attachments
and never targets Application State. Backend, recovery, and evidence retention remain separate from
ordinary platform destruction.

## Maintain the project

Read [AGENTS.md](AGENTS.md) before changing the repository. It defines the durable branch, review,
safety, and verification workflow. [docs/README.md](docs/README.md) is the project-authority index
and task-specific reading router.

Useful deeper references are:

- [system design](docs/03_system_design.md) for architecture and ownership;
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

Repository implementation through AP-M9-W9 is complete and deterministically verified. No platform
environment is currently deployed or qualified by this repository's recorded evidence. AP-M9-W10
owns the first accepted staging operation, and production remains blocked on explicit ownership
transfer and application adoption.

See [the documentation index](docs/README.md) for the current work-package sequence, evidence
boundary, and historical delivery record.
