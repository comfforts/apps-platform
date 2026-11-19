# App Platform threat model

Version 1.7 | Status: Fixture-qualified threat model, implemented AP-M6/AP-M7 controls, and
implemented AP-M9-W5 repository lifecycle controls; no provider operation or live
infrastructure is deployed

This document defines the security and privacy threats created by the logical App Platform design,
assigns control ownership, and names the evidence required before a control may be called
implemented or qualified. It is authoritative only inside the App Platform project. It does not
configure identity, provision infrastructure, mutate DNS, activate an application, or change a
consuming application's security model.

Requirements: AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006

Decisions: ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009

System design: [App Platform system design](03_system_design.md)

## Scope and status

The threat boundary includes:

- offline registration, contract validation, compilation, review, and evidence;
- the future Shared Edge, root catalogue, routing, admission, and identity delivery;
- Application Attachments and the platform-to-application request seam;
- Platform State, Application State references, lifecycle, rollback, and drift;
- Fixture Applications used for future platform qualification; and
- future Application Adoption where a real application consumes platform contracts.

The boundary excludes application product behavior except where the platform could bypass,
confuse, broaden, or interfere with application-owned controls. Vulnerabilities wholly inside an
application remain the Application Owner's responsibility, while route isolation, identity
delivery, direct-bypass prevention, and cross-application effects remain in scope for the platform.

No runtime control is operational merely because it is specified here. Deterministic contract
evidence, Fixture Application evidence, live provider readback, and application-adoption evidence
are different gates and are never substitutes for one another.

## Security objectives

The platform must preserve these objectives:

1. **Route integrity:** one canonical request path selects at most one reviewed application
   attachment, and every unknown or invalid path fails closed.
2. **Admission integrity:** public, authenticated, and restricted Admission Modes are enforced as
   registered without granting application Feature Entitlements.
3. **Identity authenticity:** only a verified issuer-and-subject assertion for the intended
   application audience can become Verified Identity Context.
4. **Application isolation:** one application's route, identity, failure, compromise, or lifecycle
   action does not expose or mutate another application.
5. **Exclusive ownership:** each managed resource has one state owner and cross-state references
   never become write authority.
6. **Configuration integrity:** only a complete, reviewed Registration Generation can become the
   Shared Edge configuration, and failed change preserves or restores the last reviewed generation.
7. **Data minimization:** the platform stores, renders, logs, and evidences only the data required
   for catalogue, routing, admission, identity verification, and accountable operation.
8. **Truthful evidence:** deterministic, fixture, live, and adoption results state their exact
   revision, environment, limitations, failures, and skipped gates.

## Assets and data classes

| Asset or data | Classification | Protection objective |
| --- | --- | --- |
| Configured hostname, route table, and catalogue | Public behavior, controlled configuration | Integrity and availability |
| Registration Sets and compiled generations | Platform configuration | Integrity, provenance, review, rollback |
| Attachment resource references | Restricted platform configuration | Integrity, non-disclosure where provider identifiers are sensitive |
| Restricted admission membership | Restricted identity policy | Confidentiality, integrity, minimal access |
| Signed identity assertions and identity claims | Restricted authentication data | Authenticity, confidentiality, replay resistance |
| State-owner references and manifests | Restricted operational metadata | Integrity and exclusive ownership |
| Credentials, signing keys, OAuth secrets, and state contents | Secret; prohibited from contracts and Git | Confidentiality and non-persistence |
| Platform logs and qualification evidence | Restricted unless explicitly safe for publication | Redaction, provenance, retention limits |
| Application data and provider payloads | Outside platform ownership | Non-collection and non-disclosure |

Catalogue output is public only after safe projection. Registration input is not public catalogue
content and must not be rendered, logged, or published wholesale.

## Actors and trust assumptions

- An **anonymous Visitor** is untrusted and may send malformed paths, spoofed headers, oversized
  inputs, or abusive traffic.
- An **authenticated identity** has proven only the configured identity assertion. Authentication
  does not imply restricted admission, application resource ownership, or a Feature Entitlement.
- An **Application Owner** is trusted to control only that application's state and to propose
  accurate attachment references. Its registration remains untrusted until validated and reviewed.
- A **Platform Operator** has bounded operational authority and may make mistakes or use a
  compromised workstation or credential. Review and readback remain required.
- The **Platform Owner** approves requirements, registrations, destructive shared-resource change,
  and live qualification. Approval cannot override a failed contract or weaken an accepted ADR
  without changing the authority first.
- A **Registered Application** is mutually untrusted with every other application. A compromised
  application must not gain Shared Edge control, another audience, or another application's state.
- The future **identity provider and cloud provider** are external trust dependencies. The platform
  must verify their configured signals and fail closed, but their internal compromise is residual
  provider risk outside this project's direct control.
- Source control and continuous integration are part of the future configuration control plane.
  Repository write access is privileged but does not by itself authorize live mutation.

Finance Assistant is not a trusted platform test harness. Its Integration Draft is untrusted input
to a future adoption review and grants no platform or Finance authority.

## Trust zones and flows

```text
  [Public Visitor]
         |
         | untrusted requests and headers
         v
  [Shared Edge data plane] <--------> [Identity provider]
         |
         | admitted request + signed identity assertion
         v
  [Application Attachment] ---------> [Application runtime and state]

  [Application Owner proposal]
         |
         | untrusted Registration Set
         v
  [Repository + review] -> [Registration Compiler] -> [compiled generation]
                                                        |
                                                        | future reviewed apply
                                                        v
                                            [Provider control plane + Platform State]
```

The major trust-boundary crossings are:

1. Visitor input crossing into the Shared Edge.
2. Identity-provider output crossing into platform admission.
3. Admitted traffic and identity crossing from the Shared Edge to an attachment.
4. Application-owner input crossing into platform configuration review.
5. Compiled configuration crossing from the repository into a provider adapter.
6. Resource references crossing between Platform State and Application State without shared write
   access.
7. Logs and evidence crossing from restricted operational systems into retained artifacts.

## Control ownership

### Platform-owned controls

