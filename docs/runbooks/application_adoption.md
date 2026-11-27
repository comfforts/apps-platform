# Adopt a real application

Status: application-owner handoff reference; no real Application Adoption is currently authorized
or qualified

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

Real Application Adoption remains separately governed after the platform's accepted staging and
production-readiness work. Before using this procedure for a live application, all of these must be
true:

- the selected Platform Environment is deployed and qualified under the required Source Authority;
- the application repository has accepted its own adoption and rollback plan;
- the application project, runtime, state, secrets, data, and release remain application-owned;
- the application implements the Version 2 integration, attachment, registration-intent, and
  Verified Identity Context contracts; and
- the platform's Cloud Run target readback accepts the selected real environment rather than the
  currently hardcoded `environment=qualification` fixture label.

The last condition is not implemented today. Stop before a real deployment until it is replaced by
an environment-derived, validated staging or production value and qualified through the applicable
delivery authority.

## Ownership through the handoff

| Platform Operator owns | Application Owner owns |
| --- | --- |
| Platform Environment deployment and qualification | Application adoption decision and release |
| Application-project Shared VPC connection | Application project, runtime, image, state, and data |
| Platform Integration Bundle | Bundle consumption and Application Attachment Bundle |
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
  ROUTE_INTENT=/<route-prefix> \
  PLATFORM_SOURCE_REVISION=<active-platform-revision> \
  PLATFORM_GENERATION=<active-registration-generation>
```

Inspect the generated Platform Integration Bundle. Give its exact file content and digest to the
Application Owner through an application-approved private handoff. It is non-secret, but it is
environment-, generation-, application-, and source-bound and must not be edited.

## Deploy the application-owned Cloud Run service

The application repository consumes the bundle and deploys its own runtime through its own exact
plan, state, approval, and readback. The resulting Cloud Run service must satisfy all of these
conditions:

- use the application project ID and provider-assigned project number from the bundle;
- run in the bundle's exact region;
- attach directly to the bundle's Shared VPC network and application subnet;
- send all egress through that network and its platform-owned NAT;
- allow internal ingress only and keep Cloud Run's Invoker IAM check enabled;
- have no `allUsers` or `allAuthenticatedUsers` Invoker grant;
- grant the bundle's exact edge-caller service account unconditional `roles/run.viewer` and
  `roles/run.invoker` on only the selected service;
- carry `state_owner=application` and `application_id=<application-id>` labels;
- become provider-ready with a serving revision; and
- retain application-owned deletion protection, scaling, runtime identity, secrets, data, and
  release controls.

When Identity Delivery is `optional` or `required`, the service must also carry the exact bundle
audience in both places checked by platform readback:

- annotation `comfforts.com/identity-audience`; and
- environment variable `APP_PLATFORM_ASSERTION_AUDIENCE`.

For public Identity Delivery `none`, both values are absent. Do not invent an audience, use another
application's audience, or use the Cloud Run invocation-token audience as Visitor identity.

The application returns a Version 2 Application Attachment Bundle containing the exact integration
bundle digest, application source revision, and target posture. Its canonical Cloud Run target is:

```text
urn:comfforts:app-platform:gcp:cloud-run:<project-number>:<region>:<service-name>
```

The Application Owner also returns a Version 2 registration intent containing the application ID,
Admission Mode, Identity Delivery, catalogue visibility/title/summary, attachment ID, mount path,
and forwarding mode. These documents contain no credential, secret, Terraform state, application
data, provider token, or member record.

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

The application must treat that header as untrusted input until it independently verifies:

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

## Inspect and activate the registration

The Platform Operator inspects the exact three-document family without editing it, then runs:

```bash
make platform-register \
  ENVIRONMENT=<staging-or-production> \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v2.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.v2.json \
  REGISTRATION_INTENT=/private/path/registration-intent.v2.json
```

Registration must verify the current platform generation, every bundle relationship, the connected
project, provider-ready service, ownership labels, internal ingress, Shared VPC posture, edge-caller
IAM, and exact identity audience before publishing and activating one complete immutable
Registration Generation. A prepared bundle or successful application deployment alone does not
make a route active.

After activation, inspect platform status and the application route. Verify anonymous, login,
restricted membership, and application permission behavior applicable to the selected policy.
Direct `run.app` invocation must remain unavailable to ordinary Visitors.

## Update, detach, destroy, or retire

- An application release remains application-owned. Produce a new attachment bundle when its source
  revision, target, or integration binding changes, then register the replacement.
- Run `platform-detach` before destroying or replacing a currently registered target. Detachment
  suspends routing while preserving the application ID and route.
- Destroy application assets only through the application repository after detachment is read back.
- Redeploy through a current Platform Integration Bundle and register the replacement attachment to
  reactivate the suspended application.
- Use `platform-retire` only for permanent removal. Retirement is terminal and retains an ID and
  route tombstone.

Do not let platform destruction implicitly destroy Application State. Every active application must
be detached, and its Application Owner must complete the separately governed application lifecycle.

## Operator completion checklist

- The application repository owns and records its adoption approval, plans, state, and rollback.
- `application_id` is stable and matches every contract and Cloud Run ownership label.
- The project connection, network, subnet, ingress, egress, IAM, service readiness, and audience pass
  platform readback.
- The application independently verifies platform assertions before constructing a principal.
- Application permissions are tested independently from platform admission and membership.
- The bundle family is canonical, current, relationship-valid, inspected, and secret-free.
- Registration activates one complete generation without changing another application's ownership.
- Route, admission, identity, direct-origin denial, detachment, rollback, and application destruction
  have evidence required by the application's adoption authority.

Until the readiness boundary at the beginning of this runbook is closed, this checklist is a
design and review aid rather than proof that a real application may be deployed.
