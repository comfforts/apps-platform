# AP-M9 lifecycle operator

Status: AP-M9-W7 application integration lifecycle implemented; no external operation performed

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
```

Preparation is credential-free. It loads one committed profile, verifies local source/repository/
tool facts, builds the complete nine-stage Deployment Specification, writes canonical bytes, and
asks for explicit approval of its exact digest. Status is read-only. Production remains blocked by
`OWNERSHIP_TRANSFER_REQUIRED`.

Deploy accepts only the exact current, approved specification. It journals preflight, backend/
identity bootstrap, foundation, immutable image publication, OAuth, Shared Edge, external DNS, TLS,
and final readback stages. Terraform mutation requires a fresh mode-`0600` saved plan under a
mode-`0700` private root, W5 policy acceptance, a redacted summary and digest, exact typed
confirmation, application of the same bound artifact, and provider/state readback. Image actions
use the same digest-bound confirmation model. OAuth and DNS display exact non-secret instructions,
wait for Enter in the same process, and then use provider-verified or explicitly operator-attested
readback with bounded DNS/TLS polling.

Outputs generates one canonical application-scoped bundle beneath the private operator directory
without exposing a secret or another application's values. Register accepts the exact integration
bundle, application-owned attachment bundle, and a strict private registration-intent document. It
validates current platform and target posture, publishes the complete immutable generation
create-only, verifies readback, and requires exact typed activation. Detach and retire require the
expected active-generation digest; replacement attachment registration reactivates a suspended
application. Interrupted confirmation may resume only the identical publication.

The default local construction remains deliberately unarmed until AP-M9-W8 completes qualification
and safe-destruction controls. Therefore the W7 integration targets report
`APPLICATION_INTEGRATION_ADAPTER_UNAVAILABLE` outside injected tests; they do not perform partial
work. The repository gate drives deployment and application integration only through deterministic
fakes and transcript tests. The non-fake Terraform command adapter is implemented behind the
injected boundary, uses absolute executable paths and argv, and is not invoked by `make check`.
It rejects path escape, ambient credential variables, shell interpolation, target/replace, lock
bypass, import, state push, and force-unlock.

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
