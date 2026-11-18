# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M8-W2 manifest-acceptance handoff](starting_prompt.md) starts a new chat from updated, clean
  `main` only after the W2 repository-support pull request merges. The prompt loads the accepted
  authority and implemented local manifest interface before the first real manifest is created and
  validated outside Git.

The handoff prompt authorizes only the post-merge creation, deterministic validation, and explicit
owner acceptance of one bounded non-secret AP-M8-W2 manifest revision. It does not authorize
AP-M8-W3, repository-setting changes, federation, credentials, backend initialization, an
authenticated plan or apply, a cloud or DNS mutation, deployment, Application Adoption, or Live
qualification.
