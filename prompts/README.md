# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W6 interactive platform deployment handoff](starting_prompt.md) starts a new chat from
  updated, clean `main` only after the AP-M9-W5 pull request merges. It composes the implemented
  lifecycle core and Terraform policy into one staged interactive deployment engine exercised
  through deterministic command and transcript fakes.

The handoff authorizes repository implementation of deployment mechanics only. The pull request
must not authenticate, initialize or migrate a real backend, run an authenticated plan or apply,
mutate cloud or DNS, create credentials, deploy staging, change Finance Assistant, claim
Application Adoption, or collect Live evidence.
