# App Platform runbooks

Status: subordinate operator procedures; no action is authorized merely because a runbook exists

Runbooks translate accepted App Platform authority into explicit human-operated procedures. They do
not replace requirements, accepted architecture decisions, system design, implementation plans, or
evaluation gates. Every external mutation still requires the approval named by its runbook.

- [Repository extraction](repository_extraction.md) governs the history-preserving extraction that
  established `https://github.com/comfforts/apps-platform.git`; all five checkpoints are complete.
  It performed no cloud, DNS, identity, Terraform, deployment, or Application Adoption action.
- [Repository extraction handoff](../repository_extraction_handoff.md) records the secret-free
  extraction, workflow, repository-setting, reconciliation, cutover, and cleanup evidence.
- [AP-M9 environment lifecycle](environment_lifecycle.md) is the current operator-product design.
  W5 adds repository-only Terraform lifecycle policy while preserving credential-free preparation
  and local status; every mutating command remains unavailable until its named AP-M9 package
  implements and qualifies it.
- [Historical AP-M8 qualification deployment](qualification_deployment.md) preserves the
  superseded manifest-driven procedure. It is excluded from the active reading order and provides
  no current action authority.

Runbooks never contain credentials, Terraform state, saved plans, authenticated browser state, or
unredacted provider output. A failed or incomplete procedure stops for inspection and does not
silently advance project status.
