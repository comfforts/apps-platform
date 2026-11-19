"""Thin command-line shell over the AP-M9 lifecycle module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from infrastructure.operator._core import LifecycleOperator
from infrastructure.operator.local import build_local_operator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DIRECTORY = PROJECT_ROOT / ".platform-operator"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apps-platform-operator")
    parser.add_argument(
        "operation",
        choices=("deploy", "prepare", "status"),
        help="platform lifecycle operation",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("production", "staging"),
    )
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=DEFAULT_STATE_DIRECTORY,
        help="private ignored directory for generated lifecycle state",
    )
    parser.add_argument(
        "--specification-digest",
        help="exact approved deployment specification digest",
    )
    return parser


def _default_factory(state_directory: Path) -> LifecycleOperator:
    return build_local_operator(PROJECT_ROOT, state_directory)


def main(
    argv: Sequence[str] | None = None,
    *,
    operator_factory: Callable[[Path], LifecycleOperator] = _default_factory,
) -> int:
    arguments = _parser().parse_args(argv)
    operator = operator_factory(arguments.state_directory)
    if arguments.operation == "prepare":
        result = operator.prepare(arguments.environment)
        print(
            json.dumps(
                {
                    "approved": result.approved,
                    "blockers": list(result.blockers),
                    "complete": result.complete,
                    "environment": arguments.environment,
                    "outcome": result.outcome,
                    "specification_digest": result.specification_digest,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0 if result.outcome in {"prepared", "unchanged"} else 2

    if arguments.operation == "deploy":
        if arguments.specification_digest is None:
            raise SystemExit("deploy requires --specification-digest")
        result = operator.execute(
            arguments.environment,
            arguments.specification_digest,
        )
        print(
            json.dumps(
                {
                    "blockers": list(result.blockers),
                    "environment": arguments.environment,
                    "journal_digest": result.journal_digest,
                    "outcome": result.outcome,
                    "specification_digest": arguments.specification_digest,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0 if result.outcome in {"succeeded", "unchanged"} else 2

    status = operator.status(arguments.environment)
    print(
        json.dumps(
            status.environment_status,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if not status.conflicts else 2
