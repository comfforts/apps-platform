# <u>App Platform system design</u>

Version 1.20 | Status: ADR-015 accepted; AP-M9-W9 Candidate Qualification is Version 1 predecessor
evidence, and all seven AP-M9-W10 slices and candidate-readiness corrections are integrated without
a Live Version 2 qualification

This document defines the smallest logical design that can support the App Platform requirements
and accepted architecture decisions. It is authoritative only inside the App Platform project. It
does not provision infrastructure, activate an application, qualify runtime behavior, or change a
consuming application.

Requirements: AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009

Decisions: ADR-001 through ADR-015

## <u>Design outcome</u>

The platform has one configuration seam: a complete, versioned Registration Set is validated and
compiled into one immutable Shared Edge configuration. The compiler has no deployment side effects.
Platform membership is environment-scoped operational data and never enters that generation.
Future provider adapters may consume only a successfully compiled generation; they may not read
application state, invent routes, copy the Platform Member Directory, or treat manual edge
configuration as another authority.

The design separates three kinds of work:

1. **Offline contract work:** validate registrations, lifecycle transitions, route isolation,
   catalogue safety, admission policy, attachment references, and exclusive ownership; then produce
   deterministic compiled output or ordered violations.
2. **Shared Edge operation:** a future platform-owned adapter realizes a reviewed compiled
   generation as hostname-level catalogue, routing, TLS, and admission behavior.
3. **Application operation:** an Application Owner supplies compatible attachments and retains its
   runtime, data, identity mapping, feature authorization, providers, and Application State.

AP-M3 implements the first kind, and AP-M4 implements and Fixture-qualifies the deterministic
in-process form of the second and third kinds. This revision selects the initial provider topology
for infrastructure planning. It does not implement a provider adapter, Terraform configuration,
cloud resource, DNS change, deployment, or Live qualification.

## <u>Logical topology</u>

```text
                         reviewed Registration Set
                                     |
                                     v
                         +------------------------+
                         | Registration Compiler  |
                         | validate + derive      |
                         +------------------------+
                           |                    |
                 violations                    v
                                      immutable compiled generation
                                                   |
                                         future provider adapter
                                                   |
     Visitor ------> configured hostname ------> Shared Edge
                                                   |  |  |
                                                   |  |  +--> closed default
                                                   |  +-----> derived catalogue
                                                   +--------> admitted route
                                                                  |
                                                        Application Attachment
                                                                  |
                                                     application-owned runtime
```

The configured hostname, cloud project, region, identity provider, and provider-adapter settings
are deployment configuration. They are never embedded in reusable contracts or derived from the
containing Finance Assistant repository.

### Initial Live qualification topology

The initial Live environment is the dedicated non-production GCP project
`comfforts-platform-non-prod` (project number `455651441682`). Regional services are located in
`us-west1`; the global load balancer remains a global resource. The first hostname is
`apps-staging.comfforts.com`. Neither the environment nor its qualification procedure may read,
import, mutate, or destroy Finance Assistant edge resources, DNS, Terraform state, identity, or
deployment.

```text
 Visitor
    |
    | HTTP redirect / HTTPS, SSE, WebSocket, upload, download
    v
 global external Application Load Balancer
    |  reserved address + Google-managed certificate
    |  one serverless backend; no application-prefix routes
    v
 Cloud Run Shared Edge (us-west1)
    |  catalogue + prefix routing + admission + assertion + target selection
    |  dedicated edge caller
    v
 gcp-cloud-run-v1 typed attachment
    |
    v
 application-owned Cloud Run service
```

The provider URL map performs only hostname-level forwarding and HTTP-to-HTTPS behavior. It sends
all application traffic to one edge service, so the active Registration Generation remains the
only application-routing authority. The initial profile has no CDN or WAF. Exact request, response,
streaming, concurrency, timeout, and scaling limits belong to the later approved infrastructure
profile and Live gate.

The desired DNS record is platform-owned configuration, but record creation and cutover are an
explicit, separately approved operator action. A Google-managed certificate covers the hostname,
not application prefixes. No application attachment needs a separate client-facing DNS name or
certificate, and this planning decision does not create either the record or certificate.

## <u>Modules and seams</u>

### Registration Compiler

The Registration Compiler is an in-process, deterministic module. Its interface accepts:

- the last reviewed Registration Generation, when one exists;
- one proposed complete Registration Set; and
- validated platform configuration containing the enabled allow-listed attachment adapter kinds.

It returns exactly one of:

- a canonical Compiled Shared Edge Configuration and State Ownership Manifest; or
- a stable, ordered collection of validation violations with machine-readable codes and paths.

The compiler performs no network, filesystem mutation, cloud lookup, DNS lookup, credential access,
or provider discovery. The same input bytes and compiler version produce the same canonical output
bytes and digest. A caller cannot request partial compilation or bypass a failed rule.

The complete set, rather than an individual registration, is the validation scope because prefix
uniqueness, reserved paths, attachment ownership, and catalogue derivation are cross-registration
properties. The compiler interface is also the deterministic test surface.

The [Version 1 contract index](../contracts/README.md), schemas, canonical serialization rules,
violation codes, and reviewed vectors now own the machine interface described here. They implement
offline Contract evidence only; a runtime or provider adapter cannot fill a later authority gap.

### Shared Edge

The Shared Edge is the future platform-owned module at the configured hostname. Its interface is a
reviewed Compiled Shared Edge Configuration. It owns only:

- hostname-level DNS intent and its explicit operator procedure;
- hostname-level addresses, TLS, HTTP-to-HTTPS behavior, forwarding, and load balancing;
- the root catalogue and platform operational paths;
- registration-derived routes and edge-only attachment resources;
- application admission at the request or new streaming-connection boundary; and
- closed behavior for unknown, malformed, suspended, and retired routes.

It does not own application runtimes, application endpoints, data, secrets, provider integrations,
Application Principals, Feature Entitlements, or product behavior. A future provider adapter must
apply one whole compiled generation and preserve or restore the Last Reviewed Working Configuration
on failure. Applying that behavior is not part of this documentation slice.

### Application Attachment

An Application Attachment is the only seam from the Shared Edge to an application-owned runtime.
An Application Registration supplies one or more versioned attachment references. Each reference
contains only the information necessary to select an allow-listed adapter and bind an application
subpath to an application-owned target. It is data, not executable configuration.

An attachment reference must include an immutable application identifier, a registration-local
attachment identifier, an adapter kind, a non-secret resource reference, a canonical mount path, a
forwarding mode, and its identity requirement. It must not contain credentials, secret payloads,
arbitrary provider commands, Terraform state addresses, or catalogue content.

Application State owns the target runtime and every access policy attached to that runtime.
Platform State may own edge-only connector resources and may publish a versioned caller-principal or
audience reference for the Application Owner to consume. Neither state may create, update, import,
or delete a resource owned by the other. A resource reference grants no state access and transfers
no ownership.

Protected attachments must accept traffic only through the Shared Edge using both network or
provider admission controls and verified application-side identity validation. A signed identity
header alone is not permission to expose a public origin. The exact provider adapter and live
direct-bypass qualification belong to later slices.

### GCP Cloud Run attachment profile

The first provider adapter kind is `gcp-cloud-run-v1`. Its resource reference is inert data with
the exact grammar
`urn:comfforts:app-platform:gcp:cloud-run:<project-number>:<region>:<service-name>`. It is not a URL,
credential, Terraform address, or permission to discover arbitrary resources.

The adapter may resolve only the named Cloud Run service through GCP metadata and IAM. A
target is activation-eligible only when provider readback establishes that the exact service exists
in the declared project and region, reports ready, is assigned to the registration's named
Application State owner, and has an Application-Owner-approved grant for the platform edge caller.
No independent DNS check is part of ownership proof.

Provider-backed fixtures and real applications use cross-project attachment. The platform project
owns a Shared VPC host network and regional application subnet. Each application project attaches
as a service project through the explicit project-connection lifecycle. Its Cloud Run service
agent receives read-only host-network discovery and network-user access on only that subnet. The
service uses all-traffic Direct VPC egress through the subnet, internal-only ingress, and IAM
admission for the dedicated edge caller. A platform-owned regional Cloud Router and Public Cloud
NAT provide the subnet's controlled public egress, including protected-application retrieval of the
platform's public JWKS endpoint. Network attachment does not give Platform State ownership of the
application's Cloud Run service, IAM policy, billing, data, or Terraform state, and applications do
not own or mutate the shared router or NAT.

Protected services require both provider-level direct-invocation denial and application-side
assertion verification. The load balancer-to-edge and edge-to-application trust details are refined
by the later identity profile; topology selection alone is not evidence that either control works.

## <u>Application Registration and Registration Set</u>

An Application Registration is versioned data within a complete Registration Set. The logical
fields are:

- contract version, immutable application identifier, and human review metadata;
- one canonical route prefix;
- safe catalogue metadata and explicit Catalogue Visibility;
- one Admission Mode and its mode-specific policy;
- one lifecycle state;
- one or more Application Attachments; and
- no application Feature Entitlements or product authorization rules.

A Registration Set has a monotonically increasing generation number, the digest of the preceding
reviewed generation when one exists, and a complete collection of current registrations including
retired tombstones. It is the only authoritative input for catalogue, routing, and admission. An
individual registration file, application state output, manual route, or provider console edit is
not another source of authority.

The compiler rejects unknown fields. This prevents an application from smuggling provider commands,
feature permissions, or platform behavior through metadata that a schema does not understand.

### Application releases and registration updates

An application release and an Application Registration revision are independent. A registration
describes the application's platform-facing interface; it is not an inventory of application
versions, images, dependencies, data migrations, providers, feature flags, or internal
configuration. The platform does not poll Application State or require a registration change for
every application deployment.

No registration update is required when an Application Owner changes application-owned behavior
while preserving the registered attachment references and every platform-facing contract. This
includes deploying new code or an image, changing internal dependencies or data, replacing a
runtime behind a stable attachment reference, and changing application-owned Feature Entitlements.
A temporary application failure also does not change registration unless the owner requests an
explicit platform suspension.

The Application Owner must propose an update under the existing immutable application identifier
when any registered value changes, including:

- route prefix, catalogue metadata, Catalogue Visibility, Admission Mode, Identity Delivery, or
  lifecycle state;
- attachment resource reference, adapter kind, mount path, forwarding mode, identity requirement,
  or audience; or
- the adopted major version of a platform contract.

This is an update to the existing Registered Application, not re-registration as a new application.
The proposed change participates in a new complete Registration Generation and requires the same
validation and Platform Owner review as every other platform configuration change. An application
never writes Platform State or registration-derived edge resources directly.

When an update replaces an attachment reference, the future operational sequence is:

1. The Application Owner deploys the new attachment through Application State while keeping the
   currently registered attachment available.
2. The owner proposes a Registration Set generation that references the new attachment.
3. The platform validates and atomically activates the complete compiled generation.
4. The old attachment remains available through the declared acceptance and rollback window.
5. Only after acceptance may the Application Owner retire the old attachment through Application
   State.

Failure before activation leaves the current Registration Generation and attachment authoritative.
Failure after activation rolls the Shared Edge back as a whole generation without transferring or
deleting either attachment. Exact acceptance windows and live procedures belong to later
implementation and evaluation authorities.

## <u>Route model</u>

### Application prefix

Version 1 uses one lowercase top-level segment as the public application prefix. Its canonical form
matches `^/[a-z0-9][a-z0-9_-]*$`. The root `/`, `/_platform` and its descendants, and
`/.well-known` and its descendants are platform-reserved.

Registration authors must supply the canonical form. The compiler rejects uppercase characters,
trailing slashes, empty segments, dot segments, percent encoding, encoded separators, query or
fragment syntax, control characters, and Unicode lookalikes instead of silently rewriting them.
Two registrations may not hold the same canonical prefix, including suspended registrations and
retired tombstones. A retired prefix is not silently reassigned to another application.

A request belongs to an application only when its path equals the registered prefix or begins with
that prefix followed by `/`. Textual prefix matches such as `/app2` for `/app` are forbidden.

### Attachment mount

An attachment mount is `/` or a canonical segment path relative to the application prefix. Multiple
attachments are selected by longest segment-bounded mount; equal or otherwise ambiguous mounts are
invalid. Version 1 supports only these explicit forwarding modes:

- preserve the complete external request path;
- remove the application prefix; or
- remove the application prefix and selected attachment mount.

Arbitrary regular expressions, templates, executable rewrites, and application-controlled host
selection are outside the contract. Query data is forwarded as request data and never participates
in route selection.

The root catalogue, reserved platform paths, and application routes are disjoint. Unknown,
malformed, suspended, or retired paths fail closed and never fall through to another
application or expose an attachment reference.

