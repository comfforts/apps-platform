# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W10 staging operation handoff](starting_prompt.md) starts a new chat
  from updated, clean `main` only after the AP-M9-W8 pull request merges. It adds the interactive
  synthetic application-owner deployment, status, handoff, registration, and destruction path.

The handoff authorizes repository implementation of Fixture Application deployment mechanics only.
The pull request must not authenticate, initialize or migrate a real backend, run an authenticated
plan or apply, mutate cloud or DNS, publish a live image or generation, deploy or destroy staging,
change Finance Assistant, claim Application Adoption, or collect Live evidence.
