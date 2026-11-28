# Adopt a real application

Status: AP-M9-W12 application-neutral staging handoff; the closed staging target-stage readback is
implemented by Slice 1; ADR-017 Version 3 complete attachment-set contracts are implemented by
Slice 2, atomic multi-target projection is implemented by Slice 3, and the fourth fixture
application is implemented by Slice 4; Slice 5 implements its separate qualification interface but
has not run its Candidate or Accepted operation; no real application is selected or authorized
until matching authority exists in both repositories

This runbook explains how a real application will join one deployed App Platform environment after
the application repository has approved its own adoption requirements, architecture, migration,
tests, and release. It describes the current platform contract and the responsibilities on both
sides of the handoff. It does not authorize a real deployment merely because the commands and
contracts exist.

Do not use the Fixture Application Terraform roots or `fixture-handoff` for a real application.
Apps Platform does not deploy or destroy a real application's runtime, data, secrets, image,
Terraform state, or application-specific permissions. The application repository must own those
operations and produce the application side of the handoff.

## Current readiness boundary

AP-M9-W11 completed Accepted Source staging platform and fixture qualification at
`b43333756b509d0f35cb82938a13f6abc459f7c4`. AP-M9-W12 now permits selection of one real staging
application only through matching platform and application-repository authority. Before using this
procedure, all of these must be true:

- the selected Platform Environment is deployed and qualified under the required Source Authority;
- the application repository has accepted its own adoption and rollback plan;
- the application project, runtime, state, secrets, data, and release remain application-owned;
- the application implements the Version 3 integration, complete attachment-set, and
  registration-intent contracts plus the Version 2 Verified Identity Context contract; and
- the platform's Cloud Run target readback accepts the closed, project-independent staging target
  stages `environment=qualification` and `environment=staging`, while rejecting a missing or other
  label; and
- the platform has implemented and deterministically verified the ADR-017 Version 3 schemas,
  compatibility loading, complete-set relationship validation, every-target provider readback, and
  atomic Version 2 registration projection; and
- the separate `fixture-multi-attachment` qualification passes against the exact readable
  Accepted Source platform qualification, complete fourth-fixture handoff, two target references,
  and active Registration Generation without replacing platform qualification status.

These are the remaining fixture-qualification and cross-owner prerequisites in W12. Stop before
a real deployment until the ordered slices merge, the complete repository gate passes, and the
separate fixture result is readable. The operator accepts a complete V2 family by default or one
explicitly selected complete V3 family. The fourth fixture is implemented in the repository, but
that implementation is not provider-backed or Live qualification evidence.

## Ownership through the handoff

| Platform Operator owns | Application Owner owns |
| --- | --- |
| Platform Environment deployment and qualification | Application adoption decision and release |
| Application-project Shared VPC connection | Application project, runtime, image, state, and data |
| Platform Integration Bundle | Bundle consumption and complete Application Attachment Bundle |
| Shared Edge, route admission, Platform Sessions, and assertion signing | Assertion verification and Application Principal mapping |
| Registration validation and complete-generation activation | Application users, roles, permissions, and Feature Entitlements |
| Platform detachment and terminal retirement | Runtime replacement, rollback, and destruction |

Neither bundle transfers resource ownership. The platform does not read application Terraform
state, and the application does not read Platform State.

## Choose the stable application identifier

`application_id` is an Apps Platform identifier, not a field required by Cloud Run itself. Choose
it once during adoption and keep it stable for the application's lifetime.

It must:

- contain 3 through 63 lowercase letters, digits, or hyphens;
- begin with a lowercase letter and end with a lowercase letter or digit;
- be unique within the Platform Environment; and
- remain reserved through detachment and retirement.

The identifier binds all of these values:

- `APPLICATION_ID` passed to platform handoff commands;
- `application_id` in the Platform Integration Bundle, Application Attachment Bundle, and
  registration intent;
- `owner_application_id` in the target attachment;
- the Cloud Run service label `application_id=<application-id>`;
- the assertion audience
  `urn:comfforts:app-platform:audience:<application-id>` when identity delivery is enabled; and
- application ownership within every complete Registration Generation.

The Cloud Run service name may differ from `application_id`. The target reference records the
actual project number, region, and service name, while the required service label proves which
application owns that target. Do not change an identifier to represent an application release,
Cloud Run revision, environment, display name, or catalogue title.

## Select admission and identity delivery

Choose one supported pair before requesting the integration bundle:

