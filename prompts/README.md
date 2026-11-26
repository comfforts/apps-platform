# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W10 Slice 5 application-handoff handoff](starting_prompt.md) starts a new chat from the latest
  clean `feat/platform-member-directory` only after the Slice 4 member-lifecycle pull request merges
  to that integration branch. It implements only Version 2 application handoffs on
  `feat/identity-delivery-application-handoffs`. The handoff is subordinate to the
  [current W10 delivery plan](../docs/plans/ap_m9/w10_platform_member_directory.md).

The handoff authorizes only the fifth ordered W10 functional slice. It excludes operator-handoff
reconciliation, Candidate Source qualification, production, and
real-application changes.
Each slice pull request targets the
integration branch and updates the prompt for its successor rather than pulling later work into its
branch.
