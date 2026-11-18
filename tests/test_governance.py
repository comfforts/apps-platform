"""Standalone App Platform authority-foundation checks."""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
            "docs/03_system_design.md",
            "docs/04_implementation_plan.md",
            "docs/05_evaluation_strategy.md",
            "docs/06_threat_model.md",
            "docs/README.md",
            "docs/repository_extraction_handoff.md",
            "docs/repository_layout.md",
            "docs/runbooks/README.md",
            "docs/runbooks/repository_extraction.md",
            "contracts/README.md",
            "contracts/validation.py",
            "contracts/test-vectors/manifest.v1.json",
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

        self.assertIn("docs/README.md", instructions)
        self.assertIn("GLOSSARY.md", instructions)
        self.assertIn("docs/01_product_requirements.md", instructions)
        self.assertIn("docs/02_architecture_decision_records.md", instructions)
        self.assertIn("docs/03_system_design.md", instructions)
        self.assertIn("docs/06_threat_model.md", instructions)
        self.assertIn("contracts/README.md", instructions)
        self.assertIn("docs/repository_layout.md", instructions)
        self.assertIn("Run `make check` from the dedicated repository root", instructions)
        self.assertNotIn("make -C apps-platform check", instructions)
        self.assertIn("one bounded slice per pull request", instructions)
        self.assertIn("leave each change uncommitted until approval", instructions)
        self.assertIn("Merge it before starting the next documented slice", instructions)
        self.assertIn(
            "AP-M5 selects infrastructure and Live-qualification planning boundaries only",
            instructions,
        )
        self.assertIn(
            "AP-M6 authorizes only repository implementation of the networked Shared Edge",
            instructions,
        )
        self.assertIn(
            "AP-M7 authorizes only reviewed Terraform configuration",
            instructions,
        )

    def test_documentation_truthfully_records_planning_and_evidence_status(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")
        overview = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        normalized_index = " ".join(index.split())
        normalized_layout = " ".join(layout.split())
        normalized_overview = " ".join(overview.split())

        self.assertIn(
            "AP-M8-W1 qualification-deployment authority proposal complete",
            normalized_index,
        )
        self.assertIn("Contract (`C`) evidence", normalized_index)
        self.assertIn("Fixture (`F`) evidence", normalized_index)
        self.assertIn(
            "Live (`L`) and Adoption (`A`) evidence remain unavailable",
            normalized_index,
        )
        self.assertIn("AP-M6", overview)
        self.assertIn("AP-M4 remains Fixture-qualified", normalized_overview)
        self.assertIn(
            "bounded HTTP, SSE, and WebSocket proxying",
            normalized_overview,
        )
        self.assertIn(
            "AP-M6 and AP-M7 supply repository implementation evidence only",
            overview,
        )
        self.assertIn("complete credential-free `make check` gate passes", overview)
        self.assertIn("AP-M7-W7 implements one immutable", normalized_index)
        self.assertIn("AP-M7-W7 implements the deep Shared Edge module", normalized_overview)
        self.assertIn("AP-M7-W8 implements a regional seven-day log bucket", normalized_index)
        self.assertIn("AP-M7-W8 adds a regional seven-day log bucket", normalized_overview)
        self.assertIn("AP-M7-W9 implements separate inert advisory-plan", normalized_index)
        self.assertIn("AP-M7-W9 adds parseable, non-executable", normalized_overview)
        self.assertIn("AP-M7-W10 binds AP-EVAL-M7-01", normalized_index)
        self.assertIn("AP-M7-W11 reconciles this static status", normalized_overview)
        self.assertIn("AP-M8-W1 authority proposal complete", normalized_layout)
        self.assertIn(
            "owner acceptance, AP-M8-W2, and every operator action pending",
            normalized_index,
        )
        self.assertIn(
            "AP-M8-W2 may begin only after this pull request merges",
            normalized_overview,
        )
        self.assertIn("planning consistency only", normalized_index)
        self.assertIn("Integration draft", index)
        self.assertIn(
            "authoritative canonical dedicated-root layout",
            normalized_layout,
        )
        self.assertIn(
            "all five repository-extraction checkpoints complete",
            normalized_layout,
        )
        self.assertIn("`contracts/`", layout)
        self.assertIn("`fixtures/`", layout)
        self.assertIn("Version 1 schemas", layout)
        self.assertIn("three independent Fixture Applications", layout)
        self.assertIn("history-preserving subtree extraction", normalized_layout)
        self.assertIn("run `make check` from the dedicated repository root", layout)

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
        self.assertIn(
            "[Repository extraction runbook](runbooks/repository_extraction.md)",
            index,
        )
        self.assertIn(
            "[Repository extraction handoff](repository_extraction_handoff.md)",
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
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
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
            *(f"AP-PR-{index:03d}" for index in range(1, 10)),
            *(f"AP-QR-{index:03d}" for index in range(1, 7)),
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
            "Integration Draft",
            "Finance Assistant migration",
            "no platform capability is implemented",
        ):
            self.assertIn(boundary, requirements)

    def test_architecture_decisions_are_unique_and_trace_requirements(self) -> None:
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )
        observed = re.findall(r"^## (ADR-\d{3}) ·", decisions, re.MULTILINE)

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
            ],
        )
        self.assertEqual(decisions.count("Status: Accepted"), 9)
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
            "Each Fixture Application uses a separate state bucket",
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
            "content-addressed, immutable compiled configuration object",
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
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )

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
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )
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
        decisions = (PROJECT_ROOT / "docs/02_architecture_decision_records.md").read_text(
            encoding="utf-8"
        )
        glossary = (PROJECT_ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
        layout = (PROJECT_ROOT / "docs/repository_layout.md").read_text(encoding="utf-8")

        for boundary in (
            "before any real application may be adopted",
            "remain outside\nPlatform State",
            "no Finance Assistant code",
            "is not platform acceptance evidence",
            "A cutover must leave each resource with one active state owner",
            "Finance Assistant-owned slice and evidence",
        ):
            self.assertIn(boundary, decisions)
        self.assertIn("## Application Adoption", glossary)
        self.assertIn("app-owned test state", layout)

    def test_ap_m8_handoff_loads_authority_without_granting_operations(
        self,
    ) -> None:
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        prompt_index = (PROJECT_ROOT / "prompts/README.md").read_text(encoding="utf-8")
        normalized_prompt = " ".join(prompt.split())

        for authority in (
            "AGENTS.md",
            "docs/README.md",
            "GLOSSARY.md",
            "docs/01_product_requirements.md",
            "docs/02_architecture_decision_records.md",
            "docs/03_system_design.md",
            "docs/04_implementation_plan.md",
            "docs/05_evaluation_strategy.md",
            "docs/06_threat_model.md",
            "docs/repository_layout.md",
            "contracts/README.md",
            "fixtures/registrations/README.md",
        ):
            self.assertIn(authority, prompt)
        for boundary in (
            "after the AP-M8 authority pull request has merged to `main`",
            "owner explicitly accepts the complete AP-M8-W1 authority and requests AP-M8-W2",
            "implement AP-M8-W2 only as a bounded, non-secret operator-input manifest",
            "A missing value stops AP-M8-W2",
            "Do not begin AP-M8-W3 repository or environment settings",
            "Do not change repository settings",
            "Do not query a provider, copy Finance Assistant values",
            "Every later external action retains its own explicit owner checkpoint",
            "credential-free, deterministic, offline, extraction-safe, and non-mutating",
        ):
            self.assertIn(boundary, normalized_prompt)
        self.assertNotIn("### AP-PR-", prompt)
        self.assertNotIn("## ADR-", prompt)
        self.assertNotIn("terraform apply", prompt)
        self.assertIn(
            "[AP-M8 implementation handoff](starting_prompt.md)",
            prompt_index,
        )

    def test_incremental_delivery_sequence_keeps_later_slices_separate(self) -> None:
        index = (PROJECT_ROOT / "docs/README.md").read_text(encoding="utf-8")
        prompt = (PROJECT_ROOT / "prompts/starting_prompt.md").read_text(encoding="utf-8")
        normalized_index = " ".join(index.split())
        normalized_prompt = " ".join(prompt.split())

        for completed in (
            "Governance foundation — complete",
            "Requirements and decisions — complete",
        ):
            self.assertIn(completed, index)
        self.assertIn("System design and versioned contracts — complete", index)
        self.assertIn(
            "Deterministic fixtures — complete and Fixture-qualified",
            index,
        )
        self.assertIn(
            "Platform infrastructure planning — implemented and planning-validated",
            index,
        )
        for later_slice in (
            "Networked provider runtime — locally implemented",
            "Terraform and workflow implementation — locally implemented and statically verified",
            "Non-production qualification deployment — authority proposed, implementation unavailable",
            "Live qualification — later",
            "Finance Application Adoption — later and independent",
        ):
            self.assertIn(later_slice, index)
        self.assertIn("separate bounded branch and pull request", normalized_index)
        self.assertIn(
            "implement AP-M8-W2 only as a bounded, non-secret operator-input manifest",
            normalized_prompt,
        )
        self.assertIn("A missing value stops AP-M8-W2", normalized_prompt)
        self.assertIn("Do not change repository settings", normalized_prompt)
        self.assertIn("Do not begin AP-M8-W3", normalized_prompt)

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
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
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
        future_boundaries = re.findall(
            r"^### (AP-EVAL-M[8-9]) ·", evaluation, re.MULTILINE
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
            future_boundaries,
            ["AP-EVAL-M8", "AP-EVAL-M9"],
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

    def test_ap_m8_authority_has_complete_unique_work_packages_and_gates(self) -> None:
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )

        work_packages = re.findall(r"^#### (AP-M8-W\d+) ·", plan, re.MULTILINE)
        evaluation_gates = re.findall(
            r"^##### (AP-EVAL-M8-\d{2}) ·", evaluation, re.MULTILINE
        )

        self.assertEqual(
            work_packages,
            [f"AP-M8-W{index}" for index in range(1, 13)],
        )
        self.assertEqual(
            evaluation_gates,
            [f"AP-EVAL-M8-{index:02d}" for index in range(1, 11)],
        )
        self.assertEqual(len(work_packages), len(set(work_packages)))
        self.assertEqual(len(evaluation_gates), len(set(evaluation_gates)))

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
            "### AP-EVAL-M8 · Qualification-deployment gate", 1
        )[1].split("### AP-EVAL-M9 · Live-qualification gate", 1)[0]

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
            "creates no schema, workflow, identity, credential, bucket object, provider action",
        ):
            self.assertIn(evidence_boundary, normalized)

    def test_ap_m8_authority_branch_contains_no_operational_capability(self) -> None:
        reserved_paths = (
            "infrastructure/backend",
            "edge/production.py",
            "fixtures/runtime.py",
            "infrastructure/images",
            "infrastructure/config/schemas/platform-configuration.v2.schema.json",
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
        self.assertFalse(any(PROJECT_ROOT.rglob("*.tfvars")))
        self.assertFalse(any(PROJECT_ROOT.rglob("*.tfstate")))
        self.assertFalse(any(PROJECT_ROOT.rglob("*.tfplan")))

    def test_ap_m7_authority_is_exact_static_and_non_operational(self) -> None:
        design = (PROJECT_ROOT / "docs/03_system_design.md").read_text(
            encoding="utf-8"
        )
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
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
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
            encoding="utf-8"
        )
        evaluation = (PROJECT_ROOT / "docs/05_evaluation_strategy.md").read_text(
            encoding="utf-8"
        )
        normalized_plan = " ".join(plan.split())
        normalized_evaluation = " ".join(evaluation.split())

        for later_slice in (
            "AP-M6 · Networked provider runtime implementation",
            "AP-M7 · Terraform and workflow implementation",
            "AP-M8 · Non-production qualification deployment",
            "AP-M9 · Live qualification",
            "Later Application Adoption",
        ):
            self.assertIn(later_slice, plan)

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
        self.assertEqual(len(tuple((config_root / "examples").glob("*.json"))), 15)
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
            "`infrastructure/terraform/fixtures/<application-id>/`",
            "`infrastructure/workflows/`",
            "`artifacts/`",
            "`docs/runbooks/`",
            "not authorization to scaffold empty modules",
        ):
            self.assertIn(reserved_reference, layout)

        terraform_files = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in PROJECT_ROOT.rglob("*")
            if path.is_file() and path.name.endswith((".tf", ".tf.json"))
        )
        self.assertEqual(
            terraform_files,
            sorted(
                [f"{root}/versions.tf" for root in expected_roots]
                + [
                    "infrastructure/terraform/bootstrap/main.tf",
                    "infrastructure/terraform/bootstrap/outputs.tf",
                    "infrastructure/terraform/bootstrap/variables.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/backend.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/main.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/outputs.tf",
                    "infrastructure/terraform/fixtures/fixture-authenticated/variables.tf",
                    "infrastructure/terraform/fixtures/fixture-public/backend.tf",
                    "infrastructure/terraform/fixtures/fixture-public/main.tf",
                    "infrastructure/terraform/fixtures/fixture-public/outputs.tf",
                    "infrastructure/terraform/fixtures/fixture-public/variables.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/backend.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/main.tf",
                    "infrastructure/terraform/fixtures/fixture-restricted/outputs.tf",
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
                    "infrastructure/terraform/platform/variables.tf",
                ]
            ),
        )
        prohibited_files = sorted(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in PROJECT_ROOT.rglob("*")
            if path.is_file()
            and path.name.endswith((".tfvars", ".tfstate", ".tfplan"))
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
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
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
        plan = (PROJECT_ROOT / "docs/04_implementation_plan.md").read_text(
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


if __name__ == "__main__":
    unittest.main()
