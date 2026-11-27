"""Immutable compiled-generation loading for the Shared Edge."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from contracts import load_json_bytes, validate_contract_instance

if TYPE_CHECKING:
    from google.cloud import storage


COMPILED_CONFIGURATION_SCHEMAS = {
    1: "urn:comfforts:app-platform:schema:compiled-shared-edge:v1",
    2: "urn:comfforts:app-platform:schema:compiled-shared-edge:v2",
}
MAX_GENERATION_BYTES = 1_048_576


class GenerationSource(Protocol):
    async def load(
        self,
        *,
        bucket: str,
        object_name: str,
        object_generation: int,
    ) -> bytes:
        """Read one exact immutable object generation as bytes."""

        ...


class GoogleCloudStorageGenerationSource:
    """Read one exact object generation through an injected Cloud Storage client."""

    def __init__(self, client: storage.Client) -> None:
        self._client = client

    async def load(
        self,
        *,
        bucket: str,
        object_name: str,
        object_generation: int,
    ) -> bytes:
        """Download one immutable object generation with provider checksums."""

        def download() -> bytes:
            blob = self._client.bucket(bucket).blob(
                object_name,
                generation=object_generation,
            )
            return blob.download_as_bytes(
                start=0,
                end=MAX_GENERATION_BYTES,
                raw_download=True,
                if_generation_match=object_generation,
                checksum="auto",
            )

        return await asyncio.to_thread(download)


@dataclass(frozen=True, slots=True)
class GenerationBinding:
    """Exact immutable provider object and logical generation binding."""

    bucket: str
    object_name: str
    object_generation: int
    content_digest: str
    generation_digest: str


@dataclass(frozen=True, slots=True)
class LoadedGeneration:
    """Validated compiled configuration retained for one process lifetime."""

    configuration: dict[str, Any]
    content_digest: str
    generation_digest: str


class GenerationLoadError(RuntimeError):
    """A safe generation-startup failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def load_generation(
    binding: GenerationBinding,
    source: GenerationSource,
) -> LoadedGeneration:
    """Load and validate one immutable Version 1 or Version 2 generation.

    Provider failures, malformed JSON, unsupported versions, schema failures,
    and either digest mismatch become stable startup codes.  The source is read
    once; callers retain the returned configuration for the process lifetime.
    """

    try:
        payload = await source.load(
            bucket=binding.bucket,
            object_name=binding.object_name,
            object_generation=binding.object_generation,
        )
    except Exception as error:
        raise GenerationLoadError("GENERATION_SOURCE_UNAVAILABLE") from error

    if not isinstance(payload, bytes):
        raise GenerationLoadError("GENERATION_DOCUMENT_INVALID")

    content_digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    if content_digest != binding.content_digest:
        raise GenerationLoadError("GENERATION_CONTENT_DIGEST_MISMATCH")

    document = load_json_bytes(payload, max_bytes=MAX_GENERATION_BYTES)
    if document.violations or not isinstance(document.value, dict):
        raise GenerationLoadError("GENERATION_DOCUMENT_INVALID")

    contract_version = document.value.get("contract_version")
    schema = COMPILED_CONFIGURATION_SCHEMAS.get(contract_version)
    if schema is None:
        raise GenerationLoadError("GENERATION_CONTRACT_INVALID")
    violations = validate_contract_instance(document.value, schema)
    if violations:
        raise GenerationLoadError("GENERATION_CONTRACT_INVALID")
    if document.value["generation_digest"] != binding.generation_digest:
        raise GenerationLoadError("GENERATION_DIGEST_MISMATCH")

    return LoadedGeneration(
        configuration=document.value,
        content_digest=content_digest,
        generation_digest=binding.generation_digest,
    )
