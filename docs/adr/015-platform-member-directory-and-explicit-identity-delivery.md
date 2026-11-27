# ADR-015 · Use a platform-owned member directory and explicit identity delivery

Status: Accepted; implementation integrated; Candidate Source qualification passed at revision
`d8fdb8afb2048e87b591ae400d7807a38784fd5c`; final post-reconciliation rerun and freeze remain

Requirements: AP-PR-004, AP-PR-005, AP-PR-006, AP-PR-008, AP-PR-010, AP-PR-011,
AP-QR-001, AP-QR-002, AP-QR-004, AP-QR-006 through AP-QR-009

Amends: ADR-003, ADR-006, ADR-008, and ADR-012 where they place restricted membership in an
Application Registration or Registration Generation, make public identity delivery implicit, or
allow a bundle to omit an explicit identity-delivery policy. Their remaining admission,
application-authorization, session, assertion, generation, and cross-owner bundle decisions remain
accepted.

## Context

The implemented Version 1 model compiles exact issuer-and-subject members into each restricted
Application Registration. That treats membership as application configuration, requires a new
Registration Generation for every membership change, and gives each restricted application a
different member set. The intended product instead has one owner-managed platform membership
boundary shared by every restricted route.

Public admission also needs an explicit privacy choice. A public application may stay anonymous,
use its own independent OAuth client, or offer Platform Identity to a visitor. The platform must
not deliver identity merely because a host-wide Platform Session happens to exist.

Google Auth Platform test users, Cloud IAM or IAP accessors, application user databases, and
application Feature Entitlements answer different questions. None is a substitute for the App
Platform member directory.

## Decision

Each Platform Environment owns one Platform Member Directory in Firestore. Terraform owns the
database configuration, indexes if required, and least-privilege runtime IAM as Platform State;
member records are remote platform operational data changed only through the platform member
lifecycle. They are never Terraform inputs, Git configuration, Registration Set fields, or
Registration Generation content.

The directory keys members by the verified Google issuer and immutable subject. Email, display
name, domain text, browser account order, and the active Cloud Operator account are not membership
keys. Email may be displayed transiently during a confirmed enrollment flow but does not enter the
member key, public bundle, ordinary terminal summary, evidence, or application assertion.

Membership is environment-wide. An active member is eligible for every `restricted` route in that
environment; an absent, suspended, removed, unreadable, or inconsistent member is not. The
directory does not store application principals, application users, product roles, provider
rights, or Feature Entitlements. Applications continue to derive their own principal and decide
all application-specific authorization.

Every Application Registration declares both Admission Mode and Identity Delivery:

| Admission Mode | Allowed Identity Delivery | Admission behavior |
| --- | --- | --- |
| `public` | `none` or `optional` | Anonymous access remains allowed. `optional` permits an application to offer platform login and receive identity for a visitor with a valid Platform Session; it never forces login. |
| `authenticated` | `required` | A valid platform-authenticated Google identity is required; platform membership is not required. |
| `restricted` | `required` | A valid platform-authenticated Google identity and an active Platform Member Directory entry are both required. |

`none` is the default for a migrated public registration. The Shared Edge strips visitor-supplied
identity headers in every mode and issues an application-audience-bound assertion only when the
registration permits delivery and verified identity is present. A public application using its own
OAuth client owns that separate identity, client, secret, session, user records, and account-linking
process. It must not implicitly merge that identity with Platform Identity.

The versioned assertion supplies only the current visitor's relevant signed context. A Version 2
identity contract may project positive membership context for that visitor, but it never exposes
the directory, another member, application permissions, or Feature Entitlements. Membership is
asserted only after a positive current lookup. A directory failure never fabricates a member:
`restricted` admission fails closed, while public or authenticated identity remains governed by
its own admission rule and cannot infer membership from an absent projection.

## Operator lifecycle

Platform deployment creates or reconciles the directory infrastructure and runtime access but
does not silently enroll a member. An empty directory is a valid deployed state: public and
authenticated routes can operate, every restricted route denies admission, and restricted Live
qualification remains unavailable.

