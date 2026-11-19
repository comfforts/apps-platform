# Comfforts App Platform

Status: AP-M9-W7 application integration lifecycle implemented and deterministically verified; no
platform environment is deployed or qualified

Comfforts App Platform owns the shared hostname edge, catalogue, registration, routing, admission,
platform identity, and environment lifecycle used by independently owned applications. Applications
retain their runtimes, data, stores, providers, secrets, principals, Feature Entitlements, and
Application State.

The product goal is a compact human-operated lifecycle for isolated staging and production
environments:

```text
prepare -> approve -> deploy -> status -> outputs -> qualify -> destroy
                                      |
                                      v
                 application deploy -> register -> detach/retire
```

The implementation remains Python for AP-M9. A Python-to-Go migration is deliberately deferred
until the Python product is delivered and qualified so the existing implementation can provide
comparison and rollback behavior.

## Current authority and status

- AP-M3 implements Version 1 contracts and deterministic compilation.
- AP-M4 Fixture-qualifies the in-process reference platform with three synthetic applications.
- AP-M5 records provider, identity, state, lifecycle, evidence, and cost planning.
- AP-M6 implements the networked Shared Edge and production adapters behind deterministic fakes and
  process-local loopback tests.
- AP-M7 implements statically verified Terraform configuration and inert workflow templates. It
  performs no backend or provider operation.
- AP-M8-W1/W2 are historical merged work from the superseded manifest-driven approach. No real
  manifest was accepted and AP-M8-W3 through AP-M8-W12 never began.
- AP-M9 is the only active remaining platform milestone. W1 established its operator-driven
  lifecycle authority, W2 removed the retired manifest implementation, W3 implemented the closed
  lifecycle contracts, W4 implements the deep Python core plus credential-free
  `platform-prepare` and `platform-status`, and W5 implements the phased Terraform lifecycle,
  backend declarations, operation-authority profiles, and exact plan policy. W6 implements the
  staged deployment engine, closed command boundary, interactive checkpoints, and
  `platform-deploy`. W7 implements least-data outputs, attachment validation, immutable
  whole-generation registration, detach/reactivate, and terminal retirement. W8 is next.

No GCP resource, state backend, OAuth client, DNS record, certificate, Shared Edge deployment,
application registration, or Live evidence is created merely by the repository implementation.

## Operator interface

AP-M9-W4, W6, and W7 expose these thin targets over one deep interactive Python lifecycle module:

```bash
make platform-prepare ENVIRONMENT=staging
make platform-status ENVIRONMENT=staging
make platform-deploy ENVIRONMENT=staging SPECIFICATION_DIGEST=sha256:<64-lowercase-hex>
make platform-outputs ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated \
  ACCESS_MODE=authenticated ROUTE_INTENT=/fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> PLATFORM_GENERATION=1
make platform-register ENVIRONMENT=staging \
  INTEGRATION_BUNDLE=/private/path/platform-integration-bundle.json \
  ATTACHMENT_BUNDLE=/private/path/application-attachment-bundle.json \
  REGISTRATION_INTENT=/private/path/registration-intent.json
make platform-detach ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> GENERATION_DIGEST=sha256:<64-lowercase-hex>
make platform-retire ENVIRONMENT=staging APPLICATION_ID=fixture-authenticated \
  PLATFORM_SOURCE_REVISION=<40-lowercase-hex> GENERATION_DIGEST=sha256:<64-lowercase-hex>
```

Preparation requires clean current `main`, the committed Environment Profile, and the pinned local
toolchain. It emits one canonical specification into the ignored private `.platform-operator/`
directory and requests explicit approval of that digest. Status reads local lifecycle state without
changing it. Deploy accepts only the exact current, approved specification digest and journals each
closed stage. Its engine requires fresh private plans, exact typed confirmations, provider
readback, same-process OAuth/Squarespace checkpoints, and bounded DNS/TLS polling. Production
remains blocked by `OWNERSHIP_TRANSFER_REQUIRED`.

W7 writes integration bundles create-only beneath the ignored private operator directory. It
validates exact application attachments, compiles immutable complete Registration Generations, and
requires exact typed confirmation before generation activation. Detach is reversible; retirement
is terminal. Its terminal result contains only coarse outcome and digest facts, never restricted
membership or target payloads.

The default local construction remains deliberately unarmed until the W8 qualification and safe-
destruction package completes. Repository checks exercise deployment and integration through
deterministic fakes, and no non-fake external adapter is invoked by `make check`. The remaining
targets are planned and do not exist yet:

```bash
make platform-qualify ENVIRONMENT=staging
make platform-destroy ENVIRONMENT=staging
```

W6 keeps the deployment wizard active across Google OAuth and Squarespace DNS work and continues
when the operator presses Enter. It never requests an OAuth secret in the terminal. The pull
request itself performs no authentication, backend initialization, plan, apply, image publication,
provider readback, DNS lookup/change, or deployment; AP-M9-W9 remains the first real operation.

## Application boundary

The W3 contracts define the non-secret Platform Integration Bundle and Application Attachment Bundle.
W7 generates least-data integration bundles from exact platform readback, validates an
application-owned target against the attachment and current platform state, and activates only
immutable complete Registration Generations. The provider and generation boundaries remain
unarmed locally until W8. Validation never reads or takes ownership of Application State.

Detachment is reversible and permits application destruction/redeployment while preserving the
application identifier and route. Retirement is terminal. Platform destruction never destroys
Application State.

Finance Assistant and `apps.comfforts.com` remain Finance-owned until a separate Finance adoption
and production ownership-transfer procedure completes. Production preparation must stop with
`OWNERSHIP_TRANSFER_REQUIRED` rather than importing or mutating those resources.

## Local verification

From the repository root:

```bash
make terraform-setup
make check
```

`terraform-setup` installs checksum-pinned public tooling into the ignored local cache. `make check`
is deterministic, credential-free, network-free after setup, and non-mutating. Authenticated plans,
applies, OAuth, DNS, provider readback, qualification, and destruction use later explicit operator
actions only.

Read [AGENTS.md](AGENTS.md) before changing the project and follow the authority order in
[docs/README.md](docs/README.md).
