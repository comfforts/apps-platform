# App Platform implementation plan

Version 0.12 | Status: AP-M9-W1 through AP-M9-W6 implemented;
AP-M8-W1/W2 preserved historically; AP-M8-W3 through W12 superseded without execution; every
external operator action remains pending

This document preserves delivery items 3 through 7 and the completed historical AP-M8-W1/W2 work.
AP-M7 implements and statically validates reviewed Terraform configuration and inert workflow
templates. AP-M8-W1/W2 implemented a manifest-driven qualification-deployment proposal but no real
manifest was accepted and no AP-M8-W3 through W12 operation began. AP-M9 supersedes that unexecuted
path with the operator-driven environment lifecycle below. AP-M9-W1 through W6 establish active
governance, remove the retired interface, implement lifecycle contracts and the credential-free
operator core, implement the repository-only Terraform lifecycle, and implement the unarmed
interactive deployment engine plus closed command boundary. No package authorizes
backend initialization, authenticated plan or apply, cloud
call, credential, identity, provider resource, DNS mutation, deployment, qualification,
destruction, production change, or Application Adoption.

Requirements: AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009

Decisions: ADR-001 through ADR-013

Design: [App Platform system design](03_system_design.md)

Threats: [App Platform threat model](06_threat_model.md)

Evaluation: [App Platform evaluation strategy](05_evaluation_strategy.md)

## AP-M3 · System design and versioned contracts

### Outcome

AP-M3 establishes the reviewed logical platform design, threat boundary, versioned machine
contracts, and deterministic offline validation needed before Fixture Applications may be planned.
It provides one deep module interface:

```text
compile(previous_generation, proposed_registration_set, platform_configuration)
    -> compiled_configuration + ownership_manifest
    |  ordered_validation_violations
```

The interface is pure and side-effect-free. It is not a deployment interface and may not call a
provider, resolve DNS, read credentials, inspect another state backend, or mutate a repository or
runtime.

### Scope

AP-M3 includes:

- system-design and threat-model authority;
- an item-scoped implementation plan and deterministic evaluation gate;
- Version 1 schemas for registration sets, attachments, compiled Shared Edge configuration,
  verified identity context, and state ownership;
- a standard-library reference compiler and validator;
- synthetic contract vectors and deterministic tests; and
- authority, status, repository-layout, and next-slice handoff updates.

AP-M3 excludes:

- a catalogue, edge, identity, fixture, or application runtime;
- provider-specific attachment adapters or provider discovery;
- Terraform, cloud resources, state backends, plans, DNS, TLS, IAM, OAuth, or secrets;
- live mutation, runtime qualification, screenshots, or authenticated evidence; and
- Finance Assistant code, configuration, migration, access changes, or Application Adoption.

## Dependencies

| Dependency | Required state | AP-M3 treatment |
| --- | --- | --- |
| Governance foundation | Merged and passing | Preserve project boundary, extraction rules, and `make check` |
| Product requirements | Authoritative | Trace every contract behavior and exclusion |
| ADR-001 through ADR-004 | Accepted | Treat ownership, admission, registration, and fixture-first decisions as constraints |
| System design | Approved in this slice | Define the compiler and future runtime seams before schemas |
| Threat model | Approved in this slice | Cover every Contract (`C`) evidence requirement |
| Owner decisions | Approved for this slice | Use the Version 1 route, lifecycle, attachment, identity, and ownership semantics in the design |

An unmet or changed dependency stops the affected work package. Discussion history, an Integration
Draft, or a later-slice implementation cannot fill an authority gap.

## Work packages

### AP-M3-W1 · Logical system design

Deliverables:

- `docs/03_system_design.md`; and
- only the canonical terms required by that design in `GLOSSARY.md`.

The design must define the Shared Edge, catalogue, Registration Set, Application Registration,
Application Attachment, route model, admission and identity seam, lifecycle, application-release
boundary, exclusive ownership, failure behavior, fixture boundary, and unresolved implementation
decisions. It must describe no runtime control as implemented.

### AP-M3-W2 · Threat boundary

Deliverables:

- `docs/06_threat_model.md`; and
- the system-design link to that authority.

The threat model must identify assets, actors, trust crossings, control ownership, data classes,
threats `AP-TM-001` through `AP-TM-014`, evidence classes, residual risks, and unresolved security
decisions. Contract evidence must never be represented as fixture, live, or adoption evidence.

### AP-M3-W3 · Plan and evaluation authority

Deliverables:

- `docs/04_implementation_plan.md`; and
- `docs/05_evaluation_strategy.md`.

These documents define only AP-M3. They must name exact deliverables, acceptance criteria, tests,
evidence, exclusions, security and privacy impact, limitations, and the merge dependency that blocks
delivery item 4.

### AP-M3-W4 · Versioned contracts

Deliverables:

- `contracts/README.md`;
- `contracts/schemas/registration-set.v1.schema.json`;
- `contracts/schemas/application-attachment.v1.schema.json`;
- `contracts/schemas/compiled-shared-edge.v1.schema.json`;
- `contracts/schemas/verified-identity-context.v1.schema.json`; and
- `contracts/schemas/state-ownership-manifest.v1.schema.json`.

All schemas use JSON Schema Draft 2020-12, stable `urn:comfforts:app-platform:` identifiers and
references resolved through a project-local registry, explicit Version 1 discriminators, bounded
strings and collections, and closed objects unless a reviewed extension point is necessary. No
schema fetches a remote reference.

`contracts/README.md` is the contract index and must define:

- authority and precedence;
- schema and instance versioning;
- backward-compatible versus breaking change rules;
- canonical serialization and digest rules;
- stable violation-code semantics;
- the compiler interface and its non-mutating behavior;
- supported and deliberately unsupported adapter kinds;
- security and secret-handling rules; and
- the difference between contract implementation and runtime qualification.

The Version 1 schemas must encode the system design without adding provider-specific behavior. An
unknown attachment adapter is invalid; AP-M3 may use a synthetic contract-only adapter kind for
test vectors, but it may not implement or imply a Fixture Application or live provider adapter.

### AP-M3-W5 · Deterministic validation

Deliverables:

- `contracts/__init__.py`;
- `contracts/validation.py`;
- `contracts/test-vectors/manifest.v1.json`;
- synthetic valid and invalid JSON cases under `contracts/test-vectors/`;
- `tests/test_contracts.py`; and
- a `contract-check` dependency in the project `Makefile`.

The reference validator uses the Python standard library only. It implements the explicitly
documented JSON Schema keyword subset used by these five schemas and fails if a schema introduces
an unsupported keyword. It is not a general JSON Schema implementation. Shape validation through
that bounded schema interpreter and semantic compilation are separate phases checked by the same
test-vector manifest so they cannot silently diverge.

The validator must:

- parse bounded JSON and reject duplicate object keys;
- validate contract versions, required fields, types, bounds, enumerations, and unknown fields;
- validate the complete set for routes, mounts, reserved paths, lifecycle, admission, attachment,
  audience, catalogue, and ownership semantics;
- compare a proposed generation with its declared predecessor when supplied;
- emit stable, ordered violations and no compiled output on any failure;
- emit canonical compiled configuration and ownership output on success; and
- perform no network access, provider lookup, credential access, input mutation, or file write.

Tests exercise only observable behavior through the compiler interface. Test data is deterministic,
synthetic, non-secret, and not a Fixture Application.

### AP-M3-W6 · Authority integration and handoff

Deliverables update only:

- `AGENTS.md`;
- `README.md`;
- `docs/README.md`;
- `docs/repository_layout.md`;
- `prompts/README.md` and `prompts/starting_prompt.md`;
- `tests/test_governance.py`; and
- the existing Finance Integration Draft checks only if required to preserve its inactive status.

The updates place the new authorities in the reading order, record contract implementation without
claiming runtime behavior, preserve the inactive Finance package, and route the next task to item 4
planning only after AP-M3 merges. They must not add a fixture implementation plan or evaluation
authority.

## Ordered delivery

Work proceeds in this order:

1. approve system design;
2. approve the threat boundary;
3. approve the AP-M3 plan and evaluation strategy;
4. approve Version 1 schemas and contract policy;
5. approve deterministic validation and test evidence; and
6. reconcile authority indexes and the next-slice handoff.

Each work package is a small reviewable commit. A later package may refine an earlier AP-M3 document
only to link newly added authority, correct an inconsistency, or record actual results. It may not
silently change an approved interface or introduce item 4 behavior.

## Acceptance criteria

AP-M3 is accepted only when all of the following are true:

1. Every planned behavior traces to a requirement, accepted ADR, system-design section, and
   applicable threat identifier.
2. The five schemas are strict, versioned, locally resolvable, extraction-safe, and free of secrets
   and provider-specific operational assumptions.
3. Schema and semantic validation agree for every declared test vector.
4. Valid input produces byte-stable canonical output and a stable digest for the same compiler
   version; invalid input produces ordered stable violations and no partial output.
5. Tests cover catalogue projection, route isolation, every Admission Mode, identity claim shape,
   attachment mounts, application updates, lifecycle transitions, rollback inputs, and exclusive
   ownership.
6. Contract controls mapped to `AP-TM-001` through `AP-TM-014` are tested to their declared `C`
   boundary without claiming `F`, `L`, or `A` evidence.
7. `make check` passes without a credential, network call, paid provider, browser, cloud account, or
   external mutation.
8. Project-relative contract loading and a temporary-copy validation test demonstrate that the
   contract layer does not depend on the source-repository layout.
9. The change contains no fixture runtime, infrastructure, Terraform state, saved plan, DNS,
   identity configuration, credential, or Finance Application Adoption change.
10. Status and handoff documents describe contract behavior as implemented only after its tests
    pass and continue to describe every runtime and live control as unimplemented.

Near-complete work, undocumented skips, or passing tests against a different schema revision do not
satisfy AP-M3.

## Required evidence

The pull-request handoff records:

- branch, source revision, and final revision;
- commits and changed paths for each AP-M3 work package;
- exact verification commands, exit status, test count, failures, and skips;
- schema identifiers, compiler version, and test-vector manifest version;
- the requirements, ADRs, and threats covered by the deterministic gate;
- security and privacy impact;
- explicit `F`, `L`, and `A` limitations and every unresolved later decision; and
- confirmation that no credential, state, saved plan, authenticated payload, or external mutation
  was used.

Test output in a review description is evidence for this repository revision. Generated reports,
screenshots, plans, caches, or authenticated artifacts are not committed merely to demonstrate a
passing deterministic gate.

## Security and privacy impact

AP-M3 reduces ambiguity by making untrusted registration inputs, identity claims, route selection,
attachment references, and state ownership strict and testable. It introduces no runtime data flow.
Restricted membership and signed assertion examples use synthetic values; secret payloads,
application data, provider data, and real identities are prohibited from schemas, vectors, logs,
and evidence.

The reference validator is not a security boundary for a live deployment. Future runtimes must
enforce the same contracts at their own trust crossings and qualify the runtime controls separately.

## Limitations and deferred work

AP-M3 does not prove that:

- a Shared Edge, catalogue, identity boundary, attachment, or state backend exists;
- signatures, ingress, IAM, TLS, DNS, routing, rollback, logging, or provider controls work live;
- a Fixture Application or real application is compatible; or
- Finance Assistant has adopted or can migrate to the platform.

AP-M3 did not approve a fixture implementation. That merge dependency is now satisfied and the
separate AP-M4 authority below does not retroactively add Fixture evidence to AP-M3. Infrastructure
and Application Adoption remain later independent slices.

## Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M3-W1 through AP-M3-W3 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-004 | AP-TM-001 through AP-TM-014 |
| AP-M3-W4 | AP-PR-001 through AP-PR-007; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001, ADR-002, ADR-003 | AP-TM-001 through AP-TM-012, AP-TM-014 |
| AP-M3-W5 | AP-PR-001 through AP-PR-008; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001 through ADR-004 | Contract (`C`) portions of AP-TM-001 through AP-TM-014 |
| AP-M3-W6 | AP-PR-008, AP-PR-009; AP-QR-003, AP-QR-004, AP-QR-006 | ADR-004 | AP-TM-010, AP-TM-011, AP-TM-014 |

## AP-M4 · Deterministic Fixture Applications

### Outcome

AP-M4 implements the smallest deterministic qualification harness for the logical platform design.
It provides one deep in-process module with three observable operations:

