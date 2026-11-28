"""Local adapters and private storage for plural-fixture qualification."""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from contracts.lifecycle import (
    canonical_lifecycle_bytes,
    lifecycle_digest,
    versioned_lifecycle_digest,
)
from infrastructure.operator._interfaces import GitSnapshot
from infrastructure.operator.cli import main
from infrastructure.operator.fixture_lifecycle import (
    FixtureApplicationDeployRequest,
    FixtureDeployRequest,
    FixtureImageReadback,
)
from infrastructure.operator.fixture_qualification import (
    FixtureQualificationReadback,
    FixtureQualificationResult,
    FixtureQualificationTarget,
)
from infrastructure.operator.integration import (
    AttachmentTargetReadback,
    PlatformIntegrationState,
    RegistrationAttachmentBinding,
    RegistrationGenerationProposal,
    RegistrationIntent,
)
from infrastructure.operator.local import LocalFilesystem
from infrastructure.operator.local_fixture_qualification import (
    LocalFailedTargetQualification,
    LocalFixtureAttachmentVerifier,
    LocalFixtureQualificationEvidence,
    LocalFixtureQualificationStateReader,
)
from infrastructure.operator.local_fixture_preparations import (
    LocalFixturePreparations,
)
from infrastructure.operator.local_handoffs import (
    ApplicationHandoffRecord,
    LocalApplicationHandoffs,
)
from infrastructure.operator.integration import ApplicationIntegrationLifecycle
from tests.environment import FIXTURES_PROJECT_ID
from tests.test_fixture_deployment_lifecycle import (
    Commands,
    EDGE_CALLER,
    NETWORK,
    SOURCE,
    SUBNET,
    _bundle,
)


AUDIENCE = (
    "urn:comfforts:app-platform:audience:fixture-multi-attachment"
)
GENERATION_DIGEST = "sha256:" + ("9" * 64)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_VECTOR = (
    PROJECT_ROOT
    / "contracts/lifecycle/test-vectors/valid/"
    "qualification-evidence.staging.synthetic.v1.json"
)


def _intent() -> RegistrationIntent:
    return RegistrationIntent(
        application_id="fixture-multi-attachment",
        access_mode="authenticated",
        identity_delivery="required",
        catalogue_visibility="unlisted",
        catalogue_title="Multi-Attachment Fixture",
        catalogue_summary="Synthetic authenticated multi-attachment fixture",
        attachment_id="web",
        mount_path="/",
        forwarding_mode="strip_application_prefix",
        contract_version=3,
        additional_attachment_bindings=(
            RegistrationAttachmentBinding(
                "api",
                "/api",
                "strip_attachment_mount",
            ),
        ),
    )


def _readback() -> FixtureQualificationReadback:
    bundle = _bundle("fixture-multi-attachment")
    image = FixtureImageReadback(
        f"us-west1-docker.pkg.dev/{FIXTURES_PROJECT_ID}/"
        "app-platform-images/fixture@sha256:" + ("4" * 64),
        SOURCE,
    )
    deployment = Commands().deploy_application(
        FixtureApplicationDeployRequest(
            "staging",
            "fixture-multi-attachment",
            "authenticated",
            "unlisted",
            SOURCE,
            image,
            bundle,
        )
    )
    attachment = deployment.attachment_bundle
    return FixtureQualificationReadback(
        environment="staging",
        application_id="fixture-multi-attachment",
        source_authority="candidate",
        platform_qualification_digest="sha256:" + ("1" * 64),
        platform_source_revision=str(bundle["platform_source_revision"]),
        fixture_source_revision=SOURCE,
        integration_bundle_digest=versioned_lifecycle_digest(
            bundle,
            "platform-integration-bundle",
        ),
        attachment_bundle_digest=versioned_lifecycle_digest(
            attachment,
            "application-attachment-bundle",
        ),
        registration_generation=8,
        registration_generation_digest=GENERATION_DIGEST,
        targets=(
            FixtureQualificationTarget(
                "api",
                "/api",
                str(
                    attachment["additional_attachments"][0]["target"][
                        "resource_reference"
                    ]
                ),
                AUDIENCE,
            ),
            FixtureQualificationTarget(
                "web",
                "/",
                str(attachment["target"]["resource_reference"]),
                AUDIENCE,
            ),
        ),
        integration_bundle=bundle,
        attachment_bundle=attachment,
        registration_intent=_intent().document(),
    )


class Platform:
    def __init__(self, current: FixtureQualificationReadback) -> None:
        self.current = current

    def read_platform(self, environment: str) -> PlatformIntegrationState:
        bundle = self.current.integration_bundle
        return PlatformIntegrationState(
            environment=environment,
            lifecycle_state="deployed",
            profile_digest=str(bundle["profile_digest"]),
            platform_source_revision=str(bundle["platform_source_revision"]),
            specification_digest=str(bundle["specification_digest"]),
            progress_digest=str(bundle["deployment_progress_digest"]),
            generation=int(bundle["generation"]),
            hostname="apps-staging.comfforts.com",
            oauth_client_id=str(bundle["identity"]["oauth_client_id"]),
            edge_caller_reference=EDGE_CALLER,
            qualification_status=str(bundle["qualification_status"]),
            source_authority=str(bundle["platform_source_authority"]),
        )


