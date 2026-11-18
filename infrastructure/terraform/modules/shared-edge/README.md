# Shared Edge module

Internal AP-M7 module for the one platform-owned qualification edge and its hostname-level
forwarding resources. Its small interface accepts one complete, non-secret edge configuration.
The implementation owns the Cloud Run revision, edge-only invocation policy, global address,
serverless NEG and backend, managed-certificate intent, HTTPS forwarding, and HTTP redirect.

Environment selection, Terraform state ownership, backend and provider configuration, operator
values, DNS, generation publication, workflow activation, attachment discovery, and application
runtime ownership remain outside this module. Attachment references enter only as typed data and
never become provider targets or URL-map routes.
