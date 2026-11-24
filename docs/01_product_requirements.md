# App Platform product requirements

Version 0.4 | Status: requirements authority through the AP-M9 operator lifecycle; operational
qualification remains unavailable

This document defines what Comfforts App Platform must provide and the ownership boundaries it must
preserve. It is authoritative for the platform project only. It does not change a consuming
application, provision infrastructure, modify DNS, or prove that any requirement is operational.

## Product outcome

The App Platform provides a configurable shared hostname where people can discover and reach
independently owned applications through stable route prefixes. It centralizes only the Shared Edge,
application catalogue, registration, routing, and admission concerns that must be coordinated across
applications. Each Registered Application retains its own runtime, data, providers, rights, and
feature authorization.

The platform must support independently configured non-production and production Platform
Environments. The intended hostnames are `apps-staging.comfforts.com` and `apps.comfforts.com`,
but hostnames, cloud projects, regions, and application registrations remain environment
configuration rather than assumptions embedded in reusable platform behavior. Existing production
resources remain under their current owner until an explicit ownership-transfer and adoption
procedure completes.

## Actors

- **Platform Owner:** approves platform requirements, registrations, admission policy, live
  qualification, and destructive shared-resource changes.
- **Platform Operator:** performs reviewed lifecycle and qualification procedures within the access
  granted by the Platform Owner.
- **Application Owner:** controls a Registered Application's runtime, data, providers, feature
  authorization, and Application Adoption.
- **Visitor:** reaches the catalogue or an application route and may be anonymous, authenticated, or
  admitted under a more restrictive application policy.

One person may hold more than one role. Roles describe authority boundaries, not a required account
or identity-provider design.

## Product requirements

### AP-PR-001 · Application catalogue

The configured hostname root must present a safe catalogue of active Registered Applications and
their navigable route prefixes. Catalogue metadata must not expose application secrets, internal
endpoints, provider credentials, or private operator data. Visibility rules must be explicit rather
than inferred from an application's admission policy.

### AP-PR-002 · Application registration

Each application must enter the platform through a versioned Application Registration that declares
a unique normalized route prefix, catalogue metadata, admission policy, lifecycle state, and the
application endpoints needed by routing. An incomplete, invalid, or conflicting registration must be
rejected before it can change the Shared Edge.

### AP-PR-003 · Prefix routing and closed failure

The Shared Edge must route a registered prefix and its intended subpaths only to that registration's
application endpoints. The root catalogue, registered prefixes, and platform-owned operational
paths must not shadow one another. An unmatched, suspended, retired, or malformed route must fail
closed without exposing another application or an internal endpoint.

### AP-PR-004 · Application admission

An Application Registration must declare an Admission Mode capable of representing public access,
access for any successfully authenticated identity, and access restricted to an explicitly managed
set. Owner-only access is a restricted policy, not a separate application type. The Shared Edge must
apply the declared admission policy before forwarding a request to a protected application.

### AP-PR-005 · Verified identity context

When admission depends on authentication, the platform must provide the application with verified,
stable issuer-and-subject identity context through a versioned contract. Anonymous requests and
unsigned or unverified identity claims must never be treated as authenticated. Applications remain
responsible for deriving their own immutable principals and for isolating application-owned data.

### AP-PR-006 · Application-owned feature authorization

Admission to an application must not grant access to application features. The Application Owner
retains authority for feature permissions, provider-plan restrictions, provider display and
retention rights, and application-specific revocation. The platform must be able to admit a person
to an application whose own policy then denies a restricted feature, such as live market data.

### AP-PR-007 · Independent application lifecycle

The platform must support registering, updating, suspending, and retiring one application without
changing another application's registration or transferring its Application State into Platform
State. Removing an application route must fail closed and must not destroy application-owned
resources implicitly.

### AP-PR-008 · Fixture-first qualification

Platform behavior must be implementable and qualifiable with deterministic Fixture Applications
before any real application migration. Fixtures must exercise catalogue navigation, route
isolation, public and authenticated admission, restricted admission, verified identity delivery,
application-owned feature denial, unmatched paths, and lifecycle changes without paid providers or
production application data.

The first staging qualification must deploy the public, authenticated, and restricted fixtures
through separate Application State, exchange the same versioned bundles required of a real
application, and exercise deployment, registration, detachment, destruction, redeployment, and
reactivation. Static Terraform, process-local loopback, or an undeployed fixture image is not
staging qualification. Provider-backed fixtures must run in an application project separate from
the platform project and use the same explicit Shared VPC project connection, internal ingress,
edge-caller IAM, project-scoped bundle, and registration boundaries required by an independently
owned GCP application. A same-project fixture cannot qualify cross-project application attachment.

