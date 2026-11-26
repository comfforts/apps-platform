# Shared Edge runtime

The Shared Edge is the platform-owned ASGI ingress boundary. It serves the platform catalogue and
identity endpoints, selects one registered application route, enforces platform admission, resolves
the exact application attachment, and forwards the request within fixed limits. It does not deploy
applications, compile registration generations, or administer the platform member directory.

The repository runtime can load and enforce both Version 1 and Version 2 compiled generations.
Version 1 remains the deployed compatibility predecessor until the operator and qualification
slices deliberately publish and activate a Version 2 generation. Repository implementation alone
does not prove that a Version 2 runtime is deployed or qualified.

## Component boundary

The Shared Edge owns:

- loading one immutable, digest-bound compiled generation at process startup;
- rendering the catalogue and serving the reserved platform endpoints;
- selecting the longest matching active application route and attachment;
- establishing Google identity through the platform OAuth client and an opaque Platform Session;
- enforcing Version 1 compatibility admission or the explicit Version 2 admission matrix;
- looking up only the current visitor when a Version 2 restricted route requires membership;
- corroborating a registered Cloud Run attachment against current provider metadata and IAM;
- issuing a short-lived, application-bound identity assertion when identity delivery requires it;
- forwarding bounded HTTP, streaming, and WebSocket traffic; and
- emitting allowlisted completion events and a coarse operator-only status document.

The Shared Edge does not own:

- application runtime or Application State deployment and destruction;
- registration compilation, generation publication, or generation activation;
- platform-member enrollment, lifecycle mutation, listing, or search;
- application users, roles, feature entitlements, or account linking;
- DNS, certificates, project IAM, or other infrastructure provisioning; or
- provider credentials, secret values, Terraform state, or operator journals.

Those boundaries prevent an application attachment or identity assertion from becoming authority
for a platform or application lifecycle operation.

## Request path

For each request or WebSocket connection, the runtime follows this order:

1. Bound the method, path, query, headers, body or message size, concurrency, and rate.
2. Use the one compiled generation loaded and validated at startup. The runtime never falls back to
   a different object generation or target.
3. Handle an exact reserved platform path, or select the longest matching active application route.
4. Resolve the existing Platform Session when the selected admission and identity-delivery policy
   calls for it.
5. For a Version 2 restricted route, derive the opaque member reference and read exactly that
   current visitor record from the named member database.
6. Resolve the registered Cloud Run resource and corroborate its readiness, ownership labels,
   audience, canonical URI, and exact edge-caller invocation grant.
7. Issue an application-bound assertion only when the selected policy calls for identity delivery.
8. Remove visitor-supplied platform identity and routing headers, add platform-owned values, and
   proxy to the resolved attachment with a short-lived edge-caller identity token.
9. Record a minimized completion event containing only allowlisted operational fields.

A missing, malformed, suspended, or unavailable member record denies a restricted request with the
same visitor-facing result. Provider detail is retained only as an allowlisted diagnostic code.
Public and authenticated Version 2 routes do not consult the member directory.

## Reserved endpoints

| Path | Behavior |
| --- | --- |
| `/` | Render the active application catalogue from the bound generation. |
| `/_platform/login` | Start a bounded Google OIDC authorization-code flow with PKCE. |
| `/_platform/auth/callback` | Validate the callback and create an opaque server-side Platform Session. |
| `/_platform/logout` | Delete the current Platform Session and clear its cookie. |
| `/_platform/status` | Return coarse runtime and adapter health only to the exact configured operator identity. |
| `/.well-known/jwks.json` | Publish the bounded public keys used to verify platform assertions. |

Unknown reserved paths return `404`. Suspended and retired application routes retain their route
reservation but return their lifecycle-specific closed response instead of reaching an attachment.

## Admission and identity delivery

Version 1 remains readable so an immutable predecessor generation can continue operating during the
transition. Its restricted policy uses the member material embedded in that generation, and its
identity behavior remains the compatibility behavior defined by the Version 1 contracts.

