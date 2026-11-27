"""Private Platform Member Directory model and deterministic lookup seam.

The module defines the storage-neutral shape shared by later edge-admission and
operator-lifecycle slices.  A member is addressed by an environment-bound opaque
reference derived from a verified Google issuer and immutable subject.  The
persisted member document contains no issuer, subject, email, display name,
application role, or feature entitlement.

The Shared Edge receives only exact current-identity lookup.  The member
lifecycle imports the shared validated record model but uses a separate
operator-only provider adapter for bounded mutation; no mutation or enumeration
surface is added to the runtime reader.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable, Literal, Protocol


CANONICAL_GOOGLE_ISSUER = "https://accounts.google.com"
MEMBER_DATABASE_NAME = "app-platform-members"
DIRECTORY_COLLECTION_NAME = "platform-member-directory-v1"
DIRECTORY_DOCUMENT_NAME = "state"
MEMBER_COLLECTION_NAME = "platform-members-v1"
MEMBER_DOCUMENT_CONTRACT_VERSION = 1
MEMBER_REFERENCE_SCHEME = "pmr1-sha256"
MEMBER_DOCUMENT_FIELDS = (
    "contract_version",
    "lifecycle",
    "mutation_cursor",
    "created_at",
    "updated_at",
)
DIRECTORY_DOCUMENT_FIELDS = (
    "contract_version",
    "initialized",
    "mutation_cursor",
    "created_at",
    "updated_at",
)
_ENVIRONMENT = re.compile(r"[a-z][a-z0-9-]{1,31}")
_MEMBER_REFERENCE = re.compile(r"pmr1_[0-9a-f]{64}")


class MemberDirectoryUnavailable(RuntimeError):
    """The member directory could not safely complete an exact lookup."""


@dataclass(frozen=True, slots=True)
class PlatformMemberIdentity:
    """Verified identity material used transiently to derive a member key."""

    issuer: str
    subject: str

    def __post_init__(self) -> None:
        """Reject non-canonical or unsafe identity material before derivation."""

        if self.issuer != CANONICAL_GOOGLE_ISSUER:
            raise ValueError("unsupported member identity issuer")
        if (
            not isinstance(self.subject, str)
            or not 1 <= len(self.subject) <= 255
            or any(ord(character) < 0x20 for character in self.subject)
        ):
            raise ValueError("invalid member identity subject")


@dataclass(frozen=True, slots=True)
class MemberRecord:
    """Minimal private member document returned by exact-key readback."""

    member_reference: str
    lifecycle: Literal["active", "suspended"]
    mutation_cursor: int
    created_at: int
    updated_at: int

    def __post_init__(self) -> None:
        """Validate the complete persisted record without accepting identity data."""

        if _MEMBER_REFERENCE.fullmatch(self.member_reference) is None:
            raise ValueError("invalid member reference")
        if self.lifecycle not in {"active", "suspended"}:
            raise ValueError("invalid member lifecycle")
        if (
            isinstance(self.mutation_cursor, bool)
            or not isinstance(self.mutation_cursor, int)
            or self.mutation_cursor < 1
        ):
            raise ValueError("invalid member mutation cursor")
        if (
            isinstance(self.created_at, bool)
            or not isinstance(self.created_at, int)
            or self.created_at < 1
            or isinstance(self.updated_at, bool)
            or not isinstance(self.updated_at, int)
            or self.updated_at < self.created_at
        ):
            raise ValueError("invalid member timestamps")


def member_reference(
    environment: str,
    identity: PlatformMemberIdentity,
) -> str:
    """Derive a stable environment-scoped reference without retaining identity."""

    if not isinstance(environment, str) or _ENVIRONMENT.fullmatch(environment) is None:
        raise ValueError("invalid member environment")
    if not isinstance(identity, PlatformMemberIdentity):
        raise TypeError("member identity must be verified")
    material = "\0".join(
        (
            MEMBER_REFERENCE_SCHEME,
            environment,
            identity.issuer,
            identity.subject,
        )
    ).encode("utf-8")
    return "pmr1_" + hashlib.sha256(material).hexdigest()


class CurrentMemberLookup(Protocol):
    """Narrow read seam available to later restricted-admission code."""

    async def lookup_current_member(
        self,
        environment: str,
        identity: PlatformMemberIdentity,
    ) -> MemberRecord | None:
        """Return only the exact current visitor's member record when present."""


