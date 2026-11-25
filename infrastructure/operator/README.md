# AP-M9 lifecycle operator

Status: AP-M9-W9 cross-project fixture lifecycle correction in progress; candidate staging is not accepted qualification

This package keeps lifecycle orchestration behind `LifecycleOperator`. Preparation and status use
injected Git, GitHub, GCP, Terraform, DNS, terminal, filesystem, and clock boundaries. Deployment
uses an immutable `StageContext` and an injected `DeploymentExecutor`, so deterministic command
fakes and the non-fake command boundary exercise the same orchestration interface.

## Implemented commands

The deploy target populates or verifies the checksum-bound local toolchain automatically. The
operator must already have an active `gcloud` login, user Application Default Credentials, and the
staging project selected:

```bash
make platform-preflight ENVIRONMENT=staging
make platform-preflight-check ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-deploy-check ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-prepare ENVIRONMENT=staging
make platform-status ENVIRONMENT=staging
make platform-deploy ENVIRONMENT=staging
make fixture-project-bootstrap \
  ENVIRONMENT=staging \
  FIXTURES_PROJECT_ID=comfforts-fixtures-nonprod \
  FIXTURES_PROJECT_NAME="Comfforts Fixtures Non-Prod"
make platform-connect-project \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod
make application-handoff-check \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod \
  APPLICATION_ID=fixture-authenticated \
  ACCESS_MODE=authenticated \
  ROUTE_INTENT=/fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  PLATFORM_GENERATION=1
make platform-outputs \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod \
  APPLICATION_ID=fixture-authenticated \
  ACCESS_MODE=authenticated \
  ROUTE_INTENT=/fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  PLATFORM_GENERATION=1
make platform-register \
  ENVIRONMENT=staging \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.json \
  REGISTRATION_INTENT=/private/path/registration-intent.json
make platform-detach \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  GENERATION_DIGEST=sha256:<64-lowercase-hex>
make platform-retire \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  GENERATION_DIGEST=sha256:<64-lowercase-hex>
make platform-qualify ENVIRONMENT=staging
make platform-destroy ENVIRONMENT=staging
make fixture-handoff \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-authenticated \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v1.json
make fixture-status ENVIRONMENT=staging
make fixture-status ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated
make fixture-destroy ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated
```

Fixture handoff and destroy always require one fixture application identifier and operate only that
fixture's Application State. Destruction additionally requires a prior platform detachment.
Fixture status is suite-wide by default and accepts the same optional identifier when a
single-fixture readback is more useful.

`platform-status` is observational. It reports the current checkout source, the source recorded by
the last deployment operation, and the source serving the active Shared Edge separately. Expected
differences are source diagnostics, not command failures; unreadable or inconsistent lifecycle
state remains a blocker.

`fixture-handoff` is the application-owned deployment step. It consumes an existing project-scoped
Platform Integration Bundle, deploys or reconciles the selected fixture in the dedicated fixture
project, and prints the canonical Platform Integration Bundle, Application Attachment Bundle, and
registration-intent paths, but does not register the fixture. Registration remains the separate
`platform-register` operation. A repeated handoff reuses the exact pair only when every source,
project connection, generation, image, digest, relationship, and provider binding is unchanged.

On success, fixture handoff prints a concise human-readable completion message in addition to its
machine-readable JSON and explicitly says that the fixture is not yet routed. Platform registration
reports activation without claiming that registration readback is full live qualification.

Accepted Source is the default and requires exact clean current `main`. To verify a pull request
against real staging provider behavior before merge, first push the clean branch and add
`SOURCE_AUTHORITY=candidate` to every command. Candidate mode requires `origin/<branch>` to equal
`HEAD` and current `origin/main` to be an ancestor. It is refused for production. Its authority is
digest-bound in the specification, status, bundles, and evidence; qualification writes beneath the
separate `qualification/candidates/` path and never replaces accepted evidence. After merge, rerun
the journey from main with the default Accepted Source.

