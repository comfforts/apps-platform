"""Deterministic Platform Member Directory model and adapter checks."""

from __future__ import annotations

import asyncio
from dataclasses import fields
import unittest

from infrastructure.member_directory import (
    CANONICAL_GOOGLE_ISSUER,
    DIRECTORY_COLLECTION_NAME,
    DIRECTORY_DOCUMENT_FIELDS,
    DIRECTORY_DOCUMENT_NAME,
    FirestoreCurrentMemberLookup,
    InMemoryMemberDirectory,
    MEMBER_COLLECTION_NAME,
    MEMBER_DATABASE_NAME,
    MEMBER_DOCUMENT_CONTRACT_VERSION,
    MEMBER_DOCUMENT_FIELDS,
    MEMBER_REFERENCE_SCHEME,
    MemberDirectoryUnavailable,
    MemberRecord,
    PlatformMemberIdentity,
    member_reference,
)


class _Snapshot:
    """Minimal Firestore snapshot fake for exact-read adapter tests."""

    def __init__(self, value: object | None) -> None:
        self.exists = value is not None
        self._value = value

    def to_dict(self) -> object | None:
        """Return the configured provider payload without normalization."""

        return self._value


class _Document:
    """Record one exact document get and return a configured snapshot."""

    def __init__(self, client: _Firestore, document_id: str) -> None:
        self._client = client
        self._document_id = document_id

    async def get(self) -> _Snapshot:
        """Perform the fake exact-key read or raise the configured provider error."""

        self._client.requests.append((self._client.collection_name, self._document_id))
        if self._client.error is not None:
            raise self._client.error
        return _Snapshot(self._client.value)


class _Collection:
    """Expose document addressing but deliberately no query interface."""

    def __init__(self, client: _Firestore) -> None:
        self._client = client

    def document(self, document_id: str) -> _Document:
        """Select one exact document identifier."""

        return _Document(self._client, document_id)


