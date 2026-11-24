"""Exact deterministic environment values supplied by the repository test runner."""

from __future__ import annotations

import os
import re


FIXTURES_PROJECT_ID = os.environ.get("FIXTURES_PROJECT_ID", "")
if re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", FIXTURES_PROJECT_ID) is None:
    raise RuntimeError("tests require a valid FIXTURES_PROJECT_ID")


__all__ = ("FIXTURES_PROJECT_ID",)
