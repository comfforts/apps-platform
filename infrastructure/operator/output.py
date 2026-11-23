"""Shared human and machine output formatting for operator entry points."""

from __future__ import annotations

import json
import sys


def _error_component(blocker: str) -> str:
    if blocker.startswith("TERRAFORM_"):
        return "terraform"
    if blocker.startswith(("GCLOUD_", "CLOUD_SDK_", "CERTIFICATE_")):
        return "google-cloud"
    if blocker.startswith("DNS_"):
        return "dns"
    if blocker.startswith("OPERATOR_"):
        return "operator-session"
    if blocker.startswith(("SOURCE_", "CANDIDATE_", "REPOSITORY_", "GITHUB_")):
        return "source-control"
    if blocker.startswith("FIXTURE_"):
        return "fixture-application"
    if blocker.startswith(("APPLICATION_", "ATTACHMENT_", "REGISTRATION_")):
        return "application-lifecycle"
    if blocker.startswith("QUALIFICATION_"):
        return "qualification"
    if blocker.startswith("EXECUTION_"):
        return "deployment-executor"
    return "platform-operator"


def report_result_errors(value: dict[str, object]) -> None:
    """Narrate stable blocker codes before emitting a machine-readable result."""

    blockers = value.get("blockers")
    if not isinstance(blockers, list):
        return
    for blocker in blockers:
        if not isinstance(blocker, str):
            continue
        print("Operator error:", file=sys.stderr)
        print(f"  component: {_error_component(blocker)}", file=sys.stderr)
        print(f"  code: {blocker}", file=sys.stderr)
        print(file=sys.stderr)


def print_result(value: dict[str, object]) -> None:
    """Write narration to stderr and one pretty machine result to stdout."""

    report_result_errors(value)
    print(json.dumps(value, indent=2, sort_keys=True))


__all__ = ("print_result", "report_result_errors")
