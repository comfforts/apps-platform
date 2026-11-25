# App Platform architecture decision index

Version 0.1 | Status: active migration router

This directory is the canonical router for App Platform architecture decisions. A decision record
captures a hard-to-reverse choice and why it was made. Requirements define required behavior;
design and contracts define implementation interfaces; the implementation plan and evaluation
strategy record realization and evidence. An accepted ADR therefore does not, by itself, mean that
the decision is implemented, deployed, or qualified.

## Current migration state

ADR-001 through ADR-014 currently remain authoritative in the
[consolidated decision record](../02_architecture_decision_records.md). They will be preserved as an
origin record, and only decisions that need active clarification, amendment, or supersession will
be extracted into individual files. Until that migration step occurs, this index routes readers to
the consolidated record and does not duplicate its decision text.

After an ADR is extracted, its individual file becomes the only current decision text for that
identifier. The preserved origin record remains provenance and cannot override an extracted ADR.
The compatibility document at `docs/02_architecture_decision_records.md` will continue routing old
links to this index after the origin record moves.

## Decision inventory

| Identifier | Decision | Decision status | Current canonical record |
| --- | --- | --- | --- |
| ADR-001 | The platform owns the Shared Edge, not application runtimes | Accepted | [Consolidated ADR-001](../02_architecture_decision_records.md#adr-001--the-platform-owns-the-shared-edge-not-application-runtimes) |
| ADR-002 | Versioned registrations derive routing without shared state ownership | Accepted | [Consolidated ADR-002](../02_architecture_decision_records.md#adr-002--versioned-registrations-derive-routing-without-shared-state-ownership) |
| ADR-003 | Platform admission does not grant application feature access | Accepted | [Consolidated ADR-003](../02_architecture_decision_records.md#adr-003--platform-admission-does-not-grant-application-feature-access) |
| ADR-004 | Qualify the platform with fixtures before application adoption | Accepted | [Consolidated ADR-004](../02_architecture_decision_records.md#adr-004--qualify-the-platform-with-fixtures-before-application-adoption) |
| ADR-005 | Qualify the first Live topology on GCP with Cloud Run attachments | Accepted; fixture-project topology superseded by ADR-014 | [Consolidated ADR-005](../02_architecture_decision_records.md#adr-005--qualify-the-first-live-topology-on-gcp-with-cloud-run-attachments) |
| ADR-006 | Use edge-managed Google OIDC and application-bound ES256 assertions | Accepted | [Consolidated ADR-006](../02_architecture_decision_records.md#adr-006--use-edge-managed-google-oidc-and-application-bound-es256-assertions) |
| ADR-007 | Separate state roots and use federated protected-main operations | Accepted; routine execution superseded by ADR-011 and fixture placement refined by ADR-014 | [Consolidated ADR-007](../02_architecture_decision_records.md#adr-007--separate-state-roots-and-use-federated-protected-main-operations) |
| ADR-008 | Activate immutable generations through one reviewed edge revision | Accepted | [Consolidated ADR-008](../02_architecture_decision_records.md#adr-008--activate-immutable-generations-through-one-reviewed-edge-revision) |
| ADR-009 | Bound demo observability, evidence, and spend | Accepted | [Consolidated ADR-009](../02_architecture_decision_records.md#adr-009--bound-demo-observability-evidence-and-spend) |
| ADR-010 | Use one interactive lifecycle module instead of an operator-authored manifest | Accepted | [Consolidated ADR-010](../02_architecture_decision_records.md#adr-010--use-one-interactive-lifecycle-module-instead-of-an-operator-authored-manifest) |
| ADR-011 | Bind interactive mutation to one verified operator session and exact plans | Accepted | [Consolidated ADR-011](../02_architecture_decision_records.md#adr-011--bind-interactive-mutation-to-one-verified-operator-session-and-exact-plans) |
| ADR-012 | Exchange versioned non-secret bundles across platform and application ownership | Accepted | [Consolidated ADR-012](../02_architecture_decision_records.md#adr-012--exchange-versioned-non-secret-bundles-across-platform-and-application-ownership) |
| ADR-013 | Isolate environments and distinguish detachment from permanent retirement | Accepted | [Consolidated ADR-013](../02_architecture_decision_records.md#adr-013--isolate-environments-and-distinguish-detachment-from-permanent-retirement) |
| ADR-014 | Qualify cross-project attachment through an explicit Shared VPC connection | Accepted | [Consolidated ADR-014](../02_architecture_decision_records.md#adr-014--qualify-cross-project-attachment-through-an-explicit-shared-vpc-connection) |

## Realization and evidence

Decision status and realization status are intentionally separate. Use the
[documentation status and delivery sequence](../README.md),
[implementation plan](../04_implementation_plan.md), and
[evaluation strategy](../05_evaluation_strategy.md) to determine whether a decision is planned,
implemented, deployed, or qualified. Historical evidence cannot reactivate superseded decision
text.

## Reserved next sequence

The following identifiers reserve sequence only; they are not decisions and grant no
implementation or external-operation authority until their own records exist:

- **ADR-015:** platform-owned member directory and explicit identity delivery;
- **ADR-016:** operator-state recovery from deployed authority without fabricated history — still
  in discussion and scheduled for a later documentation step.
