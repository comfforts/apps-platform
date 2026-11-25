# App Platform backlog

This backlog records useful product and maintenance work that is not part of the active delivery
sequence. A backlog item is a proposal, not implementation authority. Before work begins, the item
must be reconciled with the product requirements, accepted architecture decisions, threat model,
evaluation strategy, implementation plan, and an owner-approved delivery slice.

## Feature-rich catalogue experience

### Problem

The current root catalogue is intentionally a small, server-rendered public projection of the
active Registration Generation. It provides a safe application list and links, but it is not
designed as a polished product surface. As the number and variety of applications grow, operators
and visitors may need a more discoverable, accessible, branded, and informative catalogue without
adding catalogue concerns to the Shared Edge routing runtime.

### Proposed product and architecture review

Evaluate whether the catalogue should remain a minimal Shared Edge response or become a
feature-rich, independently deployable, platform-owned application. The review should prototype
and compare at least these experiences:

- responsive application cards, search, filtering, categories, and clear access-mode indicators;
- accessible keyboard, screen-reader, focus, contrast, loading, empty, and error states;
- safe application summaries, icons, ownership/support links, availability cues, and deep links;
- platform branding and environment identification that cannot confuse staging with production;
- a lightweight minimal catalogue for small installations; and
- a graceful fallback when a standalone catalogue runtime is unavailable.

If a standalone application is selected, define its deployment, routing, versioning, rollback,
observability, caching, cost, and availability ownership. Decide whether `/` remains a reserved
Shared Edge route that proxies to the catalogue, whether the catalogue consumes an immutable
public projection or a bounded read-only endpoint, and how the edge supplies a safe fallback
without creating a second catalogue implementation that can drift.

### Product and safety boundaries

- The active Registration Generation remains the only authority for application identity,
  lifecycle, catalogue inclusion, route, and access mode. The catalogue must not introduce a
  writable registry, discovery database, or independent routing decision.
- Expose only the reviewed public catalogue projection. Never disclose attachment references,
  target locations, restricted membership, visitor identity, application state, provider data,
  credentials, secrets, or private operator records.
- Preserve canonical application links and reserved-path handling. Catalogue rendering or failure
  must never make an unregistered, suspended, retired, or restricted route available.
- A standalone catalogue must not receive general Platform State, application deployment, or
  registration mutation authority merely because it is platform-owned.
- Dynamic content, icons, and links require bounded validation, safe escaping, a restrictive
  content-security policy, and explicit ownership. Third-party analytics, trackers, remote assets,
  or personalization require separate privacy and security review.
- Preserve a closed, useful response when the catalogue application or its data source is
  unavailable; do not redirect visitors to an application target or expose an internal failure.
- Keep the initial design proportionate to demonstrated catalogue needs. Do not add a frontend
  framework, content service, search service, or new billable dependency without a concrete UX or
  operational reason.

### Completion evidence

The review should produce an owner-approved UX prototype, an explicit architecture decision, and a
small delivery proposal before implementation. Deterministic tests must cover public-projection
parity with the active generation, canonical links, escaping and content security, accessibility,
responsive behavior, suspended and retired applications, stale data, catalogue-runtime failure,
and rollback. Live staging evidence must show that the richer catalogue does not become a second
routing authority and that its failure leaves application routes and protected admission
fail-closed.

## Platform observability review and operational diagnostics

### Problem

The initial platform observability design intentionally minimizes retained runtime data, but its
current verification is narrower than the operational lifecycle. Candidate login testing exposed
two gaps: standalone safe diagnostics were not selected by the dedicated completion-event sink,
and completion events written through an unconfigured standard logger could be suppressed below
the logger's inherited warning level. The active correction carries fixed diagnostic codes through
an exact JSON-line completion event. A broader review is still needed to verify that every retained
signal is useful, queryable, appropriately protected, and consistent with actual operations.

### Proposed review

Inventory and test the complete staging observability path:

- Shared Edge completion events, allowlisted diagnostic codes, correlation, and adapter health;
- Cloud Run request, startup, revision, and application-proxy failure signals;
- Cloud Logging router sinks, exclusions, regional buckets, views, IAM, retention, and query paths;
- provider audit logs for IAM, Secret Manager, KMS, Cloud Run, networking, DNS/TLS, state, and
  destructive operations;
- platform deployment, application handoff, registration, qualification, rollback, and destruction
  records that operators need for diagnosis;
- budget, availability, certificate, routing, identity, and dependency signals that may warrant an
  alert only after measured staging evidence; and
- runbook commands that report a useful safe result without requiring an operator to understand
  internal logger or sink implementation.

Prefer a small stable taxonomy of actionable codes and a few task-specific read-only operator
commands over generalized telemetry machinery. Each signal must name its owner, purpose, source,
retention, reader, cost, expected response, and prohibited fields. Remove duplicate, unused, or
unqueryable telemetry instead of retaining it speculatively.

