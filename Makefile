PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
ENVIRONMENT ?= staging
OPERATOR_STATE_DIRECTORY ?= .platform-operator
SOURCE_AUTHORITY ?= accepted
PREFLIGHT_MODE ?= operational
SPECIFICATION_DIGEST ?=
APPLICATION_ID ?=
APPLICATION_PROJECT_ID ?=
FIXTURES_PROJECT_ID ?= comfforts-fixtures-nonprod
FIXTURES_PROJECT_NAME ?= Comfforts Fixtures Non-Prod
ACCESS_MODE ?=
IDENTITY_DELIVERY ?=
ROUTE_INTENT ?=
PLATFORM_SOURCE_REVISION ?=
PLATFORM_GENERATION ?=
GENERATION_DIGEST ?=
INTEGRATION_BUNDLE ?=
ATTACHMENT_BUNDLE ?=
REGISTRATION_INTENT ?=
MEMBER_REFERENCE ?=

export FIXTURES_PROJECT_ID FIXTURES_PROJECT_NAME

.PHONY: check governance-check contract-check fixture-check runtime-check terraform-check terraform-setup operator-check platform-preflight platform-preflight-check platform-prepare platform-cancel platform-deploy platform-deploy-check platform-status fixture-project-bootstrap platform-connect-project application-handoff-check platform-outputs platform-register platform-detach platform-retire platform-qualify platform-destroy platform-member-status platform-member-bootstrap-owner platform-member-add platform-member-suspend platform-member-reactivate platform-member-remove fixture-handoff fixture-status fixture-destroy

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
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_contracts tests.test_lifecycle_contracts tests.test_identity_delivery_contracts tests.test_lifecycle_vectors tests.test_qualification_contracts

## Verify the deterministic in-process fixture edge without external services.
fixture-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_fixtures tests.test_networked_fixtures

## Verify the Shared Edge interface without credentials or external network access.
runtime-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_edge_runtime tests.test_proxy tests.test_observability tests.test_runtime_qualification tests.test_live_runtime

## Verify the pinned Terraform foundation offline in a disposable copy.
terraform-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_terraform_foundation tests.test_infrastructure_config tests.test_backend_lifecycle tests.test_plan_policy tests.test_terraform_lifecycle tests.test_terraform_bootstrap tests.test_terraform_fixtures tests.test_terraform_platform_foundation tests.test_terraform_shared_edge tests.test_terraform_platform_controls tests.test_workflow_templates tests.test_terraform_qualification tests.test_member_directory

## Verify the credential-free interactive lifecycle core with deterministic adapters.
operator-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_source_authority tests.test_operator_lifecycle tests.test_platform_deployment tests.test_operator_commands tests.test_local_deployment_inputs tests.test_local_deployment_commands tests.test_deployment_provider_commands tests.test_deployment_dns tests.test_application_integration tests.test_application_handoff_check tests.test_registration_lifecycle tests.test_integration_cli tests.test_local_integration tests.test_local_handoffs tests.test_local_generation_control tests.test_generation_provider_commands tests.test_project_connections tests.test_fixture_deployment_lifecycle tests.test_local_fixture_deployment tests.test_member_lifecycle tests.test_member_browser tests.test_member_cli tests.test_local_members tests.test_qualification_lifecycle tests.test_qualification_suite tests.test_local_qualification tests.test_live_qualification_browser tests.test_live_qualification_probe tests.test_qualification_destruction_cli tests.test_generation_rollback tests.test_destruction_specification tests.test_destruction_lifecycle tests.test_local_destruction_control tests.test_local_destruction_commands


## Platform management commands.

## Check operational readiness, or use PREFLIGHT_MODE=development for local source diagnostics.
platform-preflight:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator preflight --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --preflight-mode "$(PREFLIGHT_MODE)"

## Run real readiness diagnostics from an uncommitted working tree; grants no source authority.
platform-preflight-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator preflight --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --preflight-mode development

## Prepare and explicitly approve one complete lifecycle specification.
platform-prepare:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator prepare --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Cancel only the active private resume record; never mutate Terraform or cloud resources.
platform-cancel:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator cancel --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Check platform readiness, then prepare, approve, and execute fresh exact plans.
platform-deploy: terraform-setup
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator deploy --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" $(if $(SPECIFICATION_DIGEST),--specification-digest "$(SPECIFICATION_DIGEST)",)

## Classify current working-tree platform readiness without approval or mutation.
platform-deploy-check: terraform-setup
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator deploy-check --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Report local desired and execution state without changing it.
platform-status:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator status --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Create or repair the dedicated fixture application project; creates no runtime or route.
fixture-project-bootstrap:
	FIXTURES_PROJECT_ID="$(FIXTURES_PROJECT_ID)" FIXTURES_PROJECT_NAME="$(FIXTURES_PROJECT_NAME)" PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator fixture-project-bootstrap --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-project-id "$(FIXTURES_PROJECT_ID)"

## Attach one existing application project to the platform Shared VPC; creates no runtime or route.
platform-connect-project:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-connect-project --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-project-id "$(APPLICATION_PROJECT_ID)"

## Require platform readiness, then check project connection, services, and handoff inputs.
application-handoff-check: terraform-setup
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator application-handoff-check --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-id "$(APPLICATION_ID)" --application-project-id "$(APPLICATION_PROJECT_ID)" --access-mode "$(ACCESS_MODE)" --identity-delivery "$(IDENTITY_DELIVERY)" --route-intent "$(ROUTE_INTENT)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --platform-generation "$(PLATFORM_GENERATION)"

## Generate one application-scoped non-secret integration bundle.
platform-outputs:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator outputs --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --application-id "$(APPLICATION_ID)" --application-project-id "$(APPLICATION_PROJECT_ID)" --access-mode "$(ACCESS_MODE)" --identity-delivery "$(IDENTITY_DELIVERY)" --route-intent "$(ROUTE_INTENT)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --platform-generation "$(PLATFORM_GENERATION)"

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

## Read coarse directory state or one exact opaque member reference; never list members.
platform-member-status:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-member-status --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" $(if $(MEMBER_REFERENCE),--member-reference "$(MEMBER_REFERENCE)",)

## Enroll exactly one initial owner after remote-empty and browser-identity verification.
platform-member-bootstrap-owner:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-member-bootstrap-owner --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Enroll one browser-verified Google Visitor as an active platform member.
platform-member-add:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-member-add --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)"

## Suspend one exact previously enrolled opaque member after exact review.
platform-member-suspend:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-member-suspend --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --member-reference "$(MEMBER_REFERENCE)"

## Reactivate one exact previously enrolled opaque member after exact review.
platform-member-reactivate:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-member-reactivate --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --member-reference "$(MEMBER_REFERENCE)"

## Remove one exact previously enrolled opaque member after destructive review.
platform-member-remove:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator platform-member-remove --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --source-authority "$(SOURCE_AUTHORITY)" --member-reference "$(MEMBER_REFERENCE)"


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