Version 2 separates route admission from identity delivery:

| Admission mode | Identity delivery | Runtime behavior |
| --- | --- | --- |
| `public` | `none` | Admit anonymously, skip Platform Session lookup, and issue no platform assertion. |
| `public` | `optional` | Admit anonymously; issue an assertion only when a valid, deliberate Platform Session exists. |
| `authenticated` | `required` | Require a valid Platform Session and issue an assertion; do not consult membership. |
| `restricted` | `required` | Require a valid Platform Session and an active current-member record, then issue an assertion. |

The Version 2 assertion contains only its contract version, issuer, opaque Google subject, exact
application audience, issue and expiry times, and correlation identifier. A successful restricted
lookup may add the positive projection `platform_member: true`. It never contains email, profile
data, a member reference, a directory record, roles, feature permissions, or entitlements.

The assertion is delivered through `X-Comfforts-Verified-Identity`. The proxy always strips any
visitor-supplied value for that header before forwarding. Applications must independently verify
the signature, issuer, audience, and time bounds. `edge/verification.py` is currently the Version 1
application-side compatibility verifier; Version 2 application-consumer migration belongs to the
later application-handoff slice and is not implied by this runtime implementation.

## Sessions and member lookup

The identity flow uses Google OIDC authorization code plus PKCE. The browser receives only opaque,
secure, host-only cookies. Login-flow records expire after ten minutes and Platform Sessions expire
after eight hours. Google access and refresh tokens are not retained as session data.

Live composition stores Platform Sessions in the default Firestore database. Version 2 restricted
admission reads member records from the separate named `app-platform-members` database. The member
reference is deterministically derived from the environment, canonical Google issuer, and opaque
Google subject; the raw identity is not used as a document identifier. The runtime adapter supports
only an exact current-record read. Its production identity receives no enumerate or mutation
authority.

Suspending or removing a platform member affects the next request or newly established stream. The runtime
does not terminate a request or stream that was already admitted.

## Attachment and proxy enforcement

The active generation carries an inert, exact Cloud Run resource reference rather than a trusted
target URL. Before forwarding, the attachment resolver reads current provider metadata and verifies:

- the exact project number, region, and service name;
- service readiness and a canonical `run.app` URI;
- the application-owner and state-owner labels;
- the configured identity audience; and
- an unconditional `roles/run.invoker` grant to the dedicated edge-caller principal.

The proxy obtains a short-lived identity token through the dedicated edge-caller service account.
It removes hop-by-hop headers, authorization, host and forwarding headers, platform cookies,
correlation headers, and platform identity headers before constructing the upstream request. Request
and response bodies, streams, WebSocket messages, timeouts, concurrent work, login starts, and
per-client or per-instance rates are bounded by `ProxyLimits`. A deployment may lower those limits
but cannot raise them above the qualification profile compiled into the runtime.

## Live process composition

`edge.live:create_live_app` is the Uvicorn factory used by the Shared Edge container. It composes:

- Cloud Storage for the exact compiled-generation object version;
- the default Firestore database for login flows and Platform Sessions;
- the named Firestore database for exact current-member lookup;
- Google OIDC discovery and token exchange;
- Cloud Run service and IAM readback;
- Cloud KMS signing and public-key publication;
- an exact Secret Manager OAuth-client-secret version;
- bounded HTTP and WebSocket transports; and
- isolated JSON-line completion logging.

The process requires the following non-secret bindings or secret reference. A missing or invalid
value stops startup with a constant safe error code:

