# App Platform glossary

Status: platform requirements and decision vocabulary; no runtime behavior is implied.

## App Platform

The separately governed system intended to own the shared application catalogue and edge for a
configured hostname. The current governance foundation implements no runtime or cloud resource.

## Platform Environment

One isolated deployment of the shared platform for a configured hostname, project, state,
identity, OAuth, DNS/TLS, and evidence scope. Staging and production are different Platform
Environments even when they use the same implementation.

## Environment Profile

A small committed non-secret document containing stable owner decisions for one Platform
Environment. It is not an inventory of generated resources, a credential source, or an operator-
maintained deployment manifest.

## Deployment Specification

The canonical, digest-bound proposal produced by preparation for one environment and operation. It
fixes scope, stage order, allowed mutations, declared stage-output dependencies, checkpoints,
readback, and failure behavior before deployment or destruction begins.

## Execution Journal

A machine-generated, append-only record of one lifecycle execution, including stage inputs,
digests, outcomes, declared outputs, manual acknowledgements, and resume position. It is not
hand-authored authority and contains no credential, secret payload, Terraform state, or raw
provider response.

## Terraform Phase

One bounded bootstrap, platform-foundation, or Shared Edge configuration step. Foundation and
Shared Edge are different phases of the same Platform State root and lineage, not independent
owners or backends.

## Backend Declaration

A generated non-secret Terraform backend block binding one exact root lineage to its reviewed GCS
bucket and prefix. Rendering a declaration does not initialize, migrate, read, or write a backend.

## Operator Session

One short-lived human-authenticated local session verified against the selected environment,
provider project, reviewed source, and lifecycle scope. It contains no stored service-account key
and does not make an out-of-band provider action reviewed.

_Avoid_: Operation authority, operation identity, impersonation profile

## Operator Invocation

The Platform Owner's deliberate execution of one named lifecycle operation against one selected
environment. For an ordinary reversible staging creation or update, the invocation and the exact
in-process specification and plan confirmations together authorize that execution; a separate
out-of-band approval is not another safety boundary. Destruction, purge, ownership transfer,
production cutover, and scope expansion remain separately governed decisions.

## Accepted Source

The reviewed source revision on the repository's current protected main branch. Accepted Source is
the only source authority that can qualify a Platform Environment for normal use or operate on
production.

## Candidate Source

A clean pushed pull-request revision admitted only for staging verification before merge. Candidate
Source remains visibly distinct from Accepted Source and cannot produce accepted qualification.

## Candidate Qualification

Revision-bound staging evidence showing that a Candidate Source passed its declared checks. It is
pre-merge verification evidence, not accepted Platform Environment qualification.

## Canonical Plan Summary

The deterministic non-secret projection of a Terraform plan used for policy and digest binding. It
contains scope and resource/action inventory, not raw before/after values, state, provider payloads,
or credentials.

## Colocated Project

A repository-transition term for a standalone project whose canonical files temporarily lived
under another repository directory before extraction. It had its own authority, tooling, tests,
and extraction path and was not a module of the containing application.

## Shared Edge

The hostname-level DNS, TLS, address, load-balancing, routing, and identity foundation used by
multiple Registered Applications. It is an accepted platform ownership boundary, not a claim that
any resource is implemented.

## Registered Application

An application accepted through a versioned Application Registration. Registration does not make
the platform authoritative for the application's data, providers, or capability entitlements.

## Application Registration

The versioned declaration that binds a unique route prefix to application attachments, admission
policy, catalogue metadata, and lifecycle state.

## Registration Set

The complete versioned collection of current Application Registrations, including retained retired
tombstones, proposed and reviewed as one atomic configuration input.

## Registration Generation

An immutable, numbered revision derived from one valid Registration Set and linked to the preceding
reviewed generation by digest.

## Compiled Shared Edge Configuration

The deterministic catalogue, routing, admission, and attachment configuration derived from one
valid Registration Generation. It is future provider-adapter input, not proof of deployment.

## Last Reviewed Working Configuration

The most recent whole Registration Generation accepted for platform operation and eligible for
restoration when a later generation fails. It does not include or roll back Application State.

## Application Attachment

A versioned, non-secret reference that binds an application subpath to an application-owned runtime
through an allow-listed platform adapter. Referencing the runtime does not transfer its ownership.

## Platform Integration Bundle

A versioned, digest-bound, non-secret handoff generated by the platform for one application and
environment. It contains only the platform endpoints, identity values, caller reference,
attachment contract, and qualification status the application is authorized to consume.

## Application Attachment Bundle

A versioned, non-secret handoff generated under Application Owner authority after application
deployment. It binds an application-owned target and owner to the exact Platform Integration
Bundle it consumed; validation does not transfer target ownership to Platform State.

## Detached Application

A non-routable Registered Application whose identifier and route remain reserved while its
Application Owner may destroy, replace, or later redeploy its assets. Detachment is reversible and
invokes no application target.

## Retired Application

A permanently non-routable Registered Application retained as a tombstone. Retirement is terminal;
it is not the normal mechanism for a test cycle, temporary outage, or application redeployment.

## Catalogue Visibility

The explicit policy deciding whether an active Registered Application appears in the root
catalogue. It is independent of Admission Mode and does not grant access.

## Admission Mode

The platform policy deciding whether a request may reach an application attachment, such as public,
any authenticated identity, an allow-list, or owner-only. Feature authorization remains an
application responsibility.

## Admission Decision

The platform result that determines whether one request may reach a Registered Application. It does
not authorize any feature inside that application.

## Verified Identity Context

Minimal issuer-and-subject identity information validated by the platform and supplied to a
Registered Application. It is an input to application identity, not a shared user profile.

## Platform Session

A platform-owned, time-bounded browser authentication context established from verified identity.
It is neither an Application Principal nor a Feature Entitlement.

## Application Principal

An immutable, application-scoped identity derived by a Registered Application from Verified
Identity Context. It is owned by that application and is not a platform-wide user identifier.

## Feature Entitlement

An application-owned permission to use a specific product capability or restricted data source.
Application admission never implies a Feature Entitlement.

## Platform State

Terraform state that exclusively owns shared platform resources. It must never overlap with
Application State ownership.

## Application State

State owned by a Registered Application, including its runtime, data, provider configuration, and
application-specific authorization. Its exact future boundary is defined by approved contracts.

## State Ownership Manifest

A revision-scoped declaration that assigns each managed resource reference to exactly one Platform
State or named Application State owner. References between states do not transfer management
authority.

## Fixture Application

A deterministic, non-production Registered Application used to qualify platform behavior without a
real application migration. Its runtime and state remain application-owned test assets, not Platform
State.

## Integration Draft

A non-authoritative migration input prepared for another application. It becomes active only when
that application adopts it through its own documentation, contracts, tests, and release process.

## Application Adoption

The consuming Application Owner's explicit acceptance of an Integration Draft through that
application's own authorities, implementation, migration, evidence, and release process.

## Qualification

Versioned evidence that implemented behavior passed its declared evaluation gate. The presence of
documentation, code, or a cloud resource alone is not qualification; Candidate Qualification does
not replace qualification from Accepted Source.