class Targets:
    def __init__(self, current: FixtureQualificationReadback) -> None:
        self.current = current

    def read_target(
        self,
        environment: str,
        resource_reference: str,
    ) -> AttachmentTargetReadback:
        del environment
        if resource_reference.endswith("-missing"):
            return AttachmentTargetReadback(
                False,
                False,
                "",
                "gcp-cloud-run-v1",
                resource_reference,
                "unavailable",
                "",
                None,
            )
        return AttachmentTargetReadback(
            exists=True,
            ready=True,
            owner_application_id="fixture-multi-attachment",
            adapter_kind="gcp-cloud-run-v1",
            resource_reference=resource_reference,
            ingress_mode="shared_edge_only",
            caller_grant=EDGE_CALLER,
            audience=AUDIENCE,
            application_project_id=FIXTURES_PROJECT_ID,
            network_reference=NETWORK,
            subnetwork_reference=SUBNET,
            egress_mode="all-traffic",
        )


@dataclass
class Generations:
    proposal: RegistrationGenerationProposal
    reads: int = 0

    def current(self, environment: str) -> RegistrationGenerationProposal:
        self.reads += 1
        if environment != self.proposal.environment:
            raise ValueError("environment mismatch")
        return self.proposal


def _generations() -> Generations:
    return Generations(
        RegistrationGenerationProposal(
            environment="staging",
            registration_set={
                "contract_version": 2,
                "generation": 8,
                "registrations": [],
            },
            compiled_configuration={},
            ownership_manifest={},
            generation_digest=GENERATION_DIGEST,
            content_digest="sha256:" + ("8" * 64),
        )
    )


