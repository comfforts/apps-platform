# App Platform evaluation strategy

Version 0.17 | Status: AP-M9-W9 fixture lifecycle and live-adapter repository controls implemented; historical AP-EVAL-M8
and standalone AP-EVAL-M9 proposals superseded without execution; no AP-M9 provider or Live result
exists

This document preserves AP-EVAL-M3 through AP-EVAL-M7 and the historical unexecuted AP-EVAL-M8 and
standalone AP-EVAL-M9 proposals. The active AP-EVAL-M9 definition at the end of this document owns
the operator-driven lifecycle implementation and staging qualification gate. AP-EVAL-M7 continues
to qualify only committed configuration and inert templates through deterministic static tests with
mocked providers. AP-M9-W3 supplies lifecycle Contract evidence, W4 supplies deterministic
repository evidence for preparation, approval, status, redaction, atomic progress, and fake resume, and
W5 supplies deterministic backend, authority, plan-policy, phase-output, mocked-plan, and command-
fake evidence. W6 supplies exact-plan/action binding, typed confirmation, same-process manual
checkpoint, bounded-poll, transcript-redaction, stop-on-discrepancy, and resume evidence. W7
supplies deterministic least-data output, attachment/target validation, immutable generation,
activation, detach/reactivate, retirement, route-response, interruption, and conflict evidence.
W8 supplies deterministic exact-revision qualification, evidence redaction, network-fixture,
failure-injection, rollback, destruction-scope, confirmation, interruption, and resume evidence.
W9 supplies deterministic source-bound fixture deployment, independent state, handoff, registration,
browser qualification, exact destruction-transition, retained-resource, status, and redeployment evidence.
No result qualifies a provider operation, Live environment, consuming application's adoption, or
product authorization.

Plan: [App Platform implementation plan](04_implementation_plan.md)

Design: [App Platform system design](03_system_design.md)

Threats: [App Platform threat model](06_threat_model.md)

## AP-EVAL-M3 · System-design-and-contracts gate

### Evaluation claim

A passing AP-EVAL-M3 result means only that the repository revision contains internally consistent
App Platform design authority, Version 1 machine contracts, and deterministic offline validation
that meet AP-M3's acceptance criteria.

It does not mean the platform is deployed or runtime-qualified. It provides Contract (`C`) evidence
only. Fixture (`F`), Live (`L`), and Adoption (`A`) evidence remain unavailable.

### Evaluation environment

The gate runs from the dedicated App Platform repository root:

```bash
make check
```

The command remains project-relative, so history-preserving extraction does not change its
behavior. It must:

- require only a supported Python 3 interpreter and the Python standard library;
- perform no package installation or network access;
- require no cloud account, provider, browser, identity, credential, or secret;
- mutate no external state and create no committed artifact;
- use only project-relative paths; and
- return nonzero on any failed or skipped mandatory gate.

Ordinary ignored interpreter caches are not evidence and must not be required for success.

## Gate structure

### AP-EVAL-M3-01 · Authority and trace integrity

Verify that:

- the authority reading order includes requirements, accepted ADRs, system design, implementation
  plan, evaluation strategy, threat model, and repository layout in precedence order;
- all `AP-PR-*`, `AP-QR-*`, `ADR-*`, `AP-M3-*`, `AP-EVAL-M3-*`, and `AP-TM-*` identifiers are unique
  within their authority and every referenced identifier exists;
- public terms use the canonical glossary definitions;
- external application migrations remain outside the platform authority chain; and
- status text distinguishes documented, implemented, deployed, and qualified behavior.

Expected evidence: deterministic governance tests over committed Markdown and machine-contract
paths. Documentation presence alone cannot pass any behavioral gate.

### AP-EVAL-M3-02 · Schema integrity and compatibility

Verify all five Version 1 schemas:

- parse as duplicate-key-free JSON;
- declare JSON Schema Draft 2020-12 and a unique stable URN identifier;
- resolve every reference locally inside `contracts/`;
- require an explicit contract version and reject an unsupported major version;
- bound every string, array, and object whose size can be attacker-controlled;
- close objects against unknown properties unless a documented extension point exists;
- contain no remote reference, credential, provider command, Terraform state address, Finance path,
  containing-repository path, or secret-like payload; and
- follow the compatibility rules in `contracts/README.md`.

The schema documents and the reference validator are evaluated against the same test-vector
manifest. A case accepted by one and rejected by the other fails the gate.

### AP-EVAL-M3-03 · Deterministic successful compilation

For every valid vector, verify that the compiler:

- accepts the declared predecessor, Registration Set, and platform configuration;
- returns no violations;
- produces the expected complete Compiled Shared Edge Configuration;
- produces the expected State Ownership Manifest;
- orders applications, catalogue entries, routes, mounts, admission members, and ownership entries
  canonically;
- produces byte-identical canonical output and digest on repeated execution; and
- does not depend on input object order, current time, random values, absolute paths, environment
  identity, network state, or containing-repository files.

Valid vectors must include public, authenticated, and restricted registrations; listed and
unlisted catalogue behavior; multiple applications; multiple attachment mounts; active,
suspended, and retired states; a content-only application update; a stable attachment reference across an application
release; and an approved attachment replacement generation.

### AP-EVAL-M3-04 · Fail-closed route, catalogue, and attachment validation

Invalid vectors must cover at least:

- duplicate or near-matching application prefixes;
- root, `/_platform`, and `/.well-known` conflicts;
- uppercase, trailing slash, empty segment, dot segment, percent encoding, encoded separator,
  query, fragment, control character, and Unicode-lookalike paths;
- duplicate or ambiguous attachment mounts;
- unsupported forwarding modes or adapter kinds;
- arbitrary URLs, credentials, secret-like values, state addresses, or wrong-owner references;
- unsafe, oversized, marked-up, or private catalogue fields; and
- unknown registration or attachment properties.

Each case must return its declared ordered violation codes, produce no compiled output, perform no
external lookup, and leave its input files unchanged.

This gate supplies Contract evidence for AP-TM-001, AP-TM-002, AP-TM-003, and the applicable
configuration portion of AP-TM-012. It does not prove runtime route parsing, rendering, ingress, or
provider behavior.

### AP-EVAL-M3-05 · Admission and identity contract separation

Verify that:

- the only Admission Modes are `public`, `authenticated`, and `restricted`;
- restricted membership uses exact issuer-and-subject values and never email;
- owner-only is represented as restricted membership rather than a separate mode;
- authenticated and restricted registrations require compatible identity and audience data;
- public registrations do not require or invent an identity;
- the identity schema requires contract version, issuer, subject, audience, issued time, expiry,
  and correlation identifier within approved bounds;
- wrong-type, missing, unknown, mutable-owner, Feature Entitlement, product-role, and provider-right
  fields are rejected; and
- compiled output keeps admission separate from application authorization.

This is shape and semantic evidence only. Signature verification, header stripping, expiry,
wrong-audience rejection, replay handling, and direct-origin denial require Fixture and Live gates.

### AP-EVAL-M3-06 · Lifecycle, update, rollback-input, and ownership validation

Verify that:

- a new application is present only after one complete active candidate generation is atomically
  activated;
- only the transitions authorized by the system design are accepted;
- retired registrations are immutable tombstones and retain their identifiers and prefixes;
- a stale or missing predecessor digest is rejected;
- catalogue, route, admission, attachment, and ownership outputs are generated as one unit;
- an application release behind an unchanged attachment requires no registration difference;
- a platform-facing attachment change requires a new Registration Generation;
- valid attachment replacement retains distinct old and new application-owned references for the
  future acceptance and rollback sequence;
- each canonical resource reference has exactly one declared owner; and
- suspension, retirement, and rollback inputs never contain an instruction to destroy Application
  State.

This gate supplies the Contract portions of AP-TM-007 and AP-TM-008. It cannot prove provider
transactions, state readback, rollback execution, or destructive-action protection.

### AP-EVAL-M3-07 · Security, privacy, and isolation declarations

Verify that contracts and vectors contain:

- synthetic identities and application identifiers only;
- no credential, signing key, OAuth secret, unredacted assertion, real restricted membership,
  provider payload, application data, Terraform state, saved plan, or authenticated artifact;
- application-scoped audiences and ownership identifiers;
- no path by which an application receives Platform State write authority;
- no platform field for Application Principals or Feature Entitlements; and
- explicit unavailable states where later provider or runtime evidence is required.

Secret-pattern checks are defense in depth and do not certify that an arbitrary value is safe. A
positive match fails the committed-artifact gate; a negative match does not replace review.

### AP-EVAL-M3-08 · Extraction and non-mutation

Verify that:

- the contract loader and validator resolve from the App Platform project root;
- tests copy the contract layer to a temporary directory and exercise validation without importing
  Finance Assistant or another containing-repository path;
- `Makefile` contains no cloud, DNS, Terraform apply, provider CLI, credential, browser, or live
  mutation command in the default check dependency chain;
- validation does not modify contract inputs or tracked files; and
- ignored caches and temporary directories are not treated as evidence.

The temporary-copy test validates the contract layer's extraction boundary. Full repository
extraction, root workflow recreation, and repository settings remain later operator work.

### AP-EVAL-M3-09 · Scope and truthful handoff

Verify that the AP-M3 change:

- adds no `fixtures/` implementation, `infrastructure/terraform/` content, cloud resource, DNS
  record, identity configuration, credential, or runtime;
- leaves Finance Assistant requirements, code, infrastructure, state, deployment, and access model
  unchanged;
- keeps application-specific migration outside App Platform authority;
- records AP-M3 as contract implementation only after the complete gate passes; and
- directs the next task to propose delivery item 4 planning after AP-M3 merges, without treating the
  current branch or pull request as that merge.

## Test-vector manifest

`contracts/test-vectors/manifest.v1.json` is the reviewed index of deterministic cases. Each entry
must declare:

- stable case identifier and description;
- input schema and relative input paths;
- predecessor path when applicable;
- expected acceptance or rejection;
- expected compiled and ownership paths for acceptance;
- expected ordered violation codes and paths for rejection;
- requirements, decisions, and threat identifiers covered; and
- an explicit evidence class of `C`.

The manifest contains no executable command, absolute path, environment-specific identifier, or
expected live result. A vector not indexed by the manifest is test support, not acceptance evidence.

## Determinism and mutation checks

Tests must isolate nondeterminism by:

- injecting no clock, random generator, network client, provider client, or credential source;
- comparing canonical bytes and digests across repeated execution;
- permuting non-semantic JSON object order where the contract permits it;
- running with a minimal environment and a temporary working directory for extraction checks;
- hashing or byte-comparing input vectors before and after validation; and
- treating an unexpected file creation, external call, warning-only rejection, or skipped mandatory
  case as failure.

The AP-M3 reference compiler may read caller-supplied contract files but exposes no file-writing
interface. It returns in-memory values, and tests do not write generated artifacts into the
repository.

## Threat coverage boundary

