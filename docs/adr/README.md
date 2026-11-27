# App Platform architecture decision index

Version 0.4 | Status: canonical decision router through proposed ADR-016

This directory is the canonical router for App Platform architecture decisions. A decision record
captures a hard-to-reverse choice and why it was made. Requirements define required behavior;
design and contracts define implementation interfaces; the implementation plan and evaluation
strategy record realization and evidence. An accepted ADR therefore does not, by itself, mean that
the decision is implemented, deployed, or qualified.

## Current record model

The [origin architecture decision record](000-origin-architecture-decision-records.md) preserves
the consolidated form in which ADR-001 through ADR-014 were accepted. It remains the canonical text
for an unextracted decision. ADR-003, ADR-006, ADR-008, ADR-010, ADR-011, and ADR-012 have been
extracted to isolate the boundaries affected by accepted ADR-015 and proposed ADR-016. ADR-015
amends the identity and membership clauses in ADR-003, ADR-006, ADR-008, and ADR-012; the remaining
clauses stay accepted. ADR-016 proposes a recovery refinement but does not amend ADR-010 or ADR-011
while it remains under discussion. Each individual file is the only current decision text for its
identifier; the origin record remains provenance and cannot override it.

The compatibility document at `docs/02_architecture_decision_records.md` routes old paths to this
index. A future extraction must update the affected row here in the same change so every identifier
continues to resolve to exactly one current record.

## Decision inventory

| Identifier | Decision | Decision status | Current canonical record |
| --- | --- | --- | --- |
| ADR-001 | The platform owns the Shared Edge, not application runtimes | Accepted | [Origin ADR-001](000-origin-architecture-decision-records.md#adr-001--the-platform-owns-the-shared-edge-not-application-runtimes) |
| ADR-002 | Versioned registrations derive routing without shared state ownership | Accepted | [Origin ADR-002](000-origin-architecture-decision-records.md#adr-002--versioned-registrations-derive-routing-without-shared-state-ownership) |
| ADR-003 | Platform admission does not grant application feature access | Accepted; admission details amended by ADR-015 | [Extracted ADR-003](003-platform-admission-does-not-grant-application-feature-access.md) |
| ADR-004 | Qualify the platform with fixtures before application adoption | Accepted | [Origin ADR-004](000-origin-architecture-decision-records.md#adr-004--qualify-the-platform-with-fixtures-before-application-adoption) |
| ADR-005 | Qualify the first Live topology on GCP with Cloud Run attachments | Accepted; fixture-project topology superseded by ADR-014 | [Origin ADR-005](000-origin-architecture-decision-records.md#adr-005--qualify-the-first-live-topology-on-gcp-with-cloud-run-attachments) |
| ADR-006 | Use edge-managed Google OIDC and application-bound ES256 assertions | Accepted; membership and public-delivery details amended by ADR-015 | [Extracted ADR-006](006-edge-managed-google-oidc-and-application-bound-assertions.md) |
| ADR-007 | Separate state roots and use federated protected-main operations | Accepted; routine execution superseded by ADR-011 and fixture placement refined by ADR-014 | [Origin ADR-007](000-origin-architecture-decision-records.md#adr-007--separate-state-roots-and-use-federated-protected-main-operations) |
| ADR-008 | Activate immutable generations through one reviewed edge revision | Accepted; membership placement and compiled contract version amended by ADR-015 | [Extracted ADR-008](008-activate-immutable-generations-through-one-reviewed-edge-revision.md) |
| ADR-009 | Bound demo observability, evidence, and spend | Accepted | [Origin ADR-009](000-origin-architecture-decision-records.md#adr-009--bound-demo-observability-evidence-and-spend) |
| ADR-010 | Use one interactive lifecycle module instead of an operator-authored manifest | Accepted; proposed ADR-016 may refine recovery | [Extracted ADR-010](010-use-one-interactive-lifecycle-module.md) |
| ADR-011 | Bind interactive mutation to one verified operator session and exact plans | Accepted; proposed ADR-016 may refine recovery | [Extracted ADR-011](011-bind-interactive-mutation-to-one-verified-session.md) |
| ADR-012 | Exchange versioned non-secret bundles across platform and application ownership | Accepted; identity projection amended by ADR-015 | [Extracted ADR-012](012-exchange-versioned-non-secret-bundles.md) |
| ADR-013 | Isolate environments and distinguish detachment from permanent retirement | Accepted | [Origin ADR-013](000-origin-architecture-decision-records.md#adr-013--isolate-environments-and-distinguish-detachment-from-permanent-retirement) |
| ADR-014 | Qualify cross-project attachment through an explicit Shared VPC connection | Accepted | [Origin ADR-014](000-origin-architecture-decision-records.md#adr-014--qualify-cross-project-attachment-through-an-explicit-shared-vpc-connection) |
| ADR-015 | Use a platform-owned member directory and explicit identity delivery | Accepted; implemented, Candidate-qualified, and Accepted Source staging platform/fixture-qualified at `b433337…` | [ADR-015](015-platform-member-directory-and-explicit-identity-delivery.md) |
| ADR-016 | Recover operator working state without fabricated history | Proposed; still in discussion and not implementation authority | [ADR-016](016-recover-operator-working-state-without-fabricated-history.md) |

## Realization and evidence

Decision status and realization status are intentionally separate. Use the
[documentation status and delivery sequence](../README.md),
[implementation plan index](../plans/README.md), and
[evaluation strategy](../05_evaluation_strategy.md) to determine whether a decision is planned,
implemented, deployed, or qualified. Historical evidence cannot reactivate superseded decision
text.

## Proposed record boundary

ADR-016 records the current recovery discussion so its tradeoffs and open questions are reviewable.
It is not accepted, does not change current operator behavior, and grants no implementation or
external-operation authority. ADR-010 and ADR-011 remain controlling until a later governance
change explicitly accepts or replaces the proposal.
