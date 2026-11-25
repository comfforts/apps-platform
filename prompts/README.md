# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W10 member directory handoff](starting_prompt.md) starts a new chat from updated, clean
  `main` only after the ADR-015 governance change merges. It implements and candidate-qualifies the
  Platform Member Directory, explicit Identity Delivery, Version 2 contracts, owner bootstrap, and
  member lifecycle before the first Accepted Source staging operation. The handoff is subordinate
  to the [current W10 delivery plan](../docs/plans/ap_m9_w10_platform_member_directory.md).

The handoff authorizes the bounded W10 repository implementation. Candidate Source staging
qualification still requires the existing operator entry points and owner direction; it cannot be
promoted to Accepted Source evidence. The pull request must not mutate production or a real
application, change Finance Assistant, claim Application Adoption, or perform the W11 Accepted
Source operation.
