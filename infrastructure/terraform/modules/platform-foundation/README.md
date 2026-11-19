# Platform foundation module

Internal module for the Platform State foundation phase. Its one interface accepts only values
available before Shared Edge deployment. The implementation owns the configuration bucket,
Platform Session database and TTL field, edge runtime and caller identities, regional asymmetric
signing key, OAuth Secret Manager container, and the minimum runtime access intents.

The root retains environment, state-owner, backend, provider, and operator-input policy. This
module does not accept an image, OAuth client identifier, secret version, signing key version,
Registration Generation, attachment, application identity, or restricted member. It creates no
secret version, exports no signing material, and does not configure Shared Edge runtime,
load-balancing, or DNS resources.
