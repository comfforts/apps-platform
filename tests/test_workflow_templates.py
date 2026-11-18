"""AP-M7-W9 inert workflow authority and non-mutation checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = PROJECT_ROOT / "infrastructure" / "workflows"
EXPECTED_TEMPLATES = {
    "advisory-plan.yml.tmpl": ("plan", "plan"),
    "destroy.yml.tmpl": ("destroy", "destroy"),
    "exact-main-apply.yml.tmpl": ("apply", "apply"),
    "force-unlock.yml.tmpl": ("force-unlock", "force-unlock"),
    "rollback.yml.tmpl": ("rollback", "rollback"),
}
EXPECTED_ACTIONS = (
    "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
    "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
    "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093",
)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate key: {key}")
        value[key] = item
    return value


def _load_templates() -> dict[str, dict[str, object]]:
    loaded: dict[str, dict[str, object]] = {}
    for path in sorted(WORKFLOW_ROOT.glob("*.yml.tmpl")):
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
        if not isinstance(value, dict):
            raise TypeError(f"template is not an object: {path.name}")
        loaded[path.name] = value
    return loaded


def _only_job(template: dict[str, object]) -> tuple[str, dict[str, object]]:
    jobs = template["jobs"]
    assert isinstance(jobs, dict)
    ((name, job),) = jobs.items()
    assert isinstance(job, dict)
    return name, job


def _steps(job: dict[str, object]) -> list[dict[str, object]]:
    value = job["steps"]
    assert isinstance(value, list)
    assert all(isinstance(item, dict) for item in value)
    return value  # type: ignore[return-value]


class WorkflowTemplateTest(unittest.TestCase):
    def test_exact_inventory_parses_as_inert_json_compatible_yaml(self) -> None:
        templates = _load_templates()

        self.assertEqual(set(templates), set(EXPECTED_TEMPLATES))
        for filename, (operation, job_name) in EXPECTED_TEMPLATES.items():
            template = templates[filename]
            authority = template["x-ap-m7-authority"]
            assert isinstance(authority, dict)
            self.assertEqual(authority["status"], "inert")
            self.assertEqual(authority["activation_authority"], "AP-M8_REQUIRED")
            self.assertEqual(authority["operation"], operation)
            self.assertTrue(authority["stop_on_partial_failure"])
            self.assertEqual(_only_job(template)[0], job_name)

        executable = sorted(
            path.name
            for path in (PROJECT_ROOT / ".github" / "workflows").iterdir()
            if path.suffix in {".yml", ".yaml"}
        )
        self.assertEqual(executable, ["check.yml"])

    def test_every_action_is_pinned_to_the_reviewed_full_commit_sha(self) -> None:
        for filename, template in _load_templates().items():
            _, job = _only_job(template)
            uses = [step["uses"] for step in _steps(job) if "uses" in step]
            with self.subTest(filename=filename):
                self.assertEqual(uses, list(EXPECTED_ACTIONS))
                for action in uses:
                    assert isinstance(action, str)
                    self.assertRegex(action, r"^[a-z0-9-]+/[a-z0-9-]+@[0-9a-f]{40}$")

    def test_permissions_trigger_environment_and_concurrency_are_closed(self) -> None:
        for filename, template in _load_templates().items():
            _, job = _only_job(template)
            concurrency = template["concurrency"]
            assert isinstance(concurrency, dict)
            with self.subTest(filename=filename):
                self.assertEqual(template["on"], {"workflow_dispatch": {}})
                self.assertEqual(template["permissions"], {"contents": "read"})
                self.assertEqual(
                    job["permissions"],
                    {"contents": "read", "id-token": "write"},
                )
                self.assertEqual(job["environment"], "__PROTECTED_ENVIRONMENT__")
                self.assertEqual(
                    concurrency,
                    {
                        "group": "app-platform-__ROOT_TARGET__",
                        "cancel-in-progress": False,
                    },
                )
                self.assertIn("github.ref == 'refs/heads/main'", str(job["if"]))
                self.assertIn("github.sha == '__SOURCE_REVISION_40_HEX__'", str(job["if"]))

    def test_source_subject_and_root_are_bound_without_arbitrary_paths(self) -> None:
        expected_root_cases = (
            'bootstrap) root="infrastructure/terraform/bootstrap"',
            'platform) root="infrastructure/terraform/platform"',
            'fixture-public) root="infrastructure/terraform/fixtures/fixture-public"',
            'fixture-authenticated) root="infrastructure/terraform/fixtures/fixture-authenticated"',
            'fixture-restricted) root="infrastructure/terraform/fixtures/fixture-restricted"',
            "*) exit 1",
        )
        for filename, template in _load_templates().items():
            env = template["env"]
            assert isinstance(env, dict)
            _, job = _only_job(template)
            steps = _steps(job)
            rendered = "\n".join(str(step.get("run", "")) for step in steps)
            checkout = steps[0]
            checkout_with = checkout["with"]
            assert isinstance(checkout_with, dict)
            with self.subTest(filename=filename):
                self.assertEqual(env["AP_REPOSITORY"], "comfforts/apps-platform")
                self.assertEqual(env["AP_PROTECTED_MAIN_REF"], "refs/heads/main")
                self.assertEqual(env["AP_SOURCE_REVISION"], "__SOURCE_REVISION_40_HEX__")
                self.assertEqual(
                    env["AP_PROTECTED_SUBJECT"],
                    "repo:comfforts/apps-platform:environment:__PROTECTED_ENVIRONMENT__",
                )
                self.assertEqual(checkout_with["ref"], "__SOURCE_REVISION_40_HEX__")
                self.assertFalse(checkout_with["persist-credentials"])
                for root_case in expected_root_cases:
                    self.assertIn(root_case, rendered)

    def test_plans_are_fresh_canonical_runner_local_and_never_uploaded(self) -> None:
        templates = _load_templates()
        planned = {
            "advisory-plan.yml.tmpl",
            "destroy.yml.tmpl",
            "exact-main-apply.yml.tmpl",
            "rollback.yml.tmpl",
        }
        applied = {
            "destroy.yml.tmpl",
            "exact-main-apply.yml.tmpl",
            "rollback.yml.tmpl",
        }
        for filename, template in templates.items():
            _, job = _only_job(template)
            rendered = "\n".join(str(step.get("run", "")) for step in _steps(job))
            with self.subTest(filename=filename):
                self.assertEqual(" plan " in f" {rendered} ", filename in planned)
                self.assertEqual('"$tf" apply' in rendered, filename in applied)
                self.assertNotIn("upload-artifact", json.dumps(template))
                self.assertNotIn("artifacts/", rendered)
                if filename in planned:
                    self.assertIn("$RUNNER_TEMP/app-platform-", rendered)
                    self.assertIn('"$tf" show -json', rendered)
                    self.assertIn("document.pop('timestamp', None)", rendered)
                    self.assertIn("sort_keys=True", rendered)
                    self.assertIn("hashlib.sha256", rendered)
                    self.assertIn("rm -f", rendered)
                if filename in applied:
                    self.assertIn('test "$plan_digest" = "$AP_PLAN_DIGEST"', rendered)

    def test_destructive_authorities_are_separate_and_confirmation_bound(self) -> None:
        templates = _load_templates()
        for filename, template in templates.items():
            authority = template["x-ap-m7-authority"]
            assert isinstance(authority, dict)
            _, job = _only_job(template)
            rendered = "\n".join(str(step.get("run", "")) for step in _steps(job))
            with self.subTest(filename=filename):
                self.assertEqual(
                    '"$tf" force-unlock -force "$AP_LOCK_ID"' in rendered,
                    filename == "force-unlock.yml.tmpl",
                )
                self.assertEqual(
                    '"$tf" plan -destroy' in rendered,
                    filename == "destroy.yml.tmpl",
                )
                self.assertEqual(
                    authority["destructive_target"] is not None,
                    filename in {"destroy.yml.tmpl", "force-unlock.yml.tmpl"},
                )
                if authority["destructive_target"] is not None:
                    self.assertIn("confirmation_digest", json.dumps(authority))
                    self.assertIn('test "$confirmation_digest" = "$AP_CONFIRMATION_DIGEST"', rendered)

    def test_partial_failure_stops_and_only_safe_outcome_metadata_is_retained(self) -> None:
        allowed_metadata = {
            "operation",
            "root_target",
            "source_revision",
            "plan_digest",
            "target_id",
            "confirmation_digest",
            "outcome",
        }
        for filename, template in _load_templates().items():
            authority = template["x-ap-m7-authority"]
            assert isinstance(authority, dict)
            _, job = _only_job(template)
            rendered = "\n".join(str(step.get("run", "")) for step in _steps(job))
            with self.subTest(filename=filename):
                self.assertTrue(set(authority["outcome_metadata"]) <= allowed_metadata)
                self.assertIn("GITHUB_STEP_SUMMARY", rendered)
                self.assertIn("set -euo pipefail", rendered)
                self.assertNotIn("continue-on-error", json.dumps(template))
                self.assertNotIn("if: failure", json.dumps(template))

    def test_templates_contain_no_live_identity_secret_or_implicit_mutation(self) -> None:
        templates = _load_templates()
        combined = "\n".join(json.dumps(value, sort_keys=True) for value in templates.values())
        for prohibited in (
            "secrets.",
            "credentials_json",
            "private_key",
            "terraform_remote_state",
            "terraform state push",
            "terraform import",
            "gcloud dns",
            "upload-artifact",
            "pull_request_target",
            "apps-staging.comfforts.com",
            "comfforts-platform-non-prod",
        ):
            self.assertNotIn(prohibited, combined)
        self.assertIsNone(
            re.search(
                r"projects/[0-9]+/locations/global/workloadIdentityPools/",
                combined,
            )
        )
        self.assertIsNone(
            re.search(r"[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com", combined)
        )
        self.assertIn("gha-creds-*.json", (PROJECT_ROOT / ".gitignore").read_text())
        check_workflow = (PROJECT_ROOT / ".github/workflows/check.yml").read_text()
        self.assertNotIn("id-token: write", check_workflow)
        self.assertIn("permissions:\n  contents: read", check_workflow)


if __name__ == "__main__":
    unittest.main()