## <u>Catalogue</u>

The catalogue is a read-only projection derived from the same compiled generation as routing. It is
not maintained separately. Only an `active` registration whose Catalogue Visibility is `listed`
appears. `unlisted` is the only other visibility value and does not change Admission Mode.

Each entry contains only the immutable application identifier, bounded plain-text title and
summary, canonical route prefix, and an admission label suitable for display. Catalogue
metadata contains no HTML, scripts, images, arbitrary links, attachment references, allow-list
members, operator metadata, provider data, or secrets. A renderer must escape all text for its
output context and must not interpret catalogue text as markup.

Being listed does not grant admission. Being unlisted does not create a secret route. Catalogue
visibility and admission are validated independently.

## <u>Admission and verified identity</u>

The Version 2 Registration Compiler accepts the Admission Modes and Identity Delivery combinations
defined by ADR-003 and ADR-015:

- `public` with `none`: authentication is not required and Platform Identity is never delivered;
- `public` with `optional`: authentication is not required, but a visitor may choose platform login
  and receive Verified Identity Context after a valid Platform Session exists;
- `authenticated` with `required`: a valid Platform Identity is required; and
- `restricted` with `required`: a valid Platform Identity and a current active Platform Member
  Directory entry are required.

Every other combination is invalid. Membership is one environment-wide operational boundary, not
a member set in a registration. An environment with only its explicitly bootstrapped owner is
owner-only for every restricted route. Email is not an admission or membership key. Feature
Entitlements are prohibited from registration and membership contracts and remain an application
concern after admission.

The repository validates, canonicalizes, migrates, and compiles this Version 2 shape through
explicit compatibility interfaces. The Shared Edge loads either complete compiled version,
enforces explicit Version 2 admission and Identity Delivery, and queries one exact current-member
document. The operator publishes one complete Version 2 bundle/intent family, validates the
application attachment, migrates a readable Version 1 predecessor without its member list, and
atomically activates one complete Version 2 Registration Generation. Separate member commands
mutate the directory without republishing bundles or generations. These implemented paths remain
unqualified until the later Candidate Source slice exercises them against staging.

When Identity Delivery permits it and identity is present, the Shared Edge supplies a compact signed assertion in the versioned
`X-Comfforts-Verified-Identity` header. The edge must remove any visitor-supplied value before
setting its own. The Version 2 claims contract retains contract version, issuer, immutable subject,
intended application audience, issued-at time, expiry time, and request correlation identifier and
may add only the current visitor's positive minimal membership projection. Email, the member
directory, another member, application roles, and Feature Entitlements are prohibited claims.

A receiving application must independently verify the assertion signature, configured issuer,
application-specific audience, time bounds, and contract version before deriving its immutable
Application Principal. A missing, malformed, unsigned, expired, wrong-issuer, or wrong-audience
assertion fails closed wherever identity is required. A public application with `none` receives no
assertion. A public application with `optional` must support both anonymous requests and verified
assertions and must not invent an Application Principal for an anonymous request.

The initial provider, session, directory, signing, key-discovery, algorithm, lifetime, skew, and
rotation profile is defined below. It binds Version 2 identity without adding email, provider
tokens, application users, product roles, or Feature Entitlements to Verified Identity Context.

Admission-policy revocation takes effect at the next request or new streaming-connection boundary.
This design does not promise termination of an already established connection. Application feature
revocation remains application-owned.

### Initial Live identity and session profile

The Shared Edge uses Google OIDC authorization code with PKCE and accepts only a verified Google
issuer and immutable subject. Both consumer Google and Google Workspace accounts may authenticate.
The Admission Mode and Platform Member Directory, not the identity provider or OAuth test-user
list, decide whether that identity is admitted to a restricted application. The initial profile
requires no MFA claim.

The edge creates an opaque Platform Session backed by minimal Firestore Native state in the
qualification project and region. The browser cookie is host-only, `Secure`, `HttpOnly`,
`SameSite=Lax`, and scoped to `/`. The session expires absolutely after eight hours and cannot be
silently renewed past that boundary. The platform retains no Google access or refresh token and
does not use Visitor identity to call Google APIs. The edge runtime alone receives
`roles/datastore.user`, the lowest project-level predefined role that supplies the required
Firestore entity read/write permissions; neither the edge caller nor an application identity
receives session-store access.

A valid session may add Verified Identity Context to a public request only when that registration
selects optional Identity Delivery; `none` remains anonymous even when a host-wide session exists.
A protected request without a valid session enters the edge-owned login flow or fails closed.
Restricted admission reads the exact issuer-and-subject pair from the environment's Platform Member
Directory. Email is transient display-only session or enrollment metadata and never enters the
Version 2 assertion.

The platform-reserved logout operation deletes the server-side session, reads the session store to
verify that the opaque session is absent, clears the host cookie, and accepts only a validated
platform-relative return location. A failed deletion or readback fails closed without claiming
logout. The operation does not revoke the global Google session. An application may link to this
operation from any registered path but cannot implement a second authoritative logout for the
Platform Session.

After admission, the edge strips the identity header and creates a compact assertion with a maximum
60-second lifetime and at most 30 seconds of verifier clock skew. A new assertion is issued for each
forwarded request or new streaming connection. One environment signer uses a software-protected
Cloud KMS `EC_SIGN_P256_SHA256` key in `us-west1`, emits `ES256` with a version-specific key
identifier, and binds every assertion to the registered
`urn:comfforts:app-platform:audience:<application-id>` value.

Only public verification keys are exposed through `/.well-known/jwks.json`. A new key is published
before activation, one version signs, and the preceding key remains published for a 24-hour overlap.
Rotation occurs at least every 90 days. Applications may cache keys for 15 minutes, refresh once on
an unknown key identifier, and otherwise fail closed when verification material is unavailable or
stale.

The initial Live profile makes no distributed replay-prevention claim. Short lifetimes, unique
correlation identifiers, audience binding, TLS, Cloud Run caller IAM, and optional bounded local
replay checks reduce but do not eliminate replay risk. The Cloud Run edge-caller identity proves
workload origin; it is not the Visitor and never becomes Verified Identity Context.

Existing application-managed login remains outside this trust boundary. IAP and
`@react-oauth/google` may continue on existing deployments, but a future Application Adoption must
remove or isolate them from the platform route before their claims can be treated as application
identity.

### Platform Member Directory and member lifecycle

Each environment uses the platform-owned named Firestore database `app-platform-members`, separate
from the `(default)` database used for Platform Sessions. Terraform owns both database
configurations and the Shared Edge IAM posture; it never owns a directory-control document or
member document. The default-database `roles/datastore.user` grant is conditioned to
`projects/<project-id>/databases/(default)`. The named member database uses the custom
`appPlatformMemberReader` role, containing only `datastore.entities.get`, with an exact
per-database condition. The runtime therefore cannot enumerate, create, update, or delete member
documents. Exact document lookup requires no composite query index, and the foundation output
records the required composite-index set as empty.

The outputs of the member-directory infrastructure slice expose only closed database, namespace,
index, runtime-principal, custom-role, permission, and IAM-condition references. They do not expose
member identities, member records, session records, provider policy payloads, or a mutation
interface.

The private member-document format is independently versioned. Its namespace is Version 1 even
though the public Identity Delivery contracts are Version 2. Directory state uses
`platform-member-directory-v1/state`; members use
`platform-members-v1/<member-reference>`. Platform Sessions remain under their existing
`platform-login-flows` and `platform-sessions` collections in the default database. Provider
readback verifies the custom-role permissions and both exact conditioned runtime grants from the
live project IAM policy. An absent, changed, unconditioned, additional project-level runtime grant,
or broader custom-role permission fails closed without retaining the raw policy.

Platform Sessions and Platform Member records occupy disjoint namespaces and have different
lifecycles. The Shared Edge may look up only the current visitor's member state while serving a
request. Member creation and lifecycle mutation are available only through the verified operator
boundary; neither a request nor an application receives a member-write or directory-enumeration
capability. The infrastructure slice must prove that its database and IAM realization preserves
that separation. If the provider's available role model would grant the runtime broader member
mutation or enumeration than this design permits, implementation must stop and re-scope the data
or identity boundary instead of describing the broader grant as least privilege.

The canonical member reference is `pmr1_` plus lowercase SHA-256 over the NUL-delimited reference
scheme, environment, canonical Google issuer, and immutable subject. It is stable within one
environment and different across environments. Issuer and subject are used transiently to derive
the key and are not stored in the member document. Email and display name never enter either
namespace.

The `platform-member-directory-v1/state` control document contains exactly `contract_version`,
`initialized`, `mutation_cursor`, `created_at`, and `updated_at`. A
`platform-members-v1/<member-reference>` member document contains exactly `contract_version`,
`lifecycle`, `mutation_cursor`, `created_at`, and `updated_at`; lifecycle is `active` or
`suspended`. Removal is represented by absence of the member document after the directory control
cursor advances. This retained control document distinguishes a never-initialized empty directory
from a previously initialized directory whose members were removed, preventing owner rebootstrap
from an empty local cache. Later lifecycle mutations must update the control document and selected
member document in one Firestore transaction and then perform exact document readback. The runtime
adapter performs only an exact provider document get for the derived current-visitor reference.
Missing documents return no member; malformed documents and provider failures collapse to one
unavailable result. The runtime adapter has no query, enumeration, or mutation interface. The
separate operator mutation adapter can read the control document, one selected member, and a
boolean bootstrap-emptiness projection; it cannot return a member listing. Neither model may grow
into application profiles, feature roles, or arbitrary user metadata.

Restricted admission performs a current positive lookup. Absent, suspended, removed, malformed, or
unreadable state denies the request without revealing which condition occurred. Public and
authenticated admission do not become restricted when the directory is unavailable and must never
invent a positive membership projection. Membership revocation applies at the next request or new
streaming connection; no mid-connection termination is promised.

Platform deployment creates the database boundary and IAM but leaves the directory empty. The
separate `platform-member-bootstrap-owner` Make target verifies the environment and a remotely empty
directory, confirms a browser-authenticated Google identity independently of the Cloud Operator,
shows and confirms one bounded action, creates the first owner member idempotently, and reads it
back. A non-empty remote directory makes bootstrap fail closed even when private local operator
state is absent.

AP-M9-W10 adds shallow `platform-member-status`, `platform-member-identify`, `platform-member-add`,
`platform-member-suspend`, `platform-member-reactivate`, and `platform-member-remove` targets over
the same deep operator module. Every mutation binds one environment, verified operator session,
remote predecessor, explicit confirmation, and exact readback. Bootstrap and add obtain their
target only through verified Visitor identity. Suspend, reactivate, and remove act on an explicit
opaque reference whose identity was established during enrollment; they do not require the target
Visitor to authenticate again. Member mutation does not compile a Registration Generation, deploy
an application, or change Application State.

Identify is a read-only recovery journey over the same verified Visitor boundary. It derives one
opaque reference, reads only that exact member document, and returns its coarse lifecycle. It
cannot enumerate the directory or mutate membership.

Browser verification uses the reserved `/_platform/member/verify` endpoint. It first clears any
ambient Platform Session, completes the existing Google OIDC flow, derives the member reference at
the Shared Edge, and redirects only the reference plus the exact environment, operation, and
one-use challenge to a loopback callback. Raw issuer, subject, email, OAuth values, cookies, and
browser state never enter the operator process. Bootstrap and add use that reference as the
prospective member. Later lifecycle changes use the retained opaque reference and never ask the
affected Visitor to supply their own credentials to the Platform Operator.

### Version 2 application handoff and generation transition

Every new application handoff declares Admission Mode and Identity Delivery together. The only
valid pairs are public with `none` or `optional`, authenticated with `required`, and restricted
with `required`. `application-handoff-check` validates the requested pair and the platform,
application-project, Shared VPC, service, and identity projection without publishing a document.
`platform-outputs` then writes one application-project-scoped Version 2 Platform Integration
Bundle. The application or fixture deploy consumes that exact bundle and returns one Version 2
Application Attachment Bundle plus a Version 2 registration intent. The intent repeats the bundle's
application, Admission Mode, and Identity Delivery; it cannot define a second identity policy.
The application-owned intent separately declares Catalogue Visibility. Fixture handoff requires
that choice explicitly; platform readiness and bundle generation do not accept or infer it.

`platform-register` accepts only a matching, same-version three-document family. It validates the
target readback and compiles one complete immutable Version 2 Registration Generation that
preserves every unaffected registration. Mixed Version 1/Version 2 handoffs and member data fail
closed. When the current active generation is Version 1, the compiler creates a comparison-only
Version 2 representation: public maps to `none`, authenticated and restricted map to `required`,
and registration-scoped members are discarded. That representation never changes the historical
predecessor or its digest. Activation publishes one complete Version 2 successor whose
`previous_generation_digest` names the exact Version 1 generation. Even an otherwise unchanged
Version 1 registration must cross this atomic successor boundary before it is treated as Version
2.

