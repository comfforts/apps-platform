"""Reviewed AP-M9-W3 synthetic lifecycle vectors."""

from __future__ import annotations

from pathlib import Path
import unittest

from contracts.lifecycle import (
    PROFILE_DIRECTORY,
    load_lifecycle_document,
    load_versioned_lifecycle_document,
    validate_lifecycle_relationships,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIRECTORY = PROJECT_ROOT / "contracts" / "lifecycle" / "test-vectors" / "valid"
VECTORS = {
    "application-attachment-bundle.staging.synthetic.v1.json": (
        "application-attachment-bundle",
        "sha256:443fd2dddd7b6bc91533c1e616671eab7fe32f58e2ffc598ed7bb246175d2755",
    ),
    "application-attachment-bundle.staging.synthetic.v2.json": (
        "application-attachment-bundle",
        "sha256:d4f64aa2b2a13736f74fd8e86cd9bb6e4fdba5df27540b0375eca2bfffa7780d",
    ),
    "platform-integration-bundle.staging.synthetic.v1.json": (
        "platform-integration-bundle",
        "sha256:7108636efee7842b364f2d4605dbfe89f4da1bed5e56d872c9e09733bc0494c1",
    ),
    "platform-integration-bundle.staging.synthetic.v2.json": (
        "platform-integration-bundle",
        "sha256:36ea2480010791dcf7a37aeeb493e17a4e7af91131f1f7f4219ffb87203c3d9e",
    ),
    "qualification-evidence.staging.synthetic.v1.json": (
        "qualification-evidence",
        "sha256:96dbf65339fc57d97049f1daa5632834c9bd194b2ba5193ad8a42028948eef1f",
    ),
    "registration-intent.staging.synthetic.v2.json": (
        "registration-intent",
        "sha256:21ca9faf32aa6554aefa0ee1448a5469e02f66bd495f4ff7c54a7bf774934d8e",
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
                loader = (
                    load_versioned_lifecycle_document
                    if ".v2." in filename
                    else load_lifecycle_document
                )
                loaded = loader(VECTOR_DIRECTORY / filename, kind)

                self.assertEqual(loaded.violations, ())
                self.assertIsNotNone(loaded.value)
                self.assertEqual(loaded.digest, expected_digest)

    def test_reviewed_handoff_pair_is_cross_document_valid(self) -> None:
        def value(filename: str) -> dict[str, object]:
            kind = VECTORS[filename][0]
            loaded = load_lifecycle_document(VECTOR_DIRECTORY / filename, kind)
            assert loaded.value is not None
            return loaded.value

        integration = value(
            "platform-integration-bundle.staging.synthetic.v1.json"
        )
        attachment = value(
            "application-attachment-bundle.staging.synthetic.v1.json"
        )
        from contracts.lifecycle import lifecycle_digest

        attachment["platform_integration_bundle_digest"] = lifecycle_digest(
            integration,
            "platform-integration-bundle",
        )
        self.assertEqual(
            validate_lifecycle_relationships(
                integration_bundle=integration,
                attachment_bundle=attachment,
            ),
            (),
        )


if __name__ == "__main__":
    unittest.main()
