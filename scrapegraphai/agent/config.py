"""
Global configuration for GraphSpider Agent.
"""

from enum import Enum


class ExecutionMode(str, Enum):
    LOCAL = "local"
    DOCKER = "docker"   # reserved
    E2B = "e2b"         # reserved


class FixStrategy(str, Enum):
    SANITIZE = "sanitize"
    REGENERATE = "regenerate"
    STEALTH_BOOST = "stealth"


DEFAULT_AGENT_CONFIG = {
    "max_rounds": 3,
    "execution_timeout": 60,
    "execution_mode": ExecutionMode.LOCAL,
}