- strict registration schemas and semantic validation;
- canonical route parsing, reserved-path enforcement, and closed unmatched behavior;
- safe catalogue projection and output-context escaping requirements;
- attachment-adapter allow-listing and registration-derived edge configuration;
- Admission Mode enforcement and removal of visitor-supplied identity headers;
- whole-generation activation, drift detection, rollback, and Platform State access control; and
- platform log minimization, redaction, and revision-scoped evidence.

### Application-owned controls

- runtime and endpoint access policy, including rejection of direct protected ingress;
- independent assertion signature, issuer, audience, time, and contract-version validation;
- immutable Application Principal derivation and application-data isolation;
- Feature Entitlements, provider rights, product roles, and application revocation; and
- attachment deployment, health, rollback availability, and Application State recovery.

### Jointly coordinated controls

- attachment compatibility, audience and caller-principal exchange, and release ordering;
- lifecycle activation, suspension, retirement, and rollback windows;
- proof that cross-state resource references have one owner; and
- future adoption, state transfer, cutover, and rollback.

Joint coordination does not create joint state ownership. Each resource and control still has one
named owner.

## Evidence classes

| Class | Earliest delivery item | What it can prove | What it cannot prove |
| --- | --- | --- | --- |
| Contract (`C`) | Item 3 | Schema, semantic, transition, ownership, and deterministic compilation behavior | Runtime routing, cryptography, ingress, or cloud state |
| Fixture (`F`) | Item 4 | Observable platform behavior using synthetic registered applications | A real application's compatibility or live cloud configuration |
| Live (`L`) | Item 5 or later | Provider configuration, DNS/TLS, IAM, direct-bypass controls, drift, and operator procedures | Application Adoption or product authorization correctness |
| Adoption (`A`) | Application-owned later slice | One real application's compatibility, state handoff, product isolation, and rollback | Generic platform qualification for other applications |

An evidence requirement marked `F`, `L`, or `A` remains deferred even if all contract tests pass.
Live evidence must be secret-free and revision-scoped; screenshots or unredacted provider payloads
are not default evidence.

### Item 4 deterministic Fixture profile

Delivery item 4 uses the `fixture-in-process-v1` adapter and one synchronous Python
standard-library request pipeline. It has no listening socket, network ingress, external identity
provider, live credential, persistent registration store, provider resource, or concurrency. The
fixture application set contains separate public, authenticated, and restricted applications with
separate Fixture Application State.

The fixture pipeline accepts only `GET`, an empty body, paths and queries of at most 1,024 UTF-8
bytes each, at most 32 headers, header names of at most 64 ASCII bytes, header values of at most
1,024 UTF-8 bytes, at most 8,192 aggregate header bytes, and responses of at most 65,536 UTF-8
bytes. A 16-byte method limit is applied before method selection. There is no connection or stream
to limit; live connection, rate, concurrency, and timeout controls remain unresolved.

Synthetic protected admission uses a deterministic fixture-only HMAC-SHA-256 assertion envelope
around the Version 1 Verified Identity Context. Public test key material is injected, assertion
lifetime is at most 60 seconds, clock skew is zero, and each fixture owns a 256-entry fail-closed
replay store. These choices permit deterministic testing of signature, issuer, subject, audience,
time, cross-application, and replay failures. They are not evidence for a production identity
provider, algorithm, key custody, rotation, or network-origin control.

Fixture registration inputs are reviewed complete generations. Successful compilation installs a
complete generation into an in-memory reviewed-generation collection and atomically changes one
current pointer; rejection preserves the prior generation. There is no registration API or
database. Fixture Application State remains independently constructed and is never rolled back or
deleted by a platform generation change.

The detailed topology and evidence exclusions are owned by the [system design](03_system_design.md).
Until the separate item 4 plan, implementation, and evaluation record are accepted, this profile
is design authority and produces no Fixture (`F`) evidence.

## Threat register

### AP-TM-001 · Registration injection and unsafe catalogue content

**Scenario:** An Application Owner or compromised repository change supplies unknown fields,
executable-looking values, control characters, markup, oversized text, credentials, provider
commands, or private metadata. The values could alter compilation, create stored script injection,
or leak data through the root catalogue.

**Required controls:** Strict schemas reject unknown and out-of-bound values. Catalogue fields are a
small plain-text projection with no HTML, scripts, images, arbitrary links, attachments, allow-list
members, or secrets. Renderers escape every value for its output context. Registration data never
becomes an executable provider command.

**Evidence:** `C` covers valid and invalid vectors, size limits, unknown fields, unsafe characters,
and deterministic safe projection. `F` covers rendered catalogue behavior. `L` covers deployed
headers and renderer configuration where applicable.

**Residual risk:** AP-M6-W4 implements local escaped HTML projection with a no-store response. Live
headers, browser behavior, and provider limits remain unqualified until the deployed gates pass.

### AP-TM-002 · Route confusion, shadowing, and traversal

**Scenario:** Ambiguous prefixes, textual prefix matching, encoded separators, dot segments,
case-folding, Unicode lookalikes, attachment-mount overlap, or reserved-path collision routes a
request to the wrong application or platform handler.

**Required controls:** Registration uses canonical lowercase segment paths, fixed reserved paths,
segment-bounded matching, deterministic longest attachment-mount selection, and rejection rather
than normalization of alternate encodings. The complete Registration Set is validated for
conflicts. Unknown and malformed paths fail closed without fallback to another application.

**Evidence:** `C` covers canonicalization, conflicts, mount selection, and closed compilation.
`F` covers exact paths, subpaths, near-prefixes, encodings, reserved paths, and unmatched requests.
`L` confirms the provider adapter implements the same behavior.

**Residual risk:** AP-M6-W4 compares raw and decoded ASGI paths, rejects alternate encodings, and
uses segment-bounded route and mount selection locally. AP-M6-W8 preserves the selected rewritten
path and raw query in process-local transport tests. Uvicorn and provider-specific decoding still
require their later conformance and Live gates before qualification.

### AP-TM-003 · Malicious or mistaken attachment reference

**Scenario:** A registration names an arbitrary URL, credential-bearing value, another
application's runtime, an unsupported adapter, or a resource the proposer does not own. Validation
or routing could become server-side request forgery, credential disclosure, or cross-application
access.

