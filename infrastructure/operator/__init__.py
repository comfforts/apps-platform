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

__all__ = (
    "DiscoverySnapshot",
    "ExecutionResult",
    "GitSnapshot",
    "LifecycleOperator",
    "OperatorInterrupted",
    "OperatorAdapters",
    "PrepareResult",
    "StageContext",
    "StageExecution",
    "StatusResult",
)