| Threats | AP-EVAL-M3 claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Contract shape, semantic rejection, safe projection, and inert attachment references |
| AP-TM-004 | Declaration of protected-ingress and identity requirements only; bypass remains unqualified |
| AP-TM-005 | Identity claim shape, issuer-subject membership, and audience binding only; cryptography remains unqualified |
| AP-TM-006 | Platform contracts exclude Feature Entitlements and product roles |
| AP-TM-007 | Generation, transition, atomic-output, and rollback-input validation |
| AP-TM-008 | Declared exclusive ownership and cross-state reference validation only |
| AP-TM-009 | Unique routes, attachments, audiences, and owners in compiled configuration |
| AP-TM-010 | Prohibited committed fields, synthetic vectors, and secret-pattern defense in depth |
| AP-TM-011 | Deterministic revision-bound inputs and extraction-safe default checks only |
| AP-TM-012 | Contract and compiler size bounds only; runtime abuse and cost remain unqualified |
| AP-TM-013 | Fail-closed declarations only; dependency failure remains unqualified |
| AP-TM-014 | Authority labels and absence of fixture or adoption behavior |

## Pass, fail, and skip semantics

AP-EVAL-M3 passes only when:

- every mandatory gate passes in one revision-scoped run;
- expected test counts and vector counts match the manifest;
- there are zero failures, errors, unexpected warnings, and skips;
- the working tree contains no unexpected generated or sensitive artifact; and
- manual review confirms the declared scope and unresolved decisions.

Any mandatory failure, error, skip, schema/validator disagreement, nondeterministic output, external
dependency, unreviewed generated file, secret-like payload, missing trace, or false runtime claim
fails AP-EVAL-M3. A known limitation is recorded as unavailable; it is not converted into a skip or
passing assertion.

## Required evaluation evidence

The AP-M3 pull-request handoff records:

- evaluated commit and contract versions;
- exact command and working directory;
- interpreter version;
- test and vector counts;
- pass, failure, error, warning, and skip counts;
- duration when reported by the test runner;
- changed and evaluated artifact paths;
- Contract threat coverage and all unavailable `F`, `L`, and `A` evidence;
- security/privacy impact and unresolved decisions; and
- confirmation that no credential or external mutation was used.

Evidence reports actual output. It must not pre-fill a success result, omit a failed command, or
claim runtime qualification from documentation, schemas, or static configuration.

## Limitations

AP-EVAL-M3 does not perform load, browser, accessibility, cryptographic, network, cloud, DNS, TLS,
IAM, OAuth, Terraform, provider, runtime, direct-origin, or application-product testing. It does not
qualify availability, cost controls, logging, incident response, migration, or rollback execution.

Those gates require separately approved plans after AP-M3 merges. Finance Application Adoption
requires Finance-owned authority and evidence in addition to qualified platform behavior.

## AP-EVAL-M4 · Deterministic-fixtures gate

### Evaluation claim

A passing AP-EVAL-M4 result means only that the evaluated repository revision implements the
in-process Deterministic Reference Edge and three synthetic Fixture Applications according to
AP-M4. It provides Fixture (`F`) evidence for the behaviors explicitly named below.

It does not mean the platform is deployed, network reachable, persistent, production-secure, or
ready for a real application. Live (`L`) and Adoption (`A`) evidence remain unavailable. AP-EVAL-M3
continues to own Contract (`C`) evidence, and its implemented contract regression checks must pass
in the same `make check` run. AP-M3's historical no-fixture scope gate is not reinterpreted as a ban
on the separately authorized AP-M4 implementation.

### Evaluation environment

AP-EVAL-M4 runs from the dedicated App Platform repository root using the same project-local entry
point:

```bash
make check
```

`make check` must include `fixture-check` after governance and contract checks. The complete command
uses only a supported Python 3 interpreter and its standard library. It performs no installation,
network access, socket bind, browser automation, credential read, environment secret read, cloud
access, external mutation, or committed artifact generation. The harness itself launches no
subprocess; the extraction check may launch an isolated standard-library Python interpreter from a
temporary project copy, as AP-EVAL-M3 already requires.

The harness opens no listening socket. There is no registration API or database; tests supply
reviewed Registration Sets directly to the in-memory activation interface.

Tests use an injected clock, deterministic correlation-identifier source, explicit synthetic
session map, public test key material, immutable requests, and separately constructed in-memory
Platform and Fixture Application State. An unexpected external dependency fails the gate.

### AP-EVAL-M4-01 · Authority, trace, and scope integrity

Verify that:

- every `AP-M4-W*` and `AP-EVAL-M4-*` identifier is unique, complete, and traces to existing
  requirements, decisions, design sections, and threats;
- AP-M3 Contract evidence remains distinct and continues to pass;
- the documented fixture limits and identity profile match executable constants and tests;
- no external application migration or Finance artifact is loaded as fixture input; and
- status text distinguishes designed, implemented, Fixture-qualified, Live-qualified, and adopted.

Expected evidence: deterministic governance tests and the complete gate. Documentation presence
alone cannot pass a behavioral AP-EVAL-M4 gate.

### AP-EVAL-M4-02 · Registration, adapter binding, and atomic activation

Using independent fixture registration files, verify that:

- all three fixtures enter through a complete Version 1 Registration Set and the AP-M3 compiler;
- only the reviewed `fixture-in-process-v1` kind is enabled for the harness;
- every resource reference exactly matches its application and attachment identifier;
- the compiled attachment resolves only through the explicitly supplied read-only map;
- a wrong kind, malformed reference, absent target, owner mismatch, or stale predecessor rejects
  activation before the current-generation pointer changes; and
- successful activation installs catalogue, routes, admission, attachments, and ownership as one
  generation.

This gate proves the Fixture portions of AP-TM-003, AP-TM-007, AP-TM-008, AP-TM-009, and AP-TM-011.
It does not prove a provider resource, IAM identity, state backend, or deployment transaction.

### AP-EVAL-M4-03 · Catalogue, route, mount, and forwarding behavior

Verify through `handle(request) -> response` that:

- `/` returns deterministic UTF-8 HTML with only active, listed fixtures in canonical order;
- catalogue titles and summaries are literal escaped text and every link is the registered prefix;
- exact prefixes and segment-bounded subpaths route to only their registered fixture;
- longest segment-bounded mount selection and all three Version 1 forwarding modes behave as
  compiled;
- near-prefixes, reserved paths, malformed paths, encoded separators, dot segments, suspended,
  retired, and unmatched paths return closed responses; and
- an unavailable attachment fails only the selected fixture and never falls through to another.

This gate supplies Fixture evidence for AP-TM-001, AP-TM-002, AP-TM-003, AP-TM-009, and AP-TM-013.
It does not qualify provider path decoding, browser behavior, network routing, or availability.

### AP-EVAL-M4-04 · Admission, header stripping, and assertion delivery

Verify that:

- public admission succeeds without identity and does not invent an Application Principal;
- authenticated admission rejects a missing or unknown synthetic session;
- restricted admission requires the exact registered synthetic issuer-and-subject pair;
- a visitor-supplied `X-Comfforts-Verified-Identity` value is removed before attachment invocation;
- a protected attachment receives only a newly issued assertion for its own audience after
  successful admission; and
- authentication and restricted-denial responses reveal no member list, assertion, attachment
  reference, principal, entitlement, or application state.

This gate supplies the edge-side Fixture portions of AP-TM-004, AP-TM-005, AP-TM-006, AP-TM-009,
and AP-TM-010. It does not qualify OAuth, a production identity provider, key management, or network
origin isolation.

### AP-EVAL-M4-05 · Independent application verification and authorization

Call protected fixture entry points directly and verify rejection of:

- a missing, malformed, unsigned, wrong-key, or visitor-controlled assertion;
- a wrong contract version, issuer, subject shape, or application audience;
- an assertion issued in the future, expired, or longer than 60 seconds;
- a cross-application assertion; and
- a replayed correlation identifier or a new assertion when the 256-entry store has no expired
  capacity.

Then verify that a valid assertion derives an immutable application-scoped principal, while the
restricted fixture independently denies the synthetic premium Feature Entitlement to an admitted
principal who lacks it. Application-side verification must not consult platform membership or
another fixture's state.

This gate supplies assertion and authorization-separation Fixture evidence for AP-TM-004 through
AP-TM-006, AP-TM-009, and AP-TM-010. It cannot prove key secrecy, distributed replay defense,
provider rights, or a real application's authorization.

### AP-EVAL-M4-06 · State and cross-application isolation

Verify that:

- each fixture is constructed with a distinct state object, principal map, entitlement policy,
  verifier, and replay store;
- a request, failure, identity, or state mutation in one fixture does not alter another fixture;
- the reference edge holds only compiled references and the read-only adapter map, not application
  data or write authority;
- no fixture can change the current generation or another attachment mapping; and
- generation activation, suspension, retirement, and rollback never mutate or delete fixture state.

This gate supplies Fixture evidence for AP-TM-006, AP-TM-008, AP-TM-009, and AP-TM-014. In-process
object isolation is not provider IAM or process-isolation evidence.

### AP-EVAL-M4-07 · Release, update, lifecycle, failure, and rollback journeys

Verify in sequence that:

- the initial reviewed generation activates all intended fixture behavior;
- an application release behind an unchanged attachment needs no Registration change;
- a platform-facing update requires and activates a new complete generation;
- suspension removes route and catalogue behavior without changing Fixture Application State;
- reactivation restores the reviewed behavior; retirement is terminal and remains closed;
- attachment replacement keeps distinct old and new targets available for rollback;
- validation failure, missing attachment resolution, or simulated selected-attachment failure does
  not partially activate or affect another fixture; and
- rollback selects a retained reviewed generation as a whole without rolling back application state.

This gate supplies the in-memory Fixture portions of AP-TM-007, AP-TM-008, AP-TM-009, and AP-TM-013.
It does not qualify persistence, concurrent writers, a provider transaction, or an operator runbook.

### AP-EVAL-M4-08 · Limits, redaction, determinism, extraction, and non-mutation

At each exact boundary and one unit beyond it, verify the 16-byte method, 1,024-byte path,
1,024-byte query, 32-header, 64-byte header-name, 1,024-byte header-value, 8,192-byte aggregate
header, empty-body, 65,536-byte response, 60-second assertion, and 256-entry replay limits.

Also verify that:

- repeated runs from identical constructed state return byte-identical responses and outcomes;
- diagnostics contain only approved fixture identifiers, generation digests, outcome codes, and
  correlation identifiers;
- diagnostics and failures omit assertion envelopes, sessions, restricted members, request bodies,
  principals, entitlements, and application state;
- tests run from a temporary copy of the project-local fixture and contract layers without a
  containing-repository import; and
- tracked inputs remain byte-identical and no unexpected file, cache treated as evidence, network
  call, socket, credential read, or external mutation occurs.

This gate supplies the bounded Fixture portions of AP-TM-001, AP-TM-005, AP-TM-010 through
AP-TM-013. It is not load, concurrency, timeout, rate, cost, or availability evidence.

### AP-EVAL-M4-09 · Truthful evidence and handoff

Verify that the AP-M4 change:

- records Fixture evidence only after AP-EVAL-M3 and AP-EVAL-M4 pass at the same revision;
- reports the exact command, counts, failures, errors, warnings, and skips actually observed;
- calls synthetic signing, direct entry-point denial, in-memory activation, and object isolation by
  those names rather than production cryptography, direct-origin denial, persistence, or IAM;
- leaves every Live and Adoption gate explicitly unavailable;
- leaves Finance Assistant and infrastructure, Terraform, DNS, identity, credentials, deployment,
  and access unchanged; and
- directs the next task to separate infrastructure planning rather than implementation or
  Application Adoption.

### Determinism and mutation checks

