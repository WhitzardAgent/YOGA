"""
Yoga-Next package initialization.

This package contains the core components for the Yoga-Next project.
"""

# Import core modules to make them available at package level
from . import core
from . import model
from . import planner
from . import prompts
from . import utils
from . import agent_config

__version__ = "0.1.0"
__author__ = "Yoga-Next Team"
__all__ = [
    "core",
    "model",
    "planner",
    "prompts",
    "utils",
    "agent_config"
]