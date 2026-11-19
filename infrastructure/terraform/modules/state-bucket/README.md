# Internal state-bucket module

This AP-M7-W4 module is internal implementation behind the bootstrap root interface. It accepts one
explicit bucket name, root-owned labels, and the shared bounded recovery policy, then describes one
private, versioned GCS state bucket. It owns no backend, environment, state owner, provider
configuration, identity, IAM member, credential, or operator-specific default.

The module emits the configured bucket name and an internal policy summary used by the bootstrap
root's plan-only mocked-provider tests. The root alone constructs typed references and declares
ownership. Callers outside the bootstrap root consume the closed `bootstrap_phase_output`, which
maps four buckets to the bootstrap, platform, and three Fixture Application lineages.

No IAM member is inferred in AP-M7-W4. The `state_owner`, `owner_id`, unique bucket, and backend
prefix make root-scoped access intent explicit without inventing a principal. Identity creation,
binding, backend initialization, and provider readback remain later, separately approved work.