Generation objects use
`environments/<environment>/generations/<number>/compiled-shared-edge.v<contract-version>.json`.
The provider and private generation history retain readable Version 1 predecessors, stage Version
2 objects under the Version 2 name, and may roll back traffic to an exact retained reviewed
Version 1 or Version 2 generation. Repository implementation and deterministic tests do not imply
that this transition has been invoked against staging.

## <u>Lifecycle and atomic change</u>

The registration contracts define three lifecycle states:

- `active`: eligible for the declared catalogue visibility, routing, and admission behavior;
- `suspended`: retained for review but absent from catalogue and routing;
- `retired`: terminal tombstone, absent from catalogue and routing.

A new application enters `active` only through atomic activation of a complete immutable candidate
generation. Candidate publication is not an Application Lifecycle state: before activation a new
application is absent, while an existing application remains represented by the current active
generation. Valid transitions are `active -> suspended`, `active -> retired`, `suspended -> active`,
and `suspended -> retired`. Content may be revised while active or suspended through a new
Registration Generation. Retired registrations cannot change or reactivate, and their application
identifiers and route prefixes remain reserved.

The compiler compares the proposed set with the preceding generation and rejects skipped,
conflicting, stale, or otherwise invalid transitions. Activation is a whole-generation operation:
catalogue, route, admission, attachment, and ownership outputs cannot be accepted independently.

If validation fails, no compiled generation is produced. If a future adapter cannot realize a
compiled generation completely, it must preserve or restore the Last Reviewed Working
Configuration. Suspension or retirement removes the application's platform presence but never
deletes or mutates its Application State.

### Initial Live generation activation

The reviewed Registration Set remains in Git and compiles before planning into an immutable,
create-only GCS configuration object. New objects use the environment-and-generation path
`environments/<environment>/generations/<number>/compiled-shared-edge.v<contract-version>.json`;
the generation
digest, content digest, and GCS object generation bind its exact content. Historical initial and
digest-addressed names remain readable and immutable. One candidate Cloud Run edge revision binds
the exact source commit, compiler, generation digest, object name and generation, container image
digest, identity profile, and adapter configuration. The candidate receives no user traffic while
attachment, ownership, IAM, and provider dependencies are validated.

The current Live generation pointer is the Cloud Run service's 100-percent traffic assignment to
one immutable edge revision. Owner-approved activation changes that pointer once. The load balancer
continues to forward all application traffic to the edge and contains no registration-derived
prefix map. There is no registration API or database in the initial profile.

Readback compares protected-main source and plan digests, Terraform state, provider revision and
traffic data, the edge's operator-authorized generation status, observable catalogue and route
behavior, attachment and identity configuration, direct-origin denial, and the State Ownership
Manifest. Any disagreement makes the generation unqualified even if the apply command returned
success.

Rollback changes the traffic pointer to the retained preceding revision as a whole and repeats
readback. The objective is restored traffic assignment and readback within 15 minutes after owner
approval. Rollback does not change Application State. The previous configuration object, edge
revision, and replaced application attachment remain available for at least 24 hours; later cleanup
requires a separate owner-approved action.

Provider partial failure stops for inspection. There is no automatic rollback, unlock, state push,
target deletion, or DNS change. The predecessor digest, workflow concurrency, state lock, and
provider revision precondition reject stale or competing changes.

### Initial DNS and TLS sequence

`apps-staging.comfforts.com` is a new qualification record with a 1,800-second TTL. The load
balancer, reserved address, closed-default edge, and certificate configuration are read back before
the Platform Owner separately approves record creation. The operator checks authoritative and
recursive DNS with `dig`, waits for the Google-managed certificate to report active, and then runs
the Live route and identity readback.

The TTL controls resolver caching rather than guaranteeing propagation time. Failure may cause the
owner to remove or restore only the new qualification record after inspection, with cached answers
remaining possible through the TTL. DNS action never changes a Registration Generation and never
touches `apps.comfforts.com` or any Finance Assistant hostname, record, certificate, load balancer,
or state.

## <u>Exclusive state ownership</u>

Every managed resource has exactly one owner recorded in the versioned State Ownership Manifest.
Logical ownership is fixed as follows:

| Resource or concern | Exclusive owner |
| --- | --- |
| Hostname-level edge, catalogue, routing, admission, and edge-only connectors | Platform State |
| Application runtime, endpoint policy, data, secrets, and providers | Named Application State |
| Application Principal mapping and Feature Entitlements | Named Application State |
| Fixture runtime, data, principals, and entitlements | Fixture Application State |

The manifest records canonical, non-secret resource references, owner class, owner identifier, and
contract revision. The same canonical resource reference cannot appear under two owners. A
platform-managed resource may refer to an application-owned attachment, and an application-managed
resource may consume a platform output, but a reference is not management authority.

No platform lifecycle action imports, recreates, or destroys an application resource. No
application lifecycle action mutates or destroys the Shared Edge. Future adoption or state-transfer
procedures must prove that a resource leaves one state before another state assumes it.

### Initial Terraform state and operator profile

The planned Terraform layout contains one backend-bootstrap root, one Platform State root, and one
Fixture Application State root per fixture. The bootstrap and platform roots use different keys in
one platform-state GCS bucket. Every fixture uses its own GCS bucket and root. Future application
projects retain their own backends. This physical separation supports, but does not replace, the
State Ownership Manifest and provider readback.

GCS locking serializes each root. Object versioning retains a noncurrent state version until both
90 days have elapsed and at least 20 newer generations exist. Backend contents, locks, plans, and
recovery copies are restricted operational data and never enter Git or evidence artifacts.

The only normal mutation path is an exact protected-main plan executed by GitHub Actions through
OIDC and GCP Workload Identity Federation after explicit environment approval. Pull requests receive
deterministic checks and advisory read-only plans; the merge commit is planned again and bound to
the apply by source and plan digests. Each workflow identity is limited to its named root and
operation. One concurrency guard and the backend lock prevent competing mutations.

The dedicated repository is fixed as `comfforts/apps-platform`, with protected `main` as the only
normal source ref. AP-M9 preparation may discover read-only repository identifiers, but every
workflow, environment, federation resource, operation identity, and IAM binding is presented for
exact review before it can exist. Local checks remain credential-free. External planning,
readback, and mutation become available only through their implemented AP-M9 operator stage and
exact approval; normal ad hoc local apply is prohibited. An owner-declared break-glass operation
uses short-lived credentials, exact targets, state backup, readback, and reconciliation; it never
uses a stored service-account key.

Bootstrap, import, force-unlock, state push, backend changes, rollback, and destroy are explicit
operator procedures rather than hidden Terraform side effects. A provider error stops for
inspection. Manual console changes remain drift and cannot become the reviewed baseline without a
source change.

### Historical AP-M8 protected-source and federated-identity profile — superseded

This and the following three AP-M8 subsections record the accepted but unexecuted manifest-driven
design at revision `7b6678a7f0b3036d427517dad6bc3bec876d1a44`. ADR-010 through ADR-013 and the
AP-M9 lifecycle profile below supersede them. They are historical context, are outside the active
delivery path, and authorize no AP-M8-W3 through AP-M8-W12 implementation or operation.

The existing checkpoint-3 repository baseline is a precondition, not an AP-M8 result. `main`
remains the default protected branch; pull requests, current-branch enforcement, the
`Credential-free project checks` status, CodeQL thresholds, full-length action pins, read-only
default workflow permissions, secret scanning, push protection, and the no-bypass, no-force-push,
no-deletion rules remain enabled. AP-M8 stops rather than weakening one of those controls to make a
deployment job run.

Five distinct protected GitHub Environment classes separate authenticated plan, routine apply and
immutable publication, qualification DNS, readback/evidence, and exceptional recovery authority.
Their real names
remain operator inputs. Every class accepts
only the exact `main` deployment branch, requires a new explicit owner review for each job, and
contains no environment secret. The plan review cannot approve an apply; an apply review cannot
approve rollback, force-unlock, or destroy; and one recovery-job review cannot approve another
operation. The same owner may perform the human roles, but GitHub still records distinct protected-
environment checkpoints.

Every executable operator workflow later rendered from the AP-M7 templates is fixed to one root
and one operation. Its workflow file, protected environment, service account, federation provider,
repository, branch, and root are committed constants or reviewed non-secret configuration rather
than dispatch inputs. It uses `workflow_dispatch`, top-level `contents: read`, job-local
`id-token: write`, full action commit identifiers, non-persisted checkout credentials, root-scoped
non-cancelling concurrency, and no GitHub secret. The credential-free check workflow never receives
an OIDC permission.

The one dedicated qualification Workload Identity Pool and GitHub provider accept issuer
`https://token.actions.githubusercontent.com` and only the reviewed provider audience. Attribute
mapping retains the subject, repository name and numeric identifier, repository-owner numeric
identifier, ref, protected-ref status, workflow ref, environment, event, and source SHA. The
provider condition and service-account impersonation binding jointly require:

- repository `comfforts/apps-platform` and its exact numeric identifier;
- the exact `comfforts` owner numeric identifier;
- protected `refs/heads/main`;
- one allow-listed rendered workflow at `refs/heads/main`;
- one reviewed protected environment and the matching
  `repo:comfforts/apps-platform:environment:<name>` subject; and
- `workflow_dispatch`.

The workflow then compares its run SHA with the exact 40-character protected-main revision in the
reviewed Version 1 workflow configuration before requesting a plan or mutation. Numeric repository
and owner bindings prevent a renamed or recreated repository from inheriting name-only trust.

Each enabled root or publication operation has a distinct service account and exact impersonation binding.
Plan identities may read only the selected state and provider metadata and create/delete only that
root's native lock object; they cannot write state content or mutate a provider resource. Apply and
rollback identities may read and write only their selected backend and mutate only resources owned
by that root through the exact reviewed same-job plan. A force-unlock identity may affect only one
approved lock and no provider resource. A destroy identity may affect only its root through one
explicit reviewed destroy plan. Unused rollback, force-unlock, and destroy identities have no
binding.

Artifact publication, configuration-generation publication, and qualification DNS each use a
separate fixed workflow and identity. Artifact publication can create only immutable packages in
the qualification repository. Generation publication can create and read back only the exact
generation object under a no-overwrite precondition. DNS can change only the reviewed qualification
A record. None inherits a Terraform root's backend or resource authority.

Each root also has a separate Evidence-class readback identity with read-only access to only that
root's state metadata and provider resources and create-only access to its exact redacted record
path. One finalizer identity can read only the exact bundle prefix and create its final manifest,
checksum file, and verdict under no-overwrite preconditions; it cannot access state or provider
resources. Every other operation may
create only its own redacted operation record and cannot list or read another operation's evidence.

No workload identity may administer federation, IAM, its own service account, another operation
identity, another root, billing, or an application-owned resource. Owner, editor, project-IAM,
service-account-administrator, and user-managed-key permissions are prohibited. Federated
credentials last no longer than one hour, and user-managed service-account keys remain absent.
Import, state push, backend migration, and federation administration remain separate break-glass
authorities rather than hidden capabilities of a routine identity.

The first federation setup uses a separately approved short-lived owner credential because the
federated path does not yet exist. It records exact changes and readback without retaining the
credential or token and grants no workflow permission to alter the trust configuration. Identity
bootstrap is distinct from Terraform backend bootstrap; success or approval for one does not
authorize the other.

The subordinate [qualification-deployment runbook](runbooks/qualification_deployment.md) owns the
checkpoint inputs, setting profile, identity matrix, readback, and stop conditions. This design and
runbook are accepted AP-M8-W1 authority. AP-M8-W2 implements only their local manifest contract and
validator. They create no environment, executable workflow, pool, provider, service account, IAM
binding, credential, backend, plan, resource, DNS change, or deployment.

### Historical AP-M8 backend bootstrap and state-lineage profile — superseded

Four private versioned GCS buckets support five independent root lineages. The bootstrap and
platform roots share the platform-state bucket but use exact `bootstrap` and `platform` prefixes
with distinct conditional access. Each Fixture Application root uses its own bucket and its fixed
`fixtures/<application-id>` prefix. Only the default Terraform workspace is permitted. A root may
read or write only its own object prefix, and a bucket-wide or project-wide storage fallback is
prohibited.

