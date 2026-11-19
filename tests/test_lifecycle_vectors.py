"""Reviewed AP-M9-W3 synthetic lifecycle vectors."""

from __future__ import annotations

from pathlib import Path
import unittest

from contracts.lifecycle import (
    PROFILE_DIRECTORY,
    load_lifecycle_document,
    validate_lifecycle_relationships,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIRECTORY = PROJECT_ROOT / "contracts" / "lifecycle" / "test-vectors" / "valid"
VECTORS = {
    "application-attachment-bundle.staging.synthetic.v1.json": (
        "application-attachment-bundle",
        "sha256:88bbbefbe9f753c77c97bcdca07efe4f854b1b6f16dec6ced95e760a4c63aa04",
    ),
    "deployment-specification.staging.synthetic.v1.json": (
        "deployment-specification",
        "sha256:2a4bd4b6d78de880d8872d04609013aedd6dae77441d9c56a3865d748438545e",
    ),
    "environment-status.staging.synthetic.v1.json": (
        "environment-status",
        "sha256:3c7112d4e812a505e4769e65c4ab8ac008c994f368f3efc41f51c714278ffd88",
    ),
    "execution-journal.staging.synthetic.v1.json": (
        "execution-journal",
        "sha256:70dda6f7bdc74d992a417c15ea7d7c6e3d364c7346fa59f65e545ec3cfb2df99",
    ),
    "platform-integration-bundle.staging.synthetic.v1.json": (
        "platform-integration-bundle",
        "sha256:6fc56779c115978e38f3db5d2cad671c482f898bbab911f2fb523b9ca7865af7",
    ),
}


class LifecycleVectorTest(unittest.TestCase):
    def test_exact_reviewed_vectors_are_canonical_and_digest_stable(self) -> None:
        self.assertEqual(
            sorted(path.name for path in VECTOR_DIRECTORY.glob("*.json")),
            sorted(VECTORS),
        )
        for filename, (kind, expected_digest) in VECTORS.items():
            with self.subTest(filename=filename):
                loaded = load_lifecycle_document(VECTOR_DIRECTORY / filename, kind)

                self.assertEqual(loaded.violations, ())
                self.assertIsNotNone(loaded.value)
                self.assertEqual(loaded.digest, expected_digest)

    def test_reviewed_vector_chain_is_cross_document_valid(self) -> None:
        def value(filename: str) -> dict[str, object]:
            kind = VECTORS[filename][0]
            loaded = load_lifecycle_document(VECTOR_DIRECTORY / filename, kind)
            assert loaded.value is not None
            return loaded.value

        profile = load_lifecycle_document(
            PROFILE_DIRECTORY / "staging.v1.json",
            "environment-profile",
        )
        assert profile.value is not None

        self.assertEqual(
            validate_lifecycle_relationships(
                profile=profile.value,
                specification=value(
                    "deployment-specification.staging.synthetic.v1.json"
                ),
                journal=value("execution-journal.staging.synthetic.v1.json"),
                status=value("environment-status.staging.synthetic.v1.json"),
                integration_bundle=value(
                    "platform-integration-bundle.staging.synthetic.v1.json"
                ),
                attachment_bundle=value(
                    "application-attachment-bundle.staging.synthetic.v1.json"
                ),
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
