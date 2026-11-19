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
    IntegrationBundleRequest,
    IntegrationBundleResult,
    PlatformIntegrationReader,
    PlatformIntegrationState,
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
    "IntegrationBundleRequest",
    "IntegrationBundleResult",
    "LifecycleOperator",
    "OperatorInterrupted",
    "OperatorAdapters",
    "PrepareResult",
    "PlatformIntegrationReader",
    "PlatformIntegrationState",
    "StageContext",
    "StageExecution",
    "StatusResult",
)