The bootstrap root begins with local state because it creates the buckets. AP-M7 intentionally
commits no backend block for that root, so AP-M8-W5 must first add the reviewed
`infrastructure/backend/bootstrap-backend.tf.tmpl` and its credential-free deterministic renderer
through a protected-main pull request.
The initial apply uses an exact private copy without that declaration. Only after all four bucket
and IAM controls read back may the renderer add the reviewed declaration to the temporary copy and
migrate the state into the empty `bootstrap` prefix.

The initial local bootstrap uses one separately approved short-lived owner credential and one exact
saved plan retained only in a mode-`0700` temporary directory outside the repository. It may create
only the four AP-M7 state buckets. Each bucket retains uniform access, enforced public-access
prevention, object versioning, `STANDARD` single-region storage, deletion prevention, no force
destroy, required ownership labels, and noncurrent deletion only after both the approved age and
newer-version thresholds are satisfied. API enablement, billing mutation, project-wide storage
authority, and any non-backend resource remain outside that plan.

The AP-M7 state-bucket module deliberately defers IAM. After bucket creation, the same approved
AP-M8-W5 owner checkpoint applies only the reviewed bucket-metadata and conditionally prefix-scoped
object-access bindings. Those bindings are operator-managed Platform control settings rather than
resources claimed by another Terraform root. They may not replace an entire policy or grant whole-
bucket object access where bootstrap and platform share the platform-state bucket.

Before migration, the local state backup is integrity-checked and the remote `bootstrap` prefix is
proven empty. Migration preserves the exact lineage, a non-decreasing serial, provider and resource
address inventories, instance identities, and non-secret backend references. Post-migration
readback proves the remote object location and versioning, native lock acquisition and release, and
a no-change plan. Raw state and lineage never enter evidence; only their digests, serial, and
redacted inventories may be recorded.

The local active state remains authoritative until migration and recovery-input readback are
accepted. Recovery-input readback proves that the exact protected generation and restricted backup
can be located and integrity-checked; it does not execute restoration or qualify recovery. A
migration error freezes both copies and never triggers reconfiguration, force-copy retry,
force-unlock, state push, import, deletion, or reconstruction without a new approval.

The platform and three fixture roots initialize independently from clean private copies using only
their reviewed bucket and prefix. Initialization does not apply, pre-seed, or create dummy state.
An empty prefix has status `not-created`; its lineage is recorded only after AP-M8-W9's first
approved apply and reconciled under AP-M8-W11. This distinguishes backend readiness from a false
claim that a non-bootstrap state or resource already exists.

The subordinate [qualification-deployment runbook](runbooks/qualification_deployment.md) defines
the preparation dependency, prerequisites, fixed map, migration invariants, readback, partial-
failure stops, and allowed record. The accepted AP-M8-W1 authority and AP-M8-W2 local manifest
validator perform none of those operations.

### Historical AP-M8 deployment support and sequencing profile — superseded

The AP-M7 source is deliberately not deployable as-is. It provides individual Shared Edge
adapters, in-process Fixture Applications, one-pass static Terraform, and inert workflow templates,
but no production composition entry point, container definitions, networked synthetic Fixture
runtime, provider-backed qualification Registration Set, or executable operator workflow. The
AP-M4 registration generations use `fixture-in-process-v1`; AP-M8 qualification-deployment inputs
require separately reviewed `gcp-cloud-run-v1` references and never relabel Fixture evidence.

The AP-M7 Version 1 platform configuration also forms a real first-deployment dependency cycle: it
requires an image digest, a published configuration-object generation, and all three attachment
references before the platform root can create the Artifact Registry, configuration bucket, and
platform reference needed to produce those values. AP-M8-W6 resolves that cycle with a Version 2
platform deployment contract, not placeholder values or manual Terraform edits. Version 1 remains
accepted static evidence.

Version 2 selects exactly one phase while preserving the single `platform` root and lineage:

| Phase | Inputs | Owned result |
| --- | --- | --- |
| `foundation` | Exact environment, bucket/control, OAuth/KMS reference, labels, and independent Artifact Registry identifier inputs; no edge image, published generation, or attachment references | Configuration storage, Artifact Registry, platform identities, KMS/Firestore, logging/evidence controls, and budget controls only |
| `candidate` | The same accepted foundation configuration plus exact image digest, immutable Registration Generation object, and three typed Fixture attachment references | Preserve foundation unchanged and add the initial Shared Edge revision, serverless load-balancing path, reserved IPv4 address, and managed certificate |

W6 must update the root, schema, loaders, examples, policy, consumers, and deterministic tests
together. Phase changes may neither change backend ownership nor import, replace, or delete a
foundation resource. A candidate plan is invalid unless it shows the existing foundation
unchanged. `make check` remains credential-free and does not build or publish a container.

The initial deployment then follows one dependency chain: apply platform foundation; build and
create-only publish exact source-bound images; validate the actual platform reference; apply
`fixture-public`, `fixture-authenticated`, and `fixture-restricted` sequentially; compile the
provider-backed Registration Set; create-only publish and read back its immutable configuration
object; and apply the platform candidate from a fresh same-job plan. Cross-root data moves only as
typed reviewed references, never by reading another backend.

The initial candidate has no predecessor. Cloud Run may point 100 percent of service traffic to its
only revision while the qualification hostname still has no DNS record. This is a dark initial
candidate, not zero-percent service traffic, a successor-generation activation, or Live evidence.
After candidate state/provider/ownership readback, a separate DNS identity and approval may create
only the `apps-staging.comfforts.com` A record with TTL 1,800. Authoritative and recursive DNS must
agree with the reserved IPv4 address before the managed certificate may pass its readiness
checkpoint.

Every stage stops on its first discrepancy. A successful earlier root or immutable object remains
for inspection; failure never automatically retries, cleans up, overwrites, retags, unlocks,
imports, pushes state, rolls back, destroys, or advances to DNS. DNS/TLS readiness makes the
candidate reachable but leaves it deployed and not Live-qualified. AP-M9 owns runtime, identity,
origin-isolation, failure, availability, and cost qualification. Future generation changes retain
ADR-008 staging and explicit pointer-change authority rather than inheriting this initial-deployment
exception.

### Historical AP-M8 deployment-evidence profile — superseded

AP-M8 evidence is an append-only, source-bound deployment/readback record, not a new evidence class
and not Live evidence. The authoritative bundle remains private in the qualification project's
evidence bucket for 30 days under one `ap-eval-m8/<source-revision>/<evaluation-id>/` prefix. It
contains one manifest, hash-chained operation records, target-scoped readback records, one final
verdict, and sorted checksums. Git may retain only an approved secret-free historical index or
bundle digest.

The Version 1 evidence schema is closed and machine-verified. It binds the repository/source,
operator-manifest predecessor chain, contracts/tools/workflows, protected environments and
operation identities, approvals, exact sequence, plans, images, Registration Generation,
configuration object, state-lineage and inventory digests, provider/IAM/resource inventories,
DNS/TLS metadata, retention, outcomes, failures, limitations, and unavailable later claims.
Records use canonical non-secret resource references and hashes rather than raw state, plan, or
provider material.

Each root is reduced separately by its readback identity. The reducer uses restricted ephemeral
storage, compares expected/state/provider inventories, emits only its closed record, scans
prohibited data, and create-only publishes it. The finalizer has no state or provider access; it
validates schema, unique identifiers, sequence, predecessor hashes, checksums, required gates,
source/manifest agreement, and prohibited-data results, then create-only writes the final manifest,
checksum file, and verdict.
The checksum file covers only the manifest and operation/readback records. The bundle digest
combines its digest with the separately read-back verdict digest and therefore contains no self-
reference.

Raw state, lineage values, state attributes, plans, locks, credentials, tokens, generated
credential files, environment dumps, provider/API responses, browser state, screenshots, logs,
assertions, sessions, restricted members, identity claims, email addresses, IP addresses, user
agents, request/response data, application data, signed URLs, and recovery copies are prohibited.
A missing or prohibited record fails rather than being reconstructed, waived, or silently omitted.

Every AP-EVAL-M8 gate is mandatory. Outcomes are `pass`, `fail`, or `blocked`; the verdict also
reports the mandatory skip count, which must be zero. A dependent stage after failure is `blocked`
with its causal record. AP-M9, cross-project, Finance, and Adoption claims remain `unavailable`
limitations, not successful AP-M8 gates. Only ten complete passing gates may call the exact source
deployed and not Live-qualified.

The exact historical schema fields, gate claims, verifier command, redaction rules, retention, and
pass/fail/skip semantics were owned by the superseded AP-EVAL-M8 proposal. The historical
qualification-deployment runbook records that unexecuted approach. This profile created no evidence
bucket object, identity, provider read, or verdict.

### AP-M9 operator-driven environment lifecycle profile

AP-M9 presents one deep Python lifecycle module through thin Make targets. Its external interface is
limited to these operator operations:

```text
preflight  preflight-check  deploy-check  application-handoff-check  prepare  deploy  status  outputs  register  detach  retire  qualify  destroy
 fixture-project-bootstrap  platform-connect-project  fixture-handoff  fixture-status  fixture-destroy
```

AP-M9-W10 extends that interface with the separate platform-member bootstrap, status, add,
suspend, reactivate, and remove operations. They are not deployment stages and cannot be inferred
from `platform-deploy` success.

The module owns preflight, discovery, one small operation specification, a fixed readable stage
sequence, exact Terraform planning, interactive checkpoints, provider readback, atomic progress,
bundle generation, qualification, and safe resume. Git, provider commands, Terraform, DNS, the
operator console, private state, and time are external-effect seams with production and
deterministic fake implementations. Callers and tests cross the operator interface rather than a
generic orchestration framework.

Each environment has one small committed Environment Profile containing only stable non-secret
owner decisions. Staging fixes the approved non-production project, region, hostname, and provider
class. Production is a separate disabled profile until ownership of `apps.comfforts.com` and every
conflicting shared resource is reconciled. Generated resource names, repository identifiers, image
digests, plan digests, addresses, OAuth identifiers, secret versions, state lineage, provider
responses, and execution outcomes are not operator-maintained profile fields.

Preparation is read-only. It verifies reviewed source and tools, loads one profile, discovers
available GitHub and provider metadata, detects ownership conflicts and drift, derives deterministic
values, asks only for unresolved owner decisions, and emits one canonical Deployment Specification.
A complete specification fixes the environment, source authority and revision, profile, operation,
and reviewed workflow identity. Stage order, resource/action policy, checkpoints, and readback live
in reviewed executable code rather than a second declarative language. An address or client
identifier produced later is generated progress, not a missing preparation input. Approval is a
separate owner decision over the specification digest.

Preflight executes the preparation-readiness portion only. It loads and validates the named
profile, checks the selected source authority, and invokes the bounded GitHub, GCP, Terraform, and
DNS discovery adapters. Its result contains only `ready` or `blocked` plus blocker codes. It does
not invoke specification generation, canonical state writes, approval, executor construction,
planning, or mutation. Preparation consumes the same readiness logic and then continues into
specification generation and approval.

The two local-maintenance checks are diagnostic interfaces, not operational source authorities.
`preflight-check` runs preflight with source-admission failures demoted to explicit diagnostics.
`deploy-check` additionally validates retained specification/progress state and supplies each
currently resolvable fixed stage to a read-only checker. Terraform stages render from the working
tree, refresh remote state with locking disabled, run the normal plan policy, and delete their
ephemeral saved plan. Missing generated predecessor outputs produce `deferred`; manual checkpoints
produce `manual`. Its deep interface returns explicit platform readiness: `ready`,
`reconciliation-required`, `incomplete`, or `blocked`. The classification includes required
platform services and the platform-owned foundation, network egress, Shared Edge, active runtime,
TLS, and final readback. The checker exposes reads and plan creation only and cannot approve,
apply, execute a provider action, complete a checkpoint, or write operational lifecycle state.

`application-handoff-check` is the application-scoped readiness boundary immediately before
`outputs`. It consumes the deployment check's explicit platform-ready result without interpreting
deployment-stage names, then performs fresh provider readback for the named application project,
its required services, Shared VPC host association, host-network viewer grant, and subnet-user
grant. It validates the
same application, route, access mode, Identity Delivery, platform revision, and Registration
Generation inputs that would produce the bundle, but does not publish that bundle. Public `none`
requires no platform identity projection; public `optional`, authenticated `required`, and
restricted `required` require the exact platform identity values and application-specific audience
in that application-scoped projection. The command has no
approval, apply, provider-mutation, bundle-publication, or operational-state-write interface.
The deployment checker owns the exact application-subnet Cloud Router and NAT requirement;
missing or changed egress is platform reconciliation, not an application-project repair.

