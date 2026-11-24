# Repository extraction handoff

Status: checkpoints 1 through 5 owner-approved and complete; `comfforts/apps-platform` is the
canonical App Platform repository

This secret-free record is subordinate to the
[repository extraction runbook](runbooks/repository_extraction.md). It records repository
continuity for AP-PR-008, AP-PR-009, AP-QR-003, AP-QR-004, AP-QR-006, ADR-004, ADR-007,
AP-TM-010, AP-TM-011, and AP-TM-014. It supplies no AP-M7, Terraform, provider, cloud, DNS,
identity, deployment, Live, or Application Adoption authority.

## Extraction identity

| Evidence | Observed value |
| --- | --- |
| Source repository | `https://github.com/hankgalt/ai_finance_assitant.git` |
| Source revision | `f5f7cef84a0d7e2850e496f8ce56f3afdb7944c6` |
| Source prefix | `apps-platform/` |
| Source subtree | `d120aa3c5608dce78000a014d7bc12fd5a25555b` |
| Reproducible split revision | `66ae90b2760c44f4142236ac96c472ab1e748c60` |
| Extracted root tree | `d120aa3c5608dce78000a014d7bc12fd5a25555b` |
| Target repository | `https://github.com/comfforts/apps-platform.git` |
| Initial target refs | Empty before the approved initial push |
| Target `main` after push and clean readback | `66ae90b2760c44f4142236ac96c472ab1e748c60` |
| Target default branch | `main` |

The source subtree and extracted root tree are identical. Repeating `git subtree split` for the
fixed source revision produced the same split revision. A clean target readback clone confirmed the
pushed commit and root tree. Application-specific migration authority remained outside App
Platform authority throughout extraction.

## Toolchain and deterministic verification

The extraction and clean-readback verification used Git 2.50.1 (Apple Git-155), uv 0.12.5, and
Python 3.12.0. Frozen dependency synchronization and lock validation passed. The source repository
and extracted target each passed the complete 189-test deterministic gate with no reported failure
or error. The original wall-clock durations, warning lines, and skip counts were not separately
retained in the supplied checkpoint evidence; the revisions, tree identities, test totals, and
outcomes were retained.

The first reconciliation change was verified from the dedicated root with uv 0.12.5 and Python
3.12.12:

```text
uv sync --frozen --python 3.12.12
make check
```

The frozen setup installed 37 locked packages into the ignored local `.venv`. The final
credential-free `make check` invocation completed in 4.70 seconds of observed wall time and passed
all 189 tests: 32 governance and integration-draft, 49 contract, 18 Fixture, and 90 runtime tests.
`git diff --check` also passed. The verified first reconciliation commit and tree are:

| Evidence | Observed value |
| --- | --- |
| Commit | `a12da61450c0ca970d8b8662841a5462771c72ee` |
| Tree | `4f33144e8115005a6d5d9188b7e47adb653b498b` |
| Subject | `docs(repository): reconcile the dedicated project root` |

Two preliminary local invocations did not qualify the change. The first selected host Python 3.14.2
without the locked runtime packages. After frozen setup, the desktop sandbox denied the two
explicit process-local loopback binds. Re-running the unchanged gate with only that sandbox
restriction lifted passed; the tests made no external connection and used no credential.

The dedicated reconciliation pull request retained two small commits and merged without rewriting
them:

