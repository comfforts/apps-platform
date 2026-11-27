"""Least-data fixture handoff record tests."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest

from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationDeployment,
    FixtureDeployRequest,
    FixtureImageReadback,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_fixture_preparations import (
    LocalFixturePreparations,
)
from infrastructure.operator.local_handoffs import LocalApplicationHandoffs
from infrastructure.operator.integration import RegistrationIntent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTORS = PROJECT_ROOT / "contracts/lifecycle/test-vectors/valid"
GENERATION_DIGEST = "sha256:" + ("7" * 64)


class LocalApplicationHandoffsTest(unittest.TestCase):
    def test_record_contains_only_qualification_revision_bindings(self) -> None:
        integration = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (
                VECTORS
                / "application-attachment-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            handoffs = LocalApplicationHandoffs(
                LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
            )
            record = handoffs.from_bundles(
                integration,
                attachment,
                7,
                GENERATION_DIGEST,
            )

            self.assertTrue(handoffs.record(record))
            observed = handoffs.read(
                "staging",
                "fixture-authenticated",
                GENERATION_DIGEST,
            )
            latest = handoffs.latest_for_application(
                "staging",
                "fixture-authenticated",
                8,
            )

        self.assertEqual(observed, record)
        self.assertEqual(observed.fixture_revision.application_id, record.application_id)
        self.assertEqual(latest, record)

    def test_bundle_binding_mismatch_is_rejected_before_state_write(self) -> None:
        integration = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (
                VECTORS
                / "application-attachment-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        attachment["platform_integration_bundle_digest"] = (
            "sha256:" + ("f" * 64)
        )
        with self.assertRaises(ValueError):
            LocalApplicationHandoffs.from_bundles(
                integration,
                attachment,
                7,
                GENERATION_DIGEST,
            )

    def test_new_attachment_revision_shares_unchanged_registration_generation(
        self,
    ) -> None:
        integration = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (
                VECTORS
                / "application-attachment-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        successor_attachment = dict(attachment)
        successor_attachment["application_source_revision"] = "c" * 40
        successor_attachment["attachment_revision"] = 2
        with tempfile.TemporaryDirectory() as directory:
            filesystem = LocalFilesystem(
                PROJECT_ROOT,
                Path(directory) / "operator",
            )
            handoffs = LocalApplicationHandoffs(filesystem)
            original = handoffs.from_bundles(
                integration,
                attachment,
                7,
                GENERATION_DIGEST,
            )
            successor = handoffs.from_bundles(
                integration,
                successor_attachment,
                7,
                GENERATION_DIGEST,
            )

            self.assertTrue(handoffs.record(original))
            self.assertTrue(handoffs.record(successor))
            self.assertTrue(handoffs.record(successor))
            observed = handoffs.read(
                "staging",
                "fixture-authenticated",
                GENERATION_DIGEST,
            )
            latest = handoffs.latest_for_application(
                "staging",
                "fixture-authenticated",
                7,
            )
            stored = tuple(
                filesystem.state_path(
                    "environments/staging/applications/"
                    "fixture-authenticated/handoffs"
                ).iterdir()
            )

        self.assertEqual(observed, successor)
        self.assertEqual(latest, successor)
        self.assertEqual(len(stored), 2)


class LocalFixturePreparationsTest(unittest.TestCase):
    def test_publishes_and_reads_canonical_inspectable_bundle_pair(self) -> None:
        integration = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        attachment = json.loads(
            (
                VECTORS
                / "application-attachment-bundle.staging.synthetic.v2.json"
            ).read_text(encoding="utf-8")
        )
        request = FixtureDeployRequest(
            environment="staging",
            application_id="fixture-authenticated",
            fixture_source_revision="b" * 40,
            expected_platform_source_revision="a" * 40,
            expected_platform_generation=1,
            catalogue_visibility="listed",
        )
        image = FixtureImageReadback(
            "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
            "app-platform/fixture@sha256:" + ("1" * 64),
            "b" * 40,
        )
        deployment = FixtureApplicationDeployment(
            "fixture-authenticated",
            image.reference,
            attachment,
        )
        with tempfile.TemporaryDirectory() as directory:
            filesystem = LocalFilesystem(
                PROJECT_ROOT,
                Path(directory) / "operator",
            )
            store = LocalFixturePreparations(filesystem)

            published = store.publish(
                request,
                image,
                integration,
                deployment,
            )
            published = store.publish_registration_intent(
                request,
                published,
                RegistrationIntent(
                    application_id="fixture-authenticated",
                    access_mode="authenticated",
                    identity_delivery="required",
                    catalogue_visibility="listed",
                    catalogue_title="Fixture authenticated",
                    catalogue_summary="Synthetic authenticated fixture",
                    attachment_id="primary",
                    mount_path="/",
                    forwarding_mode="strip_application_prefix",
                ),
            )
            observed = store.read(request)
            stale_requests = (
                replace(request, environment="production"),
                replace(request, application_id="fixture-public"),
                replace(request, fixture_source_revision="c" * 40),
                replace(request, expected_platform_source_revision="d" * 40),
                replace(request, expected_platform_generation=2),
                replace(request, source_authority="candidate"),
                replace(request, catalogue_visibility="unlisted"),
            )

            self.assertIsNotNone(observed)
            self.assertEqual(observed, published)
            for stale_request in stale_requests:
                with self.subTest(stale_request=stale_request):
                    self.assertIsNone(store.read(stale_request))

            self.assertEqual(
                json.loads(Path(published.integration_bundle_path).read_bytes()),
                integration,
            )
            self.assertEqual(
                json.loads(Path(published.attachment_bundle_path).read_bytes()),
                attachment,
            )
            self.assertEqual(
                stat.S_IMODE(Path(published.integration_bundle_path).stat().st_mode),
                0o600,
            )
            self.assertEqual(
                stat.S_IMODE(Path(published.attachment_bundle_path).stat().st_mode),
                0o600,
            )
            Path(published.attachment_bundle_path).write_text(
                "{}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "stored fixture preparation document is invalid",
            ):
                store.read(request)

            current_path = filesystem.state_path(
                "environments/staging/fixtures/fixture-authenticated/"
                "preparations/current.v1.json"
            )
            legacy = json.loads(current_path.read_bytes())
            legacy.pop("catalogue_visibility")
            legacy.pop("preparation_digest")
            legacy_payload = json.dumps(
                legacy,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            legacy["preparation_digest"] = (
                "sha256:" + hashlib.sha256(legacy_payload).hexdigest()
            )
            current_path.write_text(
                json.dumps(
                    legacy,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertIsNone(store.read(request))


if __name__ == "__main__":
    unittest.main()
