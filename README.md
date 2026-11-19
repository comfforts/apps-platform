# Comfforts App Platform

Status: AP-M9-W1 governance rebaseline in review; Contract, Fixture, network-runtime, and static
Terraform implementation exist; no platform environment is deployed or qualified

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
- AP-M9 is the only active remaining platform milestone. W1 establishes its operator-driven
  lifecycle authority; W2 will remove the retired manifest implementation.

No GCP resource, state backend, OAuth client, DNS record, certificate, Shared Edge deployment,
application registration, or Live evidence is created merely by the repository implementation.

## Planned operator interface

AP-M9 will implement these Make targets over one deep interactive Python lifecycle module:

```bash
make platform-prepare ENVIRONMENT=staging
make platform-deploy ENVIRONMENT=staging
make platform-status ENVIRONMENT=staging
make platform-outputs ENVIRONMENT=staging APPLICATION=finance-assistant
make platform-register ENVIRONMENT=staging ATTACHMENT_BUNDLE=/path/to/bundle.json
make platform-detach ENVIRONMENT=staging APPLICATION=finance-assistant
make platform-retire ENVIRONMENT=staging APPLICATION=finance-assistant
make platform-qualify ENVIRONMENT=staging
make platform-destroy ENVIRONMENT=staging
```

These targets do not exist until their named AP-M9 work packages implement and test them. The normal
deployment wizard will remain active across Google OAuth and Squarespace DNS work and continue when
the operator presses Enter. It will never request an OAuth secret in the terminal.

## Application boundary

The platform generates a non-secret Platform Integration Bundle. The Application Owner consumes
that bundle, deploys its own assets, and returns an Application Attachment Bundle. Registration
validates the target without reading or taking ownership of application state.

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