class LocalFixtureQualificationTest(unittest.TestCase):
    def test_state_reader_binds_accepted_platform_v3_handoff_and_active_v2_set(
        self,
    ) -> None:
        current = _readback()
        bundle = current.integration_bundle
        attachment = current.attachment_bundle
        intent = _intent()

        class Git:
            def inspect(self) -> GitSnapshot:
                return GitSnapshot(
                    repository="comfforts/apps-platform",
                    revision=SOURCE,
                    branch="feat/fixture-scoped-qualification",
                    clean=True,
                    main_revision="c" * 40,
                    origin_main_revision="c" * 40,
                    upstream_branch=(
                        "origin/feat/fixture-scoped-qualification"
                    ),
                    upstream_revision=SOURCE,
                    origin_main_ancestor=True,
                )

        active_registration = ApplicationIntegrationLifecycle._application_registration(
            bundle,
            attachment,
            intent,
            "active",
            1,
        )
        generations = Generations(
            RegistrationGenerationProposal(
                environment="staging",
                registration_set={
                    "contract_version": 2,
                    "generation": 8,
                    "registrations": [active_registration],
                },
                compiled_configuration={},
                ownership_manifest={},
                generation_digest=GENERATION_DIGEST,
                content_digest="sha256:" + ("8" * 64),
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            filesystem = LocalFilesystem(PROJECT_ROOT, Path(directory) / "operator")
            preparations = LocalFixturePreparations(filesystem)
            request = FixtureDeployRequest(
                environment="staging",
                application_id="fixture-multi-attachment",
                fixture_source_revision=SOURCE,
                expected_platform_source_revision=str(
                    bundle["platform_source_revision"]
                ),
                expected_platform_generation=int(bundle["generation"]),
                catalogue_visibility="unlisted",
                source_authority="candidate",
            )
            image = FixtureImageReadback(
                f"us-west1-docker.pkg.dev/{FIXTURES_PROJECT_ID}/"
                "app-platform-images/fixture@sha256:" + ("4" * 64),
                SOURCE,
            )
            deployment = Commands().deploy_application(
                FixtureApplicationDeployRequest(
                    "staging",
                    "fixture-multi-attachment",
                    "authenticated",
                    "unlisted",
                    SOURCE,
                    image,
                    bundle,
                )
            )
            preparations.publish(
                request,
                image,
                bundle,
                deployment,
                intent,
            )
            handoffs = LocalApplicationHandoffs(filesystem)
            handoffs.record(
                ApplicationHandoffRecord(
                    environment="staging",
                    application_id="fixture-multi-attachment",
                    application_source_revision=SOURCE,
                    integration_bundle_digest=current.integration_bundle_digest,
                    attachment_bundle_digest=current.attachment_bundle_digest,
                    attachment_revision=1,
                    registration_generation=8,
                    registration_generation_digest=GENERATION_DIGEST,
                )
            )
            evidence = json.loads(EVIDENCE_VECTOR.read_bytes())
            evidence_digest = lifecycle_digest(
                evidence,
                "qualification-evidence",
            )
            evidence_path = (
                "environments/staging/qualification/evidence/"
                f"{evidence_digest[7:]}.v1.json"
            )
            filesystem.write_state(
                evidence_path,
                canonical_lifecycle_bytes(evidence, "qualification-evidence")
                + b"\n",
                replace=False,
            )
            filesystem.write_state(
                "environments/staging/qualification/current-evidence.v1.json",
                json.dumps(
                    {
                        "evidence_digest": evidence_digest,
                        "outcome": "qualified",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n",
                replace=True,
            )
            reader = LocalFixtureQualificationStateReader(
                filesystem,
                Git(),
                generations,
                preparations,
                handoffs,
                "candidate",
            )

            observed = reader.read_current(
                "staging",
                "fixture-multi-attachment",
            )

        self.assertEqual(observed.platform_qualification_digest, evidence_digest)
        self.assertEqual(observed.fixture_source_revision, SOURCE)
        self.assertEqual(observed.registration_generation, 8)
        self.assertEqual(
            tuple((item.attachment_id, item.mount_path) for item in observed.targets),
            (("api", "/api"), ("web", "/")),
        )

    def test_provider_and_failed_target_checks_use_no_generation_mutation(self) -> None:
        current = _readback()
        targets = Targets(current)
        integration = ApplicationIntegrationLifecycle(
            Platform(current),
            attachment_reader=targets,
        )
        verifier = LocalFixtureAttachmentVerifier(integration, targets)
        generations = _generations()

        posture = verifier.verify_attachment_set(current)
        denial = verifier.verify_direct_origin_denial(current)
        failed = LocalFailedTargetQualification(
            Platform(current),
            targets,
            generations,
        ).verify(current)

        self.assertTrue(posture.verified)
        self.assertTrue(denial.verified)
        self.assertTrue(failed.verified)
        self.assertEqual(failed.facts["rejected_candidates"], 2)
        self.assertEqual(failed.facts["publication_attempts"], 0)
        self.assertEqual(failed.facts["activation_attempts"], 0)
        self.assertEqual(generations.reads, 2)

    def test_evidence_uses_separate_candidate_result_and_status_tree(self) -> None:
        current = _readback()
        result = {
            "application_id": current.application_id,
            "attachment_bundle_digest": current.attachment_bundle_digest,
            "checks": [],
            "document_kind": "fixture-qualification-result",
            "environment": "staging",
            "fixture_source_revision": current.fixture_source_revision,
            "format_version": 1,
            "integration_bundle_digest": current.integration_bundle_digest,
            "limitations": [],
            "platform_qualification_digest": current.platform_qualification_digest,
            "platform_source_revision": current.platform_source_revision,
            "registration_generation": current.registration_generation,
            "registration_generation_digest": current.registration_generation_digest,
            "source_authority": "candidate",
            "targets": [],
            "verdict": "qualified",
        }
        payload = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "operator"
            evidence = LocalFixtureQualificationEvidence(
                LocalFilesystem(Path(__file__).resolve().parents[1], state)
            )

            publication = evidence.publish(result, digest)

            self.assertIn("fixture-qualification/candidates", publication.result_path)
            self.assertIn("fixture-qualification/candidates", publication.status_path)
            self.assertTrue((state / publication.result_path).is_file())
            status = json.loads((state / publication.status_path).read_bytes())
            self.assertEqual(status["outcome"], "candidate-qualified")
            self.assertFalse(
                (state / "environments/staging/qualification/current-evidence.v1.json").exists()
            )

    def test_cli_dispatches_fixture_qualify_without_platform_owner_input(self) -> None:
        @dataclass
        class Qualification:
            calls: list[tuple[str, str]]

            def qualify_current(self, environment: str, application_id: str):  # type: ignore[no-untyped-def]
                self.calls.append((environment, application_id))
                return FixtureQualificationResult(
                    "qualified",
                    {},
                    "sha256:" + ("1" * 64),
                    "fixture/result.json",
                    "fixture/status.json",
                )

        qualification = Qualification([])
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "fixture-qualify",
                    "--environment",
                    "staging",
                    "--application-id",
                    "fixture-multi-attachment",
                ],
                fixture_qualification_factory=lambda _path, _authority: qualification,
            )

        value = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(value["outcome"], "qualified")
        self.assertEqual(
            qualification.calls,
            [("staging", "fixture-multi-attachment")],
        )

    def test_live_factory_names_missing_gcloud_without_partial_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "operator"
            output = io.StringIO()
            with mock.patch(
                "infrastructure.operator.local.shutil.which",
                return_value=None,
            ), redirect_stdout(output):
                code = main(
                    [
                        "fixture-qualify",
                        "--environment",
                        "staging",
                        "--application-id",
                        "fixture-multi-attachment",
                        "--state-directory",
                        str(state),
                    ]
                )

            value = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(value["outcome"], "blocked")
            self.assertEqual(
                value["blockers"],
                ["GCLOUD_EXECUTABLE_UNAVAILABLE"],
            )
            self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()