AP-M4 tests must recreate all mutable harness state for every case. They may advance only the
injected clock, correlation sequence, generation pointer, replay store, and the explicitly selected
fixture's synthetic state. Case order, wall clock, hash randomization, current user, absolute path,
environment, network state, or prior test execution must not affect results.

Tests compare requests, registration inputs, compiled generations, and non-selected state before
and after each journey. Any unrequested mutation, ambient dependency, warning-only rejection,
unbounded operation, or unexpected artifact fails the gate.

### Threat coverage boundary

| Threats | AP-EVAL-M4 claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Bounded HTML catalogue, route and attachment selection, and inert fixture resolution |
| AP-TM-004 | Header stripping and assertion-side direct-entry denial only; network origin remains unqualified |
| AP-TM-005 | Deterministic synthetic signature, issuer, audience, time, cross-application, and replay failure behavior |
| AP-TM-006 | Admission remains separate from fixture-owned principal and entitlement decisions |
| AP-TM-007 | Single-process complete-generation activation and rollback |
| AP-TM-008 | Independent in-memory Platform and Fixture Application State |
| AP-TM-009 | Route, attachment, audience, failure, lifecycle, and state isolation among fixtures |
| AP-TM-010 | Synthetic inputs and redacted deterministic diagnostics |
| AP-TM-011 | Reviewed repository inputs and deterministic default checks; no live control plane |
| AP-TM-012 | Exact in-process size and count limits; no traffic or cost claim |
| AP-TM-013 | Deterministic logical dependency failure without insecure fallback |
| AP-TM-014 | Generic fixtures only; no external application migration or Application Adoption behavior |

### Pass, fail, and skip semantics

AP-EVAL-M4 passes only when all nine gates and every implemented AP-M3 contract regression check
pass in one revision-scoped `make check` run, expected test and registration-generation counts
match their reviewed indexes, and there are zero failures, errors, unexpected warnings, and
mandatory skips.

A known Live or Adoption limitation is recorded as unavailable and is not a skip. Any mandatory
fixture case that cannot run fails the gate. No manual override, document review, screenshot,
provider result, or consuming-application test substitutes for a failing deterministic case.

### Required evaluation evidence

The AP-M4 pull-request handoff records:

- evaluated commit, AP-M3 merge base, contract and fixture registration versions, and generation
  digests;
- exact command and working directory, interpreter version, duration, and test counts;
- pass, failure, error, warning, and skip counts;
- enabled fixture adapter, changed and evaluated paths, and synthetic fixture identifiers;
- requirements, decisions, and threats covered by the Fixture gate;
- security/privacy impact and unavailable Live and Adoption evidence; and
- confirmation that no credential, network, socket, package installation, cloud account, browser,
  external mutation, or generated proof artifact was used.

Evidence reports actual output and evaluated revision. It must not pre-fill success, retain an
assertion envelope, record synthetic session labels as if they were secrets, or claim that
in-process behavior occurred on a network.

### Limitations

AP-EVAL-M4 performs no browser, accessibility, load, concurrency, rate, network, cloud, DNS, TLS,
IAM, OAuth, Terraform, provider, persistence, real direct-origin, production cryptographic, cost,
alerting, incident-response, migration, or application-product testing. It does not prove that a
real application can or should adopt the platform.

Infrastructure and Live qualification require a separate owner-approved slice after AP-M4 merges.
Every Application Adoption remains an application-owned later slice with its own evidence.

## AP-EVAL-M5 · Infrastructure-planning gate

### Evaluation claim

A passing AP-EVAL-M5 result means only that the evaluated repository revision contains complete,
internally consistent planning authority for the initial GCP qualification topology and for the
later AP-M6 through AP-M9 delivery sequence.

It proves no provider behavior and creates no new evidence class. AP-EVAL-M3 Contract (`C`) and
AP-EVAL-M4 Fixture (`F`) regression gates must continue to pass. Live (`L`) and Adoption (`A`)
evidence remain unavailable.

### Evaluation environment

AP-EVAL-M5 runs through the project-local entry point:

```bash
make check
```

The complete command must remain Python
standard-library-only, credential-free, deterministic, network-free, and non-mutating. It may read
committed source but may not run Terraform, a provider CLI, DNS lookup, socket, browser, OAuth flow,
authenticated workflow, or cloud plan. It must create no committed artifact and must return nonzero
for any failed or skipped mandatory AP-M5 gate.

### AP-EVAL-M5-01 · Authority, identifiers, and trace integrity

Verify that:

- ADR-001 through ADR-009 are unique, accepted, and trace to existing requirements;
- AP-M5-W1 through AP-M5-W9 are unique, ordered, and trace to AP-PR-001 through AP-PR-009,
  AP-QR-001 through AP-QR-006, and AP-TM-001 through AP-TM-014;
- the system design, threat model, implementation plan, evaluation strategy, repository layout, and
  future handoff agree on the planning-only status;
- AP-M3 Contract and AP-M4 Fixture authorities remain intact and continue to pass; and
- every claim distinguishes selected, implemented, deployed, Live-qualified, and adopted behavior.

Documentation presence is not enough: deterministic governance checks must inspect identifiers,
required decisions, scope exclusions, and later-slice boundaries.

### AP-EVAL-M5-02 · Provider topology and attachment boundary

Verify that the authority consistently selects:

- project `comfforts-platform-non-prod`, project number `455651441682`, region `us-west1`, and no
  production environment;
- `apps-staging.comfforts.com` without changing `apps.comfforts.com` or Finance Assistant;
- one global external Application Load Balancer, Google-managed certificate, HTTP-to-HTTPS
  behavior, one Cloud Run edge, and no application-prefix duplication in the provider URL map;
- `gcp-cloud-run-v1` with the exact typed, inert project-number/region/service-name reference;
- provider metadata, readiness, ownership, and edge-caller grant as activation prerequisites rather
  than arbitrary URL fetching;
- separate Platform and Fixture Application State even in one project; and
- platform-owned Shared VPC networking for later cross-project GCP attachment without transferring
  application runtime, IAM, data, or state ownership.

The gate rejects a provider command, credential, URL target, cross-state read, Finance path, or
claim that same-project design qualifies cross-project behavior.

### AP-EVAL-M5-03 · Identity, session, and assertion trust profile

Verify that the authority distinguishes Visitor identity, Platform Session, edge-caller workload
identity, Application Principal, and Feature Entitlement, and selects:

- Google OIDC authorization code with PKCE for consumer Google and Google Workspace accounts;
- no initial MFA requirement and no other OIDC provider;
- an opaque host-only secure cookie, minimal Firestore Native session state, and an eight-hour
  absolute reauthentication boundary without stored Google access or refresh tokens;
- optional verified identity on public routes, required identity on authenticated routes, exact
  issuer-subject restricted membership, and display-only email;
- platform-owned logout with a validated relative return path;
- one environment Cloud KMS software ES256 signer with application-specific audiences and public
  JWKS only;
- 60-second assertions, 30-second clock skew, 90-day rotation, 24-hour verification overlap, and
  15-minute application key caching; and
- no distributed replay-prevention claim.

The gate must preserve existing IAP and `@react-oauth/google` behavior as unchanged application
inputs until an independently approved Application Adoption.

### AP-EVAL-M5-04 · State, operator, and source-control authority

Verify that planning defines:

- independent bootstrap, platform, and per-fixture Terraform roots;
- a platform-state GCS bucket and separate state bucket per fixture, with locking, public-access
  prevention, versioning, and recovery history of at least 90 days and 20 newer generations;
- no `terraform_remote_state`, application-backend read, shared write authority, committed state,
  saved plan, or recovery copy;
- one-time short-lived bootstrap and migration of temporary state only after verified recovery;
- GitHub Actions OIDC and GCP Workload Identity Federation bound after repository extraction;
- advisory pull-request plans, an exact protected-main plan, explicit environment approval, source
  and plan digests, concurrency, and backend locking;
- separate plan, apply, rollback, import, recovery, and destroy authority; and
- no routine local apply, with a narrowly scoped, recorded, short-lived break-glass exception.

The same human may review and approve, but normal operation may not bypass protected source,
workload identity, exact plan, target scoping, readback, or drift reconciliation.

### AP-EVAL-M5-05 · Generation activation, DNS, readback, and rollback

Verify that:

- complete Registration Sets remain reviewed Git inputs with no registration endpoint or database;
- compilation and predecessor validation produce a digest before planning;
- immutable configuration objects and edge revisions bind source, compiler, generation, object,
  image, identity, adapter, and platform versions;
- the Cloud Run traffic assignment to one revision is the only current Live generation pointer;
- staging validates dependencies before owner-approved 100-percent traffic activation;
- source, plan, state, provider, runtime, catalogue, route, attachment, identity, direct-origin, and
  ownership readback must agree;
- provider partial failure stops for inspection and never triggers automatic rollback or cleanup;
- owner-confirmed whole-generation rollback has a 15-minute post-approval objective and never
  changes Application State;
- the preceding configuration, revision, and replaced target remain for at least 24 hours; and
- the separately approved new hostname action uses a 1,800-second TTL, `dig` readback, certificate
  readiness, and no existing hostname or Finance mutation.

The gate fails if DNS is treated as a registration update, TTL is described as a propagation
guarantee, or cleanup is automatic at the end of the retention window.

### AP-EVAL-M5-06 · Logging, evidence, privacy, and incident boundary

Verify that the selected seven-day Cloud Logging profile permits only revision and generation
digests, application and route identifiers, coarse outcomes, status class, latency, correlation
identifier, and non-secret versions.

It must prohibit assertions, sessions, restricted members, issuer-subject pairs, email, bodies,
queries, raw application paths, application data, provider payloads, secrets, Terraform state,
saved plans, stream chunks, intentionally retained IP addresses, and user-agent strings. Logs have
owner-only access and no external sink.

Verify that Live evidence is a 30-day, owner-readable, private GCS bundle containing redacted
revision-bound digests, commands, readback, results, failures, limitations, and evidence labels.
Screenshots, browser state, raw provider output, and unredacted logs are not authoritative evidence.
The App Platform Owner is the incident contact, and any suspension, rollback, key action, or cleanup
requires an explicit decision.

### AP-EVAL-M5-07 · Demo-scale resource and cost controls

Verify that planning records:

- a USD 20 monthly budget with owner notifications at 50, 80, and 100 percent;
- review at 50 percent, a new-billable-change pause at 80 percent, and an explicit owner decision at
  100 percent without automatic billing disablement or destruction;
- Shared Edge Cloud Run bounds of zero minimum, two maximum, 1 vCPU, 512 MiB, and concurrency 20;
- per-fixture bounds of zero minimum, one maximum, 1 vCPU, 512 MiB, and concurrency 10;
- at most 55 minutes per SSE or WebSocket connection;
- one non-production edge and load balancer with no CDN, WAF, HSM, production replica, always-on
  instance, Firestore backup, or PITR;
- only active and overlapping KMS verification versions and active, rollback, and candidate images;
- dry-run-first, owner-approved cleanup; and
- Terraform rejection of unapproved services, larger or unbounded runtimes, longer retention,
  additional environments or edges, and missing ownership labels.

The gate must state that budgets and maximum instances are safeguards, not guaranteed hard spending
caps. Future application projects retain their own runtime and billing ownership.

### AP-EVAL-M5-08 · Later-slice and unresolved-input separation

Verify that AP-M6 provider runtime, AP-M7 Terraform/workflows, AP-M8 deployment, AP-M9 Live
qualification, and Application Adoption remain separate owner-approved branches and merge gates.

