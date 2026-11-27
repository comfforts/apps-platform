# ADR-008 · Activate immutable generations through one reviewed edge revision

Status: Accepted; restricted-membership placement and compiled contract version amended by ADR-015

Requirements: AP-PR-001, AP-PR-002, AP-PR-003, AP-PR-004, AP-PR-005, AP-PR-007,
AP-PR-008, AP-PR-009, AP-QR-001, AP-QR-002, AP-QR-004, AP-QR-005, AP-QR-006

This record is extracted from the
[origin architecture decision record](000-origin-architecture-decision-records.md). ADR-015 is
authoritative where the original decision placed member identities in compiled configuration; the
remaining immutable-generation, activation, readback, rollback, and DNS decisions stay accepted.

## Context

Application registrations change infrequently and have one operator, so the initial platform does
not need a registration API, mutable registration database, or continuously reconciled multi-writer
control plane. It does need a persistent and observable equivalent of the fixture harness's atomic
generation pointer. Catalogue, routes, admission, attachments, identity settings, and ownership
must never activate independently.

The initial qualification hostname is new. Its DNS and certificate sequence must be independently
reviewed without treating removal of that new record as rollback of a Registration Generation or
touching existing Finance Assistant records.

## Decision

Complete Registration Sets remain reviewed Git inputs. The deterministic compiler validates the
declared predecessor and produces one canonical generation digest before Terraform planning. An
immutable compiled configuration object is published as an inactive candidate in a platform-owned
GCS configuration bucket. New objects use the readable environment-and-generation path
`environments/<environment>/generations/<number>/compiled-shared-edge.v<contract-version>.json`;
create-only publication, the generation digest, content digest, and exact GCS object generation
provide the immutable binding. Version 1 and Version 2 are the supported compiled contracts.
Existing initial and digest-addressed object names remain valid historical bindings and are never
renamed or overwritten. The object is restricted platform configuration. It
contains each application's Admission Mode and Identity Delivery policy but never contains a
Platform Member Directory entry, member list, secret, credential, signed assertion, request
payload, or application data and is never a public catalogue or evidence artifact.

Each candidate Cloud Run edge revision is immutable and binds all of these values:

- source commit and compiler version;
- Registration Generation number and digest;
- compiled configuration object name and GCS object generation;
- edge container image digest; and
- applicable identity, attachment-adapter, and platform-configuration versions.

The Cloud Run service's traffic assignment to one immutable edge revision is the current Live
Registration Generation pointer. There is no separate registration endpoint or database. The
load-balancer URL map remains unchanged by an application registration because catalogue and prefix
routing stay inside the selected edge revision.

Activation is one operator workflow with two explicit phases. The staging phase publishes the
immutable configuration, verifies the predecessor, plans the exact candidate revision, validates
every attachment and IAM dependency, and creates the candidate without assigning user traffic. The
activation phase requires owner approval and changes 100 percent of edge traffic to that one
revision. It never applies catalogue, route, admission, attachment, identity, or ownership fragments
separately.

The predecessor digest, protected-main concurrency guard, Terraform backend lock, and provider
revision precondition reject stale or concurrent activation even though the initial environment has
only one operator. A provider error or incomplete apply stops for inspection. The workflow does not
automatically retry a destructive action, unlock state, change DNS, roll back, or destroy either
application target.

Successful readback must agree across source, state, provider, and runtime. It proves at least:

- the protected-main commit, reviewed plan digest, compiler version, Registration Generation, and
  generation digest agree;
- the Cloud Run service sends 100 percent of traffic to the expected immutable edge revision and
  image digest;
- the edge reports the expected generation digest through an operator-authorized platform status
  operation;
- the root catalogue, registered prefixes, attachment targets, Admission Modes, assertion issuer,
  application audiences, and published key identifier match the generation;
- unknown, suspended, retired, and malformed paths remain closed;
- protected targets reject direct unauthenticated invocation and accept only the reviewed edge
  caller plus valid application-bound assertions; and
- the provider inventory agrees with the State Ownership Manifest without reading application
  Terraform state.

Readback records identifiers, digests, coarse outcomes, and limitations only. It may confirm the
directory schema and coarse availability without enumerating membership. It never records an
assertion, session, member identity or list, request body, application data, credential, Terraform
state, or saved plan.

Rollback is an owner-confirmed whole-generation operation that returns 100 percent of edge traffic
to the retained preceding edge revision. It targets a reviewed generation digest and never rolls
back, imports, destroys, or rewrites Application State. The initial rollback-time objective is 15
minutes from owner approval to restored traffic assignment and mandatory readback. No automatic
rollback is authorized; an observed failure stops for inspection and an explicit owner decision.

The preceding compiled configuration, edge revision, and any replaced application attachment stay
available for at least 24 hours after successful activation. Cleanup after that window is a separate
owner-approved operation with current-generation and state-ownership checks. It is not automatic,
and retirement or suspension never triggers application-resource deletion.

Initial DNS and TLS enablement are separate operator actions. The load balancer, reserved address,
closed-default edge, and certificate configuration are read back before the new hostname record is
requested. The operator creates only the `apps-staging.comfforts.com` record with a 1,800-second TTL,
checks authoritative and recursive resolution with `dig`, waits for the Google-managed certificate
to become active, and then runs the Live readback. DNS propagation is observed rather than assumed;
the TTL is a cache lifetime, not a promise that every resolver updates within 30 minutes.

If initial hostname qualification fails, the owner may remove or restore only that new record after
inspection and must allow for cached answers through the TTL. This does not change the active
Registration Generation, does not touch `apps.comfforts.com`, and does not modify any Finance
Assistant record, certificate, load balancer, or state.

## Considered alternatives

- **Store a mutable current-generation row in a registration database:** rejected because the
  initial low-frequency, single-operator workflow does not justify another control-plane service or
  source of configuration authority.
- **Rewrite provider routes directly for each registration:** rejected because partial URL-map and
  runtime updates could diverge from the reviewed generation.
- **Fetch a mutable configuration object under a fixed name:** rejected because caches, concurrent
  writes, and ambiguous rollback would weaken digest and revision binding.
- **Automatically roll back on any failed check:** rejected because a partial provider failure may
  require inspection before another mutation is safe.
- **Delete replaced targets immediately:** rejected because whole-generation rollback would no
  longer restore service even if the edge revision were retained.
- **Manage the DNS zone or existing records as part of registration activation:** rejected because
  hostname lifecycle is separate from application registration and existing records are outside
  this qualification boundary.

## Consequences

- A registration change deploys a new edge revision even when the edge application code and image
  digest are unchanged.
- Immutable configuration objects and revisions consume modest storage during retention but make
  provenance and rollback explicit.
- The 15-minute rollback objective begins after owner approval; detection and decision time are
  recorded separately.
- A 24-hour retention window is a minimum recovery opportunity, not permission for automatic
  cleanup at its expiration.
- This decision creates no registration file, configuration bucket, object, edge revision, DNS
  record, certificate, deployment, mutation, or Live evidence.
