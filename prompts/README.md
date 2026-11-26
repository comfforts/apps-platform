# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W10 Candidate Source qualification](starting_prompt.md) starts a new chat from the exact
  clean pushed `feat/platform-member-directory` only after all seven functional slices merge and
  their repository gates pass. It guides the separately owner-invoked staging operation and
  revision freeze without authorizing Accepted Source or production. The handoff is subordinate to the
  [current W10 delivery plan](../docs/plans/ap_m9/w10_platform_member_directory.md).

The handoff does not itself authorize the external operation; the owner must deliberately begin it
after the prompt's prerequisites pass. It excludes Accepted Source staging, production,
operator-state recovery, and real-application changes. A defect found during the operation returns
to a reviewed fix slice instead of changing the frozen integration revision in place.
