PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
ENVIRONMENT ?= staging
OPERATOR_STATE_DIRECTORY ?= .platform-operator
SPECIFICATION_DIGEST ?=
APPLICATION_ID ?=
ACCESS_MODE ?=
ROUTE_INTENT ?=
PLATFORM_SOURCE_REVISION ?=
PLATFORM_GENERATION ?=
GENERATION_DIGEST ?=
INTEGRATION_BUNDLE ?=
ATTACHMENT_BUNDLE ?=
REGISTRATION_INTENT ?=

.PHONY: check governance-check contract-check fixture-check runtime-check terraform-check terraform-setup operator-check platform-prepare platform-deploy platform-status platform-outputs platform-register platform-detach platform-retire platform-qualify platform-destroy

check: governance-check contract-check fixture-check runtime-check terraform-check operator-check ## Run every implemented deterministic platform check.

governance-check: ## Verify the standalone project shell without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_governance tests.test_finance_integration_draft

contract-check: ## Verify versioned contracts without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_contracts tests.test_lifecycle_contracts tests.test_lifecycle_vectors tests.test_qualification_contracts

fixture-check: ## Verify the deterministic in-process fixture edge without external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_fixtures tests.test_networked_fixtures

runtime-check: ## Verify the Shared Edge interface without credentials or external network access.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_edge_runtime tests.test_proxy tests.test_observability tests.test_runtime_qualification tests.test_live_runtime

terraform-setup: ## Install pinned Terraform dependencies into the ignored project-local mirror.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) infrastructure/tools/terraform_setup.py

terraform-check: ## Verify the pinned Terraform foundation offline in a disposable copy.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_terraform_foundation tests.test_infrastructure_config tests.test_backend_lifecycle tests.test_plan_policy tests.test_terraform_lifecycle tests.test_terraform_bootstrap tests.test_terraform_fixtures tests.test_terraform_platform_foundation tests.test_terraform_shared_edge tests.test_terraform_platform_controls tests.test_workflow_templates tests.test_terraform_qualification

operator-check: ## Verify the credential-free interactive lifecycle core with deterministic adapters.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_operator_lifecycle tests.test_platform_deployment tests.test_operator_commands tests.test_application_integration tests.test_registration_lifecycle tests.test_integration_cli tests.test_local_integration tests.test_local_handoffs tests.test_local_generation_control tests.test_generation_provider_commands tests.test_qualification_lifecycle tests.test_qualification_suite tests.test_local_qualification tests.test_qualification_destruction_cli tests.test_generation_rollback tests.test_destruction_specification tests.test_destruction_lifecycle tests.test_local_destruction_control

platform-prepare: ## Prepare and explicitly approve one complete lifecycle specification.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator prepare --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)"

platform-deploy: ## Prepare, approve, and execute one exact deployment in the same interactive process.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator deploy --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" $(if $(SPECIFICATION_DIGEST),--specification-digest "$(SPECIFICATION_DIGEST)",)

platform-status: ## Report local desired and execution state without changing it.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator status --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)"

platform-outputs: ## Generate one application-scoped non-secret integration bundle.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator outputs --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --application-id "$(APPLICATION_ID)" --access-mode "$(ACCESS_MODE)" --route-intent "$(ROUTE_INTENT)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --platform-generation "$(PLATFORM_GENERATION)"

platform-register: ## Validate one attachment and propose an immutable whole registration generation.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator register --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --integration-bundle "$(INTEGRATION_BUNDLE)" --attachment-bundle "$(ATTACHMENT_BUNDLE)" --registration-intent "$(REGISTRATION_INTENT)"

platform-detach: ## Suspend one active route through an exact whole-generation transition.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator detach --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --application-id "$(APPLICATION_ID)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --generation-digest "$(GENERATION_DIGEST)"

platform-retire: ## Permanently retire one route through an exact whole-generation transition.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator retire --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)" --application-id "$(APPLICATION_ID)" --platform-source-revision "$(PLATFORM_SOURCE_REVISION)" --generation-digest "$(GENERATION_DIGEST)"

platform-qualify: ## Evaluate and record the exact current platform and fixture revisions.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator qualify --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)"

platform-destroy: ## Compile, confirm, and resume exact safe platform destruction.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator destroy --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)"
