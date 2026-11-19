# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W3 lifecycle-contracts and profiles handoff](starting_prompt.md) starts a new chat from
  updated, clean `main` only after the AP-M9-W2 pull request merges. It implements closed
  environment profiles and deterministic lifecycle contracts while preserving the AP-M7
  configuration surface and the historical AP-M8 record.

The handoff authorizes repository contract and profile implementation only. It does not authorize
AP-M9-W4 implementation, repository-setting changes, credentials, backend initialization, an
authenticated plan or apply, a cloud or DNS mutation, deployment, Application Adoption, or Live
qualification.