The plan must name, rather than infer:

- the network framework and dependency policy;
- exact live header, body, non-streaming timeout, and abusive-traffic limits;
- dedicated repository, workflow subject, and protected-environment values;
- globally unique bucket names and DNS managed-zone resource;
- OAuth client and notification configuration; and
- initial live fixture identities, registrations, image digests, and resource references.

An unavailable later input blocks its dependent slice. It is not a skip, provider lookup, fixture
default, Finance-derived value, or reason to weaken the accepted boundary.

### AP-EVAL-M5-09 · Non-mutation and truthful handoff

Verify that the AP-M5 branch:

- creates none of the reserved `edge/`, `registrations/`, `infrastructure/terraform/`,
  `docs/runbooks/`, or Live `artifacts/` capabilities;
- contains no Terraform file, workflow with cloud authority, state, plan, credential, secret,
  provider command, DNS lookup, browser state, deployment, or generated Live evidence;
- leaves default verification free of network, credentials, cloud accounts, and mutation;
- leaves Finance Assistant and every real application unchanged and inactive;
- records only planning authority after all nine AP-EVAL-M5 gates pass; and
- directs the next task to AP-M6 proposal only after this pull request merges.

### Threat coverage boundary

| Threats | AP-EVAL-M5 planning claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Provider topology, inert Cloud Run reference, catalogue/routing authority, and future validation requirements are explicit |
| AP-TM-004 through AP-TM-006 | Direct-origin layers, Google OIDC, Platform Sessions, ES256 assertions, audiences, and application authorization separation are explicit |
| AP-TM-007 through AP-TM-009 | Immutable generation pointer, state roots, concurrency, rollback, IAM, and application-isolation plans are explicit |
| AP-TM-010 | Prohibited log/evidence data, access, retention, and no-export policy are explicit |
| AP-TM-011 | Protected-main, WIF, exact-plan, break-glass, drift, and extraction dependencies are explicit |
| AP-TM-012 | Scale, concurrency, streaming, retention, budget, and billable-resource controls are explicit; remaining input limits are named |
| AP-TM-013 | DNS/TLS, key, session, configuration, provider-failure, readback, and rollback plans are explicit |
| AP-TM-014 | Fixture, Live, and Adoption claims remain separate and Finance Assistant remains unchanged |

### Pass, fail, and skip semantics

AP-EVAL-M5 passes only when all nine gates, every AP-EVAL-M3 and AP-EVAL-M4 regression test, and
the complete `make check` command pass at one repository revision with zero failures, errors,
unexpected warnings, and mandatory skips.

A missing trace, contradictory decision, false operational claim, undeclared later input, reserved
implementation path, credential, network dependency, cloud command, external mutation, Finance
change, or runtime/Live/Adoption claim fails the gate. A later capability being unavailable is an
explicit limitation, not a skipped AP-M5 gate.

### Required evaluation evidence

The AP-M5 pull-request handoff records:

- branch, AP-M4 merge base, evaluated revision, and final revision;
- AP-M5 work-package commits and changed paths;
- exact command and working directory, interpreter version, duration, and test count;
- pass, failure, error, warning, and skip counts;
- requirements, ADRs, threats, and later evaluation boundaries covered;
- security/privacy impact, limitations, and unresolved implementation inputs; and
- confirmation that no credential, network, provider, Terraform, DNS, identity, repository-setting,
  deployment, or application mutation occurred.

Console output from the deterministic run is sufficient. AP-M5 evidence contains no cloud result
because no cloud action is authorized.

### Limitations

AP-EVAL-M5 performs no runtime, Terraform, workflow, repository-setting, browser, accessibility,
load, concurrency, network, DNS, TLS, IAM, OAuth, KMS, Firestore, provider, budget, logging,
deployment, rollback, recovery, incident, migration, or application-product test. It cannot qualify
any selected control as implemented or operational.

## AP-EVAL-M6 · Networked-provider-runtime gate

### Evaluation claim

A passing AP-EVAL-M6 result means only that the exact repository revision implements the networked
Shared Edge and production-provider adapter logic and passes deterministic tests through fake
adapters and process-local loopback. It supplies implementation evidence, not Live evidence.

It does not prove a real Google login, persistent Platform Session, managed signing key, Cloud Run
target, provider IAM grant, direct-origin denial, load balancer, DNS record, certificate, log sink,
availability, cost, deployment, or Application Adoption.

### Evaluation environment

The gate runs from the App Platform root in an already synchronized `uv.lock` environment on Python
3.12 or newer:

```bash
make check
```

Dependency synchronization is a separate setup action and is not part of the gate. The check
command performs no installation,
package-index request, DNS resolution, external network call, credential lookup, metadata-server
call, browser action, provider access, repository mutation, or external state change.

Unit and ASGI tests use in-memory adapters. Network integration tests may bind only an ephemeral
loopback address, must keep the listener inside the test process, and must fail if a connection is
attempted to any non-loopback address. Tests use fixed keys, clocks, nonces, identities, metadata,
generations, and application responses committed as non-secret fixtures.

### Gate structure

#### AP-EVAL-M6-01 · Authority, packaging, and extraction

Verify the approved ASGI interface, internal adapter seams, Python range, direct dependency
declarations, frozen transitive lock, package metadata, ignored environment artifacts, and
project-relative commands. A temporary history-independent copy must run the complete gate without
the parent application package or repository layout.

The dedicated-root workflow may synchronize the frozen environment, but no platform runtime code
or configuration may live outside this repository root.

#### AP-EVAL-M6-02 · Runtime limits and closed parsing

At each exact boundary and one unit beyond it, verify:

- 16-byte methods, 4,096-byte paths, 8,192-byte queries, 64 headers, 128-byte header names,
  8,192-byte header values, and 32,768 aggregate header bytes;
- 25-MiB request and buffered-response bodies, 100-MiB streamed connection totals, and 1-MiB
  WebSocket messages;
- 10-second upstream connection, 300-second non-streaming, 300-second streaming-idle, and
  55-minute absolute streaming timeouts;
- 20 active requests, 10 streams, and four per-client streams per instance; and
- per-client request, login, WebSocket-message, and instance-wide token-bucket rates and bursts.

Malformed methods, paths, queries, text, framing, transfer encoding, content length, duplicate
security-sensitive headers, hop-by-hop headers, limit overflow, saturation, and timeout fail before
or cancel target work with deterministic closed results and no prohibited diagnostic data.

#### AP-EVAL-M6-03 · Immutable generation, catalogue, and routing

Verify exact object and content digest binding, Version 1 validation, one-generation startup,
escaped catalogue output, catalogue visibility, reserved paths, canonical prefix and mount
rewriting, query preservation, and suspended/retired/unknown/malformed closure. Provider
storage failure, digest mismatch, partial configuration, stale generation, or runtime reload attempt
cannot produce a mixed or alternate route set.

#### AP-EVAL-M6-04 · OIDC, sessions, admission, and logout

Using deterministic OIDC and session adapters, verify PKCE, state and nonce binding, verified Google
issuer and subject, opaque host-only cookie attributes, eight-hour absolute expiry, no silent renewal,
no retained Google tokens, validated return locations, logout deletion, optional public identity,
authenticated admission, exact restricted membership, email display-only treatment, revocation at
the next request or new stream, and fail-closed provider or store errors.

#### AP-EVAL-M6-05 · Assertions, JWKS, and application verification

Verify visitor-header stripping, Version 1 claim minimization, ES256 signing, application-specific
audience, versioned key identifier, 60-second lifetime, 30-second skew, current and overlapping key
publication, 15-minute verifier caching, one refresh on an unknown key, and successful direct-entry
application verification. Missing, malformed, unsigned, expired, premature, wrong-version,
wrong-issuer, wrong-audience, unknown-key, stale-key, or cross-application assertions fail closed.

No test claims distributed replay prevention or treats the edge caller identity as Visitor identity.

#### AP-EVAL-M6-06 · Cloud Run reference and provider isolation

Verify strict `gcp-cloud-run-v1` parsing and exact project number, region, service, application owner,
readiness, edge-caller grant, and audience matching through fake provider metadata. Reject URLs,
credentials, Terraform addresses, unsupported adapters, arbitrary discovery, wrong scope, absent or
unready services, ownership mismatch, caller mismatch, cross-application reuse, and metadata failure.

Production adapters must be constructible without performing I/O and must accept their client or
transport dependency rather than creating it during import.

#### AP-EVAL-M6-07 · HTTP and streaming proxy behavior

Through ASGI and process-local loopback, verify request-path and query forwarding, allowed end-to-end
headers, hop-by-hop removal, assertion replacement, uploads, buffered and streaming downloads, SSE,
WebSocket handshake and bidirectional messages, backpressure, cancellation, visitor disconnect,
idle and absolute expiry, application status propagation where safe, and protocol-appropriate
failure mapping.

One slow, malformed, saturated, disconnected, or failing application cannot select, block, leak, or
mutate another application's target or state. No test makes an availability, throughput, or load
claim.

#### AP-EVAL-M6-08 · Status, outcomes, failure, and redaction

Verify operator authorization for status/readback, revision and generation facts, adapter health,
correlation identifiers, one completion event per request or stream, coarse outcome, status class,
and latency. Across successful and failed paths, assert absence of assertions, session identifiers,
cookies, authorization values, restricted members, issuer-subject pairs, email, visitor metadata,
request or response bodies, stream chunks, provider payloads, application data, credentials,
secrets, state, and plans.

Status and readback cannot activate, reload, roll back, mutate, discover, or expose runtime secrets.

#### AP-EVAL-M6-09 · Non-mutation and truthful evidence

Verify that default checks reject external addresses and provider transports, use no environment
credential, metadata server, browser, OAuth client, KMS key, Firestore database, GCS object, Cloud
Run service, Terraform, DNS, repository setting, or live registration, and create no authenticated
artifact. Finance Assistant and every real application remain unchanged and inactive.

The repository and status documents call AP-M6 locally implemented only after all gates pass and
retain deployed, Live, and Adoption claims as unavailable.

#### AP-EVAL-M6-10 · Complete regression and handoff

Run every AP-EVAL-M3, AP-EVAL-M4, AP-EVAL-M5, and AP-EVAL-M6 gate at one source revision with zero
failures, errors, unexpected warnings, or mandatory skips. Verify unique identifiers and complete
traceability for AP-M6-W1 through AP-M6-W11 and AP-EVAL-M6-01 through AP-EVAL-M6-10, then route the
next task to AP-M7 only after the pull request merges.

### Threat coverage boundary

| Threats | AP-EVAL-M6 implementation claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Generation, catalogue, route, attachment-reference, and provider-metadata inputs validate and fail closed |
| AP-TM-004 through AP-TM-006 | Direct-entry verification, sessions, admission, assertions, audiences, and feature-authorization separation pass locally |
| AP-TM-007 through AP-TM-009 | Immutable generation binding, failure isolation, ownership checks, and cross-application rejection pass locally; provider state does not |
| AP-TM-010 | Errors, status, logs, and evidence pass prohibited-data redaction tests |
| AP-TM-011 | Locked dependencies, digest binding, injected clients, extraction, and no implicit mutation pass repository tests |
| AP-TM-012 | Exact size, duration, concurrency, stream, and per-instance rate limits pass deterministic boundary tests without load claims |
| AP-TM-013 | Provider, key, session, storage, transport, disconnect, and timeout failures preserve closed behavior locally |
| AP-TM-014 | Fixtures remain synthetic, Finance remains unchanged, and no implementation result is called Adoption or Live evidence |