Standalone preflight is the readiness-only command. It verifies source, profile, tools, active
human account, user Application Default Credentials, provider project, ownership, and readable
provider prerequisites without retaining a token or writing a specification, digest, approval,
progress, plan, or deployment working state. Its stderr trace identifies the invocation, selected
fixture or lack of one, environment profile, exact source snapshot, each bounded non-secret adapter
result, and plain-language blocker guidance. Its single stdout record is the final JSON result.
Neither stream includes tokens, secret values, raw provider payloads, Terraform state, or saved
plans.

The default `PREFLIGHT_MODE=operational` enforces the selected Accepted or Candidate Source policy.
For local code maintenance, `platform-preflight-check` runs the same read-only profile, Git,
GitHub, GCP, ADC, Terraform-tool, and DNS checks. It skips `SOURCE_NOT_CLEAN`, because the command
exists to inspect uncommitted changes, and reports other source-admission findings separately
without making them block the diagnostic run:

```bash
make platform-preflight-check ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
```

The preflight check never arms an executor, creates or approves a specification, writes lifecycle
state, runs Terraform setup or planning, emits an operational artifact, or changes a provider.

`platform-deploy-check` constructs the separate read-only checker and uses the working tree plus
real provider and Terraform state. It validates retained specification/progress records, plans with
state locking disabled, evaluates the normal plan policy, deletes each ephemeral saved plan, and
returns stage-level `pass`, `would-change`, `manual`, `deferred`, or `blocked` results plus an
explicit platform result of `ready`, `reconciliation-required`, `incomplete`, or `blocked`.
Required platform services and the platform-owned foundation, Shared VPC egress, Shared Edge,
active runtime, TLS, and final readback belong to this module. Its interface exposes no apply,
provider-action, checkpoint-execution, approval, or lifecycle-state write method.
`SOURCE_NOT_CLEAN` is omitted; other source-admission findings remain visible but non-blocking, and
the result grants no operational authority. Default deployment consumes this result before approval
or mutation and still creates fresh exact plans for execution.

`application-handoff-check` consumes the platform-ready result without interpreting stage names,
then reads the named application project, its required services, Shared VPC and subnet grants,
bundle inputs, and requested access-mode and identity projection. The command publishes no bundle,
arms no apply path, and writes no operational lifecycle state. Run it immediately before
`platform-outputs` with the same application-scoped values.

Standalone preparation repeats those checks and remains an optional specification dry run. It
writes, displays, and approves the complete private specification without an external mutation.
The normal deploy command first revalidates and automatically reuses the current approved specification when its
source, profile, environment, session, project, ownership, tools, and readable provider facts remain
valid. It does not require the operator to copy the digest. When current approved intent is absent,
stale, or unapproved, deploy builds the complete Deployment Specification, writes canonical bytes,
asks for approval, and continues in the same process. Malformed retained state and current blockers
fail closed. Status is read-only. Production remains blocked by
`OWNERSHIP_TRANSFER_REQUIRED`.

Deploy accepts only the exact current, approved specification. It follows one fixed readable
workflow for preflight, reviewed
bootstrap-service enablement, backend bootstrap, foundation, immutable image and closed initial
Registration Generation publication or active-generation preservation, OAuth, Shared Edge,
source-bound runtime activation, external DNS, TLS, and final readback stages. On reconciliation,
the runtime activation verifies the new revision against the active generation before moving
traffic and verifies the resulting active binding afterward. Terraform mutation requires a
fresh mode-`0600` saved plan under a
mode-`0700` private root, W5 policy acceptance, a redacted summary and digest, a `y/N`
confirmation, application of the same bound artifact, and provider/state readback. Image actions
use the same reviewed confirmation model. The operator module derives the four backend buckets,
foundation names, notification email, empty initial Registration Generation, and phase variable
files from committed profile, verified session, and prior stage outputs; the human maintains no
Terraform variable manifest. OAuth and DNS display exact non-secret instructions,
wait for Enter in the same process, and then use provider-verified or explicitly operator-attested
readback with bounded DNS/TLS polling.

