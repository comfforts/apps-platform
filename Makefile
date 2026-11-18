PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: check governance-check contract-check fixture-check runtime-check terraform-check terraform-setup

check: governance-check contract-check fixture-check runtime-check terraform-check ## Run every implemented deterministic platform check.

governance-check: ## Verify the standalone project shell without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_governance tests.test_finance_integration_draft

contract-check: ## Verify versioned contracts without credentials or external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_contracts

fixture-check: ## Verify the deterministic in-process fixture edge without external services.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_fixtures

runtime-check: ## Verify the Shared Edge interface without credentials or external network access.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_edge_runtime tests.test_proxy tests.test_observability tests.test_runtime_qualification

terraform-setup: ## Install pinned Terraform dependencies into the ignored project-local mirror.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) infrastructure/tools/terraform_setup.py

terraform-check: ## Verify the pinned Terraform foundation offline in a disposable copy.
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests.test_terraform_foundation tests.test_infrastructure_config tests.test_terraform_bootstrap tests.test_terraform_fixtures tests.test_terraform_platform_foundation tests.test_terraform_shared_edge tests.test_terraform_platform_controls tests.test_workflow_templates tests.test_terraform_qualification