```text
activate(proposed_registration_set) -> activation_result
rollback(reviewed_generation_digest) -> activation_result
handle(request) -> response
```

Activation resolves the declared predecessor against the harness's current reviewed generation;
the caller cannot substitute a separate predecessor object. Activation and rollback change only
the harness's in-memory Platform State. `handle` accepts and returns immutable values and is the
request test surface. Callers cannot configure routes, catalogue entries, admission exceptions, or
attachment targets outside a compiled generation and the read-only adapter map supplied at
construction.

AP-M4 produces Fixture (`F`) evidence only. It does not turn the harness into a network server or
qualify a live provider, real identity, persistent control plane, or consuming application.

### Scope

AP-M4 includes:

- the deterministic reference topology and fixture threat profile selected in system design;
- a Python standard-library, synchronous, in-process request pipeline with no listening socket;
- the `fixture-in-process-v1` attachment adapter and its exact inert resource-reference binding;
- HTML catalogue projection, canonical route and mount selection, forwarding, and closed responses;
- public, authenticated, and restricted admission using synthetic identities;
- fixture-only signed identity delivery, independent application verification, and replay denial;
- three independently constructed Fixture Applications and their Application State;
- reviewed registration generations, atomic in-memory activation, lifecycle journeys, and rollback;
- deterministic behavior, security, extraction, non-mutation, and redaction tests; and
- status, repository-layout, and next-slice handoff reconciliation after the gate passes.

AP-M4 excludes:

- a socket, HTTP framework, browser, process manager, external registration endpoint, or database;
- network ingress, DNS, TLS, OAuth, production signing, credential, IAM, or provider discovery;
- persistence, concurrent writers, streaming, load, availability, or performance qualification;
- Terraform, cloud resources, state backends, live plans, deployment, or operator mutation;
- changes to Version 1 attachment fields or identity claims; and
- Finance Assistant requirements, code, infrastructure, identity, state, registration, migration,
  access, or Application Adoption.

### Dependencies

| Dependency | Required state | AP-M4 treatment |
| --- | --- | --- |
| AP-M3 | Merged to clean `main` with `make check` passing | Reuse the accepted Version 1 contracts and compiler |
| Fixture system design | Owner-approved on the AP-M4 branch | Implement only the selected in-process topology and evidence boundary |
| Threat profile | Owner-approved on the AP-M4 branch | Cover every applicable Fixture (`F`) claim without implying Live (`L`) evidence |
| AP-M4 plan and evaluation | Approved before runtime edits | Bind implementation paths, observable behavior, gates, and evidence |
| Python runtime | Supported Python 3 standard library | Add no package, service, credential, or network dependency |
| Owner decisions | Recorded in design | Use the three fixtures, exact limits, synthetic assertion profile, and Git-reviewed registration model |

Changing a Version 1 field, a requirement, an accepted ADR, or the Fixture evidence boundary stops
the affected package for owner review. An Integration Draft, a real application, or live provider
behavior cannot substitute for a missing AP-M4 dependency.

### Work packages

#### AP-M4-W1 · Fixture topology and threat profile

Deliverables update only:

- `docs/03_system_design.md`;
- `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects the in-process reference topology, three fixtures, request limits, synthetic
identity profile, in-memory generation model, direct-bypass claim boundary, and remaining live
decisions. It implements no runtime and creates no Fixture evidence.

#### AP-M4-W2 · Plan and evaluation authority

Deliverables update only:

- `docs/04_implementation_plan.md`;
- `docs/05_evaluation_strategy.md`; and
- focused AP-M4 identifier and scope checks in `tests/test_governance.py`.

This package defines the remaining implementation order, exact acceptance boundary, mandatory
Fixture gates, evidence, exclusions, and handoff. It may not add `fixtures/` implementation.

#### AP-M4-W3 · Deterministic reference edge and attachment binding

Deliverables:

- `fixtures/__init__.py` and `fixtures/reference_edge.py`;
- the `fixture-in-process-v1` semantic binding in `contracts/validation.py` and its policy in
  `contracts/README.md`;
- `tests/test_fixtures.py` coverage for bounded requests, catalogue, routes, mounts, forwarding,
  closed responses, and attachment failure; and
- a standard-library `fixture-check` target in `Makefile`, included by `make check`.

The reference edge implements one `handle(request) -> response` interface. Adapter resolution is an
exact read-only map lookup; it performs no dynamic import, URL fetch, filesystem lookup, or provider
discovery. An invalid fixture resource reference or missing target rejects activation without
changing the current generation.

#### AP-M4-W4 · Synthetic identity and admission

Deliverables extend only:

- `fixtures/reference_edge.py` with the explicitly constructed identity adapter and fixture signer;
- `fixtures/identity.py` with envelope verification and the bounded replay store; and
- `tests/test_fixtures.py` with public, authenticated, restricted, stripping, forgery, expiry,
  issuer, audience, cross-application, and replay cases.

The implementation uses only injected public test material and an injected clock. It must not read
an environment secret, select a production algorithm, emulate OAuth, or describe its in-process
assertion denial as network-origin protection.

#### AP-M4-W5 · Independent Fixture Applications and registrations

Deliverables:

- `fixtures/applications.py`;
- complete reviewed generations under `fixtures/registrations/`;
- synthetic fixture-owned setup under `fixtures/data/` only when data cannot be clearer as code;
  and
- `tests/test_fixtures.py` coverage for all three applications, principal derivation, entitlement
  denial, catalogue visibility, state isolation, and cross-application denial.

`fixture-public`, `fixture-authenticated`, and `fixture-restricted` each receive their own runtime
and Application State. Registration inputs use the public Version 1 contracts and must not copy
contract test vectors or depend on Finance Assistant.

#### AP-M4-W6 · Generation lifecycle, failure, and rollback journeys

Deliverables extend only:

- `fixtures/reference_edge.py` with atomic activation and rollback over reviewed in-memory
  generations;
- the fixture registration generations needed for update, suspension, retirement, and attachment
  replacement; and
- `tests/test_fixtures.py` with successful and failed lifecycle journeys.

Tests observe initial registration, an unchanged-registration application release, a registration
update, suspension, retirement, replacement, invalid or unavailable activation, failure isolation,
and rollback. A generation change must never roll back, delete, or transfer Fixture Application
State.

#### AP-M4-W7 · Qualification record and handoff

Deliverables update only after every behavioral gate passes:

- `README.md`, `docs/README.md`, and `docs/repository_layout.md`;
- `prompts/README.md` and `prompts/starting_prompt.md`;
- `AGENTS.md` only if the authoritative reading or verification order changes;
- governance checks that protect truthful AP-M4 status; and
- the pull-request handoff record, without committing generated or authenticated evidence.

The updates may record the exact Fixture evidence obtained at the evaluated revision. They must
leave Live and Adoption evidence unavailable and must not initiate infrastructure or application
adoption work.

### Ordered delivery

Work proceeds in this order:

1. approve fixture topology and threat-profile authority;
2. approve AP-M4 planning and evaluation authority;
3. implement and approve the bounded reference edge and fixture adapter binding;
4. implement and approve synthetic identity and admission;
5. implement and approve the three Fixture Applications and reviewed registrations;
6. implement and approve lifecycle, failure, and rollback journeys; and
7. run the complete gate, record actual evidence, and reconcile the handoff.

Each work package is a separate small commit reviewed before the next package is edited. A later
package may change an earlier file only to complete the behavior assigned above, correct a proven
inconsistency, or record actual results. It may not add a listening service, live provider behavior,
or Application Adoption.

### Acceptance criteria

AP-M4 is accepted only when all of the following are true:

1. Every implemented behavior traces to AP-PR-001 through AP-PR-009, AP-QR-001 through AP-QR-006,
   ADR-001 through ADR-004, the fixture system design, and the applicable Fixture portions of
   AP-TM-001 through AP-TM-014.
2. Exactly three independent fixtures register through Version 1 complete Registration Sets, and
   only `fixture-in-process-v1` resolves in the harness.
3. The request pipeline enforces the exact method, path, query, header, body, and response limits
   before untrusted values cross their relevant seam.
4. Catalogue, routes, attachment mounts, forwarding, admission, and closed responses derive only
   from the one current compiled generation.
5. Protected fixtures independently reject missing, visitor-controlled, forged, expired,
   wrong-issuer, wrong-audience, cross-application, and replayed assertions.
6. Platform admission never grants the restricted fixture's synthetic premium Feature Entitlement,
   and each fixture's principal and state remain application-scoped.
7. Activation and rollback change one complete generation atomically, preserve the last reviewed
   generation after failure, and never mutate Fixture Application State.
8. Every mandatory AP-EVAL-M4 gate passes through `make check` without credentials, network access,
   package installation, browser use, cloud access, external mutation, or mandatory skips.
9. Tests and evidence label in-process direct-call denial, synthetic cryptography, and in-memory
   lifecycle behavior as Fixture evidence rather than network, production-identity, or persistence
   qualification.
10. Finance Assistant and every infrastructure, Terraform, DNS, identity, credential, deployment,
    and Application Adoption path remain unchanged.

Near-complete behavior, a warning-only denial, an undocumented skip, a test against an unreviewed
generation, or a Fixture result presented as Live or Adoption evidence fails AP-M4.

### Required evidence

The pull-request handoff records:

- branch, AP-M3 merge base, evaluated source revision, and final revision;
- one commit and changed-path list for each AP-M4 work package;
- exact commands, working directory, interpreter version, exit status, duration, test count,
  failures, errors, warnings, and skips;
- fixture registration generation and digest, contract and compiler versions, enabled adapter kind,
  and identities expressed only as synthetic labels;
- the requirements, ADRs, and Fixture threat claims covered by each gate;
- security and privacy impact, limitations, and every unresolved Live and Adoption decision; and
- confirmation that no credential, network call, state backend, saved plan, authenticated payload,
  or external mutation was used.

Console output from the revision-scoped deterministic run is sufficient. Generated reports,
screenshots, captured assertion envelopes, interpreter caches, and copied state are not committed as
proof.

### Security and privacy impact

AP-M4 introduces executable parsing, routing, admission, assertion, and application seams for
synthetic inputs. It reduces design ambiguity by exercising their failure behavior, but it creates
no external ingress and processes no real identity or application data. Public test key material is
deliberately non-secret and must never be reused as a credential.

Logs and test diagnostics may contain fixture identifiers, generation digests, outcome codes, and
correlation identifiers. They must not contain assertion envelopes, restricted member sets,
session labels, request bodies, principal maps, entitlement contents, or application state.

### Limitations and deferred work

AP-M4 cannot prove that:

- the Shared Edge is network reachable, correctly deployed, or isolated from direct origin access;
- DNS, TLS, OAuth, IAM, provider signing, key custody, rotation, quotas, or alerts work;
- generation state survives a process restart or concurrent operator change;
- the harness meets availability, latency, throughput, accessibility, or browser requirements; or
- a real application, including Finance Assistant, is compatible with or authorized to adopt the
  platform.

Infrastructure implementation, Live qualification, and each Application Adoption require separate
owner-approved branches, plans, evaluation gates, and evidence after AP-M4 merges.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M4-W1 through AP-M4-W2 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-004 | Fixture (`F`) portions of AP-TM-001 through AP-TM-014 |
| AP-M4-W3 | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004 | AP-TM-001 through AP-TM-004, AP-TM-007, AP-TM-009, AP-TM-012, AP-TM-013 |
| AP-M4-W4 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002, AP-QR-005 | ADR-003, ADR-004 | AP-TM-004 through AP-TM-006, AP-TM-009, AP-TM-010, AP-TM-013 |
| AP-M4-W5 | AP-PR-001 through AP-PR-006, AP-PR-008, AP-PR-009; AP-QR-001 through AP-QR-004, AP-QR-006 | ADR-001 through ADR-004 | AP-TM-001 through AP-TM-006, AP-TM-008 through AP-TM-010, AP-TM-014 |
| AP-M4-W6 | AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-001, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004 | AP-TM-003, AP-TM-007 through AP-TM-009, AP-TM-013 |
| AP-M4-W7 | AP-PR-008, AP-PR-009; AP-QR-003 through AP-QR-006 | ADR-004 | AP-TM-010, AP-TM-011, AP-TM-014 |

## AP-M5 · Platform infrastructure planning

### Outcome

AP-M5 converts the owner-approved Live decisions into repository authority for the smallest safe
implementation and qualification sequence. It defines what later slices may implement, how state
and operator authority remain exclusive, which actions require explicit approval, and what Live
evidence must prove. AP-M5 produces no Contract, Fixture, Live, or Adoption evidence and authorizes
no external mutation.

The planned sequence deliberately separates:

1. networked provider runtime implementation;
2. Terraform and workflow implementation;
3. qualification-environment deployment and explicit DNS enablement;
4. Live qualification and evidence review; and
5. any later Application Adoption.

Passing AP-M5 means the planning authority is internally consistent and complete enough to propose
those later slices. It does not mean any planned control exists.

### Scope

AP-M5 includes:

- accepted GCP qualification topology and `gcp-cloud-run-v1` attachment decisions;
- Google OIDC Platform Sessions and application-bound ES256 assertion decisions;
- GCS backend roots, GitHub OIDC/Workload Identity Federation, protected-main operation, and
  break-glass authority;
- immutable Registration Generation staging, activation, DNS/TLS sequencing, readback, rollback,
  and retention decisions;
- logging, evidence, incident, privacy, runtime-scaling, budget, cleanup, and cost controls;
- a later-slice delivery sequence with dependencies, acceptance and rejection boundaries;
- a deterministic AP-M5 planning gate and separately defined future Live gates; and
- authority, repository-layout, status, and next-slice handoff updates.

AP-M5 excludes:

- a network listener, Shared Edge runtime, provider adapter, OAuth flow, session store, or signer;
- Terraform files, modules, state, backends, plans, imports, or provider commands;
- GitHub workflow mutation, repository settings, Workload Identity Federation, service accounts,
  IAM bindings, credentials, secrets, or OAuth clients;
- GCP API enablement, resource creation, deployment, DNS/TLS mutation, or live readback;
- committed Live evidence, screenshots, authenticated artifacts, or provider payloads; and
- Finance Assistant requirements, code, infrastructure, Terraform state, DNS, identity, access,
  deployment, migration, or Application Adoption.

### Dependencies

| Dependency | Required state | AP-M5 treatment |
| --- | --- | --- |
| AP-M3 | Merged and Contract-qualified | Preserve Version 1 interfaces and deterministic compiler behavior |
| AP-M4 | Merged and Fixture-qualified on `main` | Preserve fixture evidence and carry every Live limitation forward |
| Requirements and ADR-001 through ADR-004 | Authoritative | Do not weaken ownership, admission, fixture-first, or adoption boundaries |
| Owner Live decisions | Approved | Record them as ADR-005 through ADR-009 and provider-specific design authority |
| Dedicated GCP project | Identified, with no AP-M5 mutation authority | Record project and region as configuration without calling GCP |
| Finance Assistant | Outside the slice | Do not read its state or change its edge, DNS, identity, deployment, or access |

If AP-M4 is absent from `main`, an owner decision conflicts with an accepted requirement, or an
edit would create or mutate an external resource, AP-M5 stops rather than absorbing later work.

### Work packages

#### AP-M5-W1 · Provider and attachment topology

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-005;
- the GCP topology and Cloud Run attachment sections of `docs/03_system_design.md`;
- applicable AP-TM-001 through AP-TM-004, AP-TM-007 through AP-TM-014 boundaries in
  `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects the dedicated project, `us-west1`, qualification hostname, global load
