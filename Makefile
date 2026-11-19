PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
ENVIRONMENT ?= staging
OPERATOR_STATE_DIRECTORY ?= .platform-operator

.PHONY: check governance-check contract-check fixture-check runtime-check terraform-check terraform-setup operator-check platform-prepare platform-status

check: governance-check contract-check fixture-check runtime-check terraform-check operator-check ## Run every implemented deterministic platform check.

governance-check: ## Verify the standalone project shell without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_governance tests.test_finance_integration_draft

contract-check: ## Verify versioned contracts without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_contracts tests.test_lifecycle_contracts tests.test_lifecycle_vectors

fixture-check: ## Verify the deterministic in-process fixture edge without external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_fixtures

runtime-check: ## Verify the Shared Edge interface without credentials or external network access.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_edge_runtime tests.test_proxy tests.test_observability tests.test_runtime_qualification

terraform-setup: ## Install pinned Terraform dependencies into the ignored project-local mirror.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) infrastructure/tools/terraform_setup.py

terraform-check: ## Verify the pinned Terraform foundation offline in a disposable copy.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_terraform_foundation tests.test_infrastructure_config tests.test_backend_lifecycle tests.test_plan_policy tests.test_terraform_lifecycle tests.test_terraform_bootstrap tests.test_terraform_fixtures tests.test_terraform_platform_foundation tests.test_terraform_shared_edge tests.test_terraform_platform_controls tests.test_workflow_templates tests.test_terraform_qualification

operator-check: ## Verify the credential-free interactive lifecycle core with deterministic adapters.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_operator_lifecycle tests.test_platform_deployment tests.test_operator_commands

platform-prepare: ## Prepare and explicitly approve one complete lifecycle specification.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator prepare --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)"

platform-status: ## Report local desired and execution state without changing it.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m infrastructure.operator status --environment "$(ENVIRONMENT)" --state-directory "$(OPERATOR_STATE_DIRECTORY)"
