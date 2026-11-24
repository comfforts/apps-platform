"""Environment-selected fixture-project identity shared by operator modules."""

from __future__ import annotations

import os
import re


_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")


def fixtures_project_id(environment: dict[str, str] | None = None) -> str:
    """Return the explicit fixture project ID or fail before provider access."""

    selected = (environment or os.environ).get("FIXTURES_PROJECT_ID", "")
    if _PROJECT_ID.fullmatch(selected) is None:
        raise ValueError("FIXTURES_PROJECT_ID must be an exact GCP project ID")
    if selected == "comfforts-platform-non-prod":
        raise ValueError("FIXTURES_PROJECT_ID must not select the platform project")
    return selected


def fixture_state_bucket(project_id: str) -> str:
    """Derive the fixture-owned state bucket from one validated project ID."""

    if _PROJECT_ID.fullmatch(project_id) is None:
        raise ValueError("fixture project ID must be exact")
    return f"{project_id}-state"


__all__ = ("fixture_state_bucket", "fixtures_project_id")
