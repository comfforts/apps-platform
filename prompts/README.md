# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W2 retired-manifest cleanup handoff](starting_prompt.md) starts a new chat from updated,
  clean `main` only after the AP-M9-W1 pull request merges. It removes the obsolete AP-M8 manifest
  interface while preserving AP-M7 configuration behavior and the historical record.

The handoff authorizes repository cleanup only. It does not authorize AP-M9-W3 implementation,
repository-setting changes, credentials, backend initialization, an authenticated plan or apply,
a cloud or DNS mutation, deployment, Application Adoption, or Live qualification.