Before default deployment prepares new intent, it reads the private current-specification pointer
and canonical specification and revalidates the current source, profile, environment, human
session, project, ownership, pinned tools, readable provider facts, approval binding, and active
progress compatibility. An exact current approval is selected automatically; the operator does not relay its
digest. Absence, drift, or missing approval falls back to normal preparation. Malformed retained
state or a current blocker fails closed without rewriting the evidence. Supplying an explicit
current digest remains an optional pin, not the ordinary interface.

The specification version and workflow identifier bind the executable stage schema. The completed
11-stage `platform-deploy-v1` workflow remains an exact readable predecessor after the current
12-stage `platform-deploy-v2` workflow adds runtime activation. A valid terminal predecessor record
is historical: status may report it, but execution cannot resume it and the lifecycle cannot add a
stage result that the predecessor never ran. Before new preparation changes the private current
pointers, the operator displays both workflows and confirms that local supersession with `y/N`.
The predecessor specification and terminal snapshot remain unchanged. A declined confirmation
changes nothing; a running or waiting predecessor remains an active-operation conflict. An invalid
or unrecognized record fails with a named readback blocker instead of reaching the generic internal
error boundary.

Source authority is an explicit specification input derived from Git readback, never a free-form
operator value. `accepted` requires the exact clean current protected-main revision. `candidate`
requires staging, a clean non-main branch, an exact pushed matching origin revision, and current
`origin/main` as an ancestor. The authority label changes the specification digest. Environment
status and Platform Integration Bundles carry the label; candidate qualification is published
under a separate candidate pointer and cannot become accepted qualification or production
authority. After merge, accepted preparation, deployment, and qualification run again from main.

For an ordinary reversible staging creation or update, invoking the named command deliberately is
the owner's selection of the operation. Specification approval and every exact plan or bounded
action confirmation occur inside that same process; no separate out-of-band approval is required.
Repository merge never invokes an operation. Destruction, purge, ownership transfer, production
cutover, and scope expansion remain separately governed decisions.

Deployment consumes exactly that approved digest, follows this fixed sequence, and atomically
replaces one private progress record after each successful readback:

1. source, identity, environment, state, ownership, and drift preflight;
2. reviewed enablement and readback of the three prerequisite APIs required for state bootstrap
   and Terraform provider planning;
3. one-time backend bootstrap when absent;
4. platform foundation, including configuration storage, registry, identities, KMS, Firestore
   session and empty member-directory infrastructure, Secret Manager containers, logging, evidence,
   and cost controls;
5. immutable Shared Edge image publication;
6. immutable closed initial Registration Generation publication;
7. platform-owned OAuth branding/client creation and direct Secret Manager entry through an
   interactive provider-console checkpoint;
8. Shared Edge, load balancer, reserved address, and full hostname readback;
9. exact source-, image-, and active-generation-bound Shared Edge revision activation;
10. the exact external Squarespace record through an interactive checkpoint;
11. authoritative and recursive DNS verification, certificate creation or readiness, and a
    one-hour readiness bound with 30-second observations; explicit provider failure states stop
    instead of being classified as pending; and
12. state/provider/ownership readback and status reconciliation.

The first execution of step 8 is dark and leaves TLS disabled until external DNS is verified. On a
later source-bound reconciliation, the operator reads the exact Platform State addresses before
planning. If the managed certificate is already state-owned, step 8 preserves the certificate and
its HTTPS resources instead of rendering the first-deployment TLS-disabled shape. State presence
does not imply readiness; step 11 still verifies DNS and the provider-managed certificate status.

The operator transcript groups those twelve internal resume checkpoints into seven numbered human
stages: verification; state and foundation bootstrap; immutable image and generation publication;
OAuth configuration; Shared Edge creation and runtime activation; DNS and TLS; and final platform
readback. Each group is
announced as `Stage n/7` when first entered in a process. A resumed process announces the group
containing its first unclosed internal checkpoint, so a resume at certificate planning reports
`Stage 6/7 · Configure DNS and TLS` without repeating the already closed DNS action.

The local wizard remains active at a manual checkpoint, prints the exact approved values and
provider destination, and waits for Enter. It never asks for a secret payload. Before the DNS
pause, readback distinguishes an exact existing record from one that must be reconciled; after
acknowledgement it verifies every provider-readable value and narrates the closed checkpoint. An
unreadable field is recorded as operator-attested. Rerunning the same operation is a crash-recovery
path that resumes after the last closed stage. A scope change, unapproved mutation, owner mismatch,
or drift requires new preparation and approval.

The lifecycle verifies and uses one short-lived human-authenticated operator session for the
selected environment and provider project. Each Terraform mutation plans, canonicalizes,
policy-checks, shows, confirms with `y/N`, and applies one exact same-execution plan, then reads back
state and provider results. Typed phrases remain reserved for irreversible boundaries. No
service-account key, long-lived credential, automatic unlock, state push, import, rollback,
cleanup, or destructive recovery is permitted. Capability available to the human account outside
the script is residual risk and never expands the reviewed lifecycle scope.

When Terraform plan or apply fails, the command boundary writes the exact captured stdout and
stderr into a new timestamped event below the ignored private operator diagnostics directory. The
event directory is mode `0700`; its streams and SHA-256 manifest are mode `0600`. Terminal output
contains only the safe blocker, diagnostic path and digest, and a handling warning. The raw streams
may contain sensitive provider material and therefore never enter a profile, specification,
approval, progress record, bundle, evidence package, qualification result, Git input, or terminal
transcript. This local troubleshooting boundary permits root-cause inspection without treating raw
provider output as reviewed authority.

After environment deployment and explicit application-project connection, `outputs` compiles a
Platform Integration Bundle for one application project, application, environment, access mode,
Identity Delivery, route intent, and platform revision. The operator first runs
`application-handoff-check` with those
same values and resolves any platform-reconciliation, project-service, connection, or protected-
identity blocker. The bundle includes the exact application project, Shared VPC host,
network, subnet, region, and egress bindings. A fixture may consume a bundle whose
qualification status is explicitly `unqualified`; real Application Adoption requires the owning
application to accept the platform's current qualification status. The application deploys through
Application State and returns an Application Attachment Bundle bound to the platform-bundle digest.
Registration validates the bundle, provider target project and network, owner, ingress, caller
grant, audience, and current platform state before activating a complete Registration Generation.
Protected fixture verification failures emit only an allowlisted constant diagnostic code and the
fixture identifier. Assertions, identities, tokens, provider exceptions, and request values remain
absent from the fixture log event.

The repository-owned Fixture Application operator acts only as the Application Owner for the three
synthetic fixtures. A one-time `fixture-project-bootstrap` creates or repairs their dedicated
application project, required services, private versioned state bucket, and image repository.
`platform-connect-project` attaches that existing project to the platform Shared VPC and records
the verified connection without creating a runtime or route.

For each fixture, the Platform Operator runs `outputs`, then passes that exact bundle to
`fixture-handoff`. The handoff builds or reuses the immutable fixture image, plans and applies only
the selected independent Application State root, emits its attachment bundle and registration
intent, publishes the canonical files with mode `0600` in ignored operator state, and stops. It is
an Application State mutation, not read-only preparation. After inspection, the Platform Operator
runs `register` to activate a complete generation. There is no combined fixture deploy-and-register
operation. `fixture-status` is read-only and reports all fixtures by default or one optional
selection. Each row reports the active generation's catalogue visibility independently of target
and route readiness. `fixture-destroy` requires the route to have been suspended through `detach`, requires
the fixture-specific destructive confirmation, operates only on the selected fixture Application
State, and never destroys Platform State. These commands are the executable staging-fixture
boundary; Terraform roots and loopback servers alone are not deployment capability.

Detachment is the reversible suspended state. The edge removes the application from the catalogue
and target routing, reserves its identifier and route, invokes no target, and returns a generic
temporary-unavailability response for the reserved path. The owner may destroy and later redeploy
the application, submit a replacement attachment, and reactivate it. Retirement is terminal and
returns a generic permanent-removal response. Unknown routes remain distinct closed responses. A
future route-release operation requires new authority.

Qualification deploys or updates synthetic Fixture Applications through the same integration and
attachment bundles, in separate Application State, then exercises DNS/TLS, catalogue, routing,
public no-identity and optional-identity behavior, authenticated admission, restricted member
allow/deny, OAuth/session/logout, assertions/JWKS, direct-origin denial, isolation, streaming,
lifecycle, redaction, and rollback. It records revision-scoped evidence without making a real
application the test harness. Restricted qualification additionally requires explicit owner
bootstrap plus a second member's add, suspension or removal, reactivation, and reviewed-baseline
restoration. Every non-mutating qualification check completes successfully before
the temporary member journey begins. That journey receives the privately retained reviewed owner
reference, proves the remote owner-only baseline, and invokes the existing source-admitted member
service for add, suspend, reactivate, and remove. Each transition is followed by a separately
confirmed browser request to `/_platform/member/qualification`. The endpoint validates one named
restricted Version 2 route, applies the same current-member lookup as ordinary route admission,
and returns only a boolean decision to a challenge-bound loopback listener. It exposes neither the
Visitor identity nor a member reference. Every exit attempts temporary-member removal and rereads
the owner-only baseline.

Only after the other checks and cleanup-safe member journey pass can
the rollback check request an owner-confirmed traffic change. The rollback check temporarily
activates the retained reviewed predecessor and verifies provider readback. Before prompting or
moving traffic, it requires the predecessor provider revision to be bound to the same platform
source revision as the active candidate. A stale historical runtime cannot qualify current-source
rollback compatibility; it fails with explicit guidance to create a fresh public-`none` generation
and its public-`optional` successor under the active candidate. One separately confirmed browser
check establishes a Platform Session and a second proves that the predecessor's public `none`
policy withholds identity. When that second callback instead observes the successor's
optional-identity policy, the qualifier performs a bounded traffic-convergence wait and may offer
up to two additional separately confirmed observations. Other browser failures do not retry. The
operator must then provide the separate exact restoration
confirmation, and provider readback must show the original public-`optional` complete generation
again. A failed predecessor browser proof retains its exact stable blocker, still proceeds to
restoration, and fails qualification;
a failed prerequisite blocks rollback without moving traffic. Fixtures are detached and may be
destroyed after evaluation without retiring their identities.

Environment destruction creates a separate destructive specification, refuses active attachments,
requires exact typed confirmation, removes traffic and external DNS safely, respects cache and
rollback windows, and never destroys Application State. State backends, recovery material, and
evidence remain until a separately approved purge. The Shared VPC host, application network, and
subnet also remain while application projects are connected; disconnecting those projects is a
separate destructive operation. Production uses independent authority and a
stronger confirmation. `platform-prepare` for production returns
`OWNERSHIP_TRANSFER_REQUIRED` while the Finance-owned production edge or any other requested
resource has not completed an explicit ownership transfer.

AP-M9-W1 defines this design, AP-M9-W2 removed the retired manifest implementation, AP-M9-W3
implemented the profile and lifecycle contracts, AP-M9-W4 implemented credential-free local
preparation/status plus resumable fake execution, AP-M9-W5 implemented the repository-only
Terraform lifecycle described below, and AP-M9-W6 implemented the unarmed multi-stage deployment engine,
closed command boundary, exact confirmations, manual checkpoints, readback, and resume. AP-M9-W7
implemented least-data application outputs, exact attachment/target validation, immutable complete-
generation activation, reversible detachment/reactivation, terminal retirement, and distinct
reserved-route responses behind injected boundaries. AP-M9-W8 implemented exact-revision
qualification, redacted evidence, network fixtures, failure injection, reviewed rollback, and
safe-destruction mechanics plus guarded local provider construction and the production Shared Edge
composition. AP-M9-W9 implements the Fixture Application operator, browser-mediated qualification,
exact retained-resource destruction transitions, and staging-only Candidate Source admission so a
pushed pull-request revision can exercise provider behavior before merge without claiming accepted
qualification. W9 Candidate Source exercised those boundaries with all three cross-project
fixtures and completed restricted-fixture detach, destruction, redeployment, reactivation, and
qualification under the predecessor Version 1 model. That operation does not promote its evidence
to Accepted Source or qualify ADR-015. AP-M9-W10 implements and candidate-qualifies the Version 2
member-directory boundary before AP-M9-W11 performs the first accepted staging operation. The live
process accepts exact generated revision, generation, provider,
OAuth-secret-version, KMS-key-version, edge-caller, and operator-subject bindings. It reads the
OAuth payload directly from the selected Secret Manager version and never puts that payload in an
environment variable, terminal, image, output, or evidence record. These packages create no identity,
credential, state,
provider resource, OAuth client, DNS record, certificate, bundle instance, application change, or
Live qualification evidence merely because the implementation exists.
Python-to-Go migration remains a later contract-preserving milestone after
the Python product is delivered and qualified.

### AP-M9-W5 deployable Terraform lifecycle

The active Terraform seam is now three ordered phases:

