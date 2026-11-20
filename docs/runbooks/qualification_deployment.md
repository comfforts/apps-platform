# Historical AP-M8 qualification-deployment runbook — superseded

Status: historical record at source revision `7b6678a7f0b3036d427517dad6bc3bec876d1a44`;
superseded by AP-M9; no active instruction or action authority

This file preserves the prior manifest-driven procedure for review history. Do not follow it as an
operator runbook. The current procedure is [Environment lifecycle](environment_lifecycle.md).
AP-M8-W3 through AP-M8-W12 never began, and no real operator manifest was accepted.

This runbook is subordinate to the App Platform requirements, accepted ADRs, system design,
implementation plan, evaluation strategy, and threat model. It defines the human checkpoints for
AP-M8-W2 through AP-M8-W12 under the accepted AP-M8-W1 authority. Its presence and W2's local
validator never authorize an external mutation.

Requirements: AP-PR-002, AP-PR-007, AP-PR-008, AP-PR-009; AP-QR-001, AP-QR-003 through AP-QR-006

Decisions: ADR-001, ADR-004, ADR-007

Threats: AP-TM-004, AP-TM-005, AP-TM-007 through AP-TM-014

Plan: AP-M8-W1 through AP-M8-W12

## Checkpoint rule

The complete AP-M8-W1 authority is owner-accepted and merged. AP-M8-W2 implements the closed
contract and deterministic chain validator, then records the exact real operator-input manifest
only after that implementation merges. AP-M8-W3 and AP-M8-W4 each require a new explicit approval
against the accepted manifest immediately before their external changes. Approval for one
checkpoint, setting, environment, workflow, root, operation, identity, or IAM binding cannot be
reused for another.

Before requesting either mutation approval, the operator must present a secret-free proposed-
change table containing:

- the protected `main` source revision and clean repository readback;
- the exact current setting or IAM binding, proposed value, and reason;
- the environment class, rendered workflow path, root or publication target, operation, and
  operation identity;
- the exact GitHub repository and owner numeric identifiers;
- the Workload Identity Pool and provider resource references;
- the requested provider permissions and their resource scope;
- the readback command or API field that will prove the result; and
- the smallest recoverable reversal for only that checkpoint's changes.

A missing, placeholder, synthetic, secret-bearing, discovered, over-broad, or unreviewed value
blocks the checkpoint. The operator does not open an authenticated session merely to fill an
authority gap.

The AP-M8-W2 operator-input manifest is append-only. Its first accepted revision fixes every value
known before provider mutation. A later package may append one immutable successor revision for a
fact that can exist only after an earlier approved operation, such as an image digest, state
lineage digest, configuration-object generation, plan digest, or run identifier. The successor
names its predecessor and receives a new explicit approval before use; it never edits, replaces,
or retroactively completes an earlier record. The exact protected-main source revision is recorded
after the authority change merges, not guessed or self-referentially embedded in that change.

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

AP-M8 uses five distinct protected GitHub Environment classes. Their exact real names are
AP-M8-W2 operator inputs and may not use a synthetic example value:

| Class | Permitted authority | Required protections |
| --- | --- | --- |
| Plan | Authenticated provider and state reads needed for one advisory or exact-main plan | Exact `main` deployment branch; explicit owner review for every job; no environment secret |
| Apply | Same-job application of one exact reviewed plan for one root, or one immutable artifact/configuration publication | Exact `main` deployment branch; fresh explicit owner review for every job; no environment secret |
| DNS | The exact qualification-hostname record transaction only | Exact `main` deployment branch; fresh explicit owner review; no environment secret; no authority over another record or zone |
| Evidence | Root-scoped readback, create-only redacted operation records, and final bundle verification | Exact `main` deployment branch; fresh explicit owner review; no environment secret; no provider mutation, state write, overwrite, or deletion |
| Recovery | One separately approved rollback, force-unlock, or destroy operation | Exact `main` deployment branch; fresh operation-specific owner review; no environment secret; no reused approval |

The same person may trigger and approve in this owner-operated demo, but GitHub must still create a
distinct environment review event after the exact source, root or target, operation, and digest are
visible.
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

- exist as one reviewed `.github/workflows/` file for one operation and one root or publication
  target, with the target, operation, environment, identity, provider, repository, and protected
  ref fixed rather than selected by an untrusted dispatch input;
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

### One identity per root or publication operation

