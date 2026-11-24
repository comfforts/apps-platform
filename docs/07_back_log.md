# App Platform backlog

This backlog records useful product and maintenance work that is not part of the active delivery
sequence. A backlog item is a proposal, not implementation authority. Before work begins, the item
must be reconciled with the product requirements, accepted architecture decisions, threat model,
evaluation strategy, implementation plan, and an owner-approved delivery slice.

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

## Environment-derived platform project identity

### Problem

The staging platform project ID and project number are repeated as literals across operator,
configuration, backend, Terraform-policy, contract-validation, runtime, and test code. Although
these values identify the platform Shared VPC host rather than the fixture application project,
duplicating them makes environment selection difficult to audit and creates a risk that one
consumer retains stale staging identity after another is updated.

The fixture project now has explicit `FIXTURES_PROJECT_ID` and `FIXTURES_PROJECT_NAME` inputs and
a provider-discovered project number. The platform project needs an equally clear environment boundary without making
provider-assigned identity implicit or allowing an operator to select an unrelated project.

### Proposed configuration interface

Introduce explicit environment inputs for the selected platform project:

```text
PLATFORM_PROJECT_ID=<exact-project-id>
PLATFORM_PROJECT_NUMBER=<provider-assigned-project-number>
```

The selected environment profile remains authoritative for the allowed project identity. Operator
startup must validate both values against the profile and provider readback before any plan,
mutation, bundle generation, registration, qualification, or destruction. An environment variable
is configuration input, not proof of ownership. Missing, malformed, mismatched, or unreadable
identity must fail closed with a precise blocker.

Use one typed configuration resolver to supply the validated project identity to all consumers.
Remove repeated staging project-ID and project-number literals from Python modules, Terraform
policy checks, backend naming, runtime settings, contract validation, operator adapters, and
non-synthetic tests. Derive project-number-based bucket names and provider references from that
validated identity instead of embedding complete staging resource names.

Synthetic fixtures and negative tests may retain clearly named fictional project IDs and numbers.
The checked-in staging environment profile may retain the reviewed real values because it is the
repository authority against which environment input and provider readback are validated.

### Safety and migration requirements

- Preserve the distinction between the platform host project and each application or fixture
  project.
- Do not obtain authority solely from ambient `gcloud` configuration.
- Verify that `PLATFORM_PROJECT_ID` resolves to `PLATFORM_PROJECT_NUMBER` before an external
  operation.
- Keep production disabled until its separately approved environment profile and ownership are
  available.
- Do not rename or migrate existing buckets, Terraform state, Shared VPC resources, identities, or
  provider resources as a side effect of replacing literals.
- Ensure private historical records remain readable when they contain the same verified project
  identity.
- Keep `make check` credential-free by supplying deterministic test environment values through the
  Makefile and test helpers.

### Completion evidence

Implementation is complete when a repository-wide search finds no real staging platform project
ID or project-number literal outside the authoritative staging profile, explicit operator examples,
and migration documentation. Deterministic tests must cover missing values, malformed values,
project-ID mismatch, project-number mismatch, provider-readback mismatch, correct derivation of
resource names, and unchanged historical-record compatibility. A later authenticated staging
readback must confirm that the resolved identity still points to the existing platform project and
does not propose resource replacement or state migration.

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