The Platform Owner enrolls deliberately after deployment through a separate
`platform-member-bootstrap-owner` operation. It must:

1. verify the selected environment and a remotely empty member directory;
2. distinguish the active Cloud Operator from the Google Visitor identity being enrolled;
3. obtain the prospective owner identity through a separately confirmed platform browser flow;
4. show a non-sensitive exact action and require explicit confirmation;
5. create one initial owner member idempotently; and
6. read back the remote result without logging identity claims or treating local state as authority.

If the remote directory is not empty, owner bootstrap refuses to create or replace a member. An
empty or recovered local `.platform-operator` directory never permits owner rebootstrap over
remote membership. Proposed ADR-016 discusses operator-state reconstruction but cannot alter this
accepted remote-authority boundary while it remains unaccepted.

Platform-owned member operations must support bounded status, add, suspend, reactivate, and remove
journeys. They name one environment, verify the operator session and remote predecessor, require
confirmation for mutation, are idempotent for an identical request, perform exact readback, and
never compile a Registration Generation or deploy an application. The enrollment mechanism must
obtain a verified issuer and subject; an operator-entered email address alone is insufficient.

Membership change takes effect at the next request or newly established streaming connection. The
initial product does not promise to terminate a connection already admitted before suspension or
removal.

## Contract and migration boundary

The change requires Version 2 registration, compiled-generation, integration-bundle,
attachment-handoff, and verified-identity contracts. Version 1 remains historical and readable but
cannot express the accepted model. Migration maps public registrations to Identity Delivery
`none`, authenticated and restricted registrations to `required`, and removes every per-registration
member list. A public application may change to `optional` only through an explicit reviewed
registration update.

The platform must not activate the new admission model until the directory infrastructure, runtime
IAM, Version 2 compiler and consumers, owner lifecycle, deterministic migration, and rollback
behavior are complete. Existing W9 Candidate Source staging evidence remains truthful evidence of
the Version 1 model and cannot qualify ADR-015. Separate Version 2 Candidate Source qualification
passed at revision `d8fdb8afb2048e87b591ae400d7807a38784fd5c`. Because the documentation
reconciliation changes the exact source revision, the resulting integration head must repeat that
qualification before freeze. The AP-M9-W11 accepted staging operation follows completed AP-M9-W10
implementation and final candidate qualification.

## Considered alternatives

- **Keep a member set in every restricted registration:** rejected because membership would remain
  application-specific configuration and every change would require generation activation.
- **Use OAuth test users as platform membership:** rejected because the provider list controls
  consent eligibility for one OAuth client and is not an application admission system.
- **Use IAP IAM accessors, a Google Group, or a Cloud Identity group initially:** rejected because
  those introduce a separate provider authorization and administration boundary instead of the
  registration-derived Shared Edge admission model. They may be reconsidered through a later ADR.
- **Let each restricted application authorize its own users:** rejected because the Shared Edge
  could not enforce platform-wide restricted admission before forwarding the request. Application
  feature authorization nevertheless remains application-owned.
- **Always deliver Platform Identity to public applications:** rejected because public admission
  does not imply an identity-processing purpose or visitor consent.
- **Enroll the active operator automatically during platform deployment:** rejected because cloud
  operation authority and Visitor identity are distinct, and deployment must not create membership
  as an ambient side effect.

## Consequences

- Restricted membership changes no longer redeploy applications or activate Registration
  Generations.
- Firestore directory availability becomes a restricted-admission dependency and must fail closed.
- The platform owns a deliberately small amount of identity operational data but still does not own
  application users, principals, roles, or entitlements.
- Public applications gain a clear privacy-preserving choice between no Platform Identity and
  optional Platform Identity.
- Applications consuming Platform Identity must adopt and verify the Version 2 assertion contract;
  applications using their own identity remain independently governed.
- Staging must be redeployed and requalified with an explicitly bootstrapped owner and a second
  member allow/deny lifecycle before Accepted Source qualification can proceed.
