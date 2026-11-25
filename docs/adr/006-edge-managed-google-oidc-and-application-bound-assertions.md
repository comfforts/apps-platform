# ADR-006 · Use edge-managed Google OIDC and application-bound ES256 assertions

Status: Accepted; admission membership and identity-delivery clauses amended by ADR-015

Requirements: AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008, AP-QR-002, AP-QR-004,
AP-QR-005, AP-QR-006

This record is extracted from the
[origin architecture decision record](000-origin-architecture-decision-records.md). ADR-015 is
authoritative for Platform Member Directory admission and explicit public identity delivery; the
remaining trust, session, assertion, signing, and verification decisions stay accepted.

## Context

Admission Modes require one consistent authentication boundary at the Shared Edge, while
applications retain their own principals and Feature Entitlements. Existing applications may use
IAP or browser libraries such as `@react-oauth/google`, but trusting those independent mechanisms
inside the platform would create multiple identity authorities, inconsistent logout, and
application-controlled claims at a shared boundary.

The edge caller's workload identity and the Visitor's identity answer different questions. Cloud
Run IAM proves which workload invoked an application target; a signed platform assertion proves
which Visitor, if any, passed platform admission. Neither may substitute for the other.

## Decision

The initial Live identity provider is Google OIDC. The Shared Edge owns the authorization-code flow
with PKCE, provider-token validation, redirect and failure behavior, Platform Sessions, and logout.
Only identities with a valid Google issuer and immutable subject are authenticated. Consumer Google
accounts and Google Workspace accounts are eligible; no other OIDC provider is accepted initially.
The platform requires no MFA claim in the first qualification profile.

The browser receives only an opaque, host-only session cookie with `Secure`, `HttpOnly`,
`SameSite=Lax`, and `Path=/`. Minimal server-side session state is stored in Firestore Native in the
qualification project and region. A Platform Session has an absolute lifetime of eight hours and
cannot be silently extended beyond that boundary; expiry requires Google reauthentication. The
platform stores no Google access token or refresh token because it does not call Google APIs on a
Visitor's behalf. OAuth client secrets and transient verification material remain outside Git and
Terraform state.

A public registration receives no Platform Identity by default. It may explicitly select optional
identity delivery; only then may a valid Platform Session produce an assertion, while absence of a
session never prevents public admission or invents an identity. Authenticated and restricted routes
require identity delivery and a valid session. Restricted admission additionally performs a current
exact issuer-and-subject lookup in the environment's Platform Member Directory. Email may be
retained only as transient display metadata at the session or enrollment boundary; it is not an
admission key, membership key, assertion claim, Application Principal, or resource-ownership key.

Logout is a platform-reserved operation reachable from the root hostname and from application
paths. It deletes the server-side Platform Session, clears the cookie, and returns only to a
validated platform-relative location. It does not promise to sign the Visitor out of the global
Google account. Invalid or expired sessions fail protected admission and are never forwarded as
Verified Identity Context.

After admission, the Shared Edge removes every visitor-supplied
`X-Comfforts-Verified-Identity` value and issues a new application-bound assertion. One signer
serves the qualification environment, but every protected attachment retains its distinct
`urn:comfforts:app-platform:audience:<application-id>` audience. The signer uses a software-protected
Cloud KMS `EC_SIGN_P256_SHA256` key in `us-west1`; the assertion envelope identifies `ES256` and a
specific key version. Private signing material is non-exportable and only public verification
material is published at the platform-reserved `/.well-known/jwks.json` path.

Assertions have a maximum lifetime of 60 seconds and verifiers allow at most 30 seconds of clock
skew. The edge issues a new assertion for each forwarded request or newly established streaming
connection. Admission changes take effect at the next request or connection as required by
ADR-003; an assertion does not promise mid-connection revocation.

The signing key rotates at least every 90 days. A new public key is published before it becomes the
active signer, exactly one version signs new assertions, and the preceding public key remains
available for a 24-hour verification overlap. Applications may cache the published key set for at
most 15 minutes and may refresh once when an unknown key identifier is observed; inability to
obtain valid, non-stale verification material fails closed.

The demo environment does not claim distributed replay prevention. Correlation identifiers remain
unique, assertions remain short-lived and audience-bound, and applications may add a bounded local
replay check, but no platform-wide replay store or guarantee exists until separately implemented
and qualified.

## Considered alternatives

- **Use provider-managed IAP as the platform admission system:** rejected for the initial platform
  because per-application policy and provider headers do not supply one registration-derived
  session, logout, and assertion boundary for all Admission Modes.
- **Trust each application's client-side Google login:** rejected because an application-controlled
  token flow cannot become the Shared Edge's Verified Identity Context and would fragment session
  and failure behavior.
- **Share an HMAC secret with every application:** rejected because verification would also grant
  assertion-signing capability and make rotation a multi-application secret-distribution event.
- **Use one signing key per application immediately:** rejected because application-specific
  audiences already prevent cross-application use while one environment signer reduces demo-scale
  key and rotation overhead.
- **Require distributed replay storage initially:** deferred because the short assertion boundary
  and non-production risk do not justify a new shared availability dependency without measured
  need.

## Consequences

- Applications migrated to the platform must trust only the platform assertion for platform-route
  identity; current IAP and `@react-oauth/google` behavior remains unchanged until each Application
  Adoption explicitly replaces or isolates it.
- A compromise of the environment signer affects every application in that environment, while
  application-specific audiences limit assertion reuse rather than signer blast radius.
- Firestore session availability, Platform Member Directory availability for restricted routes,
  and KMS/JWKS availability become protected-admission dependencies. They fail closed at their
  dependency boundary without blocking anonymous use of a public route.
- Cloud Run IAM caller authentication remains mandatory and separate from Visitor assertions.
- This decision selects the trust profile only. It creates no OAuth client, session database, key,
  secret, IAM binding, runtime, or Live evidence.
