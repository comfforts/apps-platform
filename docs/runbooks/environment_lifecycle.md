# Environment lifecycle runbook

Use this runbook to deploy, inspect, qualify, and remove one App Platform environment. An
environment is one isolated staging or production deployment with its own hostname, cloud project,
state, identity, OAuth client, DNS and TLS resources, application registrations, and evidence.

| Environment | Intended hostname | Current operating boundary |
| --- | --- | --- |
| `staging` | `apps-staging.comfforts.com` | Available for platform and synthetic fixture operation |
| `production` | `apps.comfforts.com` | Preparation stops while its DNS, traffic configuration, or requested cloud resources remain managed by another system or state |

Always name the environment on the command line. A staging specification, progress record, bundle,
approval, or qualification result cannot be reused for production.

## Before you start

Run commands from the repository root. Confirm that you have:

- the exact source revision you intend to operate;
- a clean current `main` branch for an accepted operation, or a clean pushed branch containing
  current `origin/main` for candidate staging verification;
- the project-local pinned Terraform toolchain;
- `gcloud` and `dig` on your path;
- an active human Cloud SDK login for the selected environment's project;
- user Application Default Credentials;
- access to the Google OAuth and Secret Manager console surfaces; and
- access to the external DNS provider for the selected hostname.

Run the local repository gate before an accepted operation:

```bash
make check
```

The lifecycle stores private specifications, confirmations, progress, bundles, plans, and command
results beneath `.platform-operator/`. Keep that directory outside Git. Do not paste credentials,
OAuth secrets, Terraform state, saved plans, browser state, or raw provider responses into the
repository or an evidence record.

The environment's `current-progress.v1.json` is the resumable working record. When a deployment
succeeds, fails, or is cancelled, its latest terminal result is also retained at
`environments/<environment>/progress/<specification-digest>.final.v1.json`. Compare those records
when investigating changes between specifications. A resumed specification replaces its own
terminal record; waiting and intermediate stage updates are not historical records.

The workflow identifier inside a specification is separately versioned. `platform-deploy-v1` is
the recognized completed 11-stage predecessor; `platform-deploy-v2` is the current 12-stage
workflow with explicit runtime activation. `platform-status` can read an exact predecessor result
and labels its `workflow_compatibility` as `historical`. It does not add runtime-activation evidence
or otherwise rewrite that record.

## Normal staging lifecycle

The normal accepted staging journey is:

```bash
make fixture-project-bootstrap ENVIRONMENT=staging \
  FIXTURES_PROJECT_ID=comfforts-fixtures-nonprod \
  FIXTURES_PROJECT_NAME="Comfforts Fixtures Non-Prod"
make platform-deploy ENVIRONMENT=staging
make platform-connect-project ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod
# For each fixture: application-handoff-check, platform-outputs, fixture-handoff,
# inspect, then platform-register.
make fixture-status ENVIRONMENT=staging
make platform-qualify ENVIRONMENT=staging
make platform-status ENVIRONMENT=staging
```

`platform-deploy` first looks for a current approved specification in private operator state. It
revalidates the source, profile, environment, tools, operator session, project, ownership, and
readable provider facts and reuses that specification when every binding remains valid. Otherwise
it performs preparation itself. You do not need to run `platform-prepare` first or copy a digest
between commands.

## Check readiness without preparing intent

Run preflight when you want to find and resolve prerequisites before a deployment session:

```bash
make platform-preflight ENVIRONMENT=staging
```

The command checks the current source authority, environment profile, pinned toolchain, active
account, Application Default Credentials, selected project, ownership boundary, and other readable
provider prerequisites. It reports `ready` or `blocked` with exact blocker codes. It does not
install tools, change authentication or project selection, create a specification or digest, ask
for approval, write private lifecycle state, or change an external resource. Correct a reported
prerequisite and rerun preflight. You may omit it because deployment performs the same checks.

## Check uncommitted deployment changes

During local maintenance, run the two development checks before committing or pushing:

```bash
make platform-preflight-check ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-deploy-check ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
```

`platform-preflight-check` runs real prerequisite discovery and skips `SOURCE_NOT_CLEAN` because a
working-tree check is intended to inspect uncommitted changes. Unpushed, stale, or non-main source
findings remain diagnostics. `platform-deploy-check` additionally validates the
existing private specification and progress records, renders the current working-tree Terraform,
refreshes real provider state without acquiring a Terraform state lock, and applies normal plan
policy to every stage whose generated inputs are already available. It may write private failure
diagnostics and disposable working files, but it never changes a specification, approval, current
pointer, progress record, Terraform state, or provider resource.

