# AP-M9 lifecycle operator

Status: AP-M9-W6 interactive deployment mechanics implemented; no external operation performed

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

The default local construction remains deliberately unarmed until AP-M9-W8 completes qualification
and safe-destruction controls. The repository gate drives deployment only through deterministic
command fakes and transcript tests. The non-fake Terraform command adapter is implemented behind
the injected boundary, uses absolute executable paths and argv, and is not invoked by `make check`.
It rejects path escape, ambient credential variables, shell interpolation, target/replace, lock
bypass, import, state push, and force-unlock.

## Private local state

Generated specifications, approval bindings, immutable journal revisions, and current pointers use
the ignored `.platform-operator/` directory by default. Directories use mode `0700` and files use
mode `0600`. Documents contain no credential, secret payload, Terraform state, saved plan, raw
provider response, or browser state. Private plans and raw command results never become journal
content.

An interruption leaves the current stage open and resumes after the last closed stage. A closed
mutation is never repeated. Waiting, cancellation, command failure, policy refusal, mismatched
readback, unsafe output, and production refusal remain truthful terminal states rather than being
converted into success or automatic recovery.