### Safety requirements

- Retain only fixed, reviewed fields; never arbitrary exception text or provider payloads.
- Exclude OAuth authorization codes, tokens, secrets, cookies, session identifiers, visitor
  identity, restricted membership, request parameters, bodies, application data, Terraform state,
  and saved plans.
- Keep runtime logs owner-readable, regional, time-bounded, and without external export unless a
  later accepted decision changes that boundary.
- Treat correlation identifiers as diagnostic labels, never identity or authorization signals.
- Verify that logging failure cannot change a visitor response or silently weaken fail-closed
  admission.
- Do not add dashboards, alerts, exports, long retention, or new paid services without measured
  need, explicit cost review, and the applicable authority.

### Completion evidence

Deterministic tests must prove exact JSON emission, fixed-code validation, prohibited-data absence,
sink-filter compatibility, and logging-failure isolation. Live staging evidence must produce and
query one event for each approved failure class, confirm bucket/view access and seven-day retention,
and prove the default exclusion and no-export posture. The review must leave a concise operator
troubleshooting map and explicitly record signals that remain unavailable or intentionally absent.

## Platform member directory and explicit identity delivery

### Problem

The current restricted fixture compiles one operator identity into one Application Registration.
That makes restricted membership application-specific configuration and couples membership changes
to Registration Generations. It does not represent the intended product boundary: restricted
admission should use one platform-wide, owner-managed member directory shared by every restricted
route.

Identity delivery for public routes also needs an explicit privacy boundary. A public application
may remain anonymous, use application-owned authentication, or opt into Platform Identity for a
visitor who chooses the platform login flow. Those choices must not be inferred from `public`
admission or from the existence of a Platform Session.

The Google Auth Platform test-user list is a separate provider control used while an OAuth client
has Testing status. It determines who may complete that provider's consent flow; it is not the App
Platform member directory, an application user database, or a Feature Entitlement system.

### Proposed product model

Use a platform-owned Firestore member directory keyed by the verified Google issuer and stable
subject. Membership is platform-wide:

- `public` permits anonymous access and defaults to no Platform Identity delivery; an application
  may explicitly request optional Platform Identity without making login mandatory;
- `authenticated` requires Platform Identity and admits any identity successfully authenticated by
  the configured platform identity provider; and
- `restricted` requires Platform Identity and additionally requires an active entry in the
  platform member directory.

The Shared Edge resolves only the current visitor and sends that visitor's minimal, signed context
to the selected application. It must not copy the member directory into a Registration Generation,
bundle, assertion, catalogue response, log, or application runtime. Application principals, user
records, roles, provider rights, and Feature Entitlements remain application-owned.

Add an explicit per-application identity-delivery field to the versioned handoff and registration
contracts. The intended combinations are `none` or `optional` for public admission and `required`
for authenticated or restricted admission. A public application's separate OAuth client and
identity remain independent; account linking to Platform Identity requires an explicit
application-owned process.

### Proposed operator lifecycle

Platform deployment creates the directory infrastructure and least-privilege Shared Edge access,
but it does not silently enroll the Platform Owner. A separate, deliberate owner-bootstrap command
must verify an empty remote directory, distinguish the authenticated Cloud Operator from the Google
identity being enrolled, obtain the owner identity through a confirmed browser flow, display a
non-sensitive exact action, require confirmation, write one owner member idempotently, and read it
back.

Small platform-member commands should then support status, addition, suspension or reactivation,
and removal without compiling a new Registration Generation or redeploying an application. Their
exact names and lifecycle semantics require the governing architecture decision and contracts
before implementation. Membership changes must be scoped to one Platform Environment, survive
application replacement, and take effect at the next request or new session boundary defined by
the accepted identity design.

### Product and safety boundaries

- Keep OAuth consent eligibility, Platform Identity authentication, platform membership,
  application principals, and application Feature Entitlements as separate decisions.
- Use verified issuer and stable subject as identity keys. Email and display name may be shown
  transiently for operator confirmation but are not membership or ownership keys.
- Store no application-specific feature roles, provider permissions, or application user profiles
  in the platform member directory.
- Keep the full member directory and individual member identities out of Git, public bundles,
  catalogue output, ordinary terminal summaries, and public qualification evidence.
- Require least-privilege Firestore access, idempotent mutation, exact readback, revocation tests,
  and fail-closed behavior when the directory is unavailable or inconsistent.
- An empty directory is a valid deployed state in which every restricted route denies admission;
  it cannot satisfy restricted live qualification.
- Do not infer that the active Cloud Operator is the Platform Owner member, and do not create or
  replace an owner member merely because local operator state is absent.

### Completion evidence