No operation identity spans roots or operations. AP-M8-W2 must name one distinct service account
and one exact workload-identity impersonation binding for every enabled cell in this matrix:

| Operation | Environment class | Permitted provider authority |
| --- | --- | --- |
| Plan | Plan | Read the selected root's state and provider metadata and create/delete only its native backend lock; no state-content or provider-resource mutation |
| Apply | Apply | Read and write the selected root's backend and mutate only resources owned by that root through one reviewed same-job plan |
| Artifact publish | Apply | Create immutable digest-addressed packages only in the reviewed qualification Artifact Registry repository and read back their digests; no repository administration, overwrite, tag movement, or deletion |
| Generation publish | Apply | Create and read back only the exact `generations/<n>/compiled.json` object with a zero-generation precondition; no overwrite, deletion, mutable pointer, or other object access |
| Qualification DNS | DNS | Submit and read back only the reviewed `apps-staging.comfforts.com` A-record transaction in the exact managed zone; no other record or zone mutation |
| Root readback | Evidence | Read one selected root's backend and owned provider metadata and create only its exact redacted evidence record; no lock, state, or provider-resource mutation |
| Evidence finalize | Evidence | Read only the exact evaluation bundle prefix, verify hashes/schema/completeness, and create only the final manifest, checksum file, and verdict with no-overwrite preconditions; no backend or provider-resource access |
| Rollback | Recovery | Read and write the selected root's backend and perform only the reviewed rollback plan for that root |
| Force-unlock | Recovery | Inspect the selected root's lock and remove only the exact approved lock identifier; no provider-resource mutation |
| Destroy | Recovery | Read and write the selected root's backend and delete only the exact reviewed resources owned by that root through one reviewed destroy plan |

An identity is enabled only when its rendered workflow path, root or exact publication target,
operation, environment, service account, exact permission list, resource scopes, and impersonation
principal are present in the operator manifest. Unused rollback, force-unlock, and destroy cells
retain no binding. Import,
state push, backend migration, federation administration, IAM administration, and project-wide
administration remain outside this matrix and require later break-glass authority if ever needed.

Every successful or failed operation identity may additionally create only its one schema-valid,
redacted operation record at the exact pre-approved evidence-bundle path. It cannot list another
evaluation prefix, overwrite or delete a record, or read evidence written by another operation.
This evidence-write permission is part of that operation's reviewed scope, not general evidence-
bucket access.

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

## AP-M8-W5 backend bootstrap and state lineage

AP-M8-W5 has a repository-only preparation phase and a later operator phase. Preparation adds and
deterministically tests the reviewed bootstrap-backend declaration mechanism described below, then
merges it through protected `main`. It performs no authenticated command. Only a subsequent explicit
owner approval may start the operator phase at that exact merged revision.

The AP-M7 bootstrap root intentionally has no backend block because it must create its own backend
buckets from local state. The non-bootstrap roots already contain empty `gcs` backend declarations.
AP-M8-W5 must not improvise or hand-edit a backend declaration in an authenticated working
directory. Before the operator phase, protected `main` must contain
`infrastructure/backend/bootstrap-backend.tf.tmpl`, whose only Terraform content is the empty GCS
backend declaration, and `infrastructure/backend/render_bootstrap_backend.py`, a credential-free
standard-library renderer that copies it into a private temporary bootstrap-root copy as
`backend.tf` for migration. The gate must verify the template and rendered digest, exact destination
filename, refusal to overwrite, absence during initial local apply, and presence only during
migration and later remote operation.

This requirement is unresolved implementation work owned by AP-M8-W5. Until it is merged and its
deterministic tests pass, backend bootstrap is blocked.

### Fixed root and prefix map

Four buckets hold five independent root lineages. Bucket names are exact AP-M8-W2 operator inputs;
prefixes and owners are fixed:

| Root | State owner | Bucket | Prefix | Initial state action |
| --- | --- | --- | --- | --- |
| `bootstrap` | Platform State backend resources | Platform-state bucket | `bootstrap` | Create locally, then migrate while preserving lineage |
| `platform` | Platform State | Platform-state bucket | `platform` | Initialize empty remote backend; first approved apply creates lineage |
| `fixture-public` | Fixture Application State | Fixture-public state bucket | `fixtures/fixture-public` | Initialize empty remote backend; first approved apply creates lineage |
| `fixture-authenticated` | Fixture Application State | Fixture-authenticated state bucket | `fixtures/fixture-authenticated` | Initialize empty remote backend; first approved apply creates lineage |
| `fixture-restricted` | Fixture Application State | Fixture-restricted state bucket | `fixtures/fixture-restricted` | Initialize empty remote backend; first approved apply creates lineage |

