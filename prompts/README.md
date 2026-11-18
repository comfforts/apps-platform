# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [Terraform-and-workflow handoff](starting_prompt.md) starts a new chat from updated `main` after
  AP-M7-W6 is owner-accepted and committed. The extraction handoff records AP-M6, reconciliation,
  canonical cutover, and source cleanup as complete. The prompt loads the approved Contract,
  Fixture, planning, local-runtime, and AP-M7 authority boundaries before AP-M7-W7.

The handoff prompt authorizes only the next named AP-M7 work package after owner approval. It does
not authorize backend initialization, an authenticated plan or apply, a cloud or DNS mutation,
identity configuration, repository-setting changes, deployment, Application Adoption, or Live
qualification.
