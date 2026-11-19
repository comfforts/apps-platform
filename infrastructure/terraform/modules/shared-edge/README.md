# Shared Edge module

Internal module for one platform-owned staging edge and its hostname-level forwarding resources.
Its small interface accepts one complete generated, non-secret edge binding after foundation.
The implementation owns the Cloud Run revision, edge-only invocation policy, global address,
serverless NEG and backend, optional post-DNS managed-certificate intent, HTTPS forwarding, and
HTTP redirect. The first pass can expose the reserved address without enabling TLS.

Environment selection, Terraform state ownership, backend and provider configuration, operator
values, DNS, generation publication, workflow activation, attachment discovery, and application
runtime ownership remain outside this module. Application attachments stay inside the compiled
Registration Generation; they are not Terraform inputs or provider targets.
