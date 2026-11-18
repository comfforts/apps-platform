"""Credential-free AP-M8 operator-manifest chain validation command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from infrastructure.config.validation import load_operator_manifest_chain


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate one ordered AP-M8 operator-manifest chain without discovery "
            "or external access."
        )
    )
    parser.add_argument(
        "revision",
        nargs="+",
        type=Path,
        help="manifest revision paths in predecessor order",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Validate explicit operator revisions and emit only digests or violations."""

    parsed = _parser().parse_args(arguments)
    result = load_operator_manifest_chain(tuple(parsed.revision))
    if result.violations:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "violations": [
                        {
                            "code": violation.code,
                            "path": violation.path,
                            "message": violation.message,
                        }
                        for violation in result.violations
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "accepted",
                "revision_count": len(result.digests),
                "digests": list(result.digests),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
