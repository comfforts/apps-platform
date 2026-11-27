"""Deterministic tests for the synchronous Firestore member-write adapter."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from infrastructure.member_directory import (
    DIRECTORY_COLLECTION_NAME,
    DIRECTORY_DOCUMENT_NAME,
    MEMBER_COLLECTION_NAME,
)
from infrastructure.operator.local_members import FirestoreMemberDirectoryProvider
from infrastructure.operator.member_lifecycle import (
    MemberMutation,
    MemberPredecessorStale,
    MemberProviderUnavailable,
)


REFERENCE = "pmr1_" + "4" * 64


class Snapshot:
    """Represent one exact fake document snapshot."""

    def __init__(self, document_id: str, value: dict[str, object] | None) -> None:
        self.id = document_id
        self.exists = value is not None
        self._value = value

    def to_dict(self) -> dict[str, object] | None:
        """Return an isolated provider-shaped document value."""

        return dict(self._value) if self._value is not None else None


class Document:
    """Expose exact get addressing and no query surface."""

    def __init__(self, client: Client, collection: str, document_id: str) -> None:
        self._client = client
        self.collection = collection
        self.document_id = document_id

    def get(self, *, transaction: object | None = None) -> Snapshot:
        """Read the selected document and record its transaction boundary."""

        self._client.reads.append((self.collection, self.document_id, transaction))
        if self._client.failure is not None:
            raise self._client.failure
        return Snapshot(
            self.document_id,
            self._client.values.get((self.collection, self.document_id)),
        )


class Query:
    """Provide only the bounded bootstrap-emptiness projection."""

    def __init__(self, client: Client, collection: str, limit: int) -> None:
        self._client = client
        self._collection = collection
        self._limit = limit

    def stream(self, *, transaction: object | None = None):  # type: ignore[no-untyped-def]
        """Yield at most the exact configured limit without returning a public list."""

        self._client.queries.append((self._collection, self._limit, transaction))
        selected = sorted(
            (
                (document_id, value)
                for (collection, document_id), value in self._client.values.items()
                if collection == self._collection
            ),
            key=lambda item: item[0],
        )[: self._limit]
        return iter(Snapshot(document_id, value) for document_id, value in selected)


class Collection:
    """Select exact documents or the bootstrap-only bounded query."""

    def __init__(self, client: Client, name: str) -> None:
        self._client = client
        self._name = name

    def document(self, document_id: str) -> Document:
        """Return one exact document reference."""

        return Document(self._client, self._name, document_id)

    def limit(self, count: int) -> Query:
        """Return a bounded query used only for initial emptiness proof."""

        return Query(self._client, self._name, count)


class Transaction:
    """Apply writes immediately for one deterministic atomic-test boundary."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, document: Document, value: dict[str, object]) -> None:
        """Create a document only when the fake predecessor remains absent."""

        key = (document.collection, document.document_id)
        if key in self._client.values:
            raise RuntimeError("document already exists")
        self._client.values[key] = dict(value)

    def set(self, document: Document, value: dict[str, object]) -> None:
        """Replace one exact document."""

        self._client.values[(document.collection, document.document_id)] = dict(value)

    def delete(self, document: Document) -> None:
        """Delete one exact document idempotently."""

        self._client.values.pop((document.collection, document.document_id), None)


class Client:
    """Credential-free named-database client fake."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], dict[str, object]] = {}
        self.reads: list[tuple[str, str, object | None]] = []
        self.queries: list[tuple[str, int, object | None]] = []
        self.failure: Exception | None = None
        self.transactions: list[tuple[int, Transaction]] = []

    def collection(self, name: str) -> Collection:
        """Select one collection in the named database fake."""

        return Collection(self, name)

    def transaction(self, *, max_attempts: int) -> Transaction:
        """Record the exact one-attempt transaction policy."""

        transaction = Transaction(self)
        self.transactions.append((max_attempts, transaction))
        return transaction


class FirestoreMemberDirectoryProviderTest(unittest.TestCase):
    """Verify exact translation, transaction, readback, and error boundaries."""

    def setUp(self) -> None:
        self.client = Client()
        self.provider = FirestoreMemberDirectoryProvider({"staging": self.client})

    def test_bootstrap_uses_bounded_empty_probe_and_one_atomic_successor(self) -> None:
        predecessor = self.provider.read("staging", REFERENCE, probe_empty=True)
        mutation = MemberMutation(
            "staging",
            "bootstrap-owner",
            REFERENCE,
            predecessor,
            1_700_000_001,
        )

        with patch(
            "infrastructure.operator.local_members.transactional",
            lambda function: function,
        ):
            result = self.provider.mutate(mutation)

        self.assertEqual(result.control.mutation_cursor if result.control else None, 1)
        self.assertEqual(result.member.member_reference if result.member else None, REFERENCE)
        self.assertEqual(self.client.transactions[0][0], 1)
        self.assertTrue(
            any(
                collection == MEMBER_COLLECTION_NAME and limit == 2
                for collection, limit, _ in self.client.queries
            )
        )
        self.assertEqual(
            self.client.values[(DIRECTORY_COLLECTION_NAME, DIRECTORY_DOCUMENT_NAME)][
                "mutation_cursor"
            ],
            1,
        )

    def test_lifecycle_update_and_removal_advance_control_without_enumeration(self) -> None:
        with patch(
            "infrastructure.operator.local_members.transactional",
            lambda function: function,
        ):
            initial = self.provider.read("staging", REFERENCE, probe_empty=True)
            active = self.provider.mutate(
                MemberMutation(
                    "staging", "bootstrap-owner", REFERENCE, initial, 100
                )
            )
            suspended = self.provider.mutate(
                MemberMutation("staging", "suspend", REFERENCE, active, 200)
            )
            removed = self.provider.mutate(
                MemberMutation("staging", "remove", REFERENCE, suspended, 300)
            )

        self.assertEqual(suspended.member.lifecycle if suspended.member else None, "suspended")
        self.assertIsNone(removed.member)
        self.assertEqual(removed.control.mutation_cursor if removed.control else None, 3)
        self.assertNotIn((MEMBER_COLLECTION_NAME, REFERENCE), self.client.values)
        self.assertEqual(len(self.client.queries), 2)

    def test_stale_and_provider_failures_do_not_become_success(self) -> None:
        predecessor = self.provider.read("staging", REFERENCE, probe_empty=True)
        self.client.values[(DIRECTORY_COLLECTION_NAME, DIRECTORY_DOCUMENT_NAME)] = {
            "contract_version": 1,
            "initialized": True,
            "mutation_cursor": 1,
            "created_at": 100,
            "updated_at": 100,
        }
        with patch(
            "infrastructure.operator.local_members.transactional",
            lambda function: function,
        ), self.assertRaises(MemberPredecessorStale):
            self.provider.mutate(
                MemberMutation(
                    "staging", "bootstrap-owner", REFERENCE, predecessor, 200
                )
            )

        self.client.failure = PermissionError("private provider detail")
        with self.assertRaisesRegex(
            MemberProviderUnavailable,
            "member directory unavailable",
        ) as raised:
            self.provider.read("staging", REFERENCE)
        self.assertNotIn("private provider detail", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
