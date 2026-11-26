# Terraform lifecycle composition

Status: AP-M9-W5 repository implementation. No function in this package authenticates, initializes
a backend, invokes a production command, or mutates a provider resource.

This package is the deterministic seam between the lifecycle core and later interactive deployment
work:

- `backend_declarations()` returns the reviewed environment, Terraform-root, state-owner, bucket,
  and prefix bindings.
- `render_backend_declaration()` writes one canonical private `backend.tf` beneath an explicitly
  supplied working root and returns its digest.
- `plan_policy()` and `evaluate_plan()` reduce a redacted plan observation to an accepted canonical
  summary and digest, or ordered fail-closed violations.
- `prepare_phase_plan()` composes those declarations through an injected `TerraformPlanCommands`
  interface. W5 tests supply deterministic command fakes; this package provides no production
  command adapter.

The active operator uses one verified short-lived human session; this package creates no operation
identity, impersonation binding, service-account key, credential, or token. Production remains
unavailable and returns `OWNERSHIP_TRANSFER_REQUIRED`. Generated backend files,
saved plans, state, credentials, provider payloads, and authenticated artifacts must remain outside
Git in an owner-approved private working directory. AP-M9-W6 may add non-fake command adapters only
behind the injected boundary and must preserve these declarations and fail-closed policies.

The platform-foundation inventory includes the isolated Firestore member database and its custom
exact-read runtime role. When an existing Shared Edge makes the foundation pass refresh-only, the
shared-edge policy admits only the exact named database, role, conditioned binding, and session
binding reconciliation addresses. Another inherited IAM or Firestore mutation remains prohibited.