```text
bootstrap(backend_configuration) -> bootstrap_phase_output
platform(platform_configuration{phase=foundation}) -> foundation_phase_output
platform(platform_configuration{phase=shared-edge, shared_edge_binding=complete})
    -> shared_edge_phase_output
```

Foundation and Shared Edge use the same `infrastructure/terraform/platform` root and the same
`platform` backend prefix. Changing phase cannot transfer ownership, import a resource, or create a
second Platform State lineage. Foundation accepts no edge image, OAuth client identifier, OAuth
secret version, signing key version, Registration Generation, or Application Attachment. Those
generated facts enter only through a complete Version 2 Shared Edge binding. Application
attachments remain inside the compiled Registration Generation and never become Terraform target
inputs.

Staging fixes four backend buckets and five lineages:

| Bucket | Prefix | State owner |
| --- | --- | --- |
| `comfforts-ap-stg-455651441682-platform-state` | `bootstrap` | Platform State |
| `comfforts-ap-stg-455651441682-platform-state` | `platform` | Platform State |
| `comfforts-ap-stg-455651441682-fixture-public-state` | `fixtures/fixture-public` | Fixture Application State |
| `comfforts-ap-stg-455651441682-fixture-authenticated-state` | `fixtures/fixture-authenticated` | Fixture Application State |
| `comfforts-ap-stg-455651441682-fixture-restricted-state` | `fixtures/fixture-restricted` | Fixture Application State |

The backend renderer writes canonical `gcs` declarations only beneath a caller-approved private
working root, uses mode `0600`, returns a content digest, is idempotent for identical content, and
refuses traversal or replacement. It does not invoke Terraform or access a backend.

The operator-session profile contains the selected environment, exact provider project, active
human account readback, explicit clean accepted or candidate source revision, and local
authentication freshness result.
It is private execution state, not an operator-authored manifest or committed identity value. The
lifecycle creates no operation-specific service accounts or impersonation bindings. Terraform-
managed runtime identities remain distinct per environment and owner, and service-account keys
remain prohibited.

Plan policy accepts only a redacted observation bound to the exact environment, source revision,
state owner, owner identifier, root, phase, project, explicitly configured Google provider, and
phase resource/action inventory. It sorts that projection before hashing. Raw plans, before/after
values, provider payloads, and state never enter the canonical summary. A mismatch, ambient
provider default, unexpected resource/action, replacement, or non-destructive delete yields
ordered violations and no consumable plan digest.

Foundation and Shared Edge share one Terraform root and Platform State lineage. A Shared Edge plan
may therefore include exact `module.platform_foundation` and `module.platform_controls` resources
from the preceding phase only as `no-op` or `read` observations. The sole migration exception is
the first cross-project fixture reconciliation: policy admits the exact Shared VPC network,
application subnet, host-project binding, application-subnet Cloud Router, and Cloud NAT creates
plus the exact qualification image-repository update and edge session-store role creation. Those
addresses and actions are closed and the stage rereads the foundation output, including exact
all-traffic, router, and NAT references.
Every other inherited create, update, delete, replacement, unexpected prefix, or unknown type
fails policy instead of acquiring Shared Edge authority.

A failed Shared Edge apply can leave a valid partial `module.shared_edge[0]` inventory in that same
lineage. When a later source-bound deployment reaches foundation, the operator first projects the
exact state addresses. If any Shared Edge address is already recorded, it creates an explicit
refresh-only foundation plan rather than interpreting the foundation phase as authority to remove
the edge. In that mode, both foundation and inherited Shared Edge resources may appear only as
`no-op` or `read`; any drift or mutation fails policy and no refresh-only plan is applied. The later
normal Shared Edge exact plan reconciles the partial inventory while preserving one Platform State
owner and lineage.

Terraform manages each inactive candidate's revision name, environment binding, and image digest as
one immutable Cloud Run configuration. A later source or image therefore produces a newly named
candidate instead of attempting to alter an existing revision. Terraform deliberately ignores only
the service traffic assignment after creation: registration activation and rollback own that Live
generation pointer and may move it only after their separate validation and confirmation.

The Shared Edge phase can first reserve the address with TLS disabled. Certificate and HTTPS
resources become eligible only after the later deployment engine has completed the external-DNS
checkpoint. Bootstrap, foundation, and edge outputs are closed, typed, non-secret projections.
Mocked providers and an injected deterministic command fake exercise the same composition; no
production command adapter or operator deploy target exists in W5. Production returns
`OWNERSHIP_TRANSFER_REQUIRED` before rendering or command invocation.

### AP-M7 Terraform configuration profile

AP-M7 implements Terraform 1.17.2 configuration with `hashicorp/google` 8.11.0. Every root records
the exact CLI constraint, exact provider constraint, and a committed provider lock for
`linux_amd64` and `darwin_arm64`. Provider installation is an explicit setup action into an ignored
filesystem mirror; the default gate never consults a registry or upgrades a lock.

The external Terraform seam consists of three deep root-module interfaces:

```text
bootstrap(backend_configuration) -> backend_reference_set
fixture_application(fixture_configuration, platform_reference) -> attachment_reference
platform(platform_configuration, attachment_references, registration_generation)
    -> platform_reference_set
```

`bootstrap/` owns only backend buckets, access intent, versioning, and recovery policy. One
`fixtures/<application-id>/` root owns exactly one Fixture Application's runtime and ingress IAM.
`platform/` owns the Shared Edge, edge identity, session and signing resources, registration-
generation objects, hostname-level load balancing and certificate intent, observability, evidence,
and cost controls. DNS record mutation is absent. Each root accepts one typed configuration object
plus the minimum typed non-secret references it consumes and returns only typed non-secret
references. Reusable modules are internal implementation: callers and tests use the root
interfaces, and no module reads another root's state.

Configuration contracts live under `infrastructure/config/` as versioned JSON Schemas with
synthetic examples for backend, platform, fixture, cross-state-reference, and workflow inputs.
Terraform variable types and validation duplicate the security-critical constraints at the root
interface. Committed configuration may contain project, region, resource, image-digest, audience,
issuer, key-version, and Secret Manager version references, but never secret values, credentials,
restricted members, state addresses, saved plans, or provider responses. Every cross-state value is
reviewed data conforming to the reference contract; `terraform_remote_state`, backend-object reads,
and application credentials are prohibited.

Each non-bootstrap root declares an empty `backend "gcs" {}` block. Bucket and prefix values enter
only through an operator-reviewed, non-secret backend configuration outside reusable modules.
Backend initialization, migration, lineage verification, and destruction remain AP-M9 operator
actions. The bootstrap root starts locally only during that separately approved procedure; AP-M7
does not initialize it or create local state.

The only executable AP-M7 workflow remains the credential-free repository check. Operator workflow
designs live under `infrastructure/workflows/` as inert `*.yml.tmpl` files for advisory planning,
exact-main apply, rollback, force-unlock, and destroy. Static validation requires SHA-pinned actions,
read-only repository permissions by default, explicit `id-token: write` only in templates that need
federation, protected-environment and protected-main placeholders, per-root concurrency, exact
source and plan digest binding, explicit targets, and no persisted plan. AP-M8 must separately
approve values, repository settings, environments, federation, and activation before any template
can become an executable cloud workflow.

AP-M7's Terraform tests use only explicit `command = plan` runs and mocked providers. Validation
runs from a temporary copy with `-backend=false`, committed locks, and the pre-populated filesystem
mirror. It performs no apply, backend access, credential lookup, metadata-server request, provider
API call, DNS lookup, repository mutation, or external network request. A missing CLI, mirror,
provider, lock checksum, operator input, or static assertion fails rather than downloading,
skipping, or inventing a value.

The fixed environment facts are repository `comfforts/apps-platform`, project
`comfforts-platform-non-prod` (`455651441682`), region `us-west1`, and qualification hostname
`apps-staging.comfforts.com`. Globally unique bucket names, protected workflow subjects and
environment, managed-zone resource, immutable image digests, OAuth client and secret-version
references, billing-account reference, notification destination, and the initial Live Registration
Set remain unresolved operator inputs. AP-M7 supplies their typed interfaces and synthetic test
values only.

## <u>Failure and rollback behavior</u>

- Schema, semantic, transition, or ownership failure produces ordered violations and no compiled
  output.
- An unmatched or malformed request receives a closed platform response and is not forwarded.
- An unavailable attachment fails for that application only; the edge does not retry against a
  different application.
- Missing or invalid identity fails protected admission and application-side verification.
- Suspended and retired registrations produce no live route or catalogue entry.
- Provider-console or hand-written route changes are drift and cannot become the reviewed baseline.
- Rollback selects a previously reviewed whole generation; it never rolls back or deletes
  Application State.

Runtime status, provider health, and live rollback require measured evidence from later evaluation
gates. Static configuration or a successful compiler run is not runtime qualification.

## <u>Threat and data boundary</u>

Registrations, catalogue text, attachment references, identity headers, request paths, provider
payloads, and operator-supplied configuration are untrusted inputs. Every interface is bounded,
strictly parsed, and allow-listed before it can influence derived configuration. The dedicated
[threat model](06_threat_model.md) owns the detailed trust zones, abuse cases, controls, residual
risks, and future qualification mappings.

Platform logs and evidence may contain contract versions, generation digests, immutable application
identifiers, route identifiers, coarse admission outcomes, violation codes, and correlation
identifiers. They must not contain secret payloads, raw credentials, restricted allow-list contents,
signed assertions, provider payloads, application request bodies, or application data. A
correlation identifier is not an identity or authorization signal.

The initial logging, evidence, incident, and cost profile is defined below. Its selection does not
make a sink, retention policy, alert, responder, quota, or budget operational.

### Initial logging, evidence, incident, and cost profile

The edge emits one exact JSON-line structured completion event per request or streaming connection
into a dedicated Cloud Logging bucket in the qualification project and `us-west1`. The live logger
uses an isolated `INFO` handler with no human-readable prefix so Cloud Logging parses the record as
the `jsonPayload` selected by the dedicated sink. Seven-day retention and owner-only access apply.
Events contain only generation, application and route identifiers, coarse outcomes, status class,
latency, correlation identifier, non-secret platform versions, and an optional diagnostic code
from the fixed runtime allowlist. They exclude identity, visitor metadata, payloads, application
data, assertions, sessions, secrets, provider exceptions, state, saved plans, and stream chunks.
Logs have no external sink.

Control-plane events record digest-bound plan, apply, activation, rollback, DNS/TLS, key, IAM,
state, drift, break-glass, incident, and destructive-cleanup outcomes without copying protected
payloads. Provider-required administrative audit metadata remains restricted inside the project and
is not copied into platform evidence.

Secret-free Live evidence is a 30-day, owner-readable bundle in a dedicated GCS evidence bucket.
It contains revision and plan digests, generation and image digests, redacted provider and runtime
readback, commands, timestamps, results, failures, limitations, and evidence-class labels. A
screenshot or raw provider export is not an authoritative record. Git may hold only a reviewed safe
index or digest.

The App Platform Owner is the initial incident responder. Response stops new mutation, identifies
the revision and generation, preserves permitted evidence, and requires an explicit decision for
suspension, rollback, secret rotation, or cleanup. Only budget notifications are automated in the
first profile; later security or availability alerts require measured operating needs and a new
reviewed decision.

The project budget is USD 20 per month with owner notifications at 50, 80, and 100 percent. The
80-percent threshold pauses new billable changes, and the 100-percent threshold requires an owner
continuation, suspension, or teardown decision. No threshold disables billing or mutates resources
automatically.

The Shared Edge uses zero minimum and two maximum 1-vCPU, 512-MiB Cloud Run instances at concurrency
20. Each Fixture Application uses zero minimum and one maximum instance with the same CPU and memory
at concurrency 10. Streams last at most 55 minutes and hold concurrency while open. The initial
profile has one non-production edge and load balancer and no CDN, WAF, HSM, production replica,
always-on instance, Firestore backup, or Firestore point-in-time recovery.

Firestore holds expiring Platform Sessions and the minimum environment-scoped Platform Member
records required by ADR-015, in disjoint namespaces. Session expiry does not remove or alter a
member; member retention changes only through the explicit member lifecycle. KMS keeps only active
and required overlapping verification versions. Artifact Registry retains active, rollback, and
current-candidate images; cleanup begins in dry-run and deletion remains owner-approved. Terraform
checks reject unbounded or larger runtimes, extra environments or edges, unapproved billable
services, longer retention, and missing `environment`, `managed_by`, `state_owner`, or applicable
`application_id` labels.

The platform project pays for Shared Edge and Shared VPC host resources. The dedicated fixture
project pays for fixture runtimes, images, and state. Other application projects pay for their
runtime, data, networking use, and provider services unless their Application Adoption explicitly
records another allocation.