| Admission Mode | Identity Delivery | Application behavior |
| --- | --- | --- |
| `public` | `none` | Accept anonymous traffic and receive no Platform Identity. |
| `public` | `optional` | Accept anonymous traffic; accept verified Platform Identity after deliberate platform login. |
| `authenticated` | `required` | Require a valid Platform Identity; platform membership is irrelevant. |
| `restricted` | `required` | Require a valid Platform Identity and current environment membership at the Shared Edge. |

Catalogue visibility is a separate decision. `listed` or `unlisted` does not change admission,
identity delivery, or application permission.

## Prepare the platform handoff

Run platform commands from the Apps Platform repository. Run application deployment commands from
the application repository. Do not switch an ambient gcloud project to cross the ownership
boundary; every provider command must name its project explicitly.

Connect the existing application project once per Platform Environment:

```bash
make platform-connect-project \
  ENVIRONMENT=<staging-or-production> \
  APPLICATION_PROJECT_ID=<application-project-id>
```

Read the deployed platform revision and active Registration Generation:

```bash
make platform-status ENVIRONMENT=<staging-or-production>
```

Check the proposed handoff without publishing a bundle:

```bash
make application-handoff-check \
  ENVIRONMENT=<staging-or-production> \
  APPLICATION_PROJECT_ID=<application-project-id> \
  APPLICATION_ID=<application-id> \
  ACCESS_MODE=<public|authenticated|restricted> \
  IDENTITY_DELIVERY=<none|optional|required> \
  HANDOFF_VERSION=3 \
  ROUTE_INTENT=/<route-prefix> \
  PLATFORM_SOURCE_REVISION=<active-platform-revision> \
  PLATFORM_GENERATION=<active-registration-generation>
```

Resolve every blocker, then generate the canonical application-scoped bundle with the same exact
values:

```bash
make platform-outputs \
  ENVIRONMENT=<staging-or-production> \
  APPLICATION_PROJECT_ID=<application-project-id> \
  APPLICATION_ID=<application-id> \
  ACCESS_MODE=<public|authenticated|restricted> \
  IDENTITY_DELIVERY=<none|optional|required> \
  HANDOFF_VERSION=3 \
  ROUTE_INTENT=/<route-prefix> \
  PLATFORM_SOURCE_REVISION=<active-platform-revision> \
  PLATFORM_GENERATION=<active-registration-generation>
```

Inspect the generated Platform Integration Bundle. Give its exact file content and digest to the
Application Owner through an application-approved private handoff. It is non-secret, but it is
environment-, generation-, application-, and source-bound and must not be edited.

`HANDOFF_VERSION=3` makes this command write a Version 3 bundle that declares one required root
attachment and at most fifteen optional additional attachments. Omitting it retains the Version 2
default used by the three qualified fixtures. The platform bundle remains application-scoped; it
does not prescribe service names, attachment IDs, optional mount paths, or an application
architecture.

## Deploy the application-owned Cloud Run services

The application repository consumes the bundle and deploys one or more runtimes through its own
exact plan, state, approval, and readback. Every resulting Cloud Run service must satisfy all of
these conditions independently:

- use the application project ID and provider-assigned project number from the bundle;
- run in the bundle's exact region;
- attach directly to the bundle's Shared VPC network and application subnet;
- send all egress through that network and its platform-owned NAT;
- allow internal ingress only and keep Cloud Run's Invoker IAM check enabled;
- have no `allUsers` or `allAuthenticatedUsers` Invoker grant;
- grant the bundle's exact edge-caller service account unconditional `roles/run.viewer` and
  `roles/run.invoker` on only that selected service;
- carry `state_owner=application` and `application_id=<application-id>` labels;
- carry `environment=qualification` for a staging candidate or `environment=staging` for a staging
  release, regardless of whether the connected application project is a fixture or real project;
- become provider-ready with a serving revision; and
- retain application-owned deletion protection, scaling, runtime identity, secrets, data, and
  release controls.

When Identity Delivery is `optional` or `required`, every service must also carry the exact bundle
audience in both places checked by platform readback:

- annotation `comfforts.com/identity-audience`; and
- environment variable `APP_PLATFORM_ASSERTION_AUDIENCE`.

For public Identity Delivery `none`, both values are absent. Do not invent an audience, use another
application's audience, or use the Cloud Run invocation-token audience as Visitor identity.

