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
        "sha256:87c53c012f9aaade05943983eb0b1bc80a99491038fd8efafef8507ff0776694",
    ),
    "deployment-specification.staging.synthetic.v1.json": (
        "deployment-specification",
        "sha256:0c307e09e19262701855d8ec92e3a93e6027b639b40a749c5765ee89d5da46c1",
    ),
    "environment-status.staging.synthetic.v1.json": (
        "environment-status",
        "sha256:160c03afb53895ae188f94564c2086c71e367530c9aba0943a76f7c7d3308d5c",
    ),
    "execution-journal.staging.synthetic.v1.json": (
        "execution-journal",
        "sha256:07039c77d05224c98a14d2111e5f09bfb20d928ba82dcb8704853d003bb29091",
    ),
    "platform-integration-bundle.staging.synthetic.v1.json": (
        "platform-integration-bundle",
        "sha256:462f3c33853b9c63cb2fa23645766e86cba4f1f525a09d3890d59e2e3f8b2db0",
    ),
    "qualification-evidence.staging.synthetic.v1.json": (
        "qualification-evidence",
        "sha256:24df3c604305298ee24086c94294b16a3d0257bddde1de996c0a84a569ce1e7c",
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
