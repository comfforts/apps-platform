# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M8 authority handoff](starting_prompt.md) starts a new chat from updated, clean `main` only
  after the AP-M7 pull request merges. The prompt loads the approved Contract, Fixture, planning,
  local-runtime, and static Terraform/workflow boundaries before proposing detailed AP-M8
  qualification-deployment authority.

The handoff prompt authorizes only an AP-M8 authority proposal after owner direction. It does not
authorize repository-setting changes, federation, credentials, backend initialization, an
authenticated plan or apply, a cloud or DNS mutation, deployment, Application Adoption, or Live
qualification.
