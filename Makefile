PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
ENVIRONMENT ?= staging
OPERATOR_STATE_DIRECTORY ?= .platform-operator
SOURCE_AUTHORITY ?= accepted
PREFLIGHT_MODE ?= operational
SPECIFICATION_DIGEST ?=
APPLICATION_ID ?=
APPLICATION_PROJECT_ID ?=
FIXTURES_PROJECT_ID ?= comfforts-app-fixtures-nonprod
ACCESS_MODE ?=
ROUTE_INTENT ?=
PLATFORM_SOURCE_REVISION ?=
PLATFORM_GENERATION ?=
GENERATION_DIGEST ?=
INTEGRATION_BUNDLE ?=
ATTACHMENT_BUNDLE ?=
REGISTRATION_INTENT ?=

export FIXTURES_PROJECT_ID

.PHONY: check governance-check contract-check fixture-check runtime-check terraform-check terraform-setup operator-check platform-preflight platform-prepare platform-cancel platform-deploy platform-status fixture-project-bootstrap platform-connect-project platform-outputs platform-register platform-detach platform-retire platform-qualify platform-destroy fixture-handoff fixture-status fixture-destroy

## Install pinned Terraform dependencies into the ignored project-local mirror.
terraform-setup:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) infrastructure/tools/terraform_setup.py


## Deterministic platform checks include governance, contract, fixture, runtime, and Terraform validations.

## Deterministic platform checks.
check: governance-check contract-check fixture-check runtime-check terraform-check operator-check ## Run every implemented deterministic platform check.

## Verify the standalone project shell without credentials or external services.
governance-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_governance

## Verify versioned contracts without credentials or external services.
contract-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_contracts tests.test_lifecycle_contracts tests.test_lifecycle_vectors tests.test_qualification_contracts

## Verify the deterministic in-process fixture edge without external services.
fixture-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_fixtures tests.test_networked_fixtures

## Verify the Shared Edge interface without credentials or external network access.
runtime-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_edge_runtime tests.test_proxy tests.test_observability tests.test_runtime_qualification tests.test_live_runtime

## Verify the pinned Terraform foundation offline in a disposable copy.
terraform-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_terraform_foundation tests.test_infrastructure_config tests.test_backend_lifecycle tests.test_plan_policy tests.test_terraform_lifecycle tests.test_terraform_bootstrap tests.test_terraform_fixtures tests.test_terraform_platform_foundation tests.test_terraform_shared_edge tests.test_terraform_platform_controls tests.test_workflow_templates tests.test_terraform_qualification

## Verify the credential-free interactive lifecycle core with deterministic adapters.
operator-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_source_authority tests.test_operator_lifecycle tests.test_platform_deployment tests.test_operator_commands tests.test_local_deployment_inputs tests.test_local_deployment_commands tests.test_deployment_provider_commands tests.test_deployment_dns tests.test_application_integration tests.test_registration_lifecycle tests.test_integration_cli tests.test_local_integration tests.test_local_handoffs tests.test_local_generation_control tests.test_generation_provider_commands tests.test_project_connections tests.test_fixture_deployment_lifecycle tests.test_local_fixture_deployment tests.test_qualification_lifecycle tests.test_qualification_suite tests.test_local_qualification tests.test_live_qualification_browser tests.test_live_qualification_probe tests.test_qualification_destruction_cli tests.test_generation_rollback tests.test_destruction_specification tests.test_destruction_lifecycle tests.test_local_destruction_control tests.test_local_destruction_commands


## Platform management commands.

## Check operational readiness, or use PREFLIGHT_MODE=development for local source diagnostics.
platform-preflight:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator preflight --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --preflight-mode "$(PREFLIGHT_MODE)"

## Prepare and explicitly approve one complete lifecycle specification.
platform-prepare:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator prepare --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Cancel only the active private resume record; never mutate Terraform or cloud resources.
platform-cancel:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator cancel --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Prepare, approve, and execute one exact deployment in the same interactive process.
platform-deploy: terraform-setup
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator deploy --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" $(if $(SPECIFICATION_DIGEST),--specification-digest "$(SPECIFICATION_DIGEST)",)

## Report local desired and execution state without changing it.
platform-status:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator status --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Create or repair the dedicated fixture application project; creates no runtime or route.
fixture-project-bootstrap:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator fixture-project-bootstrap --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-project-id "$(FIXTURES_PROJECT_ID)"

## Attach one existing application project to the platform Shared VPC; creates no runtime or route.
platform-connect-project:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-connect-project --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-project-id "$(APPLICATION_PROJECT_ID)"

## Generate one application-scoped non-secret integration bundle.
platform-outputs:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator outputs --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-id "$(APPLICATION_ID)" --application-project-id "$(APPLICATION_PROJECT_ID)" --access-mode "$(ACCESS_MODE)" --route-intent "$(ROUTE_INTENT)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --platform-generation "$(PLATFORM_GENERATION)"

## Validate one attachment and propose an immutable whole registration generation.
platform-register:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator register --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --integration-bundle "$(INTEGRATION_BUNDLE)" --attachment-bundle "$(ATTACHMENT_BUNDLE)" --registration-intent "$(REGISTRATION_INTENT)"

## Suspend one active route through an exact whole-generation transition.
platform-detach:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator detach --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-id "$(APPLICATION_ID)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --generation-digest "$(GENERATION_DIGEST)"

## Permanently retire one route through an exact whole-generation transition.
platform-retire:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator retire --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-id "$(APPLICATION_ID)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --generation-digest "$(GENERATION_DIGEST)"

## Evaluate and record the exact current platform and fixture revisions.
platform-qualify:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator qualify --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Compile, confirm, and resume exact safe platform destruction.
platform-destroy:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator destroy --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"


## Fixture management commands.

## Deploy one selected fixture from an existing integration bundle and stop before registration.
fixture-handoff: terraform-setup
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator fixture-handoff --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-id "$(APPLICATION_ID)" --integration-bundle "$(INTEGRATION_BUNDLE)"

## Reconcile all fixtures, or APPLICATION_ID when supplied, without mutation.
fixture-status:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator fixture-status --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" $(if $(APPLICATION_ID),--application-id "$(APPLICATION_ID)",)

## Destroy one selected fixture after platform-detach has suspended its route.
fixture-destroy: terraform-setup
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator fixture-destroy --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-id "$(APPLICATION_ID)"
