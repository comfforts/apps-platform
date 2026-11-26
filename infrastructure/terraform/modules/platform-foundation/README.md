# Platform foundation module

Internal module for the Platform State foundation phase. Its one interface accepts only values
available before Shared Edge deployment. The implementation owns the configuration bucket, the
default Firestore database and TTL field for Platform Sessions, the isolated
`app-platform-members` Firestore database for the Platform Member Directory, edge runtime and
caller identities, regional asymmetric signing key, OAuth Secret Manager container, required
provider services, and the minimum runtime access intents. Provider services remain enabled on
destroy so teardown cannot silently affect unmanaged project workloads.

The Shared Edge session role is conditioned to the default database. Its member-directory role is
a project custom role containing only `datastore.entities.get`, conditioned to the named member
database. It cannot list, create, update, or delete member documents. Exact-key lookup needs no
composite index, so the closed output reports an empty required-index set rather than creating an
enumeration-oriented index. Terraform publishes only the database, namespace, role, condition, and
capability posture; it never owns or emits a directory control document or member record.

The root retains environment, state-owner, backend, provider, and operator-input policy. This
module does not accept an image, OAuth client identifier, secret version, signing key version,
Registration Generation, attachment, member identity, or member record. It creates no secret
version, exports no signing material, and does not configure Shared Edge runtime, load-balancing,
or DNS resources.