Read every `blocked` stage before continuing. `deferred` means that an exact plan depends on an
output that only a preceding real deployment stage can create. `manual` identifies an OAuth or DNS
checkpoint that the diagnostic does not perform. The final result is `ready` only when the required
platform services, Platform State, Shared VPC, application subnet, Cloud Router, Cloud NAT, Shared
Edge, active runtime, TLS, and final readback pass. `reconciliation-required` names platform changes
for `platform-deploy`; `incomplete` means an earlier real stage must first produce an input; and
`blocked` means the check itself could not safely continue. None of these results is deployment,
source admission, qualification, or proof that a later apply will succeed.

## Optional preparation

Use preparation when you want to review and approve the complete specification before the
deployment window:

```bash
make platform-prepare ENVIRONMENT=staging
```

Preparation repeats readiness checks, displays the complete proposed deployment, writes its
canonical private lifecycle state, prints its specification digest, and requests approval without
creating or changing an external resource.

To deploy after that review, run the ordinary command:

```bash
make platform-deploy ENVIRONMENT=staging
```

The command automatically selects the prepared specification while its bindings remain valid. If
it is absent, stale, or unapproved, deployment creates and requests approval for a fresh one. If
retained state is malformed or a current prerequisite is blocked, deployment stops without
replacing it. `SPECIFICATION_DIGEST=sha256:<digest>` is an optional explicit pin for a current
approved digest, not a normal handoff requirement.

When current private pointers identify a terminal `platform-deploy-v1` result, preparation prints
that workflow, source revision, digest, status, and completed-stage count. It then asks whether to
supersede the current pointers with `platform-deploy-v2`. Answering `N` leaves the pointers and
records unchanged. Answering `y` retains the old specification and terminal progress snapshot,
then allows the Version 2 specification review; deployment later starts fresh 12-stage progress.
This local confirmation performs no Terraform or provider mutation and does not replace the later
plan/action confirmations. A running or waiting predecessor is an active operation and still
requires exact-source resume or `platform-cancel`.

## Deploy the shared platform

Start deployment with:

```bash
make platform-deploy ENVIRONMENT=staging
```

The command keeps one interactive process open while it:

1. verifies the selected environment, source, tools, account, project, ownership, and readable
   provider facts;
2. reuses the current approved specification when those bindings remain exact, or displays one
   complete fresh deployment specification for review;
3. asks for confirmation only when a fresh specification requires approval;
4. creates and displays a fresh exact Terraform plan for each stage;
5. applies only the plan confirmed with the stage's `y/N` prompt;
6. explains each required Google OAuth or external-DNS action at the point of use;
7. waits for Enter after the operator completes the displayed manual action;
8. reads back every result the provider exposes; and
9. atomically records each readback-closed stage in private deployment progress.

When an active Registration Generation already exists, deployment does not republish or replace
it. The command carries that exact generation into the newly rendered Shared Edge revision,
verifies the staged revision's source, image, generation, and configuration-object bindings, then
activates it and verifies that it owns 100 percent of edge traffic. A checkout revision difference
by itself is only a status diagnostic; run deployment when platform-owned desired state actually
needs reconciliation.

Every operator command writes a redacted execution trace to stderr before its final JSON result on
stdout. The trace shows the operation, environment, state directory, source authority, selected
fixture, profile, Git source facts, and the bounded non-secret result from each readiness adapter.
When readiness is blocked, read the named adapter facts and the plain-language guidance printed
with each stable blocker code. The trace never includes credentials, secret values, raw provider
responses, Terraform state, or saved-plan content.

Read-only gcloud session checks retry once before stopping. A persistent failure distinguishes the
active account, project, billing reference, identity token, Application Default Credentials,
Cloud SDK configuration, and required local tools. When a failed session read or image build has
raw command output, the operator stores it under
`.platform-operator/diagnostics/<environment>/`, prints its local paths and digest, and keeps it out
of lifecycle state and terminal output. Inspect those files locally and redact them before sharing.

For local maintenance of preflight behavior, use:

```bash
make platform-preflight ENVIRONMENT=staging PREFLIGHT_MODE=development
```

