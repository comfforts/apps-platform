# App Platform contracts

Version 1 | Scope: repository-owned machine interfaces and deterministic validation; no operation
authority

Status: Version 1 remains implemented and readable as predecessor behavior. The accepted next
contract family is Version 2, which adds explicit Identity Delivery and moves restricted membership
out of registrations and generations into an environment-wide platform member directory. No
Version 2 schema is operational until its implementation slice adds the complete family, migration,
consumers, and deterministic tests.

The `contracts/` directory defines the versioned data exchanged between platform components,
operators, and applications. It answers four questions:

- what data the platform accepts;
- what a compiler, runtime, or operator workflow may produce;
- how documents are validated, canonicalized, versioned, and digest-bound; and
- how invalid or incompatible data fails closed.

Contracts describe data, not actions. Loading a schema or validating a document does not provision
a resource, approve or execute an operation, activate a registration, verify a live signature, or
qualify runtime behavior. The contracts are authoritative only inside App Platform and remain
subordinate to the product requirements, accepted architecture decisions, and system design.

## Directory map

| Path | Purpose |
| --- | --- |
| `schemas/` | Registration, attachment, compiled-edge, identity, and ownership schemas |
| `validation.py` | Bounded JSON loader, local schema registry, canonical JSON, semantic validator, and deterministic registration compiler |
| `test-vectors/` | Reviewed valid and invalid examples for the platform/application contract family |
| `lifecycle/schemas/` | Environment profile, destructive-operation, handoff, and qualification-evidence schemas |
| `lifecycle/validation.py` | Lifecycle loader, canonical digests, prohibited-data checks, and cross-document relationship validation |
| `lifecycle/test-vectors/` | Synthetic, non-secret examples for the operator lifecycle and handoff family |

Both families use closed JSON objects, stable local URNs, bounded input, deterministic validation,
and the same canonical JSON rules. They have separate registries so an operator document cannot be
mistaken for a registration or runtime document.

## Platform and application contract inventory

| Schema | Stable identifier | Interface |
| --- | --- | --- |
| `schemas/registration-set.v1.schema.json` | `urn:comfforts:app-platform:schema:registration-set:v1` | Complete reviewed application registrations for one immutable generation |
| `schemas/application-attachment.v1.schema.json` | `urn:comfforts:app-platform:schema:application-attachment:v1` | Application-owned target reference and Shared Edge handoff requirements |
| `schemas/compiled-shared-edge.v1.schema.json` | `urn:comfforts:app-platform:schema:compiled-shared-edge:v1` | Deterministic catalogue, route, admission, attachment, and lifecycle projection consumed by the Shared Edge |
| `schemas/verified-identity-context.v1.schema.json` | `urn:comfforts:app-platform:schema:verified-identity-context:v1` | Minimal signed visitor-identity claims delivered to an authenticated or restricted application |
| `schemas/state-ownership-manifest.v1.schema.json` | `urn:comfforts:app-platform:schema:state-ownership-manifest:v1` | Exclusive platform/application resource-owner declaration for a generation |

The local schema registry is exactly the identifier-to-path mapping in this table. A validator must
resolve these URNs from the project checkout and must fail rather than fetch an unknown or remote
reference.

The compiler-only platform-configuration input uses the definition at
`urn:comfforts:app-platform:schema:registration-set:v1#/$defs/platformConfiguration`. It selects
enabled attachment adapter kinds but is not part of an Application Registration and cannot add a
route, admission policy, or provider command.

## Operator lifecycle and application handoff inventory

| Schema | Stable identifier | Interface |
| --- | --- | --- |
| `lifecycle/schemas/environment-profile.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:environment-profile:v1` | Stable reviewed decisions for one isolated staging or production environment |
| `lifecycle/schemas/deployment-specification.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:deployment-specification:v1` | Separately confirmed destructive scope, ordered steps, and retained-resource boundary |
| `lifecycle/schemas/platform-integration-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:platform-integration-bundle:v1` | Application- and project-scoped non-secret platform, Shared VPC, identity, and attachment values required before an application deploys its target |
| `lifecycle/schemas/application-attachment-bundle.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:application-attachment-bundle:v1` | Application-owned target project, network, ingress, IAM, and audience posture bound to the exact integration bundle it consumed |
| `lifecycle/schemas/qualification-evidence.v1.schema.json` | `urn:comfforts:app-platform:lifecycle:qualification-evidence:v1` | Redacted, revision-bound results for evaluated platform and fixture behavior |

