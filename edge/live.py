"""Production composition for the Shared Edge Cloud Run process."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import logging
import os
import re
from typing import Any, Mapping
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession, Request
from google.cloud import firestore, kms, run_v2, storage
import google_crc32c
import httpx

from ._assertions import AssertionIssuer, CloudKmsAssertionKeys, KmsKeyVersion
from ._attachments import CloudRunAttachmentResolver, GoogleCloudRunMetadataProvider
from ._generation import GoogleCloudStorageGenerationSource
from ._identity import (
    AuthlibGoogleOidc,
    FirestoreIdentityStore,
    SecureTokenSource,
    SystemClock,
)
from ._observability import (
    ExactSessionOperatorAuthorizer,
    SecureCorrelationIdSource,
    StructuredLoggingCompletionSink,
)
from ._proxy import (
    BoundedApplicationProxy,
    GoogleAuthServiceIdentityTokenSource,
    HttpxApplicationTransport,
    ScopeTrustedClientClassifier,
    WebsocketsApplicationConnector,
)
from ._runtime import RuntimeAdapters, RuntimeConfiguration, create_app


_SOURCE_REVISION = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
_REGION = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_SUBJECT = re.compile(r"[1-9][0-9]{5,63}")
_SECRET_VERSION = re.compile(
    r"projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/secrets/"
    r"[A-Za-z][A-Za-z0-9_-]{0,254}/versions/[1-9][0-9]{0,18}"
)
_EDGE_CALLER = re.compile(
    r"serviceAccount:[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com"
)
_REQUIRED_ENVIRONMENT = (
    "APP_PLATFORM_CONFIGURATION_BUCKET",
    "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST",
    "APP_PLATFORM_CONFIGURATION_OBJECT",
    "APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION",
    "APP_PLATFORM_EDGE_CALLER_PRINCIPAL",
    "APP_PLATFORM_GENERATION_DIGEST",
    "APP_PLATFORM_ISSUER",
    "APP_PLATFORM_IDENTITY_CLIENT_ID",
    "APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION",
    "APP_PLATFORM_OPERATOR_ISSUER",
    "APP_PLATFORM_OPERATOR_SUBJECT",
    "APP_PLATFORM_PROJECT_ID",
    "APP_PLATFORM_REGION",
    "APP_PLATFORM_SIGNING_KEY_VERSION",
    "APP_PLATFORM_SOURCE_REVISION",
)


class LiveConfigurationError(RuntimeError):
    """A safe startup failure caused by incomplete or invalid process input."""


@dataclass(frozen=True, slots=True)
class LiveRuntimeSettings:
    """Complete non-secret settings for one immutable Shared Edge revision."""

    source_revision: str
    project_id: str
    region: str
    external_origin: str
    generation_bucket: str
    generation_object: str
    generation_object_generation: int
    generation_content_digest: str
    generation_digest: str
    oauth_client_id: str
    oauth_client_secret_version: str
    signing_key_version: str
    edge_caller_principal: str
    operator_issuer: str
    operator_subject: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> LiveRuntimeSettings:
        missing = tuple(name for name in _REQUIRED_ENVIRONMENT if not environment.get(name))
        if missing:
            raise LiveConfigurationError("LIVE_RUNTIME_CONFIGURATION_INCOMPLETE")
        try:
            object_generation = int(
                environment["APP_PLATFORM_CONFIGURATION_OBJECT_GENERATION"]
            )
        except ValueError as error:
            raise LiveConfigurationError("LIVE_RUNTIME_CONFIGURATION_INVALID") from error

        issuer = environment["APP_PLATFORM_ISSUER"]
        project_id = environment["APP_PLATFORM_PROJECT_ID"]
        region = environment["APP_PLATFORM_REGION"]
        secret_version = environment["APP_PLATFORM_OAUTH_CLIENT_SECRET_VERSION"]
        signing_key_version = environment["APP_PLATFORM_SIGNING_KEY_VERSION"]
        edge_caller = environment["APP_PLATFORM_EDGE_CALLER_PRINCIPAL"]
        operator_issuer = environment["APP_PLATFORM_OPERATOR_ISSUER"]
        operator_subject = environment["APP_PLATFORM_OPERATOR_SUBJECT"]
        if (
            _SOURCE_REVISION.fullmatch(environment["APP_PLATFORM_SOURCE_REVISION"])
            is None
            or _PROJECT_ID.fullmatch(project_id) is None
            or _REGION.fullmatch(region) is None
            or object_generation < 1
            or _DIGEST.fullmatch(
                environment["APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST"]
            )
            is None
            or _DIGEST.fullmatch(environment["APP_PLATFORM_GENERATION_DIGEST"])
            is None
            or not issuer.startswith("https://")
            or not issuer.endswith("/_platform")
            or _SECRET_VERSION.fullmatch(secret_version) is None
            or not secret_version.startswith(f"projects/{project_id}/")
            or not signing_key_version.startswith(
                f"projects/{project_id}/locations/{region}/keyRings/"
            )
            or _EDGE_CALLER.fullmatch(edge_caller) is None
            or not edge_caller.endswith(f"@{project_id}.iam.gserviceaccount.com")
            or operator_issuer != "https://accounts.google.com"
            or _SUBJECT.fullmatch(operator_subject) is None
        ):
            raise LiveConfigurationError("LIVE_RUNTIME_CONFIGURATION_INVALID")

        settings = cls(
            source_revision=environment["APP_PLATFORM_SOURCE_REVISION"],
            project_id=project_id,
            region=region,
            external_origin=issuer.removesuffix("/_platform"),
            generation_bucket=environment["APP_PLATFORM_CONFIGURATION_BUCKET"],
            generation_object=environment["APP_PLATFORM_CONFIGURATION_OBJECT"],
            generation_object_generation=object_generation,
            generation_content_digest=environment[
                "APP_PLATFORM_CONFIGURATION_CONTENT_DIGEST"
            ],
            generation_digest=environment["APP_PLATFORM_GENERATION_DIGEST"],
            oauth_client_id=environment["APP_PLATFORM_IDENTITY_CLIENT_ID"],
            oauth_client_secret_version=secret_version,
            signing_key_version=signing_key_version,
            edge_caller_principal=edge_caller,
            operator_issuer=operator_issuer,
            operator_subject=operator_subject,
        )
        try:
            settings.runtime_configuration()
            KmsKeyVersion(settings.key_id, settings.signing_key_version)
        except ValueError as error:
            raise LiveConfigurationError("LIVE_RUNTIME_CONFIGURATION_INVALID") from error
        return settings

    @property
    def key_id(self) -> str:
        return f"kms-{self.signing_key_version.rsplit('/', maxsplit=1)[-1]}"

    def runtime_configuration(self) -> RuntimeConfiguration:
        return RuntimeConfiguration(
            profile="qualification-v1",
            source_revision=self.source_revision,
            generation_bucket=self.generation_bucket,
            generation_object=self.generation_object,
            generation_object_generation=self.generation_object_generation,
            generation_content_digest=self.generation_content_digest,
            generation_digest=self.generation_digest,
            external_origin=self.external_origin,
        )


@dataclass(frozen=True, slots=True)
class LiveClients:
    """Injected provider and transport clients used to compose the live process."""

    storage: Any
    firestore: Any
    cloud_run: Any
    kms: Any
    auth_request: Any
    http: httpx.AsyncClient


def access_oauth_client_secret(
    version: str,
    session: Any | None = None,
) -> str:
    """Read one exact Secret Manager version without exposing its payload."""

    if _SECRET_VERSION.fullmatch(version) is None:
        raise LiveConfigurationError("OAUTH_SECRET_VERSION_INVALID")
    if session is None:
        credentials, _ = google.auth.default(
            scopes=("https://www.googleapis.com/auth/cloud-platform",)
        )
        session = AuthorizedSession(credentials)
    url = (
        "https://secretmanager.googleapis.com/v1/"
        f"{quote(version, safe='/')}:access"
    )
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        document = response.json()
        payload = document["payload"]
        encoded = payload["data"]
        expected_crc = int(payload["dataCrc32c"])
        if not isinstance(encoded, str):
            raise ValueError
        contents = base64.b64decode(encoded, validate=True)
        if not contents or len(contents) > 16_384:
            raise ValueError
        if google_crc32c.value(contents) != expected_crc:
            raise ValueError
        secret = contents.decode("utf-8")
        if not secret or "\x00" in secret:
            raise ValueError
        return secret
    except Exception as error:
        raise LiveConfigurationError("OAUTH_SECRET_ACCESS_FAILED") from error


def build_live_app(
    settings: LiveRuntimeSettings,
    clients: LiveClients,
    oauth_client_secret: str,
) -> Any:
    """Compose every production adapter without performing provider discovery."""

    clock = SystemClock()
    tokens = SecureTokenSource()
    signing_key = KmsKeyVersion(settings.key_id, settings.signing_key_version)
    assertion_keys = CloudKmsAssertionKeys(
        clients.kms,
        active_key=signing_key,
        published_keys=(signing_key,),
    )
    service_tokens = GoogleAuthServiceIdentityTokenSource(clients.auth_request)
    application_proxy = BoundedApplicationProxy(
        HttpxApplicationTransport(clients.http, service_tokens),
        WebsocketsApplicationConnector(service_tokens),
    )
    adapters = RuntimeAdapters(
        generation_source=GoogleCloudStorageGenerationSource(clients.storage),
        attachment_resolver=CloudRunAttachmentResolver(
            GoogleCloudRunMetadataProvider(clients.cloud_run),
            settings.edge_caller_principal,
        ),
        google_oidc=AuthlibGoogleOidc(
            client_id=settings.oauth_client_id,
            client_secret=oauth_client_secret,
        ),
        identity_store=FirestoreIdentityStore(clients.firestore),
        clock=clock,
        token_source=tokens,
        assertion_issuer=AssertionIssuer(assertion_keys, clock, tokens),
        verification_key_source=assertion_keys,
        application_proxy=application_proxy,
        trusted_client_classifier=ScopeTrustedClientClassifier(),
        operator_authorizer=ExactSessionOperatorAuthorizer(
            ((settings.operator_issuer, settings.operator_subject),)
        ),
        correlation_ids=SecureCorrelationIdSource(),
        completion_events=StructuredLoggingCompletionSink(
            logging.getLogger("comfforts.shared_edge")
        ),
    )
    return create_app(settings.runtime_configuration(), adapters)


def create_live_app() -> Any:
    """Uvicorn factory for the immutable Cloud Run Shared Edge revision."""

    settings = LiveRuntimeSettings.from_environment(os.environ)
    clients = LiveClients(
        storage=storage.Client(project=settings.project_id),
        firestore=firestore.AsyncClient(
            project=settings.project_id,
            database="(default)",
        ),
        cloud_run=run_v2.ServicesAsyncClient(),
        kms=kms.KeyManagementServiceAsyncClient(),
        auth_request=Request(),
        http=httpx.AsyncClient(),
    )
    secret = access_oauth_client_secret(settings.oauth_client_secret_version)
    return build_live_app(settings, clients, secret)


__all__ = (
    "LiveClients",
    "LiveConfigurationError",
    "LiveRuntimeSettings",
    "access_oauth_client_secret",
    "build_live_app",
    "create_live_app",
)
