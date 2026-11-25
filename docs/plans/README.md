# App Platform implementation plan index

Version 0.1 | Status: canonical plan router through AP-M9-W12

This directory is the canonical router for App Platform delivery plans. Requirements and accepted
architecture decisions define required behavior and durable choices. A delivery plan defines how a
bounded implementation slice will realize that authority, how it will be reviewed, and what
evidence closes it. A plan does not, by itself, implement behavior or authorize an external
operation.

## Current plan model

The [origin implementation plan](000-origin-implementation-plan.md) preserves the consolidated
record through AP-M9-W12. It remains the canonical plan for every delivery item that has not been
extracted. AP-M9-W10 has an individual plan because the Platform Member Directory and explicit
Identity Delivery change is substantial enough to require its own baseline, operator journey,
scope controls, commit map, and effort signals.

The compatibility document at `docs/04_implementation_plan.md` routes old links to this index.
When a delivery item is extracted, its individual file becomes the only current plan for that
identifier. The origin document remains provenance and cannot override the extracted plan.

## Plan inventory

| Delivery identifier | Delivery status | Current canonical plan |
| --- | --- | --- |
| AP-M3 through AP-M7 | Complete | [Origin implementation plan](000-origin-implementation-plan.md) |
| AP-M8 | Historical; W1/W2 merged and W3-W12 superseded without execution | [Origin implementation plan](000-origin-implementation-plan.md) |
| AP-M9-W1 through AP-M9-W9 | Implemented; W9 candidate-qualified under the Version 1 predecessor model | [Origin implementation plan](000-origin-implementation-plan.md) |
| AP-M9-W10 | Planned; implementation and Candidate Source qualification not started | [Platform Member Directory and explicit Identity Delivery](ap_m9_w10_platform_member_directory.md) |
| AP-M9-W11 | Planned first Accepted Source staging operation | [Origin implementation plan](000-origin-implementation-plan.md#ap-m9-w11--accepted-source-staging-deployment-and-qualification) |
| AP-M9-W12 | Planned read-only production readiness and Finance handoff | [Origin implementation plan](000-origin-implementation-plan.md#ap-m9-w12--production-readiness-and-finance-handoff) |

## Plan status and estimates

Plan status is separate from implementation and evidence status. Use the
[documentation status and delivery sequence](../README.md),
[evaluation strategy](../05_evaluation_strategy.md), and the active plan to determine whether work
is planned, implemented, candidate-qualified, accepted-qualified, or historical.

File counts, working-token ranges, elapsed-time ranges, and relative percentages in an individual
plan are estimation signals. They help detect unexpected scope growth; they are not commitments,
authority, or acceptance criteria. Repeatedly touched files make per-commit file estimates
non-additive. Actual verification and evidence, not an estimate, determine completion.

## Updating plans

- Keep a completed or superseded plan as historical evidence; do not rewrite its result into a
  different outcome.
- Extract a delivery item when its implementation is large enough that the consolidated record no
  longer provides a practical review map.
- Update the index, compatibility router, documentation reading order, prompt, and governance tests
  in the same change.
- Keep implementation detail out of an ADR unless it is necessary to express the durable decision.
- Stop and re-scope before a ninth substantive commit or when work crosses a lifecycle, authority,
  contract family, or independently reviewable outcome.
