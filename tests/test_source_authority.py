"""Closed accepted-main and staging-candidate source admission tests."""

from __future__ import annotations

from dataclasses import replace
import unittest

from infrastructure.operator import GitSnapshot
from infrastructure.operator.source_authority import source_authority_blockers


REVISION = "a" * 40
BRANCH = "feat/candidate-source"


def accepted() -> GitSnapshot:
    return GitSnapshot(
        repository="comfforts/apps-platform",
        revision=REVISION,
        branch="main",
        clean=True,
        main_revision=REVISION,
        origin_main_revision=REVISION,
    )


def candidate() -> GitSnapshot:
    return GitSnapshot(
        repository="comfforts/apps-platform",
        revision=REVISION,
        branch=BRANCH,
        clean=True,
        main_revision="b" * 40,
        origin_main_revision="b" * 40,
        upstream_branch=f"origin/{BRANCH}",
        upstream_revision=REVISION,
        origin_main_ancestor=True,
    )


class SourceAuthorityTest(unittest.TestCase):
    def test_accepted_source_remains_exact_current_main(self) -> None:
        self.assertEqual(
            source_authority_blockers(accepted(), "staging", "accepted"),
            (),
        )
        self.assertEqual(
            source_authority_blockers(candidate(), "staging", "accepted"),
            ("SOURCE_NOT_CURRENT", "SOURCE_NOT_MAIN"),
        )

    def test_candidate_source_is_clean_pushed_current_and_staging_only(self) -> None:
        self.assertEqual(
            source_authority_blockers(candidate(), "staging", "candidate"),
            (),
        )

        cases = (
            (
                replace(candidate(), clean=False),
                "staging",
                "SOURCE_NOT_CLEAN",
            ),
            (
                replace(candidate(), upstream_revision="c" * 40),
                "staging",
                "CANDIDATE_NOT_PUSHED",
            ),
            (
                replace(candidate(), upstream_branch="origin/another-branch"),
                "staging",
                "CANDIDATE_UPSTREAM_MISMATCH",
            ),
            (
                replace(candidate(), origin_main_ancestor=False),
                "staging",
                "CANDIDATE_BASE_STALE",
            ),
            (
                candidate(),
                "production",
                "CANDIDATE_SOURCE_PRODUCTION_PROHIBITED",
            ),
        )
        for snapshot, environment, blocker in cases:
            with self.subTest(blocker=blocker):
                self.assertIn(
                    blocker,
                    source_authority_blockers(
                        snapshot,
                        environment,
                        "candidate",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
