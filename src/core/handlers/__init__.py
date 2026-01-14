"""
Recording Handlers Package

Provides focused handler classes for recording operations:
- RecoveryHandler: Crash recovery and auto-save
- PauseResumeHandler: Pause/resume state machine
- PeriodicAnalysisHandler: Real-time analysis during recording
- FinalizationHandler: Post-recording cleanup and queuing
"""

from core.handlers.recovery_handler import RecoveryHandler
from core.handlers.pause_resume_handler import PauseResumeHandler
from core.handlers.periodic_analysis_handler import PeriodicAnalysisHandler
from core.handlers.finalization_handler import FinalizationHandler

__all__ = [
    "RecoveryHandler",
    "PauseResumeHandler",
    "PeriodicAnalysisHandler",
    "FinalizationHandler",
]
