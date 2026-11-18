# AP-M8 qualification-deployment runbook

Status: AP-M8-W1 authority proposal only; no repository setting, identity, credential, backend,
provider, DNS, traffic, or deployment action is authorized

This runbook is subordinate to the App Platform requirements, accepted ADRs, system design,
implementation plan, evaluation strategy, and threat model. It will define the human checkpoints
for AP-M8-W2 through AP-M8-W12 after the complete AP-M8-W1 authority is owner-accepted and merged.
Its presence in the repository never authorizes an external mutation.

Requirements: AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003 through AP-QR-006

Decisions: ADR-001, ADR-004, ADR-007

Threats: AP-TM-004, AP-TM-005, AP-TM-007 through AP-TM-011, AP-TM-013, AP-TM-014

Plan: AP-M8-W1, AP-M8-W3, AP-M8-W4

## Checkpoint rule

The owner first approves and merges the complete AP-M8-W1 authority. AP-M8-W2 then records the
exact operator-input manifest. AP-M8-W3 and AP-M8-W4 each require a new explicit approval against
that manifest immediately before their external changes. Approval for one checkpoint, setting,
environment, workflow, root, operation, identity, or IAM binding cannot be reused for another.

Before requesting either mutation approval, the operator must present a secret-free proposed-
change table containing:

- the protected `main` source revision and clean repository readback;
- the exact current setting or IAM binding, proposed value, and reason;
- the environment class, rendered workflow path, root, operation, and operation identity;
- the exact GitHub repository and owner numeric identifiers;
- the Workload Identity Pool and provider resource references;
- the requested provider permissions and their resource scope;
- the readback command or API field that will prove the result; and
- the smallest recoverable reversal for only that checkpoint's changes.

A missing, placeholder, synthetic, secret-bearing, discovered, over-broad, or unreviewed value
blocks the checkpoint. The operator does not open an authenticated session merely to fill an
authority gap.

## AP-M8-W3 protected repository baseline

Checkpoint 3 of repository extraction established the repository baseline. AP-M8 preserves and
reads back all of these controls before creating a deployment environment or executable workflow:

| Control | Required state |
| --- | --- |
| Repository and default branch | `comfforts/apps-platform`; `main` is the default branch |
| Main ruleset | Active for the default branch, no bypass actor, deletion restricted, force push blocked |
| Merge gate | Pull request required, branch must be current, `Credential-free project checks` required |
| Code scanning | CodeQL default setup enabled; security results required at High or higher and standard scanning results at Errors |
| Actions policy | Actions pinned to full commit identifiers; repository default permissions read-only |
| Supply-chain and secret controls | Dependency Graph and dependency review available; secret scanning and push protection enabled |
| Existing executable workflow | `.github/workflows/check.yml` remains credential-free with only `contents: read` |

Any absent, disabled, bypassed, or weakened baseline control stops AP-M8-W3. AP-M8 does not use an
environment or federation binding to compensate for a weaker branch rule. A separately approved
repair restores the baseline before AP-M8 continues and may not introduce an apply authority.

### Environment classes

AP-M8 uses three distinct protected GitHub Environment classes. Their exact real names are
AP-M8-W2 operator inputs and may not use a synthetic example value:

| Class | Permitted authority | Required protections |
| --- | --- | --- |
| Plan | Authenticated provider and state reads needed for one advisory or exact-main plan | Exact `main` deployment branch; explicit owner review for every job; no environment secret |
| Apply | Same-job application of one exact reviewed plan for one root | Exact `main` deployment branch; fresh explicit owner review for every job; no environment secret |
| Recovery | One separately approved rollback, force-unlock, or destroy operation | Exact `main` deployment branch; fresh operation-specific owner review; no environment secret; no reused approval |

The same person may trigger and approve in this owner-operated demo, but GitHub must still create a
distinct environment review event after the exact source, root, operation, and digest are visible.
There is no approval bypass, branch or tag wildcard, wait-timer substitute, environment credential,
or unprotected fallback. Non-secret environment variables may hold only reviewed resource
references from the operator-input manifest.

The GitHub OIDC subject for each class is exactly:

```text
repo:comfforts/apps-platform:environment:<exact-protected-environment-name>
```

Changing an environment name changes the subject and requires a new AP-M8-W3 setting approval,
AP-M8-W4 federation review, and readback before use.

### Executable workflow boundary

AP-M8-W3 does not render a workflow; AP-M8-W6 owns that later change. The protected-source profile
requires every future executable operator workflow to:

- exist as one reviewed `.github/workflows/` file for one operation and one root, with the root,
  operation, environment, identity, provider, repository, and protected ref fixed rather than
  selected by an untrusted dispatch input;
- use `workflow_dispatch` only and reject every repository, ref, revision, environment, root, or
  operation mismatch before requesting credentials;
- set workflow-level permissions to `contents: read` and grant `id-token: write` only to the single
  federated job after its protected environment review;
- pin every action to a full commit identifier, disable checkout credential persistence, and read
  no GitHub Actions secret;
- use root-scoped non-cancelling concurrency and the backend lock; and
- retain no OIDC token, generated credential file, saved plan, provider payload, or authenticated
  cache after the job.