Deterministic tests must cover public anonymous access, public optional Platform Identity,
authenticated admission for a valid Google identity, restricted admission for an active member,
restricted denial for a non-member, member suspension and removal, directory unavailability,
cross-application consistency, prohibited-data absence, and application-owned Feature Entitlements.
Live staging qualification must bootstrap the owner explicitly, exercise a second member's
allow/deny lifecycle through `fixture-restricted`, prove that public and authenticated behavior is
unchanged, and restore the reviewed member baseline before closing qualification.

## Fixture project disconnect and clean lifecycle

### Problem

The dedicated fixture application project is intended to be reused. After fixture testing, an
operator can detach the fixture routes and destroy each fixture's Application State, but there is
no bounded workflow for disconnecting the now-unused project from the platform network or removing
the bootstrap-owned resources that can retain data or incur cost.

Deleting the Google Cloud project is not the desired lifecycle. The project must remain available
for a later fixture bootstrap and deployment.

### Proposed operator interface

Add these explicit Make tasks:

```text
make fixture-project-disconnect ENVIRONMENT=<environment> APPLICATION_PROJECT_ID=<project-id>
make fixture-project-clean ENVIRONMENT=<environment> APPLICATION_PROJECT_ID=<project-id>
```

Both commands must resolve the supplied project ID to the immutable project number recorded by the
successful fixture-project bootstrap. Supplying an arbitrary project ID must never grant authority
to disconnect or clean that project.

The normal sequence is:

1. Run `platform-detach` for every active fixture registration.
2. Run `fixture-destroy` for every deployed fixture Application State root.
3. Verify that every fixture route is suspended or retired and every fixture target is absent.
4. Run `fixture-project-disconnect`.
5. Run `fixture-project-clean` only after reviewing its exact inventory and destructive plan.

### `fixture-project-disconnect`

This task should remove only the connection created for the recorded fixture project:

- detach the project as a service project from the platform Shared VPC;
- remove the fixture project's Cloud Run service-agent access to the platform network and
  application subnet;
- verify that no other project, network, subnet, IAM grant, route, runtime, or Platform State was
  changed; and
- record and read back a private non-secret disconnected state.

The task must stop when a fixture registration is active, a fixture target exists, an Application
State root is not destroyed, the project identity or ownership marker differs, an unknown network
grant exists, or provider readback is incomplete. Repeating a completed disconnect should be
idempotent.

### `fixture-project-clean`

This task should remove the resources created by `fixture-project-bootstrap` while leaving the
Google Cloud project itself active and reusable. Its reviewed inventory should cover:

- fixture container images and the fixture Artifact Registry repository;
- the fixture Terraform-state bucket and retained object versions;
- bootstrap-created IAM grants and identities that are no longer required;
- enabled APIs that are no longer needed after resource removal; and
- any other bootstrap-owned resource that can retain data or incur cost.

Cleaning the state bucket, image repository, or another retained recovery resource is a purge and
must not be implied by ordinary fixture destruction. Before implementation, the design must decide
whether cleanup exports or permanently purges retained state, whether project billing is unlinked,
and what minimal project metadata or IAM must remain for safe reuse. Until those decisions are
approved, the command must fail closed rather than claim that the project is empty or cannot incur
cost.

The task must:

- require the project to be disconnected and every fixture root to be destroyed;
- compare the provider inventory with the exact bootstrap-owned inventory and reject unknown
  resources;
- show the complete deletion and service-disable plan before mutation;
- use an exact typed confirmation naming the environment, project ID, and project number;
- delete only resources owned by the fixture-project bootstrap lifecycle;
- retain a private non-secret cleanup tombstone and final provider readback; and
- be safely repeatable when the project is already clean.

### Explicit non-goals

- Do not delete or shut down the Google Cloud project.
- Do not operate on a real application's project.
- Do not detach or destroy an active application implicitly.
- Do not delete Platform State, the Shared Edge, the platform network, DNS, TLS, OAuth, or another
  environment's resources.
- Do not treat API disablement alone as proof that billable resources or retained data are absent.

### Completion evidence

Implementation is complete only when deterministic tests cover wrong-project rejection, active
fixture rejection, unknown-resource rejection, interrupted and repeated operations, exact
inventory scoping, and redacted readback. A later live staging rehearsal must prove that the
recorded fixture project remains active, disconnected, free of the approved removable inventory,
and able to be bootstrapped and connected again without changing its project identity.

## Environment-derived platform project identity and hostname

### Problem

The staging platform project ID, project number, and platform hostname are repeated as literals
across operator, configuration, backend, Terraform-policy, contract-validation, runtime, and test
code. Although the project values identify the platform Shared VPC host rather than the fixture
application project, all three values bind operations to one Platform Environment. Duplicating
them makes environment selection difficult to audit and creates a risk that one consumer retains
stale staging identity or hostname after another is updated.

