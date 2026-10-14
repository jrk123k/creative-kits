"""Continuity checker for draft continuity."""

__version__ = "2.0.0"

from continuity_checker.engine import check
from continuity_checker.rules import RuleError, load_rules

__all__ = ["__version__", "check", "load_rules", "RuleError"]
