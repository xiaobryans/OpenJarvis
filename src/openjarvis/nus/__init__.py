"""NUS — Next-generation Upgrade System package.

NUS 1A: Learning Foundation (local, read-only, no self-modification).
"""
from openjarvis.nus.learning_foundation import (
    AgentScorecard,
    CapabilitySignal,
    FailurePatternRecord,
    LearningFoundation,
    LearningSignal,
    LearningSnapshot,
    TaskOutcomeRecord,
    get_learning_foundation,
)

__all__ = [
    "AgentScorecard",
    "CapabilitySignal",
    "FailurePatternRecord",
    "LearningFoundation",
    "LearningSignal",
    "LearningSnapshot",
    "TaskOutcomeRecord",
    "get_learning_foundation",
]