| Environment variable | Binding |
| --- | --- |
| `APP_PLATFORM_SOURCE_REVISION` | Exact repository revision represented by the runtime image. |
| `APP_PLATFORM_ENVIRONMENT` | Platform environment used to scope member references and runtime state. |
| `APP_PLATFORM_PROJECT_ID` / `APP_PLATFORM_PROJECT_NUMBER` | Exact platform provider project identity. |
| `APP_PLATFORM_REGION` | Runtime, KMS, and attachment region. |
| `APP_PLATFORM_ISSUER` | Exact HTTPS platform assertion issuer and external origin. |
| `APP_PLATFORM_CONFIGURATION_BUCKET` | Bucket containing the immutable compiled generation. |
| `APP_PLATFORM_CONFIGURATION_OBJECT` | Exact compiled-generation object name. |
| `APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION` | Immutable provider object generation number. |
| `APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST` | Digest of the stored object bytes. |
| `APP_PLATFORM_GENERATION_DIGEST` | Logical compiled-generation digest. |
| `APP_PLATFORM_IDENTITY_CLIENT_ID` | Platform Google OAuth client identifier. |
| `APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION` | Exact Secret Manager version reference, never the secret value. |
| `APP_PLATFORM_SIGNING_KEY_VERSION` | Exact Cloud KMS assertion-signing key version. |
| `APP_PLATFORM_EDGE_CALLER_PRINCIPAL` | Dedicated application-invocation service account. |
| `APP_PLATFORM_OPERATOR_ISSUER` / `APP_PLATFORM_OPERATOR_SUBJECT` | Exact identity authorized for runtime status. |

The container runs as a non-root user. Provider clients and credentials are constructed only in the
live composition boundary; importing the package or constructing the deterministic runtime opens no
listener and performs no external operation.

## Module map

| Module | Responsibility |
| --- | --- |
| `edge/__init__.py` | Small public import surface for runtime construction and application verification. |
| `edge/_runtime.py` | ASGI endpoints, admission sequencing, member lookup, assertion delivery, and forwarding orchestration. |
| `edge/_generation.py` | Exact immutable Version 1 or Version 2 compiled-generation loading and validation. |
| `edge/_routing.py` | Catalogue projection, reserved-path handling, route selection, and forwarding-path derivation. |
| `edge/_identity.py` | Google OIDC, opaque login-flow and session models, clocks, and identity stores. |
| `edge/_assertions.py` | Versioned ES256 assertion issuance, KMS signing, and public-key publication. |
| `edge/_attachments.py` | Strict Cloud Run resource parsing and provider-backed attachment corroboration. |
| `edge/_proxy.py` | Bounded HTTP, stream, and WebSocket forwarding plus edge-caller token acquisition. |
| `edge/_observability.py` | Correlation identifiers, completion-event allowlist, adapter health, and operator status. |
| `edge/live.py` | Production provider composition and immutable environment parsing. |
| `edge/verification.py` | Version 1 application-side assertion verification compatibility helper. |

`infrastructure/member_directory.py` supplies the shared member model, opaque-reference derivation,
deterministic fake, and provider-backed exact lookup used by the runtime. Member lifecycle mutation
belongs to the operator component, not to `edge/`.

Modules prefixed with `_` are internal implementation details. Prefer the exports from
`edge/__init__.py` in repository consumers.

## Deterministic construction and verification

Tests construct the runtime with `create_app(RuntimeConfiguration(...), RuntimeAdapters(...))` and
inject clocks, token sources, generation sources, identity stores, member lookup, attachment
metadata, signing, proxy, and observability adapters. This is the supported credential-free seam;
tests must not discover provider state or contact external services.

Use these repository checks from the project root:

```console
make runtime-check
make check
```

The focused runtime coverage is primarily in:

- `tests/test_edge_runtime.py` for generation binding, admission, identity delivery, and fail-closed
  behavior;
- `tests/test_live_runtime.py` for production configuration and provider composition;
- `tests/test_member_directory.py` for member-reference and exact-read boundaries;
- `tests/test_proxy.py` for forwarding, header, rate, size, timeout, and stream limits;
- `tests/test_observability.py` for minimized events and operator-only status; and
- `tests/test_runtime_qualification.py` for the complete deterministic runtime journey.

When changing this component, update the applicable public contracts and every consumer in the same
bounded slice. New adapters, diagnostics, headers, or provider fields must remain explicit,
allowlisted, and deterministically tested. Keep this guide and the affected module documentation in
sync with the complete current implementation.
