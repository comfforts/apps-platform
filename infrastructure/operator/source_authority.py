"""Closed source-authority policy for accepted and staging-candidate operations."""

from __future__ import annotations

from infrastructure.operator._interfaces import GitSnapshot


SOURCE_AUTHORITIES = ("accepted", "candidate")


def validate_source_authority(source_authority: str) -> str:
    """Return one supported authority label or reject configuration drift."""

    if source_authority not in SOURCE_AUTHORITIES:
        raise ValueError(f"unsupported source authority {source_authority!r}")
    return source_authority


def source_authority_blockers(
    snapshot: GitSnapshot,
    environment: str,
    source_authority: str,
) -> tuple[str, ...]:
    """Evaluate source admission without performing Git or provider mutation."""

    authority = validate_source_authority(source_authority)
    blockers: list[str] = []
    if snapshot.repository != "comfforts/apps-platform":
        blockers.append("REPOSITORY_MISMATCH")
    if not snapshot.clean:
        blockers.append("SOURCE_NOT_CLEAN")

    if authority == "accepted":
        if snapshot.branch != "main":
            blockers.append("SOURCE_NOT_MAIN")
        if not (
            snapshot.revision
            == snapshot.main_revision
            == snapshot.origin_main_revision
        ):
            blockers.append("SOURCE_NOT_CURRENT")
        return tuple(sorted(set(blockers)))

    if environment != "staging":
        blockers.append("CANDIDATE_SOURCE_PRODUCTION_PROHIBITED")
    if not snapshot.branch or snapshot.branch == "main":
        blockers.append("CANDIDATE_BRANCH_REQUIRED")
    expected_upstream = (
        f"origin/{snapshot.branch}" if snapshot.branch and snapshot.branch != "main" else None
    )
    if snapshot.upstream_branch != expected_upstream:
        blockers.append("CANDIDATE_UPSTREAM_MISMATCH")
    if (
        snapshot.upstream_revision is None
        or snapshot.revision != snapshot.upstream_revision
    ):
        blockers.append("CANDIDATE_NOT_PUSHED")
    if not snapshot.origin_main_ancestor:
        blockers.append("CANDIDATE_BASE_STALE")
    return tuple(sorted(set(blockers)))


__all__ = (
    "SOURCE_AUTHORITIES",
    "source_authority_blockers",
    "validate_source_authority",
)