### AP-M6 networked runtime profile

AP-M6 implements one deep Shared Edge module behind this external interface:

```text
create_app(runtime_configuration, adapters) -> ASGI application
```

The returned application is the interface used by the server and by integration tests. It accepts
all network requests through one pipeline and hides catalogue projection, reserved paths, route
selection, admission, identity assertion, attachment resolution, forwarding, limits, failure
mapping, and completion-event redaction. Framework routes may identify platform-reserved paths and
one catch-all entry, but they may not duplicate registration-derived application routes.

The implementation uses Python 3.12 or newer, Starlette as the ASGI framework, and Uvicorn as the
server. Provider and network behavior is accepted through internal seams for immutable generation
loading, Google OIDC, Platform Sessions, assertion signing and public-key discovery, Cloud Run
metadata, upstream HTTP/WebSocket transport, trusted client classification, and time. Each seam has
both a production adapter and a deterministic fake before it is treated as real. Callers do not
assemble the request pipeline or depend on those internal interfaces.

The application-side verifier is a separate deep module with one interface that accepts an
assertion, expected issuer, expected application audience, verification material, and time, then
returns a validated Version 1 or Version 2 Verified Identity Context or an ordered verification
violation. Version 2 may include only the positive `platform_member: true` projection. The verifier
does not perform admission, create an Application Principal, or grant a Feature Entitlement.

Direct dependencies are declared in `pyproject.toml`; complete transitive resolution is committed
in `uv.lock`. Runtime work adds a dependency only with its first production use. The selected
families are Starlette and Uvicorn for ASGI, HTTPX and `websockets` for upstream transport, Authlib
and `cryptography` for OIDC and ES256, and official Google Cloud clients for Storage, Firestore,
KMS, Cloud Run metadata, and service identity. Production code may not hand-build provider signing,
token, or discovery protocols. `make check` consumes an already synchronized locked environment;
it performs no installation or network access.

AP-M6-W3 accepts at most one mebibyte from the exact configured Cloud Storage object generation
through an injected source adapter; the ranged read includes only one additional byte needed to
detect overflow. Startup verifies the raw SHA-256 content digest, applies the Version 1
duplicate-safe JSON and compiled-configuration schema profile, and verifies the compiled generation
digest before binding the generation in memory. Any missing adapter, source failure, invalid
document, invalid contract, or digest mismatch fails startup with a coarse code. Loading does not
discover storage, compile registrations, follow a mutable pointer, activate a provider revision, or
reload during the process lifetime.

AP-M6-W4 renders only the active catalogue projection from that bound generation and escapes every
value for HTML. One canonical raw-path parser rejects percent encoding, alternate separators,
empty or dot segments, control or whitespace characters, decoded/raw disagreement, invalid UTF-8,
and paths over 4,096 bytes. The same catch-all request path keeps reserved platform paths disjoint,
selects only an active segment-bounded application prefix, selects the longest attachment mount,
and applies the declared rewrite while preserving query bytes. Public routes expose only an
internal deterministic route-selection handoff exercised by a deterministic fake and still return
`503`; AP-M6-W4 performs no attachment resolution or proxy operation.

AP-M6-W5 adds an edge-owned Google authorization-code flow with PKCE and validates only signed
Google issuer-and-subject identity. A browser receives opaque host-only `Secure`, `HttpOnly`,
`SameSite=Lax`, `Path=/` cookies; transient login material and minimal sessions remain server-side.
The Firestore adapter hashes opaque identifiers before using them as document identifiers, consumes
login flows once, and stores no Google access or refresh token. Sessions expire absolutely after
eight hours without renewal. Public routing remains anonymous when session storage is unavailable;
authenticated and restricted routing fail closed. Restricted admission compares the exact reviewed
issuer-and-subject pair, never email. Logout deletes server state, clears the cookie, and accepts
only a root or active registered platform-relative return location. Production provider and store
failures retain the same generic visitor response while emitting only constant, non-sensitive
boundary codes that distinguish the session store from the identity provider. Production provider
and store adapters are exercised with deterministic local transports; default verification performs no
provider call. AP-M6-W6 replaces the internal admitted identity at the handoff with its signed
Version 1 assertion.

AP-M6-W6 replaces any visitor-supplied identity value with a compact ES256 JWS only after identity
is admitted and the selected attachment supplies its application-specific audience. The payload is
exactly the Version 1 claim contract: contract version, canonical Google issuer, immutable subject,
audience, issued and expiry times, and one request correlation identifier. It contains no email,
session identifier, provider token, role, Feature Entitlement, or shared application principal.
Assertions last 60 seconds and the independent application verifier accepts at most 30 seconds of
clock skew.

One signing seam has a deterministic fixed-key adapter and a Cloud KMS adapter bound to exact
`us-west1` key-version resources. The KMS adapter validates digest, signature, public-key CRC32C,
algorithm, and returned resource identity before accepting a result. The reserved JWKS path emits
only bounded P-256 public verification material for the active and overlap keys with a 15-minute
cache limit. The application verifier accepts an assertion, exact issuer, exact application
audience, key fetcher, and time; it refreshes once for an unknown key and rejects unavailable or
stale material. It returns Version 1 or Version 2 Verified Identity Context only after selecting
the declared local schema and validating contract, signature, issuer, audience, lifetime, and
clock. It creates no Application Principal, grants no Feature Entitlement, and makes no distributed
replay-prevention claim.

AP-M6-W7 accepts only the exact `gcp-cloud-run-v1` URN grammar and turns its project number, region,
and service name into one exact Cloud Run v2 service read and one exact IAM-policy read. The
production adapter accepts its Cloud Run client at construction and performs no discovery or I/O
until resolution; deterministic verification supplies an exact-key in-memory metadata adapter.
Provider readback is eligible only when the returned resource scope matches, reconciliation has
completed successfully at the observed generation, a serving revision and provider-derived
`https://*.run.app` origin exist, and the Invoker IAM check remains enabled.

The Application Owner marks the service with `state_owner=application` and an `application_id`
label matching the attachment owner. Protected and public-`optional` targets carry the exact
application assertion audience in the `comfforts.com/identity-audience` annotation. A target used
only for public-`none` delivery may omit it. A public-`none` registration may also address the same
application's canonical identity-capable target so an immutable predecessor remains routable after
the target gains optional identity support. That target annotation is a capability, not delivery
authority: the active registration retains a null audience and the Shared Edge emits no assertion.
An unrelated or otherwise mismatched audience remains invalid.

An unconditional `roles/run.invoker` binding must contain the configured platform edge
service-account principal. Conditional grants are not interpreted by the runtime. Any URL or state
address in the registration, unsupported adapter, malformed URN, provider failure, missing service,
mismatched scope, unready service, owner reuse, caller mismatch, prohibited audience mismatch,
disabled Invoker check, or invalid provider target closes before application delivery. Local fake
readback is not evidence that IAM, ingress, a target service, or an edge caller exists in GCP.

The Shared Edge runtime identity receives no direct invocation grant on application services. It
may create short-lived credentials for only the dedicated edge-caller service account. That caller
receives Cloud Run Viewer and Invoker only on each exact attached service, allowing the runtime to
read the named service and IAM policy and then mint an audience-bound ID token without a stored
service-account key. A project number from the typed attachment reference is accepted only when it
maps to the configured project ID; the canonical provider response must then match that exact
project ID, region, and service name.

AP-M6-W8 delivers only a successfully selected, admitted, asserted, and resolved request. Its HTTP
transport obtains a Google service-identity token for the resolved audience, preserves the
registration-derived rewritten path and raw query bytes, and never accepts a registration-supplied
URL. Request forwarding removes hop-by-hop, forwarding, visitor authorization, platform-session,
and visitor-controlled identity values before installing the edge-controlled authorization and
application assertion. Response forwarding removes hop-by-hop and application-controlled platform
identity or session behavior while preserving eligible application headers and cookies.

The same proxy supports bounded uploads, buffered responses, streaming HTTP, SSE, downloads, and
bidirectional WebSockets. It preserves an eligible WebSocket subprotocol, applies the same identity
replacement, and closes both directions on visitor disconnect, upstream close, size or rate
violation, idle or absolute timeout, or cancellation. Provider, transport, and malformed-response
failures map to coarse closed results without selecting a different attachment. Deterministic tests
exercise the production HTTP and WebSocket transports only against ephemeral process-local
loopback servers and exercise remaining failure paths through deterministic fakes. They do not
authenticate to GCP or prove deployed network behavior.

The initial `qualification-v1` request profile applies before target selection and permits lower
environment settings but no higher value without a reviewed profile change:

- ASCII methods of at most 16 bytes, raw paths of at most 4,096 bytes, and queries of at most 8,192
  bytes;
- at most 64 request headers, with an ASCII name of at most 128 bytes, a value of at most 8,192
  bytes, and at most 32,768 aggregate header bytes;
- at most 25 MiB per request body and per buffered response body;
- at most 100 MiB per streamed HTTP response, SSE connection, or WebSocket connection, with at most
  1 MiB in one WebSocket message;
- a 10-second upstream connection timeout, a 300-second non-streaming request timeout, a 300-second
  streaming idle timeout, and the already selected 55-minute absolute streaming lifetime; and
- at most 20 active requests and 10 streaming connections per edge instance, with at most four
  streams for one trusted client key.

The profile uses an in-memory, per-instance token bucket of 120 request starts per minute per
trusted client key with a burst of 40, 10 login starts per 10 minutes per key, and 20 WebSocket
messages per second with a burst of 40. It also caps all request starts at 600 per minute per
instance with a burst of 100. Client keys come only from load-balancer-authenticated metadata, are
held for at most 10 minutes, and are never logged or persisted. When trusted client metadata is
unavailable, only the instance-wide cap applies. This is bounded demo abuse resistance, not a
distributed rate-limit or WAF claim; two instances can independently permit their full limits.

