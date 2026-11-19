# AP-M9 lifecycle operator

Status: AP-M9-W4 credential-free preparation/status implemented; no executable deployment adapter

This package keeps lifecycle orchestration behind `LifecycleOperator`. Its injected boundaries are
Git, GitHub repository identity, GCP profile facts, the pinned Terraform toolchain, DNS profile
facts, terminal interaction, filesystem state, clock, and an optional stage executor. The local W4
construction installs no stage executor, so it cannot deploy or mutate an environment.

## Implemented commands

From clean current `main`, after `make terraform-setup` has populated the checksum-bound local
toolchain:

```bash
make platform-prepare ENVIRONMENT=staging
make platform-status ENVIRONMENT=staging
```

Preparation loads one committed profile, verifies local source/repository/tool facts, builds the
complete nine-stage Deployment Specification, writes its canonical bytes, and asks for explicit
approval of the exact digest. Completeness is established before approval. A cancelled approval
leaves the complete specification unapproved; a source or profile change produces another digest
and requires another approval. Production remains blocked by `OWNERSHIP_TRANSFER_REQUIRED`.

Status reads the current local specification and journal chain without writing a file. Before an
execution journal exists, an environment remains truthfully `absent`; an approved specification is
intent, not proof of deployment.

## Private local state

Generated specifications, approval bindings, immutable journal revisions, and current pointers use
the ignored `.platform-operator/` directory by default. Directories use mode `0700` and files use
mode `0600`. The documents contain no credential, secret payload, Terraform state, saved plan, or
raw provider response. They are generated local operation records, not committed evidence.

Journal execution is available in W4 only when a caller injects a deterministic stage executor.
Tests prove append-only revisions, exact specification binding, last-closed-stage resume, truthful
waiting/failure/cancellation, scope-conflict rejection, and prohibited-output redaction. The real
CLI exposes no `deploy` command. AP-M9-W5 and W6 own Terraform lifecycle support and interactive
deployment respectively.