The application returns one Version 3 Application Attachment Bundle containing the exact
integration-bundle digest, application source revision, and required singular `target` for the
application root. It may also contain an `additional_attachments` array sorted by stable unique
`attachment_id`; each additional entry carries one target posture. A canonical Cloud Run target
is:

```text
urn:comfforts:app-platform:gcp:cloud-run:<project-number>:<region>:<service-name>
```

The Application Owner also returns one Version 3 registration intent containing the application
ID, Admission Mode, Identity Delivery, catalogue visibility, title, summary, and the required root
`attachment_id`, `mount_path`, and `forwarding_mode`. The root mount must be `/`. The intent may
also contain `additional_attachment_bindings`, sorted by `attachment_id`, for the optional targets.
The two optional attributes must both be absent or contain the exact same additional IDs, cannot
reuse the root ID, and may contain at most fifteen entries. Duplicate or ambiguous mounts are
invalid. Omitting both optional attributes is a valid root-only handoff.

A separately deployed frontend and backend remain one Registered Application. A representative
shape is:

| Attachment ID | Application-owned target | Application-relative mount |
| --- | --- | --- |
| required `web` root | frontend Cloud Run service | `/` |
| optional additional `api` | backend Cloud Run service | `/api` |

The application chooses these identifiers. Longest segment-bounded mount selection sends `/api`
and its subpaths to `api` while `/apix` remains on the required root `web` attachment. Do not
create a second application merely to represent the backend, and do not require the frontend to
proxy it unless the application's own architecture deliberately chooses that pattern.

The required root and all optional additional attachments in the initial Version 3 family share
the application project, region, Shared VPC connection, owner, edge caller, Admission Mode,
Identity Delivery, and assertion audience. A need for per-attachment values is a stop condition and
new design work. These documents contain no credential, secret, Terraform state, application data,
provider token, or member record.

Before the first real adoption, the implemented `fixture-multi-attachment` fourth platform-owned
fixture must be qualified without changing `fixture-public`, `fixture-authenticated`, or
`fixture-restricted`. The fourth fixture is authenticated with required Identity Delivery and
unlisted catalogue visibility. Its single independent Application State root owns the required
`web` frontend Cloud Run target at `/` and a distinct dummy `api` backend target at `/api`.

Run its implemented `fixture-qualify` interface separately from `platform-qualify`. The qualifier binds
the exact readable platform result, fixture source, Version 3 handoff, both targets, and active
Registration Generation; it records separate least-data fixture evidence and status. It does not
rerun the three-fixture platform suite, change platform qualification status, exercise member
lifecycle, or qualify Finance Assistant. Real-application adoption requires both exact results and
cannot use either as a substitute for the other.

## Build application identity and permissions

Cloud Run IAM authenticates the Shared Edge workload. It does not identify the Visitor. Visitor
identity arrives separately in the `X-Comfforts-Verified-Identity` header only when the selected
Identity Delivery policy allows it.

For `authenticated` and `restricted` routes, the Shared Edge starts platform login before the
request reaches the application. A public `optional` application remains reachable anonymously and
must offer an explicit visitor action, such as a **Sign in with the platform** link to:

```text
/_platform/login?return_to=/<application-route-or-subpath>
```

URL-encode the platform-relative `return_to` value and keep it under the registered route. The
Shared Edge owns the Google authorization request, callback, OAuth client secret, token validation,
Platform Session, and return-location validation. The application must not receive or process the
Google authorization code, Google token, or platform OAuth client secret. After login, the returned
request reaches the application with the short-lived platform assertion. The corresponding
platform logout link is `/_platform/logout?return_to=/<application-route-or-subpath>`; it removes
the Platform Session but does not promise to sign the Visitor out of Google.

Every attachment that consumes identity must treat that header as untrusted input until it
independently verifies:

1. the Version 2 contract shape;
2. the ES256 signature using the bundle's HTTPS JWKS URI;
3. the exact platform issuer from the bundle;
4. the exact application audience from the bundle;
5. issued-at, expiry, and allowed clock skew; and
6. key selection and refresh within the platform's bounded caching rules.

Failure to obtain current keys or validate any field fails closed when identity is required. A
public `optional` application continues anonymously when the header is absent, but it must reject an
invalid header rather than silently treating it as anonymous. Public `none` must never construct a
Platform Identity.

After successful verification, derive or look up an immutable Application Principal using the
verified issuer and subject together. Email is not the principal key. The application may retain a
separate application-owned user profile and display email under its own privacy and retention
rules, but a changed email must not create or transfer identity implicitly.