**Required controls:** Attachment kinds and resource-reference forms are allow-listed and bounded.
References are treated as inert data; offline validation performs no fetch or provider discovery.
The immutable application identifier, attachment identifier, mount, forwarding mode, identity
requirement, and ownership entry must agree. Secrets and Terraform state addresses are forbidden.
Provider adapters resolve only their own typed references with least-privilege credentials.

**Evidence:** `C` covers unsupported kinds, malformed references, secrets, duplicate ownership, and
cross-registration conflicts. `F` covers attachment selection and application isolation. `L`
confirms resource identity, IAM, and absence of arbitrary egress.

**Residual risk:** AP-M6-W7 strictly parses `gcp-cloud-run-v1` and locally validates exact fake
provider scope, readiness, declared owner, audience, target origin, and edge-caller grant. The
production adapter is implemented behind an injected client, but no real provider lookup, IAM
grant, ownership readback, target request, or Live qualification has occurred.

### AP-TM-004 · Direct protected-origin bypass

**Scenario:** A Visitor reaches an application runtime without crossing platform admission, or
spoofs the platform identity header against a publicly reachable origin.

**Required controls:** Application State restricts protected runtime ingress to the Shared Edge
caller using provider or network controls. The Shared Edge strips visitor-supplied identity headers.
The application independently verifies the signed assertion and application-specific audience. A
header alone never compensates for a public protected origin.

**Evidence:** `C` can prove only that protected attachments declare the required identity and
ingress posture. `F` exercises spoofed headers and direct calls to protected fixture entry points,
but can prove only assertion-side denial in one process. `L` must read back and test the actual
ingress and IAM configuration. `A` repeats the gate for a real application.

**Residual risk:** AP-M6-W6 implements local visitor-value replacement and independent assertion
verification. AP-M6-W7 rejects fake metadata without the exact edge-caller Invoker grant, but it
does not create or prove that caller, Cloud Run ingress, or network isolation. AP-M6-W8 strips
visitor authorization and identity values, installs edge-controlled service identity and the
application assertion, and forwards only the resolved origin in local tests. The load balancer and
deployed network direct-bypass control remain future work. Local metadata, transport, and verifier
denial must never be reported as origin isolation.

### AP-TM-005 · Identity spoofing, replay, and confused audience

**Scenario:** An unsigned, expired, replayed, wrong-issuer, wrong-audience, or visitor-controlled
assertion is treated as Verified Identity Context. An assertion for one application is reused
against another, or mutable email is treated as an ownership key.

**Required controls:** Admission and the application validate signature, configured issuer,
immutable subject, application-specific audience, issued and expiry times, and contract version.
Visitor values are removed before edge forwarding. Restricted policy matches exact issuer-and-
subject pairs. Applications derive their own principals and never use email as an ownership key.

**Evidence:** `C` covers claim shape and rejection semantics, not cryptographic validity. `F` covers
missing, forged, expired, wrong-issuer, wrong-audience, and cross-application assertions. `L` covers
signer, key discovery, algorithms, audience issuance, and clock behavior.

**Residual risk:** AP-M6-W5 locally validates Google OIDC through a PKCE-bound, one-use flow and
matches restricted identities by exact issuer and subject. AP-M6-W6 locally issues and independently
verifies minimized ES256 assertions with exact audiences, 60-second lifetimes, 30-second skew,
versioned keys, and bounded public-key overlap/cache behavior. Cloud KMS operation and application
delivery remain unqualified. The demo accepts residual cross-instance replay risk because it makes
no distributed replay-prevention claim.

### AP-TM-006 · Admission mistaken for feature authorization

**Scenario:** Successful platform admission is interpreted as permission to use restricted
application features, provider data, or another user's resources.

**Required controls:** Registration schemas contain no Feature Entitlement or product-role fields.
The platform makes only an Admission Decision. Each application derives an Application Principal,
isolates application data, and independently enforces every entitlement and provider right.

**Evidence:** `C` rejects feature-authorization fields in platform contracts. `F` proves an admitted
identity can use an unrestricted fixture feature while the fixture denies a market-data-style
entitlement. `A` qualifies a consuming application's actual product and provider boundaries.

**Residual risk:** Platform qualification cannot prove any real application's authorization or
provider rights.

### AP-TM-007 · Stale, concurrent, partial, or unsafe lifecycle change

**Scenario:** Two proposals race, a stale generation overwrites a reviewed one, catalogue and route
updates diverge, a suspension leaves a route active, or a failed attachment replacement destroys
the rollback target.

**Required controls:** Each complete Registration Set carries a monotonic generation and preceding
digest. The compiler enforces lifecycle transitions and produces one canonical generation. Future
activation is atomic across catalogue, routes, admission, attachments, and ownership. The old
attachment and Last Reviewed Working Configuration remain available through the declared rollback
window.

**Evidence:** `C` covers stale digests, invalid transitions, deterministic generations, and
all-or-no-output failure. `F` covers register, update, suspend, retire, attachment replacement, and
rollback journeys. `L` covers provider partial-failure recovery and drift.

**Residual risk:** GCS locking, protected-main concurrency, immutable edge revisions, and one
traffic pointer are selected but not implemented. Terraform cannot make several provider control
planes transactional, so partial failure still requires stop, readback, inspection, and an
owner-approved recovery decision.

### AP-TM-008 · Dual state ownership or destructive cross-state action

**Scenario:** Platform State and Application State manage the same resource, one side deletes the
other's resource during lifecycle change, or a migration imports before the previous owner releases
management.

**Required controls:** The State Ownership Manifest assigns each canonical resource reference to
one owner. Platform lifecycle never mutates application-owned runtime or data; application
lifecycle never mutates Shared Edge resources. Cross-state exchange is versioned reference data,
not backend access. Destructive actions identify exact targets and require explicit review.

**Evidence:** `C` rejects duplicate owners and ownership/type mismatches. `F` covers independent
fixture and platform lifecycle. `L` covers state inventories, plans, readback, and destructive-action
guards. `A` proves exclusive ownership at every transfer phase for a real application.

**Residual risk:** Separate roots and buckets reduce accidental cross-owner access but do not prove
exclusive ownership until state inventory, IAM, provider readback, and destructive plans are
qualified together.

### AP-TM-009 · Cross-application lateral movement

**Scenario:** A compromised application receives another route, reuses another audience, accesses
another attachment, influences the catalogue, or obtains platform credentials capable of changing
the Shared Edge.