### Pass, fail, and skip semantics

AP-EVAL-M6 passes only when all ten gates and every prior regression gate pass at one revision. Any
external connection attempt, real credential use, provider call, missing production/fake adapter
pair, untested limit, prohibited diagnostic value, cross-application effect, dependency drift,
runtime mutation path, later-slice artifact, false operational claim, failure, error, unexpected
warning, or mandatory skip fails the gate.

An unavailable provider resource or Live control is a declared limitation, not a skipped AP-M6
test. Platform-specific conditional skips are prohibited.

### Required evaluation evidence

The pull-request handoff records the branch, AP-M5 merge base, evaluated and final revisions,
AP-M6 work-package commits and paths, `uv.lock` digest, Python version, exact commands and working
directory, duration, test totals, failures, errors, warnings, and skips, identifier and threat
coverage, security/privacy impact, limitations, and unresolved later inputs. It confirms loopback-
only networking, fake-provider use, no external mutation, and unchanged Finance behavior.

Console output is sufficient and no generated report is committed.

### Limitations

AP-EVAL-M6 performs no authenticated provider, browser, Terraform, repository-setting, DNS, TLS,
IAM, deployment, load, availability, cost, direct-origin network, multi-instance, rollback,
recovery, incident, migration, or application-product test. Its production adapters are locally
tested implementations, not evidence that their required provider resources or permissions exist.

## AP-EVAL-M7 · Terraform-and-workflow gate

### Evaluation claim

A passing AP-EVAL-M7 result means only that the exact repository revision implements the approved
Terraform roots, internal modules, typed configuration contracts, and inert workflow templates and
passes deterministic static verification with mocked providers. It supplies repository
implementation evidence, not provider, deployment, or Live evidence.

It does not prove a backend, state lineage, provider credential, Workload Identity Federation
binding, IAM grant, Google identity, Cloud Run service, load balancer, certificate, DNS record,
budget notification, log retention, direct-origin denial, recovery operation, or Application
Adoption.

### Evaluation environment

The gate runs from the dedicated repository root after an explicit dependency-only setup action:

```bash
make terraform-setup
make check
```

`make terraform-setup` installs only Terraform 1.17.2 and the locked `hashicorp/google` 8.11.0
provider into ignored local tool and filesystem-mirror paths after checksum verification. It does
not initialize a root or backend, read a credential, run a plan, or contact GCP. The setup network
access is not part of AP-EVAL-M7 and its exact artifacts and checksums are recorded.

`make check` remains the sole evaluation command. Terraform evaluation copies configuration into a
temporary directory, uses `TF_CLI_CONFIG_FILE` to permit only the pre-populated filesystem mirror,
disables update checks, unsets credential variables, and runs with no external network. It may run
`terraform fmt -check -recursive`, `terraform init -backend=false -lockfile=readonly`,
`terraform validate`, and `terraform test` only with explicit `command = plan` and mocked providers.
No command writes the repository or a backend, creates state outside the disposable directory, or
uses a provider API.

### Gate structure

#### AP-EVAL-M7-01 · Authority, toolchain, locks, and extraction

Verify AP-M7-W1 through AP-M7-W11 authority, Terraform 1.17.2, `hashicorp/google` 8.11.0, exact root
constraints, committed `linux_amd64` and `darwin_arm64` provider checksums, ignored setup paths, and
project-relative commands. Reject prerelease, floating, unlocked, extra, or unapproved providers.

A temporary history-independent copy must run the complete gate without the source repository,
Finance Assistant, user Terraform configuration, global plugin cache, credential, or network.

#### AP-EVAL-M7-02 · Root and module ownership

Verify exactly one bootstrap root, one platform root, and roots for `fixture-public`,
`fixture-authenticated`, and `fixture-restricted`. Every managed resource has one root and one
declared owner. Bootstrap owns backend resources only; the platform root owns only Platform State;
each fixture root owns only that fixture's Application State.

Reusable modules declare no backend, environment, provider credentials, operator values, state
owner, cross-root data source, or hidden root resource. Tests exercise root interfaces rather than
depending on internal module structure.

#### AP-EVAL-M7-03 · Configuration and reference contracts

Validate Version 1 backend, platform, fixture, cross-state-reference, and workflow schemas and every
synthetic example. Require closed properties, exact owner classes, canonical resource references,
immutable image digests, bounded values, required labels, Secret Manager version references, and
explicit destructive targets. Terraform variable types and validations must agree with the schemas.

Reject missing, extra, malformed, placeholder-as-live, secret-bearing, state-bearing, ambiguous,
cross-owner, or unbounded inputs. Reject `terraform_remote_state`, backend-object reads, application
credentials, discovered references, and output values containing secret, state, or plan material.

#### AP-EVAL-M7-04 · Backend bootstrap and recovery controls

Using explicit plan-only mocked-provider tests, verify one platform-state bucket and one bucket for
each Fixture Application, uniform bucket-level access, public-access prevention, object versioning,
at least 90 days and 20 newer noncurrent versions before expiration, ownership labels, and explicit
root-scoped access intent. Outputs expose only typed non-secret bucket references.

Reject a backend initialization, local state file, weak retention, public access, cross-root object
access, implicit bucket name, destroy-on-budget behavior, or backend mutation command.

#### AP-EVAL-M7-05 · Fixture Application isolation

For all three fixture roots, verify one Cloud Run runtime and identity, the declared Application
State owner, edge-only caller intent, protected direct ingress, exact audience and platform
references, zero minimum, one maximum 1-vCPU/512-MiB instance, concurrency 10, required labels, and
one canonical `gcp-cloud-run-v1` attachment output.

Reject public unauthenticated origin intent, platform-owned fixture resources, shared fixture state,
cross-fixture IAM, load balancer or DNS ownership, application feature grants, mutable image tags,
or management of another root's resource.

#### AP-EVAL-M7-06 · Platform identity and immutable generation

Verify configuration-object immutability and digest inputs, Firestore Native session settings,
eight-hour application expiry intent without backup or PITR, software-protected regional ES256 KMS
key intent, active/overlap version constraints, Secret Manager references without values, edge and
caller identity separation, and minimal typed platform outputs.

Reject an embedded OAuth secret, signing material, restricted member set, mutable generation name,
unreviewed compilation path, credential output, application-owned identity resource, or activation
side effect.

#### AP-EVAL-M7-07 · Shared Edge and hostname forwarding

Verify one `us-west1` Cloud Run edge, immutable image and generation binding, zero minimum and two
maximum 1-vCPU/512-MiB instances, concurrency 20, approved timeouts, restricted ingress, dedicated
runtime and caller identities, one global address, one Google-managed certificate intent, HTTP-to-
HTTPS redirect, one serverless backend, and one hostname-level URL map with no application prefix.

Reject a DNS record, CDN, WAF, public direct edge origin, arbitrary target URL, application runtime
ownership, extra environment, additional load balancer, mutable image tag, unbounded scaling, or
fragmented registration-derived provider routing.

#### AP-EVAL-M7-08 · Observability, evidence, retention, labels, and cost

Verify a dedicated seven-day log bucket and exclusions, 30-day evidence bucket intent, owner-only
access intent, USD 20 budget with 50/80/100-percent notifications, dry-run-first artifact cleanup,
active/rollback/candidate retention, required `environment`, `managed_by`, `state_owner`, and
applicable `application_id` labels, approved services, and every selected scaling and retention cap.

Reject identity, visitor, payload, state, plan, secret, or provider response in configured logs or
evidence; automatic billing disablement, automatic destroy, unapproved billable service, longer
retention, always-on instance, backup, PITR, HSM, production replica, missing label, or implicit
notification destination.

#### AP-EVAL-M7-09 · Workflow authority and non-mutation

Parse every inert template and verify separate plan, apply, rollback, force-unlock, and destroy
authorities; full-length action pins; read-only default permissions; explicit `id-token: write` only
for future federated jobs; protected-main and environment placeholders; per-root concurrency; exact
commit checkout; fresh exact-main plan; source and plan digest recording; same-job plan and apply;
explicit root and destructive targets; stop-on-partial-failure; and secret-free outcome metadata.

Reject placement under `.github/workflows/`, a real federation or service-account value, stored key,
secret read, pull-request apply, reused pull-request plan, uploaded saved plan, unpinned action,
implicit apply, automatic unlock, rollback, DNS change, or destroy. The existing executable check
workflow retains read-only permissions and no OIDC authority.

#### AP-EVAL-M7-10 · Complete regression, truthful status, and handoff

Run every AP-EVAL-M3 through AP-EVAL-M7 gate at one source revision with zero failures, errors,
unexpected warnings, mandatory skips, external connections, credential lookups, or repository
changes. Verify unique identifiers and complete traceability for AP-M7-W1 through AP-M7-W11 and
AP-EVAL-M7-01 through AP-EVAL-M7-10.

Status may call AP-M7 implemented only after all gates pass. Backend initialization, provider
operation, repository settings, federation, deployment, Live, and Adoption remain unavailable, and
the next task routes to AP-M8 only after merge.

### Threat coverage boundary

| Threats | AP-EVAL-M7 implementation claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | Configuration, generation, routing, and attachment inputs have closed typed contracts and static policy |
| AP-TM-004 through AP-TM-006 | Ingress, identity, audience, and entitlement separation are represented in mocked plans without an operational claim |
| AP-TM-007 through AP-TM-009 | Immutable binding, root ownership, typed references, concurrency, and cross-application isolation pass statically |
| AP-TM-010 | Contracts, outputs, templates, tests, and scans exclude prohibited secret, identity, state, plan, and payload data |
| AP-TM-011 | Exact locks, action pins, source/plan binding, offline extraction, inert workflows, and no implicit mutation pass |
| AP-TM-012 | Scaling, retention, approved-service, label, and budget policies pass without an availability or cost claim |
| AP-TM-013 | Failure templates stop for inspection and retain explicit recovery authority without testing provider recovery |
| AP-TM-014 | Fixtures remain synthetic, Finance remains unchanged, and no static result is called Live or Adoption evidence |

### Pass, fail, and skip semantics

AP-EVAL-M7 passes only when all ten gates and every prior regression gate pass at one revision. Any
floating dependency, lock mismatch, registry or provider access, real credential or operator value,
backend operation, apply-mode test, root overlap, cross-state read, executable mutation workflow,
state, saved plan, prohibited data, external connection, repository change, false operational claim,
failure, error, unexpected warning, or mandatory skip fails the gate.

An unavailable provider resource, operator input, or Live control is a declared limitation, not a
skipped test. Platform-specific conditional skips are prohibited.

### Required evaluation evidence

The pull-request handoff records branch and AP-M6/governance merge base, evaluated and final
revisions, AP-M7 work-package commits and paths, Terraform and provider versions, lock and tool
digests, exact setup and gate commands, working directory, duration, test totals, failures, errors,
warnings, and skips, identifier and threat coverage, configuration examples, security/privacy
impact, limitations, and unresolved AP-M8 inputs. It confirms mocked-provider and offline-mirror use,
no external mutation, and unchanged Finance behavior.

Console output is sufficient and no generated report is committed.

### Limitations

