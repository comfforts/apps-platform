# AP-M9 environment lifecycle runbook

Status: AP-M9-W8 shared-platform lifecycle mechanics implemented; AP-M9-W9 fixture deployment
lifecycle is next; no external action has run, and AP-M9-W10 remains the first operation

This runbook describes the intended human experience. It is subordinate to AP-PR-010 through
AP-PR-012, AP-QR-007 through AP-QR-009, ADR-010 through ADR-013, AP-M9-W1 through AP-M9-W11, and
AP-EVAL-M9. AP-M9-W1 through AP-M9-W8 create no credential, identity, backend, cloud resource, DNS
record, certificate, deployment, or Live evidence. W3 implements the closed profiles and lifecycle
documents, W4 implements credential-free local preparation/status, W5 implements the exact
Terraform phase, backend, and plan-policy seams, and W6 implements staged execution, confirmation,
manual checkpoints, readback, and resume. W7 implements the platform side of application
integration: least-data bundle generation, exact attachment validation, immutable whole-generation activation,
reversible detachment/reactivation, and terminal retirement behind injected boundaries.
W8 implements exact-revision qualification, redacted evidence, process-local network fixtures, failure injection,
reviewed rollback, separate safe-destruction authority with resumable progress, and the real staging
deployment adapters behind verified-human-session gates.

## Environment flow

1. `platform-deploy` selects `staging` or `production`, loads a small non-secret profile, performs
   bounded read-only discovery, shows unresolved human inputs and ownership blockers, and writes a
   digest-bound Deployment Specification. `platform-prepare` offers the same read-only work as an
   optional dry run.
2. In the same deploy invocation, the operator reviews and explicitly approves that exact
   specification. Approval is a property
   of a complete valid specification; it does not hide or override an unresolved blocker.
3. Deployment verifies source, profile, specification, environment, active human account, exact
   provider project, and approval bindings, then creates fresh exact Terraform plans immediately
   before each stage. After showing a plan it uses one `y/N` confirmation and applies only that
   saved plan in the same process. Typed phrases are reserved for irreversible actions.
4. The deployment remains in one interactive process for human-only checkpoints. It displays the
   allocated edge address, pauses while the operator adds the external Squarespace DNS record, and
   continues on Enter only after readback verifies propagation. Google OAuth branding and client
   creation use the same guided checkpoint model. OAuth client secrets are entered only into the
   approved secret-manager surface and never into the platform terminal, journal, or bundle.
5. `platform-status` reports desired, observed, and last-qualified state without changing it.
6. `platform-outputs` writes a versioned non-secret Platform Integration Bundle for an application
   owner. It may contain an OAuth client identifier for a protected application, never an OAuth
   client secret, secret-manager reference, restricted-member set, or another application's value.
7. The application owner deploys Application State and returns an Application Attachment Bundle.
   `platform-register` validates and activates that attachment. `platform-detach` suspends routing
   reversibly; `platform-retire` terminates the application identity while reserving its route.
8. For the repository-owned synthetic suite, `fixture-deploy` performs the application-owner side
   sequentially across three independent Application State lineages and completes the bundle return
   and registration. `fixture-status` is read-only; `fixture-destroy` detaches and destroys only
   selected Fixture Application State after typed confirmation.
9. `platform-qualify` evaluates the exact deployed revisions and records redacted evidence.
10. `platform-destroy` shows the exact platform-owned destruction scope and requires a fresh
   confirmation. It refuses while active application attachments or ownership blockers remain and
   never destroys Application State.

The interactive process may be resumed after an ordinary retryable failure using its local
execution journal, but a changed specification or source requires new preparation and approval.
Pressing Enter acknowledges a named human checkpoint; it never grants a general permission.

The operator experience intentionally follows the proven Finance Assistant script model: one
command, readable staged output, discovered defaults, `y/N` plan gates, browser-console guidance,
Enter-to-continue pauses, immediate readback, and a clear stop on the first mismatch. The platform
does not require a hand-authored manifest, a mandatory prepare/deploy round trip, or an
operation-service-account bootstrap.

## Environment isolation

Staging and production have distinct projects, hostnames, backends, state lineages, identities,
specifications, journals, bundles, approvals, and evidence. A staging approval or artifact cannot
be reused for production.

The first real operation belongs to AP-M9-W10 and targets `apps-staging.comfforts.com` with synthetic
applications. Production preparation must stop with `OWNERSHIP_TRANSFER_REQUIRED` while Finance
Assistant or `apps.comfforts.com` remains Finance-owned. AP-M9 never silently imports, mutates, or
destroys those assets.

## Current operator rule

After W8 merges, `make platform-prepare ENVIRONMENT=staging` may be used from clean current `main`
to create and explicitly approve one complete specification in the ignored private
`.platform-operator/` directory. It performs read-only Git, profile, repository-identity,
pinned-tool, active-account, project, billing-reference, Google-subject, and user-ADC discovery.
Tokens are discarded in memory and never enter the specification or journal. `make platform-status
ENVIRONMENT=staging` reads the local status without changing provider state. Production preparation
reports `OWNERSHIP_TRANSFER_REQUIRED`.

Preparation may use the already authenticated Cloud SDK for bounded read-only session discovery;
neither preparation nor status initializes a backend, creates a Terraform plan, or mutates a
repository, cloud resource, OAuth client, secret, DNS record, certificate, or application. W6 adds
`make platform-deploy ENVIRONMENT=staging SPECIFICATION_DIGEST=sha256:<digest>` as the exact
interactive entry point. The non-fake Terraform subprocess boundary
is implemented and closed to shell interpolation, ambient credentials, path escape, target/replace,
state push, import, force-unlock, and lock bypass; repository tests invoke only deterministic
recording fakes. W8 wires that boundary to the local deploy command only when `gcloud`, `dig`, the
pinned Terraform mirror, the exact staging project, an active human account, and user Application
Default Credentials are all ready. For ordinary staging creation or update, the owner deliberately
invokes `platform-deploy`; its same-process specification and plan confirmations authorize that
execution without a duplicate out-of-band approval. Destructive and irreversible boundaries retain
their separately named approvals.

W7 adds `platform-outputs`, `platform-register`, `platform-detach`, and `platform-retire`. Outputs
writes canonical create-only bundles beneath `.platform-operator/`. Register accepts an exact
integration bundle, attachment bundle, and strict private registration intent; it publishes and
activates only complete immutable generations after readback and confirmation. Detach
and retire require the expected active-generation digest. Interrupted confirmation can resume only
the identical create-only publication. W8 conditionally constructs provider and generation-control
adapters only when an explicit private Cloud SDK configuration exists.
W8 adds `platform-qualify` and `platform-destroy`; their default live entry points return
`W9_LIVE_QUALIFICATION_AUTHORITY_REQUIRED` or `W9_DESTRUCTION_AUTHORITY_REQUIRED` until the owner
merges the W9 fixture lifecycle and exact live executors. W9 replaces these implementation gates;
W10 invokes the merged targets. `make check` remains credential-free, deterministic, and non-mutating.
