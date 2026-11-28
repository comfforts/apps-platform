# ADR-017 · Exchange complete application attachment sets

Status: Accepted; repository contract and atomic operator behavior implemented by AP-M9-W12
Slices 2–3; not deployed or qualified

Requirements: AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-009, AP-PR-011, AP-PR-012,
AP-QR-001 through AP-QR-004, AP-QR-006 through AP-QR-009

Amends: ADR-012 where its singular Application Attachment Bundle and registration intent cannot
represent an application with more than one independently deployed target. ADR-012's remaining
cross-owner bundle, digest, validation, and ownership decisions stay accepted.

## Context

The Version 2 Registration Set already models one application with multiple attachments and the
Shared Edge already selects the longest segment-bounded mount. The Version 2 cross-owner handoff
does not expose that depth: one Application Attachment Bundle carries one target and one
registration intent carries one attachment identifier, mount, and forwarding mode. A real
application such as a separately deployed frontend and backend therefore cannot describe its
complete runtime boundary without inventing a second application, hiding one service behind the
other, or changing the qualified Version 2 meaning in place.

Two registrations would split one product's route, lifecycle, admission, identity audience, and
catalogue entry. Requiring the frontend to proxy every backend request would add an application
runtime hop only to compensate for a shallow platform interface. Revising Version 2 in place would
break its closed-object contract after Accepted Source qualification.

## Decision

AP-M9-W12 introduces Version 3 of the three-document application-handoff interface. One Platform
Integration Bundle remains scoped to one application, connected project, Platform Environment,
Admission Mode, Identity Delivery policy, platform source revision, and Registration Generation.
Its attachment contract declares that one root attachment is required and at most fifteen
additional attachments are supported.

The Version 3 Application Attachment Bundle preserves the required singular `target` as the root
attachment and adds an optional `additional_attachments` attribute. When present, that array
contains between one and fifteen entries sorted by stable unique `attachment_id`; each entry owns
one additional target and its posture. Omitting the attribute is a valid root-only handoff.

The Version 3 registration intent preserves the required root `attachment_id`, `mount_path`, and
`forwarding_mode`, requires the root mount to be `/`, and adds an optional
`additional_attachment_bindings` attribute. When present, that array is sorted by
`attachment_id` and owns each additional attachment's mount and forwarding mode. The two optional
arrays must either both be absent or contain the exact same unique identifier set. The root ID
must not appear in either optional array. Duplicate identifiers, duplicate or ambiguous mounts, a
missing or extra binding, an unsupported forwarding mode, or a partially returned optional set
fails closed. Total cardinality remains one through sixteen.

All attachments in the initial Version 3 handoff share the application-level project, region,
Shared VPC connection, application owner, edge-caller identity, Admission Mode, Identity Delivery
policy, and assertion audience. Each target is nevertheless read back independently for its exact
Cloud Run service, internal ingress, Direct VPC egress, readiness, ownership labels, invoker grant,
and identity-audience posture. Per-attachment admission, identity delivery, audience, project,
region, or network policy is outside this decision and requires separate authority.

The application-handoff module is the ownership seam. Its Version 3 interface is plural, while the
Cloud Run provider adapter remains target-specific. `platform-register` must validate the complete
relationship and read back every target before compiling or publishing anything. One failed or
stale target prevents the whole application update; no subset may activate. After validation, an
adapter projects the Version 3 handoff into the existing Version 2 Application Registration,
whose `attachments` array already supports the required cardinality, and activates one complete
Version 2 Registration Generation. Handoff and compiled-generation major versions are independent
interfaces and do not advance merely to keep their numbers equal.

Version 2 handoff documents remain readable and supported for the already qualified single-target
fixtures. One registration invocation accepts either a complete same-version Version 2 family or
a complete same-version Version 3 family and never a mixture. A Version 3 root-only family is also
valid, so existing fixtures can adopt the new specification without inventing a second service.
Version 3 is required when an application returns an additional attachment. The existing Version 2
Registration Set, Compiled Shared Edge, Verified Identity Context, and State Ownership Manifest
meanings remain unchanged.

An active application update always returns the required root attachment and, when any additional
attachment is desired, the complete `additional_attachments` and
`additional_attachment_bindings` arrays including every unchanged entry. Removing one additional
attachment is therefore an explicit full-optional-set registration change rather than a missing
partial document. A replaced or removed target remains available for the accepted
rollback-retention window. `platform-detach` continues to suspend the whole application; it is not
a per-attachment lifecycle.

For a frontend/backend application, the expected shape is one stable application route whose
required root target is the frontend and whose optional `additional_attachments` contains a
backend bound at a more specific path such as `/api`. Longest segment-bounded mount selection
sends `/api` traffic to the backend and all other application-relative traffic to the root target.
These identifiers and mounts are application choices, not Finance Assistant values embedded in
reusable platform behavior.

## Considered alternatives

- **Register the frontend and backend as separate applications:** rejected because one product
  would gain two catalogue, route, lifecycle, admission, and identity boundaries.
- **Require the frontend to proxy the backend:** rejected as a mandatory platform workaround; an
  application may still choose a backend-for-frontend architecture under its own authority.
- **Add a second Version 2 document per target:** rejected because independent documents could
  activate incompletely and would change the qualified Version 2 relationship semantics.
- **Change the core registration family to Version 3 at the same time:** rejected because its
  existing multi-attachment interface already has the needed depth and a number-only version bump
  would add migration without changing meaning.
- **Allow per-attachment identity or project policy immediately:** rejected because it expands the
  trust and ownership model beyond the first real-application adoption.

## Consequences

- One application can attach separately deployed frontend and backend Cloud Run services without
  transferring either runtime or state to the platform.
- The cross-owner interface becomes deep enough to represent the existing registration model, at
  the cost of a new handoff schema family, compatibility loading, vectors, validation, operator
  changes, provider readback aggregation, and deterministic tests in AP-M9-W12.
- Root-only Version 3 handoffs remain valid. AP-M9-W12 adds a fourth
  `fixture-multi-attachment` application while leaving `fixture-public`,
  `fixture-authenticated`, and `fixture-restricted` unchanged. The fourth fixture uses
  authenticated admission with required Identity Delivery, an unlisted catalogue entry, a
  required `web` frontend at `/`, and an optional `api` dummy backend at `/api`.
- One independent Fixture Application State root owns both services of the fourth fixture. A
  fixture-scoped qualification interface records its own source-bound result and status; it does
  not rerun, replace, or broaden the platform-wide qualification result.
- Atomic validation and activation prevent a frontend-only or backend-only generation from
  becoming current.
- Existing fixtures and their qualified Version 2 handoffs remain truthful compatibility
  evidence; they do not qualify Version 3 or a multi-attachment application.
- Acceptance of this decision creates no schema, bundle, registration, target readback, provider
  operation, application deployment, route, or Application Adoption evidence.
