# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W7 application integration lifecycle handoff](starting_prompt.md) starts a new chat from
  updated, clean `main` only after the AP-M9-W6 pull request merges. It adds least-data integration
  bundles, attachment validation, complete-generation registration, reversible detachment,
  replacement/reactivation, and terminal retirement through deterministic fakes.

The handoff authorizes repository implementation of application integration mechanics only. The
pull request must not authenticate, initialize or migrate a real backend, run an authenticated plan
or apply, mutate cloud or DNS, publish a live generation, deploy staging, change Finance Assistant,
claim Application Adoption, or collect Live evidence.