This runs the real read-only checks, skips `SOURCE_NOT_CLEAN`, and reports other source-admission
findings separately as development diagnostics. `ready: true` means the development checks passed;
`operational_ready: false` means the
same source still cannot authorize preparation or deployment. Authentication, project, profile,
tool, DNS, and discovery failures remain blocking. Development preflight writes no lifecycle state
and has no executor, Terraform-plan, provider-mutation, bundle, evidence, or qualification path.

Each manual checkpoint first prints a pretty machine-readable record and then a numbered
natural-language procedure. Follow the numbered procedure; the JSON record is supporting evidence,
not the operator instruction by itself. OAuth is divided into three focused reviews: application
branding, the Web client, and its Secret Manager version. Each review may leave an exact existing
configuration unchanged or make only the displayed correction. The command prints and attempts to open
the exact allow-listed Google Cloud console page for each step, pauses after each one, and asks for
only the OAuth client ID after the client review. The Secret Manager step names the existing target
and requires exactly one enabled version before readback. The script never asks for the OAuth
client secret in the terminal.

Before showing the DNS procedure, the command uses `dig` to compare the displayed address at every
authoritative name server and the two approved recursive resolvers, and checks the authoritative
TTL. An already valid record is reported as verified and needs no change. Otherwise the command
opens the Squarespace domains page and asks the operator to add or update only that record. After
Enter, the same checks must pass and the command prints a completion message. Managed-certificate
readback then runs every 30 seconds for up to one hour. A known provider or domain failure stops
immediately instead of appearing as pending; a genuine provisioning state remains resumable if it
outlasts the bound.

Stop on a plan, account, project, ownership, DNS, TLS, OAuth, or provider-readback mismatch. Do not
repair it by manually broadening scope, importing resources, pushing state, bypassing locks, or
running a blind Terraform command.

## Inspect an environment

Run:

```bash
make platform-status ENVIRONMENT=staging
```

Status reports the current checkout source, the source recorded by the last deployment operation,
the source serving the active Shared Edge, desired configuration, execution progress, active
registration generation, and latest qualification state without changing the provider or
repository. These three source revisions can legitimately differ during candidate maintenance, so
status reports their alignment as diagnostics rather than treating every difference as a failed
read. An unreadable or internally inconsistent record remains a blocker. A deployed resource is
not necessarily qualified; status reports those states separately.

## Connect an application

Applications remain responsible for their own runtime, data, state, secrets, and feature
authorization. The platform and application exchange non-secret, digest-bound bundles:

1. Run `platform-connect-project` once for the application project in this environment. It attaches
   only that existing project to the platform Shared VPC and verifies subnet access for its Cloud
   Run service agent.
2. Run `application-handoff-check` with the intended application, route, admission mode, active
   platform revision, and Registration Generation. Resolve every blocker before publishing a
   handoff.
3. Run `platform-outputs` with the same values.
4. Give the resulting Platform Integration Bundle to the Application Owner.
5. The Application Owner deploys the application through its own lifecycle and state.
6. The Application Owner returns an Application Attachment Bundle bound to the integration-bundle
   digest.
7. Run `platform-register` with those bundles and the reviewed registration intent.
8. The platform validates project, network, ingress, IAM, audience, and target posture and activates one complete immutable registration
   generation.

Project connection does not create a runtime, application backend, image, route, registration, or
qualification. Every provider command names its project explicitly; do not switch the active
gcloud project merely to connect or operate an application.

Use `platform-detach` for a reversible maintenance or replacement cycle. Detachment removes the
application from routing while reserving its identifier and route. Use `platform-retire` only for
permanent retirement; it cannot be reversed.

## Deploy the staging fixtures

The synthetic fixtures exercise the same bundle and registration path as real applications:

```bash
make fixture-project-bootstrap ENVIRONMENT=staging \
  FIXTURES_PROJECT_ID=comfforts-fixtures-nonprod \
  FIXTURES_PROJECT_NAME="Comfforts Fixtures Non-Prod"
make platform-connect-project ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod
```

The bootstrap is idempotent and normally runs once. It creates or repairs the dedicated fixture
application project, enables its required services, and creates its private versioned state bucket
and image repository. Google Cloud assigns the new project's numeric identifier. Bootstrap reads
that project number back and prints it; the operator never supplies or derives it. The later
project-connection operation reads the number again and writes it into the private connection
record consumed by bundle generation and fixture deployment. Bootstrap creates no runtime or
route. The connection is also idempotent and
normally runs once after the platform network exists.

