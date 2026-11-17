# App Platform runbooks

Status: subordinate operator procedures; no action is authorized merely because a runbook exists

Runbooks translate accepted App Platform authority into explicit human-operated procedures. They do
not replace requirements, accepted architecture decisions, system design, implementation plans, or
evaluation gates. Every external mutation still requires the approval named by its runbook.

- [Repository extraction](repository_extraction.md) governs the history-preserving extraction that
  established `https://github.com/comfforts/apps-platform.git` and the remaining reconciliation,
  canonical-cutover, and source-repository-cleanup checkpoints. It performs no cloud, DNS,
  identity, Terraform, deployment, or Application Adoption action.
- [Repository extraction handoff](../repository_extraction_handoff.md) records the secret-free
  extraction, workflow, repository-setting, approval, and remaining-checkpoint evidence.

Runbooks never contain credentials, Terraform state, saved plans, authenticated browser state, or
unredacted provider output. A failed or incomplete procedure stops for inspection and does not
silently advance project status.