The Version 1 backend configuration and `backend_reference_set` continue to expose the platform and
three fixture references. The `bootstrap` prefix is an operator-procedure constant for the state of
the root that owns those buckets; it is not a cross-state reference and is never supplied to another
root. Terraform workspaces other than `default` are prohibited because they create unreviewed
object paths and lineages.

The two platform-state prefixes require separate conditional object access for the bootstrap and
platform root identities. Each fixture bucket admits only identities for its own root. If GCS IAM
readback cannot prove the reviewed prefix or bucket scope without granting cross-root access,
AP-M8-W5 stops and requires a new design; project-wide or whole-platform-bucket object authority is
not an acceptable fallback.

### Operator prerequisites

Before the one-time local bootstrap begins, the owner reviews one proposed-operation record proving:

- AP-M8-W1 is merged, and AP-M8-W2 through AP-M8-W4 passed their exact checkpoints;
- the source is the exact clean protected-main revision containing the reviewed backend renderer;
- `make check` passed at that revision with Terraform 1.17.2 and `hashicorp/google` 8.11.0;
- the operator-class Version 1 backend configuration validates and its digest matches the manifest;
- project `comfforts-platform-non-prod`, number `455651441682`, region `us-west1`, four globally
  unique bucket names, five prefixes, recovery bounds, labels, and IAM scopes match the manifest;
- every target bucket and prefix is absent and unclaimed; an existing object or bucket is not
  imported, emptied, overwritten, or adopted by this procedure;
- required provider APIs and the billing attachment are already reviewed and available without an
  unapproved service enablement or billing change;
- one short-lived owner credential has only the approved bucket-bootstrap and binding permissions,
  contains no service-account key, and will not be retained; and
- the private temporary working directory, state-backup location, evidence destination, stop
  owner, and recovery contact are known before planning.

A missing API, unavailable name, pre-existing bucket or prefix, provider default, synthetic value,
unexpected IAM inheritance, or broader credential stops before a plan is created.

### Private local bootstrap

The operator creates a mode-`0700` temporary directory outside the repository and runner caches,
copies the exact reviewed Terraform subtree into it, and verifies the copy digest. Backend,
variable, plan, state, and provider-response files remain under that directory with restrictive
permissions and never enter Git, an Actions artifact, a job summary, or the AP-M8 evidence bundle.

The bootstrap-root copy initially contains no backend declaration. It initializes only the locked
toolchain and local backend, validates the exact operator configuration, creates a saved plan under
the private temporary directory, records the canonical redacted plan digest, and applies that exact
plan with the short-lived owner credential. The operation never uses `-lock=false`, a mutable
provider selection, an implicit variable, or an automatically approved follow-on command.

The plan may create exactly four GCS buckets and their AP-M7 labels and recovery controls. Each
bucket must read back:

- the exact project, globally unique name, `US-WEST1` location, and `STANDARD` storage class;
- uniform bucket-level access and enforced public-access prevention;
- object versioning;
- deletion prevention and `force_destroy = false` in the exact applied configuration;
- noncurrent deletion only after both the reviewed 90-to-365-day age and 20-to-50-newer-version
  thresholds are met; and
- the exact `environment`, `managed_by`, `state_owner`, and applicable `application_id` labels.

IAM readback must then match only the approved root-operation principals and conditional scopes.
Because the AP-M7 state-bucket module deliberately defers IAM, the same approved owner checkpoint
then applies only the reviewed per-bucket metadata and conditionally prefix-scoped object-access
bindings. Those bindings are operator-managed Platform control settings, remain outside another
Terraform root, and cannot replace an entire policy or grant whole-bucket object access where two
roots share the platform-state bucket. The bootstrap apply does not enable an API, create another
resource, write a remote state object, or grant a project-wide storage role.

### Bootstrap-state migration

After bucket and IAM readback succeeds, the operator captures a restricted local state backup and
records only its SHA-256 digest, Terraform state-format version, Terraform version, lineage digest,
serial, provider-address set, and sorted resource-address inventory. Raw state, lineage, attributes,
outputs, and provider payloads remain outside evidence.