**Required controls:** Routes and attachment identifiers are unique and registration-derived.
Identity audiences and Application Principals are application-scoped. Applications receive no
Platform State credentials or registration write access. Provider adapters and edge callers use
least-privilege identities, and one unavailable application never becomes another's fallback.

**Evidence:** `C` covers unique identifiers, ownership, and audience binding. `F` covers route,
identity, failure, and lifecycle isolation between at least two registrations. `L` covers actual IAM
and credential scope.

**Residual risk:** Shared Edge compromise has hostname-wide impact and requires provider hardening,
operator separation, audit, and recovery evidence in later slices.

### AP-TM-010 · Secret, identity, or application-data leakage

**Scenario:** Credentials, restricted membership, signed assertions, provider payloads, request
bodies, application data, Terraform state, or authenticated browser artifacts enter contracts,
logs, plans, test vectors, evidence, or Git.

**Required controls:** Contracts accept only non-secret references and bounded identity policy.
Synthetic values are used in tests. Logs and evidence allow only contract versions, generation
digests, application and route identifiers, coarse outcomes, violation codes, and correlation
identifiers. Secret payloads and application data are prohibited and externally stored.

**Evidence:** `C` includes secret-pattern and prohibited-field checks over committed contract
artifacts. `F`, `L`, and `A` inspect generated evidence and logs for redaction without recording the
prohibited payloads themselves.

**Residual risk:** AP-M6-W9 implements one typed, minimized local completion-event shape, shared
correlation, an injected standard-logging seam, prohibited-data tests, and an operator-authorized
read-only status response. It configures no provider sink or bucket. Seven-day owner-only logging,
30-day evidence, no external export, and provider audit behavior remain unimplemented and
unqualified until their infrastructure and Live gates pass. Provider-mandated audit metadata may
still include operator or network information and remains subject to provider access and retention
behavior.

### AP-TM-011 · Unauthorized control-plane change, drift, or supply-chain substitution

**Scenario:** A repository, dependency, workflow, operator credential, or provider-console change
alters routing or admission outside the reviewed Registration Generation. Validation tooling or
contract schemas are substituted between review and apply.

**Required controls:** Canonical output is bound to input and compiler versions by digest. Protected
review covers schemas, registrations, validation code, and provider plans. Default checks are
deterministic and credential-free. Live mutation uses separate explicit operator actions. Manual
provider changes are drift and never become configuration authority.

**Evidence:** `C` covers deterministic output, schema identifiers, test-vector expectations, and
extraction-safe checks. `L` covers revision binding, workload identity, least privilege, drift
readback, plan review, and audit records.

**Residual risk:** Protected-main is configured and AP-M7 statically verifies exact-plan binding in
inert templates. Workload Identity Federation and executable mutation workflows remain unavailable.
The accepted AP-M8-W1 profile below supplies no operational control. AP-M8-W2 adds only a local
manifest contract and validator. The same
owner may review and apply, so environment checkpoints, retained evidence, and drift readback
remain important compensating controls.

### AP-TM-012 · Availability and cost abuse

**Scenario:** Oversized registrations, catalogue fields, path inputs, authentication attempts,
request bodies, streaming connections, or traffic volume exhaust validation, edge, identity,
logging, application, or billable provider capacity.

**Required controls:** Contracts place numeric size and count limits on every collection and string.
Compiler work is bounded and performs no external calls. AP-M6 adapters enforce the approved
`qualification-v1` request, header, body, connection, message, duration, concurrency, per-client,
and per-instance limits; cancel closed work; isolate application failures; and expose no implicit
cost-bearing action. Rate or abuse controls must not silently broaden admission.

**Evidence:** `C` covers contract boundary values and deterministic rejection. `F` covers the
in-process profile. AP-EVAL-M6 covers the exact network-runtime profile with deterministic boundary
and isolation tests but no load claim. `L` covers provider quotas, timeouts, alerts, billable-resource
inventory, and observed multi-instance behavior.

**Residual risk:** AP-M6-W2 implements construction-time profile rejection and an unconfigured
closed response. AP-M6-W3 bounds compiled-generation bytes and fails closed on load or validation
failure. AP-M6-W4 enforces the 4,096-byte path limit. AP-M6-W5 bounds identity query and cookie
inputs and uses absolute session and login-flow expiry. AP-M6-W8 implements the remaining request,
body, response, stream, message, duration, concurrency, and process-local rate limits and cancels
closed work in deterministic tests.
The AP-M6 token buckets are per instance, are not a WAF or distributed rate limit, and can permit
twice their per-instance values when both selected instances are active. Provider limits can be
exceeded briefly, and budget notifications do not cap spend.

### AP-TM-013 · External dependency failure or stale trust material

**Scenario:** DNS, TLS, identity-provider keys, certificates, attachment resolution, or provider
control-plane operations fail or become stale. The platform falls back to insecure routing or
accepts identity it can no longer verify.

**Required controls:** Protected admission and identity verification fail closed. Unknown routes do
not fall back to an application. Provider failure for one attachment does not reroute to another.
Configuration retains the Last Reviewed Working Configuration and records unavailable or partial
status without implying success.

**Evidence:** `F` covers logical dependency failure using deterministic adapters. `L` covers actual
DNS, TLS, key rotation, certificate, provider failure, and recovery behavior.

**Residual risk:** Local immutable-generation loading fails startup on source, contract, or digest
failure. AP-M6-W5 fails protected admission closed on provider or session-store failure while public
routes remain anonymously usable. AP-M6-W6 fails protected assertion issuance and stale or
unavailable verification keys closed; public routes may remain anonymous. AP-M6-W7 fails one
unavailable or mismatched attachment closed without selecting another target. AP-M6-W8 maps local
transport failure, timeout, malformed response, disconnect, and cancellation to closed outcomes
without another target. The selected DNS, certificate, activation, and owner-confirmed rollback
sequence is not implemented or qualified. Provider availability and disaster recovery beyond the
15-minute post-approval rollback objective remain outside the demo commitment.

### AP-TM-014 · Integration Draft or fixture mistaken for Application Adoption

**Scenario:** A draft integration, synthetic fixture result, or platform qualification is treated as
permission to migrate a real application, broaden admission, transfer resources, or supersede the
application's requirements and security decisions.

