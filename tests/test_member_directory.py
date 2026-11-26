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


if __name__ == "__main__":
    unittest.main()
