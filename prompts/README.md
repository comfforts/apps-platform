# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W10 Slice 7 Candidate qualification readiness](starting_prompt.md) starts a new chat from
  the latest clean `feat/platform-member-directory` only after the Slice 6 operator-handoff pull
  request merges to that integration branch. It implements deterministic qualification support on
  `evidence/member-admission-candidate-qualification`; the real Candidate Source operation remains
  a separately owner-invoked post-merge action. The handoff is subordinate to the
  [current W10 delivery plan](../docs/plans/ap_m9/w10_platform_member_directory.md).

The handoff authorizes only the seventh ordered W10 functional slice. It excludes the Live
Candidate operation on the slice branch, Accepted Source staging, production, operator-state
recovery, and real-application changes.
Each slice pull request targets the
integration branch and updates the prompt for its successor rather than pulling later work into its
branch.
