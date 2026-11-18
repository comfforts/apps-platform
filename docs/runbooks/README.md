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
- [AP-M8 qualification deployment](qualification_deployment.md) is the complete AP-M8-W1 proposed
  procedure for protected repository, federation, backend, deployment, DNS/TLS, and evidence
  checkpoints. Until the authority pull request is merged and the complete AP-M8-W1 profile is
  explicitly owner-accepted, it authorizes no AP-M8-W2 implementation or operator action.

Runbooks never contain credentials, Terraform state, saved plans, authenticated browser state, or
unredacted provider output. A failed or incomplete procedure stops for inspection and does not
silently advance project status.
