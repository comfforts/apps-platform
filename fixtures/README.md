# Fixture Applications

The `fixtures/` package contains synthetic applications used to verify that Apps Platform treats an
application as an independently owned contract consumer. Fixtures exercise application handoff,
network attachment, routing, identity delivery, lifecycle, rollback, and failure isolation without
standing in for a real application or weakening the platform/application ownership boundary.

A Fixture Application owns its runtime, image, Terraform state, and synthetic behavior. The
platform owns the Shared Edge, route registration, admission decision, Platform Session, Platform
Member Directory, and the application-bound assertion it forwards. A fixture never reads Platform
State, lists platform members, receives an OAuth secret, or grants a real product entitlement.

## Current architecture

There are two deliberately different fixture layers:

| Layer | Files | Purpose |
| --- | --- | --- |
| Networked fixtures | `networked.py` plus the independent Terraform roots under `infrastructure/terraform/fixtures/` | Current cross-project application runtimes used by the operator handoff and staging qualification journeys |
| Deterministic reference harness | `applications.py`, `identity.py`, `reference_edge.py`, and `registrations/` | Historical in-process Version 1 contract and lifecycle regression evidence; it opens no socket and is not the deployed Shared Edge or the current Version 2 handoff path |

The networked layer is the application-side boundary for current work. One immutable fixture image
selects exactly one profile from environment variables and exposes a small Starlette application.
The platform operator deploys each profile through an independent Terraform root in the dedicated
fixture application project. The application project is attached to the platform Shared VPC, but
its state and resources remain Application State.

`create_environment_app()` is the image entry point. It loads the closed non-secret environment
configuration, constructs an independent `ApplicationIdentityVerifier` when Identity Delivery is
enabled, and returns the ASGI application. `create_network_fixture()` is the deterministic
construction seam used by repository tests. The fixture image packages only `contracts/`,
`edge/`, and `fixtures/`; a hermetic startup test constructs the application from that exact
package set so an accidental dependency on platform-owned `infrastructure/` code fails before a
provider-backed rollout.

## Fixture profiles

| Application ID | Admission Mode | Identity Delivery | Expected application behavior |
| --- | --- | --- | --- |
| `fixture-public` | `public` | `none` or `optional` | `none` accepts anonymous requests and receives no platform assertion. `optional` still accepts anonymous requests and independently verifies an assertion when a visitor deliberately establishes Platform Identity. |
| `fixture-authenticated` | `authenticated` | `required` | Requires and independently verifies Platform Identity. Platform Membership is irrelevant. |
| `fixture-restricted` | `restricted` | `required` | Receives requests only after the Shared Edge verifies Platform Identity and current active Platform Membership; the fixture still independently verifies the resulting assertion. |
| `fixture-multi-attachment` | `authenticated` | `required` | Uses one application identity and audience across distinct `web` and `api` targets, each returning only its safe target marker after independent assertion verification. |

Admission is not application feature authorization. A `fixture-ready` response proves only that
the request reached the synthetic runtime under the selected platform policy. The fixtures contain
no real user database, provider authorization, product role, or Feature Entitlement.

### Multi-attachment fixture

W12 adds a fourth `fixture-multi-attachment` profile. It uses authenticated admission, required
Identity Delivery, unlisted catalogue visibility, and one independent Fixture Application State
root. That root owns a `fixture-multi-attachment-web` frontend Cloud Run service returned as the
required `web` attachment at `/` and a distinct `fixture-multi-attachment-api` dummy backend
returned as the optional `api` attachment at `/api`. Both services independently verify the same
application audience and expose distinct safe `web` and `api` markers. The existing three profiles
and their Version 2 handoffs remain unchanged.

The runtime, Terraform root, Version 3 handoff, status, destruction behavior, and separate
fixture-scoped qualification interface are implemented and deterministically tested. No provider
operation or Live qualification occurred in this implementation slice. A separately authorized
provider-backed result is produced by `fixture-qualify`, never by `platform-qualify`; neither
result replaces the other.

## Application handoff lifecycle

Fixtures use the same cross-owner sequence expected of an external application:

1. `application-handoff-check` verifies platform, application-project, Shared VPC, service, and
   requested Admission Mode/Identity Delivery readiness without publishing a bundle.
2. `platform-outputs` writes one application-scoped Version 2 Platform Integration Bundle for an
   existing single-target fixture or the explicit Version 3 bundle for `fixture-multi-attachment`.