The check workflow never receives `id-token: write`. A pull-request event, tag, fork, reusable
workflow not named in the manifest, mutable action reference, runtime-selected service account, or
workflow with repository write permission cannot receive AP-M8 authority.

## AP-M8-W4 federation and operation-identity profile

AP-M8 uses one dedicated GCP Workload Identity Pool and GitHub OIDC provider in project
`comfforts-platform-non-prod` (`455651441682`). Their exact resource identifiers remain AP-M8-W2
inputs. They are not shared with Finance Assistant, another repository, a production environment,
or an application project.

The provider accepts only issuer `https://token.actions.githubusercontent.com` and the exact
provider audience recorded in the operator-input manifest. Its attribute mapping is limited to:

| Google attribute | GitHub claim |
| --- | --- |
| `google.subject` | `assertion.sub` |
| `attribute.repository` | `assertion.repository` |
| `attribute.repository_id` | `assertion.repository_id` |
| `attribute.repository_owner_id` | `assertion.repository_owner_id` |
| `attribute.ref` | `assertion.ref` |
| `attribute.ref_protected` | `assertion.ref_protected` |
| `attribute.workflow_ref` | `assertion.workflow_ref` |
| `attribute.environment` | `assertion.environment` |
| `attribute.event_name` | `assertion.event_name` |
| `attribute.sha` | `assertion.sha` |

The provider condition and every service-account impersonation binding must jointly require the
exact repository name and numeric identifier, exact repository-owner numeric identifier,
`refs/heads/main`, protected-ref claim, one allow-listed rendered workflow at
`refs/heads/main`, one reviewed environment name and matching subject, and
`workflow_dispatch`. The workflow separately compares the token/run source SHA with the exact
40-character protected-main revision in the approved workflow configuration. Repository or owner
names without their numeric identifiers are insufficient because a renamed or recreated repository
must not inherit trust.

### One identity per root and operation

No operation identity spans roots or operations. AP-M8-W2 must name one distinct service account
and one exact workload-identity impersonation binding for every enabled cell in this matrix:

| Operation | Environment class | Permitted provider authority |
| --- | --- | --- |
| Plan | Plan | Read the selected root's backend and only the provider metadata required to calculate and read back its plan; no mutation |
| Apply | Apply | Read and write the selected root's backend and mutate only resources owned by that root through one reviewed same-job plan |
| Rollback | Recovery | Read and write the selected root's backend and perform only the reviewed rollback plan for that root |
| Force-unlock | Recovery | Inspect the selected root's lock and remove only the exact approved lock identifier; no provider-resource mutation |
| Destroy | Recovery | Read and write the selected root's backend and delete only the exact reviewed resources owned by that root through one reviewed destroy plan |

An identity is enabled only when its rendered workflow path, root, operation, environment, service
account, exact permission list, resource scopes, and impersonation principal are present in the
operator manifest. Unused rollback, force-unlock, and destroy cells retain no binding. Import,
state push, backend migration, federation administration, IAM administration, and project-wide
administration remain outside this matrix and require later break-glass authority if ever needed.

Workload identities receive no owner, editor, IAM administrator, service-account administrator,
project IAM administrator, billing administrator, or user-managed-key permission. They cannot
alter the Workload Identity Pool/provider, their own service account or impersonation policy,
another operation identity, another root's backend, or an application-owned resource. Federated
credentials last no longer than one hour and no service-account key may exist.

### Bootstrap exception

Creating the pool, provider, operation service accounts, and initial impersonation and resource
bindings requires a separately approved, short-lived owner credential because the federated path
does not yet exist. That credential is never stored in GitHub or the repository, never exported as
evidence, and is revoked or allowed to expire immediately after readback. The bootstrap identity
change records exact commands and results in the private redacted evidence destination and grants
no workload identity permission to administer federation or IAM.

This identity bootstrap is separate from Terraform backend bootstrap. Approval or success for one
does not authorize the other.

## Readback and stop conditions

AP-M8-W3 readback covers the default branch, ruleset target and bypass list, merge and required-
check rules, CodeQL threshold, action pinning, default permissions, secret controls, and each
environment's branch policy, reviewers, variables, and absence of secrets.

AP-M8-W4 readback covers the pool/provider issuer, audience, state, attribute mapping and condition;
every service account's user-managed-key count; every impersonation principal; every direct and
inherited IAM role; and the exact root, operation, workflow, environment, and resource scope. It
must also prove that no Finance, production, real-application, or cross-root principal entered the
change.

Any unexpected bypass, wildcard, alternate ref, alternate event, missing numeric binding, secret,
stored key, broad role, cross-root permission, provider mismatch, inherited permission, or
unreviewed change stops the checkpoint. There is no automatic retry, policy broadening, rollback,
or cleanup. The operator reports the partial state and obtains a new exact approval before changing
it.

Readback records only non-secret setting names, resource references, numeric repository identifiers,
workflow/environment/root/operation bindings, role identifiers, source revisions, timestamps,
coarse outcomes, and hashes. OIDC tokens, generated credentials, IAM access tokens, raw provider
responses, browser state, and environment dumps are prohibited.
