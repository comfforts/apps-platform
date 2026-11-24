"""AP-M9-W5 backend lineage and rendering checks."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from infrastructure.backend import (
    EnvironmentUnavailableError,
    backend_declarations,
    render_backend_declaration,
)


class BackendLifecycleTest(unittest.TestCase):
    def test_staging_defines_six_lineages_over_two_owner_buckets(self) -> None:
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
            2,
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

if __name__ == "__main__":
    unittest.main()