**Required controls:** Integration Drafts remain outside both authority chains until adopted.
Fixtures use synthetic state and cannot depend on a real application. Adoption names compatible
contract revisions, application-owned authority changes, state-owner transitions, cutover,
rollback, and product-specific evidence. One project cannot approve another project's change.

**Evidence:** `C` preserves authority labels and dependency checks. `F` proves only generic platform
behavior. `A` is mandatory for every real application and retains its prior historical evidence.

**Residual risk:** Human process can still misstate adoption; truthful status checks, review, and
release ownership are required at every handoff.

## AP-M7 infrastructure-configuration controls

AP-EVAL-M7 covers the static infrastructure profile without treating configuration as an
operational control. The following controls refine the existing threats:

- **AP-TM-001 through AP-TM-003:** Version 1 configuration schemas, Terraform root validation, and
  mocked plans accept only complete immutable generations, canonical typed attachment references,
  named state owners, allow-listed adapters, and one hostname-level route authority. Arbitrary URLs,
  provider commands, mutable image tags, application-prefix URL-map routes, and discovered targets
  are rejected.
- **AP-TM-004 through AP-TM-006:** Fixture roots configure protected ingress and edge-caller intent;
  the platform root keeps workload identity separate from Visitor assertions; every application
  audience remains distinct; and no IAM or infrastructure value grants a Feature Entitlement.
  These are static intents until AP-EVAL-M9 proves provider enforcement.
- **AP-TM-007:** Immutable source, image, generation, object, and plan digests, explicit predecessor
  inputs, root-scoped concurrency templates, backend-lock intent, and one 100-percent candidate
  traffic value prevent a configuration from describing a partial registration activation.
  Workflow templates stop on failure and never auto-retry, unlock, roll back, change DNS, or destroy.
- **AP-TM-008 and AP-TM-009:** The bootstrap, platform, and three Fixture Application roots have
  disjoint resource allow-lists. Cross-state values conform to typed non-secret reference contracts;
  `terraform_remote_state`, backend-object reads, application credentials, and cross-owner resource
  management are forbidden. Reusable modules own no environment or state.
- **AP-TM-010:** Schema examples, variables, outputs, plan policy, workflow templates, logs, and
  evidence reject secret values, credentials, restricted membership, assertions, sessions, visitor
  data, application data, state addresses or contents, saved plans, and raw provider responses.
  Secret Manager and KMS inputs are versioned references only.
- **AP-TM-011:** Terraform 1.17.2, `hashicorp/google` 8.11.0, provider checksums, action commit pins,
  protected-main and environment placeholders, exact source/plan digest binding, an offline
  filesystem mirror, and extraction tests constrain supply-chain and control-plane substitution.
  Only the existing read-only check workflow is executable during AP-M7.
- **AP-TM-012:** Static policy fixes one non-production environment, one load balancer, zero-minimum
  bounded Cloud Run services, selected CPU, memory, concurrency and timeouts, seven-day logs,
  30-day evidence, approved services, required labels, USD 20 notifications, and no automatic cost
  mutation. It supplies no availability or spend guarantee.
- **AP-TM-013:** Missing tools, locks, configuration, operator inputs, mirrors, references, or mocked
  provider results fail the gate. Provider failures in later templates stop for inspection and keep
  rollback, unlock, state recovery, and destroy under separate explicit authority.
- **AP-TM-014:** All fixture values remain synthetic, Finance Assistant remains unchanged, and
  Terraform formatting, validation, or mocked plans can supply neither Live nor Adoption evidence.

The AP-M7 gate runs only explicit plan-mode tests with mocked providers in a disposable copy. It
performs no backend initialization, credential lookup, provider or metadata request, DNS lookup,
repository mutation, apply, or destroy. A static pass cannot qualify key custody, ingress, IAM,
logging, budget delivery, rollback, recovery, or any other provider behavior.

## Historical AP-M8 protected-source and federated-identity controls — superseded

This and the following three AP-M8 sections record the accepted but unexecuted manifest-driven
control proposal at revision `7b6678a7f0b3036d427517dad6bc3bec876d1a44`. ADR-010 through ADR-013
and the AP-M9 controls below supersede it. The historical sections authorize no implementation,
identity, credential, state, provider, DNS, or evidence action.

AP-M8-W1 defines the controls below for AP-M8-W3 and AP-M8-W4. They refine the existing threats
without claiming implementation:

- **AP-TM-004 and AP-TM-005:** GitHub workload identity is only an operator credential. It never
  becomes Visitor identity, a Platform Session, an assertion subject, an Application Principal, or
  a restricted member. The repository actor, workflow subject, service-account email, and provider
  token remain absent from runtime identity contracts and application requests.
- **AP-TM-007:** Protected `main`, required credential-free checks, a fixed rendered workflow,
  protected-environment approval, exact run SHA, reviewed plan digest, non-cancelling root
  concurrency, and the backend lock form independent gates. A plan approval grants no apply or
  recovery authority, and no partial failure automatically advances to another operation.
- **AP-TM-008 and AP-TM-009:** Every enabled root or publication operation has a distinct service
  account, rendered workflow, environment class, impersonation binding, backend scope where
  applicable, and provider scope. Plan, apply, artifact publish, generation publish, DNS, rollback,
  force-unlock, and destroy authority cannot cross a state owner or become another application's
  runtime, state, or IAM authority. Unused exceptional identities have no binding.
- **AP-TM-010:** GitHub environments contain no secret; workflows read no Actions secret and retain
  no OIDC token, generated credential, state, saved plan, raw provider response, browser state, or
  authenticated cache. Service-account keys are prohibited. Readback records only the reviewed
  non-secret setting, resource, role, binding, revision, outcome, and digest fields.
- **AP-TM-011:** Trust binds repository and owner names plus their immutable numeric identifiers,
  protected `refs/heads/main`, an allow-listed workflow ref, one reviewed environment and matching
  subject, `workflow_dispatch`, and the exact source SHA checked by the workflow. Full action pins,
  read-only defaults, non-persisted checkout credentials, CodeQL thresholds, secret scanning, push
  protection, and no repository-rule bypass remain mandatory. A renamed or recreated repository,
  alternate ref, pull-request run, tag, fork, unlisted workflow, or runtime-selected identity fails
  before credentials are usable.
