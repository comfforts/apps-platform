# App Platform prompts

Prompts are bounded task entry points, not architecture authority. Each prompt must link to the
platform documentation required for its task instead of copying requirements, decisions, or
acceptance criteria.

- [AP-M9-W8 qualification and safe destruction handoff](starting_prompt.md) starts a new chat from
  updated, clean `main` only after the AP-M9-W7 pull request merges. It adds revision-bound
  synthetic qualification, strict redacted evidence, reviewed generation rollback, failure
  injection, fixture cleanup boundaries, and safe Platform Environment destruction.

The handoff authorizes repository implementation of qualification and safe-destruction mechanics only. The
pull request must not authenticate, initialize or migrate a real backend, run an authenticated plan
or apply, mutate cloud or DNS, publish or roll back a live generation, deploy or destroy staging,
change Finance Assistant, claim Application Adoption, or collect Live evidence.
