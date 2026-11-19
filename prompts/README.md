# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W5 deployable Terraform lifecycle handoff](starting_prompt.md) starts a new chat from
  updated, clean `main` only after the AP-M9-W4 pull request merges. It reshapes the AP-M7 static
  roots into lifecycle phases, implements deterministic backend rendering, identity and
  impersonation profiles, plan policy, typed outputs, and mocked plans while preserving W4.

The handoff authorizes repository implementation of the Terraform lifecycle only. It does not
authorize AP-M9-W6 implementation, repository-setting changes, credentials, backend initialization
or migration, an authenticated plan or apply, a cloud or DNS mutation, deployment, Application
Adoption, or Live qualification.