AP-EVAL-M7 performs no backend, state-lineage, authenticated provider, browser, repository-setting,
federation, DNS, TLS, IAM, deployment, load, availability, cost-delivery, direct-origin network,
multi-instance, rollback, recovery, incident, migration, or application-product test. Static
configuration and mocked plans are implementation evidence only and cannot satisfy AP-EVAL-M8 or
AP-EVAL-M9.

## Historical unexecuted evaluation proposals

The following two sections preserve the accepted but unexecuted AP-M8 deployment/readback proposal
and the withdrawn standalone Live-qualification proposal as they stood at source revision
`7b6678a7f0b3036d427517dad6bc3bec876d1a44`. They are not active gates, authorize no external
operation, and produced no result. The active AP-EVAL-M9 definition follows them.

### Historical AP-EVAL-M8 · Manifest-driven qualification-deployment gate — superseded

#### Evaluation claim

A passing AP-EVAL-M8 result proves only that the exact protected-main revision was deployed into
project `comfforts-platform-non-prod` (`455651441682`) in `us-west1` through the approved operation
sequence; its five Terraform state lineages and provider inventories agree with their declared
owners; its immutable images and Registration Generation are bound to the initial Shared Edge
candidate; its new `apps-staging.comfforts.com` A record and managed certificate read back as
approved; and no unapproved resource or authority changed.

AP-EVAL-M8 is deployment/readback evidence, not a fifth evidence class and not Live (`L`) evidence.
A deployment result cannot qualify routing, identity, direct-origin denial, rollback, cost behavior,
or application adoption.
It does not invoke an application route or status endpoint and does not qualify catalogue or proxy
behavior, Visitor identity, admission, sessions, assertions, direct-origin denial, failure
isolation, rollback execution or time, recovery, availability, load, cost delivery, incident
response, cross-project attachment, Finance Assistant, or Application Adoption.

#### Evaluation environment and command boundary

The gate begins only after the complete AP-M8-W1 authority is accepted and merged, the exact
AP-M8-W2 real manifest and digest are accepted, and the exact
protected-main source revision has passed:

```bash
make terraform-setup
make check
```

Those commands remain credential-free and provide only AP-EVAL-M3 through AP-EVAL-M7 regression
evidence. Every authenticated AP-EVAL-M8 step runs through its fixed protected-main
`workflow_dispatch` file, reviewed environment, and operation identity. There is no routine local
apply, provider-console substitution, pull-request apply, reusable unlisted workflow, or command
that selects a root, identity, environment, repository, ref, or operation at runtime.

AP-M8-W6 must implement one credential-free final verifier with this interface:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m infrastructure.deployment.verify_evidence \
  --bundle <private-read-only-bundle-directory> \
  --manifest-digest sha256:<64-lowercase-hex> \
  --source-revision <40-lowercase-hex> \
  --verdict-output <new-ephemeral-verdict-file>
