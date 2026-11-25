# ADR-011 · Bind interactive mutation to one verified operator session and exact plans

Status: Accepted; operator-state reconstruction is still in discussion for reserved ADR-016

Requirements: AP-PR-010, AP-QR-001, AP-QR-004 through AP-QR-009

Supersedes: ADR-007 only where ADR-007 requires routine mutation to execute exclusively inside
GitHub Actions. ADR-007's independent roots, remote state, locking, recovery, exclusive ownership,
no-key, exact-source, exact-plan, and readback decisions remain accepted.

This record is extracted from the
[origin architecture decision record](000-origin-architecture-decision-records.md). ADR-016 does
not yet exist as a decision; until it is recorded and accepted, the decision below remains current.

## Context

The product operator is a human running one local interactive lifecycle. Dividing one deployment
across many protected jobs would require repeated UI approvals and cannot directly support the
same-process OAuth and Squarespace checkpoints. The earlier unexecuted design added 31
operation-specific service accounts and repeated exact-phrase confirmations. That design reduced
ambient privilege in theory but made the product substantially harder to operate, bootstrap, and
verify than the proven Finance Assistant scripts.

## Decision

The normal local lifecycle verifies the active human account, exact provider project, explicit
source authority, pinned tools, selected environment, and reviewed Deployment Specification before
mutation. Accepted Source is the exact clean current protected `main`. Candidate Source is a clean
pushed non-main revision whose matching origin branch contains current `origin/main`; it is admitted
only for pre-merge staging verification. Source authority is part of the specification and bundle
bindings. Candidate qualification uses separate evidence pointers, cannot overwrite accepted
qualification, cannot authorize production, and must be repeated from Accepted Source after merge.
The lifecycle uses that short-lived human-authenticated session directly for the bounded interactive
run. It creates no operation-identity fleet, impersonation binding, service-account key, or
long-lived credential. Runtime service accounts remain Terraform-managed resources with their
existing Platform State or Application State owners.

For ordinary reversible staging creation and update, the owner's deliberate invocation of the
named command selects the operation. The same process prepares and displays the specification,
requests its approval, displays each exact plan or bounded action, and requests confirmation before
mutation; no separate out-of-band approval is required. A second chat, ticket,
workflow-environment, or other approval would duplicate that decision without narrowing scope.
Destruction, purge, ownership transfer, production cutover,
and any proposed scope expansion retain separately named approval and stronger confirmation.

Every Terraform mutation creates a fresh exact plan, canonical digest, policy result, and `y/N`
owner confirmation in the same execution that applies that plan. Typed confirmation remains
mandatory for destruction, purge, ownership transfer, and other irreversible boundaries. Provider
and state readback close each stage. An unexpected change stops without automatic unlock, state
push, rollback, cleanup, or scope broadening. The lifecycle never treats the human session's broad
provider capability as authority to exceed the displayed plan or named action. Repository checks
and source review remain protected, but GitHub workflow execution is not the product's routine
interactive interface.

## Consequences

- The operator can complete one deployment without switching between local lifecycle invocations.
- `platform-preflight` provides an optional readiness-only diagnostic over the same source,
  profile, tool, authentication, project, ownership, and discovery checks. It reports blockers but
  creates no specification, digest, approval, progress, plan, local deployment state, or external
  mutation.
- `platform-preflight-check` and `platform-deploy-check` may inspect a dirty working tree but never
  report `SOURCE_NOT_CLEAN` or admit that tree as operational source. Other source findings remain
  non-blocking diagnostics. The deeper check uses real provider readback and lock-free exact
  planning, deletes ephemeral plans, classifies platform readiness as ready, reconciliation
  required, incomplete, or blocked, and has no approval, apply, provider-action,
  checkpoint-execution, or lifecycle-state-write interface.
- `application-handoff-check` consumes the platform-ready result rather than interpreting internal
  deployment stages. It then verifies the named application project, its required services, Shared
  VPC grants, bundle inputs, admission mode, and application identity projection. It publishes no
  bundle and exposes no mutation interface.
- `platform-deploy` consumes the same platform-readiness interface before preparation, review,
  approval, and deployment in one process; a blocked check stops before approval or mutation, while
  reconciliation-required or incomplete results continue only through fresh exact stage plans.
  `platform-prepare` remains an optional read-only preview. When that preview has already stored a
  current approved specification, deploy discovers and reuses it after freshness validation
  without requiring a copied digest; absent, stale, or unapproved intent returns to preparation.
- Automatic selection never trusts a pointer alone: canonical readback, exact source/profile/
  environment/approval binding, current session/project/tool/provider discovery, and active-
  progress compatibility must pass. Malformed retained state and current blockers stop without replacement.
- Deliberate invocation plus the in-process review gates authorizes an ordinary staging execution;
  repository merge alone never starts one.
- Source binding is enforced by the lifecycle and retained evidence rather than by a remote runner
  alone.
- A pull request can exercise the real staging provider boundary before merge without presenting
  its result as accepted-main qualification; production remains main-only.
- The operator account remains powerful; exact plans, small command allow-lists, confirmations,
  readback, drift detection, and evidence are the active controls. Provider IAM outside the script
  remains an owner responsibility and residual risk.
- A later remote execution adapter requires its own decision and parity evidence.