Before migration, the platform-state bucket's `bootstrap` prefix must contain no state or lock
object. The deterministic renderer adds the reviewed empty GCS backend declaration to the temporary
bootstrap copy and produces a backend configuration containing only the exact platform-state bucket
and `bootstrap` prefix. The operator compares both files with their reviewed digests.

Migration uses Terraform's explicit state-migration mode with locking enabled. Non-interactive
`-force-copy` is permitted only when the proposed operation named it and the owner approved the
already verified empty target immediately before execution; it is never a retry shortcut. A
migration warning, prompt outside the reviewed confirmation, lineage change, occupied target,
credential change, or lock failure stops with the local backup retained.

Post-migration readback must prove:

- the remote state lineage equals the original local lineage;
- the remote serial is not lower than the pre-migration serial;
- provider addresses, resource addresses, instance identities, and non-secret bucket references
  match the pre-migration state;
- the state object is in the platform-state bucket under only the `bootstrap` prefix, versioning is
  active, and no alternate or local active state exists;
- the bootstrap root can acquire and release the native GCS backend lock through a no-change
  operation without `-lock=false`; and
- a fresh remote plan at the same source and input digests reports no unreviewed change.

The restricted local backup remains until those checks and the private recovery-input readback are
owner-accepted. Recovery-input readback proves the exact state generation can be located, read, and
integrity-checked and that an older protected copy remains available; it does not execute a restore
or qualify AP-M9 recovery behavior. After acceptance, the temporary active state, generated
credential, plan, and provider payloads are removed from the working directory. Any retained
recovery copy remains encrypted, access-controlled, separately inventoried, and excluded from the
evidence bundle.

### Non-bootstrap backend initialization

The platform and three fixture roots initialize one at a time from clean private copies. Each
backend configuration contains only its exact bucket and fixed prefix from the reviewed map. The
operator verifies that no local state exists and the remote prefix is empty, then initializes with
input disabled, the committed lock read-only, and no migration or force-copy flag.

Initialization may verify backend access but does not apply a root, create an empty state object,
invent a lineage, or read another root's backend. An empty prefix is recorded as `not-created`; its
lineage becomes available only after AP-M8-W9's first approved apply and is reconciled by
AP-M8-W11. Claiming a lineage for an empty backend, pre-seeding state with `state push`, or using a
dummy resource to create a state generation fails AP-M8-W5.

Each plan identity must be unable to write state content or read another root, while retaining only
the create/delete permission required for its own native lock object. Each apply or rollback
identity must be unable to access another root's bucket or prefix. Exceptional force-unlock and
destroy identities remain unbound unless their separately approved operation is active.

### Partial failure and recovery boundary

Failure before any bucket exists leaves no provider resource and closes the checkpoint. Partial
bucket creation retains the private local state and stops; the operator does not delete, import,
recreate, rename, or manually edit a bucket. A new exact plan and owner decision are required.

Migration failure retains the local state and backup and freezes both local and remote targets.
The operator does not retry with `-reconfigure`, `-force-copy`, `-lock=false`, force-unlock, or state
push until readback identifies the authoritative lineage and a new recovery action is approved.
Loss of the local state before accepted migration is a recovery incident, not permission to import
provider resources or reconstruct state manually.

A mismatch during non-bootstrap initialization leaves that root unapplied and cannot affect another
root. No AP-M8-W5 failure triggers resource destroy, backend deletion, IAM broadening, state repair,
workflow realization, deployment, DNS, traffic, or cleanup.

### Backend checkpoint record

The AP-M8-W5 record may contain source and configuration digests, tool versions, exact command
shapes with values redacted where required, bucket names, regions, policy and label summaries, IAM
role identifiers and conditions, root/prefix mappings, state and lineage digests, serials, object-
generation digests, resource-address inventories, timestamps, approvals, outcomes, limitations, and
the `not-created` status of empty roots.

It contains no credential, token, local or remote state content, lineage value, state attribute,
saved plan, backend object payload, generated credential file, raw provider response, environment
dump, or recovery copy. Passing AP-M8-W5 proves only backend creation, bootstrap-lineage migration,
policy readback, and empty-root initialization; it does not prove a non-bootstrap apply, state
recovery, provider runtime, or Live behavior.

## AP-M8-W6 repository deployment support