```

The evidence-finalization workflow copies only the exact private bundle prefix into an ephemeral
mode-`0700` runner directory, renders the final manifest and sorted record checksums from the exact
approved operator-manifest chain, and runs the verifier with an absent output path. After a pass or
fail verdict is produced, it create-only publishes the manifest, checksum file, and verdict, reads
back their digests, and removes the local copy and generated credential. The CLI rejects an extra
file, missing operation, hash mismatch, duplicate identifier, unknown schema field, unexpected
status, prohibited datum, source/manifest mismatch, pre-existing verdict output, or incomplete gate.
It performs no provider query or mutation. The complete `make check` gate tests it against
synthetic pass and failure bundles without a credential, network, or real operator value.

Provider and state readback occur before finalization through one fixed readback workflow per root
and fixed target-specific artifact, generation, and DNS workflows. Each command consumes exact
reviewed configuration, writes raw state/plan/provider output only to runner-temporary restricted
storage, reduces it to the approved schema, scans the result for prohibited data, and create-only
publishes its redacted operation record. A raw response, state, plan, lock payload, generated
credential, environment dump, or shell transcript never enters the evidence bundle.

#### Evidence bundle and schema

The authoritative bundle is private in the AP-M7 evidence bucket under exactly one
`ap-eval-m8/<source-revision>/<evaluation-id>/` prefix. Uniform access, public-access prevention,
owner-only read, no external sink, and the 30-day retention policy apply. The bundle is append-only
while operations run and contains only:

```text
manifest.v1.json
operations/<sequence>-<operation-id>.v1.json
readback/<target-id>.v1.json
verdict.v1.json
checksums.sha256
```

`manifest.v1.json` records the schema/evaluation identifiers; repository and exact source;
project, number, region, and hostname; operator-manifest predecessor chain and digests; contract,
compiler, Terraform, provider, and workflow versions; environment/workflow/operation-identity
resource references; immutable image, Registration Generation, configuration-object, and plan
digests; expected sequence and target inventory; bundle prefix; creation/expiry timestamps; and
the prohibited-data policy version.

Each operation record contains a unique operation and workflow-run identifier, fixed target,
environment class, source and manifest digests, approval-event reference and timestamp, start/end
timestamps, input and output digests, expected and observed coarse change summaries, redacted
readback hash, predecessor-record hash, outcome, failure category, limitations, and the next-stage
decision. It contains no approval comment or retained human identity beyond the provider's
non-secret immutable event reference.

Each readback record contains only the target's declared owner; resource types and canonical
non-secret resource references; project/region; required labels and protection states; sorted state-
address and provider-resource inventory digests; state-lineage digest and serial; backend prefix;
IAM role and workload-principal resource references; artifact/configuration/DNS/TLS metadata where
applicable; expected/observed comparison outcomes; and prohibited-data scan result. It never
contains state attributes, lineage values, secret values, identity claims, visitor/application
data, assertions, sessions, restricted members, raw logs, payloads, IP addresses, or user agents.

`verdict.v1.json` records all ten gate outcomes, totals for pass/fail/blocked/skip, the first
failure and causal chain, complete operation/readback/checksum inventories, security and privacy
limitations, unavailable AP-M9 and Adoption claims, the digest of `checksums.sha256`, finalizer
workflow/run reference, and exact finalizer command outcome. `checksums.sha256` covers the manifest,
operation records, and readback records in sorted path order; it covers neither itself nor the
later verdict. After verdict readback, the final workflow computes the bundle digest from the
canonical tuple of checksum-file digest and verdict-object digest, avoiding a self-referential
hash.

Git may later retain only an owner-approved secret-free index containing the evidence identifier,
source revision, evaluation outcome, bundle digest, expiry timestamp, and historical-status label.
The bundle, object contents, GCS access URL, signed URL, credentials, and raw outputs remain outside
Git. Expiry or deletion of evidence never converts an unavailable or failed gate into a pass.

#### Gate structure

##### Historical AP-EVAL-M8-01 · Authority, source, and regression integrity

Verify the accepted AP-M8 authority revision precedes every operator action; repository identity,
protected default branch, exact clean deployed source, complete required checks, CodeQL and secret
controls, full action pins, tool/provider locks, operator-manifest chain, expected sequence, and
private evidence destination. AP-EVAL-M3 through AP-EVAL-M7 must pass at the deployed source.

##### Historical AP-EVAL-M8-02 · Protected environments, federation, and operation identities

Read back the Plan, Apply, DNS, Evidence, and Recovery environment protections and absence of
secrets; Workload Identity Pool/provider issuer, audience, mappings, conditions, and state; exact
repository/owner numeric bindings; protected ref, workflow, event, environment, and source claims;
service-account key absence; and every operation's direct/inherited roles and resource scopes.
Reject a bypass, wildcard, alternate workflow/ref/event, broad primitive role, cross-root scope,
unused exceptional binding, or Finance/production/real-application principal.

##### Historical AP-EVAL-M8-03 · Backends, lineages, locks, and recovery inputs

Verify four private versioned state buckets and five fixed prefixes; conditional root access;
default-workspace-only operation; bootstrap migration lineage and serial invariants; one lineage for
each applied non-bootstrap root; native-lock behavior; recovery-version availability; retention,
public-access prevention, deletion protection, labels, and no cross-root read. Record hashes and
inventories only and execute no restore, force-unlock, push, import, or destroy.

##### Historical AP-EVAL-M8-04 · Source-bound artifacts and publication

Verify the Shared Edge and Fixture runtime images were built from the exact source, pinned base
images, frozen dependencies, reviewed non-root definitions, and create-only publication. Registry
readback must agree on immutable digests and package ownership with no mutable deployment tag,
unapproved package, overwrite, deletion, external registry, retained build credential, or cleanup
execution.

##### Historical AP-EVAL-M8-05 · Platform foundation and controls

Reconcile the Platform foundation same-job plan, state, and provider inventories for configuration
storage, Artifact Registry, edge runtime/caller identities, KMS/Firestore, log/evidence controls,
budget/notification configuration, labels, approved services, and typed platform reference. Prove
the foundation phase created no Shared Edge, load balancer, certificate, DNS record, generation
object, or Fixture resource.

##### Historical AP-EVAL-M8-06 · Fixture roots and attachment ownership

For public, authenticated, then restricted fixtures, reconcile the fresh same-job plan, independent
state lineage, provider inventory, application owner, runtime identity, immutable image, ingress,
edge-caller IAM intent, limits, labels, and canonical `gcp-cloud-run-v1` attachment reference.
Reject shared state, cross-fixture IAM, Platform ownership of Application State, public direct-
origin intent, or a root applied after an earlier fixture failure. Do not invoke the runtimes.

##### Historical AP-EVAL-M8-07 · Registration Generation and dark candidate binding

Verify the provider-backed initial Registration Set and no-predecessor declaration, deterministic
compiler output, create-only configuration object and object generation, content/generation
digests, three actual attachment references, edge image, source, contract versions, candidate
revision, state/provider ownership, load-balancer/address/certificate intent, and 100-percent
Cloud Run pointer to the only revision. Confirm foundation resources are unchanged and the DNS
record was absent throughout candidate apply. This proves a dark initial candidate only, not
runtime activation behavior or a successor-generation pointer change.

##### Historical AP-EVAL-M8-08 · Qualification DNS and TLS readiness

Verify the separately approved transaction created only the `apps-staging.comfforts.com` A record
with TTL 1,800 and the candidate's exact reserved IPv4 address. Authoritative provider readback and
independent recursive answers must agree, and the Google-managed certificate must report active for
that hostname. Reject an AAAA, wildcard, existing/production/Finance record change, alternate
address, zone mutation, timeout, or omitted cached-answer limitation. Make no HTTP application
request.

##### Historical AP-EVAL-M8-09 · Complete ownership and no-unapproved-change reconciliation

Compare the approved expected inventory with sorted Terraform state-address, provider-resource,
IAM, image, generation, DNS/TLS, label, protection, and enabled-service inventories for every owner.
Every item must have one owner and every expected item must exist exactly once. Reject drift,
replacement, destroy, extra/missing resource, unknown API/service, provider default, cross-owner
management, unrecorded retry, cleanup, or discrepancy hidden by hashing.

##### Historical AP-EVAL-M8-10 · Evidence privacy, truthful verdict, and handoff

Verify the append-only operation chain, all required record/checksum/schema fields, 30-day private
retention, owner-only access, prohibited-data scans, actual command outcomes, failures, limitations,
blocked stages, and zero mandatory skips. The final verdict calls the environment only deployed and
not Live-qualified, leaves every AP-M9 and Adoption claim unavailable, and confirms Finance
Assistant and existing hostnames/resources were unchanged.

#### Threat coverage boundary

| Threats | AP-EVAL-M8 deployment/readback claim |
| --- | --- |
| AP-TM-001 through AP-TM-003 | The exact reviewed complete Registration Set, immutable object, candidate, and three attachment references agree without a runtime-routing claim |
| AP-TM-004 through AP-TM-006 | Provider identity/secret references and ownership read back as configured; Visitor, session, assertion, entitlement, and direct-origin behavior remain AP-M9 |
| AP-TM-007 through AP-TM-009 | Source/plan/generation binding, ordered operations, root lineages, typed references, locks, state/provider ownership, and cross-root denial agree |
| AP-TM-010 | Private retention, schema minimization, hashing, prohibited-data scans, no external export, and no raw operational material pass |
| AP-TM-011 | Protected source, pins, manifests, workflow subjects, immutable publication, operation chain, and exact finalizer pass |
| AP-TM-012 | Selected limits, labels, retention, approved-service inventory, and budget configuration read back without an availability or hard-spend claim |
| AP-TM-013 | Partial failure, blocked-stage, no-automatic-follow-on, and discrepancy reporting are complete; rollback/recovery remain unexecuted |
| AP-TM-014 | Only synthetic qualification fixtures exist; Finance, production, real applications, external migrations, and Adoption remain unchanged |

#### Pass, fail, and skip semantics

All ten AP-EVAL-M8 gates are mandatory. `pass` requires complete exact readback for that gate.
`fail` records any mismatch, command error, timeout, prohibited data, unexpected warning, missing
record, hash/schema error, unapproved change, or false claim. After the first failure, a dependent
gate that cannot safely run is `blocked` with the causal gate and operation record; it is not
silently omitted or called a skip.

The mandatory skip count must be zero. An operator choice not to run a reachable mandatory gate is
a failure. AP-M9, cross-project, Finance, and Adoption behaviors are recorded as `unavailable`
limitations outside AP-EVAL-M8's mandatory-gate counts, not skips. A failed or partial deployment
retains a failed evidence bundle and never receives a passing index. No manual attestation,
screenshot, console view, document review, prior run, waived discrepancy, or expired record can
substitute for a mandatory result.

AP-EVAL-M8 passes only when all ten gates pass for one exact source/manifest chain, all required
operations and readbacks have unique identifiers and valid hashes, every expected inventory agrees,
there are zero failures, blocked gates, errors, unexpected warnings, prohibited findings, and
mandatory skips, and the final create-only verdict reads back with the expected digest.

#### Required evaluation evidence

The private bundle records the schema-approved source, authority, manifest, configuration,
workflow, environment, identity, plan, image, generation, object, state-lineage, provider, IAM,
resource, DNS/TLS, approval-event, command, timing, ownership, retention, security/privacy,
limitation, outcome, and checksum fields described above. Every attempted operation is present,
including failures and reversals. The final result reports actual pass/fail/blocked/skip counts and
the first causal failure.

Raw Terraform state or plans, provider/API responses, credentials, OIDC/access tokens, generated
credential files, environment dumps, browser state, screenshots, logs, assertions, sessions,
restricted members, identity claims, email addresses, IP addresses, user agents, request/response
data, application data, signed URLs, and recovery copies are prohibited. The W6 schema and verifier
must fail a bundle that contains them or an unrecognized field.

#### Limitations

AP-EVAL-M8 does not exercise runtime HTTP, catalogue, routes, mounts, forwarding, admission, OAuth,
session, logout, assertion, JWKS, application verification, direct-origin denial, failure injection,
streaming, limits, scaling, availability, load, cost delivery, incident response, drift injection,
rollback, restoration, cleanup, or Application Adoption. Provider readback is evidence that the
selected configuration exists, not proof of its runtime behavior. Those claims remain AP-M9 or a
later application-owned gate.

This section is accepted AP-M8-W1 authority, not a passing result. AP-M8-W2's local schema and
validator create no workflow, identity, credential, bucket object, provider action, resource, DNS
record, certificate, evidence bundle, or passing result.

### Historical standalone Live-qualification gate — withdrawn before implementation

AP-EVAL-M9 supplies Live (`L`) evidence only for the exact non-production project, hostname,
revision, Registration Generation, and fixture resources named by the approved gate. It uses
owner-approved non-production Google test identities without retaining their identifiers or browser
state as evidence. The default `make check` remains separate and credential-free.

#### Historical gate 01 · Revision, environment, and evidence integrity

Verify protected-main source and plan digests, compiler and contract versions, image digests,
Registration Generation and predecessor, Terraform lineages, project number, region, hostname,
workflow identity, approval, timestamps, and redacted evidence destinations. Any mismatch or
unapproved resource fails before behavioral claims proceed.

#### Historical gate 02 · DNS, TLS, catalogue, and route behavior

Read back authoritative and recursive DNS, certificate status, HTTPS, HTTP redirection, security
headers, one load-balancer backend, one edge traffic target, catalogue projection, registered exact
and subpaths, mounts, forwarding, and closed unknown, malformed, reserved, suspended, and retired
paths. Confirm application prefixes are not duplicated in the provider URL map.

#### Historical gate 03 · Attachment ownership and direct-origin denial

Read back each typed Cloud Run target, readiness, project, region, Application State owner, edge
caller grant, ingress, and absence of arbitrary URL resolution. Prove a protected target rejects an
unauthenticated direct request and a caller lacking the edge identity, while the reviewed edge path
reaches only the intended application. Same-project evidence does not qualify cross-project
attachment.

#### Historical gate 04 · OIDC, session, admission, and logout

Exercise anonymous public access, optional identity on public access, authenticated admission,
restricted allow and deny, invalid/expired session failure, eight-hour boundary configuration,
cookie attributes, safe redirect state, logout from root and application paths, and display-only
email. Prove authentication grants no Fixture Application Feature Entitlement.

#### Historical gate 05 · Assertion, KMS, JWKS, and application verification

Read back the software ES256 key location and active version, public JWKS, key identifier, one
environment signer, and application-specific audiences. Exercise valid, missing, visitor-supplied,
malformed, expired, future, wrong-issuer, wrong-audience, cross-application, and unknown-key
assertions; 60-second lifetime; 30-second skew; key refresh; overlap; and fail-closed stale-key
behavior. Record that distributed replay prevention remains unavailable rather than implying it.

#### Historical gate 06 · Activation, failure, readback, and rollback

Stage a reviewed successor without traffic, reject a stale predecessor and invalid dependency,
activate one complete generation, and compare source, state, provider, runtime, route, attachment,
identity, ownership, and digest readback. Simulate an approved non-destructive partial failure and
confirm stop-for-inspection. With owner confirmation, measure whole-generation rollback against the
15-minute objective and prove Application State is unchanged and prior assets remain for 24 hours.

#### Historical gate 07 · State, operator, drift, and recovery controls

Read back independent roots, buckets, IAM, locking, versioning, recovery lifecycle, WIF conditions,
protected environment, concurrency, and plan/apply scope. Confirm platform identities cannot read
fixture state and fixtures cannot read one another. Introduce only an approved reversible drift
case, prove detection, and reconcile through source. Break-glass, force-unlock, push, import, and
destroy remain unexecuted unless a separately approved recovery case requires them.

#### Historical gate 08 · Limits, streaming, isolation, and cost inventory

Exercise the approved header, body, timeout, concurrency, and stream boundaries without load claims;
verify SSE and WebSocket behavior through the edge up to the bounded test duration; and prove one
fixture's failure does not route to or alter another. Read back scale-to-zero, instance maxima,
resources, budgets, thresholds, labels, image-retention dry run, approved billable-service inventory,
and excluded services. State explicitly that budgets and instance maxima are not hard spend caps.

#### Historical gate 09 · Logging, redaction, retention, incident, and evidence

Verify one bounded completion event, required control-plane audit events, allowed fields, prohibited
field absence, owner-only access, seven-day log retention, no external sink, 30-day evidence
retention, and evidence hashes. Exercise the incident procedure without destructive action and
confirm screenshots, assertions, identities, IP addresses, payloads, state, and raw provider output
are absent from authoritative evidence.

#### Historical gate 10 · Truthful qualification and adoption boundary

AP-EVAL-M9 passes only when all mandatory gates and AP-EVAL-M3 through AP-EVAL-M8 dependencies pass
for the exact revision with zero mandatory skips. Report every failure, limitation, residual risk,
unavailable cross-project claim, and unimplemented alert. Record Live evidence only; leave Finance
Assistant and every Application Adoption unchanged and unavailable.

## AP-EVAL-M9 · Operator-driven environment lifecycle gate

### Evaluation claim

A complete passing AP-EVAL-M9 result proves that the exact reviewed Python product can prepare,
deploy, inspect, integrate, qualify, detach, safely destroy, redeploy, and requalify the staging
Platform Environment through the approved interactive lifecycle; that synthetic Fixture
Applications remain independently owned and consume versioned bundles; and that production
preparation detects existing Finance ownership without mutation.

AP-EVAL-M9 produces Contract, Fixture, and staging Live evidence within their existing meanings. It
does not produce Application Adoption evidence, qualify Finance Assistant, transfer a production
resource, or prove a production availability commitment. A repository-only pass through AP-M9-W9
means implemented and deterministically verified, not deployed or Live-qualified.

### Evaluation environments

The credential-free gate runs from the repository root:

```bash
make terraform-setup
make check
```

It performs no credential lookup, provider request, DNS lookup, Terraform backend operation,
mutation, or browser action. It uses synthetic profiles, command fakes, temporary mode-`0700`
directories, mocked Terraform providers, process-local loopback, and deterministic clocks.

Accepted staging Live gates begin only after AP-M9-W1 through W9 are merged and the exact
protected-main revision passes the complete gate. Before merge, a clean pushed pull-request
revision containing current `origin/main` may run the same staging journey with
`SOURCE_AUTHORITY=candidate` to test provider behavior. Candidate specifications, bundles, and
evidence remain digest-bound and separate, cannot satisfy AP-EVAL-M9, cannot overwrite accepted
qualification, and cannot authorize production. After merge, the owner repeats deployment and
qualification from Accepted Source. The owner starts an ordinary reversible staging creation or
update by deliberately invoking its named command; that process completes specification approval,
exact plan or bounded-action confirmation, and readback without a duplicate out-of-band approval.
Destruction, purge, ownership transfer, production cutover, scope expansion, rollback, or recovery
retains its separately named approval where required by its boundary. The local wizard uses only the
verified short-lived human operator session and creates no operation-identity fleet or stored key.
Production commands remain read-only throughout AP-M9.

### Evidence model

Repository evidence is the exact source revision, command, tool versions, test count, duration,
failures, errors, warnings, and skips reported by `make check`. Staging evidence is a private,
revision-scoped, schema-valid qualification record generated from the approved operation,
readback-closed progress, bundles, and runtime observations. It records canonical cross-boundary
digests, exact plans through redacted summaries, provider/state/ownership comparisons,
qualification results, limitations, and the final environment status.

Evidence never contains a credential, token, OAuth secret, Secret Manager payload, Terraform state,
saved plan, raw provider response, browser state, screenshot, assertion, session, restricted
member, identity claim, email address, request/response body, application data, signed URL, or
recovery copy. Provider-readable facts are marked verified; facts unavailable through an approved
readback are marked operator-attested. Attestation cannot replace a mandatory provider or runtime
gate.

### Gate structure

#### AP-EVAL-M9-01 · Authority, supersession, source, and regression integrity

Verify AP-PR-001 through AP-PR-012, AP-QR-001 through AP-QR-009, ADR-001 through ADR-014,
AP-TM-001 through AP-TM-014, AP-M9-W1 through W11, and this evaluation definition are complete and
uniquely traced. Confirm AP-M8-W1/W2 remain historical, AP-M8-W3 through W12 and the old standalone
AP-M9 proposal are superseded without execution, the source is clean protected main, and every
prior deterministic gate passes without credential or mutation.

#### AP-EVAL-M9-02 · Environment profiles and lifecycle contracts

Verify closed staging and disabled-production profiles, the small private deployment
specification, atomic progress, truthful status, Platform Integration Bundles, Application
Attachment Bundles, and Qualification Evidence. Reject placeholders, discoverable/generated facts
in profiles, cross-environment values, unknown fields, secrets, state, plans, raw provider data,
mutable references, non-canonical bytes, and stale cross-owner digests.

#### AP-EVAL-M9-03 · Interactive preparation, approval, status, and resume

With deterministic adapters, exercise first deployment, update, no-change, drift, conflict,
interruption, and resume. Prove preparation is read-only, asks only unresolved decisions, emits one
complete specification and digest, keeps approval separate from completeness, and never repeats a
closed stage. Exercise standalone preflight with ready and multi-blocker outcomes and prove it
creates no specification, digest, approval prompt, progress, plan, private lifecycle state, executor,
or external mutation. Verify the default deploy invocation performs preparation, review, approval, and
deployment without a mandatory second command; standalone prepare remains a dry run. After an
approved standalone preparation, invoke default deploy without a digest and prove it reuses the
exact current specification without regeneration, a copied digest, or another approval while all
bindings remain valid. Change source or profile binding and prove deploy returns to preparation;
introduce a discovery blocker or malformed retained specification and prove it stops without
replacement. Verify explicit current-digest selection remains compatible. Verify terminal
transcripts for `y/N` plan review, typed irreversible boundaries, Enter checkpoints, bounded
polling, cancellation, truthful waiting/failure states, and no secret prompt or output.

Retain an exact terminal predecessor workflow and prove status reads it as historical without
changing its canonical bytes or synthesizing newly introduced stage evidence. Prove declined
current-pointer supersession changes no file; confirmed supersession retains the predecessor
specification and final snapshot and starts fresh current-workflow progress. A running or waiting
predecessor must remain an active-operation conflict, and malformed retained progress must return a
named readback blocker rather than `OPERATOR_INTERNAL_ERROR`.

Exercise both local-maintenance checks from dirty and unpushed source. Prove preflight-check retains
every non-source prerequisite blocker. Prove deploy-check validates retained records, uses actual
read-only provider state, renders current Terraform, plans without a state lock, applies normal
policy, deletes ephemeral plans, distinguishes `would-change`, `manual`, and `deferred`, and never
creates approval, specification, progress, operational evidence, provider mutation, or source
authority. Prove its public result is `ready` only when required platform services, Platform State,
Shared VPC, application-subnet router/NAT, Shared Edge, active runtime, TLS, and final readback pass;
otherwise prove it distinguishes reconciliation-required, incomplete, and blocked outcomes.
Invoke default deployment and prove it consumes this result before approval or mutation, stops on a
blocked check, and replans every executable change at its exact apply boundary.

Exercise `application-handoff-check` for public, authenticated, and restricted requests. Prove it
consumes platform readiness without interpreting stage names; blocks on platform reconciliation,
missing application services, stale or absent application-project Shared VPC grants, mismatched
platform revision or generation, and an invalid application identity projection.
Prove it succeeds without publishing a bundle, approving or applying a plan, acquiring a state
lock, changing provider state, or writing operational lifecycle state.

#### AP-EVAL-M9-04 · State, Terraform, operator session, plans, and ownership

Verify deployable bootstrap/foundation/edge phases preserve independent state ownership, locking,
recovery, provider locks, environment isolation, runtime-identity separation, key absence, active
human account/project checks, plan canonicalization, policy enforcement, same-execution plan/apply
binding, and readback. Reject a wrong account or project, cross-root target, alternate source,
implicit provider default, replacement, unexpected destroy, state push, force-unlock, import, or
automatic recovery. Verify the platform bootstrap manages only the platform-state bucket; the
dedicated fixture project owns its versioned fixture-state bucket and independent root prefixes.
Verify Platform State owns the exact regional Cloud Router and Public Cloud NAT serving only the
application subnet, with provider-managed addresses, VM endpoints, error-only logging, and
all-traffic egress. Reject an application-owned, unbounded, differently named, or unlogged NAT.
Verify the lifecycle creates no operation-identity or impersonation fleet.
Verify deployment checking rejects the same destructive, replacement, ownership, provider, and
scope violations as deployment while never invoking apply or acquiring the remote state lock.

#### AP-EVAL-M9-05 · Interactive staging deployment, OAuth, DNS, and TLS

For the exact approved staging specification, reconcile foundation, immutable image, OAuth client
identifier and redirect configuration, Secret Manager version metadata, Shared Edge, load balancer,
reserved address, exact Squarespace instruction, authoritative and recursive DNS, certificate
readiness, labels, budgets, retention, and provider/state inventories. Prove the wizard remained
active across manual checkpoints, never received the OAuth secret, and stopped on every mismatch.

#### AP-EVAL-M9-06 · Application bundles, attachments, and registration lifecycle

Create or read back the dedicated fixture project, connect it to the platform Shared VPC, and prove
the Cloud Run service agent has read-only host-network discovery and network-user access only on
the application subnet, while neither operation created a runtime or route. Generate public,
authenticated, and restricted
application-project-scoped fixture bundles; verify exact project, host network, subnet, region,
all-traffic egress, least-data projections, and absence of the OAuth client secret. Before each bundle is
published, run the application handoff check and prove the platform plans, application services,
project connection, and access-mode projection are ready without mutation. Deploy each selected fixture
through its separate Application State invocation in that project; validate its returned attachment
bundle plus target project, network, internal ingress, edge-caller IAM, audience, and readiness;
then separately activate a complete Registration Generation preserving prior registrations after
each selection, culminating in a generation containing all three fixtures. Exercise attachment replacement, stale bundle
rejection, detach, redeploy/reactivate,
terminal retirement, route reservation, `503` detached behavior, `410` retired behavior, closed
unknown routes, and proof that no platform action destroys Application State.

For one selected fixture, stop after attachment generation and verify the operator receives exact
mode-`0600` canonical integration-bundle, attachment-bundle, and registration-intent paths and
digests without a registration transition. Inspect them, then run `platform-register` and prove it
performs no Application State apply. Rerun the handoff and prove it reuses the pair only when every
source, authority, project connection, platform-generation, digest, image, relationship, and
provider-posture binding remains current. Change each binding class and verify reuse is refused and
the normal fixture reconciliation path runs instead.

#### AP-EVAL-M9-07 · Live routing, identity, isolation, and limits

Exercise HTTPS redirect, certificate, catalogue, routes, mounts, path rewriting, public access,
Google OIDC/session/logout, authenticated and restricted allow/deny, assertion issuer/audience/time,
JWKS/key behavior, visitor-header replacement, direct-origin denial, application verification,
cross-application isolation, failure isolation, HTTP/SSE/WebSocket/upload/download boundaries,
timeouts, concurrency, and redacted completion events. Force each allowlisted identity dependency
failure and verify that its constant diagnostic code is queryable from the dedicated regional log
bucket while provider exceptions, authorization codes, tokens, identities, sessions, request
parameters, and payloads remain absent. Record the approved demo limitations without claiming
general availability or distributed replay prevention. Prove a protected application in the
connected service project can retrieve the public platform JWKS through the platform-owned
application-subnet NAT, then deny or remove that egress and verify the application fails closed
with only `verification_keys_unavailable` in its diagnostic event.

#### AP-EVAL-M9-08 · Rollback, fixture cleanup, platform destruction, and redeployment

Only after every non-mutating qualification check passes, explain the traffic effect and obtain
explicit confirmation before temporarily activating the reviewed predecessor complete generation.
Verify the predecessor readback, obtain separate explicit restoration confirmation, restore the
original generation, and verify it owns 100 percent of traffic, all while preserving Application
State. A failed prerequisite must block the rollback exercise without prompting or changing
traffic. Detach and destroy fixture-owned assets under fixture authority. Verify platform
destruction refuses an active attachment, names the exact environment and inventory, requires
typed confirmation, handles DNS/cache and OAuth checkpoints, touches no application resource,
stops on partial failure, and retains backends/evidence and the connected Shared VPC foundation
absent separate disconnect or purge authority. After an approved staging destroy, redeploy and
repeat mandatory qualification before reporting staging ready.

#### AP-EVAL-M9-09 · Evidence privacy, truthful status, drift, and handoff

Verify operation/progress/evidence digests, allowed fields, prohibited-data scans, retention,
owner access, actual failures and blocked stages, provider/state/ownership agreement, drift
detection, operator-attested versus verified labels, and final source-bound status. A missing,
malformed, expired, mismatched, skipped, or prohibited record fails rather than being waived or
reconstructed.

#### AP-EVAL-M9-10 · Production isolation and Application Adoption boundary

Run production preparation read-only. Prove it uses distinct profile, state, identity, OAuth,
DNS/TLS, evidence, and destructive authority; detects current `apps.comfforts.com` ownership; emits
`OWNERSHIP_TRANSFER_REQUIRED`; and performs no provider mutation or import. Confirm the Finance
integration remains inactive, Finance scripts and state are unchanged, and actual production
cutover requires a separate platform checkpoint plus Finance-owned adoption authority.

### Pass, fail, blocked, and unavailable semantics

Every gate reachable for the current AP-M9 work package is mandatory. `pass` requires exact
complete evidence. `fail` records any mismatch, unexpected warning, command error, prohibited data,
scope expansion, false claim, or unsafe mutation. A dependent gate after failure is `blocked` with
its cause. Behavior owned by an unimplemented later AP-M9 package is `unavailable`, never a pass or
skip. At final AP-M9 acceptance all ten gates must pass with zero failures, blocked gates,
unexpected warnings, prohibited findings, or mandatory skips.

### Limitations

AP-EVAL-M9 does not qualify production traffic, Finance Assistant compatibility, another real
application, production availability, cross-cloud behavior, Python-to-Go migration, or an
application's principals, data isolation, provider rights, Feature Entitlements, recovery, or
destruction. Those remain production-cutover, later migration, or Application Adoption evidence.

This definition originated in AP-M9-W1. AP-M9-W2 removed the retired manifest path, W3 implemented
the lifecycle contracts, W4 implemented credential-free preparation/status and deterministic fake
resumable progress, W5 implemented repository-only Terraform lifecycle policy and mocked plans, and
W6 implemented the interactive deployment engine plus closed command boundary. W7
implemented application handoff and registration lifecycle controls, and W8 implemented
qualification and safe-destruction controls behind guarded boundaries and wired the real staging
deployment adapters only for a verified human session. The repository work itself created no identity,
credential, Terraform state or saved plan, provider
resource, OAuth client, secret, DNS record, certificate, application asset, Live evidence bundle,
deployment, destruction, or passing operational result.
