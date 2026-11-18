# Platform foundation module

Internal AP-M7 module for the Platform State identity and immutable-generation foundation. Its one
interface accepts reviewed non-secret storage, generation, session, identity-reference, and signing
policy. The implementation owns the configuration bucket, Platform Session database and TTL field,
edge runtime and caller identities, regional asymmetric signing key, and the minimum runtime access
intents.

The root retains environment, state-owner, backend, provider, and operator-input policy. This
module does not compile or upload a Registration Generation, create a secret or secret version,
export signing material, activate a revision, create an application identity, or configure Shared
Edge runtime, load-balancing, DNS, observability, evidence, or cost resources.