3. `fixture-handoff` consumes that bundle, reconciles only the selected fixture's Application
   State, requires the explicit `listed` or `unlisted` catalogue choice, and writes the bound
   same-version Application Attachment Bundle and registration intent.
   The route is still inactive.
4. The operator inspects the three canonical documents and invokes `platform-register`.
5. Registration validates the complete same-version family, reads back every target, compiles one
   immutable complete generation, and atomically activates it at the Shared Edge.
6. `fixture-status` reports the active `listed` or `unlisted` catalogue policy and reports aggregate
   and per-attachment target posture separately from route readiness. Detachment precedes
   `fixture-destroy`; registration recovery and reactivation remain platform operations.
7. After the plural fixture is active, `fixture-qualify` independently binds the accepted platform
   result, exact Version 3 family, both targets, and active Version 2 generation; it neither reruns
   the three-fixture suite nor exercises Platform Member lifecycle or platform rollback.

The fixture helper exists so real application repositories can copy the ownership pattern, not so
Apps Platform can deploy real applications. A real application owns its equivalent deploy, status,
and destroy commands.

## Runtime configuration and surfaces

The networked image requires these non-secret variables:

- `APP_PLATFORM_APPLICATION_ID` — one of the four implemented exact fixture IDs;
- `APP_PLATFORM_ADMISSION_MODE` — the matching `public`, `authenticated`, or `restricted` mode;
- `APP_PLATFORM_ISSUER` — the exact environment issuer ending in `/_platform`;
- `APP_PLATFORM_PUBLIC_KEY_REFERENCE` — the matching platform JWKS URL; and
- `APP_PLATFORM_ASSERTION_AUDIENCE` — omitted for public `none`, present with the exact
  application audience for public `optional`, authenticated, or restricted delivery; and
- `APP_PLATFORM_TARGET_MARKER` — required as `web` or `api` only for the corresponding
  `fixture-multi-attachment` service and prohibited for the three existing fixture profiles.

The runtime exposes only bounded qualification surfaces:

- `GET /healthz` for target health;
- `GET /` and `GET /api` for ordinary delivery;
- `POST /upload` for request-stream handling;
- `GET /stream` for SSE-like streaming behavior;
- `GET /failure` for application failure isolation;
- `GET /qualification/browser` for a challenge-bound loopback callback carrying only the fixture
  identifier, one-use challenge, and whether identity delivery was observed; enabled identity is
  counted only after verification, while a disabled public fixture reports any prohibited header
  presence so public-`none` qualification fails closed. The multi-attachment profile additionally
  returns its allowlisted `web` or `api` marker; only its web target accepts the closed
  `GET /apix/qualification/browser` observation used to prove segment-bounded root selection; and
- `/socket` for WebSocket admission and delivery.

Unknown paths return the fixture's fixed not-found response. Responses contain only the fixture ID
and a coarse outcome. Identity rejection logs contain an allowlisted constant diagnostic code and
never an assertion, subject, email, token, session, request parameter, or payload.

## Identity verification boundary

When Identity Delivery is enabled, the fixture accepts at most one platform identity header and
passes it to the independent application verifier. The verifier validates the Version 1 or Version
2 contract, ES256 signature, platform issuer, application-specific audience, lifetime, and clock
bounds using the platform's public JWKS. A Version 2 positive `platform_member: true` claim may be
observed by the application, but it is not a role or entitlement and the application never receives
the directory or another member.

Public `optional` accepts a missing assertion. Every required profile fails closed on a missing or
invalid assertion. JWKS retrieval is HTTPS-only, bounded, does not follow redirects, and retries
one transient HTTP failure. The platform remains responsible for stripping visitor-supplied
identity headers before forwarding; the fixture's independent verification prevents a forwarded
forgery from becoming an Application Principal.

## Verification and limitations

Focused behavior lives in `tests/test_networked_fixtures.py`; contract and operator suites cover
bundle relationships, target posture, immutable generation activation, and fixture lifecycle. Run
the repository-wide credential-free gate with `make check`.

Deterministic fixture tests are Contract or Fixture evidence only. They do not prove a deployed
provider resource, DNS/TLS, direct-origin isolation, live IAM, member data, production readiness,
Version 2 activation, or adoption by a real application. The existing W9 staging fixtures remain
Version 1 predecessor evidence until the separately governed operator
qualification journey described in the
[environment lifecycle runbook](../docs/runbooks/environment_lifecycle.md).
