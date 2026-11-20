# AP-M9 lifecycle operator

Status: AP-M9-W8 qualification and safe-destruction lifecycle implemented; no external operation performed

This package keeps lifecycle orchestration behind `LifecycleOperator`. Preparation and status use
injected Git, GitHub, GCP, Terraform, DNS, terminal, filesystem, and clock boundaries. Deployment
uses an immutable `StageContext` and an injected `DeploymentExecutor`, so deterministic command
fakes and the non-fake command boundary exercise the same orchestration interface.

## Implemented commands

After `make terraform-setup` has populated the checksum-bound local toolchain:

```bash
make platform-prepare ENVIRONMENT=staging
make platform-status ENVIRONMENT=staging
make platform-deploy \
  ENVIRONMENT=staging \
  SPECIFICATION_DIGEST=sha256:<64-lowercase-hex>
make platform-outputs \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-authenticated \
  ACCESS_MODE=authenticated \
  ROUTE_INTENT=/fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  PLATFORM_GENERATION=1
make platform-register \
  ENVIRONMENT=staging \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.json \
  REGISTRATION_INTENT=/private/path/registration-intent.json
make platform-detach \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  GENERATION_DIGEST=sha256:<64-lowercase-hex>
make platform-retire \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  GENERATION_DIGEST=sha256:<64-lowercase-hex>
make platform-qualify ENVIRONMENT=staging
make platform-destroy ENVIRONMENT=staging
```

Standalone preparation is credential-free and remains an optional dry run. The normal deploy
command verifies local source/repository/tool facts plus the active human account and provider
project, builds the complete Deployment Specification, writes canonical bytes, asks for approval,
and continues in the same process. Status is read-only. Production remains blocked by
`OWNERSHIP_TRANSFER_REQUIRED`.

Deploy accepts only the exact current, approved specification. It journals preflight, backend
bootstrap, foundation, immutable image publication, OAuth, Shared Edge, external DNS, TLS,
and final readback stages. Terraform mutation requires a fresh mode-`0600` saved plan under a
mode-`0700` private root, W5 policy acceptance, a redacted summary and digest, a `y/N`
confirmation, application of the same bound artifact, and provider/state readback. Image actions
use the same reviewed confirmation model. OAuth and DNS display exact non-secret instructions,
wait for Enter in the same process, and then use provider-verified or explicitly operator-attested
readback with bounded DNS/TLS polling.

Outputs generates one canonical application-scoped bundle beneath the private operator directory
without exposing a secret or another application's values. Register accepts the exact integration
bundle, application-owned attachment bundle, and a strict private registration-intent document. It
validates current platform and target posture, publishes the complete immutable generation
create-only, verifies readback, and requires activation confirmation. Detach and retire require the
expected active-generation digest; replacement attachment registration reactivates a suspended
application. Interrupted confirmation may resume only the identical publication.

W8 implements exact revision readback, the closed qualification profile, redacted evidence,
network fixtures, failure injection, reviewed rollback, separate destruction authority, and
create-only resume state. It constructs shell-free Cloud SDK generation, traffic, attachment, and
readback adapters through the verified active human session. The qualification
and destruction live defaults retain explicit W9 authority gates; no partial external work occurs.
Repository tests use deterministic fakes and process-local loopback only. Non-fake command adapters
are not invoked by `make check` and reject path escape, ambient credential variables, shell
interpolation, mutable scope, and raw-output persistence.

## Private local state

Generated specifications, approval bindings, immutable journal revisions, current pointers, and
create-only application-scoped integration bundles use the ignored `.platform-operator/` directory
by default. Directories use mode `0700` and files use mode `0600`. Registration intent is a strict
private operator input; restricted members are never echoed in terminal results. Documents contain
no credential, secret payload, Terraform state, saved plan, raw provider response, or browser
state. Private plans and raw command results never become journal content.

An interruption leaves the current stage open and resumes after the last closed stage. A closed
mutation is never repeated. Waiting, cancellation, command failure, policy refusal, mismatched
readback, unsafe output, and production refusal remain truthful terminal states rather than being
converted into success or automatic recovery.
