"""Closed command boundary for AP-M9-W7 application integration operations."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from contracts.lifecycle import lifecycle_digest, load_lifecycle_document
from infrastructure.operator.cli import main
from infrastructure.operator.integration import (
    IntegrationBundleRequest,
    IntegrationBundleResult,
    LifecycleChangeRequest,
    RegistrationIntent,
    RegistrationLifecycleResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTORS = PROJECT_ROOT / "contracts/lifecycle/test-vectors/valid"
SOURCE_REVISION = "a" * 40
GENERATION_DIGEST = "sha256:" + ("7" * 64)


class FakeIntegrationLifecycle:
    def __init__(self) -> None:
        self.outputs_requests: list[IntegrationBundleRequest] = []
        self.registrations: list[
            tuple[dict[str, object], dict[str, object], RegistrationIntent]
        ] = []
        self.detaches: list[LifecycleChangeRequest] = []
        self.retirements: list[LifecycleChangeRequest] = []

    def outputs(self, request: IntegrationBundleRequest) -> IntegrationBundleResult:
        self.outputs_requests.append(request)
        bundle = json.loads(
            (
                VECTORS
                / "platform-integration-bundle.staging.synthetic.v1.json"
            ).read_text(encoding="utf-8")
        )
        return IntegrationBundleResult(
            outcome="generated",
            bundle=bundle,
            bundle_digest=lifecycle_digest(
                bundle,
                "platform-integration-bundle",
            ),
        )

    def register(
        self,
        integration_bundle: dict[str, object],
        attachment_bundle: dict[str, object],
        intent: RegistrationIntent,
    ) -> RegistrationLifecycleResult:
        self.registrations.append(
            (integration_bundle, attachment_bundle, intent)
        )
        return RegistrationLifecycleResult(
            outcome="activated",
            generation=7,
            generation_digest=GENERATION_DIGEST,
        )

    def detach(
        self,
        request: LifecycleChangeRequest,
    ) -> RegistrationLifecycleResult:
        self.detaches.append(request)
        return RegistrationLifecycleResult(
            outcome="activated",
            generation=8,
            generation_digest=GENERATION_DIGEST,
        )

    def retire(
        self,
        request: LifecycleChangeRequest,
    ) -> RegistrationLifecycleResult:
        self.retirements.append(request)
        return RegistrationLifecycleResult(
            outcome="activated",
            generation=9,
            generation_digest=GENERATION_DIGEST,
        )


def _run(
    arguments: list[str],
    lifecycle: FakeIntegrationLifecycle,
) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            arguments,
            integration_factory=lambda _: lifecycle,
        )
    return exit_code, json.loads(output.getvalue())


class IntegrationCliTest(unittest.TestCase):
    def test_outputs_writes_one_canonical_create_only_bundle(self) -> None:
        lifecycle = FakeIntegrationLifecycle()
        with tempfile.TemporaryDirectory() as directory:
            state_directory = Path(directory) / "operator"
            arguments = [
                "outputs",
                "--environment",
                "staging",
                "--state-directory",
                str(state_directory),
                "--application-id",
                "fixture-authenticated",
                "--access-mode",
                "authenticated",
                "--route-intent",
                "/fixture-authenticated",
                "--platform-source-revision",
                SOURCE_REVISION,
                "--platform-generation",
                "1",
            ]

            first_code, first = _run(arguments, lifecycle)
            second_code, second = _run(arguments, lifecycle)

            bundle_path = state_directory / str(first["bundle_path"])
            loaded = load_lifecycle_document(
                bundle_path,
                "platform-integration-bundle",
            )

        self.assertEqual((first_code, second_code), (0, 0))
        self.assertEqual(first, second)
        self.assertEqual(first["outcome"], "generated")
        self.assertEqual(loaded.violations, ())
        self.assertEqual(len(lifecycle.outputs_requests), 2)
        self.assertEqual(
            lifecycle.outputs_requests[0].expected_platform_source_revision,
            SOURCE_REVISION,
        )

    def test_register_reads_strict_private_inputs_and_emits_coarse_result(self) -> None:
        lifecycle = FakeIntegrationLifecycle()
        with tempfile.TemporaryDirectory() as directory:
            intent_path = Path(directory) / "registration-intent.json"
            intent_path.write_text(
                json.dumps(
                    {
                        "attachment_id": "primary",
                        "catalogue_summary": "Synthetic qualification application",
                        "catalogue_title": "Fixture application",
                        "catalogue_visibility": "listed",
                        "forwarding_mode": "strip_application_prefix",
                        "mount_path": "/",
                        "restricted_members": [],
                    }
                ),
                encoding="utf-8",
            )
            code, result = _run(
                [
                    "register",
                    "--environment",
                    "staging",
                    "--integration-bundle",
                    str(
                        VECTORS
                        / "platform-integration-bundle.staging.synthetic.v1.json"
                    ),
                    "--attachment-bundle",
                    str(
                        VECTORS
                        / "application-attachment-bundle.staging.synthetic.v1.json"
                    ),
                    "--registration-intent",
                    str(intent_path),
                ],
                lifecycle,
            )

        self.assertEqual(code, 0)
        self.assertEqual(result["outcome"], "activated")
        self.assertEqual(result["generation"], 7)
        self.assertNotIn("restricted_members", json.dumps(result))
        self.assertNotIn("resource_reference", json.dumps(result))
        self.assertEqual(len(lifecycle.registrations), 1)
        self.assertEqual(lifecycle.registrations[0][2].attachment_id, "primary")

    def test_detach_and_retire_preserve_exact_preconditions(self) -> None:
        lifecycle = FakeIntegrationLifecycle()
        base = [
            "--environment",
            "staging",
            "--application-id",
            "fixture-authenticated",
            "--platform-source-revision",
            SOURCE_REVISION,
            "--generation-digest",
            GENERATION_DIGEST,
        ]

        detach_code, detach_result = _run(["detach", *base], lifecycle)
        retire_code, retire_result = _run(["retire", *base], lifecycle)

        self.assertEqual((detach_code, retire_code), (0, 0))
        self.assertEqual(detach_result["generation"], 8)
        self.assertEqual(retire_result["generation"], 9)
        self.assertEqual(
            lifecycle.detaches[0],
            LifecycleChangeRequest(
                environment="staging",
                application_id="fixture-authenticated",
                expected_platform_source_revision=SOURCE_REVISION,
                expected_generation_digest=GENERATION_DIGEST,
            ),
        )
        self.assertEqual(lifecycle.retirements[0], lifecycle.detaches[0])

    def test_unarmed_local_adapter_fails_closed_without_external_action(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["outputs", "--environment", "staging"])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(
            result["blockers"],
            ["APPLICATION_INTEGRATION_ADAPTER_UNAVAILABLE"],
        )


if __name__ == "__main__":
    unittest.main()
