# Comfforts App Platform

Status: AP-M6 is locally implemented and passes its deterministic AP-EVAL-M6 repository gate.
Immutable generation loading, catalogue and routing, Platform Sessions and admission, identity
assertions and application verification, Cloud Run attachment resolution, bounded HTTP, SSE, and
WebSocket proxying, read-only status, correlation, adapter-health observations, and redacted
completion events are implemented locally. AP-M4 remains Fixture-qualified and AP-M5 remains
planning-validated. AP-M6 supplies repository implementation evidence only. AP-M7 Terraform-and-
workflow implementation authority is defined. AP-M7-W2 implements the pinned Terraform foundation,
and AP-M7-W3 implements only the Version 1 non-secret configuration schemas, synthetic examples,
and deterministic loader and semantic policy. AP-M7-W4 implements static backend-bootstrap and
state-bucket configuration. AP-M7-W5 implements three isolated Fixture Application roots, one
internal runtime module, and typed attachment references with plan-only mocked-provider tests.
AP-M7-W6 implements the Platform State identity and immutable-generation foundation. AP-M7-W7
implements the immutable Shared Edge candidate and hostname-forwarding topology. AP-M7-W8
implements the bounded observability, evidence-retention, artifact-retention, label, scaling, and
cost-control intent. AP-M7-W9 implements the five inert operator-workflow authority templates. All
Terraform roots pass plan-only mocked-provider tests, and every workflow template passes static
non-mutation policy. No backend was initialized, provider operation performed, cloud resource
created, generation uploaded or activated, or deployment, Live evidence, or Application Adoption
qualified.

Comfforts App Platform is a separately governed project in its canonical dedicated repository. The
history-preserving extraction, dedicated-repository settings, reconciliation, explicit authority
cutover, and source-repository cleanup are complete. Nothing in the extraction changed the current
Finance Assistant deployment, requirements, or Terraform ownership.

The project will be implemented and qualified with deterministic fixture applications before any
Finance Assistant migration is proposed. Draft application integrations remain inactive until the
consuming application adopts them through its own requirements and release process.

## Local verification

From the dedicated repository root:

```bash
make terraform-setup
make check
```

`terraform-setup` downloads only the checksum-pinned public Terraform CLI and locked provider into
the ignored project-local cache. `check` is credential-free, offline, and non-mutating. It does not
access GCP, DNS, IAP, provider accounts, or the live Finance Assistant deployment.

## Project authority

Read `AGENTS.md` before changing this project and follow the authority and reading order in
`docs/README.md`. Product requirements, accepted architecture decisions, system design, threat
model, AP-M3 through AP-M6 plan and evaluation authority, and Version 1 contracts are authoritative
within their declared boundaries. The contract layer supplies Contract (`C`) evidence, and the
in-process harness supplies Fixture (`F`) evidence only; AP-M5 supplies planning authority rather
than provider or deployed evidence.

AP-M3 through AP-M5 are merged and pass their deterministic gates. AP-M6-W1 through AP-M6-W11 are
implemented locally, and the complete credential-free `make check` gate passes. AP-M6-W2 supplies
the locked dependency environment and closed-default ASGI foundation. AP-M6-W3 adds bounded
compiled-generation parsing, exact object/content/generation binding, and an injected
Cloud Storage source adapter. It performs no provider call during construction or verification and
cannot discover, compile, activate, or mutate a generation. AP-M6-W4 renders the compiled catalogue
and performs canonical, lifecycle-aware route and mount selection.
AP-M6-W5 adds Google OIDC authorization-code-with-PKCE behavior, opaque host-only eight-hour
Platform Sessions, Firestore and in-memory session adapters, optional public identity, exact
issuer-and-subject restricted admission, and platform-owned logout. Deterministic tests replace
provider and Firestore I/O; no OAuth credential or provider operation is required. No AP-M6 package
authorizes Terraform, cloud, DNS, identity configuration, deployment, or Live mutation.

AP-M6-W6 replaces admitted identity at the route handoff with a minimized, application-audience-
bound ES256 assertion. It adds deterministic and Cloud KMS signing adapters, public-only JWKS with
current/overlap keys, and an independent application verifier with bounded caching and fail-closed
refresh behavior. Fixed synthetic keys and provider fakes exercise the adapters locally; no KMS
key, credential, external request, or provider resource is used.