- **AP-TM-012:** Operation identities omit owner, editor, IAM-administration, billing-administration,
  and cross-root permissions. One-hour-or-shorter federated credentials reduce exposure but do not
  prove provider quotas, runtime cost, or abuse controls.
- **AP-TM-013:** An unexpected repository bypass, environment secret, claim mismatch, wildcard,
  stored key, broad or inherited role, cross-root grant, provider mismatch, or partial identity
  change stops for inspection. There is no automatic policy broadening, retry, rollback, cleanup,
  or fallback to a local or stored credential.
- **AP-TM-014:** The pool, provider, environments, workflows, and identities bind only the canonical
  App Platform repository and non-production qualification project. They grant no Finance
  Assistant, production, real-application, Integration Draft, or Application Adoption authority.

The initial federation setup remains a separately approved short-lived owner operation because no
federated path exists yet. Its credential cannot enter Git or retained evidence, and the created
workload identities cannot administer federation, IAM, or themselves. This identity bootstrap is
separate from Terraform backend bootstrap.

The exact protected-setting, attribute-mapping, identity-matrix, readback, and stop profile is in
the subordinate [qualification-deployment runbook](runbooks/qualification_deployment.md). AP-M8-W1
is owner-accepted and merged; until the exact W2 manifest and the AP-M8-W3/AP-M8-W4 checkpoints are
separately approved and executed, these controls produce no provider or Live evidence.

## Historical AP-M8 backend-bootstrap and state-lineage controls — superseded

AP-M8-W1 defines these AP-M8-W5 controls without creating a backend or state:

- **AP-TM-007:** The bootstrap root uses one exact local plan and private state before a reviewed
  backend declaration is rendered from protected source. Migration targets a proven-empty
  `bootstrap` prefix and preserves lineage, non-decreasing serial, providers, resources, instances,
  and references. Empty non-bootstrap prefixes remain `not-created` until their first approved
  apply; no dummy state or invented lineage may satisfy the checkpoint.
- **AP-TM-008 and AP-TM-009:** Four buckets hold five root lineages. Bootstrap and platform share
  only a bucket and use distinct conditionally authorized prefixes; every fixture has its own
  bucket. Default-workspace-only operation, root-scoped IAM, typed non-secret references, and
  explicit owner/prefix mapping prohibit backend reads, writes, locks, or recovery actions across
  roots and applications.
- **AP-TM-010:** Local and remote state, lineage values, plans, backend payloads, credentials,
  provider responses, lock data, recovery copies, and generated backend files remain restricted
  operational material. Evidence retains only approved hashes, serials, redacted inventories,
  resource references, policies, labels, conditions, outcomes, and `not-created` statuses.
- **AP-TM-011:** The bootstrap backend declaration and renderer must be committed, digest-bound,
  deterministic, and passing before use. The operator uses exact Terraform/provider locks,
  protected source, operator-class configuration, one reviewed temporary copy, one saved plan, and
  an explicit migration action. An occupied bucket or prefix, alternate workspace, implicit input,
  mutable provider, manual backend file, or unreviewed reconfiguration fails closed.
- **AP-TM-012:** State buckets use uniform access, public-access prevention, versioning, deletion
  prevention, no force destroy, fixed regional standard storage, bounded noncurrent retention, and
  required labels. Those safeguards reduce accidental exposure and deletion but do not prove
  provider availability, disaster recovery, or spending behavior.
- **AP-TM-013:** Partial bucket creation retains the private local state and stops. Migration
  failure freezes local and remote copies. No failure automatically retries with force-copy,
  disables locking, unlocks, pushes state, imports, deletes, reconstructs state, broadens IAM,
  initializes another root, or advances deployment. Loss of the authoritative local state before
  migration acceptance is a recovery incident.
- **AP-TM-014:** Backend names, identities, prefixes, state, and evidence belong only to the
  non-production App Platform and synthetic Fixture Applications. No Finance, real-application,
  Integration Draft, or Adoption state can enter the bootstrap or be inferred from it.

The initial owner credential may create only the four reviewed buckets and their exact controls.
API enablement, billing mutation, project-wide storage roles, and non-backend resources require
other authority. Recovery-input readback verifies protected copies are locatable and intact but
does not restore one or qualify AP-M9 recovery.

The complete procedure, fixed mapping, migration invariants, partial-failure boundary, and allowed
record are in the [qualification-deployment runbook](runbooks/qualification_deployment.md). Until
the required AP-M8-W5 repository preparation is merged and the later operator checkpoint is
explicitly approved, these controls supply no backend, state, provider, deployment, or Live
evidence.

## Historical AP-M8 deployment-sequencing and activation controls — superseded

AP-M8-W1 defines these AP-M8-W6 through AP-M8-W10 controls without creating a workflow, image,
generation, resource, record, or DNS entry:

- **AP-TM-001 through AP-TM-003:** The initial provider-backed Registration Set contains only the
  three synthetic qualification applications and exact `gcp-cloud-run-v1` references produced by
  their independent roots. The complete set compiles before create-only publication, and the
  candidate binds its exact source, generation, content digest, object generation, edge image, and
  attachment references. The AP-M4 `fixture-in-process-v1` generations cannot be relabeled as
  deployed input.
- **AP-TM-004 through AP-TM-006:** A production Shared Edge composition entry point may assemble
  only the accepted identity, assertion, verification, resolution, and proxy adapters. The
  networked Fixture runtime independently verifies the production application assertion and keeps
  each application's synthetic authorization and state boundary. Repository support and provider
  deployment still supply no runtime identity or origin-isolation evidence; AP-M9 must exercise it.
- **AP-TM-007:** A Version 2 `foundation`/`candidate` contract breaks the first-deployment cycle
  without placeholder image, generation, or attachment values and preserves one Platform State
  lineage. Source, base image, package, configuration, object-generation, plan, and run digests are
  added through immutable predecessor-linked operation records. The candidate plan must preserve
  foundation resources and bind all exact dependencies before apply.
- **AP-TM-008 and AP-TM-009:** Platform foundation, each Fixture root, immutable artifact
  publication, immutable generation publication, platform candidate, and DNS are sequential
  operation boundaries. Typed references cross roots as reviewed data; no operation reads another
  backend. Artifact, generation, and DNS identities have no Terraform backend authority and can
  mutate only their exact repository, object, or A record.
