"""Private deterministic deployment-input rendering tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from contracts import validate_contract_instance
from infrastructure.backend import (
    PhasePlanRequest,
    backend_declarations,
    render_backend_declaration,
)
from infrastructure.operator._interfaces import StageContext
from infrastructure.operator.local_deployment import (
    DeploymentConfigurationRenderer,
    LocalDeploymentInputError,
    OperatorSessionFacts,
    initial_generation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "a" * 40
SPECIFICATION_DIGEST = "sha256:" + "9" * 64


def _session() -> OperatorSessionFacts:
    return OperatorSessionFacts(
        active_account="operator@example.com",
        billing_account_reference="billingAccounts/ABCDEF-123456-789ABC",
        operator_issuer="https://accounts.google.com",
        operator_subject="123456789012345678901",
    )


def _request(working_root: Path, phase: str) -> PhasePlanRequest:
    declaration = next(
        item for item in backend_declarations("staging") if item.phase == phase
    )
    rendered = render_backend_declaration(
        declaration,
        working_root,
        f"{phase}/backend.tf",
    )
    return PhasePlanRequest(
        environment="staging",
        source_revision=SOURCE_REVISION,
        phase=phase,
        terraform_root=declaration.terraform_root,
        state_owner=declaration.state_owner,
        owner_id=declaration.owner_id,
        project_id=declaration.project_id,
        backend_path=rendered.path,
        backend_digest=rendered.digest,
        backend_bucket=declaration.bucket,
        backend_prefix=declaration.prefix,
    )


def _context(
    stage_id: str,
    inputs: tuple[tuple[str, str], ...] = (),
) -> StageContext:
    return StageContext(
        environment="staging",
        source_revision=SOURCE_REVISION,
        specification_digest=SPECIFICATION_DIGEST,
        stage={"stage_id": stage_id},
        inputs=inputs,
    )


class LocalDeploymentInputsTest(unittest.TestCase):
    def test_initial_generation_is_empty_closed_and_revision_bound(self) -> None:
        generation = initial_generation(SOURCE_REVISION)

        self.assertEqual(generation.registration_set["registrations"], [])
        self.assertEqual(generation.compiled_configuration["catalogue"], [])
        self.assertEqual(generation.compiled_configuration["routes"], [])
        self.assertEqual(generation.compiled_configuration["admission_policies"], [])
        self.assertEqual(
            validate_contract_instance(
                generation.compiled_configuration,
                "urn:comfforts:app-platform:schema:compiled-shared-edge:v1",
            ),
            (),
        )
        reference = json.loads(generation.reference(17))
        self.assertEqual(reference["generation"], 1)
        self.assertEqual(reference["object_generation"], 17)
        self.assertEqual(reference["generation_digest"], generation.generation_digest)
        self.assertEqual(reference["content_digest"], generation.content_digest)

    def test_platform_bootstrap_input_manages_only_platform_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            working_root = Path(directory) / "work"
            renderer = DeploymentConfigurationRenderer(
                PROJECT_ROOT,
                working_root,
                _session(),
            )

            rendered = renderer.render(
                _context("bootstrap"),
                _request(working_root, "bootstrap"),
            )
            value = json.loads(rendered.variable_file.read_bytes())[
                "backend_configuration"
            ]
            variable_mode = os.stat(rendered.variable_file).st_mode & 0o777

        self.assertEqual(value["configuration_class"], "operator")
        self.assertEqual(len(value["state_buckets"]), 1)
        self.assertEqual(
            {item["owner_id"] for item in value["state_buckets"]},
            {"app-platform"},
        )
        self.assertEqual(variable_mode, 0o600)

    def test_foundation_uses_verified_account_without_channel_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            working_root = Path(directory) / "work"
            renderer = DeploymentConfigurationRenderer(
                PROJECT_ROOT,
                working_root,
                _session(),
            )

            rendered = renderer.render(
                _context("foundation"),
                _request(working_root, "platform-foundation"),
            )
            configuration = json.loads(rendered.variable_file.read_bytes())[
                "platform_configuration"
            ]

        foundation = configuration["foundation"]
        self.assertEqual(configuration["phase"], "foundation")
        self.assertIsNone(configuration["shared_edge"])
        self.assertEqual(foundation["notification_email"], "operator@example.com")
        self.assertEqual(
            foundation["billing_account_reference"],
            "billingAccounts/ABCDEF-123456-789ABC",
        )
        self.assertNotIn("notification_destination", foundation)

    def test_shared_edge_consumes_only_declared_generated_references(self) -> None:
        generation = initial_generation(SOURCE_REVISION)
        inputs = (
            (
                "foundation.foundation-reference",
                json.dumps(
                    {
                        "signing_key_version": (
                            "projects/comfforts-platform-non-prod/locations/us-west1/"
                            "keyRings/app-platform/cryptoKeys/edge-signing/"
                            "cryptoKeyVersions/1"
                        )
                    },
                    separators=(",", ":"),
                ),
            ),
            (
                "image-publish.shared-edge-image-digest",
                "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
                "app-platform-images/shared-edge@sha256:" + "3" * 64,
            ),
            (
                "oauth-configuration.oauth-client-id",
                "client.apps.googleusercontent.com",
            ),
            (
                "oauth-configuration.oauth-secret-version",
                "projects/comfforts-platform-non-prod/secrets/"
                "app-platform-edge-oauth/versions/1",
            ),
            (
                "generation-publish.registration-generation-reference",
                generation.reference(17),
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            working_root = Path(directory) / "work"
            renderer = DeploymentConfigurationRenderer(
                PROJECT_ROOT,
                working_root,
                _session(),
            )
            request = _request(working_root, "shared-edge")

            edge = renderer.render(_context("shared-edge", inputs), request)
            edge_configuration = json.loads(edge.variable_file.read_bytes())[
                "platform_configuration"
            ]
            tls = renderer.render(_context("tls-readiness", inputs), request)
            tls_configuration = json.loads(tls.variable_file.read_bytes())[
                "platform_configuration"
            ]

        self.assertFalse(edge_configuration["shared_edge"]["tls_enabled"])
        self.assertTrue(tls_configuration["shared_edge"]["tls_enabled"])
        self.assertEqual(
            edge_configuration["shared_edge"]["operator_identity"],
            {
                "issuer": "https://accounts.google.com",
                "subject": "123456789012345678901",
            },
        )
        self.assertEqual(
            edge_configuration["shared_edge"]["registration_generation"][
                "source_revision"
            ],
            SOURCE_REVISION,
        )

    def test_shared_edge_accepts_an_existing_content_addressed_generation(self) -> None:
        generation_digest = (
            "sha256:44080cfd4ef038237c33f3c2a883cf9ad63646e9f33adf44379b64055983cd25"
        )
        generation_reference = json.dumps(
            {
                "content_digest": (
                    "sha256:d5917d35a3190f314a5be589ea59c6808cd58790262b942f6916adba11218c8a"
                ),
                "generation": 2,
                "generation_digest": generation_digest,
                "object_generation": 84,
                "object_name": (
                    f"generations/{generation_digest[7:]}/"
                    "compiled-shared-edge.v1.json"
                ),
            },
            separators=(",", ":"),
        )
        inputs = (
            (
                "foundation.foundation-reference",
                json.dumps(
                    {
                        "signing_key_version": (
                            "projects/comfforts-platform-non-prod/locations/us-west1/"
                            "keyRings/app-platform/cryptoKeys/edge-signing/"
                            "cryptoKeyVersions/1"
                        )
                    },
                    separators=(",", ":"),
                ),
            ),
            (
                "image-publish.shared-edge-image-digest",
                "us-west1-docker.pkg.dev/comfforts-platform-non-prod/"
                "app-platform-images/shared-edge@sha256:" + ("3" * 64),
            ),
            (
                "oauth-configuration.oauth-client-id",
                "client.apps.googleusercontent.com",
            ),
            (
                "oauth-configuration.oauth-secret-version",
                "projects/comfforts-platform-non-prod/secrets/"
                "app-platform-edge-oauth/versions/1",
            ),
            (
                "generation-publish.registration-generation-reference",
                generation_reference,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            working_root = Path(directory) / "work"
            renderer = DeploymentConfigurationRenderer(
                PROJECT_ROOT,
                working_root,
                _session(),
            )

            rendered = renderer.render(
                _context("shared-edge", inputs),
                _request(working_root, "shared-edge"),
            )
            configuration = json.loads(rendered.variable_file.read_bytes())[
                "platform_configuration"
            ]

        self.assertEqual(
            configuration["shared_edge"]["registration_generation"]["object_name"],
            (
                f"generations/{generation_digest[7:]}/"
                "compiled-shared-edge.v1.json"
            ),
        )

    def test_cross_environment_and_missing_generated_inputs_fail_before_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            working_root = Path(directory) / "work"
            renderer = DeploymentConfigurationRenderer(
                PROJECT_ROOT,
                working_root,
                _session(),
            )
            request = _request(working_root, "shared-edge")

            with self.assertRaisesRegex(
                LocalDeploymentInputError,
                "SHARED_EDGE_INPUT_INCOMPLETE",
            ):
                renderer.render(_context("shared-edge"), request)


if __name__ == "__main__":
    unittest.main()