AP-M6-W7 strictly parses the `gcp-cloud-run-v1` resource URN and resolves only that exact service
through an injected Cloud Run metadata adapter. Resolution requires matching project, region,
service, Application State owner, readiness, application audience, and an unconditional edge-caller
Invoker grant before the provider-derived target can reach the internal handoff. Deterministic
metadata exercises success and every closed mismatch; no provider call, IAM mutation, target
request, credential, or cloud resource is used.

AP-M6-W8 forwards an eligible resolved request through one bounded application proxy. It preserves
the rewritten path and raw query, obtains a Cloud Run service-identity token, strips hop-by-hop and
visitor-controlled identity headers, installs the platform assertion, and supports buffered HTTP,
streaming HTTP/SSE, uploads, downloads, and bidirectional WebSockets. Exact request, response,
message, timeout, concurrency, and process-local rate limits fail closed and cancel bounded work.
Production transports are exercised only against ephemeral loopback servers or deterministic
fakes; no external target, service identity, credential, cloud resource, or Live route is used.

AP-M6-W9 adds an operator-authorization seam and a read-only `/_platform/status` operation exposing
only source revision, generation facts, and coarse local adapter health. One generated correlation
identifier follows each HTTP or WebSocket boundary into application delivery and any identity
assertion. A typed completion-event allow-list retains only revision/generation facts, normalized
application and route identifiers, coarse outcome, status class, latency, correlation, and
non-secret component versions. Tests prove prohibited request, response, identity, visitor,
provider, credential, state, and plan data cannot enter that shape. An injected standard-logging
adapter exists, but no log bucket, sink, retention rule, operator identity configuration, provider
call, credential, or Live readback is created or qualified.

AP-M6-W10 enforces the complete AP-EVAL-M6 matrix, including exact numeric boundaries, immutable
generation and identity paths, fake-provider parity, streaming cancellation and isolation,
loopback-only networking, history-independent extraction, dependency locking, redaction, and all
prior regressions. AP-M6-W11 reconciles this status. AP-M7-W1 defines the detailed Terraform-and-
workflow implementation authority. AP-M7-W2 implements its pinned, credential-free Terraform
foundation and deterministic offline root validation. AP-M7-W3 implements the five closed
configuration contract families. AP-M7-W4 implements the deep bootstrap root and internal hardened
state-bucket module without an IAM principal, backend operation, or provider call. AP-M7-W5
implements the three deep Fixture Application roots and their internal Cloud Run runtime module,
runtime identities, protected ingress, edge-only Invoker intent, bounded scaling, required labels,
non-secret platform references, and typed `gcp-cloud-run-v1` attachment outputs. All provider
behavior is mocked and plan-only. AP-M7-W6 implements the deep Platform foundation module and root
for private versioned configuration storage, immutable generation metadata, Firestore Native
Platform Sessions with TTL and eight-hour application expiry intent, separate edge runtime and
caller identities, regional software ES256 signing with manual-rotation intent, versioned OAuth
secret references, least-privilege access intent, and minimal typed platform outputs. AP-M7-W7
implements the deep Shared Edge module and Platform State composition for one immutable Cloud Run
candidate, closed direct-origin posture, bounded scaling and timeout profile, typed Fixture
Application references consumed only as data, one global address and serverless backend, managed-
certificate intent, hostname-only HTTPS forwarding, and HTTP-to-HTTPS redirect. All provider
behavior remains mocked and plan-only; no DNS record, application runtime, credential, backend
operation, provider operation, deployment, or Live evidence exists. AP-M7-W8 adds a regional
seven-day log bucket, minimized internal sink, and `_Default`-bucket exclusion, private 30-day
evidence storage, explicit owner-readable access intent, a USD 20 notification-only budget,
dry-run-first Artifact Registry retention, required-label and runtime-cap policy, and explicit
prohibited-capability assertions. It uploads no evidence or image, exports no log, and performs no
automatic budget or cleanup mutation. AP-M7-W9 adds parseable, non-executable advisory-plan,
exact-main apply, rollback, force-unlock, and destroy templates outside `.github/workflows/`. They
use only unresolved operator placeholders, full-length action pins, read-only default permissions,
protected-main/source and plan-digest binding, root concurrency, runner-temporary plans, same-job
plan/apply, explicit destructive confirmation, and secret-free outcome metadata. After owner
acceptance of AP-M7-W9, AP-M7-W10 is next; AP-M7 remains one separate branch and pull request.

All platform files are project-relative at the dedicated repository root. Repository extraction
preserved their history. The separately reviewed source cleanup removed the historical colocated
tree and containing-repository CI wrapper; it supplied no platform implementation authority.