[`lifecycle/`](lifecycle/README.md) is a separate local registry for the Environment Profile,
destructive Deployment Specification, Platform Integration Bundle, Application Attachment Bundle,
and Qualification Evidence. Preparation, status, and resume progress are private operator state,
not cross-owner contracts. The registry reuses the bounded JSON Schema
interpreter but does not widen the platform/application registry above or the separate
infrastructure-configuration registry. Its canonical digests and cross-document validation are
repository behavior only; they perform no prompt, approval, credential, provider, Terraform, DNS,
deployment, application operation, or qualification probe.

## Authority and precedence

Conflicts are resolved in this order:

1. product requirements;
2. accepted architecture decisions;
3. system design;
4. this contract index and the Version 1 schemas in both local registries;
5. implementation plan and evaluation strategy; and
6. test vectors, prompts, and evidence.

The implementation plan governs delivery but cannot change a field meaning defined by the system
design or these reviewed schemas. A contract change updates every consumer, vector, test, and
authority reference in the same reviewed slice.

An external application's paths, provider details, state, identity configuration, and migration
intent are never platform contract sources and do not specialize these generic interfaces.

## Versioning

Each instance carries contract_version with the integer value 1. The filename suffix and schema URN
use v1 for the same major version.

Before the first accepted Live qualification and Application Adoption, an owner-approved incompatible
correction may revise Version 1 in place only when every repository consumer, vector, test, and
authority reference changes atomically and no released external consumer exists. This repository
is still in that pre-accepted-qualification, pre-Adoption condition; candidate staging operation
does not release a public application contract.

After the first Live deployment or Application Adoption, Version 1 is strict. Removing a field,
adding a required field, adding a property that an existing closed-object consumer would reject,
changing a field meaning, narrowing an accepted value, changing canonicalization, changing digest
semantics, or adding an enum value requires a new major schema and contract_version. Documentation
corrections that do not change machine behavior may retain Version 1.

Registration generation and registration_revision are data revisions, not contract versions:

- generation advances the complete Registration Set;
- registration_revision advances one existing Application Registration when a registered value
  changes; and
- contract_version changes only when the machine interface changes.

Application code, image, dependency, data, provider, or Feature Entitlement releases do not advance
registration_revision when every registered value and attachment reference remains unchanged.

## JSON and schema profile

Instances are UTF-8 JSON without a byte-order mark. Duplicate object keys, invalid Unicode scalar
values, floating-point numbers, and values outside the schema bounds are invalid.

The standard-library validators support only this reviewed JSON Schema Draft 2020-12 profile:

- $schema, $id, $ref, and $defs;
- type, const, enum, oneOf, properties, required, and additionalProperties;
- items, minItems, maxItems, and uniqueItems;
- minLength, maxLength, and pattern; and
- minimum and maximum.

A schema using another keyword fails the local schema-profile check until this authority and the
validator are reviewed together. Annotation keywords title and description do not affect
acceptance.

The Shared Edge runtime applies this same bounded, duplicate-safe JSON profile to generation bytes
before validating the compiled Shared Edge schema. It accepts only the exact configured object
generation, content digest, and compiled generation digest. The accepted generation exclusively
derives its escaped catalogue, reserved paths, active route selection, attachment mount, and
rewrite. This consumer does not compile a Registration Set, follow a mutable source, resolve an
attachment, or activate a provider revision while loading configuration.

All cross-schema references are stable URNs from the local registry. Remote references and
repository-external paths are prohibited.

## Canonical JSON and digests

App Platform Canonical JSON Version 1 uses these rules:

- output is UTF-8 without a byte-order mark or insignificant whitespace;
- object keys are schema-known ASCII names emitted in ascending byte order;
- strings preserve their Unicode scalar values and use JSON escaping only for quotation mark,
  reverse solidus, and required control characters;
- integers use base-10 form without a leading plus sign or leading zero;
- null, true, and false use lowercase JSON literals; and
- arrays whose schema represents a set are sorted by the field named in that schema's description;
  other arrays preserve their contract-defined order.

The compiler first canonicalizes a valid Registration Set. Its generation digest is the lowercase
SHA-256 digest of those canonical bytes, prefixed with sha256:. The digest is returned in both the
Compiled Shared Edge Configuration and State Ownership Manifest. The next Registration Set places
that value in previous_generation_digest. Generation 1 uses null.

The compiled configuration and ownership manifest are independently canonicalized for comparison,
but their bytes are not used as the predecessor digest. No timestamp, current user, absolute path,
random value, environment field, or provider lookup participates in canonical output.

## Compiler interface

The reference interface accepts:

- an optional preceding valid Registration Set and its calculated generation digest;
- one proposed complete Registration Set; and
- bounded platform configuration containing enabled attachment adapter kinds.