balancer, one Cloud Run edge, typed attachment grammar, same-project fixture boundary, future
cross-project Shared VPC ownership, and explicit DNS action. It implements none of them.

#### AP-M5-W2 · Identity and assertion trust profile

Deliverables update only:

- `GLOSSARY.md` with Platform Session;
- `docs/02_architecture_decision_records.md` with ADR-006;
- the identity sections of `docs/03_system_design.md` and `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects Google OIDC, edge-managed sessions, Firestore Native, logout, restricted
membership, KMS ES256 signing, JWKS, lifetime, skew, rotation, caching, and replay posture. Existing
IAP and application-managed Google login remain unchanged pending Application Adoption.

#### AP-M5-W3 · State and operator authority

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-007;
- state and operator sections of `docs/03_system_design.md` and `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects state roots and buckets, backend recovery, protected-main operation, federated
identity, revision/plan binding, concurrency, normal local limits, and break-glass authority. It
creates no root, bucket, workflow, repository setting, identity, or state.

#### AP-M5-W4 · Activation, DNS, readback, and rollback

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-008;
- lifecycle sections of `docs/03_system_design.md` and `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects content-addressed configurations, immutable edge revisions, the one active
generation pointer, staged activation, explicit DNS/TLS sequencing, cross-layer readback, a
15-minute post-approval rollback objective, and a 24-hour minimum retention window. It performs no
activation, rollback, DNS lookup, or provider operation.

#### AP-M5-W5 · Observability, evidence, incident, and cost controls

Deliverables update only:

- `docs/02_architecture_decision_records.md` with ADR-009;
- data, evidence, and cost sections of `docs/03_system_design.md` and
  `docs/06_threat_model.md`; and
- focused authority checks in `tests/test_governance.py`.

This package selects minimized seven-day logs, 30-day evidence, owner incident authority, the USD
20 budget response, scale-to-zero bounds, resource sizes, concurrency, streaming duration, service
exclusions, image cleanup, labels, and cost allocation. It creates no sink, bucket, budget, runtime,
alert, or cleanup action.

#### AP-M5-W6 · Delivery plan and repository locations

Deliverables update only:

- `docs/04_implementation_plan.md`;
- `docs/repository_layout.md`.

This package defines AP-M5 acceptance and the later AP-M6 through AP-M9 separation, identifies
implementation inputs that remain unresolved and must not be guessed, and reserves later-owned
locations without creating them.

#### AP-M5-W7 · Evaluation authority

Deliverables update only:

- `docs/05_evaluation_strategy.md`.

This package defines the deterministic AP-EVAL-M5 planning gate and the future AP-EVAL-M6 through
AP-EVAL-M9 claim boundaries. It performs no Live evaluation and pre-fills no success result.

#### AP-M5-W8 · Planning authority validation

Deliverables update only:

- `tests/test_governance.py` and the default `make check` dependency chain only if required.

This package enforces AP-M5 identifiers, traces, later-slice separation, reserved paths, truthful
status, and absence of infrastructure or live mutation. It remains standard-library,
credential-free, deterministic, and non-mutating.

#### AP-M5-W9 · Planning record and next-slice handoff

Deliverables update only after the AP-M5 deterministic gate passes:

- `README.md`, `docs/README.md`, and `prompts/starting_prompt.md`;
- `AGENTS.md` only if its authority routing must change;
- `tests/test_governance.py`; and
- the secret-free pull-request handoff record.

These updates may record AP-M5 as merged planning authority only. They must leave every runtime,
Terraform, deployment, Live, and Adoption claim unavailable and route the next task to AP-M6 only
after this pull request merges.

## AP-M6 · Networked provider runtime implementation

### Outcome

AP-M6 implements and deterministically tests the networked Shared Edge through the approved ASGI
interface:

```text
create_app(runtime_configuration, adapters) -> ASGI application
```

The module owns the complete request pipeline behind that interface. Internal provider seams accept
production and deterministic fake adapters; callers do not assemble catalogue, routing, admission,
identity, target, forwarding, limit, failure, or logging behavior themselves. The separately
consumable application verifier exposes one compact assertion-verification interface and grants no
application permission.

Passing AP-M6 provides repository implementation evidence only. It does not prove a provider
resource, IAM grant, Google login, Cloud Run origin, DNS record, deployment, availability, cost, or
Live behavior.

### Scope

AP-M6 includes:

- the Python 3.12-or-newer Starlette/Uvicorn runtime and locked dependency environment;
- immutable generation loading and digest binding through production and fake storage adapters;
- the generation-derived root catalogue, reserved platform paths, prefix routing, and closed
  default behavior;
- Google OIDC and Firestore Platform Session adapters plus deterministic fakes;
- ES256 assertion creation, KMS signing, JWKS publication, rotation overlap behavior, and the
  direct-entry application verifier;
- `gcp-cloud-run-v1` metadata resolution, readiness and ownership checks, service-identity target
  transport, and deterministic provider fakes;
- bounded HTTP, upload, download, SSE, and WebSocket forwarding under the approved
  `qualification-v1` limits;
- generation status/readback, failure isolation, correlation identifiers, completion outcomes, and
  required redaction; and
- deterministic unit, adapter-contract, ASGI, loopback integration, extraction, and regression
  tests under AP-EVAL-M6.

AP-M6 excludes:

- a registration submission endpoint, registration database, operator control plane, mutable
  generation pointer, or unreviewed route source;
- Terraform, a backend, state, saved plan, workflow with cloud authority, repository setting,
  credential, secret value, provider call, resource creation, IAM mutation, DNS change, identity
  configuration, deployment, or authenticated evidence;
- a real Google account, OAuth client, Firestore database, KMS key, GCS object, Cloud Run service,
  load balancer, certificate, log bucket, budget, or alert;
- distributed rate limiting, WAF, CDN, load, availability, browser, or Live claims; and
- Finance Assistant code, configuration, state, hostname, identity, access, deployment, migration,
  or Application Adoption.

### Dependencies

| Dependency | Required state | AP-M6 treatment |
| --- | --- | --- |
| AP-M3 and AP-M4 | Merged and passing | Preserve Version 1 contracts, compiler behavior, Fixture evidence, and regression gates |
| AP-M5 | Merged and planning-validated | Implement only the runtime portion of the selected topology and trust profiles |
| Runtime profile | Owner-approved in AP-M6-W1 | Use Starlette/Uvicorn, the locked dependency policy, and exact `qualification-v1` limits |
| Provider access | Unavailable and prohibited | Exercise production adapter logic only through deterministic fake transports and metadata |
| Terraform and deployment | Deferred to AP-M7 and AP-M8 | Create no infrastructure path, workflow authority, or external mutation |
| Application Adoption | Unavailable | Use only independent Fixture Applications and synthetic identities |

An unmet dependency stops the affected package. A fixture default, provider default, local
credential, Finance configuration, or discussion history may not fill a missing input.

### Work packages

#### AP-M6-W1 · Runtime authority and limits

Update `docs/03_system_design.md`, this plan, `docs/05_evaluation_strategy.md`, and
`docs/06_threat_model.md` to approve:

- the deep ASGI module interface and internal provider seams;
- Python, Starlette, Uvicorn, dependency declaration, lock, and installation boundaries;
- exact header, body, timeout, concurrency, stream, rate, and rejection behavior; and
- the implementation, evidence, and later-slice exclusions.

This package creates no runtime, dependency manifest, reserved implementation directory, or cloud
configuration. Owner acceptance of its exact values is required before AP-M6-W2.

#### AP-M6-W2 · Locked runtime foundation

Add `pyproject.toml`, `uv.lock`, the smallest functional `edge/` package, an ASGI application
factory, typed runtime settings and adapter bundle, a closed-default request result, and the
project-local test target. Keep the extraction-owned root workflow synchronized with the frozen
environment.

The external module interface remains `create_app(runtime_configuration, adapters)`. Internal
interfaces are not re-exported. Tests call the ASGI interface and prove that dependency setup is
separate from the network-free `make check` command.

#### AP-M6-W3 · Immutable generation loading

Implement the generation-source seam, GCS production adapter, deterministic fake, exact object and
content digest verification, Version 1 compiled-configuration validation, startup binding, and
failure behavior. Loading one generation never discovers a bucket, follows a mutable registration
source, compiles an unreviewed set, or changes the current provider pointer.

#### AP-M6-W4 · Catalogue and registered routing

Implement escaped root-catalogue rendering, explicit platform-reserved paths, exact longest-prefix
selection within the already compiled non-overlapping route set, mount rewriting, staged/suspended/
retired exclusion, and closed unknown or malformed behavior. Framework routing contains no copy of
registration-derived application routes.

#### AP-M6-W5 · Sessions and admission

Implement Google OIDC authorization-code-with-PKCE flow, opaque host-only Platform Sessions,
Firestore production and in-memory fake stores, public optional identity, authenticated and
restricted admission, logout, absolute expiry, return-location validation, and fail-closed provider
errors. No Google access or refresh token is retained, and email never becomes an admission key.

#### AP-M6-W6 · Assertion and application verification

Implement the Version 1 ES256 assertion envelope, KMS production and deterministic fake signers,
application-specific audiences, 60-second lifetime, 30-second skew, versioned key identifiers,
JWKS publication, overlap/cache behavior, visitor-header stripping, and the application-side
verifier. Tests cover malformed, expired, wrong-issuer, wrong-audience, unknown-key, and stale-key
results without a real key or identity.

#### AP-M6-W7 · Cloud Run attachment resolution

Implement strict `gcp-cloud-run-v1` URN parsing, Cloud Run production metadata and deterministic fake
adapters, exact project/region/service matching, readiness, declared owner, edge-caller grant, and
application-audience checks. A registration-supplied URL, credential, state address, provider query,
cross-application result, or unresolved target fails closed.

#### AP-M6-W8 · Bounded application proxy

Implement service-identity target transport, path and query preservation, hop-by-hop and identity
header handling, uploads, downloads, buffered and streamed HTTP, SSE, WebSocket bridging,
cancellation, timeout, size, rate, and concurrency enforcement, and protocol-appropriate closed
errors. Tests use loopback only inside the test process and never contact an external address.

#### AP-M6-W9 · Status, readback, failure, and redaction

Implement operator-authorized generation status and readback, correlation identifiers, one
structured completion event per request or streaming connection, coarse outcomes, latency, adapter
health, failure isolation, and the approved prohibited-data list. Status reports repository and
generation facts only; it cannot activate, roll back, mutate, or reveal secrets or identity data.

#### AP-M6-W10 · Runtime qualification gate

Implement the complete AP-EVAL-M6 matrix in behavior-named tests and the default `make check`
dependency chain. Enforce all AP-M6 identifiers and traces, exact limits, adapter parity, extraction,
dependency locking, no external network, no credentials, no reserved later-slice paths, no provider
or repository mutation, and all AP-M3/AP-M4 regressions.

#### AP-M6-W11 · Runtime record and AP-M7 handoff

After AP-EVAL-M6 passes, update `README.md`, `docs/README.md`, `prompts/starting_prompt.md`, prompt
index, governance assertions, and the secret-free pull-request handoff. Record only locally
implemented runtime behavior. Leave provider deployment, Terraform, Live, and Adoption claims
unavailable and route the next task to AP-M7 only after the AP-M6 pull request merges.
If repository extraction is in progress, its reconciliation merge and explicit canonical cutover
must also complete first.

### Ordered delivery

AP-M6 work proceeds in work-package order. Each package is a separately reviewable commit and adds
its tests with its behavior. No package may defer failing behavior tests to AP-M6-W10, weaken an
existing gate, or introduce a later-slice file because its interface is known.

### Acceptance criteria

AP-M6 is accepted only when all of the following are true:

1. The owner has accepted AP-M6-W1's exact framework, dependency, and limit profile.
2. The Shared Edge presents one small ASGI interface and keeps provider adapters behind internal
   seams with production and deterministic fake implementations.
3. One immutable compiled generation exclusively derives catalogue, platform paths, application
   routing, admission, attachments, and status facts.
4. Public, authenticated, and restricted requests, session lifecycle, logout, assertion delivery,
   application verification, and every fail-closed identity path pass AP-EVAL-M6.
5. Cloud Run references resolve only through the allow-listed adapter and exact declared resource;
   no arbitrary URL, discovery, cross-application reuse, or ownership transfer is possible.
6. HTTP, uploads, downloads, SSE, and WebSocket behavior enforces every approved numeric limit,
   closes or cancels failed work, and isolates application failures.
7. Logs, status, errors, and test output exclude assertions, sessions, restricted members, request
   and response bodies, visitor metadata, application data, secrets, credentials, and state.
8. `make check` is deterministic, credential-free, external-network-free, non-mutating,
   extraction-safe, and mandatory-skip-free in an already synchronized locked environment.
9. The branch contains no Terraform, state, plan, credential, secret value, cloud call, repository
   setting change, DNS or identity mutation, deployment, or generated Live evidence.
10. Finance Assistant and all existing applications and Integration Drafts remain unchanged and
    inactive.

Near-complete runtime behavior, an untested production adapter, a fake-only hypothetical seam, an
implicit framework default, a provider lookup during tests, or a Live claim fails AP-M6.

### Required evidence

The pull-request handoff records branch and AP-M5 merge base, evaluated and final revisions, all
AP-M6 commits and changed paths, frozen dependency digest, Python version, exact commands, duration,
test counts and outcomes, identifier coverage, security/privacy impact, limitations, and unresolved
AP-M7/AP-M8 inputs. It confirms that tests used only deterministic adapters and process-local
loopback, that no external mutation occurred, and that Finance Assistant remained unchanged.

Console output is sufficient. The branch commits no credential, browser state, provider response,
request payload, generated report, screenshot, or Live evidence bundle.

### Security and privacy impact

AP-M6 introduces executable network parsing, identity, signing, provider-reference, proxy, and
logging code. Numeric limits, closed failure, header stripping, audience binding, application
isolation, fake-provider tests, and strict redaction reduce its attack surface. No production
identity, member set, application payload, key, token, session, or visitor address enters committed
test data or evidence.

The runtime cannot prove provider IAM, direct-origin denial, key custody, session persistence,
distributed rate limiting, availability, or cost. Those controls remain unqualified until their
later provider and Live gates pass.

### Limitations and unresolved inputs

AP-M6 does not deploy or call its production adapters. OAuth client values, secret references,
bucket names, object generations, key versions, Firestore database, Cloud Run services, caller
identity, IAM grants, trusted load-balancer metadata, repository federation, and initial Live
Registration Set remain AP-M7/AP-M8 inputs. Exact provider behavior, direct-origin denial,
multi-instance effects, browser login, accessibility, load, recovery, and cost remain AP-M9 Live
evidence.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M6-W1, AP-M6-W2 | AP-PR-001 through AP-PR-008; AP-QR-002 through AP-QR-006 | ADR-001 through ADR-006, ADR-008, ADR-009 | AP-TM-001 through AP-TM-007, AP-TM-009 through AP-TM-013 |
| AP-M6-W3, AP-M6-W4 | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007; AP-QR-002, AP-QR-003, AP-QR-004, AP-QR-006 | ADR-001, ADR-002, ADR-005, ADR-008 | AP-TM-001, AP-TM-002, AP-TM-007, AP-TM-011, AP-TM-013 |
| AP-M6-W5, AP-M6-W6 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-006 | ADR-003, ADR-004, ADR-006, ADR-009 | AP-TM-004 through AP-TM-006, AP-TM-010 through AP-TM-013 |
| AP-M6-W7, AP-M6-W8 | AP-PR-002, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-008; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-008 | AP-TM-002 through AP-TM-005, AP-TM-007 through AP-TM-013 |
| AP-M6-W9 through AP-M6-W11 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 | AP-TM-001 through AP-TM-014 |

`AP-PR-009`, `AP-QR-001`, `ADR-007`, `AP-TM-008`, and `AP-TM-014` are negative constraints in
AP-M6: they preserve explicit adoption and exclusive state ownership and do not authorize state or
application mutation.

## AP-M7 · Terraform and workflow implementation

### Outcome

AP-M7 implements the selected non-production topology as statically verifiable Terraform
configuration behind three root-module interfaces:

```text
bootstrap(backend_configuration) -> backend_reference_set
fixture_application(fixture_configuration, platform_reference) -> attachment_reference
platform(platform_configuration, attachment_references, registration_generation)
    -> platform_reference_set
