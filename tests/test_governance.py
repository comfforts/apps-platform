"""Standalone App Platform authority-foundation checks."""

from __future__ import annotations

from collections.abc import Iterator
import json
import re
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _canonical_architecture_decisions() -> str:
    """Load one current text for each indexed ADR, excluding origin duplicates."""

    adr_directory = PROJECT_ROOT / "docs/adr"
    origin = (
        adr_directory / "000-origin-architecture-decision-records.md"
    ).read_text(encoding="utf-8")
    origin_sections = {
        match.group(1): match.group(0).replace("## ADR-", "# ADR-", 1)
        for match in re.finditer(
            r"^## (ADR-\d{3}) ·[\s\S]*?(?=^## ADR-\d{3} ·|\Z)",
            origin,
            re.MULTILINE,
        )
    }
    extracted = {}
    for path in adr_directory.glob("[0-9][0-9][0-9]-*.md"):
        if path.name.startswith("000-"):
            continue
        content = path.read_text(encoding="utf-8")
        identifier = re.search(r"^# (ADR-\d{3}) ·", content, re.MULTILINE)
        if identifier is None:
            raise AssertionError(f"extracted ADR has no identifier: {path}")
        extracted[identifier.group(1)] = content

    return "\n\n".join(
        extracted[identifier] if identifier in extracted else origin_sections[identifier]
        for identifier in (f"ADR-{number:03d}" for number in range(1, 17))
    )


def _repository_files() -> Iterator[Path]:
    """Yield repository files without ignored private operator runtime state."""

    for path in PROJECT_ROOT.rglob("*"):
        relative = path.relative_to(PROJECT_ROOT)
        if path.is_file() and relative.parts[0] != ".platform-operator":
            yield path


