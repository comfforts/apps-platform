# Fixture Application module

Internal AP-M7 module for one application-owned qualification runtime. Its small interface accepts
one complete runtime object and one reviewed edge-caller principal. The implementation owns the
runtime identity, Cloud Run service, ingress posture, bounded scaling, non-secret identity
references, and the single Invoker grant intent.

Environment selection, Terraform state ownership, backend configuration, provider configuration,
operator values, and cross-root lookup remain root responsibilities. The module performs no data
lookup and creates no key, credential, load balancer, DNS record, platform identity, or application
feature grant.
