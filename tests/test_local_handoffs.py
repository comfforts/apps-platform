"""Least-data fixture handoff record tests."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTORS = PROJECT_ROOT / "contracts/lifecycle/test-vectors/valid"
GENERATION_DIGEST = "sha256:" + ("7" * 64)


class LocalApplicationHandoffsTest(unittest.TestCase):
    def test_record_contains_only_qualification_revision_bindings(self) -> None:
        integration = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v1.json"
            ).read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (
                VECTORS
                / "application-attachment-bundle.staging.synthetic.v1.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            handoffs = LocalApplicationHandoffs(
                LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
            )
            record = handoffs.from_bundles(
                integration,
                attachment,
                GENERATION_DIGEST,
            )

            self.assertTrue(handoffs.record(record))
            observed = handoffs.read(
                "staging",
                "fixture-authenticated",
                GENERATION_DIGEST,
            )

        self.assertEqual(observed, record)
        self.assertEqual(observed.fixture_revision.application_id, record.application_id)

    def test_bundle_binding_mismatch_is_rejected_before_state_write(self) -> None:
        integration = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v1.json"
            ).read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (
                VECTORS
                / "application-attachment-bundle.staging.synthetic.v1.json"
            ).read_text(encoding="utf-8")
        )
        attachment["platform_integration_bundle_digest"] = (
            "sha256:" + ("f" * 64)
        )
        with self.assertRaises(ValueError):
            LocalApplicationHandoffs.from_bundles(
                integration,
                attachment,
                GENERATION_DIGEST,
            )


if __name__ == "__main__":
    unittest.main()