AP-M7 deliberately stops at static Terraform and inert workflow templates. The present source is
not an operator-deployable release: it has no production Shared Edge composition entry point, no
container definitions, no networked Fixture Application runtime, no provider-backed qualification
Registration Set, and no executable cloud workflow. In addition, the Version 1 platform interface
requires an image digest, a published configuration-object generation, and three attachment
references before the same root can create their Artifact Registry and configuration bucket.
AP-M8-W6 resolves those repository dependencies through protected-main pull requests before any
AP-M8-W7 authenticated preflight or AP-M8-W9 deployment.

W6 must add and deterministically test only these bounded capabilities:

- a production composition entry point that assembles the already accepted Shared Edge adapters,
  and a pinned, non-root container definition for that entry point;
- one networked synthetic Fixture Application runtime that independently verifies the production
  application assertion and preserves the three fixture applications' separate identity, state,
  authorization, and failure behavior, plus a pinned non-root container definition;
- a provider-backed initial qualification Registration Set using `gcp-cloud-run-v1` attachment
  references under `registrations/qualification/`; the `fixture-in-process-v1` generations under
  `fixtures/registrations/` remain Fixture evidence and are never deployed as Live inputs;
- a Version 2 platform deployment configuration and matching root behavior that preserve one
  Platform State lineage while selecting exactly `foundation` or `candidate` phase;
- credential-free renderers for the append-only operation record and exact workflow
  configurations; and
- fixed `.github/workflows/` files for root plan/apply, artifact publication, generation
  publication, qualification DNS, and the already approved exceptional operations, each bound to
  one workflow, identity, environment class, target, and protected-main source.

The Version 1 platform contract remains accepted AP-M7 static evidence and is not silently
reinterpreted. Version 2 adds an explicit deployment phase and an independently reviewed Artifact
Registry repository identifier. `foundation` accepts no edge image, published generation, or
attachment references and may instantiate only platform foundation and control resources.
`candidate` requires all of those exact immutable values and adds the Shared Edge, load balancer,
address, and managed-certificate resources. Both phases address the same `platform` backend and
state lineage; phase selection never creates a sixth root or permits resource import, replacement,
or deletion. The candidate plan must prove that the previously applied foundation remains
unchanged.

Executable workflows are repository implementation, not permission to run. They remain unusable
until their exact protected source, environments, identities, bindings, operator-manifest revision,
and operation approval all exist. Container and workflow tests use local deterministic substitutes;
the default `make check` never builds, publishes, authenticates, queries a provider, or mutates a
repository setting.

## AP-M8-W7 authenticated deployment preflight

Before the first deployment mutation, one proposed-operation record must bind the exact clean
protected-main revision to the accepted manifest revision and prove all of the following:

- required checks passed with the locked Terraform/provider/Python dependencies and every action,
  base image, and deployable image input is immutable;
- billing and the approved provider APIs are already available, and the reviewed OAuth client,
  redirect, numeric Secret Manager version, managed zone, notification destination, bucket names,
  environment names, identities, and evidence destination exist as references without exposing a
  secret;
- the initial provider-backed Registration Set validates and compiles deterministically, identifies
  no predecessor, and contains only the three synthetic qualification applications;
- every empty non-bootstrap backend still reports `not-created`, bootstrap readback still agrees,
  and no provider or state drift is present;
- the authenticated Platform-foundation plan uses only exact present inputs; the later Fixture and
  candidate expected-resource inventories and plan policies are reviewed without inventing image,
  platform-reference, attachment, or object-generation values, and every later root must receive a
  fresh authenticated plan after its exact dependencies exist;
- every available plan contains no destroy, replacement, unknown service, unapproved API
  enablement, cross-owner resource, Finance resource, or provider default; and
- the owner has approved the exact source, manifest, configuration, expected-resource inventory,
  and redacted plan digests before any dependent operation begins.

Planning may confirm availability and render an expected change set. It cannot publish a package,
reserve a digest, create a state lineage, or discover a value that the accepted manifest was
required to supply. A runtime-generated fact enters only an approved successor manifest revision.

## AP-M8-W8 and AP-M8-W9 deployment sequence

AP-M8 uses this fixed initial-deployment sequence. Each row has its own protected-environment
review, operation identity, backend lock where applicable, readback, immutable record revision, and
stop boundary. Approval or success for one row never authorizes the next.