### AP-PR-009 · Explicit application adoption

A real application may adopt the platform only through that application's own requirements,
decisions, contracts, tests, migration, and release process. Platform qualification must not depend
on a real-application migration, and platform documentation must not silently change another
application's behavior or ownership.

### AP-PR-010 · Operator-controlled environment lifecycle

A Platform Operator must be able to prepare, deploy, inspect, qualify, and destroy one explicitly
selected Platform Environment through a small interactive interface. Preparation must discover or
derive available non-secret facts, request only genuine owner decisions, and produce one complete
digest-bound Deployment Specification before mutation. Complete means the environment, source
authority and revision, profile, operation, and reviewed fixed workflow are known; generated
provider values do not have to exist yet. Deployment must execute that workflow in one interactive
session, pause at unavoidable provider-console or external-DNS checkpoints, and resume safely after
interruption without requiring a hand-authored inventory of generated facts.

The lifecycle must keep non-production and production configuration, state, identity, DNS, OAuth,
evidence, and approvals independent. Production preparation must stop when an existing resource has
another owner; it must never import, replace, or claim that resource implicitly.

For an ordinary reversible staging creation or update, the owner's deliberate invocation of the
named lifecycle command selects the operation, and the same process reviews and confirms the exact
specification and plans; no separate out-of-band approval is required. Destruction, purge,
ownership transfer, production cutover, or a scope expansion retains its separately named approval
and stronger confirmation boundary.

Source authority must be explicit and digest-bound. Accepted operations use the exact clean current
protected-main revision. Before merge, a clean pushed pull-request revision whose branch tracks its
matching origin branch and contains current `origin/main` may operate only on staging as Candidate
Source. Candidate specifications, bundles, and qualification evidence must remain distinguishable
from Accepted Source, cannot qualify or authorize production, and cannot overwrite accepted
qualification. After merge, the operator must deploy and qualify the accepted main revision rather
than promoting candidate evidence.

### AP-PR-011 · Versioned platform and application handoff

The platform must generate a versioned, digest-bound Platform Integration Bundle containing only
the non-secret environment and identity values a named application needs to deploy an eligible
attachment. The Application Owner retains deployment authority and returns a versioned Application
Attachment Bundle identifying the application-owned target and the exact Platform Integration
Bundle it consumed. The platform must validate the bundle and provider posture before a complete
Registration Generation may route traffic to the attachment.

The operator must be able to inspect the exact canonical Platform Integration Bundle and
Application Attachment Bundle before registration. A repository-owned Fixture Application may
reuse that prepared pair only while its environment, application, source authority, application
source, platform source and generation, bundle digests, immutable image, and provider posture still
match; inspection never authorizes registration by itself.

An integration bundle must never contain an OAuth client secret, credential payload, Terraform
state, application provider key, or a platform secret reference that the application is not
authorized to consume.

### AP-PR-012 · Reversible attachment and terminal retirement

The platform must support detaching an application without releasing its immutable application
identifier or route reservation, allowing the Application Owner to destroy and later redeploy its
assets before supplying a replacement attachment and reactivating the registration. A detached
route must remain platform-controlled and invoke no application target.

Retirement is a distinct permanent transition. A retired application identifier remains a
tombstone and cannot reactivate. Route release, if later required, is an explicit separately
reviewed operation and never follows automatically from detachment, retirement, application
destruction, or platform-environment destruction.

## Quality requirements

### AP-QR-001 · Exclusive resource and state ownership

Every managed resource must have exactly one state owner. Platform State may own only shared
platform resources and registration-derived edge configuration; Application State must own
application runtimes, data services, providers, and application authorization. The two states may
exchange versioned references but must never manage the same resource.

### AP-QR-002 · Fail-closed security boundary

Protected applications must reject direct public ingress that bypasses the Shared Edge. The
platform must use encrypted transport, least-privilege identities, verified authentication signals,
bounded inputs, and external secret storage. Registration and catalogue inputs are untrusted and
must be validated before they affect routing or rendered content.

### AP-QR-003 · Configurability and extractability

Canonical platform requirements, decisions, contracts, implementation, tests, prompts, and evidence
must remain inside the project root and use project-relative paths. Reusable behavior must not
hard-code the containing repository, Finance Assistant, a cloud project, or a deployment region.
The project must remain operable after history-preserving extraction to a dedicated repository.

### AP-QR-004 · Deterministic and credential-free verification

The default `make check` path must be deterministic, non-mutating, and require no cloud account,
external service, paid provider, browser session, or secret. Live qualification must use separate,
explicit operator actions and produce revision-scoped, secret-free evidence.

