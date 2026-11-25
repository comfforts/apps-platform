# ADR-003 · Platform admission does not grant application feature access

Status: Accepted; admission membership and identity-delivery clauses are under review for reserved
ADR-015

Requirements: AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008, AP-QR-002

This record is extracted from the
[origin architecture decision record](000-origin-architecture-decision-records.md). Until ADR-015
is recorded and accepted, the decision below remains current.

## Context

Requiring one owner allow-list for an entire application conflates two different questions: whether
a request may reach the application and whether that person may use a restricted application
feature. This would unnecessarily block otherwise available functionality and would make the
platform responsible for product-specific provider plans, rights, and authorization rules.

## Decision

The Shared Edge makes an Admission Decision using the Admission Mode in the Application
Registration:

- **Public:** a request may reach the application without authentication; verified identity context
  is not guaranteed.
- **Authenticated:** any identity successfully authenticated by the configured identity boundary may
  reach the application.
- **Restricted:** only an authenticated identity included by the registration's admission policy may
  reach the application. Owner-only access is one restricted policy configuration.

Catalogue visibility is separate from Admission Mode. Being listed does not grant admission, and
being admitted does not grant a Feature Entitlement.

When authentication occurs, the platform supplies minimal Verified Identity Context through a
versioned, verifiable contract. An application derives its own immutable Application Principal from
the verified issuer and subject. Email addresses are display or contact attributes and must not be
used as application resource-ownership keys. Anonymous requests, forwarded user input, and unsigned
or unverified identity headers are not verified identity context.

The Application Owner defines and enforces every Feature Entitlement, including provider-plan and
data-display restrictions. The platform neither interprets those entitlements nor maintains a
cross-application entitlement database. An authenticated person may therefore be admitted to an
application, use its unrestricted functionality, and still be denied a restricted feature such as
live market data.

Admission-policy revocation applies at the next request or new streaming-connection boundary. The
platform does not promise to terminate an already established connection unless a future contract
explicitly requires and qualifies that behavior. Feature-entitlement revocation remains an
application responsibility.

The identity provider, authentication mechanism, identity assertion format, signature validation,
and application-principal derivation contract remain system-design and contract decisions.

## Considered alternatives

- **Restrict every application to one owner allow-list:** rejected because users without restricted
  feature permission may still be allowed to use the rest of an application.
- **Centralize application feature entitlements in the platform:** rejected because provider rights,
  product roles, and application data are outside the platform ownership boundary.
- **Use email addresses as shared resource-owner identifiers:** rejected because addresses are
  mutable attributes and do not form an immutable, application-scoped principal.
- **Let applications trust forwarded identity headers without an edge contract:** rejected because
  direct or spoofed requests could impersonate an authenticated identity.

## Consequences

- Fixture qualification must distinguish public, authenticated, and restricted admission.
- A fixture must prove that an admitted identity can use an unrestricted feature while the fixture
  application denies that identity a market-data-style Feature Entitlement.
- Anonymous access to a public application cannot imply an Application Principal.
- Applications must implement their own principal mapping, data isolation, feature authorization,
  and entitlement revocation.
- Expanding Finance Assistant from owner-only admission remains a future Finance Assistant change;
  this decision does not alter its current access policy.
