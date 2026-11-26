# App Platform implementation plan index

Version 0.4 | Status: canonical plan router through AP-M9-W12

This directory is the canonical router for App Platform delivery plans. Requirements and accepted
architecture decisions define required behavior and durable choices. A delivery plan defines how a
bounded implementation slice will realize that authority, how it will be reviewed, and what
evidence closes it. A plan does not, by itself, implement behavior or authorize an external
operation.

## Current plan model

The [origin implementation plan](000-origin-implementation-plan.md) preserves AP-M3 through AP-M8
and the historical later-sequence notes that accompanied those plans. AP-M9 has its own
[milestone plan](ap_m9/000-m9_interactive_platform_lifecycle.md), which owns the milestone outcome,
boundaries, ordered work packages, acceptance criteria, and trace. The `000-` prefix marks that
file as the AP-M9 directory entry point.

The [AP-M9-W10 work-package plan](ap_m9/w10_platform_member_directory.md) is a sibling of the
milestone plan because the Platform Member Directory and explicit Identity Delivery change is
substantial enough to require its own baseline, operator journey, scope controls, functional-slice
map, atomic integration branch, and effort signals. Not every work package needs an individual
file; the milestone plan remains canonical when no extracted work-package plan exists.

The compatibility document at `docs/04_implementation_plan.md` routes old links to this index.
When a delivery item is extracted, its individual file becomes the only current plan for that
identifier. A milestone plan controls sequence and milestone-wide boundaries; an extracted
work-package plan controls only that package's implementation detail. The origin document remains
provenance and cannot override either current plan.

## Plan inventory

| Delivery identifier | Delivery status | Current canonical plan |
| --- | --- | --- |
| AP-M3 through AP-M7 | Complete | [Origin implementation plan](000-origin-implementation-plan.md) |
| AP-M8 | Historical; W1/W2 merged and W3-W12 superseded without execution | [Origin implementation plan](000-origin-implementation-plan.md) |
| AP-M9-W1 through AP-M9-W9 | Implemented; W9 candidate-qualified under the Version 1 predecessor model | [AP-M9 milestone plan](ap_m9/000-m9_interactive_platform_lifecycle.md) |
| AP-M9-W10 | Slices 1-3 implemented without Version 2 runtime activation; Slice 3 integration merge, Slices 4-7, and Candidate Source qualification remain | [Platform Member Directory and explicit Identity Delivery](ap_m9/w10_platform_member_directory.md) |
| AP-M9-W11 | Planned first Accepted Source staging operation | [AP-M9 milestone plan](ap_m9/000-m9_interactive_platform_lifecycle.md#ap-m9-w11--accepted-source-staging-deployment-and-qualification) |
| AP-M9-W12 | Planned read-only production readiness and Finance handoff | [AP-M9 milestone plan](ap_m9/000-m9_interactive_platform_lifecycle.md#ap-m9-w12--production-readiness-and-finance-handoff) |

## Plan status and estimates

Plan status is separate from implementation and evidence status. Use the
[documentation status and delivery sequence](../README.md),
[evaluation strategy](../05_evaluation_strategy.md), and the active plan to determine whether work
is planned, implemented, candidate-qualified, accepted-qualified, or historical.

File counts, working-token ranges, elapsed-time ranges, and relative percentages in an individual
plan are estimation signals. They help detect unexpected scope growth; they are not commitments,
authority, or acceptance criteria. Repeatedly touched files make per-slice file estimates
non-additive. Actual verification and evidence, not an estimate, determine completion.

## Updating plans

- Keep a completed or superseded plan as historical evidence; do not rewrite its result into a
  different outcome.
- Treat milestones and work packages as planning containers. Give each independently reviewable
  functional slice its own functionality-oriented branch and pull request, and merge ordered slices
  before beginning their successors.
- Use an integration branch only when the active work-package plan explicitly requires the entire
  multi-slice feature to remain absent from `main` until complete. Name its branch, slice bases,
  pull-request targets, synchronization rule, final qualification gate, and cumulative `main`
  handoff in that plan.
- Keep milestone plans in a milestone directory with `000-` as the entry point. Add a sibling
  work-package plan only when the milestone summary no longer provides a practical review map.
- Update the index, compatibility router, documentation reading order, prompt, and governance tests
  in the same change.
- Keep implementation detail out of an ADR unless it is necessary to express the durable decision.
- Stop and re-scope before a ninth substantive commit or when work crosses a lifecycle, authority,
  contract family, or independently reviewable outcome.
