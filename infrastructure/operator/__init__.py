"""Small public interface for the AP-M9 interactive lifecycle module."""

from infrastructure.operator._core import LifecycleOperator
from infrastructure.operator._interfaces import (
    DiscoverySnapshot,
    ExecutionResult,
    GitSnapshot,
    OperatorInterrupted,
    OperatorAdapters,
    PrepareResult,
    StageContext,
    StageExecution,
    StatusResult,
)
from infrastructure.operator.deployment import DeploymentExecutor
from infrastructure.operator.integration import (
    ApplicationIntegrationLifecycle,
    AttachmentTargetReadback,
    AttachmentTargetReader,
    AttachmentValidationResult,
    GenerationActivationReadback,
    GenerationPublicationReadback,
    IntegrationBundleRequest,
    IntegrationBundleResult,
    PlatformIntegrationReader,
    PlatformIntegrationState,
    RegistrationGenerationControl,
    RegistrationGenerationProposal,
    RegistrationIntent,
    RegistrationLifecycleResult,
)

__all__ = (
    "DiscoverySnapshot",
    "DeploymentExecutor",
    "ExecutionResult",
    "GitSnapshot",
    "ApplicationIntegrationLifecycle",
    "AttachmentTargetReadback",
    "AttachmentTargetReader",
    "AttachmentValidationResult",
    "GenerationActivationReadback",
    "GenerationPublicationReadback",
    "IntegrationBundleRequest",
    "IntegrationBundleResult",
    "LifecycleOperator",
    "OperatorInterrupted",
    "OperatorAdapters",
    "PrepareResult",
    "PlatformIntegrationReader",
    "PlatformIntegrationState",
    "RegistrationGenerationControl",
    "RegistrationGenerationProposal",
    "RegistrationIntent",
    "RegistrationLifecycleResult",
    "StageContext",
    "StageExecution",
    "StatusResult",
)