It returns either:

- one complete Compiled Shared Edge Configuration, one complete State Ownership Manifest, and the
  calculated generation digest; or
- an ordered collection of violations and no compiled output.

The interface is pure. It reads no credentials, network, DNS, provider, Terraform state,
application-owned file, clock, or random source, and it exposes no file-writing interface.

`adapter_kind` is a deliberate bounded extension point. The schema admits only canonical lowercase
kind names and inert URN resource references; the compiler rejects any kind not enabled by reviewed
platform configuration. `contract-test-v1` exists solely to exercise contract shape and compiler
semantics and is not a Fixture Application, network adapter, or provider implementation. Enabling
another kind requires its own approved design, implementation, and evidence; changing attachment
fields or their meaning requires a new contract major version.

The deterministic fixture harness enables `fixture-in-process-v1` only inside process-local tests.
Its exact resource-reference form is
`urn:comfforts:app-platform:fixture:<application-id>:<attachment-id>`. The compiler verifies that
the identifiers in the reference match the owning registration and attachment; activation then
requires an exact target in the explicitly supplied in-memory adapter map. The reference performs
no import, fetch, provider discovery, or credential lookup. This adapter adds no Version 1 field or
provider behavior and is not evidence for a live attachment.

## Violation semantics

Each violation contains a stable code and an RFC 6901 JSON Pointer to the rejected value or nearest
owning object. Human-readable text may improve without changing the code meaning. Violations are
ordered by pointer and then code.

Version 1 reserves these codes:

| Code | Meaning |
| --- | --- |
| JSON_INVALID | Input is not valid bounded JSON |
| JSON_DUPLICATE_KEY | An object repeats a key |
| SCHEMA_PROFILE_INVALID | A schema uses an unsupported or unresolved construct |
| CONTRACT_VERSION_UNSUPPORTED | An instance uses another contract major version |
| FIELD_REQUIRED | A required field is absent |
| FIELD_UNKNOWN | A closed object contains an unknown field |
| FIELD_TYPE | A value has the wrong JSON type |
| FIELD_BOUNDS | A string, integer, object, or array exceeds its bounds |
| FIELD_PATTERN | A string violates its canonical grammar |
| GENERATION_INVALID | Generation numbering or predecessor digest is invalid |
| APPLICATION_ID_CONFLICT | Application identifiers are duplicated or changed illegally |
| ROUTE_INVALID | A route or mount is not canonical |
| ROUTE_RESERVED | A route conflicts with a platform-reserved path |
| ROUTE_CONFLICT | Routes or mounts are ambiguous or duplicated |
| CATALOGUE_INVALID | Catalogue metadata or projection is unsafe or inconsistent |
| ADMISSION_INVALID | Admission policy is incomplete or inconsistent |
| IDENTITY_INVALID | Identity requirements, membership, or audience are invalid |
| ATTACHMENT_INVALID | An attachment kind, reference, owner, or setting is invalid |
| ATTACHMENT_CONFLICT | Attachment identifiers or bindings conflict |
| LIFECYCLE_TRANSITION_INVALID | A registration transition is not permitted |
| OWNER_CONFLICT | A resource reference has inconsistent or multiple owners |

A validator may report more than one independent violation, but it must never emit compiled output
when any violation exists. Adding or changing a violation meaning is a contract change.

## Security and privacy

Contracts and examples contain no credential, key, OAuth secret, signed assertion, real Platform
Member record or directory listing, provider payload, application data, Terraform state address, saved plan, authenticated
artifact, or unredacted external payload. Attachment references are inert non-secret URNs.

Catalogue data is the only public projection. Registration Sets, identity policy, attachment
references, identity contexts, ownership manifests, compiler violations, and compiled configuration
are restricted configuration unless a later authority explicitly proves a safe narrower view.

The identity schema defines claims, not signature verification. The attachment schema declares
shared-edge-only ingress, not proof of ingress enforcement. Those controls require Fixture and Live
evidence.

## Unsupported behavior

Version 1 contracts do not define:

- a provider-specific attachment or resource lookup;
- a live catalogue or route adapter;
- identity-provider configuration, algorithms, keys, rotation, or replay protection;
- cloud projects, regions, DNS, TLS, IAM, OAuth, state backends, or Terraform;
- runtime health, logging, cost, availability, or rollback procedures; or
- a real application's registration, migration, or Application Adoption procedure.

Version 1 also cannot express public optional Platform Identity or the accepted environment-wide
member directory. Its per-registration restricted member set is retained only for predecessor
readability and migration; it must not be copied into Version 2 or treated as current product
authority.

Absence from the schema is prohibition, not an extension point.
