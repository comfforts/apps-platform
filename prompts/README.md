# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W4 interactive lifecycle core handoff](starting_prompt.md) starts a new chat from updated,
  clean `main` only after the AP-M9-W3 pull request merges. It implements credential-free
  preparation, explicit digest approval, truthful status, append-only journaling, safe resume, and
  deterministic adapter fakes while preserving the AP-M7 and W3 interfaces.

The handoff authorizes repository implementation of the interactive core only. It does not
authorize AP-M9-W5 implementation, repository-setting changes, credentials, backend
initialization, an authenticated plan or apply, a cloud or DNS mutation, deployment, Application
Adoption, or Live qualification.
