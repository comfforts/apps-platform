# ADR-010 · Use one interactive lifecycle module instead of an operator-authored manifest

Status: Accepted; operator-state reconstruction is still in discussion for reserved ADR-016

Requirements: AP-PR-010, AP-PR-012, AP-QR-004 through AP-QR-009

This record is extracted from the
[origin architecture decision record](000-origin-architecture-decision-records.md). ADR-016 does
not yet exist as a decision; until it is recorded and accepted, the decision below remains current.

## Context

The AP-M8 manifest experiment required the operator to collect values that source or provider
readback can derive, predict facts that exist only after deployment, and maintain an append-only
document whose interface was comparable in complexity to the implementation. That surface is not
human-operable and does not provide leverage for the operator.

## Decision

AP-M9 exposes one focused interactive lifecycle through the prepare, deploy, status, outputs,
register, detach, retire, qualify, and destroy operations, plus explicit read-only preflight and
deployment checks for local maintenance and a read-only application-handoff check before bundle
publication. Stable environment decisions live in a
small Environment Profile. Preparation discovers or derives available non-secret facts and creates
one canonical Deployment Specification containing the environment, source, profile, operation,
and fixed workflow identity. Deployment creates exact plans and generated facts just in time,
validates each against reviewed code and provider readback, and atomically replaces one private
progress record after a stage closes. The specification is not a data-driven stage language and
the progress record is not a public contract or append-only hash chain.

The normal local wizard remains active across provider-console and external-DNS work. It displays
the exact manual action, waits for an Enter acknowledgement, verifies every readable fact, and
continues without requiring another invocation. Rerunning is recovery after interruption, not the
normal checkpoint interface.

AP-M9-W2 removed the retired AP-M8 operator-manifest schema, chain, prompt, and manual-input
workflow from the active tree. Their merged history remains evidence that the approach was
implemented and superseded; it is not active deployment authority.

## Consequences

- The operator learns one small interface rather than Terraform-root and manifest internals.
- Cross-owner facts remain digest-bound without turning every internal action into an attestation.
- Deterministic tests exercise the same operator commands through external-effect fakes.
- No AP-M9 repository change alone authorizes credentials or an external mutation.