Outputs generates one canonical application-scoped bundle beneath the private operator directory
without exposing a secret or another application's values. Register accepts the exact integration
bundle, application-owned attachment bundle, and a strict private registration-intent document. It
validates current platform and target posture, publishes the complete immutable generation
create-only, verifies readback, and requires activation confirmation. Detach and retire require the
expected active-generation digest; replacement attachment registration reactivates a suspended
application. Interrupted confirmation may resume only the identical publication.

W8 implements exact revision readback, the closed qualification profile, redacted evidence,
network fixtures, failure injection, reviewed rollback, separate destruction authority, and
create-only resume state. Qualification evaluates every non-mutating check before the reviewed
rollback can prompt or move traffic; the live rollback explains its temporary 100-percent traffic
effect and requires separate exact rollback and restoration confirmations. It constructs shell-free Cloud SDK deployment, generation, traffic,
attachment, and readback adapters through the verified active human session. Deployment covers
first-run or recovered backend bootstrap, immutable source-bound image publication, initial
generation publication, OAuth metadata, DNS propagation, and TLS readiness. The Cloud Build upload
uses a repository-root allow-list and cannot include private operator state. The qualification
and destruction live defaults retain explicit W9 authority gates; no partial external work occurs.
Repository tests use deterministic fakes and process-local loopback only. Non-fake command adapters
are not invoked by `make check` and reject path escape, ambient credential variables, shell
interpolation, mutable scope, and raw-output persistence outside the private diagnostic boundary.

## Private local state

Generated specifications, approval bindings, atomic progress, current pointers,
create-only application-scoped integration bundles, and inspectable fixture preparation pairs use
the ignored `.platform-operator/` directory by default. Directories use mode `0700` and files use
mode `0600`. Registration intent is a strict
private operator input; restricted members are never echoed in terminal results. Documents contain
no credential, secret payload, Terraform state, saved plan, raw provider response, or browser
state. Private plans and raw command results never become progress content.

A failed Terraform init, plan, or apply, persistent gcloud session read, or Cloud Build submission
stores its exact stdout and stderr only beneath
`.platform-operator/diagnostics/<environment>/`. Each
event has a mode-`0700` directory, mode-`0600` stream files, a timestamp, and a SHA-256 manifest.
The terminal reports only the stdout/stderr paths and content digest plus a warning that the local
files may contain sensitive provider data. Successful and retry-recovered session reads create no
diagnostic artifact. Diagnostic files are troubleshooting artifacts: they are never lifecycle
documents, progress, evidence, qualification output, bundle content, or Git input, and the
operator must not commit or share them without reviewing and redacting their contents.

The current deployment progress remains the single resume record. Its latest succeeded, failed, or
cancelled value is also retained once per specification beneath `progress/`; a later terminal
result for the same specification replaces that snapshot. Waiting and intermediate values are not
retained as history.

Deployment specifications also name their exact executable workflow. The recognized
`platform-deploy-v1` predecessor has 11 stages; current `platform-deploy-v2` has 12 and includes
explicit runtime activation. A structurally and digest-valid terminal Version 1 record is loaded as
immutable historical state and reported by status, never resumed and never padded with a synthetic
runtime-activation result. Preparing Version 2 requires a separate `y/N` confirmation before the
private current pointers move. Declining changes no file. Accepting keeps the predecessor
specification and terminal snapshot at their content-addressed paths; fresh progress is written
only when Version 2 execution begins. A running or waiting predecessor remains an active-operation
conflict and uses `platform-cancel` rather than this supersession path.

An interruption leaves the current stage open and resumes after the last closed stage. A closed
mutation is never repeated. Waiting, cancellation, command failure, policy refusal, mismatched
readback, unsafe output, and production refusal remain truthful terminal states rather than being
converted into success or automatic recovery.

A same-source, same-specification rerun of cancelled progress is not automatic recovery. The
operator first displays the last closed stage, open stage, and retained blocker, then asks whether
to resume. Approval changes only private progress back to running and retries the open stage; all
remaining plan and action confirmations still apply. Declining retains the cancelled record byte
for byte and returns `CANCELLED_OPERATION_RESUME_DECLINED`.