For each fixture, generate its project-scoped bundle, deploy its application-owned runtime, inspect
the handoff, and register it explicitly. For example:

```bash
make application-handoff-check \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod \
  APPLICATION_ID=fixture-public \
  ACCESS_MODE=public \
  ROUTE_INTENT=/fixture-public \
  PLATFORM_SOURCE_REVISION=<active-platform-revision> \
  PLATFORM_GENERATION=<active-registration-generation>

make platform-outputs \
  ENVIRONMENT=staging \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod \
  APPLICATION_ID=fixture-public \
  ACCESS_MODE=public \
  ROUTE_INTENT=/fixture-public \
  PLATFORM_SOURCE_REVISION=<active-platform-revision> \
  PLATFORM_GENERATION=<active-registration-generation>

make fixture-handoff \
  ENVIRONMENT=staging \
  APPLICATION_ID=fixture-public \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v1.json

# Inspect all three printed files without editing them.
make platform-register \
  ENVIRONMENT=staging \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.v1.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.v1.json \
  REGISTRATION_INTENT=/private/path/registration-intent.v1.json

make fixture-status ENVIRONMENT=staging APPLICATION_ID=fixture-public
```

`application-handoff-check` is read-only. It consumes the explicit platform-ready result rather
than interpreting internal deployment stages. It then verifies that the application project exists
with Cloud Resource Manager, Compute, IAM, Cloud Run, and Service Usage enabled; that its Shared VPC
connection and subnet grants remain exact; that the requested bundle can be compiled; and, for
authenticated or restricted access, that the application-scoped identity projection contains the
exact platform endpoints, OAuth client identifier, and application audience. It
publishes no bundle and writes no operational lifecycle state. `PLATFORM_RECONCILIATION_REQUIRED`
means run and review `platform-deploy` before attempting the application handoff.

Repeat for the authenticated and restricted fixture with the matching admission mode and route.
Each fixture root uses an independent prefix in the fixture-project state bucket and creates only
that fixture's Application State. `platform-register` reads back the target before activating a
complete Registration Generation that preserves the other registrations.

For an authenticated or restricted fixture, a successful browser test redirects through Google,
sets the Platform Session, and returns to the requested fixture route. `identity unavailable` is a
closed dependency failure, not a successful login. Query only the allowlisted diagnostic field from
the dedicated regional bucket; never copy the callback URL, authorization code, cookie, token,
identity, or raw provider response into a terminal transcript or issue:

```bash
gcloud logging read \
  'jsonPayload.event_type="request_completion" AND
   jsonPayload.component="shared-edge" AND
   jsonPayload.diagnostic_code:*' \
  --project=<platform-project-id> \
  --location=<platform-region> \
  --bucket=<platform-log-bucket-id> \
  --view=_AllLogs \
  --freshness=30m \
  --limit=20 \
  --format='table(timestamp,jsonPayload.diagnostic_code,jsonPayload.status_class,jsonPayload.correlation_id)'
```

The code identifies the failed store or provider boundary without retaining the provider exception
or visitor material. An empty result after a request is itself an observability failure; stop and
inspect the deployed runtime revision, sink filter, bucket, and JSON-line emission before diagnosing
the identity provider from unredacted data.

Do not redeploy the platform merely because the repository revision running a fixture command is
newer than the deployed platform revision. The command validates its own source admission, reads
the active platform revision and Registration Generation from provider-backed platform state, and
binds both revisions independently. Run `platform-deploy` first only when platform-owned desired
state must change. Accepted qualification is a separate claim and requires an Accepted Source
platform deployment.

`fixture-handoff` is not read-only preparation. It builds or reuses the immutable image, plans and
applies the selected fixture's Application State, validates provider posture, and writes the two
canonical non-secret bundle files and registration intent beneath `.platform-operator/`; it does
not activate a Registration Generation or make the route available. It labels the steps as stage
1/2 and 2/2.
Stage 2/2 is `Prepare the Fixture Application Handoff`: it may deploy or reconcile Application
State, but it never registers or activates the route. Inspect the files without editing them.

Registration is always the separate `platform-register` step. If the handoff must be regenerated,
rerun it with the current Platform Integration Bundle and inspect the newly printed files before
registration. There is no combined fixture deploy-and-register shortcut.

### One-time transition from the former same-project fixture

