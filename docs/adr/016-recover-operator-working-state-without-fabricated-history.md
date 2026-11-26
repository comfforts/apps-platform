# ADR-016 · Recover operator working state without fabricated history

Status: Proposed; still in discussion and grants no implementation or operation authority

Requirements: AP-PR-010, AP-PR-012, AP-QR-004 through AP-QR-009

Would refine ADR-010 and ADR-011 if accepted. ADR-007's state-ownership and recovery controls and
ADR-015's remote-member-directory authority remain unchanged. While this record is proposed,
ADR-010 and ADR-011 remain the accepted authority for operator state and interruption recovery.

## Context

The operator lifecycle keeps private progress, approved intent, bundle inspection copies,
diagnostics, and other working artifacts outside Git. That private state makes one interrupted
session resumable, but a workstation directory is not an adequate sole authority for resources
that already exist in provider control planes and independently owned Terraform state.

Deleting or losing private working state must not make a deployed environment unknowable. It also
must not permit a tool to invent the approvals, plans, browser state, observations, or unfinished
intent that existed on another workstation. Treating provider readback as a complete history would
be as inaccurate as treating the local directory as the deployed system of record.

The recovery problem is therefore two different problems:

1. reconstruct the current, independently verifiable deployment posture; and
2. preserve actual local run history without claiming that missing history was reconstructed.

## Proposed decision

Use four distinct records with different authority:

- **Deployed Authority** is the present posture independently established by the owning control
  planes. It includes provider readback, Terraform state ownership and approved outputs, the active
  immutable runtime and Registration Generation, and published non-secret pointers whose current
  bindings can be verified. No single local cache is Deployed Authority.
- **Operator Working State** is the ignored private cache and journal used by one operator process
  for preparation, inspection, progress, and safe resume. The `.platform-operator/` directory is
  its current repository-local location. It is useful but not authoritative by itself.
- **Operator Run Record** preserves what one real invocation actually observed or produced. Each
  run remains separate; a later recovery never edits it to add events that did not occur.
- **Recovery Baseline** is a new, provenance-labelled local view of the current deployment built
  from Deployed Authority. It is neither an earlier Operator Run Record nor evidence that an
  earlier approval, plan, or checkpoint occurred.

The proposed operator entry point is `platform-operator-recover`. It is externally read-only and
may write only new private local recovery artifacts. It must:

1. name one Platform Environment and verify the active operator session, provider project,
   environment profile, tools, and recovery implementation source;
2. read each available deployed authority through its owning provider, state, generation, or
   published-record boundary;
3. correlate the observed environment, ownership, source, generation, resource, and digest facts;
4. label every retained fact by provenance as remotely verified, deterministically derived,
   unavailable, or conflicting;
5. stop short of an operationally usable baseline when a required fact is unavailable,
   ambiguous, or conflicting; and
6. create a new Recovery Baseline without overwriting an Operator Run Record or pretending to
   continue an interrupted mutation.

Operator testimony may explain a discrepancy, but it cannot turn an unverified fact into Deployed
Authority. A convenience pointer to the newest local record is not authority and cannot choose a
winner between conflicting runs or provider observations.

## What recovery cannot reconstruct

Recovery must not synthesize any fact that cannot be independently verified, including:

- original interactive confirmations or typed destructive phrases;
- an exact saved Terraform plan or its review context;
- historical local-only bundle inspection copies;
- browser state, cookies, tokens, credentials, or secret values;
- uncommitted source, unapproved intent, or the in-memory position of an interrupted command;
- private diagnostics or terminal output that no longer exists; and
- records intentionally never published to a remote authority.

When retained, those facts belong to separate private Operator Run Records. If such a record is
lost, recovery reports the fact as unavailable. It does not copy a later observation backward into
history or merge several runs into a fictional continuous journal.

## Run separation and reconciliation

Every invocation that writes private state must have a distinct run identity. Closing, cancelling,
or superseding a run preserves that run's actual record separately from the next invocation. A
local `latest` selection may help the operator navigate those records, but it is only a convenience
pointer and is never evidence that the selected run describes the deployed environment.

Reconciliation compares an Operator Run Record or Recovery Baseline with fresh Deployed Authority.
It reports matches, missing facts, and conflicts without rewriting either side. A new Recovery
Baseline becomes the current local starting point only after its required remote facts agree; the
older runs remain available for inspection. The storage layout, retention period, and safe method
for reconciling records copied from another workstation remain open design questions.

## Recovery and later mutation

A Recovery Baseline describes current posture; it does not approve a future operation. It cannot
resume or apply a plan from a missing run, assert that a manual checkpoint was completed, qualify a
source revision, or satisfy an approval gate.

After recovery, any mutation must enter the normal lifecycle through a fresh readiness check,
current Deployment Specification, exact plan or bounded action, operator confirmation, and
readback. If current provider posture disagrees with an older Operator Run Record, provider and
state readback govern the next operational decision while the older record remains unchanged as
history.

Recovery is distinct from rerunning an interrupted operation whose valid Operator Working State is
still present. It is also distinct from Terraform import, state push, force-unlock, backend repair,
provider disaster recovery, Application State recovery, Platform Member owner bootstrap, and
restoration of qualification evidence. Each of those requires its own existing or future
authority.

## Considered alternatives

### Keep local working state as the sole authority

Rejected because loss of one ignored directory would strand a deployed environment and another
operator could not establish its current posture.

### Treat provider and Terraform readback as complete history

Rejected because current resources cannot prove which local plan was reviewed, which prompt was
confirmed, what browser session existed, or which unpublished intent was abandoned.

### Replicate the entire private operator directory remotely

Rejected because the directory may contain saved plans, raw diagnostics, browser-adjacent state,
and local-only inspection artifacts. Replicating it would broaden secret, privacy, retention, and
ownership boundaries without making all of its contents authoritative.

### Delete local state and rerun the normal lifecycle blindly

Rejected because a fresh run must first understand existing ownership and deployment posture. A
blind replay can duplicate resources, conflict with remote state, or turn missing history into an
implicit approval.

### Reconstruct current posture and preserve actual runs separately

Proposed because it permits a new operator to understand deployed reality while preserving the
difference between verifiable current state and irrecoverable historical context.

## Consequences

- The platform can eventually recover a truthful current-state baseline on a new workstation
  without making the local cache the cloud system of record.
- Recovery remains useful even when historical local artifacts are gone, but it reports that loss
  instead of manufacturing continuity.
- Per-run storage, retention, access, and reconciliation need an explicit private-record design.
- A recovered baseline cannot shorten normal planning, confirmation, destructive-action, source,
  or qualification boundaries.
- Recovery must use least-data projections; raw state, provider payloads, credentials, browser
  state, and secrets remain outside recovered records.
- No current AP-M9 work package implements this proposal. AP-M9-W10 continues to exclude
  operator-state recovery.

## Questions required before acceptance

1. Which remote facts form the minimum complete Recovery Baseline for each lifecycle state?
2. Which safe run summaries, if any, should be published remotely, under whose ownership and
   retention policy?
3. How are run identifiers, local retention, encryption, export, and deletion handled without
   turning private working state into a public contract?
4. How does an operator compare records from multiple workstations without automatically merging
   them or treating recency as authority?
5. Which source or schema incompatibilities permit read-only inspection but prohibit an
   operationally usable baseline?
6. Which deterministic, fixture, and Live evaluation gates are required before the recovery entry
   point can be accepted and implemented?
