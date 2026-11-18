# Inert operator-workflow templates

These AP-M7-W9 `*.yml.tmpl` files are JSON-compatible YAML documents stored outside
`.github/workflows/`. They are parsed as data by the deterministic repository gate and cannot run
as GitHub Actions workflows. AP-M8 must separately approve the protected environment, federation,
operation identities, backend inputs, repository settings, rendering process, and executable
workflow before using any design here.

Every template keeps repository permissions read-only by default, grants `id-token: write` only to
its future federated job, pins every action to a full commit SHA, fixes protected main and the
repository identity, uses unresolved operator placeholders, serializes by root, and retains only a
secret-free outcome summary. No template reads a GitHub secret or names a real Workload Identity
Federation provider or service account.

The plan, apply, rollback, and destroy designs write their plan only under `RUNNER_TEMP`; no plan is
uploaded or reused for apply. The plan digest is SHA-256 over canonical compact JSON from
`terraform show -json` after removing only its top-level `timestamp`. Apply, rollback, and destroy
create a fresh plan at the exact protected-main revision, compare that canonical digest with the
reviewed workflow configuration, and apply that same runner-local plan in the same job.

Force-unlock and destroy require an exact destructive target and confirmation digest. Their
confirmation material is, respectively:

```text
force-unlock|<root-target>|<lock-id>|<source-revision>
destroy|<root-target>|<target-id>|<source-revision>|<plan-digest>
```

A mismatch, provider error, or partial failure stops without automatic rollback, unlock, state
push, DNS change, or follow-on mutation. Placeholder strings beginning and ending with `__` are
deliberately unresolved and must never be treated as deployable defaults.