class InMemoryMemberDirectory:
    """Deterministic exact-key lookup adapter with no enumeration or mutation API."""

    def __init__(
        self,
        records: Iterable[MemberRecord] = (),
        *,
        available: bool = True,
    ) -> None:
        """Load unique opaque records for deterministic tests only."""

        loaded: dict[str, MemberRecord] = {}
        for record in records:
            if not isinstance(record, MemberRecord):
                raise TypeError("member directory records must be validated")
            if record.member_reference in loaded:
                raise ValueError("duplicate member reference")
            loaded[record.member_reference] = record
        self._records = loaded
        self._available = available

    async def lookup_current_member(
        self,
        environment: str,
        identity: PlatformMemberIdentity,
    ) -> MemberRecord | None:
        """Read one derived key or fail closed when the adapter is unavailable."""

        if not self._available:
            raise MemberDirectoryUnavailable("member directory unavailable")
        return self._records.get(member_reference(environment, identity))


class FirestoreCurrentMemberLookup:
    """Read only the current visitor's document from an injected named database.

    The caller must construct the client for :data:`MEMBER_DATABASE_NAME`.  This
    adapter never queries a collection, enumerates documents, or mutates state.
    Missing documents return ``None``.  Provider failures and documents whose
    exact private shape cannot be validated collapse to
    :class:`MemberDirectoryUnavailable` so restricted admission can fail closed
    without disclosing the reason to the visitor.
    """

    def __init__(self, client: Any) -> None:
        """Bind one provider client without performing discovery or I/O."""

        self._client = client

    async def lookup_current_member(
        self,
        environment: str,
        identity: PlatformMemberIdentity,
    ) -> MemberRecord | None:
        """Read and validate one derived document key from the named database."""

        reference = member_reference(environment, identity)
        try:
            snapshot = await (
                self._client.collection(MEMBER_COLLECTION_NAME)
                .document(reference)
                .get()
            )
            if not snapshot.exists:
                return None
            value = snapshot.to_dict()
            if not isinstance(value, dict) or set(value) != set(MEMBER_DOCUMENT_FIELDS):
                raise ValueError("member document shape is invalid")
            if (
                isinstance(value["contract_version"], bool)
                or value["contract_version"] != MEMBER_DOCUMENT_CONTRACT_VERSION
            ):
                raise ValueError("member document version is invalid")
            return MemberRecord(
                member_reference=reference,
                lifecycle=value["lifecycle"],
                mutation_cursor=value["mutation_cursor"],
                created_at=value["created_at"],
                updated_at=value["updated_at"],
            )
        except MemberDirectoryUnavailable:
            raise
        except Exception as error:
            raise MemberDirectoryUnavailable("member directory unavailable") from error


__all__ = (
    "CANONICAL_GOOGLE_ISSUER",
    "CurrentMemberLookup",
    "DIRECTORY_COLLECTION_NAME",
    "DIRECTORY_DOCUMENT_FIELDS",
    "DIRECTORY_DOCUMENT_NAME",
    "FirestoreCurrentMemberLookup",
    "InMemoryMemberDirectory",
    "MEMBER_COLLECTION_NAME",
    "MEMBER_DATABASE_NAME",
    "MEMBER_DOCUMENT_CONTRACT_VERSION",
    "MEMBER_DOCUMENT_FIELDS",
    "MEMBER_REFERENCE_SCHEME",
    "MemberDirectoryUnavailable",
    "MemberRecord",
    "PlatformMemberIdentity",
    "member_reference",
)