If staging still contains a fixture created by the former same-project implementation, remove that
fixture through the source-admitted predecessor revision before beginning the cross-project
sequence. From a clean branch whose pushed upstream still points to that exact predecessor, use
the same `SOURCE_AUTHORITY` that created the fixture, run `platform-detach` for the active fixture,
and then run its former `fixture-destroy`. A detached commit does not satisfy Candidate Source
admission. Confirm with provider and Terraform-state readback that the old Cloud Run service and
its Application State are gone. Do not delete the old service or edit its state by hand. Then
return to the cross-project revision and run `fixture-project-bootstrap`,
`platform-deploy`, `platform-connect-project`, `application-handoff-check`, `platform-outputs`, `fixture-handoff`, and
`platform-register` in the documented order. The route remains reserved during this transition and
is unavailable until the new attachment is registered.

This transition is needed only for fixture state that predates the dedicated fixture project. New
fixture revisions remain in `comfforts-fixtures-nonprod` and use the normal detach, destroy,
handoff, and register lifecycle.

The first `platform-deploy` from the cross-project revision also reconciles the former bootstrap
state. Review its bootstrap plan carefully. It must show the existing platform-state bucket as an
unchanged move to its dedicated module address and exactly these three state-only removals:

- `fixture-public` state bucket: `forget`, never `delete`;
- `fixture-authenticated` state bucket: `forget`, never `delete`; and
- `fixture-restricted` state bucket: `forget`, never `delete`.

An approved apply removes only those obsolete Terraform bindings. It does not delete the buckets,
their retained object versions, or any other provider resource. Stop if the plan proposes any
destruction, an unknown `forget` action, or a change to the platform-state bucket. Do not delete or
edit the legacy buckets manually; their eventual retention, export, or purge is a separately
governed backlog lifecycle.

On an environment with an existing Shared Edge, the foundation plan is refresh-only and cannot
create the new cross-project network resources. The later normal Shared Edge plan is therefore
expected to show exactly these inherited migration changes: create the platform Shared VPC
network, application subnet, host-project binding, application-subnet Cloud Router, and Cloud NAT;
update the qualification image repository for fixture-project use; and create the edge
session-store role. The NAT uses provider-managed public addresses and serves only the application
subnet. It may also reconcile Shared Edge resources owned by that phase. Stop for any other
inherited create or update, any replacement or deletion, or a failed foundation-output readback.
This exception is exact migration authority, not general permission for the Shared Edge phase to
mutate foundation resources.

`fixture-status` reconciles all three fixture registrations and provider targets by default. During
an individual rollout or investigation, add `APPLICATION_ID=<fixture-application-id>` to narrow the
read-only result to one fixture. `target_ready` is Cloud Run/provider posture;
`route_ready` is a separate HTTPS read of the platform route and becomes true only for a successful
response or a real authentication redirect. An active registration and ready target do not by
themselves make `route_ready` true.

## Qualify an environment

After platform and fixture deployment, run:

```bash
make platform-qualify ENVIRONMENT=staging
```

Qualification checks the exact source, specification, final deployment progress, registration generation, provider
resources, DNS and TLS behavior, catalogue and routing, admission and identity, assertion
verification, direct-origin denial, isolation, streaming behavior, rollback readiness, and
redaction. It records only approved, redacted evidence.

The command completes all non-mutating checks before offering a rollback. If any of them fails,
`lifecycle-rollback` is recorded as blocked with
`QUALIFICATION_ROLLBACK_PREREQUISITE_FAILED`; the command does not prompt for rollback and does not
move traffic. When they all pass, the command explains the traffic effect before asking for the
exact rollback phrase. Confirmation temporarily moves 100 percent of staging traffic from the
current Registration Generation to its reviewed predecessor. Keep the command running: after
provider readback it asks for a second exact phrase to restore the original generation and verifies
that restoration. Declining or interrupting restoration leaves the predecessor active; follow the
printed `RESTORATION REQUIRED` guidance and inspect the active generation before attempting
qualification again.

Do not call the environment qualified if a required check failed, was skipped, used a different
revision, or could not be read back.

## Resume an interrupted operation

Rerun the same command with the same environment and source authority. The lifecycle validates its
private progress and resumes after the last completed stage.