The application then applies its own authorization model:

```text
verified platform issuer + subject
    -> application-owned principal
    -> application-owned user/status
    -> application-owned roles or permissions
    -> resource- and feature-specific authorization decision
```

`platform_member: true`, when present, means only that the current Visitor passed the platform's
environment-wide restricted membership check. It is not an application role, administrator flag,
provider permission, subscription plan, or Feature Entitlement. An admitted user may still be
denied any application feature. Application permission changes and revocation remain in the
application's own runtime and data lifecycle.

A public application may instead use an independent application-owned OAuth client. That identity,
session, user database, and account-linking process remain separate. Do not merge it with Platform
Identity unless the application adopts an explicit, reviewed account-linking flow.

## Qualify the candidate before the staging release

The selected real application first deploys its Candidate Source targets with
`environment=qualification`. Under separately approved joint authority, the Platform Operator
registers the complete set, exercises every declared application-adoption check, records
revision-bound Candidate Qualification in both repositories, and restores the reviewed
predecessor. A failed or missing candidate result blocks merge and release.

After that exact candidate becomes Accepted Source, the Application Owner reconciles every target
with `environment=staging`. The Platform Operator must read the prior candidate result and repeat
the complete registration, posture, route, identity, application-authorization, isolation,
rollback, and restoration gate before recording staging release qualification. Fixture projects
may also carry `staging`, and real projects may carry `qualification`; project ownership is not a
label policy. Neither valid label proves that its corresponding evidence gate passed.

## Inspect and activate the registration

The Platform Operator inspects the exact three-document family without editing it, then runs:

```bash
make platform-register \
  ENVIRONMENT=<staging-or-production> \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v3.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.v3.json \
  REGISTRATION_INTENT=/private/path/registration-intent.v3.json
```

Registration must verify the current platform generation, the required root and its `/` binding,
the exact equality of optional additional target and binding IDs, the connected project, and every service's environment label, project, region,
ownership labels, internal ingress, Shared VPC posture, all-traffic egress, edge-caller IAM,
identity audience, and readiness before projecting the set into the existing Version 2
Application Registration and publishing one complete immutable Registration Generation. One
failed target activates no subset. A prepared bundle or successful application deployment alone
does not make a route active.

After activation, inspect platform status and every application mount. Verify longest-match
selection, anonymous, login, restricted membership, and application permission behavior applicable
to the selected policy. Direct `run.app` invocation of every target must remain unavailable to
ordinary Visitors.

## Update, detach, destroy, or retire

- An application release remains application-owned. Produce a new complete attachment bundle and
  registration intent when its source revision, any target, attachment membership, mount, or
  integration binding changes. Always include the root. When optional attachments exist, include
  every unchanged optional entry and register root plus optionals atomically.
- Run `platform-detach` before destroying or replacing a currently registered target. Detachment
  suspends routing while preserving the application ID and route.
- Destroy application assets only through the application repository after detachment is read back.
- Redeploy through a current Platform Integration Bundle and register the complete replacement set
  to reactivate the suspended application.
- Use `platform-retire` only for permanent removal. Retirement is terminal and retains an ID and
  route tombstone.

Do not let platform destruction implicitly destroy Application State. Every active application must
be detached, and its Application Owner must complete the separately governed application lifecycle.

## Operator completion checklist

- The application repository owns and records its adoption approval, plans, state, and rollback.
- `application_id` is stable and matches every contract and Cloud Run ownership label.
- The required root attachment is present and bound to `/`; the optional additional attributes are
  both absent or contain the exact same unique IDs and complete desired additional set.
- Every target's project connection, network, subnet, environment label, ingress, egress, IAM,
  service readiness, and audience pass platform readback.
- The selected real application's exact Candidate Source revision passed Candidate Qualification
  with `environment=qualification` before its Accepted Source targets were reconciled with
  `environment=staging` and the release gate was repeated.
- Every identity-consuming target independently verifies platform assertions before constructing a
  principal.
- Application permissions are tested independently from platform admission and membership.
- The bundle family is canonical, current, relationship-valid, inspected, and secret-free.
- Registration activates one complete generation only after all targets pass and without changing
  another application's ownership.
- Every mount, longest-match selection, admission, identity, direct-origin denial, target failure,
  detachment, rollback, and application destruction has the evidence required by the application's
  adoption authority.

Until the readiness boundary at the beginning of this runbook is closed, this checklist is a
design and review aid rather than proof that a real application may be deployed.