```

The roots hide provider resources behind typed configuration and reference contracts. Reusable
modules are internal and own no environment or state. Passing AP-EVAL-M7 proves only committed
configuration shape, policy, and workflow-template behavior. It creates no state, plan, identity,
provider resource, deployment, Live evidence, or Application Adoption.

### Scope

AP-M7 includes:

- Terraform 1.17.2 and `hashicorp/google` 8.11.0 constraints, committed cross-platform provider
  locks, and an explicit provider-mirror setup boundary;
- Version 1 backend, platform, fixture, cross-state-reference, and workflow configuration schemas
  with synthetic examples and duplicate Terraform root validation;
- one backend-bootstrap root, one Platform State root, and one root for each of the three Fixture
  Applications;
- internal reusable modules for state buckets, one Fixture Application, the platform identity and
  generation foundation, the Shared Edge and hostname-level forwarding intent, and bounded
  observability, evidence, retention, labels, scaling, and cost controls;
- typed non-secret outputs and reviewed inputs without `terraform_remote_state`, backend-object
  reads, or cross-owner credentials;
- inert templates for advisory plan, exact-main apply, rollback, force-unlock, and destroy
  authorities; and
- formatting, offline validation, mocked-provider plan tests, policy tests, extraction tests, secret
  and state exclusion, and all prior regression gates under AP-EVAL-M7.

AP-M7 excludes:

- `terraform init` against any backend, authenticated plan or apply, local or remote state, saved
  plan, backend migration, import, force-unlock, state push, rollback execution, or destroy;
- a credential, secret value, OIDC token, Workload Identity Federation pool or binding, service-
  account key, GitHub environment, repository secret, variable, setting, or executable cloud
  workflow;
- a provider, metadata-server, registry, DNS, browser, or external network request during the
  default gate;
- resource creation, IAM mutation, identity configuration, image publication, DNS record, traffic
  change, deployment, readback, Live claim, or Application Adoption; and
- any Finance Assistant requirement, code, infrastructure, state, hostname, identity, access,
  deployment, migration, or integration activation.

### Dependencies and fixed inputs

| Dependency | Required state | AP-M7 treatment |
| --- | --- | --- |
| AP-M3 through AP-M6 | Merged and passing | Preserve contracts, Fixture evidence, runtime behavior, and every regression gate |
| Repository extraction | Checkpoints 1 through 5 complete | Use only canonical dedicated-root paths and repository identity `comfforts/apps-platform` |
| Terraform toolchain | Owner-approved in AP-M7-W1 | Pin Terraform 1.17.2 and `hashicorp/google` 8.11.0; never upgrade during the gate |
| Provider access | Unavailable and prohibited | Use committed schemas, synthetic values, mocked providers, and a pre-populated filesystem mirror only |
| Qualification environment | Fixed planning facts | Project `comfforts-platform-non-prod` (`455651441682`), `us-west1`, and `apps-staging.comfforts.com` remain reviewed configuration rather than module defaults |
| Operator-specific values | Unresolved | Require explicit typed values; never query, generate, or infer them |
| Deployment and Live evidence | Deferred to AP-M8 and AP-M9 | Create no executable mutation path or operational claim |

The unresolved operator values are globally unique state, configuration, log, and evidence bucket
names; protected workflow subjects and environment; managed-zone resource; immutable edge and
fixture image digests; OAuth client and Secret Manager version references; billing-account and
notification-destination references; and the initial Live Registration Set. These are unavailable
inputs, not permission to query a provider or copy a value from Finance Assistant. The repository
identity is fixed as `comfforts/apps-platform`; that fact creates no federation or mutation
authority.

### Work packages

#### AP-M7-W1 · Infrastructure implementation authority

Update `AGENTS.md`, `README.md`, `docs/README.md`, `docs/03_system_design.md`, this plan,
`docs/05_evaluation_strategy.md`, `docs/06_threat_model.md`, `docs/repository_layout.md`, the AP-M7
prompt and prompt index, and governance assertions to approve:

- the three deep root-module interfaces and internal reusable-module seams;
- the exact Terraform and provider versions, configuration contracts, and offline setup boundary;
- the root ownership, cross-state reference, workflow-template, and operator-input rules; and
- AP-M7-W2 through AP-M7-W11, AP-EVAL-M7-01 through AP-EVAL-M7-10, evidence, and exclusions.

This package creates no `infrastructure/` path, Terraform file, provider lock, Make target,
workflow template, credential, or cloud configuration. Owner acceptance of its exact profile is
required before AP-M7-W2.

#### AP-M7-W2 · Pinned Terraform foundation

Add `.terraform-version`, exact root constraints, root-specific `.terraform.lock.hcl` files,
provider-mirror setup tooling, ignored cache policy, and the temporary-copy offline validation
harness. Extend the dedicated check workflow only to install the pinned CLI, verify its checksum,
populate the locked provider mirror during setup, and then run the unchanged credential-free
`make check` interface.

Setup may access only the official Terraform release and provider registries and writes only
ignored dependency data. The gate itself performs no installation or network access and fails on a
missing tool, mirror entry, checksum, platform lock, or unexpected provider.

#### AP-M7-W3 · Versioned configuration contracts

Add Version 1 JSON Schemas, synthetic examples, loaders, and semantic policy checks for backend,
platform, fixture, cross-state-reference, and workflow configuration. Define exact required fields,
closed additional properties, canonical resource-reference forms, state-owner classes, immutable
image digests, Secret Manager references, protected subjects, destructive targets, and prohibited
secret or state material.

Examples use reserved synthetic values and cannot be selected as operator configuration. Root
variables must mirror security-critical schema types and validations; disagreement between schema
and Terraform fails the gate.

#### AP-M7-W4 · Backend bootstrap root

Implement the internal state-bucket module and the bootstrap root for one platform-state bucket and
one state bucket per Fixture Application. Enforce uniform bucket-level access, public-access
prevention, object versioning, noncurrent recovery retention of at least 90 days and 20 newer
versions, ownership labels, explicit access intent, and minimal non-secret bucket references.

The root owns only backend resources. Tests use mocked provider plans and never initialize,
migrate, read, write, lock, unlock, or destroy a backend.

#### AP-M7-W5 · Fixture Application roots

Implement one deep Fixture Application module and independent roots for `fixture-public`,
`fixture-authenticated`, and `fixture-restricted`. Each root owns exactly one Cloud Run runtime,
runtime identity, direct-ingress restriction, edge-caller grant intent, scaling caps, labels, and
typed `gcp-cloud-run-v1` attachment reference. It accepts platform issuer, audience, caller, and
public-key references as data without managing Platform State.

No fixture root owns a load balancer, platform identity, another fixture, application data,
feature entitlement, backend bucket, or registration activation.

#### AP-M7-W6 · Platform identity and generation foundation

Implement the Platform State configuration bucket, immutable compiled-generation object shape,
Firestore session database settings, KMS signing key and rotation intent, Secret Manager reference
inputs, edge runtime identity, edge caller identity, and minimal typed platform references. Secret
values never enter Terraform variables or state; AP-M7 configures only references and access
intent.

No root compiles an unreviewed Registration Set, uploads a real generation, creates an OAuth secret,
or activates a candidate revision during AP-M7.

#### AP-M7-W7 · Shared Edge and hostname forwarding

Implement the platform-owned Cloud Run edge, immutable revision-binding inputs, global reserved
address, HTTPS load balancer, Google-managed certificate intent, HTTP-to-HTTPS redirect, one
serverless backend, edge-only IAM, and 100-percent traffic configuration for one explicit candidate.
The provider URL map contains no application prefixes. Scaling, timeout, concurrency, ingress, and
identity settings match the approved runtime profile.

The root creates no DNS record and cannot import, mutate, discover, or destroy an application-owned
runtime. Synthetic plan tests prove exact resource ownership and closed direct-origin intent.

#### AP-M7-W8 · Observability, evidence, retention, and cost controls

Implement the dedicated seven-day log bucket and exclusion intent, 30-day evidence bucket,
owner-readable access intent, USD 20 budget notification thresholds, required resource labels,
zero-minimum and maximum-instance caps, Artifact Registry retention intent, and prohibited-service
policy. Billing-account reference, notification destination, and globally unique names remain
required operator inputs.

No budget event mutates resources, no raw provider or runtime payload becomes evidence, and no
cleanup policy performs an owner-unapproved deletion.

#### AP-M7-W9 · Inert workflow authority templates

Add non-executable templates under `infrastructure/workflows/` for advisory plan, exact-main apply,
rollback, force-unlock, and destroy. Enforce SHA-pinned actions, read-only default permissions,
explicit OIDC permission only where required, protected-main and environment placeholders,
root-scoped concurrency, exact source and plan digest binding, explicit targets, same-job plan/apply,
no uploaded saved plan, stop-on-partial-failure, and retained secret-free outcome metadata.

Templates cannot be placed under `.github/workflows/`, name a real federation provider or service
account, read a secret, or become executable in AP-M7. AP-M8 must separately approve and realize
every repository and cloud value.

#### AP-M7-W10 · Terraform qualification gate

Implement AP-EVAL-M7-01 through AP-EVAL-M7-10 in behavior-named tests and the default `make check`
dependency chain. Run formatting, temporary-copy offline initialization with `-backend=false` and
locked filesystem mirror, validation, explicit plan-only mocked-provider tests, static policy,
configuration examples, extraction, prohibited-file scanning, and all prior regressions.

The gate fails on an apply-mode Terraform test, provider access, implicit download, backend access,
credential lookup, live operator value, executable mutation workflow, skipped root, or false
deployed claim.

#### AP-M7-W11 · Infrastructure record and AP-M8 handoff

After AP-EVAL-M7 passes, update repository status, documentation index, prompt handoff, governance
assertions, and the secret-free pull-request record. Record only static Terraform-and-workflow
implementation. Leave backend initialization, federation, repository settings, provider resources,
deployment, Live, and Adoption unavailable and route the next task to AP-M8 only after merge.

### Ordered delivery

AP-M7 proceeds in work-package order. Each package is a separately reviewable commit and adds its
tests with its behavior. No package may defer failing policy tests to AP-M7-W10, introduce a live
operator value, or create an executable cloud mutation path because a template is already known.

### Acceptance criteria

AP-M7 is accepted only when all of the following are true:

1. The owner has accepted AP-M7-W1's exact root interfaces, toolchain, configuration contracts,
   work packages, static gate, and exclusions.
2. Bootstrap, Platform State, and each Fixture Application State are independent roots with one
   declared owner and no overlapping managed resource.
3. Reusable modules own no environment or state and remain hidden behind the root interfaces.
4. Typed non-secret references are the only cross-state exchange; no root reads another backend or
   uses `terraform_remote_state`.
5. Root variables and Version 1 configuration schemas reject missing, extra, malformed, secret,
   state-bearing, placeholder, cross-owner, or unbounded inputs.
6. Mocked plans enforce topology, direct-origin restriction, identity separation, immutable
   generation binding, scaling, retention, labels, approved services, and cost controls.
7. Workflow templates keep plan, apply, rollback, unlock, and destroy authorities explicit,
   source-bound, root-scoped, and inert.
8. `make check` passes from a temporary dedicated-root copy without credentials, backend access,
   external network, provider APIs, repository mutation, or mandatory skips after explicit setup.
9. The branch contains no state, saved plan, credential, secret value, authenticated artifact,
   executable cloud workflow, provider result, deployment, DNS change, or Live evidence.
10. Finance Assistant and every Integration Draft remain unchanged and inactive.

An unlocked provider, implicit registry access, reusable module with state ownership, cross-state
read, synthetic value accepted as deployable, default-apply Terraform test, workflow capable of
mutation, or operational claim fails AP-M7.

### Required evidence

The pull-request handoff records branch and AP-M6/governance merge base, evaluated and final
revisions, AP-M7 work-package commits and paths, Terraform and provider versions, lock digests,
toolchain checksums, setup and gate commands, working directory, duration, test totals and outcomes,
identifier and threat coverage, configuration examples, security/privacy impact, limitations, and
unresolved AP-M8 inputs. It confirms that evaluation used only mocked providers and an offline
filesystem mirror and that Finance Assistant remained unchanged.

Console output is sufficient. The branch commits no generated report, `.terraform/` directory,
provider binary, state, saved plan, credential, authenticated artifact, provider response, raw log,
or Live evidence bundle.

### Security and privacy impact

AP-M7 introduces configuration for resources that will later enforce identity, state, ingress,
routing, logging, and spend controls. Root isolation, typed references, secret-reference-only
inputs, plan policy, inert workflows, static tests, and exact locks reduce configuration and supply-
chain risk. Static success cannot prove IAM enforcement, key custody, direct-origin denial, session
persistence, provider retention, budget delivery, or recovery.

### Limitations and unresolved inputs

AP-M7 does not initialize or contact a backend, authenticate, plan against GCP, apply, configure
federation or GitHub environments, publish an image, upload a generation, create a resource, change
DNS or traffic, exercise a browser, perform provider readback, or collect Live evidence. Operator-
specific values remain unresolved until AP-M8 reviews them. Provider behavior, direct-origin
denial, identity custody, multi-instance effects, rollback, recovery, and cost remain AP-M9 evidence.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M7-W1 through AP-M7-W3 | AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-004, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-007 | AP-TM-003, AP-TM-007, AP-TM-008, AP-TM-010, AP-TM-011, AP-TM-014 |
| AP-M7-W4, AP-M7-W5 | AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-001 through AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-005, ADR-007 | AP-TM-003, AP-TM-004, AP-TM-008 through AP-TM-013 |
| AP-M7-W6, AP-M7-W7 | AP-PR-001 through AP-PR-005, AP-PR-007, AP-PR-008; AP-QR-001 through AP-QR-006 | ADR-001, ADR-002, ADR-005 through ADR-008 | AP-TM-001 through AP-TM-005, AP-TM-007 through AP-TM-013 |
| AP-M7-W8, AP-M7-W9 | AP-PR-001, AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-001 through AP-QR-006 | ADR-001, ADR-004, ADR-007 through ADR-009 | AP-TM-007 through AP-TM-013 |
| AP-M7-W10, AP-M7-W11 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 | AP-TM-001 through AP-TM-014 |

`AP-PR-006`, `AP-PR-009`, and `AP-TM-014` are negative constraints in AP-M7: infrastructure cannot
grant a Feature Entitlement, activate an Integration Draft, or claim Application Adoption.

## Historical AP-M8 · Manifest-driven qualification deployment — superseded

This section preserves the accepted AP-M8-W1/W2 record as it stood at source revision
`7b6678a7f0b3036d427517dad6bc3bec876d1a44`. Its references to an active W2 checkpoint and future
W3–W12 sequence are historical statements, not current instructions. AP-M9 is the only active
remaining delivery sequence.

### Authority status

AP-M8-W1 is complete, owner-accepted, and merged. It defines the bounded milestone, complete plan,
design refinements, threat controls, AP-EVAL-M8 gate, repository locations, deterministic
governance checks, and implementation handoff. AP-M8-W2 is the only active package. AP-M8-W3
through AP-M8-W12 remain unauthorized until W2's repository support merges and the owner accepts
one real manifest revision bound to that exact protected-main source.

Acceptance or merge of AP-M8-W1 still does not execute an operator action. Each later package has
its own explicit owner checkpoint, and any package that changes repository settings, cloud IAM,
state, provider resources, DNS, or traffic requires its named operator approval immediately before
the change. Discussion history, this branch name, an inert AP-M7 template, or a passing static gate
cannot supply that approval.

### Outcome

AP-M8 deploys the exact approved App Platform revision and the three synthetic Fixture
Applications into the named non-production qualification environment through protected,
source-bound operator procedures. It establishes independent Terraform backends, realizes only the
approved executable workflow authorities, applies the reviewed roots in an approved order, performs
the separately approved qualification-hostname DNS/TLS action, and produces redacted state,
provider, and resource readback for the exact source and configuration digests.

A passing AP-EVAL-M8 result means only that the named revision's approved resources exist in the
named environment, their state and provider inventories agree, and no unapproved resource changed.
That result is a deployment/readback record, not a fifth evidence class and not AP-M9 Live (`L`)
qualification. It does not qualify runtime routing, visitor identity, direct-origin denial,
assertion behavior, rollback execution, availability, cost behavior, or Application Adoption.

### Scope

AP-M8 includes, only after the required package approvals:

- one reviewed manifest of exact non-secret operator inputs, immutable source and configuration
  digests, and unresolved secret references;
- protected `comfforts/apps-platform` main-branch and environment controls, GitHub Actions OIDC,
  GCP Workload Identity Federation, and least-privilege operation identities;
- one-time backend bootstrap, temporary-state migration, state-lineage and recovery verification,
  and independent backend initialization for Platform State and each Fixture Application State;
- repository support for production composition, synthetic network fixtures, pinned images, a
  provider-backed qualification Registration Set, staged Platform deployment, and separately
  scoped plan, apply, publication, DNS, rollback, force-unlock, and destroy workflows without
  granting one operation another's authority;
- authenticated advisory and exact-main plans, explicit environment approval, source and plan
  digest binding, root-scoped concurrency, and same-job application of the reviewed plan;
- ordered deployment of the three Fixture Application roots and Platform State root, immutable
  Registration Generation and image bindings, dependency validation, and stop-on-partial-failure
  behavior;
- a separately approved `apps-staging.comfforts.com` DNS record and TLS-readiness checkpoint that
  changes no existing hostname;
- provider, state, IAM, resource, DNS/TLS, and approved-service readback with exact ownership and
  change-set reconciliation; and
- a redacted, revision-bound AP-EVAL-M8 record and truthful AP-M9 handoff.

AP-M8 excludes:

- AP-M9 runtime, browser, identity, direct-origin, assertion, failure-injection, rollback-timing,
  load, availability, cost-delivery, incident, drift-injection, or recovery qualification;
- a production environment, `apps.comfforts.com`, an existing DNS record, real application project,
  real restricted member, real application payload, or consuming-application resource;
- Finance Assistant code, configuration, identity, infrastructure, state, hostname, deployment,
  migration, access, integration activation, or Application Adoption;
- service-account keys, long-lived credentials, unprotected source, routine local apply, implicit
  provider discovery, cross-state reads, `terraform_remote_state`, automatic rollback, automatic
  force-unlock, state push, destroy, or automatic cleanup; and
- treating screenshots, browser state, raw provider output, Terraform state, saved plans,
  credentials, secrets, assertions, sessions, identities, or payloads as committed evidence.

The AP-M8-W1 authority branch itself may change only documentation and deterministic governance
tests. It must not change repository settings, create or use federation, initialize a backend, run
an authenticated plan, contact a provider, publish an image or generation, change DNS or traffic,
deploy a resource, execute recovery, collect Live evidence, or begin AP-M9.

### Dependencies and fixed inputs

| Dependency | Required state | AP-M8 treatment |
| --- | --- | --- |
| AP-M3 through AP-M7 | Merged and passing | Preserve Contract, Fixture, runtime, Terraform, workflow-template, and regression authority without reinterpreting static evidence as deployment proof |
| Canonical repository | Clean protected `main` in `comfforts/apps-platform` | Bind every later plan, approval, apply, and record to an exact merged source revision |
| Complete AP-M8-W1 authority | Owner-accepted and merged | Authorize only the named later package; no operator action inherits authority from this profile |
| Qualification environment | Fixed planning facts | Use project `comfforts-platform-non-prod` (`455651441682`), region `us-west1`, and hostname `apps-staging.comfforts.com`; never infer another environment |
| Operator inputs | Reviewed before their dependent package | Record exact values and digests without provider discovery, Finance-derived values, or invented defaults |
| Credentials and provider access | Unavailable through AP-M8-W2 | Later packages may use only approved short-lived identities within their exact operation boundary |
| AP-EVAL-M8 | Authority complete and accepted; result unavailable | Preserve deployment/readback claims, commands, fixtures, evidence, redaction, and pass/fail/skip semantics before mutation |
| AP-M9 and Application Adoption | Unavailable | Produce no Live qualification or consuming-application change |

The exact repository and owner numeric identifiers, protected workflow refs, subjects and
environment names, Workload Identity Federation pool/provider and operation identities, service-
account permission sets and IAM bindings, globally unique state/configuration/log/
evidence bucket names, managed DNS zone and record transaction, immutable edge and fixture image
digests, OAuth client and redirect registration, Secret Manager version references, billing-account
and notification references, reviewed Fixture Registration Set, restricted synthetic members, and
attachment resource references remain unresolved operator inputs. A missing value stops its
dependent package. It is not permission to query GCP, inspect an unrelated repository, copy a
Finance value, use a provider default, or weaken a gate.

### Work packages

#### AP-M8-W1 · Qualification-deployment authority

Define the complete AP-M8 plan, system-design refinements, threat controls, evaluation gate,
repository locations, governance checks, and operator handoff. This package changes only
documentation and deterministic tests. Owner acceptance and merge are prerequisites to every later
package; AP-M8-W1 creates no executable workflow or external mutation authority.

#### AP-M8-W2 · Operator-input manifest

Review one bounded, non-secret manifest that fixes the exact protected source, environment,
resource names, immutable digests, identity references, secret-version references, registration
inputs, backend prefixes, and evidence destination needed by later packages. Reject missing,
placeholder, synthetic-as-live, secret-bearing, mutable, cross-owner, discovered, or unapproved
values before an authenticated command runs.

The manifest is append-only rather than falsely complete before deployment facts exist. Its first
accepted revision records every then-known value. Image digests, state-lineage digests,
configuration-object generations, plan digests, and run identifiers enter only through immutable
successor revisions that name their predecessor and receive a fresh approval before use. The exact
protected-main source revision is recorded after merge; no commit is required to contain its own
future identifier.

Repository status: the closed Version 1 revision schema, deterministic local loader, canonical
digest, immutable-input comparison, predecessor-chain validation, explicitly synthetic example,
and security/governance regression checks are implemented on the W2 branch. This repository
implementation neither contains nor accepts the real operator manifest. After merge, one real
non-secret revision must be created in an owner-approved non-Git location, validated against the
exact merged source, and explicitly accepted by digest before W3 can begin.

#### Historical AP-M8-W3 · Protected repository and environment controls — superseded

Read back and preserve the extraction checkpoint-3 baseline: default protected `main`, no bypass,
force-push or deletion; pull requests, current-branch enforcement, `Credential-free project
checks`, CodeQL thresholds, full action pins, read-only default permissions, dependency and secret
controls, and the credential-free check workflow. A missing or weakened baseline control stops the
package.

Under a separate repository-setting approval, create only the reviewed plan, apply, DNS, Evidence,
and recovery GitHub Environment classes. Each accepts exact `main`, requires a fresh owner review
for every job, contains no secret, and produces the exact environment-bound OIDC subject. No
environment approval transfers to another class or operation. The
[qualification-deployment runbook](runbooks/qualification_deployment.md) owns the setting profile,
proposed-change table, readback fields, and stop conditions. AP-M8-W3 does not render or invoke an
operator workflow.

#### Historical AP-M8-W4 · Federation and operation identities — superseded

Under a separate cloud-IAM approval and one short-lived owner bootstrap credential, create one
dedicated qualification Workload Identity Pool/provider and only the reviewed root-operation
service accounts and impersonation bindings. Trust jointly binds the GitHub issuer, provider
audience, repository and owner names plus numeric identifiers, protected `main`, an allow-listed
workflow ref, one reviewed environment and matching subject, `workflow_dispatch`, and the exact run
SHA verified by the workflow.

Plan, apply, rollback, force-unlock, and destroy identities are distinct for every enabled root.
Artifact publish, generation publish, and qualification DNS also have distinct identities and
fixed targets, with no backend permission. Each root has a distinct readback identity, and one
finalizer identity can read only the exact evidence prefix and create its no-overwrite verdict.
Each receives only its exact state, owned-resource, repository, object, record, or evidence-prefix
permissions; unused exceptional identities have no binding. Workload identities cannot administer
federation, IAM, themselves, billing, another root, or an application.
Keys, wildcard subjects, broad primitive roles, credentials longer than one hour, implicit
credential sources, and name-only repository trust are prohibited. Readback must prove mappings,
conditions, key absence, impersonation principals, direct and inherited roles, and scopes before
the owner closes the package.

#### Historical AP-M8-W5 · Backend bootstrap and state lineage — superseded

First merge a repository-only implementation of
`infrastructure/backend/bootstrap-backend.tf.tmpl` and its credential-free deterministic renderer,
with tests proving that the AP-M7 root remains local for its initial apply and receives only the
reviewed declaration as `backend.tf` for migration. No authenticated action may begin before that
support passes the complete gate on protected `main`.

Under a later explicit operator approval, use one short-lived owner credential and one private
exact-source copy to plan and create only four reviewed private, versioned, recovery-bounded state
buckets. Five lineages use fixed prefixes: `bootstrap` and `platform` in the platform-state bucket,
plus one `fixtures/<application-id>` prefix in each fixture bucket. Conditional access must preserve
root separation even where the bucket is shared; a project-wide or cross-prefix fallback is
prohibited.

After bucket, policy, label, IAM, and empty-prefix readback succeeds, retain a restricted local
backup, render the reviewed backend declaration, and migrate bootstrap state while preserving
lineage, non-decreasing serial, providers, resource and instance inventories, and non-secret
references. Verify remote versioning, native locking, recovery inputs, and a no-change plan before
removing the active local copy. Initialize the four non-bootstrap roots one at a time without apply,
migration, dummy state, state push, or invented lineage; empty prefixes remain `not-created` until
AP-M8-W9. The [qualification-deployment runbook](runbooks/qualification_deployment.md) owns exact
prerequisites, invariants, records, and failure stops.

#### Historical AP-M8-W6 · Deployment support and executable workflow realization — superseded

First close the repository dependencies that AP-M7 deliberately left outside static Terraform:
implement and test the production Shared Edge composition entry point and pinned non-root image,
one networked synthetic Fixture runtime and pinned non-root image, and a reviewed provider-backed
qualification Registration Set using `gcp-cloud-run-v1`. Fixture registrations using
`fixture-in-process-v1` remain AP-M4 evidence and are not deployment inputs.

Add a Version 2 platform deployment configuration that selects `foundation` or `candidate` without
changing the single Platform State owner or lineage. Foundation creates configuration storage,
Artifact Registry, identities, KMS/Firestore, logging/evidence, and budget controls without an edge
image, generation object, or attachments. Candidate requires those exact immutable values, retains
foundation unchanged, and adds the Shared Edge/load-balancer/certificate resources. Version 1
remains accepted AP-M7 static evidence; update every Version 2 consumer and deterministic test
together.

Render only the separately approved root plan/apply, artifact-publish, generation-publish, DNS,
rollback, force-unlock, and destroy authorities into fixed executable workflows with exact action
pins, operation identities, environment protection, source binding, per-root concurrency where
applicable, no-overwrite publication, and secret-free outcome records. Realization does not invoke
a workflow, build or publish an image, contact a provider, or combine exceptional authorities.

#### Historical AP-M8-W7 · Authenticated plans and deployment preflight — superseded

Bind the exact protected-main revision to the accepted manifest; verify locked tools, actions, base
images, dependencies, existing APIs/billing, reviewed OAuth/secret/zone/notification references,
empty backends, bootstrap readback, and the initial provider-backed Registration Set. Run the exact
authenticated Platform-foundation plan, and review the expected-resource inventories and plan
policies for later roots without inventing not-yet-created dependency values. Each Fixture root and
the candidate receives its own fresh authenticated plan and approval only after its exact image,
platform-reference, attachment, and object-generation inputs exist. Reconcile the complete change
and ownership inventory and obtain explicit approval for the exact source, configuration,
expected-resource, and available redacted plan digests. Any drift, replacement, destroy, unknown
service, missing dependency, unapproved API enablement, provider default, Finance resource, or
unreviewed change stops deployment.

#### Historical AP-M8-W8 · Operation sequencing and failure authority — superseded

Approve the fixed initial order: Platform foundation; immutable image publication; platform-
reference validation; sequential public, authenticated, and restricted Fixture roots; provider-
backed generation compilation and create-only publication; Platform candidate; then the separately
approved DNS/TLS checkpoint. Each dependency enters an append-only manifest revision and each stage
has its own identity, approval, readback, and stop. Approve retry and owner decisions for rollback,
import, recovery, force-unlock, state push, destroy, or cleanup before mutation. No failure
automatically invokes a follow-on operation or changes a successful earlier root.

#### Historical AP-M8-W9 · Qualification resource deployment — superseded

Apply Platform foundation at the exact protected-main revision using a fresh same-job plan, then
create-only publish exact-source images. Apply the three Fixture roots sequentially with the actual
typed platform reference. Compile the reviewed provider-backed Registration Set from their actual
attachment references and create-only publish its immutable object. Finally, apply the Platform
candidate from a fresh same-job plan that preserves foundation and binds the exact image,
Registration Generation, object generation, and attachments. Candidate deployment changes no DNS,
qualifies no runtime behavior, and touches no real application.

The first Cloud Run service has no predecessor and may point 100 percent of service traffic to its
only revision while the hostname has no DNS. This is a dark initial candidate, not zero-percent
service traffic, a successor-generation activation, or Live evidence. Future pointer changes keep
ADR-008's separate activation authority.

#### Historical AP-M8-W10 · Qualification DNS and TLS checkpoint — superseded

After resource and ownership readback succeeds, require a distinct owner approval for the new
`apps-staging.comfforts.com` A record, its 1,800-second TTL, exact reserved IPv4 address,
authoritative and recursive readback, and managed-certificate readiness. The DNS identity changes
no AAAA, wildcard, zone, existing, production, or Finance record. Failure blocks AP-M9; a reversal
may change only the new qualification A record after a fresh approval. DNS/TLS readiness makes the
candidate reachable but leaves it deployed and not Live-qualified.

#### Historical AP-M8-W11 · Deployment readback and evidence — superseded

Use distinct root-scoped readback identities to reconcile the exact source, manifest chain,
configuration, plan, state-lineage, provider, IAM, resource, image, generation, traffic, DNS/TLS,
ownership, protection, label, budget, retention, and approved-service inventories. Each workflow
reduces temporary raw material to one schema-valid create-only record, scans prohibited data, and
hash-chains the record without reading another root. Produce the Version 1 AP-EVAL-M8 private
bundle under its exact source/evaluation prefix with owner-only access and 30-day retention;
discrepancies and failed operations remain explicit failures rather than omitted or skipped
evidence. Git may retain only the approved secret-free index or digest.

#### Historical AP-M8-W12 · Qualification-deployment gate and standalone-Live handoff — superseded

Use the dedicated Evidence identity to read only the exact bundle prefix, run the committed
credential-free final verifier in ephemeral storage, and create-only publish/read back the final
manifest, checksum file, and verdict. Derive the bundle digest from the checksum-file and verdict
digests. Run all ten AP-EVAL-M8 gates for one exact source/manifest chain and record actual pass,
fail, blocked, and skip outcomes, the causal failure, checksums, limitations, and unavailable later
claims. A pass requires complete unique records, agreeing inventories, successful prohibited-data
scans, zero failures/blocked gates/mandatory skips, and the expected verdict digest. Reconcile
truthful repository status only after that result; a passing result may route the next task to an
AP-M9 proposal after merge but may not claim Live qualification or authorize Application Adoption.

### Ordered delivery

AP-M8-W1 is owner-accepted and merged, and AP-M8-W2 is the only active package. After W2's
repository implementation merges and its exact real manifest revision is accepted, AP-M8-W3
through AP-M8-W12 proceed in order, each behind its named owner checkpoint. Work may be split
across separately approved branches and pull requests where the package changes a distinct
authority surface. A later package may not begin from an unmerged branch, fill a missing input,
reuse an earlier approval for a different operation, or continue past a failed checkpoint.

The three Fixture Application roots retain separate identities, backends, locks, plans, applies,
results, and stop boundaries and run sequentially for the initial deployment. The accepted order is
Platform foundation, image publication, platform-reference validation, public fixture,
authenticated fixture, restricted fixture, generation publication, Platform candidate, then the
separate DNS/TLS checkpoint. No provider tolerance or module internal can reorder that sequence.

### Acceptance criteria

AP-M8 is accepted only when all of the following are true:

1. AP-M8-W1's complete plan, design, threat controls, AP-EVAL-M8, repository locations, and
   governance checks were owner-accepted and merged before the first operator action.
2. Every operator value, immutable digest, target, expected change, identity, backend, and evidence
   destination is explicit, reviewed, and bound to the exact protected-main revision.
3. Repository and environment protections, federation conditions, and operation identities are
   no broader than their named source, root, environment, and action.
4. Bootstrap, Platform State, and every Fixture Application State retain independent lineage,
   locking, recovery, access, and exclusive ownership with typed non-secret reference exchange.
5. Plans are fresh, complete, reviewed, source- and digest-bound, root-scoped, and applied only in
   the same protected job after explicit environment approval.
6. Root ordering, immutable generation and image binding, dependency validation, partial-failure
   stops, and exceptional operation boundaries match the approved procedure.
7. The separately approved qualification DNS/TLS action changes only
   `apps-staging.comfforts.com` and passes its named readback checkpoint.
8. State, provider, IAM, resource, generation, traffic, DNS/TLS, ownership, and approved-service
   inventories agree, with every discrepancy reported.
9. AP-EVAL-M8 records actual outcomes in the approved redacted schema without committing or
   retaining prohibited operational data.
10. No result is called AP-M9 Live qualification, availability, cost proof, recovery proof,
    rollback proof, or Application Adoption.
11. Finance Assistant, every Integration Draft, all existing hostnames, and every real application
    remain unchanged and inactive.

### Security and privacy boundary

AP-M8 crosses from static configuration into protected repository, identity, state, provider, and
DNS control planes. Exact-source binding, least privilege, state isolation, explicit checkpoints,
stop-on-partial-failure behavior, and redacted readback reduce but do not eliminate those risks.
The evidence rules and AP-EVAL-M8 gate are accepted W1 authority. W2's deterministic manifest
contract and chain validation are repository implementation only; merge plus explicit acceptance
of the exact real manifest and digest still block AP-M8-W3.

No credential, token, assertion, session, restricted identity, application payload, state content,
saved plan, raw provider response, browser state, or unredacted log may enter Git or the retained
evidence record. Non-secret project numbers, resource references, source/configuration digests, and
coarse operation outcomes are not secrets but remain bounded to the approved record schema.

### Limitations and unresolved authority

The protected-control, backend, deployment-sequencing, and AP-EVAL-M8 profiles are accepted
planning authority, not implemented controls. AP-M8-W1 is owner-accepted and merged. AP-M8-W2 implements
only the local manifest contract and validator; no real manifest is committed or accepted by that
result. Until the exact post-merge revision is validated and owner-accepted, AP-M8-W3 through
AP-M8-W12 cannot start.

AP-M8 deployment cannot prove visitor or application behavior, direct-origin denial, real login,
assertion verification, load, availability, multi-instance behavior, rollback time, recovery,
incident response, cost delivery, or application compatibility. Those claims remain AP-M9 or
Application Adoption work even if all resources exist and read back correctly.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M8-W1, AP-M8-W2 | AP-PR-001 through AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-004, AP-QR-006 | ADR-001 through ADR-009 | AP-TM-007, AP-TM-008, AP-TM-010, AP-TM-011, AP-TM-014 |
| AP-M8-W3, AP-M8-W4 | AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003 through AP-QR-006 | ADR-001, ADR-004, ADR-007 | AP-TM-004, AP-TM-005, AP-TM-008 through AP-TM-011, AP-TM-014 |
| AP-M8-W5 through AP-M8-W10 | AP-PR-001 through AP-PR-005, AP-PR-007 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-005, ADR-007 through ADR-009 | AP-TM-001 through AP-TM-014 |
| AP-M8-W11, AP-M8-W12 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 | AP-TM-001 through AP-TM-014 |

`AP-PR-006`, `AP-PR-009`, and `AP-TM-014` are negative constraints throughout AP-M8: deployment
cannot grant a Feature Entitlement, activate an Integration Draft, or become Application Adoption.

## AP-M9 · Operator-driven environment lifecycle

### Authority status

AP-M9-W1 is merged and establishes the active operator-lifecycle authority. It supersedes the
unexecuted AP-M8-W3 through AP-M8-W12 packages and the previously proposed standalone AP-M9
Live-qualification milestone. The old proposal produced no implementation, provider resource,
evidence bundle, or qualification result. AP-M8-W1/W2 remain historical merged work; AP-M9-W2
removed their retired manifest implementation from the active tree, AP-M9-W3 implemented lifecycle
contracts and profiles, AP-M9-W4 implemented the credential-free interactive core, AP-M9-W5
implemented the deployable Terraform lifecycle, and AP-M9-W6 implemented interactive deployment
mechanics without running an external operation. AP-M9-W7 begins only after W6 merges.

Each AP-M9 repository package begins from updated clean `main`, uses a dedicated branch and pull
request, passes `make check`, and merges before the next package starts. Repository implementation
does not authorize an external operation. AP-M9-W9 operator actions each require their exact owner
approval from protected main after AP-M9-W1 through W8 are merged.

### Outcome

AP-M9 delivers one Python operator product that prepares, deploys, inspects, integrates, qualifies,
and safely destroys an isolated Platform Environment. It deploys and qualifies staging with
synthetic Fixture Applications, generates versioned application handoffs, supports reversible
detachment and terminal retirement, and prepares production ownership transfer without changing
the existing Finance-owned production deployment.

The normal operator interface is:

```text
platform-prepare  platform-deploy  platform-status  platform-outputs
platform-register platform-detach  platform-retire platform-qualify platform-destroy
```

The local wizard remains active through OAuth and Squarespace work and continues after Enter.
Rerunning is interruption recovery only. Generated execution facts are journal outputs rather than
operator-authored manifest fields.

### Scope and boundaries

AP-M9 includes:

- the governance clean break and removal of the retired manifest path;
- small non-secret staging and disabled production Environment Profiles;
- closed Deployment Specification, Execution Journal, status, Platform Integration Bundle, and
  Application Attachment Bundle contracts;
- one deep interactive Python lifecycle module with real and deterministic fake adapters;
- deployable bootstrap, platform-foundation, and Shared Edge Terraform phases;
- short-lived local operator authentication with operation-specific service-account
  impersonation, exact plans, typed confirmation, and readback;
- interactive OAuth/Secret Manager and external Squarespace DNS checkpoints;
- application registration, detach/reactivate, permanent retirement, and complete-generation
  activation;
- synthetic Fixture Application deployment, Live qualification, evidence, rollback, and safe
  platform destruction; and
- read-only production preparation and a Finance ownership-transfer handoff.

AP-M9 excludes:

- automatic Finance Assistant adoption, script mutation, state import, production cutover, or
  ownership transfer;
- implicit import or replacement of any existing `apps.comfforts.com` resource;
- application runtime, store, provider, secret, principal, or Feature Entitlement ownership;
- a service-account key, long-lived credential, secret payload in a prompt or bundle, routine broad
  owner apply, cross-state read, automatic rollback, automatic cleanup, or destructive recovery;
- a production availability commitment or staging evidence used as production qualification; and
- Python-to-Go migration, which remains a later contract-preserving milestone after the Python
  product is delivered and qualified.

### Work packages

#### AP-M9-W1 · Governance rebaseline

Define AP-PR-010 through AP-PR-012, AP-QR-007 through AP-QR-009, ADR-010 through ADR-013, canonical
vocabulary, the AP-M9 design and threat refinements, this plan, AP-EVAL-M9, active reading order,
repository layout, historical status, and deterministic governance checks. Preserve AP-M8-W1/W2 as
history and mark AP-M8-W3 through W12 and the old AP-M9 proposal superseded before execution. This
package changes documentation and tests only and authorizes no external action.

#### AP-M9-W2 · Retired manifest-path cleanup

Removed the operator-input-manifest schema, synthetic example, chain loader, command, exports,
manifest-specific tests, obsolete acceptance prompt, and inactive workflow assumptions that served
only the superseded path. Preserved reusable Terraform, runtime, fixture, contract, state, security,
and deterministic verification assets. Git history and the historical status record preserve the
removed implementation.

#### AP-M9-W3 · Lifecycle contracts and environment profiles

Implement small closed staging and disabled-production profiles plus versioned contracts for the
Deployment Specification, Execution Journal, Environment Status, Platform Integration Bundle, and
Application Attachment Bundle. Canonicalization and digest rules must be deterministic. Profiles
contain stable owner decisions only; generated or discoverable facts, credentials, secrets, state,
plans, and provider payloads are prohibited.

#### AP-M9-W4 · Interactive operator core

Implemented the deep Python lifecycle module and thin Make targets for credential-free preparation
and status. Injected Git, GitHub, GCP, Terraform, DNS, terminal, filesystem, and clock adapters;
provided deterministic fakes; validated clean source and tools; discovered non-secret facts;
compiled and explicitly approved one specification; journaled stages; reported truthful status;
and resumed interrupted fake journeys. This package performs no authenticated mutation.

#### AP-M9-W5 · Deployable Terraform lifecycle

Implemented bootstrap, platform-foundation, and Shared Edge phases that preserve exclusive
ownership and one platform lineage without placeholder inputs. Added exact staging backend
declarations and a path-bounded renderer, 31 keyless operation-authority intents, local
impersonation profiles, canonical plan policy, production refusal, closed phase outputs, mocked
plans, and deterministic command fakes. No authenticated plan, backend operation, provider
mutation, or DNS action occurred in the repository slice.

#### AP-M9-W6 · Interactive platform deployment

Implemented the staged deployment engine: preflight; backend/identity bootstrap; foundation; image
publication; OAuth branding/client/Secret Manager checkpoint; Shared Edge/load balancer/address;
Squarespace DNS checkpoint; DNS propagation and TLS readiness; readback; stop-on-discrepancy; and
resume. The same process displays exact manual values and waits for Enter. Every Terraform stage
binds a fresh private saved plan to W5 policy, redacted digest/summary, exact typed confirmation,
same-artifact apply, and readback. The closed non-fake subprocess boundary uses absolute executables,
argv, private bounded paths, closed environments, and operation identities without shell
interpolation. Deterministic command fakes and transcript tests cover success, no-change,
cancellation, manual checkpoint, bounded polling, partial failure, discrepancy, interruption, and
resume. The default local construction remains unarmed pending the W8 external-action safety gate;
the pull request executed no real operation.

#### AP-M9-W7 · Application integration lifecycle

Implement outputs, bundle validation, provider target readback, registration, complete-generation
activation, detachment, replacement attachment/reactivation, and terminal retirement. Public,
authenticated, and restricted applications receive only their required values. A detached route
returns a generic temporary-unavailability result; a retired route returns a generic permanent-
removal result; unknown routes remain closed. No operation destroys Application State.

#### AP-M9-W8 · Qualification and safe destruction

Implement networked synthetic Fixture Applications in separate Application State, `platform-
qualify`, closed evidence, failure injection, rollback, and `platform-destroy`. Qualification covers
DNS/TLS, catalogue, routing, admission, OAuth/session/logout, assertions/JWKS, attachment IAM,
direct-origin denial, isolation, streaming, lifecycle, limits, and redaction. Destruction refuses
active attachments, uses a separate specification and typed confirmation, respects DNS/rollback
windows, never destroys Application State, and retains backends/evidence absent a separate purge.

#### AP-M9-W9 · Staging deployment and qualification

From clean protected main, separately approve and run staging preparation, deployment, OAuth and
Squarespace checkpoints, fixture bundle generation, fixture deployment/registration, complete
AP-EVAL-M9, detach and destroy fixture assets, and an owner-approved platform destroy/redeploy
rehearsal. Leave staging deployed and qualified at the accepted revision. Commit only an approved
secret-free evidence index; no credential, secret, state, plan, raw provider response, browser
state, or application payload enters Git.

#### AP-M9-W10 · Production readiness and Finance handoff

Enable only read-only production preparation. Discover existing production ownership, return
`OWNERSHIP_TRANSFER_REQUIRED`, inventory future Platform versus Finance Application State, and
define the application-script change, state transfer or replacement, DNS/traffic cutover, rollback,
and evidence prerequisites. This package changes no production resource. Actual production
deployment is a later joint platform checkpoint plus Finance-owned Application Adoption.

### Ordered delivery and external-action gate

AP-M9-W1 through W8 are repository branches in order. No staging resource is created merely because
W6 contains deployment mechanics. W9 begins only after W8 is merged so registration, qualification,
detach, rollback, and safe destruction exist before the first provider mutation. W10 follows the
accepted staging result.

Within W9 the operator order is preparation and digest approval; shared-platform deployment; fixture
integration-bundle generation; fixture application deployment; attachment registration;
qualification; fixture detachment and application-owned cleanup; optional approved platform
destroy/redeploy rehearsal; final qualification; and evidence reconciliation. The first failed or
discrepant stage stops every dependent action.

### Acceptance criteria

AP-M9 is accepted only when:

1. AP-M9-W1 through W8 are merged in order and the complete deterministic gate passes.
2. A fresh operator can deploy staging from reviewed source through one interactive session.
3. OAuth and Squarespace actions use exact same-process Enter checkpoints and truthful readback or
   operator-attested status.
4. Preparation asks only genuine decisions and produces one complete approved specification.
5. Interruption resumes from the last closed stage without repeating a successful mutation.
6. Public, authenticated, and restricted fixtures consume real platform bundles, deploy in separate
   Application State, register, route, detach, redeploy, reactivate, and retain terminal retirement.
7. AP-EVAL-M9 passes for the exact staging revision with secret-free evidence.
8. Platform destruction refuses unsafe state, changes no application-owned resource, and passes its
   approved staging rehearsal.
9. Production preparation proves staging/production isolation and blocks on current Finance
   ownership rather than importing or mutating it.
10. `make check` remains deterministic, credential-free, network-free, and non-mutating.
11. Finance Assistant, `apps.comfforts.com`, and every real application remain unchanged pending
    their own adoption and production-cutover approvals.

### Trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M9-W1, AP-M9-W2 | AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-013 | AP-TM-007 through AP-TM-014 |
| AP-M9-W3, AP-M9-W4 | AP-PR-010 through AP-PR-012; AP-QR-003, AP-QR-004, AP-QR-006 through AP-QR-009 | ADR-010 through ADR-013 | AP-TM-001 through AP-TM-003, AP-TM-007 through AP-TM-014 |
| AP-M9-W5, AP-M9-W6 | AP-PR-001 through AP-PR-005, AP-PR-010; AP-QR-001 through AP-QR-009 | ADR-001, ADR-004 through ADR-011, ADR-013 | AP-TM-001 through AP-TM-014 |
| AP-M9-W7 | AP-PR-001 through AP-PR-007, AP-PR-009, AP-PR-011, AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-006, ADR-008, ADR-012, ADR-013 | AP-TM-001 through AP-TM-014 |
| AP-M9-W8, AP-M9-W9 | AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-013 | AP-TM-001 through AP-TM-014 |
| AP-M9-W10 | AP-PR-007, AP-PR-009 through AP-PR-012; AP-QR-001, AP-QR-003 through AP-QR-009 | ADR-001, ADR-002, ADR-004, ADR-007, ADR-010 through ADR-013 | AP-TM-007 through AP-TM-014 |

## Historical later delivery sequence

AP-M8 authorizes no later work by itself. Each item below requires a new owner-approved branch,
plan refinement, evaluation gate, merge, and clean-main handoff.

### Historical standalone Live qualification proposal — withdrawn before implementation

Execute the approved Live gates against the exact deployed revision and Registration Generation.
Exercise provider routing, identity, IAM, direct-origin denial, state ownership, failure isolation,
activation, rollback, logging, retention, drift, cost controls, and recovery. Store only approved
redacted evidence and obtain owner acceptance before calling the platform Live-qualified.

### Later Application Adoption

Only after AP-M9 is accepted may a consuming application propose adoption through its own
requirements, decisions, contracts, implementation, state transition, cutover, rollback, and
release authority. Finance Assistant remains unchanged until that independent process approves it.

### Ordered delivery

AP-M5 work proceeds in this order:

1. approve provider and attachment topology;
2. approve the identity and assertion trust profile;
3. approve state and operator authority;
4. approve activation, DNS, readback, and rollback behavior;
5. approve observability, evidence, incident, and cost controls;
6. approve the delivery plan and repository locations;
7. approve evaluation authority;
8. enforce the complete deterministic planning gate; and
9. reconcile truthful status and the next-slice handoff.

Each work package is a separate small commit reviewed before the next package is edited. A later
package may correct an inconsistency or complete traceability, but it may not add provider runtime,
Terraform, a workflow with live authority, a credential, or external mutation.

### Acceptance criteria

AP-M5 is accepted only when all of the following are true:

1. Every decision traces to AP-PR-001 through AP-PR-009, AP-QR-001 through AP-QR-006, ADR-001
   through ADR-009, and the applicable AP-TM-001 through AP-TM-014 boundary.
2. The design defines provider topology, attachment ownership, identity trust, state roots,
   operator authority, activation, DNS/TLS, readback, rollback, observability, incident response,
   cost control, retention, and later-slice boundaries without claiming implementation.
3. AP-M6, AP-M7, AP-M8, AP-M9, and Application Adoption are distinct review and merge boundaries;
   no later slice inherits mutation authority merely because AP-M5 is accepted.
4. Every selected cloud value remains environment configuration rather than a reusable contract or
   Finance-derived assumption.
5. Exact unresolved implementation inputs are named and block only their dependent later package;
   they are not silently filled from fixture code, provider defaults, or discussion history.
6. The default `make check` remains deterministic, credential-free, network-free, non-mutating,
   extraction-safe, and mandatory-skip-free.
7. The branch contains no provider runtime, Terraform configuration, workflow with cloud authority,
   state, saved plan, credential, secret, cloud call, DNS change, identity change, deployment, or
   generated Live evidence.
8. Finance Assistant and every existing application resource, state, hostname, identity, access
   rule, deployment, and integration package remain unchanged and inactive.
9. Status and handoff text call AP-M5 planning authority only and leave Contract, Fixture, Live,
   and Adoption evidence classes unchanged.

Near-complete documentation, a missing owner decision disguised as a default, a cloud lookup in the
default gate, or any operational claim fails AP-M5.

### Required evidence

The pull-request handoff records:

- branch, AP-M4 merge base, evaluated source revision, and final revision;
- one commit and changed-path list for every AP-M5 work package;
- exact verification command, working directory, interpreter version, duration, test count,
  failures, errors, warnings, and skips;
- requirements, ADRs, threats, and proposed later gates covered;
- security and privacy impact, limitations, and unresolved implementation inputs;
- confirmation that no `infrastructure/`, runtime, live registration, state, saved plan, credential,
  provider call, repository mutation, DNS action, deployment, or authenticated artifact was added;
  and
- confirmation that Finance Assistant and every Integration Draft remain unchanged and inactive.

This is planning evidence for review, not a new evidence class and not Live evidence. Console output
from the deterministic gate is sufficient; generated reports and screenshots are not committed.

### Security and privacy impact

AP-M5 reduces future ambiguity by selecting explicit trust, state, operation, retention, and cost
boundaries. It introduces no runtime data flow. It records project identifiers, resource-reference
grammar, and non-secret operational settings, but no real restricted membership, OAuth client,
credential, key, state, plan, log, IP address, assertion, provider response, or application data.

The selected controls remain declarations until later implementation and Live evidence prove them.
Their presence must not be used to weaken existing Finance Assistant access or justify migration.

### Limitations and unresolved inputs

AP-M5 does not prove that any cloud resource, identity, state backend, route, certificate, session,
assertion, log, alert, budget, rollback, or recovery behavior exists. It does not qualify latency,
availability, throughput, browser behavior, accessibility, or a real application.

The following exact inputs remain required at their named later boundary:

| Input | Required before |
| --- | --- |
| Exact protected workflow subjects, protected environment, and federation bindings for `comfforts/apps-platform` | AP-M8 operator-input review and deployment |
| Globally unique state, configuration, log, and evidence bucket names | AP-M8 operator-input review |
| DNS managed-zone resource and exact separately approved record transaction | AP-M8 operator-input review and DNS action |
| OAuth client identifiers, redirect registration, secret references, billing-account reference, and owner notification destination | AP-M8 operator-input review and deployment |
| Initial live Fixture Registration Set, restricted synthetic members, image digests, and attachment resource references | AP-M8 operator-input review and deployment |
| Application-specific principals, data, providers, entitlements, state transfer, and cutover | Each Application Adoption |

These are unavailable inputs, not permission to query a provider, copy Finance configuration, or
invent a value in AP-M5.

### Plan trace

| Work packages | Requirements | Decisions | Threats |
| --- | --- | --- | --- |
| AP-M5-W1 | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-002, AP-QR-003, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-005 | AP-TM-001 through AP-TM-004, AP-TM-007 through AP-TM-014 |
| AP-M5-W2 | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-003, ADR-004, ADR-005, ADR-006 | AP-TM-004 through AP-TM-006, AP-TM-009, AP-TM-010, AP-TM-013 |
| AP-M5-W3 | AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-007 | AP-TM-007 through AP-TM-014 |
| AP-M5-W4 | AP-PR-001 through AP-PR-005, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-008 | AP-TM-002 through AP-TM-005, AP-TM-007 through AP-TM-014 |
| AP-M5-W5 | AP-PR-001, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001 through ADR-004, ADR-009 | AP-TM-001, AP-TM-004, AP-TM-005, AP-TM-007 through AP-TM-014 |
| AP-M5-W6 through AP-M5-W9 | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 | AP-TM-001 through AP-TM-014 |
