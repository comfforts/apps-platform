# Repository engineering instructions

This file contains durable working rules for this repository. Product behavior, architecture,
active delivery sequence, evidence gates, and operator procedures belong in the project
documentation. [docs/README.md](docs/README.md) is the canonical router to that authority.

## Before modifying the repository

1. Read [docs/README.md](docs/README.md) completely and follow its task-specific reading order.
   Read every document it marks as required for the task before editing.
2. Inspect the working tree and current branch. Preserve unrelated changes and do not overwrite
   work whose ownership is unclear.
3. State the active slice and every requirement, decision, plan, evaluation, and threat identifier
   required by the documentation for that slice. Treat absent authority as unresolved rather than
   inferred.
4. Map each planned behavior and file placement to its governing documentation before editing. A
   branch name, discussion history, historical record, example, or prompt is not a substitute for
   active authority.
5. Trace every claimed operator or user journey to an executable entry point and deterministic
   tests. Documentation, reserved interfaces, static configuration, and local fakes support only
   the claims assigned to them by the active evaluation authority.
6. Stop for direction when authority is absent, the requested change expands the approved slice,
   or completing it would change an external system, credential, protected state, or separately
   owned resource outside the documented authority.

## Authority routing

- Use the precedence, status meanings, completed/next sequence, and task-specific reading branches
  in `docs/README.md`. Do not recreate them in this file.
- Use the product requirements and accepted architecture decisions reached through that router as
  the source of truth for behavior. Use the active design, contracts, plan, evaluation strategy,
  threat model, layout, and runbooks for their documented responsibilities.
- Treat historical material as evidence, not current instruction, unless the documentation router
  explicitly activates it. Treat prompts as bounded entry points subordinate to the authority they
  cite.
- Keep claims truthful: repository implementation, merge, deployment, qualification, and adoption
  are distinct states unless the active evaluation authority says otherwise.
- Keep each project-specific rule in its authoritative project document. Update that source and
  its consumers together instead of copying milestone or product rules into `AGENTS.md`.

## Safety and scope

- Preserve repository, security, secret-handling, source-control, and destructive-action
  guardrails throughout a change. Use the smallest exact target and a recoverable operation when
  one is available.
- Keep credentials, secret values, protected state, saved plans, authenticated browser state, and
  unredacted external payloads out of Git and review artifacts.
- Use only the external-operation entry points and approval boundaries defined by the active
  authority. An approved implementation slice does not implicitly authorize an external mutation.
- Keep repository-owned implementation, contracts, tests, documentation, prompts, and permitted
  evidence inside this repository. Do not import authority from another project.
- Update a public contract and all repository consumers in the same bounded slice. Record
  unimplemented behavior as planned rather than operational.

## Code documentation

- Treat documentation debt as touched-code work. For every undocumented function or method
  encountered while tracing or changing the requested execution path, add or update a docstring
  that describes its complete current behavior. Cover inputs, outputs, side effects, state
  transitions, external interactions, failure behavior, and important invariants or authority
  boundaries when they apply. Keep trivial implementation details in the code rather than
  restating it line by line.
- Keep an existing module docstring and component `README.md` current when a change affects that
  module or component's responsibility, architecture, behavior, usage, entry points, ownership, or
  external boundaries.
- When relevant module or component documentation does not exist, report the gap and ask the owner
  whether complete current-state documentation should be created. Treat that work as an explicit
  scope decision instead of silently expanding the active slice.
- Describe implemented behavior truthfully, mark future behavior as planned, and update
  documentation and deterministic tests with the implementation they describe.

## Branch and review workflow

- Start each new approved slice from an updated, clean `main` on a dedicated semantically named
  branch unless the active plan explicitly defines an atomic multi-slice integration branch. For
  that bounded exception, create the integration branch from updated clean `main`, create each
  slice from the latest clean integration branch, and target every slice pull request back to that
  integration branch.
- Treat milestones and work packages as planning containers rather than automatic branch or pull-
  request boundaries. Decompose a substantial work item into ordered, independently reviewable
  functional slices; give each slice its own branch and pull request, and merge it before beginning
  the next slice.
- Keep an explicitly planned integration branch isolated from `main` until every required slice and
  integration-level gate passes. Freeze an exact qualified integration revision before its
  cumulative pull request to `main`; any later tracked change invalidates that qualification and
  requires the documented gate to run again. Use the active plan for the integration branch name,
  synchronization rule, ordered slices, and completion evidence.
- Name branches `<type>/<short-scope>` using the primary change: `docs/` for documentation or
  governance-only work, `feat/` for product behavior, `fix/` for defect correction, `evidence/`
  for qualification evidence, and `chore/` for small maintenance. Use an owner-specified branch
  name when provided; never substitute an author or tool name such as `codex/` for the change type.
- Keep `<short-scope>` functionality-oriented. Omit milestone and work-package identifiers from
  branch names; name a `feat/` branch for the behavior that its slice delivers.
- Keep one bounded slice per pull request. Merge it before starting the next documented slice.
- Plan each slice for approximately five to eight coherent commits. Treat that range as a scope
  signal, not a reason to split one atomic cross-cutting change artificially.
- Before creating a ninth substantive commit, stop and reassess the slice with the owner. Report
  completed and remaining work, and propose a follow-up slice when the remainder adds a lifecycle,
  authority boundary, contract family, or independently reviewable outcome. Newly discovered work
  does not enter the current slice merely because it was found during implementation.
- Use small coherent commits that remain independently reviewable. When the owner requests
  commit-by-commit review, leave each change uncommitted until approval.
- During unmerged development, use amendments or fixup commits and consolidate them before pull-
  request handoff when that makes the history clearer. Preserve owner-approved commit-by-commit
  checkpoints, and never rewrite published history without owner approval.
- Keep later-slice implementation out of the current branch even when its directories or
  interfaces are already reserved.
- Follow the completed/next sequence in `docs/README.md`; do not infer a new sequence from branch
  names or discussion history.

## Verification and handoff

- Run focused deterministic tests while editing, then run `make check` from the dedicated
  repository root before handoff and report the actual result.
- Keep `make check` credential-free, deterministic, and non-mutating. Use separately documented
  operator entry points for authenticated plans, applies, DNS, identity, deployment,
  qualification, destruction, or other external operations.
- Report the evaluated revision, relevant commands, failures, errors, warnings, skips, and known
  limitations required by the active evaluation authority. A pull-request merge records repository
  progress; it does not by itself prove an external or runtime result.