If the prior result is `cancelled` and the exact source and specification remain selected, the
rerun displays the last completed stage, stage to retry, and cancellation blocker. Answer its
separate `y/N` prompt to resume. `y` retries only the open stage; every remaining Terraform plan or
bounded action still has its normal confirmation. `n` returns
`CANCELLED_OPERATION_RESUME_DECLINED` and leaves the private record unchanged. Do not edit the
record or change source merely to escape a declined action confirmation.

Resume is refused when the source, specification, environment, scope, or recorded outputs no longer
match. `ACTIVE_OPERATION_CONFLICT` prints the active source authority and revision, specification,
last closed stage, active stage, requested source and specification, and the exact cancellation
command. If the old operation should continue, restore its exact source and rerun the original
command. If it should be abandoned in favor of changed source, run the displayed command, for
example:

```bash
make platform-cancel ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
```

Review the displayed operation and answer its `y/N` confirmation. Cancellation atomically marks
only that private progress record as cancelled and retains its terminal snapshot. It does not run
Terraform, call a provider, or change a cloud resource. Repeating the command returns `unchanged`
without asking again. Then rerun `platform-deploy`; it prepares fresh source-bound intent and uses
fresh plans plus provider readback to reconcile resources created by the earlier operation. If the
same exact source and specification are still selected, the cancelled-resume prompt above applies
instead of preparing different intent. Never
edit or delete `current-progress.v1.json` by hand. The lifecycle never automatically unlocks state,
pushes state, imports a resource, broadens scope, or hides a failed readback.

A completed predecessor workflow is not resumed. It remains inspectable history until the operator
accepts the displayed current-pointer supersession prompt. The old final snapshot remains at its
original digest path. An unrecognized, malformed, or digest-mismatched private record instead
returns `SPECIFICATION_READBACK_FAILED` or `PROGRESS_READBACK_FAILED`; inspect the private files
locally and fix the software or restore the exact record rather than deleting evidence.

A failed Shared Edge apply may have already recorded some valid edge resources, such as the
reserved global address, in Platform State. When changed source starts a fresh deployment, the
foundation PLAN then reports `planning_mode: refresh-only`. Review that plan as usual. It may show
foundation and Shared Edge resources only as `no-op` or `read`; it is never applied and the later
normal Shared Edge plan reconciles the partial inventory. Any create, update, delete, replacement,
unexpected address, or unknown type in the refresh-only plan fails policy. Do not disable
`prevent_destroy`, manually remove the partial resources, or edit state to advance the lifecycle.

That later Shared Edge plan also reads the exact Platform State address inventory. A true first
deployment keeps TLS disabled until the DNS checkpoint. If the managed-certificate address is
already in Platform State, reconciliation keeps TLS enabled so Terraform cannot reinterpret the
existing certificate, HTTPS proxy, or forwarding rule as a return to the dark first-deployment
phase. This preservation is not certificate readiness: the DNS and TLS stage still verifies the
record and requires the provider certificate status to become active.

A failed foundation apply can leave the already-created signing key ring marked as tainted in
Terraform state. On the next deployment, the operator recognizes only the exact protected-key-ring
diagnostic, removes the unusable failed plan, and reads back the immutable live key-ring identity.
It displays that identity and explains that the proposed repair changes only Terraform's taint
marker. Confirm the separate `y/N` recovery only when the displayed project, region, and key-ring
name match the selected environment. The operator reads the identity again, runs the exact
state-recovery command, and creates a fresh foundation plan for normal review. Declining, failed
readback, changed identity, or another protected resource stops without state or provider mutation.
Never disable `prevent_destroy`, use a targeted replacement, or replace the live key ring to bypass
this stop.

When deployment cannot construct an external command boundary, use the returned blocker rather
than treating every case as the same adapter failure. Executor blockers name the unavailable
gcloud, Cloud SDK configuration, operator identity session, Application Default Credentials, DNS,
Terraform, or private-state boundary. Resolve only the named prerequisite, then rerun the same
command.