### AP-QR-005 · Demo-scale operability and cost control

The initial platform is a low-traffic demonstration environment with reasonable downtime and no
production availability commitment. Shared-platform and application lifecycle operations must be
separate, identify their exact targets and billable resources, and require explicit confirmation
before destructive or data-losing actions.

### AP-QR-006 · Truthful status and recoverable change

Documentation and automation must distinguish proposed, implemented, deployed, and qualified
behavior. A failed registration or platform change must preserve or restore the last reviewed
working configuration, and evidence must record failures, limitations, and skipped qualifications
without implying success.

### AP-QR-007 · Human-operable automation

The normal operator interface must be interactive, documented, and compact. It must discover facts
available from reviewed source and provider readback, derive deterministic values, explain each
manual action at the point of use, and accept an Enter-to-continue acknowledgement without making
the operator restart the lifecycle. Private progress must be machine-produced, atomically
replaced, and never hand-authored. An interrupted operation must report its last accepted stage and
provide a safe resume path. The normal deploy command must perform read-only preparation, specification review,
approval, deployment, and manual checkpoints in one invocation; a separate prepare command is an
optional dry run, not a mandatory operator round trip. When that dry run has already produced a
current approved specification, the normal deploy command must locate and reuse it automatically
after read-only freshness validation; the operator must not copy its digest between commands.
Absent, stale, or unapproved intent must return to normal preparation, while malformed retained
state or a current prerequisite blocker must fail closed. A separate optional preflight command
must expose those readiness blockers without generating a specification or digest, asking for
approval, writing lifecycle state, or mutating an external system. Ordinary reviewed plan
applications use one clear `y/N` confirmation after the plan is shown. Typed phrases are reserved
for destruction, purge, ownership transfer, and similarly irreversible actions.

### AP-QR-008 · Environment isolation

Every Platform Environment must have distinct configuration, state, identities, OAuth client,
DNS/TLS resources, evidence, integration bundles, and destructive authority. An operation must name
exactly one environment and must fail before mutation when a source, project, hostname, state,
identity, or ownership fact belongs to another environment. Staging evidence cannot qualify
production.

### AP-QR-009 · Bounded mutation and readback

Every mutating lifecycle must bind the selected environment, approved Deployment Specification,
exact source revision, exact Terraform plan or bounded provider action, and provider readback. The
reviewed fixed workflow defines stage order, resource policy, and how later steps consume generated
values. Any unapproved resource type, owner, environment, destructive action, or scope expansion
stops the lifecycle and requires new preparation and approval. Manual provider steps must be
recorded as operator-attested when no readback exists and must never be described as
provider-verified.

## Security, privacy, and rights invariants

- The platform stores no application prompts, portfolios, goals, provider payloads, or other product
  data merely because it routes an application.
- Identity context contains only the fields required by the approved identity contract; it is not a
  shared user profile or a cross-application principal.
- Provider credentials, plans, use rights, display rights, caching rights, retention rights, and
  spending limits remain application-owned.
- Catalogue and registration metadata must be safe to expose at their declared visibility and must
  never be used as trusted executable input.
- No credential, secret value, Terraform state, saved plan, authenticated browser state, or
  unredacted external payload may be committed.

## Non-goals for the initial platform

- General-public production hosting, high availability, or a zero-downtime service-level objective
- Ownership of application runtimes, databases, vector stores, queues, provider integrations, or
  business data
- A central feature-entitlement service or a shared cross-application user database
- Automatic adoption or migration of Finance Assistant or any other application
- Multi-cloud portability or abstraction over every compute and identity provider
- Infrastructure implementation, live DNS mutation, credential creation, or cloud qualification in
  this documentation slice

## Decisions deferred to subsequent authorities

The accepted architecture decisions, system design, contracts, implementation plan, and evaluation
strategy will determine the following without weakening these requirements:

- the initial cloud resource topology and application-attachment mechanism;
- the identity assertion, verification, and forwarding contract;
- the registration schema, lifecycle state machine, and update transaction;
- the catalogue presentation and catalogue-visibility policy;
- operator roles, audit retention, rollback procedures, and evidence schemas; and
- the exact fixture implementation and live qualification environments.

Discussion history is not authority for those decisions. Until the corresponding documents are
approved, they remain unresolved and no implementation may infer them.

## Acceptance boundary

Each requirement must be traced to future system-design components, implementation-plan work,
deterministic tests, and evaluation evidence before it may be called qualified. The existence of
this document is requirements evidence only; it is not implementation or deployment evidence.