- **AP-TM-010:** Images contain no credential or secret. Builds use exact source, pinned base
  images, frozen dependencies, non-root runtime users, and no retained build credential. Generated
  credentials, plans, state, provider responses, compiled object payloads, tokens, sessions,
  assertions, restricted members, and DNS-provider payloads remain outside Git and retained
  evidence; only approved digests, references, inventories, and coarse results enter the record.
- **AP-TM-011:** W6 implements fixed protected-main manual workflows with full action pins,
  non-persisted checkout credentials, exact identity/environment/target constants, and no Actions
  secret. Create-only artifact and object publication reject overwrite or mutable deployment tags.
  The candidate is built and planned from the exact accepted source rather than an unreviewed
  working tree or provider-discovered default.
- **AP-TM-012:** Foundation creates only the approved controls and bounded Artifact Registry;
  image publication cannot delete or administer it. The candidate retains AP-M7 zero-minimum and
  maximum-instance limits. DNS changes only the one new qualification A record. These constraints
  do not prove observed load, availability, cost, provider cleanup, or cache behavior.
- **AP-TM-013:** The first failure stops all dependent stages. A successfully created immutable
  image, object, root, or state remains for readback and never triggers automatic cleanup, retry,
  retag, overwrite, rollback, force-unlock, state push, import, destroy, IAM broadening, alternate
  artifact, or console repair. Candidate failure blocks DNS; DNS or certificate failure blocks
  AP-M9 and requires a new approval even to reverse only the new record.
- **AP-TM-014:** Images, Registration Sets, roots, identities, objects, state, hostname, and records
  remain confined to the App Platform qualification project and synthetic Fixture Applications.
  No Finance, production, real-application, Integration Draft, or Adoption input can enter the
  sequence.

The initial candidate has no predecessor and may receive 100 percent of its Cloud Run service's
traffic pointer before the hostname exists. This is a dark initial candidate, not zero-percent
traffic, successor-generation activation, or Live proof. The separately approved A record and
managed-certificate readiness make it reachable but leave it deployed and not Live-qualified.
ADR-008 pointer-change authority and all runtime claims remain AP-M9 or later work.

The exact W6 dependency closure, W7 preflight, W8/W9 operation order, W10 DNS/TLS checkpoint, and
partial-failure table are in the subordinate
[qualification-deployment runbook](runbooks/qualification_deployment.md). Until W6 is merged and
each later checkpoint is separately approved, this profile supplies no executable or provider
authority.

## Historical AP-M8 deployment-evidence controls — superseded

AP-M8-W1 defines these AP-M8-W11/W12 and AP-EVAL-M8 controls without reading a provider or
creating evidence:

- **AP-TM-001 through AP-TM-006:** Evidence binds the complete provider-backed Registration Set,
  configuration object, candidate, images, attachment references, and provider resource metadata
  but makes no catalogue, routing, identity, assertion, direct-origin, or authorization behavior
  claim. Those claims remain explicitly unavailable until AP-M9 exercises them.
- **AP-TM-007:** One exact source and append-only manifest chain bind every operation, plan,
  artifact, root, readback, approval reference, and verdict. Unique identifiers, predecessor hashes,
  sorted checksums, create-only records, and a no-overwrite final verdict expose omission,
  substitution, replay, or reordering. An expired or earlier bundle cannot qualify a later source.
- **AP-TM-008 and AP-TM-009:** Each root has its own readback identity and reducer; no reducer reads
  another backend. Artifact, generation, and DNS records remain target-scoped. The finalizer can
  read only one bundle prefix and has no state/provider access. Expected, state, provider, IAM, and
  owner inventories must agree exactly and cannot hide cross-owner drift behind an aggregate hash.
- **AP-TM-010:** A closed schema, field allow-list, prohibited-data scan, ephemeral mode-`0700`
  reduction, private owner-only bucket, 30-day retention, no external sink, and minimal optional Git
  index exclude raw state, plans, locks, credentials, tokens, provider responses, logs, screenshots,
  visitor/application data, identity claims, signed URLs, and recovery copies. A scan or evidence-
  write failure fails closed.
- **AP-TM-011:** Fixed protected-main readback/finalization workflows, exact environment and
  identity bindings, full action pins, source/manifest comparison, immutable schema/tool versions,
  deterministic synthetic verifier tests, and no runtime-selected target constrain evidence
  fabrication. The final verifier performs no provider query and rejects unknown files or fields.
- **AP-TM-012:** Evidence records selected scaling, retention, labels, approved services, artifact-
  retention policy, and budget thresholds only as configuration/readback. It cannot turn them into
  availability, hard-spend, cleanup, or notification-delivery proof.
- **AP-TM-013:** A failed operation still produces a redacted failed record when safe. Dependent
  gates are `blocked` with the causal record; a reachable unrun gate is a mandatory skip and fails.
  Missing, malformed, expired, prohibited, hash-mismatched, or incomplete evidence is never waived,
  reconstructed, or called a limitation. Recovery and rollback stay unexecuted.
- **AP-TM-014:** The bundle names only the canonical repository, non-production qualification
  project/hostname, and three synthetic fixtures. Finance, production, real applications,
  Integration Drafts, cross-project behavior, and Adoption remain unavailable and unchanged.

The proposed historical bundle was append-only under one private
`ap-eval-m8/<source-revision>/<evaluation-id>/` prefix. Per-operation create-only permissions do not
permit listing or reading another record. Root readback identities cannot write state or provider
resources. The finalizer may read that exact prefix and create only `manifest.v1.json`,
`checksums.sha256`, and `verdict.v1.json` with no-overwrite preconditions; it cannot read a backend
or repair a discrepancy.

AP-EVAL-M8 passes only with ten mandatory passes and zero failures, blocked gates, unexpected
warnings, prohibited findings, or mandatory skips. Its only positive status claim is deployed and
not Live-qualified. The exact schema, verifier, gates, and allowed fields are in
[the historical evaluation definition](05_evaluation_strategy.md); its collection and failure
handling were recorded in the superseded qualification-deployment runbook.

## AP-M9 interactive lifecycle controls

