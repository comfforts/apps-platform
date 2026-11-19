# AP-M9 environment lifecycle runbook

Status: AP-M9-W1 design authority only; operator commands and external actions are unavailable

This runbook describes the intended human experience. It is subordinate to AP-PR-010 through
AP-PR-012, AP-QR-007 through AP-QR-009, ADR-010 through ADR-013, AP-M9-W1 through AP-M9-W10, and
AP-EVAL-M9. AP-M9-W1 creates no command, credential, identity, backend, cloud resource, DNS record,
certificate, deployment, or Live evidence.

## Planned environment flow

1. `platform-prepare` selects `staging` or `production`, loads a small non-secret profile, performs
   bounded read-only discovery, shows unresolved human inputs and ownership blockers, and writes a
   digest-bound Deployment Specification.
2. The operator reviews and explicitly approves that exact specification. Approval is a property
   of a complete valid specification; it does not hide or override an unresolved blocker.
3. `platform-deploy` verifies source, profile, specification, environment, and approval bindings,
   then creates fresh exact Terraform plans immediately before each stage and applies only the
   plan just shown in the same process.
4. The deployment remains in one interactive process for human-only checkpoints. It displays the
   allocated edge address, pauses while the operator adds the external Squarespace DNS record, and
   continues on Enter only after readback verifies propagation. Google OAuth branding and client
   creation use the same guided checkpoint model. OAuth client secrets are entered only into the
   approved secret-manager surface and never into the platform terminal, journal, or bundle.
5. `platform-status` reports desired, observed, and last-qualified state without changing it.
6. `platform-outputs` writes a versioned non-secret Platform Integration Bundle for an application
   owner. It may contain an OAuth client identifier and stable secret-manager references, never an
   OAuth client secret.
7. The application owner deploys Application State and returns an Application Attachment Bundle.
   `platform-register` validates and activates that attachment. `platform-detach` suspends routing
   reversibly; `platform-retire` terminates the application identity while reserving its route.
8. `platform-qualify` evaluates the exact deployed revisions and records redacted evidence.
9. `platform-destroy` shows the exact platform-owned destruction scope and requires a fresh
   confirmation. It refuses while active application attachments or ownership blockers remain and
   never destroys Application State.

The interactive process may be resumed after an ordinary retryable failure using its local
execution journal, but a changed specification or source requires new preparation and approval.
Pressing Enter acknowledges a named human checkpoint; it never grants a general permission.

## Environment isolation

Staging and production have distinct projects, hostnames, backends, state lineages, identities,
specifications, journals, bundles, approvals, and evidence. A staging approval or artifact cannot
be reused for production.

The first real operation belongs to AP-M9-W9 and targets `apps-staging.comfforts.com` with synthetic
applications. Production preparation must stop with `OWNERSHIP_TRANSFER_REQUIRED` while Finance
Assistant or `apps.comfforts.com` remains Finance-owned. AP-M9 never silently imports, mutates, or
destroys those assets.

## Current operator rule

Until the packages named above implement and qualify each command, use no `platform-*` command as
an external operator procedure. `make check` remains the only repository gate and is credential-
free, deterministic, and non-mutating.