| Order | Operation | Required result before continuing |
| --- | --- | --- |
| 1 | Apply Platform `foundation` | Configuration bucket, Artifact Registry, edge identities, KMS/Firestore resources, logging/evidence controls, and budget controls agree with the exact same-job plan; no Shared Edge, load balancer, certificate, DNS record, image, or generation object exists |
| 2 | Build and publish images | The Shared Edge and synthetic Fixture runtime are built only from the exact source and pinned bases/dependencies; create-only publication returns reviewed immutable registry digests and leaves no mutable deployment tag authority |
| 3 | Accept platform reference | Actual foundation outputs validate against the Version 1 cross-state-reference contract and the intended issuer, JWKS, and edge-caller identity; no root reads Platform State directly |
| 4 | Apply `fixture-public` | The exact image digest and platform reference produce only that application's runtime, identity, ingress, IAM, state, and attachment reference; provider/state readback agrees |
| 5 | Apply `fixture-authenticated` | The same checks pass in its independent backend and ownership boundary |
| 6 | Apply `fixture-restricted` | The same checks pass in its independent backend and ownership boundary |
| 7 | Compile and publish generation | Actual attachment references form the reviewed `gcp-cloud-run-v1` Registration Set; compilation is deterministic; create-only upload with `ifGenerationMatch=0` returns an exact object generation whose content and generation digests read back correctly |
| 8 | Plan and apply Platform `candidate` | A fresh candidate plan contains only the expected Shared Edge, load balancer, address, and certificate additions, preserves every foundation resource, and binds the exact image digest, object generation, Registration Generation, and three attachments before same-job apply and provider/state readback |

Fixture roots deploy sequentially for the initial environment. A later optimization may not run
them in parallel without new authority because a failure must stop before another application root
starts. The typed platform and attachment references are copied as reviewed non-secret values; a
workflow never reads another root's backend or uses `terraform_remote_state`.

The initial Shared Edge service has no predecessor revision. Its Terraform resource may therefore
assign 100 percent of the Cloud Run service's internal traffic pointer to its only revision, but
the qualification hostname has no DNS record during order 8. AP-M8 calls this a **dark initial
candidate**, not zero-percent Cloud Run traffic, activation, or Live qualification. It does not
authorize a successor-generation traffic switch. Future generation activation must retain
ADR-008's complete-generation staging and explicit pointer-change boundary under later authority.

## AP-M8-W10 qualification DNS and TLS checkpoint

DNS is a separate operation after candidate provider/state/ownership readback. The proposed change
must identify the exact managed zone, the candidate's reserved IPv4 address, the absent current
record, and one new `apps-staging.comfforts.com` A record with TTL 1,800. The DNS identity may
submit only that reviewed transaction. It cannot change `apps.comfforts.com`, an existing record,
an AAAA record, a wildcard, the zone, a Finance hostname, or the load balancer.

After the change, the operator reads back the authoritative zone and independent recursive
resolvers, then waits for the managed certificate to report provider-ready for the exact hostname.
An absent, conflicting, or unexpected answer, address mismatch, certificate failure, or unreviewed
record stops AP-M8 before AP-M9. Reversing only the newly created A record requires a fresh DNS
approval and cannot guarantee immediate disappearance from recursive caches.

DNS and TLS readiness make the deployed candidate reachable; they do not prove routing, login,
assertions, application denial, direct-origin denial, failures, availability, or cost behavior.
Those are AP-M9 Live gates. Until AP-M9 passes, the truthful status is **deployed and not Live-
qualified**.

## Deployment partial-failure boundary

| Failure point | Mandatory stop |
| --- | --- |
| Platform foundation | Publish no image and start no Fixture root; retain exact state/provider readback for owner inspection |
| Image publication | Start no Fixture root; retain any successfully created immutable package, perform no automatic deletion, retag, or retry |
| Platform-reference validation or any Fixture root | Start no later Fixture root, publish no generation, and plan no candidate; do not mutate a successful earlier root |
| Registration compilation or generation publication | Plan no candidate; retain any create-only object for inspection and never overwrite it |
| Candidate plan or apply | Create no DNS record; inspect the partial provider/state result without automatic rollback, unlock, destroy, import, or state repair |
| DNS or certificate | Begin no AP-M9 gate; change only the new record after a separately approved exact reversal, if the owner selects it |

No failure enables broader IAM, provider retry, cleanup, state push, force-unlock, import, destroy,
manual console repair, alternate image, mutable tag, replacement registration, or a skipped
readback. Each requires its own pre-authorized operation or a new owner-approved recovery record.

## AP-M8-W11 deployment readback and evidence

