"""Authoritative and independent recursive DNS readback for staging."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
from pathlib import Path
import re
import subprocess
from typing import Protocol


_ZONE = "comfforts.com."
_HOSTNAME = "apps-staging.comfforts.com."
_EXPECTED_TTL = 1800
_RECURSIVE_RESOLVERS = ("1.1.1.1", "8.8.8.8")
_DNS_NAME = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
)


class DnsReadbackError(RuntimeError):
    """Coarse DNS failure that never contains raw resolver output."""


@dataclass(frozen=True, slots=True)
class DnsCommandRequest:
    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: int = 20


@dataclass(frozen=True, slots=True)
class DnsCommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class DnsCommandRunner(Protocol):
    def run(self, request: DnsCommandRequest) -> DnsCommandResult: ...


class ClosedDigRunner:
    """Run only fixed NS and A-record readback commands without a shell."""

    def __init__(self, executable: Path, working_root: Path) -> None:
        self._executable = executable.resolve()
        self._working_root = working_root.resolve()

    def validate(self, request: DnsCommandRequest) -> None:
        if not request.argv or Path(request.argv[0]).resolve() != self._executable:
            raise ValueError("DNS command executable is outside the approved set")
        cwd = request.cwd.resolve()
        if cwd != self._working_root and self._working_root not in cwd.parents:
            raise ValueError("DNS command working directory escapes its root")
        if request.cwd.is_symlink() or not cwd.is_dir():
            raise ValueError("DNS command working directory is not real")
        if not 1 <= request.timeout_seconds <= 30:
            raise ValueError("DNS command timeout is outside the approved bound")
        arguments = request.argv[1:]
        ns_lookup = arguments == ("+short", "NS", _ZONE)
        answer_lookup = (
            len(arguments) == 5
            and arguments[:2] == ("+noall", "+answer")
            and arguments[2].startswith("@")
            and arguments[3:] == (_HOSTNAME, "A")
        )
        if not ns_lookup and not answer_lookup:
            raise ValueError("DNS command is outside the approved readback set")
        if answer_lookup:
            server = arguments[2].removeprefix("@").lower()
            if (
                server not in _RECURSIVE_RESOLVERS
                and _DNS_NAME.fullmatch(server) is None
            ):
                raise ValueError("DNS server is not a valid authoritative or recursive host")

    def run(self, request: DnsCommandRequest) -> DnsCommandResult:
        self.validate(request)
        completed = subprocess.run(
            list(request.argv),
            cwd=request.cwd,
            env={},
            check=False,
            capture_output=True,
            timeout=request.timeout_seconds,
        )
        return DnsCommandResult(
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )


@dataclass(frozen=True, slots=True)
class DnsReadback:
    ready: bool
    attestation: str | None = None


class DigDnsReadback:
    """Verify all authoritative servers and two independent recursive resolvers."""

    def __init__(
        self,
        executable: Path,
        working_root: Path,
        runner: DnsCommandRunner,
    ) -> None:
        self._executable = executable.resolve()
        self._working_root = working_root.resolve()
        self._runner = runner
        if not self._executable.is_file():
            raise ValueError("an absolute dig executable is required")
        if not self._working_root.is_dir() or self._working_root.is_symlink():
            raise ValueError("DNS working root must be real")

    def _run(self, *arguments: str) -> DnsCommandResult:
        try:
            return self._runner.run(
                DnsCommandRequest(
                    argv=(str(self._executable), *arguments),
                    cwd=self._working_root,
                )
            )
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            raise DnsReadbackError("DNS_COMMAND_REJECTED") from error

    @staticmethod
    def _lines(result: DnsCommandResult) -> tuple[str, ...]:
        if result.returncode != 0 or len(result.stdout) > 64 * 1024:
            raise DnsReadbackError("DNS_READBACK_FAILED")
        try:
            return tuple(
                line.strip().lower()
                for line in result.stdout.decode("ascii").splitlines()
                if line.strip()
            )
        except UnicodeDecodeError as error:
            raise DnsReadbackError("DNS_READBACK_INVALID") from error

    @staticmethod
    def _answer(lines: tuple[str, ...]) -> tuple[int, str] | None:
        if not lines:
            return None
        answers: list[tuple[int, str]] = []
        for line in lines:
            fields = line.split()
            if len(fields) != 5 or fields[0] != _HOSTNAME:
                raise DnsReadbackError("DNS_READBACK_INVALID")
            try:
                ttl = int(fields[1])
                address = str(ipaddress.IPv4Address(fields[4]))
            except (ValueError, ipaddress.AddressValueError) as error:
                raise DnsReadbackError("DNS_READBACK_INVALID") from error
            if fields[2:4] != ["in", "a"]:
                raise DnsReadbackError("DNS_READBACK_INVALID")
            answers.append((ttl, address))
        if len(set(answers)) != 1:
            raise DnsReadbackError("DNS_READBACK_CONFLICT")
        return answers[0]

    def read(self, expected_address: str) -> DnsReadback:
        try:
            expected = str(ipaddress.IPv4Address(expected_address))
        except ipaddress.AddressValueError as error:
            raise ValueError("expected DNS address must be IPv4") from error
        nameservers = self._lines(self._run("+short", "NS", _ZONE))
        if not nameservers:
            raise DnsReadbackError("DNS_AUTHORITATIVE_SERVERS_MISSING")
        if any(_DNS_NAME.fullmatch(value) is None for value in nameservers):
            raise DnsReadbackError("DNS_AUTHORITATIVE_SERVERS_INVALID")

        observations: list[str] = []
        for server in (*sorted(set(nameservers)), *_RECURSIVE_RESOLVERS):
            answer = self._answer(
                self._lines(
                    self._run(
                        "+noall",
                        "+answer",
                        f"@{server}",
                        _HOSTNAME,
                        "A",
                    )
                )
            )
            if answer is None or answer[1] != expected:
                return DnsReadback(False)
            if server in nameservers and answer[0] != _EXPECTED_TTL:
                raise DnsReadbackError("DNS_AUTHORITATIVE_TTL_MISMATCH")
            observations.append(f"{server}:{answer[1]}")
        payload = "\n".join(observations).encode("ascii")
        return DnsReadback(
            True,
            "sha256:" + hashlib.sha256(payload).hexdigest(),
        )

    def absent(self) -> DnsReadback:
        """Verify the staging A record is absent at every approved resolver."""

        nameservers = self._lines(self._run("+short", "NS", _ZONE))
        if not nameservers:
            raise DnsReadbackError("DNS_AUTHORITATIVE_SERVERS_MISSING")
        if any(_DNS_NAME.fullmatch(value) is None for value in nameservers):
            raise DnsReadbackError("DNS_AUTHORITATIVE_SERVERS_INVALID")
        observations: list[str] = []
        for server in (*sorted(set(nameservers)), *_RECURSIVE_RESOLVERS):
            answer = self._answer(
                self._lines(
                    self._run(
                        "+noall",
                        "+answer",
                        f"@{server}",
                        _HOSTNAME,
                        "A",
                    )
                )
            )
            if answer is not None:
                return DnsReadback(False)
            observations.append(f"{server}:absent")
        payload = "\n".join(observations).encode("ascii")
        return DnsReadback(
            True,
            "sha256:" + hashlib.sha256(payload).hexdigest(),
        )


__all__ = (
    "ClosedDigRunner",
    "DigDnsReadback",
    "DnsCommandRequest",
    "DnsCommandResult",
    "DnsCommandRunner",
    "DnsReadback",
    "DnsReadbackError",
)