Limit or saturation rejection occurs before application selection where possible, returns a closed
`413`, `429`, or protocol-appropriate close result, and records only the coarse outcome and
correlation identifier. The runtime drains or cancels bounded work and does not continue an
upstream operation after the visitor connection or platform timeout closes it. The body and header
caps remain below the selected provider limits while retaining room for provider-added metadata.
Specifically, 25 MiB is below Cloud Run's 32-MiB HTTP/1 request and buffered-response limits, the
55-minute stream lifetime is below its 60-minute request maximum, and the 32-KiB aggregate header
cap plus bounded path and query leaves room below the global external Application Load Balancer's
60-KiB combined request-header and URL limit. See the provider's
[Cloud Run quotas](https://cloud.google.com/run/quotas),
[request-timeout guidance](https://cloud.google.com/run/docs/configuring/request-timeout), and
[load-balancer quotas](https://cloud.google.com/load-balancing/docs/quotas). Larger uploads or
downloads require a later reviewed profile rather than an application-specific exception.

AP-M6-W9 adds one reserved, read-only `/_platform/status` operation. It denies access unless an
injected operator authorizer approves the request; the initial exact-session adapter compares only
the immutable issuer-and-subject pair. The response contains the bound source revision, non-secret
component version, Registration Generation number and digest, contract and compiler versions, and
coarse process-local adapter states. It contains no route table, attachment reference or target,
restricted member, operator identity, session, assertion, provider payload, state, plan, secret, or
mutation interface. Status reads the already bound generation and local observations; it cannot
load, discover, activate, reload, roll back, or change them. Exact operator identity and deployed
authorization remain infrastructure inputs.

An outer ASGI completion boundary creates one opaque correlation identifier for each HTTP request
or WebSocket connection. The same value is supplied to any application assertion and replaces any
visitor correlation header before application delivery. After the boundary closes, a typed event
can contain only source revision, generation digest, normalized application and attachment-based
route identifiers, coarse outcome, response status class or WebSocket class, bounded latency,
correlation identifier, and non-secret component versions. Stream timeout, size closure,
disconnect, cancellation, and WebSocket close update only the coarse outcome. Sink failure marks
the local sink observation degraded and never changes the visitor response.

The production event adapter writes the typed JSON object through an injected standard logger;
deterministic tests use an in-memory sink. Neither adapter accepts an arbitrary event mapping.
Provider log routing, the dedicated bucket, seven-day retention, owner-only access, and absence of
external export remain AP-M7 static configuration plus AP-M9 deployment and qualification
evidence, not AP-M6 behavior.

## <u>Fixture boundary</u>

Fixture Applications are contract consumers, not internal compiler branches or privileged platform
runtimes. Each networked fixture registers and attaches through the same active Version 2 handoff
contracts as any other application. Its runtime, synthetic data, Application Principals, Feature
Entitlements, and Fixture Application State remain outside Platform State. The in-process
reference fixture and committed Version 1 registration sequence remain historical deterministic
regression evidence; they are not the current deployed handoff path.

Contract test vectors may use synthetic application names and identities to validate schemas and
compiler behavior. They are not Fixture Applications and cannot qualify routing, identity delivery,
direct-bypass denial, lifecycle operations, or rollback. Delivery item 4 must introduce independent
fixture registrations and application-owned fixture implementations.

### Deterministic reference topology

Item 4 uses one Python standard-library, in-process request pipeline. Its external seam is one
bounded `handle(request) -> response` operation over ordinary immutable request and response values.
It opens no listening socket and performs no HTTP, DNS, TLS, filesystem, subprocess, credential, or
cloud operation. An injected clock and explicitly constructed adapters make every result
deterministic.

```text
 reviewed fixture Registration Set
                |
                v
      Registration Compiler
                |
                v
 immutable compiled generation ---> in-memory generation activation
                                           |
 synthetic request ------------------------v
                               Deterministic Reference Edge
                                 | catalogue / closed response
                                 | admission + identity assertion
                                 v
                         fixture-in-process-v1
                                 |
                                 v
                       Fixture Application State
```

The Deterministic Reference Edge is a fixture adapter for the logical Shared Edge interface. It
must derive catalogue, route, admission, attachment, and lifecycle behavior only from one compiled
generation. It may not add a route, admission exception, or catalogue entry through constructor
options or fixture-specific branching. Provider-facing behavior, network ingress, TLS, concurrency,
streaming, availability, and performance are outside this adapter and outside Fixture evidence.

The only enabled attachment adapter kind is `fixture-in-process-v1`. Its resource references use
`urn:comfforts:app-platform:fixture:<application-id>:<attachment-id>` and are inert lookup keys into
an explicitly supplied read-only attachment map. Resolution performs no import, fetch, discovery,
or dynamic execution. This selection does not define a live provider adapter or change the Version
1 attachment schema.

### Fixture Application set

The fixture qualification set contains exactly three independent applications:

| Fixture | Catalogue | Admission | Application-owned behavior |
| --- | --- | --- | --- |
| `fixture-public` | Listed | Public | Exercises both `none` and `optional` Identity Delivery while retaining anonymous access and two mounts for forwarding and longest-match checks |
| `fixture-authenticated` | Unlisted | Authenticated | Derives an application-scoped principal only after independently verifying the edge assertion |
| `fixture-restricted` | Listed | Restricted | Uses the shared synthetic Platform Member Directory and separately denies an admitted member a synthetic premium Feature Entitlement |

Each fixture has its own runtime object, mutable synthetic state, principal map, entitlement policy,
and assertion verifier inside separately constructed Fixture Application State. The platform holds
only the attachment reference and callable adapter supplied at construction. One fixture cannot
read or mutate another fixture or the platform's generation state. Finance Assistant code, data,
infrastructure, identity, state, and migration are never fixture dependencies.

### Request, catalogue, and response profile

The item 4 pipeline accepts `GET` only and applies these fixture-only limits before routing or
admission:

- an ASCII method of at most 16 bytes;
- a raw path of at most 1,024 UTF-8 bytes and query data of at most 1,024 UTF-8 bytes;
- at most 32 headers, with an ASCII name of at most 64 bytes, a value of at most 1,024 UTF-8 bytes,
  and at most 8,192 aggregate header bytes;
- an empty request body; and
- a response body of at most 65,536 UTF-8 bytes.

Unsupported methods, malformed text, duplicate security-sensitive headers, limit violations, and
non-empty bodies fail before attachment selection. These bounds qualify only this synchronous,
in-process profile. Connection, streaming, network timeout, traffic-rate, concurrency, and live
provider limits remain unresolved.

The root `/` response is UTF-8 HTML derived from the compiled catalogue. The renderer escapes every
text field for HTML and constructs each link only from the canonical registered route prefix. It
does not accept templates, raw markup, arbitrary links, attachment references, or operator data.
Deterministic tests inspect the parsed links and literal text; they do not require a browser.

Unknown, malformed, reserved, suspended, and retired paths return a closed platform
response and never invoke an attachment. Authentication failures are distinct from restricted
membership denial, but neither response reveals membership, attachment, or application-state
details. An unavailable or oversized fixture response fails only the selected application and is
never retried against another fixture.

### Synthetic identity and application verification

The fixture identity adapter recognizes only an explicit in-memory mapping from synthetic session
labels to immutable `(issuer, subject)` pairs. Those labels and identities are test data, not
credentials or an identity-provider simulation. Before routing, the edge removes every
visitor-supplied `X-Comfforts-Verified-Identity` value.

After successful protected admission, a fixture-only signer wraps the existing Version 1 Verified
Identity Context in a deterministic HMAC-SHA-256 envelope. The signer uses injected, explicitly
public test key material; it is not a production algorithm or key-management choice. Assertions
have a maximum 60-second lifetime, allow zero clock skew, and use their correlation identifier as
the replay identifier. Each protected fixture independently verifies the envelope, contract
version, signature, issuer, application-specific audience, issued and expiry times, and replay
identifier before deriving an Application Principal. A bounded 256-entry replay store removes only
expired entries and fails closed when no safe capacity remains.

Tests must call a protected fixture directly with a missing, forged, expired, wrong-issuer,
wrong-audience, cross-application, and replayed assertion and observe denial. This is evidence of
application-side assertion verification only. An in-process call cannot prove network origin
isolation, provider IAM, key protection, or denial of a live direct-origin request; those remain
Live and Adoption gates.

### Registration, activation, and lifecycle

Fixture registrations are committed, reviewed files that form complete Registration Sets. Item 4
adds no external registration endpoint, self-service registration flow, or database. A proposed
fixture change is compiled through the Version 1 compiler, then the complete generation is either
installed in an in-memory reviewed-generation collection and selected by one current-generation
pointer or rejected without changing runtime state.

Activation swaps catalogue, routes, admission, attachments, and ownership as one generation.
Rollback selects a retained, previously reviewed complete generation. It does not reverse or
delete Fixture Application State. Tests must cover initial registration, an application release
that preserves its registration, a registration update, suspension, retirement, attachment
replacement, failed activation, and rollback. A process restart deliberately loses this in-memory
activation state; persistence, concurrent writers, and an operator control plane remain later
design decisions.

This Git-reviewed, in-memory mechanism is the item 4 qualification harness, not a commitment that
future real applications must use an external API or a database. Application Adoption must select
and authorize its onboarding and operational workflow without weakening complete-generation review
or exclusive state ownership.

### Fixture evidence boundary

Fixture evidence may qualify deterministic catalogue rendering, routing, forwarding, admission,
synthetic identity delivery and application verification, application-owned entitlement denial,
lifecycle behavior, rollback, failure isolation, state isolation, limits, and redaction through the
same in-process seams used by callers. It may not qualify network reachability, DNS, TLS, OAuth,
real credentials, signing-key custody, provider resources, IAM, direct-origin network denial,
availability, performance, persistence, Application Adoption, or any Finance Assistant behavior.

This section is design authority only. No Fixture (`F`) evidence exists until a later approved item
4 plan, implementation, and evaluation record exercise these claims.

Real-application code, data, infrastructure, identity, state, and migration are never fixture
dependencies. Application migration remains under the consuming application's authority.

## <u>Configurability and extraction</u>

Canonical documents, schemas, validation code, test vectors, and tests use project-relative paths
inside the App Platform root. Contract identifiers do not encode the containing repository, a cloud
project, a deployment region, or Finance Assistant. Default verification performs no network or
credential access and no cloud, DNS, identity, or application mutation.

Extraction to a dedicated repository changes the project root but not contract identifiers,
compiler behavior, paths relative to that root, or ownership boundaries.

## <u>Historical pre-implementation boundary — superseded</u>

The original contract-and-fixture design stopped before the following work. This list is preserved
only as historical scope evidence; the active AP-M9 sections above and the implementation plan
record which items are now implemented:

- environment profiles, lifecycle contracts, the operator workflow, provider command seams,
  deployment progress, integration bundles, attachment bundles, or qualification evidence;
- the deployable bootstrap/foundation/edge Terraform phases, operation identities, backend objects,
  state migration, provider composition entry point, container definitions, or IAM grants;
- OAuth client registration values, Firestore session configuration, KMS key versions, secret
  versions, credentials, DNS records, certificates, traffic changes, or provider readback;
- a deployed catalogue or Shared Edge, provider-qualified attachment, Live qualification result,
  destruction result, or production environment; or
- Finance Assistant registration, Application Adoption, state transfer, migration, access
  expansion, production cutover, or script change.

AP-M6 now resolves the network framework, dependency policy, and initial header, body, timeout, and
abusive-traffic limits as implementation authority. Local runtime and adapter implementation does
not make provider resources or Live behavior implemented or qualified.

The versioned schemas and deterministic validation from that delivery remain part of the current
design where later authority did not replace them. This historical boundary does not override the
active status and claim discipline in `docs/README.md`.

## <u>Design acceptance boundary</u>

This system design remains documentation authority rather than operational evidence. AP-M3 provides
revision-scoped Contract evidence that the Version 1 schemas and deterministic reference compiler
satisfy their declared offline gate. AP-M4 supplies the Fixture evidence defined by Version 0.2.
Version 0.3 selects the initial GCP Live topology, Version 0.4 selects its identity trust profile,
Version 0.5 selects state and operator authority, Version 0.6 selects activation, DNS, readback, and
rollback behavior, Version 0.7 selects observability, evidence, incident, and cost controls, and
Version 0.8 selects the AP-M6 network module, dependency, and bounded-request profile. Version 0.9
selects the AP-M7 root interfaces, configuration contracts, pinned toolchain, static verification,
and inert workflow-template profile. Version 1.0 proposes the AP-M8 protected-source, environment,
federation, and root-operation identity profile without configuring it. Version 1.1 proposes the
AP-M8 backend-bootstrap and state-lineage profile without creating a bucket, state, or lineage.
Version 1.2 proposes the AP-M8 repository-support dependency break, exact initial-deployment order,
dark-candidate boundary, separate DNS/TLS checkpoint, and partial-failure stops without building,
publishing, deploying, or activating anything.
Version 1.3 proposed the now-superseded deployment-evidence bundle, root-scoped reducers, isolated
finalizer, redaction boundary, and mandatory outcomes without collecting evidence or reading a
provider. Version 1.5 supersedes the unexecuted AP-M8 path with the AP-M9 interactive lifecycle,
environment, bundle, application-handoff, qualification, and destruction design. None supplies
provider, network, identity, deployment, or Live evidence. Adoption qualification remains a later
application-owned gate.

## <u>Design trace</u>

| Design area | Requirements | Decisions |
| --- | --- | --- |
| Shared Edge and catalogue | AP-PR-001, AP-PR-003; AP-QR-002, AP-QR-006 | ADR-001, ADR-002 |
| Registration, routing, and compiled generations | AP-PR-002, AP-PR-003, AP-PR-007; AP-QR-004, AP-QR-006 | ADR-002 |
| Attachments and exclusive ownership | AP-PR-002, AP-PR-007, AP-PR-008; AP-QR-001, AP-QR-003 | ADR-001, ADR-002, ADR-004, ADR-007 |
| Admission, verified identity, and platform membership | AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008; AP-QR-002 | ADR-003, ADR-004, ADR-006, ADR-015 |
| Lifecycle, failure, and rollback | AP-PR-003, AP-PR-007, AP-PR-008; AP-QR-005, AP-QR-006 | ADR-002, ADR-004, ADR-008 |
| Fixture and adoption boundary | AP-PR-008, AP-PR-009; AP-QR-003, AP-QR-004, AP-QR-006 | ADR-004 |
| Initial GCP Live topology and Cloud Run attachments | AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-002, AP-QR-003, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-005 |
| AP-M6 network module and bounded-request profile | AP-PR-001 through AP-PR-008; AP-QR-002 through AP-QR-006 | ADR-001 through ADR-006, ADR-008, ADR-009 |
| Terraform state and operator authority | AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-004, ADR-007 |
| AP-M7 Terraform configuration profile | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 |
| Historical AP-M8 proposal, superseded before execution | AP-PR-001 through AP-PR-009; AP-QR-001 through AP-QR-006 | ADR-001 through ADR-009 |
| AP-M9 interactive environment lifecycle | AP-PR-001 through AP-PR-012; AP-QR-001 through AP-QR-009 | ADR-001 through ADR-015 |
| Observability, evidence, incidents, and cost | AP-PR-001, AP-PR-003, AP-PR-005, AP-PR-007, AP-PR-008; AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006 | ADR-001, ADR-002, ADR-003, ADR-004, ADR-009 |
