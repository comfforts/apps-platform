"""Production composition for the Platform Member Directory lifecycle.

This module is the only operator component with member-write provider authority.
It binds the verified local Cloud Operator session to a synchronous Firestore
client for the named member database, a strict Shared Edge browser launcher, and
the provider-neutral lifecycle service.  Provider payloads and exceptions never
cross the service result boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit
import webbrowser

from google.api_core import exceptions as google_exceptions
from google.cloud import firestore
from google.cloud.firestore_v1 import transactional

from infrastructure.member_directory import (
    DIRECTORY_COLLECTION_NAME,
    DIRECTORY_DOCUMENT_FIELDS,
    DIRECTORY_DOCUMENT_NAME,
    MEMBER_COLLECTION_NAME,
    MEMBER_DOCUMENT_CONTRACT_VERSION,
    MEMBER_DOCUMENT_FIELDS,
    MEMBER_DATABASE_NAME,
    MemberRecord,
)
from infrastructure.operator.member_lifecycle import (
    DirectoryControl,
    MemberDirectorySnapshot,
    MemberMutation,
    MemberPredecessorStale,
    MemberProviderUnavailable,
    MemberReadbackMismatch,
    MemberStateMalformed,
)
from infrastructure.operator.source_authority import source_authority_blockers


_PROJECTS = {"staging": "comfforts-platform-non-prod"}
_ORIGINS = {"staging": "https://apps-staging.comfforts.com"}


def _control(snapshot: Any) -> DirectoryControl | None:
    """Validate one exact control snapshot without retaining provider metadata."""

    if not snapshot.exists:
        return None
    value = snapshot.to_dict()
    if (
        not isinstance(value, dict)
        or set(value) != set(DIRECTORY_DOCUMENT_FIELDS)
        or value.get("contract_version") != MEMBER_DOCUMENT_CONTRACT_VERSION
        or value.get("initialized") is not True
    ):
        raise MemberStateMalformed("member directory control is malformed")
    try:
        return DirectoryControl(
            mutation_cursor=value["mutation_cursor"],
            created_at=value["created_at"],
            updated_at=value["updated_at"],
        )
    except (TypeError, ValueError) as error:
        raise MemberStateMalformed("member directory control is malformed") from error


def _member(snapshot: Any, member_reference: str) -> MemberRecord | None:
    """Validate one exact member snapshot without accepting identity fields."""

    if not snapshot.exists:
        return None
    value = snapshot.to_dict()
    if (
        not isinstance(value, dict)
        or set(value) != set(MEMBER_DOCUMENT_FIELDS)
        or value.get("contract_version") != MEMBER_DOCUMENT_CONTRACT_VERSION
    ):
        raise MemberStateMalformed("member directory record is malformed")
    try:
        return MemberRecord(
            member_reference=member_reference,
            lifecycle=value["lifecycle"],
            mutation_cursor=value["mutation_cursor"],
            created_at=value["created_at"],
            updated_at=value["updated_at"],
        )
    except (TypeError, ValueError) as error:
        raise MemberStateMalformed("member directory record is malformed") from error


class FirestoreMemberDirectoryProvider:
    """Apply exact member transitions in one named-database transaction."""

    def __init__(self, clients: dict[str, Any]) -> None:
        """Bind one explicit client per supported environment without I/O."""

        if set(clients) != set(_PROJECTS):
            raise ValueError("member provider environments are incomplete")
        self._clients = dict(clients)

    def _client(self, environment: str) -> Any:
        """Select only the closed environment-to-project mapping."""

        try:
            return self._clients[environment]
        except KeyError as error:
            raise MemberProviderUnavailable(
                "member directory environment is unavailable"
            ) from error

    @staticmethod
    def _read_with_client(
        client: Any,
        member_reference: str | None,
        *,
        probe_empty: bool,
        transaction: Any | None = None,
    ) -> MemberDirectorySnapshot:
        """Read control, one exact member, and an optional boolean emptiness probe."""

        control_document = client.collection(DIRECTORY_COLLECTION_NAME).document(
            DIRECTORY_DOCUMENT_NAME
        )
        control_snapshot = control_document.get(transaction=transaction)
        member_record = None
        member_collection = client.collection(MEMBER_COLLECTION_NAME)
        if member_reference is not None:
            member_record = _member(
                member_collection.document(member_reference).get(transaction=transaction),
                member_reference,
            )
        members_present = None
        other_members_present = None
        if probe_empty:
            observed = tuple(
                member_collection.limit(2).stream(transaction=transaction)
            )
            members_present = bool(observed)
            other_members_present = any(
                member_reference is None or item.id != member_reference
                for item in observed
            )
        try:
            return MemberDirectorySnapshot(
                control=_control(control_snapshot),
                member=member_record,
                members_present=members_present,
                other_members_present=other_members_present,
            )
        except ValueError as error:
            raise MemberStateMalformed("member directory state is malformed") from error

    def read(
        self,
        environment: str,
        member_reference: str | None = None,
        *,
        probe_empty: bool = False,
    ) -> MemberDirectorySnapshot:
        """Read a bounded remote projection and classify provider failures."""

        try:
            return self._read_with_client(
                self._client(environment),
                member_reference,
                probe_empty=probe_empty,
            )
        except MemberStateMalformed:
            raise
        except Exception as error:
            raise MemberProviderUnavailable("member directory unavailable") from error

    @staticmethod
    def _successor(mutation: MemberMutation) -> MemberDirectorySnapshot:
        """Compile the exact successor expected from the atomic transaction."""

        predecessor = mutation.predecessor
        previous_control = predecessor.control
        cursor = (previous_control.mutation_cursor if previous_control else 0) + 1
        created_at = (
            previous_control.created_at if previous_control else mutation.timestamp
        )
        control = DirectoryControl(cursor, created_at, mutation.timestamp)
        previous_member = predecessor.member
        if mutation.operation == "remove":
            member = None
        else:
            member = MemberRecord(
                member_reference=mutation.member_reference,
                lifecycle=(
                    "suspended" if mutation.operation == "suspend" else "active"
                ),
                mutation_cursor=cursor,
                created_at=(
                    previous_member.created_at
                    if previous_member is not None
                    else mutation.timestamp
                ),
                updated_at=mutation.timestamp,
            )
        return MemberDirectorySnapshot(control, member)

    def mutate(self, mutation: MemberMutation) -> MemberDirectorySnapshot:
        """Compare, mutate atomically, then require byte-equivalent model readback."""

        client = self._client(mutation.environment)
        successor = self._successor(mutation)
        control_document = client.collection(DIRECTORY_COLLECTION_NAME).document(
            DIRECTORY_DOCUMENT_NAME
        )
        member_document = client.collection(MEMBER_COLLECTION_NAME).document(
            mutation.member_reference
        )

        @transactional
        def apply(active_transaction: Any) -> None:
            """Apply one exact compare-and-set inside the provider transaction."""

            current = self._read_with_client(
                client,
                mutation.member_reference,
                probe_empty=mutation.operation == "bootstrap-owner",
                transaction=active_transaction,
            )
            if current != mutation.predecessor:
                raise MemberPredecessorStale("member predecessor changed")
            if (
                mutation.operation == "bootstrap-owner"
                and (current.control is not None or current.members_present)
            ):
                raise MemberPredecessorStale("member bootstrap predecessor changed")
            assert successor.control is not None
            control_value = {
                "contract_version": MEMBER_DOCUMENT_CONTRACT_VERSION,
                "initialized": True,
                "mutation_cursor": successor.control.mutation_cursor,
                "created_at": successor.control.created_at,
                "updated_at": successor.control.updated_at,
            }
            if current.control is None:
                active_transaction.create(control_document, control_value)
            else:
                active_transaction.set(control_document, control_value)
            if successor.member is None:
                active_transaction.delete(member_document)
            else:
                active_transaction.set(
                    member_document,
                    {
                        "contract_version": MEMBER_DOCUMENT_CONTRACT_VERSION,
                        "lifecycle": successor.member.lifecycle,
                        "mutation_cursor": successor.member.mutation_cursor,
                        "created_at": successor.member.created_at,
                        "updated_at": successor.member.updated_at,
                    },
                )

        try:
            apply(client.transaction(max_attempts=1))
            readback = self._read_with_client(
                client,
                mutation.member_reference,
                probe_empty=False,
            )
        except MemberPredecessorStale:
            raise
        except MemberStateMalformed:
            raise
        except (
            google_exceptions.Aborted,
            google_exceptions.Conflict,
            google_exceptions.FailedPrecondition,
        ) as error:
            raise MemberPredecessorStale("member predecessor changed") from error
        except Exception as error:
            raise MemberProviderUnavailable("member directory unavailable") from error
        if readback != successor:
            raise MemberReadbackMismatch("member directory readback mismatch")
        return readback


@dataclass(frozen=True, slots=True)
class LocalMemberOperationAuthorizer:
    """Require exact source admission after Cloud Operator verification."""

    git: Any
    source_authority: str
    cloud_operator_verified: bool

    def authorize(self, environment: str) -> tuple[str, ...]:
        """Return stable source/session blockers without provider mutation."""

        blockers = list(
            source_authority_blockers(
                self.git.inspect(),
                environment,
                self.source_authority,
            )
        )
        if not self.cloud_operator_verified:
            blockers.append("MEMBER_CLOUD_OPERATOR_UNVERIFIED")
        if environment not in _PROJECTS:
            blockers.append("MEMBER_ENVIRONMENT_UNAVAILABLE")
        return tuple(sorted(set(blockers)))


@dataclass(frozen=True, slots=True)
class UnixMemberClock:
    """Persist whole UTC seconds without provider-specific timestamp objects."""

    def now(self) -> int:
        """Return a positive integer suitable for exact contract readback."""

        return int(time.time())


class SystemMemberBrowserLauncher:
    """Open only the closed Apps Platform member-verification URL shape."""

    def open(self, url: str) -> bool:
        """Reject any non-platform host, path, fragment, or missing return target."""

        parsed = urlsplit(url)
        query = parse_qs(parsed.query, strict_parsing=True)
        if (
            parsed.scheme != "https"
            or parsed.netloc not in {"apps-staging.comfforts.com", "apps.comfforts.com"}
            or parsed.path != "/_platform/logout"
            or set(query) != {"return_to"}
            or len(query["return_to"]) != 1
            or not query["return_to"][0].startswith("/_platform/member/verify?")
            or parsed.fragment
        ):
            raise ValueError("member browser URL is outside the approved set")
        return webbrowser.open(url, new=2, autoraise=True)


def member_origins() -> dict[str, str]:
    """Return the closed environment origins without exposing a mutable global."""

    return dict(_ORIGINS)


def member_clients() -> dict[str, Any]:
    """Construct one ADC-backed named-database client per supported environment."""

    return {
        environment: firestore.Client(
            project=project_id,
            database=MEMBER_DATABASE_NAME,
        )
        for environment, project_id in _PROJECTS.items()
    }


__all__ = (
    "FirestoreMemberDirectoryProvider",
    "LocalMemberOperationAuthorizer",
    "SystemMemberBrowserLauncher",
    "UnixMemberClock",
    "member_clients",
    "member_origins",
)
