# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W10 Slice 1 contract handoff](starting_prompt.md) starts a new chat from the latest clean
  `feat/platform-member-directory` only after this governance change merges to that integration
  branch. It implements only the Version 2 contract family and deterministic Version 1 migration on
  `feat/identity-delivery-v2-contracts`. The handoff is subordinate to the
  [current W10 delivery plan](../docs/plans/ap_m9/w10_platform_member_directory.md).

The handoff authorizes only the first ordered W10 functional slice. It excludes directory
infrastructure, edge enforcement, member operations, application handoffs, Candidate Source
qualification, production, and real-application changes. Each slice pull request targets the
integration branch and updates the prompt for its successor rather than pulling later work into its
branch.