Readback never reuses an apply identity. After the DNS/TLS checkpoint, each fixed root-readback
workflow uses its own Evidence-class identity to read only that root's state metadata and owned
provider resources, reduce the result in runner-temporary restricted storage, scan it for prohibited
data, and create its one redacted readback record. Artifact, generation, and DNS workflows produce
their target-specific readback records through their already scoped identities. No workflow reads
another root's backend or retains raw provider output.

The expected inventory is the accepted manifest chain plus the exact approved plan summaries. For
each root and target, W11 compares:

- source, manifest, configuration, plan, workflow-run, image, Registration Generation,
  configuration-object, and predecessor-chain digests;
- backend bucket/prefix, lineage digest, serial, default workspace, lock result, state-address
  inventory digest, owner, and recovery-input status;
- provider resource types and canonical references, project/region, labels, deletion protection,
  ingress, scale limits, retention, budget thresholds, approved services, and owner;
- direct and inherited IAM roles, workload-principal resource references, key absence, and exact
  root or publication scope;
- Artifact Registry packages/digests, configuration object name/generation/digests, candidate
  revision/image/traffic metadata, three attachment references, reserved IPv4 address, A record,
  TTL, recursive answers, and managed-certificate state; and
- the expected, state, and provider inventories as sorted sets with every missing, extra,
  duplicate, cross-owned, drifted, or unapproved item reported.

The authoritative evidence bundle uses the Version 1 AP-EVAL-M8 schema and exact private
`ap-eval-m8/<source-revision>/<evaluation-id>/` prefix defined by
[the evaluation strategy](../05_evaluation_strategy.md). Operation and readback objects are created
once and hash-chain to their predecessor. A failed operation still writes its redacted failure
record when safe to do so; if evidence writing itself fails, the gate fails and the absence is
recorded by the next owner-controlled recovery record rather than reconstructed.

W11 records no raw state, lineage value, state attribute, plan, lock payload, provider/API response,
credential, token, generated credential file, environment dump, browser state, screenshot, raw log,
assertion, session, restricted member, identity claim, email, IP address, user agent, payload,
application data, signed URL, or recovery copy. The private bundle is owner-readable, retained for
30 days, and not exported. Git may later contain only the approved secret-free index fields.

Any inventory disagreement, unrecognized field, prohibited datum, missing record, hash mismatch,
unexpected warning, expired/mis-scoped access policy, or unrecorded operation fails W11. It is not
redacted away, waived, or converted to a limitation. W11 performs no HTTP runtime request,
rollback, restoration, cleanup, drift injection, force-unlock, state push, import, destroy, or
provider repair.

## AP-M8-W12 qualification-deployment verdict and AP-M9 handoff

The finalization workflow uses the dedicated Evidence identity to read only the exact bundle
prefix. In an ephemeral mode-`0700` directory it renders the final evidence manifest and sorted
record checksums from the approved operator-manifest chain, then runs the committed
`infrastructure.deployment.verify_evidence` command with the exact source, evidence-manifest digest,
and absent verdict-output path. It create-only writes `manifest.v1.json`, `checksums.sha256`, and
`verdict.v1.json`, reads back all three digests, and derives the bundle digest from the canonical
checksum-file/verdict-digest tuple. It cannot query or mutate a provider, read state, alter an
earlier record, or finalize a second source/manifest chain.

All ten AP-EVAL-M8 gates are mandatory. The verdict reports actual `pass`, `fail`, `blocked`, and
`skip` totals, the first causal failure, every attempted operation, and every unavailable later
claim. A dependent gate not run after failure is `blocked`; an otherwise reachable gate not run is
a mandatory skip and fails the verdict. AP-M9, cross-project, Finance, and Adoption claims are
`unavailable` limitations outside the mandatory counts.

W12 passes only when every AP-EVAL-M8 gate passes, all records and checksums are complete and
unique, inventories agree, prohibited-data scans pass, the mandatory skip count is zero, and the
final verdict object reads back with its expected digest. A partial deployment produces only a
failed bundle. A screenshot, manual attestation, console view, prior run, waived discrepancy,
document review, or expired bundle cannot create a pass.

The truthful passing handoff names the exact deployed revision and calls it **deployed and not
Live-qualified**. It may propose AP-M9 only after the AP-M8 implementation/evidence reconciliation
pull request merges. It does not start AP-M9, invoke a runtime, declare rollback or recovery proven,
activate Finance Assistant or an external application migration, authorize a real application, or claim
Application Adoption.
