"""Exact authoritative and recursive DNS deployment readback."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import unittest

from infrastructure.operator.deployment_dns import (
    ClosedDigRunner,
    DigDnsReadback,
    DnsCommandRequest,
    DnsCommandResult,
    DnsReadbackError,
)


ADDRESS = "34.120.10.20"


@dataclass
class FakeDig:
    propagated: bool = True
    requests: list[DnsCommandRequest] = field(default_factory=list)

    def run(self, request: DnsCommandRequest) -> DnsCommandResult:
        self.requests.append(request)
        arguments = request.argv[1:]
        if arguments == ("+short", "NS", "comfforts.com."):
            return DnsCommandResult(
                0,
                b"ns-cloud-a1.googledomains.com.\nns-cloud-a2.googledomains.com.\n",
                b"",
            )
        if arguments[:2] == ("+noall", "+answer"):
            server = arguments[2]
            if not self.propagated and server == "@1.1.1.1":
                return DnsCommandResult(0, b"", b"")
            ttl = "1800" if server.startswith("@ns-") else "725"
            answer = f"apps-staging.comfforts.com. {ttl} IN A {ADDRESS}\n"
            return DnsCommandResult(0, answer.encode("ascii"), b"")
        return DnsCommandResult(2, b"", b"unexpected")


class DeploymentDnsTest(unittest.TestCase):
    def _reader(self, directory: str, fake: FakeDig) -> DigDnsReadback:
        root = Path(directory)
        executable = root / "dig"
        executable.write_bytes(b"binary")
        executable.chmod(0o700)
        return DigDnsReadback(executable, root, fake)

    def test_all_authoritative_and_recursive_answers_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeDig()
            result = self._reader(directory, fake).read(ADDRESS)

        self.assertTrue(result.ready)
        self.assertRegex(result.attestation or "", r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(fake.requests), 5)
        self.assertEqual(
            [request.argv[3] for request in fake.requests[1:]],
            [
                "@ns-cloud-a1.googledomains.com.",
                "@ns-cloud-a2.googledomains.com.",
                "@1.1.1.1",
                "@8.8.8.8",
            ],
        )

    def test_missing_recursive_answer_is_waiting_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._reader(directory, FakeDig(propagated=False)).read(ADDRESS)

        self.assertFalse(result.ready)
        self.assertIsNone(result.attestation)

    def test_authoritative_ttl_mismatch_stops_readback(self) -> None:
        @dataclass
        class WrongTtl(FakeDig):
            def run(self, request: DnsCommandRequest) -> DnsCommandResult:
                result = super().run(request)
                if request.argv[3:4] == ("@ns-cloud-a1.googledomains.com.",):
                    return DnsCommandResult(
                        0,
                        f"apps-staging.comfforts.com. 300 IN A {ADDRESS}\n".encode(),
                        b"",
                    )
                return result

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                DnsReadbackError,
                "DNS_AUTHORITATIVE_TTL_MISMATCH",
            ):
                self._reader(directory, WrongTtl()).read(ADDRESS)

    def test_closed_runner_rejects_record_mutation_and_alternate_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "dig"
            executable.write_bytes(b"binary")
            runner = ClosedDigRunner(executable, root)
            unsafe = (
                DnsCommandRequest(
                    (str(executable), "apps.comfforts.com", "A"),
                    root,
                ),
                DnsCommandRequest(
                    (str(executable), "+short", "AAAA", "apps-staging.comfforts.com."),
                    root,
                ),
            )

            for request in unsafe:
                with self.subTest(argv=request.argv), self.assertRaises(ValueError):
                    runner.validate(request)


if __name__ == "__main__":
    unittest.main()