When changed source conflicts with a running or waiting deployment, `platform-cancel` is the only
supported local reset. It displays and confirms the exact active source, specification, last closed
stage, and active stage, then atomically marks that progress record cancelled. It never constructs
an executor, invokes Terraform, calls a provider, edits Terraform state, or changes a cloud
resource. A repeated cancellation is unchanged. The next deployment creates fresh source-bound
intent when source changed, or uses the explicit cancelled-resume prompt when the exact source and
specification remain selected. Both paths reconcile existing resources through normal exact plans
and readback; operators never
hand-edit or delete progress to bypass the conflict.

Reconciliation treats the empty first Registration Generation as independently versioned
configuration. If its create-only object already exists, deployment validates its complete schema,
empty registration posture, immutable object generation, content digest, and generation digest,
then reuses that exact reference across source revisions. It never overwrites or deletes the
generation. Invalid or non-empty content fails closed.

The foundation planner recognizes one bounded state-recovery case: the exact protected signing key
ring is live under its expected immutable identity but Terraform retained a taint marker after a
partial apply. The command boundary deletes the failed saved-plan artifact, provider readback
verifies the identity before and after the prompt, and an exact allow-listed `terraform untaint`
runs only after separate operator confirmation. The executor then produces a new plan; it never
disables `prevent_destroy`, applies the failed plan, or generalizes this path to another resource.

Executor construction returns explicit safe prerequisite blockers instead of collapsing every
missing executable, session, configuration, command adapter, or private-state error into one
unavailable result. Terraform planning classifies a closed allow-list of state, backend,
authentication, permission, quota, configuration, plugin, and protected-taint diagnostics. The
terminal prints guidance for the selected code while raw command output remains absent from the
terminal and retained records; an unmatched diagnostic becomes `TERRAFORM_PLAN_FAILED_UNKNOWN`.
The private diagnostic boundary retains exact failed init/plan/apply streams for local inspection.
Terraform apply
failures use a separate closed classifier and may print only the bounded resource address,
operation, HTTP status, provider status, and service name extracted from stderr. Arbitrary provider
messages remain suppressed. A provider result inconsistent with the reviewed plan reports
`TERRAFORM_APPLY_PROVIDER_INCONSISTENT_RESULT` with the bounded resource address; an unmatched
apply response becomes `TERRAFORM_APPLY_FAILED_UNKNOWN`. A Cloud Run response that rejects changed
configuration under an existing immutable revision name reports
`TERRAFORM_APPLY_IMMUTABLE_REVISION_CONFLICT` rather than the generic concurrent/existing-operation
conflict.

The CLI reports every returned blocker to stderr with a derived component before serializing the
result JSON. Its outer exception boundary catches otherwise unhandled adapter or operator errors,
prints only the operation and exception class, and returns `OPERATOR_INTERNAL_ERROR`; raw exception
messages and tracebacks are not operator output.

Known retained-state failures do not use that outer fallback. Invalid current specification
pointers or records return `SPECIFICATION_READBACK_FAILED`; malformed, digest-mismatched, or
unrecognized progress first reports the exact safe structural invariant that failed and then
returns `PROGRESS_READBACK_FAILED`. A blocked execution likewise narrates its exact blocker codes
and their operator guidance before returning the final machine result. These blockers preserve the
private records for local inspection. Shared final-result formatting lives in the operator output
module so entry points do not duplicate blocker-component mapping or JSON presentation.

Safe `ACTION`, `READBACK`, and `PLAN` narration uses multiline, sorted, two-space-indented JSON for
operator inspection. Digest binding continues to use canonical compact serialization independently
of this display-only formatting.

`platform-deploy` presents seven numbered operator stages while retaining twelve internal
readback-closed resume checkpoints. Related internal actions share one human stage, including DNS
creation and TLS planning/readiness as `Stage 6/7 · Configure DNS and TLS`. A new process announces
the stage containing its first pending checkpoint, making resume position visible without
replaying a completed mutation.