The fixture project now has explicit `FIXTURES_PROJECT_ID` and `FIXTURES_PROJECT_NAME` inputs and
a provider-discovered project number. The platform project and hostname need an equally clear
environment boundary without making provider-assigned identity implicit or allowing an operator
to select an unrelated project or hostname.

### Proposed configuration interface

Introduce explicit environment inputs for the selected platform project:

```text
PLATFORM_PROJECT_ID=<exact-project-id>
PLATFORM_PROJECT_NUMBER=<provider-assigned-project-number>
PLATFORM_HOSTNAME=<exact-environment-hostname>
```

The selected environment profile remains authoritative for the allowed project identity and
hostname. Operator startup must validate all three values against the profile and the applicable
provider or DNS readback before any plan, mutation, bundle generation, registration,
qualification, or destruction. An environment variable is configuration input, not proof of
ownership. Missing, malformed, mismatched, or unreadable identity or hostname must fail closed
with a precise blocker.

Use one typed configuration resolver to supply the validated project identity and hostname to all
consumers. Remove repeated staging project-ID, project-number, and hostname literals from Python
modules, Terraform policy checks, backend naming, runtime settings, contract validation, operator
adapters, and non-synthetic tests. Derive project-number-based bucket names, provider references,
external origins, issuer and callback URLs, DNS/TLS bindings, and route URLs from those validated
values instead of embedding complete staging resource names or hostnames.

Synthetic fixtures and negative tests may retain clearly named fictional project IDs, numbers,
and hostnames. The checked-in staging environment profile may retain the reviewed real values
because it is the repository authority against which environment input and provider or DNS
readback are validated.

### Safety and migration requirements

- Preserve the distinction between the platform host project and each application or fixture
  project.
- Do not obtain authority solely from ambient `gcloud` configuration.
- Verify that `PLATFORM_PROJECT_ID` resolves to `PLATFORM_PROJECT_NUMBER` before an external
  operation.
- Require `PLATFORM_HOSTNAME` to be the exact normalized hostname selected by the environment
  profile; ambient DNS resolution alone does not establish ownership or operation authority.
- Keep production disabled until its separately approved environment profile and ownership are
  available.
- Do not rename or migrate existing buckets, Terraform state, Shared VPC resources, identities,
  DNS records, certificates, OAuth callbacks, or provider resources as a side effect of replacing
  literals.
- Ensure private historical records remain readable when they contain the same verified project
  identity and hostname.
- Keep `make check` credential-free by supplying deterministic test environment values through the
  Makefile and test helpers.

### Completion evidence

Implementation is complete when a repository-wide search finds no real staging platform project
ID, project-number, or hostname literal outside the authoritative staging profile, explicit
operator examples, and migration documentation. Deterministic tests must cover missing values,
malformed values, project-ID mismatch, project-number mismatch, hostname mismatch,
provider-readback mismatch, DNS-readback mismatch where applicable, correct derivation of resource
names and URLs, and unchanged historical-record compatibility. A later authenticated staging
readback must confirm that the resolved identity and hostname still point to the existing platform
environment and do not propose resource replacement, DNS/TLS replacement, or state migration.

## Legacy same-project fixture state-bucket disposition

### Problem

The cross-project fixture transition releases the three former same-project fixture state buckets
from Platform State without destroying them. This is intentionally safer than allowing ordinary
`platform-deploy` or `fixture-destroy` to purge retained Terraform state, but it leaves the legacy
buckets and their object versions in the platform project until their disposition is reviewed.

### Proposed lifecycle

Add a separate inventory-and-disposition workflow that:

- resolves the exact former `fixture-public`, `fixture-authenticated`, and `fixture-restricted`
  bucket identities from historical provider-backed state;
- proves that no active or recoverable same-project fixture still depends on them;
- inventories object versions, retention constraints, ownership labels, IAM, and billable storage;
- lets the owner choose a documented retention period, a controlled export, or a permanent purge;
- rejects unknown buckets, objects, principals, or ownership markers; and
- requires an exact typed destructive confirmation before any purge.

The workflow must not be folded into `platform-deploy`, `platform-destroy`, `fixture-destroy`, or
fixture-project cleanup. A Terraform `forget` action is evidence only that configuration no longer
manages a resource; it is not evidence that provider data was deleted or that retention is no
longer required.

### Completion evidence

Deterministic tests must cover exact legacy-bucket selection, active dependency rejection,
retention-policy refusal, unknown-resource refusal, export-before-purge behavior, interruption,
and idempotent readback. Live evidence must identify the reviewed buckets by immutable provider
identity and prove either their approved retention posture or their completed purge without
touching the platform-state bucket or dedicated fixture-project state.
