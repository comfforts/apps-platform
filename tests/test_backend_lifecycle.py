"""AP-M9-W5 backend lineage and rendering checks."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from infrastructure.backend import (
    EnvironmentUnavailableError,
    backend_declarations,
    operation_authorities,
    render_backend_declaration,
)


class BackendLifecycleTest(unittest.TestCase):
    def test_staging_defines_five_lineages_over_four_exclusive_buckets(self) -> None:
        declarations = backend_declarations("staging")

        self.assertEqual(
            tuple(declaration.phase for declaration in declarations),
            (
                "bootstrap",
                "platform-foundation",
                "shared-edge",
                "fixture-public",
                "fixture-authenticated",
                "fixture-restricted",
            ),
        )
        self.assertEqual(
            tuple(declaration.prefix for declaration in declarations),
            (
                "bootstrap",
                "platform",
                "platform",
                "fixtures/fixture-public",
                "fixtures/fixture-authenticated",
                "fixtures/fixture-restricted",
            ),
        )
        self.assertEqual(
            len({declaration.bucket for declaration in declarations}),
            4,
        )
        self.assertEqual(
            len(
                {
                    (declaration.bucket, declaration.prefix)
                    for declaration in declarations
                }
            ),
            5,
        )
        self.assertEqual(declarations[1].bucket, declarations[2].bucket)
        self.assertEqual(declarations[1].state_owner, "platform")
        self.assertEqual(declarations[2].state_owner, "platform")
        self.assertNotEqual(declarations[0].prefix, declarations[1].prefix)
        self.assertEqual(
            {declaration.environment for declaration in declarations},
            {"staging"},
        )

    def test_production_lineages_remain_unavailable(self) -> None:
        with self.assertRaisesRegex(
            EnvironmentUnavailableError,
            "OWNERSHIP_TRANSFER_REQUIRED",
        ):
            backend_declarations("production")

    def test_renderer_is_canonical_idempotent_and_path_bounded(self) -> None:
        declaration = backend_declarations("staging")[1]
        expected = (
            'terraform {\n'
            '  backend "gcs" {\n'
            '    bucket = "comfforts-ap-stg-455651441682-platform-state"\n'
            '    prefix = "platform"\n'
            '  }\n'
            '}\n'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = render_backend_declaration(
                declaration,
                root,
                "platform/backend.generated.tf",
            )
            second = render_backend_declaration(
                declaration,
                root,
                "platform/backend.generated.tf",
            )

            self.assertEqual(
                first.path,
                (root / "platform/backend.generated.tf").resolve(),
            )
            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(first.digest, second.digest)
            self.assertEqual(first.path.read_bytes(), expected)
            self.assertEqual(first.path.stat().st_mode & 0o777, 0o600)

            with self.assertRaisesRegex(ValueError, "escapes its approved root"):
                render_backend_declaration(
                    declaration,
                    root,
                    "../backend.generated.tf",
                )

    def test_renderer_refuses_to_replace_a_different_declaration(self) -> None:
        declarations = backend_declarations("staging")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            render_backend_declaration(
                declarations[0],
                root,
                "backend.generated.tf",
            )
            with self.assertRaisesRegex(FileExistsError, "different backend declaration"):
                render_backend_declaration(
                    declarations[1],
                    root,
                    "backend.generated.tf",
                )

    def test_operation_authorities_are_exact_short_lived_and_keyless(self) -> None:
        authorities = operation_authorities("staging")
        identities = [authority.service_account_email for authority in authorities]

        self.assertEqual(len(authorities), 31)
        self.assertEqual(len(set(identities)), 31)
        self.assertEqual(
            authorities[0].service_account_email,
            "ap-stg-bootstrap-bootstrap@comfforts-platform-non-prod.iam.gserviceaccount.com",
        )
        self.assertEqual(
            {authority.action for authority in authorities},
            {
                "apply",
                "bootstrap",
                "destroy",
                "plan",
                "readback",
                "recovery",
                "rollback",
            },
        )
        for authority in authorities:
            with self.subTest(identity=authority.service_account_email):
                self.assertEqual(authority.environment, "staging")
                self.assertEqual(authority.project_id, "comfforts-platform-non-prod")
                self.assertEqual(authority.token_lifetime_seconds, 3600)
                self.assertEqual(authority.credential_source, "short-lived-human-adc")
                self.assertFalse(authority.service_account_key_allowed)
                self.assertFalse(authority.self_administration_allowed)
                self.assertEqual(
                    authority.impersonation_environment,
                    (
                        (
                            "GOOGLE_IMPERSONATE_SERVICE_ACCOUNT",
                            authority.service_account_email,
                        ),
                    ),
                )

    def test_authorities_preserve_exact_root_and_backend_scope(self) -> None:
        declarations = backend_declarations("staging")
        lineages = {
            (item.terraform_root, item.bucket, item.prefix, item.state_owner, item.owner_id)
            for item in declarations
        }
        authorities = operation_authorities("staging")

        self.assertEqual(
            {
                (
                    item.terraform_root,
                    item.backend_bucket,
                    item.backend_prefix,
                    item.state_owner,
                    item.owner_id,
                )
                for item in authorities
            },
            lineages,
        )
        expected_access = {
            "apply": ("read-state", "write-state", "lock"),
            "bootstrap": (),
            "destroy": ("read-state", "write-state", "lock"),
            "plan": ("read-state", "lock"),
            "readback": ("read-metadata",),
            "recovery": ("read-state", "write-state", "lock", "recovery-copy"),
            "rollback": ("read-state", "write-state", "lock"),
        }
        expected_provider = {
            "apply": "mutate-owned-resources",
            "bootstrap": "create-backend-and-operation-identities",
            "destroy": "destroy-owned-resources",
            "plan": "read-owned-resources",
            "readback": "read-owned-resources",
            "recovery": "none",
            "rollback": "mutate-owned-resources",
        }
        for authority in authorities:
            self.assertEqual(
                authority.backend_access,
                expected_access[authority.action],
            )
            self.assertEqual(
                authority.provider_access,
                expected_provider[authority.action],
            )

    def test_production_operation_authorities_remain_unavailable(self) -> None:
        with self.assertRaisesRegex(
            EnvironmentUnavailableError,
            "OWNERSHIP_TRANSFER_REQUIRED",
        ):
            operation_authorities("production")


if __name__ == "__main__":
    unittest.main()
