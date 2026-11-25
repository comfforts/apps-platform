# ADR-012 · Exchange versioned non-secret bundles across platform and application ownership

Status: Accepted; identity-delivery projection is under review for reserved ADR-015

Requirements: AP-PR-002, AP-PR-007, AP-PR-009, AP-PR-011, AP-PR-012, AP-QR-001 through AP-QR-004,
AP-QR-006, AP-QR-008, AP-QR-009

This record is extracted from the
[origin architecture decision record](000-origin-architecture-decision-records.md). Until ADR-015
is recorded and accepted, the decision below remains current.

## Context

Applications require environment-specific platform values before they can deploy an eligible
runtime, while the platform cannot know the application-owned attachment until that deployment
finishes. Reading another Terraform state or sharing a hand-maintained configuration would couple
the owners and weaken provenance.

## Decision

The platform produces one Platform Integration Bundle for a named application, environment, access
mode, and platform revision. The application consumes it under its own authority and returns an
Application Attachment Bundle bound to the exact platform-bundle digest. Both bundles are closed,
versioned, canonical, non-secret contracts.

The platform bundle contains only values the application needs, such as hostname, login/logout
endpoints when applicable, assertion issuer, JWKS URI, application audience, edge-caller identity,
attachment contract, and qualification status. An OAuth client identifier appears only when the
consumer interface requires it. The platform-owned OAuth client secret never appears as a value or
application-readable secret reference.

Registration validates the returned bundle, target metadata, owner, ingress, caller grant,
audience, and current platform-bundle digest before activation. Neither bundle grants state access
or transfers resource ownership.

The repository-owned fixture operator may persist an exact canonical bundle pair in ignored private
operator state after deploying and reading back one fixture but before registration. It exposes the
two paths and digests for inspection. A later end-to-end fixture deployment may reuse the pair only
after revalidating its complete source, platform-generation, image, digest, relationship, and live
target bindings; otherwise it regenerates the handoff through the normal lifecycle.

## Consequences

- Applications can deploy and destroy independently using an explicit platform contract.
- Bundle digests expose stale handoffs without coupling either owner to another backend.
- Optional fixture inspection does not activate a route, weaken registration validation, or make a
  prepared bundle an authority record.
- Application Adoption remains application-owned and cannot be inferred from bundle generation.
