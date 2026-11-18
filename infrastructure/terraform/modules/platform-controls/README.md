# Platform Controls module

Internal AP-M7 module for the qualification environment's bounded observability, evidence,
retention, and cost intent. Its small interface accepts one complete non-secret controls object.
The implementation owns the regional seven-day log bucket, internal sink, and default-bucket
exclusion, explicit owner-read intent, private 30-day evidence bucket, USD 20 project budget, and
dry-run Artifact Registry retention policy.

Environment and Terraform state ownership, backend and provider configuration, operator values,
credentials, evidence objects, image publication, billing response, cleanup approval, deployment,
and provider readback remain outside this module. Its budget produces notifications only, and its
artifact cleanup policy cannot delete while dry-run remains enabled.