When Terraform cannot initialize or produce a plan, the blocker distinguishes an unreadable
reviewed module, initialization backend, authentication, or pinned-provider failure, a state lock
or read failure, backend access denial, operator reauthentication requirement, provider permission
or quota failure, invalid rendered configuration, provider-plugin startup failure, the separately
handled protected key-ring taint, a proposed protected-resource deletion, or an unknown safe
category. Apply failures separately distinguish authentication,
dependency or identity propagation, service disablement, permission denial, quota exhaustion,
invalid arguments, conflicts, state locks, provider-plugin failures, and unknown responses. Before
the blocker, a plan-policy refusal prints only its safe resource address, type, and actions; an
apply failure prints any safely extracted resource address, operation, HTTP status, provider
status, and service name. Follow the adjacent guidance. Raw Terraform stderr and arbitrary provider
messages are deliberately not displayed because they may contain protected state or provider
details. A failed init, plan, or apply stores exact stdout and stderr beneath
`.platform-operator/diagnostics/<environment>/` in a new mode-`0700` event directory with mode-`0600`
files. The terminal prints the stderr path and SHA-256 digest. Inspect that local file when the safe
blocker is insufficient; do not commit it or share it without reviewing and redacting its content.
It is troubleshooting data, not lifecycle evidence or authority.

For every blocked or failed command, read stderr before the final JSON. The CLI prints an
`Operator error` block containing the responsible component and safe blocker code. Known modules
may print additional specific guidance first. If an unexpected exception crosses the adapter
boundary, the CLI prints only the operation, exception class, and `OPERATOR_INTERNAL_ERROR`; it
never echoes the exception message. Treat that internal code as a software defect requiring source
inspection, not as permission to bypass the failed boundary.

## Candidate staging verification

A clean pushed branch containing current `origin/main` may exercise staging before merge:

```bash
git push -u origin HEAD
make fixture-project-bootstrap ENVIRONMENT=staging SOURCE_AUTHORITY=candidate \
  FIXTURES_PROJECT_ID=comfforts-fixtures-nonprod \
  FIXTURES_PROJECT_NAME="Comfforts Fixtures Non-Prod"
make platform-deploy ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-connect-project ENVIRONMENT=staging SOURCE_AUTHORITY=candidate \
  APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod
# For each fixture: application-handoff-check, platform-outputs, fixture-handoff,
# inspect, then platform-register.
make fixture-status ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
make platform-qualify ENVIRONMENT=staging SOURCE_AUTHORITY=candidate
```

Candidate mode is staging-only. Candidate specifications, progress, bundles, status, and evidence
remain separate from accepted results and cannot qualify production. After merge, repeat deployment
and qualification from clean current `main` using the default accepted source.

Only one staging operation may run at a time because candidate and accepted operations target the
same staging environment.

## Remove a fixture

Detach a fixture before destroying its Application State:

```bash
make platform-detach \
  ENVIRONMENT=staging \
  APPLICATION_ID=<fixture-application-id> \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> \
  GENERATION_DIGEST=sha256:<active-generation-digest>

make fixture-destroy \
  ENVIRONMENT=staging \
  APPLICATION_ID=<fixture-application-id>
```

Fixture destruction requires its displayed typed confirmation and targets only the selected
fixture's Application State. Redeploying it later returns a new attachment and can reactivate the
reserved application and route.

## Destroy a platform environment

Before platform destruction:

1. inspect the environment with `platform-status`;
2. detach every active application;
3. have each Application Owner destroy or retain its Application State through its own lifecycle;
4. review the exact platform-owned destruction scope; and
5. run `platform-destroy` and enter its typed destructive confirmation.

```bash
make platform-destroy ENVIRONMENT=staging
```

The command refuses to continue while active attachments or ownership blockers remain. It removes
traffic and external DNS in the controlled order, verifies each transition, and never issues a
blind root destroy. Platform destruction never destroys Application State.

Backend state, recovery material, retained configuration, signing keys, provider services,
evidence, and the Shared VPC host/network/subnet may remain after ordinary destruction. The
billable Cloud NAT and its router are removed with the destructible platform foundation. The
network remains because connected application projects are outside ordinary platform-destruction
scope; removing their connection is a separate destructive authority. Purging retained material
is a separate operation, not an automatic final step.

## Production

Production uses a separate profile, project, hostname, state, identity, OAuth client, DNS and TLS
resources, registrations, evidence, and destructive authority. Never reuse a staging artifact or
confirmation for production.

Preparation stops with `OWNERSHIP_TRANSFER_REQUIRED` while `apps.comfforts.com`, its DNS or traffic
configuration, or any requested production cloud resource remains managed by another system or
Terraform state. This blocker does not refer to the active `gcloud` account or GitHub repository
ownership; those are checked separately as operator identity and source-repository authority. Do
not import, replace, mutate, or destroy an externally managed resource as part of preparation.
Complete the separately owned resource/state transfer and application-adoption work before
attempting production deployment again.