| Evidence | Observed value |
| --- | --- |
| Root-reconciliation commit | `a12da61450c0ca970d8b8662841a5462771c72ee` |
| Root-reconciliation tree | `4f33144e8115005a6d5d9188b7e47adb653b498b` |
| Handoff-record commit | `6ecd60079dc87458fac993222cbb9e789d2e78ac` |
| Handoff-record tree | `8a0615e56149130814b371db4c5d9cb6ca23c52f` |
| [Dedicated reconciliation pull request](https://github.com/comfforts/apps-platform/pull/1) | Merged 2026-11-17 at 15:39 PST |
| Reconciliation merge commit | `22f32da94854bbc265d40c8125f56b4efbbe7558` |
| Reconciliation merge tree | `8a0615e56149130814b371db4c5d9cb6ca23c52f` |

The pull request's required `Credential-free project checks`, CodeQL Actions analysis, and CodeQL
checks succeeded. A clean, updated dedicated clone read back `main` at the exact merge commit before
this governance closeout branch was created.

## GitHub workflow evidence

| Workflow | Revision and result |
| --- | --- |
| [Initial App Platform checks run](https://github.com/comfforts/apps-platform/actions/runs/44192487649) | Run 44192487649 on `main` at `66ae90b`; success on 2026-11-17 at 14:41 PST; 34 seconds total; `Credential-free project checks` completed in 30 seconds; no artifact |
| [Initial Dependency Graph run](https://github.com/comfforts/apps-platform/actions/runs/44195072491) | Run 44195072491; success on 2026-11-17 at 14:58 PST; 44 seconds |
| [Initial CodeQL run](https://github.com/comfforts/apps-platform/actions/runs/44195292276) | Run 44195292276 using default setup; success on 2026-11-17 at 14:59 PST; 57 seconds; the security overview recorded the scan at 15:00 PST |
| [Post-merge App Platform checks](https://github.com/comfforts/apps-platform/actions/runs/44201272475) | Run 44201272475 on `main` at `22f32da`; success after reconciliation merge |
| [Post-merge CodeQL analysis](https://github.com/comfforts/apps-platform/actions/runs/44201272079) | Run 44201272079 on `main` at `22f32da`; success after reconciliation merge |

These runs qualify only repository checks and security-tool availability. They do not supply Live or
Application Adoption evidence.

## Checkpoint 3 repository settings

The owner completed checkpoint 3 and the settings readback observed:

- `main` is the default branch.
- The active `main pull-request gate`
  [ruleset](https://github.com/comfforts/apps-platform/settings/rules/27504912) has identifier
  `27504912`, targets the default branch, and has no bypass actor.
- The ruleset restricts branch deletion and blocks force pushes.
- Normal changes require a pull request with zero required approving reviews. Dismiss-stale-review,
  code-owner-review, and last-push-approval requirements are disabled. GitHub displays its
  additional-approval option for unattributed Copilot-authored pull requests, but with zero required
  reviews it creates no effective approval requirement.
- `Credential-free project checks`, sourced from GitHub Actions, is required and the branch must be
  up to date before merge.
- CodeQL results are required at security severity `High` or higher and standard scanning severity
  `Errors`.
- Actions must be pinned to a full-length commit SHA. Default workflow permissions are read-only for
  repository contents and packages.
- Dependency Graph is enabled. Dependency review is available for pull-request changes; checkpoint
  3 added no separate dependency-review workflow or required check.
- Secret scanning through Secret Protection and push protection are enabled.
- Code scanning uses CodeQL default setup, and its initial analysis completed successfully.

Checkpoint 3 created no Actions secret, cloud credential, OIDC trust, Workload Identity Federation
binding, protected deployment environment, Terraform state, saved plan, or apply authority.

## Completed approvals and canonical cutover

| Checkpoint | Status |
| --- | --- |
| 1. Source revision and dry-run extraction | Owner-approved and complete |
| 2. Exact initial push | Owner-approved and complete |
| 3. Dedicated-repository settings and required checks | Owner-approved, configured, and read back |
| 4. Reconciliation pull request and canonical-authority cutover | Owner-approved and complete; pull request merged with required checks passing, then the owner explicitly declared `comfforts/apps-platform` canonical |
| 5. Source-tree and CI-wrapper cleanup | Owner-approved and complete through a separate source-repository pull request |

After the reconciliation pull request merged and its required checks passed, the owner explicitly
declared `comfforts/apps-platform` canonical on 2026-11-17. The declaration—not the extraction or
reconciliation commit—performed the authority cutover. Platform changes now occur only in this
dedicated repository.

The separately reviewed source cleanup completed through
[source pull request 70](https://github.com/hankgalt/ai_finance_assitant/pull/70), merged on
2026-11-17 at 16:49 PST as `b049be2bd4e8969a4160f05f6e0943092bace780`. Its required checks
passed. A later read-only source `main` readback at
`5a44dd16e4976a24e9e1a4256cc4769c18eaa86a` confirmed that the tree contains neither the
`apps-platform/` directory nor `.github/workflows/apps-platform-ci.yml`.

Checkpoint 5 changed only the containing repository's platform copy, wrapper, and boundary notes.
Finance Assistant requirements, application behavior, infrastructure, state, DNS, identity,
deployment, and access remain unchanged. AP-M7 and every later provider or application slice remain
outside this extraction and require their own proposal, approval, implementation, and evidence.