class ProjectAuthorityTest(unittest.TestCase):
    def test_project_shell_is_self_contained(self) -> None:
        expected_files = (
            ".gitignore",
            ".github/workflows/check.yml",
            "AGENTS.md",
            "GLOSSARY.md",
            "Makefile",
            "README.md",
            "docs/01_product_requirements.md",
            "docs/02_architecture_decision_records.md",
            "docs/adr/README.md",
            "docs/adr/000-origin-architecture-decision-records.md",
            "docs/adr/003-platform-admission-does-not-grant-application-feature-access.md",
            "docs/adr/006-edge-managed-google-oidc-and-application-bound-assertions.md",
            "docs/adr/008-activate-immutable-generations-through-one-reviewed-edge-revision.md",
            "docs/adr/010-use-one-interactive-lifecycle-module.md",
            "docs/adr/011-bind-interactive-mutation-to-one-verified-session.md",
            "docs/adr/012-exchange-versioned-non-secret-bundles.md",
            "docs/adr/015-platform-member-directory-and-explicit-identity-delivery.md",
            "docs/adr/016-recover-operator-working-state-without-fabricated-history.md",
            "docs/03_system_design.md",
            "docs/04_implementation_plan.md",
            "docs/plans/README.md",
            "docs/plans/000-origin-implementation-plan.md",
            "docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md",
            "docs/plans/ap_m9/w10_platform_member_directory.md",
            "docs/05_evaluation_strategy.md",
            "docs/06_threat_model.md",
            "docs/README.md",
            "docs/repository_extraction_handoff.md",
            "docs/repository_layout.md",
            "docs/history/README.md",
            "docs/history/ap_m8_manifest_delivery.md",
            "docs/runbooks/README.md",
            "docs/runbooks/environment_lifecycle.md",
            "docs/runbooks/repository_extraction.md",
            "contracts/README.md",
            "contracts/lifecycle/README.md",
            "contracts/lifecycle/__init__.py",
            "contracts/lifecycle/validation.py",
            "contracts/lifecycle/schemas/application-attachment-bundle.v1.schema.json",
            "contracts/lifecycle/schemas/deployment-specification.v1.schema.json",
            "contracts/lifecycle/schemas/environment-profile.v1.schema.json",
            "contracts/lifecycle/schemas/platform-integration-bundle.v1.schema.json",
            "contracts/validation.py",
            "contracts/test-vectors/manifest.v1.json",
            "infrastructure/config/profiles/production.v1.json",
            "infrastructure/config/profiles/staging.v1.json",
            "infrastructure/operator/__init__.py",
            "infrastructure/operator/__main__.py",
            "infrastructure/operator/_core.py",
            "infrastructure/operator/_interfaces.py",
            "infrastructure/operator/README.md",
            "infrastructure/operator/cli.py",
            "infrastructure/operator/local.py",
            "fixtures/__init__.py",
            "fixtures/applications.py",
            "fixtures/identity.py",
            "fixtures/reference_edge.py",
            "fixtures/registrations/manifest.v1.json",
            "edge/__init__.py",
            "edge/_attachments.py",
            "edge/_assertions.py",
            "edge/_generation.py",
            "edge/_identity.py",
            "edge/_observability.py",
            "edge/_proxy.py",
            "edge/_routing.py",
            "edge/_runtime.py",
            "edge/verification.py",
            "infrastructure/workflows/README.md",
            "infrastructure/workflows/advisory-plan.yml.tmpl",
            "infrastructure/workflows/destroy.yml.tmpl",
            "infrastructure/workflows/exact-main-apply.yml.tmpl",
            "infrastructure/workflows/force-unlock.yml.tmpl",
            "infrastructure/workflows/rollback.yml.tmpl",
            "prompts/README.md",
            "prompts/starting_prompt.md",
            "pyproject.toml",
            "tests/test_contracts.py",
            "tests/test_edge_runtime.py",
            "tests/test_fixtures.py",
            "tests/test_governance.py",
            "tests/__init__.py",
            "tests/_network_guard.py",
            "tests/test_observability.py",
            "tests/test_operator_lifecycle.py",
            "tests/test_proxy.py",
            "tests/test_runtime_qualification.py",
            "tests/test_terraform_qualification.py",
            "tests/test_workflow_templates.py",
            "tests/fixtures/assertion-test-keys.jwk.json",
            "tests/fixtures/oidc-test-private.jwk.json",
            "uv.lock",
        )

        self.assertTrue(all((PROJECT_ROOT / path).is_file() for path in expected_files))

    def test_extraction_owned_workflow_is_root_relative_and_read_only(self) -> None:
        workflow = (PROJECT_ROOT / ".github/workflows/check.yml").read_text(
            encoding="utf-8"
        )
        uses = re.findall(r"^\s+- uses: ([^@\s]+)@([0-9a-f]{40})", workflow, re.MULTILINE)

        self.assertEqual(
            uses,
            [
                (
                    "actions/checkout",
                    "d23441a48e516b6c34aea4fa41551a30e30af803",
                ),
                (
                    "actions/setup-python",
                    "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
                ),
                (
                    "astral-sh/setup-uv",
                    "68559e99cc807c1eb7e9238fd43a15bba460eec2",
                ),
            ],
        )
        self.assertEqual(workflow.count("- uses:"), len(uses))
        for required in (
            "pull_request:",
            "push:",
            "branches: [main]",
            "workflow_dispatch:",
            "permissions:\n  contents: read",
            "persist-credentials: false",
            "python-version: 3.12.12",
            "version: 0.12.5",
            "cache-dependency-glob: uv.lock",
            "uv sync --frozen --python 3.12.12",
            "run: make terraform-setup",
            "run: make check",
        ):
            self.assertIn(required, workflow)
        for prohibited in (
            "pull_request_target",
            "id-token: write",
            "contents: write",
            "apps-platform/",
            "make -C",
            "terraform apply",
            "terraform plan",
            "terraform init",
            "gcloud",
            "secrets.",
        ):
            self.assertNotIn(prohibited, workflow)

    def test_makefile_exposes_a_portable_non_mutating_check(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn(
            "check: governance-check contract-check fixture-check",
            makefile,
        )
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", makefile)
        self.assertIn("python3", makefile)
        self.assertNotIn("../", makefile)
        self.assertNotIn("terraform apply", makefile)
        self.assertNotIn("gcloud", makefile)

    def test_locked_runtime_foundation_is_extraction_safe(self) -> None:
        pyproject = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        lock = tomllib.loads((PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        observability = (PROJECT_ROOT / "edge/_observability.py").read_text(
            encoding="utf-8"
        )
        packages = {package["name"]: package for package in lock["package"]}

        self.assertEqual(pyproject["project"]["requires-python"], ">=3.12")
        self.assertIn(
            f'RUNTIME_VERSION = "{pyproject["project"]["version"]}"',
            observability,
        )
        self.assertEqual(
            pyproject["project"]["dependencies"],
            [
                "Authlib>=1.9,<1.10",
                "cryptography>=50,<51",
                "google-cloud-kms>=3.19,<3.20",
                "google-cloud-run>=0.16,<0.17",
                "google-cloud-firestore>=2.34,<2.35",
                "google-cloud-storage>=3.17,<3.18",
                "google-crc32c>=1.9,<1.10",
                "google-auth>=2.62,<2.63",
                "httpx>=0.28,<0.29",
                "starlette>=1.10,<1.11",
                "uvicorn>=0.54,<0.55",
                "websockets>=17.4,<18",
            ],
        )
        self.assertFalse(pyproject["tool"]["uv"]["package"])
        self.assertEqual(packages["authlib"]["version"], "1.9.8")
        self.assertEqual(packages["cryptography"]["version"], "50.0.2")
        self.assertEqual(packages["google-cloud-kms"]["version"], "3.19.0")
        self.assertEqual(packages["google-cloud-run"]["version"], "0.16.3")
        self.assertEqual(packages["google-cloud-firestore"]["version"], "2.34.1")
        self.assertEqual(packages["google-cloud-storage"]["version"], "3.17.1")
        self.assertEqual(packages["google-crc32c"]["version"], "1.9.0")
        self.assertEqual(packages["google-auth"]["version"], "2.62.2")
        self.assertEqual(packages["httpx"]["version"], "0.28.1")
        self.assertEqual(packages["starlette"]["version"], "1.10.0")
        self.assertEqual(packages["uvicorn"]["version"], "0.54.0")
        self.assertEqual(packages["websockets"]["version"], "17.4")
        self.assertIn("hash", packages["authlib"]["sdist"])
        self.assertIn("hash", packages["cryptography"]["sdist"])
        self.assertIn("hash", packages["google-cloud-kms"]["sdist"])
        self.assertIn("hash", packages["google-cloud-run"]["sdist"])
        self.assertIn("hash", packages["google-cloud-firestore"]["sdist"])
        self.assertIn("hash", packages["google-cloud-storage"]["sdist"])
        self.assertIn("hash", packages["google-crc32c"]["sdist"])
        self.assertIn("hash", packages["google-auth"]["sdist"])
        self.assertIn("hash", packages["httpx"]["sdist"])
        self.assertIn("hash", packages["starlette"]["sdist"])
        self.assertIn("hash", packages["uvicorn"]["sdist"])
        self.assertIn("hash", packages["websockets"]["sdist"])
        self.assertIn("runtime-check", makefile)
        self.assertNotIn("uv sync", makefile)
        self.assertNotIn("uv lock", makefile)

    def test_local_ignore_policy_excludes_sensitive_runtime_state(self) -> None:
        ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        for pattern in (
            ".env",
            ".venv/",
            "**/.terraform/",
            ".cache/terraform/",
            "*.tfstate",
            "*.tfplan",
            "*.tfvars",
        ):
            self.assertIn(pattern, ignore)
        self.assertNotIn(".terraform.lock.hcl", ignore)

    def test_agent_instructions_route_to_platform_authority(self) -> None:
        instructions = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        normalized_instructions = " ".join(instructions.split())

        self.assertIn("docs/README.md", instructions)
        self.assertIn("canonical router to that authority", instructions)
        self.assertIn("Do not recreate them in this file", instructions)
        self.assertIn(
            "Keep each project-specific rule in its authoritative project document",
            instructions,
        )
        self.assertIn("run `make check` from the dedicated", instructions)
        self.assertNotIn("make -C apps-platform check", instructions)
        self.assertIn("one bounded slice per pull request", instructions)
        self.assertIn("leave each change uncommitted until approval", instructions)
        self.assertIn("Merge it before starting the next documented slice", instructions)
        self.assertIn("Name branches `<type>/<short-scope>`", instructions)
        self.assertIn("`docs/` for documentation or", instructions)
        self.assertIn("`feat/` for product behavior", instructions)
        self.assertIn("`fix/` for defect correction", instructions)
        self.assertIn("`evidence/`", instructions)
        self.assertIn("`chore/` for small maintenance", instructions)
        self.assertIn("never substitute an author or tool name such as `codex/`", instructions)
        self.assertIn(
            "Trace every claimed operator or user journey to an executable entry point and deterministic tests",
            normalized_instructions,
        )
        self.assertIn(
            "Treat absent authority as unresolved rather than inferred",
            normalized_instructions,
        )
        self.assertIn(
            "An approved implementation slice does not implicitly authorize an external mutation",
            normalized_instructions,
        )
        self.assertNotRegex(instructions, r"AP-M\d")
        self.assertNotIn("Finance Assistant", instructions)
        self.assertNotIn("platform-deploy", instructions)
        self.assertNotIn("operator-manifest", instructions)

    def test_operator_authorization_and_fixture_readiness_are_unambiguous(self) -> None:
        requirements = (PROJECT_ROOT / "docs/01_product_requirements.md").read_text(
            encoding="utf-8"
        )
        decisions = _canonical_architecture_decisions()
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        glossary = (PROJECT_ROOT / "GLOSSARY.md").read_text(encoding="utf-8")

        for document in (requirements, decisions, design):
            normalized = " ".join(document.split())
            self.assertIn("no separate out-of-band approval", normalized)
            self.assertIn("Destruction, purge, ownership transfer", normalized)
        self.assertIn("## Operator Invocation", glossary)
        self.assertIn("separate Application State", requirements)
        self.assertIn("Static Terraform, process-local loopback", requirements)
        self.assertIn("`fixture-handoff`", design)
        self.assertIn("`fixture-project-bootstrap`", design)
        self.assertIn("`platform-connect-project`", design)
        self.assertIn("`fixture-status`", design)
        self.assertIn("`fixture-destroy`", design)

    def test_documentation_truthfully_records_planning_and_evidence_status(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")
        overview = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        history = (
            PROJECT_ROOT / "docs/history/ap_m8_manifest_delivery.md"
        ).read_text(encoding="utf-8")
        normalized_index = " ".join(index.split())
        normalized_layout = " ".join(layout.split())
        normalized_overview = " ".join(overview.split())

        self.assertIn(
            "AP-M9-W9 candidate-qualified under Version 1",
            normalized_index,
        )
        self.assertIn("Contract (`C`) and Fixture (`F`) evidence", normalized_index)
        self.assertIn("Candidate Source Live (`L`) evidence", normalized_index)
        self.assertIn(
            "Accepted Source Live evidence and Application Adoption (`A`) evidence do not yet exist",
            normalized_index,
        )
        self.assertIn("AP-M8 | historical", index)
        self.assertIn("AP-M9-W1 — governance rebaseline", index)
        self.assertIn("AP-M9-W12 — production readiness", index)
        self.assertIn("candidate staging proved the dedicated fixture project", normalized_overview.lower())
        self.assertIn("not accepted source qualification", normalized_overview.lower())
        self.assertIn("Platform Integration Bundle", overview)
        self.assertIn("Application Attachment Bundle", overview)
        self.assertIn("OWNERSHIP_TRANSFER_REQUIRED", overview)
        for section in (
            "## What the platform owns",
            "## Application categories",
            "## How the platform works",
            "## Repository structure",
            "## Set up the repository",
            "## Prepare for an operator session",
            "## Operate a platform environment",
            "## Integrate and manage applications",
            "## Maintain the project",
            "## Operational readiness",
        ):
            self.assertIn(section, overview)
        self.assertIn("uv sync --frozen --python 3.12", overview)
        self.assertIn("make terraform-setup", overview)
        self.assertIn("make check", overview)
        self.assertIn("SOURCE_AUTHORITY=candidate", overview)
        for application_category in (
            "### Admission mode",
            "`public`",
            "`authenticated`",
            "`restricted`",
            "### Catalogue visibility",
            "`listed`",
            "`unlisted`",
            "### Lifecycle state",
            "`active`",
            "`suspended` / detached",
            "`retired`",
            "### Fixture and adopted applications",
            "`fixture-public`",
            "`fixture-authenticated`",
            "`fixture-restricted`",
        ):
            self.assertIn(application_category, overview)
        self.assertIn("Admission decides whether a request may reach", overview)
        self.assertIn("the application still decides its own users, principals", overview)
        self.assertIn("`public` describes only the platform's admission decision", overview)
        self.assertIn("including a separate\nOAuth client", overview)
        self.assertIn(
            "Applications registered as `authenticated` or `restricted` rely on platform admission",
            overview,
        )
        self.assertIn("application-specific audience, time bounds, and contract", overview)
        self.assertIn("must verify the resulting assertion by the same rules", overview)
        self.assertIn("receives neither the platform OAuth client", overview)
        self.assertIn("Applications using\n`authenticated` or `restricted` admission", overview)
        self.assertIn("including a public one, accepts traffic only from the Shared Edge", overview)
        self.assertNotIn("Protected applications", overview)
        self.assertIn("There is intentionally no\ncombined `fixture-deploy` command", overview)
        self.assertIn(
            "make fixture-handoff \\\n  ENVIRONMENT=staging \\\n  APPLICATION_ID=fixture-public",
            overview,
        )
        self.assertIn("writes the canonical bundle pair and registration intent", normalized_overview)
        self.assertIn("It never registers or routes the fixture", overview)
        self.assertIn("FIXTURES_PROJECT_ID=comfforts-fixtures-nonprod", overview)
        self.assertIn('FIXTURES_PROJECT_NAME="Comfforts Fixtures Non-Prod"', overview)
        self.assertIn("APPLICATION_PROJECT_ID=comfforts-fixtures-nonprod", overview)
        for fixture_application_id in (
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
        ):
            self.assertIn(fixture_application_id, overview)
        self.assertIn(
            "`fixture-status` is suite-wide by default, or narrowed with an optional `APPLICATION_ID`",
            overview,
        )
        self.assertIn("keeping `platform-outputs`, fixture runtime deployment, and", overview)
        self.assertIn("There is no App Platform Make target for deploying a real application", overview)
        self.assertIn("The complete handoff sequence is", overview)
        self.assertIn("Readiness preflight", overview)
        self.assertIn("Optional specification preparation and review", overview)
        self.assertIn("make platform-preflight ENVIRONMENT=staging", overview)
        self.assertIn("without creating lifecycle state", overview)
        self.assertIn("not a required predecessor to `platform-deploy`", overview)
        self.assertIn("The operator does not need to copy its digest", overview)
        self.assertIn("No digest copy-and-paste is required", overview)
        self.assertIn("SPECIFICATION_DIGEST=sha256:<digest>", overview)
        self.assertIn("ordinary one-command deployment sequence starts with `platform-deploy`", overview)
        self.assertIn("fixture-destroy", overview)
        self.assertNotIn("## Current authority and status", overview)
        self.assertNotIn("AP-M8-W3 through AP-M8-W12", overview)
        self.assertIn("canonical dedicated repository", normalized_layout)
        self.assertIn("docs/history/", layout)
        self.assertIn("AP-M9 capability locations", layout)
        self.assertIn("`contracts/`", layout)
        self.assertIn("`fixtures/`", layout)
        self.assertIn("history-preserving extraction", normalized_layout)
        self.assertIn("7b6678a7f0b3036d427517dad6bc3bec876d1a44", history)
        self.assertIn("no real operator manifest had been accepted", history)
        self.assertIn("AP-M9-W2 removed the schema", history)

        for current_entry_point in (
            PROJECT_ROOT / "AGENTS.md",
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "docs/README.md",
            PROJECT_ROOT / "docs/repository_layout.md",
            PROJECT_ROOT / "docs/05_evaluation_strategy.md",
            PROJECT_ROOT / "prompts/starting_prompt.md",
        ):
            contents = current_entry_point.read_text(encoding="utf-8")
            self.assertNotIn("make -C apps-platform check", contents)
            self.assertNotIn("temporarily colocated", contents)

    def test_repository_extraction_runbook_preserves_history_and_authority(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        runbook_index = (PROJECT_ROOT / "docs/runbooks/README.md").read_text(
            encoding="utf-8"
        )
        runbook = (
            PROJECT_ROOT / "docs/runbooks/repository_extraction.md"
        ).read_text(encoding="utf-8")
        handoff = (
            PROJECT_ROOT / "docs/repository_extraction_handoff.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(runbook.split())
        normalized_handoff = " ".join(handoff.split())

        self.assertIn("[Runbook index](runbooks/README.md)", index)
        self.assertIn("[Repository extraction runbook](runbooks/repository_extraction.md)", index)
        self.assertIn(
            "[handoff](repository_extraction_handoff.md)",
            index,
        )
        self.assertIn(
            "[repository extraction handoff](../repository_extraction_handoff.md)",
            runbook,
        )
        self.assertIn("no action is authorized merely because a runbook exists", runbook_index)
        for boundary in (
            "https://github.com/hankgalt/ai_finance_assitant.git",
            "https://github.com/comfforts/apps-platform.git",
            "Target visibility | Public",
            "Target default branch | `main`",
            "the target repository exists, has the fixed identity above, and `git ls-remote` reports no branch",
            "Run the dry run in a new disposable directory",
            "subtree split",
            "must be byte-identical",
            "make -C \"$extraction_workspace/extracted\" check",
            "requires a new explicit owner approval after the dry-run evidence is reviewed",
            "The first `ls-remote` must be empty",
            "Do not push another branch or tag",
            "During transition, platform changes stop in both repositories",
            "Only after that pull request and its required checks pass may the Platform Owner declare",
            "Removing or replacing that copy and its CI wrapper is a separate, recoverable",
            "It proves no Terraform, provider, cloud, DNS, identity, deployment, Live, or Application Adoption behavior",
        ):
            self.assertIn(boundary, normalized)
        self.assertLess(runbook.index("## Dry-run"), runbook.index("## Initial push"))
        self.assertLess(
            runbook.index("## Initial push"),
            runbook.index("## Repository settings and reconciliation"),
        )
        self.assertNotIn("git push --force", runbook)
        self.assertNotIn("git push --mirror", runbook)
        self.assertNotIn("terraform apply", runbook)
        self.assertNotIn("gcloud ", runbook)

        for evidence in (
            "f5f7cef84a0d7e2850e496f8ce56f3afdb7944c6",
            "66ae90b2760c44f4142236ac96c472ab1e748c60",
            "d120aa3c5608dce78000a014d7bc12fd5a25555b",
            "a12da61450c0ca970d8b8662841a5462771c72ee",
            "Git 2.50.1 (Apple Git-155)",
            "all 189 tests",
            "Credential-free project checks",
            "Secret scanning through Secret Protection and push protection are enabled",
            "Code scanning uses CodeQL default setup",
            "22f32da94854bbc265d40c8125f56b4efbbe7558",
            "6ecd60079dc87458fac993222cbb9e789d2e78ac",
            "b049be2bd4e8969a4160f05f6e0943092bace780",
            "5a44dd16e4976a24e9e1a4256cc4769c18eaa86a",
            "Status: checkpoints 1 through 5 owner-approved and complete",
            "Source-tree and CI-wrapper cleanup | Owner-approved and complete",
            "the owner explicitly declared `comfforts/apps-platform` canonical",
            "contains neither the `apps-platform/` directory nor `.github/workflows/apps-platform-ci.yml`",
            "AP-M7 and every later provider or application slice remain outside this extraction",
        ):
            self.assertIn(evidence, normalized_handoff)
        self.assertNotIn("source-repository cleanup pending", normalized_handoff)

    def test_ap_m3_authorities_have_complete_unique_identifiers(self) -> None:
        plan = (PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^### (AP-M3-W\d+) ·", plan, re.MULTILINE)
        evaluation_gates = re.findall(
            r"^### (AP-EVAL-M3-\d{2}) ·", evaluation, re.MULTILINE
        )
        threats = re.findall(r"^### (AP-TM-\d{3}) ·", threat_model, re.MULTILINE)

        self.assertEqual(
            work_packages, [f"AP-M3-W{index}" for index in range(1, 7)]
        )
        self.assertEqual(
            evaluation_gates,
            [f"AP-EVAL-M3-{index:02d}" for index in range(1, 10)],
        )
        self.assertEqual(
            threats,
            [f"AP-TM-{index:03d}" for index in range(1, 15)],
        )

    def test_product_requirements_have_unique_stable_identifiers(self) -> None:
        requirements = (PROJECT_ROOT / "docs/01_product_requirements.md").read_text(
            encoding="utf-8"
        )
        observed = re.findall(r"^### (AP-(?:PR|QR)-\d{3}) ·", requirements, re.MULTILINE)
        expected = {
            *(f"AP-PR-{index:03d}" for index in range(1, 13)),
            *(f"AP-QR-{index:03d}" for index in range(1, 10)),
        }

        self.assertEqual(set(observed), expected)
        self.assertEqual(len(observed), len(set(observed)))

    def test_product_requirements_preserve_platform_boundaries(self) -> None:
        requirements = (PROJECT_ROOT / "docs/01_product_requirements.md").read_text(
            encoding="utf-8"
        )

        for boundary in (
            "feature authorization",
            "Application State",
            "Platform State",
            "Fixture Applications",
            "Application Adoption",
            "real-application migration",
            "does not change a consuming",
        ):
            self.assertIn(boundary, requirements)

    def test_architecture_decisions_are_unique_and_trace_requirements(self) -> None:
        decisions = _canonical_architecture_decisions()
        observed = re.findall(r"^# (ADR-\d{3}) ·", decisions, re.MULTILINE)

        self.assertEqual(
            observed,
            [
                "ADR-001",
                "ADR-002",
                "ADR-003",
                "ADR-004",
                "ADR-005",
                "ADR-006",
                "ADR-007",
                "ADR-008",
                "ADR-009",
                "ADR-010",
                "ADR-011",
                "ADR-012",
                "ADR-013",
                "ADR-014",
                "ADR-015",
                "ADR-016",
            ],
        )
        self.assertEqual(decisions.count("Status: Accepted"), 15)
        self.assertEqual(decisions.count("Status: Proposed"), 1)
        normalized_decisions = " ".join(decisions.split())
        for identifier in (
            "AP-PR-001",
            "AP-PR-002",
            "AP-PR-003",
            "AP-PR-004",
            "AP-PR-005",
            "AP-PR-006",
            "AP-PR-007",
            "AP-PR-008",
            "AP-PR-009",
            "AP-QR-001",
            "AP-QR-002",
            "AP-QR-003",
            "AP-QR-004",
            "AP-QR-006",
        ):
            self.assertIn(identifier, decisions)

        for live_topology_decision in (
            "comfforts-platform-non-prod",
            "apps-staging.comfforts.com",
            "gcp-cloud-run-v1",
            "platform-owned Shared VPC",
            "explicit, separately approved operator actions",
            "no Terraform configuration",
        ):
            self.assertIn(live_topology_decision, decisions)

        for live_identity_decision in (
            "authorization-code flow",
            "Consumer Google",
            "accounts and Google Workspace accounts",
            "Firestore Native",
            "absolute lifetime of eight hours",
            "EC_SIGN_P256_SHA256",
            "maximum lifetime of 60 seconds",
            "at most 30 seconds of clock skew",
            "at least every 90 days",
            "24-hour verification overlap",
            "at most 15 minutes",
            "does not claim distributed replay prevention",
        ):
            self.assertIn(live_identity_decision, normalized_decisions)

        for state_and_operator_decision in (
            "remote GCS backend with native state locking and object versioning",
            "fixtures use separate prefixes in one versioned bucket owned by their dedicated fixture application project",
            "at least 90 days old",
            "at least 20 newer generations",
            "No platform root uses `terraform_remote_state`",
            "GitHub Actions using OIDC and GCP Workload Identity Federation",
            "A pull-request plan is advisory",
            "Routine workstation apply is prohibited",
            "Provider-console changes are drift",
            "no backend bucket, state, workflow, identity, credential, plan",
        ):
            self.assertIn(state_and_operator_decision, normalized_decisions)

        for activation_and_rollback_decision in (
            "immutable compiled configuration object is published as an inactive candidate",
            "environment-and-generation path",
            "generation digest, content digest, and exact GCS object generation",
            "traffic assignment to one immutable edge revision",
            "There is no separate registration endpoint or database",
            "100 percent of edge traffic",
            "provider error or incomplete apply stops for inspection",
            "Successful readback must agree across source, state, provider, and runtime",
            "initial rollback-time objective is 15 minutes",
            "available for at least 24 hours",
            "1,800-second TTL",
            "checks authoritative and recursive resolution with `dig`",
            "does not touch `apps.comfforts.com`",
            "no registration file, configuration bucket, object, edge revision, DNS",
        ):
            self.assertIn(activation_and_rollback_decision, normalized_decisions)

        for evidence_and_cost_decision in (
            "dedicated Cloud Logging bucket",
            "retention is seven days",
            "does not intentionally retain source IP addresses",
            "dedicated private GCS evidence bucket",
            "Evidence retention is 30 days",
            "Screenshots, authenticated browser state, raw provider responses",
            "App Platform Owner is the initial security, availability, privacy, and cost incident contact",
            "monthly budget of USD 20",
            "notifications at 50, 80, and 100 percent",
            "Shared Edge | 0 | 2 | 1 vCPU | 512 MiB | 20",
            "Each Fixture Application | 0 | 1 | 1 vCPU | 512 MiB | 10",
            "at most 55 minutes per connection",
            "no CDN, WAF, HSM key, production replica",
            "Cleanup policy is evaluated in dry-run mode first",
            "platform project pays for Shared Edge resources",
            "no log or evidence bucket, budget, alert, runtime limit",
        ):
            self.assertIn(evidence_and_cost_decision, normalized_decisions)

    def test_shared_edge_decisions_preserve_exclusive_ownership(self) -> None:
        decisions = _canonical_architecture_decisions()

        for boundary in (
            "certificate secures a hostname",
            "not a certificate boundary",
            "only authoritative input",
            "No resource may be managed by both states",
            "does not transfer ownership",
            "does not move them",
            "Direct manual route changes are drift",
        ):
            self.assertIn(boundary, decisions)

    def test_admission_decision_does_not_become_feature_authorization(self) -> None:
        decisions = _canonical_architecture_decisions()
        glossary = (PROJECT_ROOT / "GLOSSARY.md").read_text(encoding="utf-8")

        for mode in ("**Public:**", "**Authenticated:**", "**Restricted:**"):
            self.assertIn(mode, decisions)
        for boundary in (
            "Being listed does not grant admission",
            "being admitted does not grant a Feature Entitlement",
            "Email addresses are display or contact attributes",
            "next request or new streaming-connection boundary",
            "market-data-style Feature Entitlement",
            "does not alter its current access policy",
        ):
            self.assertIn(boundary, decisions)
        for term in (
            "## Admission Decision",
            "## Verified Identity Context",
            "## Application Principal",
            "## Feature Entitlement",
        ):
            self.assertIn(term, glossary)

    def test_fixture_first_decision_keeps_application_adoption_separate(self) -> None:
        decisions = _canonical_architecture_decisions()
        normalized_decisions = " ".join(decisions.split())
        glossary = (PROJECT_ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")

        for boundary in (
            "before any real application may be adopted",
            "remain outside Platform State",
            "no Finance Assistant code",
            "is not platform acceptance evidence",
            "A cutover must leave each resource with one active state owner",
            "Finance Assistant-owned slice and evidence",
        ):
            self.assertIn(boundary, normalized_decisions)
        self.assertIn("## Application Adoption", glossary)
        self.assertIn("independent synthetic Application State roots", layout)

    def test_architecture_decision_index_routes_one_canonical_record_per_identifier(
        self,
    ) -> None:
        index = (PROJECT_ROOT / "docs/adr/README.md").read_text(encoding="utf-8")
        docs_router = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        compatibility_router = (
            PROJECT_ROOT / "docs/02_architecture_decision_records.md"
        ).read_text(encoding="utf-8")
        origin = (
            PROJECT_ROOT / "docs/adr/000-origin-architecture-decision-records.md"
        ).read_text(encoding="utf-8")
        inventory = index.split("## Decision inventory", 1)[1].split(
            "## Realization and evidence", 1
        )[0]
        normalized_index = " ".join(index.split())
        observed = re.findall(r"^\| (ADR-\d{3}) \|", inventory, re.MULTILINE)

        self.assertEqual(
            observed,
            [f"ADR-{number:03d}" for number in range(1, 17)],
        )
        self.assertEqual(len(observed), len(set(observed)))
        self.assertEqual(inventory.count("Origin ADR-"), 8)
        self.assertEqual(inventory.count("Extracted ADR-"), 6)
        canonical_links = re.findall(
            r"\[(?:Origin|Extracted) ADR-\d{3}\]\(([^)#]+)(?:#[^)]+)?\)",
            inventory,
        )
        self.assertEqual(len(canonical_links), 14)
        self.assertTrue(
            all((PROJECT_ROOT / "docs/adr" / link).is_file() for link in canonical_links)
        )
        self.assertEqual(
            sorted(
                path.name[:3]
                for path in (PROJECT_ROOT / "docs/adr").glob("[0-9][0-9][0-9]-*.md")
                if not path.name.startswith("000-")
            ),
            ["003", "006", "008", "010", "011", "012", "015", "016"],
        )
        self.assertEqual(
            re.findall(r"^## (ADR-\d{3}) ·", origin, re.MULTILINE),
            [f"ADR-{number:03d}" for number in range(1, 15)],
        )
        self.assertIn("preserves the consolidated form", origin)
        self.assertIn("compatibility path", compatibility_router)
        self.assertIn("[architecture decision index](adr/README.md)", compatibility_router)
        self.assertIn("Decision status and realization status are intentionally separate", index)
        self.assertIn("ADR-016", index)
        self.assertIn("Proposed; still in discussion", index)
        self.assertIn(
            "grants no implementation or external-operation authority",
            normalized_index,
        )
        self.assertIn("[Architecture decision index](adr/README.md)", docs_router)

    def test_proposed_operator_recovery_separates_current_posture_from_history(
        self,
    ) -> None:
        recovery = (
            PROJECT_ROOT
            / "docs/adr/016-recover-operator-working-state-without-fabricated-history.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(recovery.split())

        for boundary in (
            "Status: Proposed; still in discussion",
            "Deployed Authority",
            "Operator Working State",
            "Operator Run Record",
            "Recovery Baseline",
            "platform-operator-recover",
            "externally read-only",
            "must not synthesize",
            "Run separation and reconciliation",
            "local `latest` selection",
            "cannot resume or apply a plan from a missing run",
            "fresh readiness check",
            "does not approve a future operation",
            "AP-M9-W10 continues to exclude operator-state recovery",
        ):
            self.assertIn(boundary, normalized)
        self.assertIn("ADR-010 and ADR-011 remain the accepted authority", normalized)

    def test_ap_m9_w10_handoff_loads_exact_member_directory_authority(
        self,
    ) -> None:
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        prompt_index = (PROJECT_ROOT / "prompts/README.md").read_text(encoding="utf-8")
        normalized_prompt = " ".join(prompt.split())

        for authority in (
            "AGENTS.md",
            "docs/README.md",
            "AP-M9-W10",
            "AP-PR-004 through AP-PR-006",
            "AP-QR-006 through AP-QR-009",
            "ADR-015",
            "AP-EVAL-M9-09",
            "AP-TM-004",
        ):
            self.assertIn(authority, prompt)
        for boundary in (
            "after the governance change accepting ADR-015 has merged",
            "Platform Member Directory",
            "explicit Identity Delivery",
            "platform-member-bootstrap-owner",
            "remotely empty directory",
            "suspend, reactivate, and remove",
            "do not compile a Registration Generation",
            "Run the complete credential-free `make check` gate",
            "Candidate Source staging testing",
            "first Accepted Source staging operation after W10",
            "any real application",
        ):
            self.assertIn(boundary, normalized_prompt)
        self.assertNotIn("### AP-PR-", prompt)
        self.assertNotIn("## ADR-", prompt)
        self.assertIn(
            "[AP-M9-W10 member directory handoff](starting_prompt.md)",
            prompt_index,
        )

    def test_implementation_plan_index_routes_m9_and_w10_to_current_plans(self) -> None:
        index = (PROJECT_ROOT / "docs/plans/README.md").read_text(encoding="utf-8")
        origin = (
            PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md"
        ).read_text(encoding="utf-8")
        m9 = (
            PROJECT_ROOT / "docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md"
        ).read_text(encoding="utf-8")
        w10 = (
            PROJECT_ROOT / "docs/plans/ap_m9/w10_platform_member_directory.md"
        ).read_text(encoding="utf-8")
        compatibility = (
            PROJECT_ROOT / "docs/04_implementation_plan.md"
        ).read_text(encoding="utf-8")
        docs_router = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")

        self.assertIn("canonical plan router through AP-M9-W12", index)
        self.assertIn("000-origin-implementation-plan.md", index)
        self.assertIn("ap_m9/000-m9_interactive_platform_lifecycle.md", index)
        self.assertIn("ap_m9/w10_platform_member_directory.md", index)
        self.assertIn("only current plan for that\nidentifier", index)
        self.assertIn("estimation signals", index)
        self.assertIn("# App Platform origin implementation plan", origin)
        self.assertIn("## Historical AP-M8", origin)
        self.assertNotIn("# AP-M9 · Operator-driven environment lifecycle", origin)
        self.assertIn("# AP-M9 · Operator-driven environment lifecycle", m9)
        self.assertIn("### AP-M9-W10", m9)
        self.assertIn("### AP-M9-W12", m9)
        self.assertIn("compatibility router", compatibility)
        self.assertIn("plans/README.md", compatibility)
        self.assertIn(
            "plans/ap_m9/000-m9_interactive_platform_lifecycle.md",
            compatibility,
        )
        self.assertIn("plans/ap_m9/w10_platform_member_directory.md", compatibility)
        self.assertIn("[Implementation plan index](plans/README.md)", docs_router)
        self.assertIn(
            "[AP-M9 milestone plan](plans/ap_m9/000-m9_interactive_platform_lifecycle.md)",
            docs_router,
        )
        self.assertIn(
            "[AP-M9-W10 delivery plan](plans/ap_m9/w10_platform_member_directory.md)",
            docs_router,
        )

        for section in (
            "## Current platform baseline",
            "## Scope controls",
            "## Proposed operator interface",
            "## Operator journeys after W10",
            "## Planned commits and effort signals",
            "## Verification strategy",
            "## PR-ready definition",
        ):
            self.assertIn(section, w10)
        for command in (
            "platform-member-bootstrap-owner",
            "platform-member-status",
            "platform-member-add",
            "platform-member-suspend",
            "platform-member-reactivate",
            "platform-member-remove",
            "IDENTITY_DELIVERY=<none|optional|required>",
        ):
            self.assertIn(command, w10)
        for boundary in (
            "application users, principals, account links",
            "ADR-016 operator-state recovery",
            "W11 Accepted Source staging operation",
            "Candidate Source staging qualification",
            "seven coherent commits",
            "122k-196k working tokens",
            "55-85 unique changed paths",
            "7-12 focused implementation days",
        ):
            self.assertIn(boundary, w10)

    def test_incremental_delivery_sequence_keeps_later_slices_separate(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        normalized_index = " ".join(index.split())
        normalized_prompt = " ".join(prompt.split())

        for work_package in range(1, 13):
            self.assertIn(f"AP-M9-W{work_package}", index)
        self.assertIn("Each work package is one bounded branch and pull request", normalized_index)
        self.assertLess(index.index("AP-M9-W1"), index.index("AP-M9-W12"))
        self.assertIn("AP-M9-W10", normalized_prompt)
        self.assertIn("first Accepted Source staging operation", normalized_prompt)
        self.assertIn("Do not mutate production, `apps.comfforts.com`, Finance Assistant, or any real application", normalized_prompt)

    def test_ap_m9_handoff_assigns_candidate_accepted_and_production_work_once(
        self,
    ) -> None:
        requirements = (PROJECT_ROOT / "docs/01_product_requirements.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        m9 = (
            PROJECT_ROOT / "docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md"
        ).read_text(encoding="utf-8")
        w10 = (
            PROJECT_ROOT / "docs/plans/ap_m9/w10_platform_member_directory.md"
        ).read_text(encoding="utf-8")
        recovery = (
            PROJECT_ROOT
            / "docs/adr/016-recover-operator-working-state-without-fabricated-history.md"
        ).read_text(encoding="utf-8")

        normalized_requirements = " ".join(requirements.split())
        normalized_evaluation = " ".join(evaluation.split())
        normalized_m9 = " ".join(m9.split())
        normalized_recovery = " ".join(recovery.split())

        self.assertIn(
            "ADR-015 implementation and Candidate Source qualification remain AP-M9-W10 work",
            normalized_requirements,
        )
        self.assertIn(
            "Accepted Source qualification remains AP-M9-W11 work",
            normalized_requirements,
        )
        self.assertIn(
            "W10 must repeat the applicable staging journey from Candidate Source",
            normalized_evaluation,
        )
        self.assertIn(
            "After W10 merges, AP-M9-W11 repeats deployment and qualification from Accepted Source",
            normalized_evaluation,
        )
        self.assertIn("AP-M9-W1 through AP-M9-W12", normalized_m9)
        self.assertNotIn("AP-M9-W1 through W10 are repository branches", m9)
        self.assertNotIn("operation-specific service-account impersonation", m9)
        self.assertIn("no operation-identity fleet", normalized_m9)
        self.assertIn("seven planned commit outcomes", w10)
        self.assertIn("ADR-016 operator-state recovery", w10)
        self.assertIn("Status: Proposed; still in discussion", recovery)
        self.assertIn(
            "AP-M9-W10 continues to exclude operator-state recovery",
            normalized_recovery,
        )

    def test_fixture_design_selects_a_bounded_in_process_profile(self) -> None:
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )
        normalized_threat_model = " ".join(threat_model.split())

        for boundary in (
            "handle(request) -> response",
            "It opens no listening socket",
            "fixture-in-process-v1",
            "fixture-public",
            "fixture-authenticated",
            "fixture-restricted",
            "adds no external registration endpoint",
            "or database",
            "No Fixture (`F`) evidence exists",
        ):
            self.assertIn(boundary, design)

        for threat_control in (
            "at most 32 headers",
            "65,536 UTF-8 bytes",
            "HMAC-SHA-256",
            "60 seconds",
            "256-entry fail-closed replay store",
            "There is no registration API or database",
            "produces no Fixture (`F`) evidence",
        ):
            self.assertIn(threat_control, normalized_threat_model)

        self.assertIn("Finance Assistant code", design)
        self.assertIn("network direct-bypass control", threat_model)

    def test_ap_m5_through_ap_m7_authorities_have_complete_unique_identifiers(self) -> None:
        plan = (PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^#### (AP-M5-W\d+) ·", plan, re.MULTILINE)
        planning_gates = re.findall(
            r"^### (AP-EVAL-M5-\d{2}) ·", evaluation, re.MULTILINE
        )
        runtime_packages = re.findall(r"^#### (AP-M6-W\d+) ·", plan, re.MULTILINE)
        runtime_gates = re.findall(
            r"^#### (AP-EVAL-M6-\d{2}) ·", evaluation, re.MULTILINE
        )
        infrastructure_packages = re.findall(
            r"^#### (AP-M7-W\d+) ·", plan, re.MULTILINE
        )
        infrastructure_gates = re.findall(
            r"^#### (AP-EVAL-M7-\d{2}) ·", evaluation, re.MULTILINE
        )
        live_gates = re.findall(
            r"^#### (AP-EVAL-M9-\d{2}) ·", evaluation, re.MULTILINE
        )
        active_lifecycle_boundaries = re.findall(
            r"^## (AP-EVAL-M9) ·", evaluation, re.MULTILINE
        )

        self.assertEqual(
            work_packages,
            [f"AP-M5-W{index}" for index in range(1, 10)],
        )
        self.assertEqual(
            planning_gates,
            [f"AP-EVAL-M5-{index:02d}" for index in range(1, 10)],
        )
        self.assertEqual(
            runtime_packages,
            [f"AP-M6-W{index}" for index in range(1, 12)],
        )
        self.assertEqual(
            runtime_gates,
            [f"AP-EVAL-M6-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(
            infrastructure_packages,
            [f"AP-M7-W{index}" for index in range(1, 12)],
        )
        self.assertEqual(
            infrastructure_gates,
            [f"AP-EVAL-M7-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(
            live_gates,
            [f"AP-EVAL-M9-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(
            active_lifecycle_boundaries,
            ["AP-EVAL-M9"],
        )
        for identifiers in (
            work_packages,
            planning_gates,
            runtime_packages,
            runtime_gates,
            infrastructure_packages,
            infrastructure_gates,
            live_gates,
        ):
            self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_ap_m8_history_and_ap_m9_authority_have_unique_identifiers(self) -> None:
        plan = (PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md").read_text(
            encoding="utf-8"
        )
        m9 = (
            PROJECT_ROOT / "docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md"
        ).read_text(encoding="utf-8")
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^#### (AP-M8-W\d+) ·", plan, re.MULTILINE)
        lifecycle_packages = re.findall(
            r"^### (AP-M9-W\d+) ·", m9, re.MULTILINE
        )
        lifecycle_gates = re.findall(
            r"^#### (AP-EVAL-M9-\d{2}) ·", evaluation, re.MULTILINE
        )

        self.assertEqual(
            work_packages,
            ["AP-M8-W1", "AP-M8-W2"],
        )
        self.assertEqual(
            lifecycle_packages,
            [f"AP-M9-W{index}" for index in range(1, 13)],
        )
        self.assertEqual(len(work_packages), len(set(work_packages)))
        self.assertEqual(
            lifecycle_gates,
            [f"AP-EVAL-M9-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(len(lifecycle_packages), len(set(lifecycle_packages)))
        self.assertEqual(len(lifecycle_gates), len(set(lifecycle_gates)))
        self.assertIn(
            "AP-M8-W3 through AP-M8-W12 were superseded without execution",
            plan,
        )
        self.assertIn(
            "Historical standalone Live-qualification gate — withdrawn before implementation",
            evaluation,
        )

    def test_ap_m8_operator_authorities_are_separate_and_exact(self) -> None:
        runbook = (
            PROJECT_ROOT / "docs/runbooks/qualification_deployment.md"
        ).read_text(encoding="utf-8")

        environment_section = runbook.split("### Environment classes", 1)[1].split(
            "### Executable workflow boundary", 1
        )[0]
        environment_classes = re.findall(
            r"^\| (Plan|Apply|DNS|Evidence|Recovery) \|",
            environment_section,
            re.MULTILINE,
        )
        self.assertEqual(
            environment_classes,
            ["Plan", "Apply", "DNS", "Evidence", "Recovery"],
        )

        identity_section = runbook.split(
            "### One identity per root or publication operation", 1
        )[1].split("### Bootstrap exception", 1)[0]
        operation_names = re.findall(
            r"^\| (Plan|Apply|Artifact publish|Generation publish|"
            r"Qualification DNS|Root readback|Evidence finalize|Rollback|"
            r"Force-unlock|Destroy) \|",
            identity_section,
            re.MULTILINE,
        )
        self.assertEqual(
            operation_names,
            [
                "Plan",
                "Apply",
                "Artifact publish",
                "Generation publish",
                "Qualification DNS",
                "Root readback",
                "Evidence finalize",
                "Rollback",
                "Force-unlock",
                "Destroy",
            ],
        )
        normalized_identity = " ".join(identity_section.split())
        for boundary in (
            "No operation identity spans roots or operations",
            "Workload identities receive no owner, editor, IAM administrator",
            "They cannot alter the Workload Identity Pool/provider, their own service account",
            "no service-account key may exist",
            "Import, state push, backend migration, federation administration",
            "cannot list another evaluation prefix, overwrite or delete a record",
        ):
            self.assertIn(boundary, normalized_identity)

    def test_ap_m8_state_and_deployment_order_are_fixed(self) -> None:
        runbook = (
            PROJECT_ROOT / "docs/runbooks/qualification_deployment.md"
        ).read_text(encoding="utf-8")

        state_section = runbook.split("### Fixed root and prefix map", 1)[1].split(
            "### Operator prerequisites", 1
        )[0]
        for root_mapping in (
            "| `bootstrap` | Platform State backend resources | "
            "Platform-state bucket | `bootstrap` |",
            "| `platform` | Platform State | Platform-state bucket | `platform` |",
            "| `fixture-public` | Fixture Application State | Fixture-public state "
            "bucket | `fixtures/fixture-public` |",
            "| `fixture-authenticated` | Fixture Application State | "
            "Fixture-authenticated state bucket | `fixtures/fixture-authenticated` |",
            "| `fixture-restricted` | Fixture Application State | "
            "Fixture-restricted state bucket | `fixtures/fixture-restricted` |",
        ):
            self.assertIn(root_mapping, state_section)
        self.assertIn(
            "Four buckets hold five independent root lineages", state_section
        )
        self.assertIn("workspaces other than `default` are prohibited", state_section)

        sequence_section = runbook.split(
            "## AP-M8-W8 and AP-M8-W9 deployment sequence", 1
        )[1].split("## AP-M8-W10 qualification DNS and TLS checkpoint", 1)[0]
        operations = re.findall(
            r"^\| [1-8] \| ([^|]+?) \|", sequence_section, re.MULTILINE
        )
        self.assertEqual(
            operations,
            [
                "Apply Platform `foundation`",
                "Build and publish images",
                "Accept platform reference",
                "Apply `fixture-public`",
                "Apply `fixture-authenticated`",
                "Apply `fixture-restricted`",
                "Compile and publish generation",
                "Plan and apply Platform `candidate`",
            ],
        )
        normalized_sequence = " ".join(sequence_section.split())
        for boundary in (
            "Fixture roots deploy sequentially for the initial environment",
            "workflow never reads another root's backend or uses `terraform_remote_state`",
            "dark initial candidate",
            "not zero-percent Cloud Run traffic, activation, or Live qualification",
        ):
            self.assertIn(boundary, normalized_sequence)

    def test_ap_eval_m8_evidence_is_closed_private_and_non_live(self) -> None:
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join(evaluation.split())
        ap_m8 = evaluation.split(
            "### Historical AP-EVAL-M8 · Manifest-driven qualification-deployment gate — superseded",
            1,
        )[1].split(
            "### Historical standalone Live-qualification gate — withdrawn before implementation",
            1,
        )[0]

        for bundle_entry in (
            "manifest.v1.json",
            "operations/<sequence>-<operation-id>.v1.json",
            "readback/<target-id>.v1.json",
            "verdict.v1.json",
            "checksums.sha256",
        ):
            self.assertIn(bundle_entry, ap_m8)
        for verifier_argument in (
            "--bundle <private-read-only-bundle-directory>",
            "--manifest-digest sha256:<64-lowercase-hex>",
            "--source-revision <40-lowercase-hex>",
            "--verdict-output <new-ephemeral-verdict-file>",
        ):
            self.assertIn(verifier_argument, ap_m8)
        for evidence_boundary in (
            "deployment/readback evidence, not a fifth evidence class",
            "It does not invoke an application route or status endpoint",
            "Uniform access, public-access prevention, owner-only read",
            "covers neither itself nor the later verdict",
            "avoiding a self-referential hash",
            "All ten AP-EVAL-M8 gates are mandatory",
            "The mandatory skip count must be zero",
            "dependent gate that cannot safely run is `blocked`",
            "AP-M9, cross-project, Finance, and Adoption behaviors are recorded as `unavailable`",
            "AP-M8-W2's local schema and validator create no workflow, identity, credential, bucket object, provider action",
        ):
            self.assertIn(evidence_boundary, normalized)

    def test_ap_m8_authority_branch_contains_no_operational_capability(self) -> None:
        reserved_paths = (
            "edge/production.py",
            "fixtures/runtime.py",
            "infrastructure/deployment",
            "registrations",
            "artifacts",
        )
        for relative_path in reserved_paths:
            self.assertFalse(
                (PROJECT_ROOT / relative_path).exists(),
                f"AP-M8-W1 must not implement reserved capability: {relative_path}",
            )

        workflow_root = PROJECT_ROOT / ".github/workflows"
        self.assertEqual(
            sorted(item.name for item in workflow_root.iterdir() if item.is_file()),
            ["check.yml"],
        )
        repository_files = tuple(_repository_files())
        self.assertFalse(any(path.name.endswith(".tfvars") for path in repository_files))
        self.assertFalse(any(path.name.endswith(".tfstate") for path in repository_files))
        self.assertFalse(any(path.name.endswith(".tfplan") for path in repository_files))

    def test_ap_m9_w2_removes_the_retired_manifest_implementation(self) -> None:
        config_root = PROJECT_ROOT / "infrastructure/config"
        validation = (
            config_root / "validation.py"
        ).read_text(encoding="utf-8")
        package = (config_root / "__init__.py").read_text(
            encoding="utf-8"
        )

        for removed_path in (
            config_root / "schemas/operator-input-manifest.v1.schema.json",
            config_root / "examples/operator-input-manifest.synthetic.v1.json",
            config_root / "operator_manifest.py",
        ):
            self.assertFalse(removed_path.exists())
        for retired_interface in (
            "operator-input-manifest",
            "OperatorManifestChainResult",
            "load_operator_manifest_chain",
            "validate_operator_manifest_chain",
        ):
            self.assertNotIn(retired_interface, package)
            self.assertNotIn(retired_interface, validation)

        for later_path in (
            "infrastructure/deployment",
            "edge/production.py",
            "fixtures/runtime.py",
            "registrations/qualification",
        ):
            self.assertFalse(
                (PROJECT_ROOT / later_path).exists(),
                f"AP-M9-W2 must not create later capability: {later_path}",
            )
        self.assertEqual(
            sorted(
                path.name
                for path in (PROJECT_ROOT / ".github/workflows").iterdir()
                if path.is_file()
            ),
            ["check.yml"],
        )

    def test_ap_m7_authority_is_exact_static_and_non_operational(self) -> None:
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        plan = (PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )
        normalized_design = " ".join(design.split())
        normalized_plan = " ".join(plan.split())
        normalized_evaluation = " ".join(evaluation.split())
        normalized_threat_model = " ".join(threat_model.split())

        for selected_value in (
            "Terraform 1.17.2",
            "`hashicorp/google` 8.11.0",
            "bootstrap(backend_configuration) -> backend_reference_set",
            "fixture_application(fixture_configuration, platform_reference)",
            "platform(platform_configuration, attachment_references, registration_generation)",
            "`terraform_remote_state`, backend-object reads",
            "inert `*.yml.tmpl` files",
            "explicit `command = plan` runs and mocked providers",
        ):
            self.assertIn(selected_value, normalized_design)

        for authority_boundary in (
            "AP-M7-W1 · Infrastructure implementation authority",
            "AP-M7-W11 · Infrastructure record and AP-M8 handoff",
            "The unresolved operator values are globally unique state, configuration, log, and evidence bucket names",
            "Owner acceptance of its exact profile is required before AP-M7-W2",
            "AP-M7 does not initialize or contact a backend",
        ):
            self.assertIn(authority_boundary, normalized_plan)

        for gate_boundary in (
            "make terraform-setup make check",
            "uses `TF_CLI_CONFIG_FILE` to permit only the pre-populated filesystem mirror",
            "terraform init -backend=false -lockfile=readonly",
            "AP-EVAL-M7-10 · Complete regression, truthful status, and handoff",
            "Static configuration and mocked plans are implementation evidence only",
        ):
            self.assertIn(gate_boundary, normalized_evaluation)

        self.assertIn("AP-M7 infrastructure-configuration controls", threat_model)
        self.assertIn("Only the existing read-only check workflow is executable", normalized_threat_model)
        self.assertIn("can supply neither Live nor Adoption evidence", normalized_threat_model)

    def test_ap_m6_resolves_runtime_inputs_and_separates_later_delivery(self) -> None:
        plan = (PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md").read_text(
            encoding="utf-8"
        )
        m9 = (
            PROJECT_ROOT / "docs/plans/ap_m9/000-m9_interactive_platform_lifecycle.md"
        ).read_text(encoding="utf-8")
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        routed_plans = f"{plan}\n{m9}"
        normalized_plan = " ".join(plan.split())
        normalized_evaluation = " ".join(evaluation.split())

        for later_slice in (
            "AP-M6 · Networked provider runtime implementation",
            "AP-M7 · Terraform and workflow implementation",
            "Historical AP-M8 · Manifest-driven qualification deployment — superseded",
            "AP-M9 · Operator-driven environment lifecycle",
            "Later Application Adoption",
        ):
            self.assertIn(later_slice, routed_plans)

        for planning_boundary in (
            "AP-M5 produces no Contract, Fixture, Live, or Adoption evidence",
            "Each item below requires a new owner-approved branch",
            "no later slice inherits mutation authority merely because AP-M5 is accepted",
            "Python 3.12-or-newer Starlette/Uvicorn runtime",
            "exact header, body, timeout, concurrency, stream, rate, and rejection behavior",
            "Owner acceptance of its exact values is required before AP-M6-W2",
            "repository identity is fixed as `comfforts/apps-platform`",
            "Globally unique state, configuration, log, and evidence bucket names",
            "These are unavailable inputs, not permission to query a provider",
        ):
            self.assertIn(planning_boundary, normalized_plan)

        for evaluation_boundary in (
            "internally consistent planning authority for the initial GCP qualification topology",
            "It proves no provider behavior and creates no new evidence class",
            "The default `make check` remains separate and credential-free",
            "A deployment result cannot qualify routing, identity, direct-origin denial",
            "leave Finance Assistant and every Application Adoption unchanged and unavailable",
        ):
            self.assertIn(evaluation_boundary, normalized_evaluation)

    def test_ap_m6_runtime_profile_is_exact_and_non_operational(self) -> None:
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )
        normalized_design = " ".join(design.split())
        normalized_evaluation = " ".join(evaluation.split())
        normalized_threat_model = " ".join(threat_model.split())

        for selected_value in (
            "create_app(runtime_configuration, adapters) -> ASGI application",
            "Starlette as the ASGI framework",
            "Uvicorn as the server",
            "complete transitive resolution is committed in `uv.lock`",
            "at most 64 request headers",
            "at most 25 MiB per request body",
            "at most 100 MiB per streamed HTTP response",
            "300-second non-streaming request timeout",
            "55-minute absolute streaming lifetime",
            "at most 20 active requests and 10 streaming connections",
            "120 request starts per minute per trusted client key",
            "not a distributed rate-limit or WAF claim",
        ):
            self.assertIn(selected_value, normalized_design)

        for evaluation_boundary in (
            "must fail if a connection is attempted to any non-loopback address",
            "Dependency synchronization is a separate setup action",
            "AP-EVAL-M6 performs no authenticated provider",
            "production adapters are locally tested implementations",
        ):
            self.assertIn(evaluation_boundary, normalized_evaluation)

        self.assertIn(
            "AP-EVAL-M6 covers the exact network-runtime profile",
            normalized_threat_model,
        )
        self.assertIn(
            "AP-M6-W8 implements the remaining request, body, response, stream, "
            "message, duration, concurrency, and process-local rate limits",
            normalized_threat_model,
        )

    def test_ap_m7_w9_workflow_template_paths_are_bounded(
        self,
    ) -> None:
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(
            encoding="utf-8"
        )

        reserved_paths = (
            "registrations",
            "artifacts",
        )
        for relative_path in reserved_paths:
            self.assertFalse(
                (PROJECT_ROOT / relative_path).exists(),
                f"AP-M7-W9 must not create later implementation path: {relative_path}",
            )

        workflow_root = PROJECT_ROOT / "infrastructure/workflows"
        self.assertEqual(
            sorted(path.name for path in workflow_root.iterdir()),
            [
                "README.md",
                "advisory-plan.yml.tmpl",
                "destroy.yml.tmpl",
                "exact-main-apply.yml.tmpl",
                "force-unlock.yml.tmpl",
                "rollback.yml.tmpl",
            ],
        )

        config_root = PROJECT_ROOT / "infrastructure/config"
        self.assertTrue((config_root / "README.md").is_file())
        self.assertTrue((config_root / "validation.py").is_file())
        self.assertEqual(len(tuple((config_root / "schemas").glob("*.json"))), 5)
        self.assertEqual(len(tuple((config_root / "examples").glob("*.json"))), 16)
        module_root = PROJECT_ROOT / "infrastructure/terraform/modules"
        self.assertEqual(
            sorted(path.name for path in module_root.iterdir() if path.is_dir()),
            [
                "fixture-application",
                "platform-controls",
                "platform-foundation",
                "shared-edge",
                "state-bucket",
            ],
        )

        expected_roots = (
            "infrastructure/terraform/bootstrap",
            "infrastructure/terraform/platform",
            "infrastructure/terraform/fixtures/fixture-public",
            "infrastructure/terraform/fixtures/fixture-authenticated",
            "infrastructure/terraform/fixtures/fixture-restricted",
        )
        for relative_root in expected_roots:
            root = PROJECT_ROOT / relative_root
            self.assertTrue((root / "versions.tf").is_file())
            self.assertTrue((root / ".terraform.lock.hcl").is_file())

        self.assertTrue((PROJECT_ROOT / "edge/__init__.py").is_file())
        self.assertTrue((PROJECT_ROOT / "edge/_generation.py").is_file())
        self.assertTrue((PROJECT_ROOT / "edge/_routing.py").is_file())
        self.assertTrue((PROJECT_ROOT / "edge/_runtime.py").is_file())

        for reserved_reference in (
            "`edge/`",
            "`registrations/`",
            "`infrastructure/config/`",
            "`infrastructure/terraform/bootstrap/`",
            "`infrastructure/terraform/platform/`",
            "`infrastructure/terraform/fixtures/*/`",
            "`infrastructure/workflows/`",
            "`artifacts/`",
            "`docs/`",
            "Do not create a reserved path merely because this document names it",
        ):
            self.assertIn(reserved_reference, layout)

        terraform_files = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in _repository_files()
            if path.name.endswith((".tf", ".tf.json"))
        )
        self.assertEqual(
            terraform_files,
            sorted(
                [f"{root}/versions.tf" for root in expected_roots]
                + [
                    "infrastructure/terraform/bootstrap/main.tf",
                    "infrastructure/terraform/bootstrap/outputs.tf",
                    "infrastructure/terraform/bootstrap/provider.tf",
                    "infrastructure/terraform/bootstrap/variables.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/backend.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/main.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/outputs.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/provider.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/variables.tf",
                    "infrastructure/terraform/fixtures/fixture-public/backend.tf",
                    "infrastructure/terraform/fixtures/fixture-public/main.tf",
                    "infrastructure/terraform/fixtures/fixture-public/outputs.tf",
                    "infrastructure/terraform/fixtures/fixture-public/provider.tf",
                    "infrastructure/terraform/fixtures/fixture-public/variables.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/backend.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/main.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/outputs.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/provider.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/variables.tf",
                    "infrastructure/terraform/modules/fixture-application/main.tf",
                    "infrastructure/terraform/modules/fixture-application/outputs.tf",
                    "infrastructure/terraform/modules/fixture-application/variables.tf",
                    "infrastructure/terraform/modules/platform-foundation/main.tf",
                    "infrastructure/terraform/modules/platform-foundation/outputs.tf",
                    "infrastructure/terraform/modules/platform-foundation/variables.tf",
                    "infrastructure/terraform/modules/platform-controls/main.tf",
                    "infrastructure/terraform/modules/platform-controls/outputs.tf",
                    "infrastructure/terraform/modules/platform-controls/variables.tf",
                    "infrastructure/terraform/modules/shared-edge/main.tf",
                    "infrastructure/terraform/modules/shared-edge/outputs.tf",
                    "infrastructure/terraform/modules/shared-edge/variables.tf",
                    "infrastructure/terraform/modules/state-bucket/main.tf",
                    "infrastructure/terraform/modules/state-bucket/outputs.tf",
                    "infrastructure/terraform/modules/state-bucket/variables.tf",
                    "infrastructure/terraform/platform/backend.tf",
                    "infrastructure/terraform/platform/main.tf",
                    "infrastructure/terraform/platform/outputs.tf",
                    "infrastructure/terraform/platform/provider.tf",
                    "infrastructure/terraform/platform/variables.tf",
                ]
            ),
        )
        prohibited_files = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in _repository_files()
            if path.name.endswith((".tfvars", ".tfstate", ".tfplan"))
        )
        self.assertEqual(prohibited_files, [])
        self.assertTrue((PROJECT_ROOT / ".github/workflows/check.yml").is_file())

    def test_ap_m7_w9_default_gate_has_no_live_operator_command(self) -> None:
        makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        normalized_makefile = " ".join(makefile.split())

        for prohibited_command in (
            "terraform apply",
            "terraform plan",
            "terraform init",
            "gcloud",
            "gsutil",
            " dig ",
            " curl ",
            "docker",
            "kubectl",
            "openssl",
        ):
            self.assertNotIn(prohibited_command, f" {normalized_makefile} ")

        self.assertIn(
            "check: governance-check contract-check fixture-check runtime-check terraform-check",
            makefile,
        )
        self.assertIn("terraform-setup:", makefile)
        self.assertIn("terraform-check:", makefile)
        self.assertIn("tests.test_workflow_templates", makefile)
        self.assertIn("tests.test_terraform_qualification", makefile)
        self.assertIn("credential-free, deterministic, network-free", evaluation)

    def test_ap_m4_authorities_have_complete_unique_identifiers(self) -> None:
        plan = (PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^#### (AP-M4-W\d+) ·", plan, re.MULTILINE)
        evaluation_gates = re.findall(
            r"^### (AP-EVAL-M4-\d{2}) ·", evaluation, re.MULTILINE
        )

        self.assertEqual(
            work_packages, [f"AP-M4-W{index}" for index in range(1, 8)]
        )
        self.assertEqual(
            evaluation_gates,
            [f"AP-EVAL-M4-{index:02d}" for index in range(1, 10)],
        )
        self.assertEqual(len(work_packages), len(set(work_packages)))
        self.assertEqual(len(evaluation_gates), len(set(evaluation_gates)))

    def test_ap_m4_authority_is_fixture_only(self) -> None:
        plan = (PROJECT_ROOT / "docs/plans/000-origin-implementation-plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        normalized_plan = " ".join(plan.split())
        normalized_evaluation = " ".join(evaluation.split())

        for boundary in (
            "It does not turn the harness into a network server",
            "external registration endpoint, or database",
            "AP-M4 produces Fixture (`F`) evidence only",
            "Each work package is a separate small commit",
            "Finance Assistant requirements, code, infrastructure",
        ):
            self.assertIn(boundary, normalized_plan)

        for gate_boundary in (
            "AP-EVAL-M3 continues to own Contract (`C`) evidence",
            "Live (`L`) and Adoption (`A`) evidence remain unavailable",
            "no listening socket",
            "There is no registration API or database",
            "AP-EVAL-M4 passes only when all nine gates",
        ):
            self.assertIn(gate_boundary, normalized_evaluation)

    def test_ap_m9_design_supersedes_the_unexecuted_manifest_path(self) -> None:
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        threat_model = (PROJECT_ROOT / "docs/06_threat_model.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            design.count("### AP-M9 operator-driven environment lifecycle profile"),
            1,
        )
        self.assertIn(
            "Historical AP-M8 protected-source and federated-identity profile — superseded",
            design,
        )
        for operation in (
            "prepare",
            "deploy",
            "status",
            "outputs",
            "register",
            "detach",
            "retire",
            "qualify",
            "destroy",
        ):
            self.assertIn(operation, design)

        self.assertIn("OWNERSHIP_TRANSFER_REQUIRED", design)
        self.assertIn("AP-M9 interactive lifecycle controls", threat_model)
        self.assertIn("operator-attested", threat_model)
        self.assertIn("No current result proves", threat_model)

    def test_ap_m9_w9_status_and_w10_member_handoff_are_bounded(self) -> None:
        overview = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        docs_index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        runbook = (
            PROJECT_ROOT / "docs/runbooks/environment_lifecycle.md"
        ).read_text(encoding="utf-8")
        normalized_runbook = " ".join(runbook.split())
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(
            encoding="utf-8"
        )
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(
            encoding="utf-8"
        )
        normalized_prompt = " ".join(prompt.split())

        for document in (docs_index, layout):
            self.assertIn("AP-M9-W9", document)
            self.assertIn("implemented", document.lower())
        self.assertIn(
            "AP-M9-W9 is implemented and candidate-qualified",
            overview,
        )
        self.assertIn("AP-M9-W10 must still implement and", overview)
        self.assertIn("diagnostic pre-merge evidence", docs_index)
        self.assertIn("platform-prepare", overview)
        self.assertIn("platform-cancel", overview)
        self.assertIn("platform-status", overview)
        self.assertIn("platform-deploy", overview)
        self.assertNotIn("W9_LIVE_QUALIFICATION_AUTHORITY_REQUIRED", runbook)
        self.assertNotIn("W9_DESTRUCTION_AUTHORITY_REQUIRED", runbook)
        self.assertIn("never issues a blind root destroy", normalized_runbook)
        self.assertIn("one isolated staging or production deployment", normalized_runbook)
        self.assertIn("## Normal staging lifecycle", runbook)
        self.assertIn("## Resume an interrupted operation", runbook)
        self.assertIn("make platform-cancel", runbook)
        self.assertIn("does not run Terraform", normalized_runbook)
        self.assertIn("## Destroy a platform environment", runbook)
        self.assertIn("OWNERSHIP_TRANSFER_REQUIRED", runbook)
        for governance_identifier in (
            "AP-M",
            "AP-PR-",
            "AP-QR-",
            "ADR-",
            "AP-TM-",
            "AP-EVAL-",
        ):
            self.assertNotIn(governance_identifier, runbook)
        self.assertIn("`infrastructure/operator/`", layout)

        for required in (
            "AP-M9-W10",
            "AP-EVAL-M9-09",
            "Platform Member Directory",
            "explicit Identity Delivery",
            "platform-member-bootstrap-owner",
            "suspend, reactivate, and remove",
            "first Accepted Source staging operation",
            "Do not mutate production, `apps.comfforts.com`, Finance Assistant, or any real application",
        ):
            self.assertIn(required, normalized_prompt)
        self.assertNotIn("AP-M9-W8 qualification and safe destruction handoff", prompt)


if __name__ == "__main__":
    unittest.main()