AP-M9 carries forward AP-TM-001 through AP-TM-014 and adds the following control refinements:

- **AP-TM-001 through AP-TM-003:** Environment Profiles and platform/application bundles are closed,
  bounded, non-secret contracts. Discovery cannot add a route, attachment, resource type, provider
  command, or owner outside the approved Deployment Specification. Registration still compiles one
  complete generation before activation.
- **AP-TM-004 through AP-TM-006:** The platform-owned OAuth secret remains readable only by the
  Shared Edge. Integration bundles expose platform login/assertion values rather than shared
  signing or OAuth authority. Application targets retain direct-origin denial, independent assertion
  verification, principals, data isolation, and Feature Entitlements.
- **AP-TM-007:** One canonical specification, exact-source check, stage-output graph, append-only
  Execution Journal, exact plan digest, state lock, provider readback, and resume cursor reject stale,
  concurrent, reordered, repeated, or partial lifecycle changes. A journal cannot authorize a
  mutation absent from its parent specification.
- **AP-TM-008 and AP-TM-009:** Environment, Platform State, Fixture Application State, and real
  Application State remain distinct. Bundles are reference exchange, not backend access. Detach,
  retire, application destruction, platform destruction, and environment destruction cannot cross
  an owner.
- **AP-TM-010:** Terminal prompts never accept a secret payload. OAuth secrets enter Secret Manager
  directly. Profiles, specifications, journals, bundles, status, logs, and evidence exclude
  credentials, secret values, state, plans, raw provider responses, browser state, identity claims,
  restricted membership, and application data.
- **AP-TM-011:** The lifecycle binds clean reviewed source, pinned tools and dependencies, one
  environment, an approved specification digest, an operation-specific impersonated identity, an
  exact plan, and readback. A profile or journal edit, alternate source, wrong project, provider
  default, console mutation, or unexpected drift stops before continuation.
- **AP-TM-012:** Preparation inventories every billable resource and destruction names every target.
  Existing limits, budgets, retention, scale-to-zero, and approved-service controls remain. A
  budget event never authorizes automated destruction.
- **AP-TM-013:** Manual OAuth and DNS checkpoints display exact values, wait in the same process,
  verify readable provider state, distinguish operator attestation from verification, bound polling,
  record unreadable fields as operator-attested, and stop without insecure fallback. Interruption
  resumes from closed readback rather than assuming the manual step succeeded.
- **AP-TM-014:** Staging fixtures remain synthetic. Production preparation fails closed on existing
  Finance ownership, and a generated bundle remains an inactive input until the application adopts
  it under its own authority.

The local operator workstation and its short-lived human session are privileged but fallible. The
lifecycle therefore uses least-privilege service-account impersonation after bootstrap, mode-`0700`
ephemeral working storage, source and environment checks, exact typed confirmations, prohibited-data
scans, and post-stage readback. A compromised workstation remains residual risk; no script can make
an owner credential incapable of out-of-band provider action. Such action is drift and never becomes
reviewed authority without reconciliation.

AP-M9-W1 defines controls and evaluation authority, AP-M9-W2 removed the retired manifest attack
surface, AP-M9-W3 implemented the closed lifecycle contracts, AP-M9-W4 implements local
source/tool discovery, exact digest approval, append-only journal revisions, truthful status,
redaction, and interruption-safe fake execution through injected adapters, and AP-M9-W5 implements
exact backend, operation-authority, phase, output, and plan-policy declarations through mocked
providers and command fakes. No current result proves an identity, backend, provider, OAuth, DNS,
deployment, or Live control operational.

## Unresolved security decisions

The following decisions must be approved by their owning later slice before the named evidence can
pass:

| Decision | Required before |
| --- | --- |
| Exact staging profile, profile schema, Deployment Specification, journal, and bundle contracts | AP-M9-W3 acceptance |
| Interactive discovery, prompt, digest, resume, and fake-adapter behavior | AP-M9-W4 acceptance |
| Exact OAuth branding constraints, client reference, redirect registration, and Secret Manager target | AP-M9 staging preparation before OAuth console action |
| Exact managed zone, absent record, allocated address, TTL, and external-DNS acknowledgement | AP-M9 staging deployment before DNS mutation |
| Provider ingress, IAM, identity, session, signing, logging, evidence, budget, and retention realization | AP-M9 staging deployment and qualification |
| Integration- and attachment-bundle schemas, application target posture, registration activation, detachment, and retirement | AP-M9-W7 acceptance before fixture deployment |
| Qualification fixtures, evidence schema, failure injection, rollback, and safe destroy behavior | AP-M9-W8 acceptance before staging deployment |
| Existing `apps.comfforts.com` resource/state ownership and Finance script changes | Production preparation and separate Finance Application Adoption |
| Production profile values, OAuth client, DNS transaction, cutover, rollback, and destructive authority | Separately approved production cutover after ownership transfer |
| Application-specific principals, data isolation, providers, and entitlements | Each Application Adoption |

An unresolved decision causes its dependent gate to remain unavailable; it is not an accepted risk
by silence.

## Threat-model acceptance boundary

This document is accepted when every in-scope trust crossing has an owner, every threat has required
controls and an evidence class, deferred decisions are explicit, and no deterministic claim is used
as runtime or adoption evidence. Acceptance of the document does not implement any control.

The implementation plan and evaluation strategy for this delivery item must reference these threat
identifiers. Versioned schemas and deterministic validation must cover every `C` requirement. Later
fixture, infrastructure, and adoption plans must carry forward the applicable `F`, `L`, and `A`
requirements without weakening them.

## Threat trace

| Threats | Requirements | Decisions |
| --- | --- | --- |
| AP-TM-001 through AP-TM-003 | AP-PR-001, AP-PR-002, AP-PR-003; AP-QR-002, AP-QR-003, AP-QR-004 | ADR-001, ADR-002, ADR-005 |
| AP-TM-004 through AP-TM-006 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002 | ADR-003, ADR-004, ADR-005, ADR-006 |
| AP-TM-007 through AP-TM-009 | AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-001, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-005, ADR-007, ADR-008 |
| AP-TM-010 through AP-TM-013 | AP-PR-001, AP-PR-003, AP-PR-005, AP-PR-007; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-003, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009 |
| AP-TM-014 | AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-006 | ADR-004 |
