# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M8 implementation handoff](starting_prompt.md) starts a new chat from updated, clean `main`
  only after the AP-M8 authority pull request merges and the owner explicitly accepts the complete
  AP-M8-W1 profile. The prompt loads the approved Contract, Fixture, planning, local-runtime,
  static Terraform/workflow, and proposed qualification-deployment boundaries before AP-M8-W2.

The handoff prompt authorizes only the bounded, non-secret AP-M8-W2 operator-input manifest after
owner direction. It does not authorize AP-M8-W3, repository-setting changes, federation,
credentials, backend initialization, an authenticated plan or apply, a cloud or DNS mutation,
deployment, Application Adoption, or Live qualification.