class _Firestore:
    """Minimal named-database client fake used without credentials or network."""

    def __init__(
        self,
        value: object | None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.value = value
        self.error = error
        self.collection_name = ""
        self.requests: list[tuple[str, str]] = []

    def collection(self, name: str) -> _Collection:
        """Record the selected collection and expose exact document addressing."""

        self.collection_name = name
        return _Collection(self)


class MemberDirectoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = PlatformMemberIdentity(
            CANONICAL_GOOGLE_ISSUER,
            "123456789012345678901",
        )

    def test_storage_layout_is_versioned_disjoint_and_identity_free(self) -> None:
        self.assertEqual(MEMBER_DATABASE_NAME, "app-platform-members")
        self.assertEqual(
            (DIRECTORY_COLLECTION_NAME, DIRECTORY_DOCUMENT_NAME),
            ("platform-member-directory-v1", "state"),
        )
        self.assertEqual(MEMBER_COLLECTION_NAME, "platform-members-v1")
        self.assertEqual(MEMBER_DOCUMENT_CONTRACT_VERSION, 1)
        self.assertEqual(MEMBER_REFERENCE_SCHEME, "pmr1-sha256")
        self.assertEqual(
            MEMBER_DOCUMENT_FIELDS,
            (
                "contract_version",
                "lifecycle",
                "mutation_cursor",
                "created_at",
                "updated_at",
            ),
        )
        self.assertEqual(
            DIRECTORY_DOCUMENT_FIELDS,
            (
                "contract_version",
                "initialized",
                "mutation_cursor",
                "created_at",
                "updated_at",
            ),
        )
        prohibited = {"issuer", "subject", "email", "display_name", "role"}
        self.assertTrue(prohibited.isdisjoint(MEMBER_DOCUMENT_FIELDS))
        self.assertTrue(prohibited.isdisjoint(DIRECTORY_DOCUMENT_FIELDS))

    def test_reference_is_stable_environment_bound_and_opaque(self) -> None:
        first = member_reference("staging", self.identity)
        repeated = member_reference("staging", self.identity)
        production = member_reference("production", self.identity)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, production)
        self.assertRegex(first, r"^pmr1_[0-9a-f]{64}$")
        self.assertNotIn(self.identity.subject, first)
        self.assertNotIn(self.identity.issuer, first)

    def test_identity_and_record_validation_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "issuer"):
            PlatformMemberIdentity("https://example.invalid", self.identity.subject)
        with self.assertRaisesRegex(ValueError, "subject"):
            PlatformMemberIdentity(CANONICAL_GOOGLE_ISSUER, "bad\nsubject")
        with self.assertRaisesRegex(ValueError, "environment"):
            member_reference("Staging", self.identity)

        reference = member_reference("staging", self.identity)
        with self.assertRaisesRegex(ValueError, "lifecycle"):
            MemberRecord(reference, "removed", 1, 100, 100)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "cursor"):
            MemberRecord(reference, "active", 0, 100, 100)
        with self.assertRaisesRegex(ValueError, "timestamps"):
            MemberRecord(reference, "active", 1, 101, 100)

    def test_in_memory_adapter_exposes_only_exact_lookup(self) -> None:
        record = MemberRecord(
            member_reference("staging", self.identity),
            "active",
            1,
            100,
            100,
        )
        directory = InMemoryMemberDirectory((record,))

        observed = asyncio.run(
            directory.lookup_current_member("staging", self.identity)
        )
        absent = asyncio.run(
            directory.lookup_current_member(
                "staging",
                PlatformMemberIdentity(
                    CANONICAL_GOOGLE_ISSUER,
                    "987654321098765432109",
                ),
            )
        )

        self.assertEqual(observed, record)
        self.assertIsNone(absent)
        self.assertEqual(
            tuple(field.name for field in fields(record)),
            (
                "member_reference",
                "lifecycle",
                "mutation_cursor",
                "created_at",
                "updated_at",
            ),
        )
        self.assertFalse(hasattr(directory, "list_members"))
        self.assertFalse(hasattr(directory, "put_member"))
        self.assertFalse(hasattr(directory, "delete_member"))

    def test_unavailable_adapter_never_fabricates_membership(self) -> None:
        directory = InMemoryMemberDirectory(available=False)

        with self.assertRaisesRegex(
            MemberDirectoryUnavailable,
            "member directory unavailable",
        ):
            asyncio.run(
                directory.lookup_current_member("staging", self.identity)
            )

    def test_firestore_adapter_reads_only_the_derived_current_member_key(self) -> None:
        value = {
            "contract_version": 1,
            "lifecycle": "active",
            "mutation_cursor": 4,
            "created_at": 100,
            "updated_at": 200,
        }
        client = _Firestore(value)
        lookup = FirestoreCurrentMemberLookup(client)

        observed = asyncio.run(
            lookup.lookup_current_member("staging", self.identity)
        )

        reference = member_reference("staging", self.identity)
        self.assertEqual(client.requests, [(MEMBER_COLLECTION_NAME, reference)])
        self.assertEqual(
            observed,
            MemberRecord(reference, "active", 4, 100, 200),
        )
        self.assertFalse(hasattr(lookup, "list_members"))
        self.assertFalse(hasattr(lookup, "put_member"))

    def test_firestore_adapter_collapses_missing_malformed_and_provider_failure(self) -> None:
        missing = FirestoreCurrentMemberLookup(_Firestore(None))
        self.assertIsNone(
            asyncio.run(missing.lookup_current_member("staging", self.identity))
        )

        malformed_values = (
            {"contract_version": 1, "lifecycle": "active"},
            {
                "contract_version": True,
                "lifecycle": "active",
                "mutation_cursor": 1,
                "created_at": 100,
                "updated_at": 100,
            },
            {
                "contract_version": 2,
                "lifecycle": "active",
                "mutation_cursor": 1,
                "created_at": 100,
                "updated_at": 100,
            },
            {
                "contract_version": 1,
                "lifecycle": "removed",
                "mutation_cursor": 1,
                "created_at": 100,
                "updated_at": 100,
            },
        )
        for value in malformed_values:
            with self.subTest(value=value), self.assertRaisesRegex(
                MemberDirectoryUnavailable,
                "member directory unavailable",
            ):
                asyncio.run(
                    FirestoreCurrentMemberLookup(_Firestore(value)).lookup_current_member(
                        "staging",
                        self.identity,
                    )
                )

        with self.assertRaisesRegex(
            MemberDirectoryUnavailable,
            "member directory unavailable",
        ):
            asyncio.run(
                FirestoreCurrentMemberLookup(
                    _Firestore(None, error=PermissionError("private provider detail"))
                ).lookup_current_member("staging", self.identity)
            )


if __name__ == "__main__":
    unittest.main()
