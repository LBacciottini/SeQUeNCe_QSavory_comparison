"""SeQUeNCe adapter for the shared cross-validation configuration."""

from .mapping import inspect_sequence_configuration
from .simulation import run_sequence

__all__ = ["inspect_sequence_configuration", "run_sequence"]
