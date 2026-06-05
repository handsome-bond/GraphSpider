"""
Prompt templates for ScrapeGraphAI.
"""

from .generate_answer_node_prompts import (
    REGEN_ADDITIONAL_INFO,
    TEMPLATE_CHUNKS,
    TEMPLATE_CHUNKS_MD,
    TEMPLATE_MERGE,
    TEMPLATE_MERGE_MD,
    TEMPLATE_NO_CHUNKS,
    TEMPLATE_NO_CHUNKS_MD,
)
from .merge_answer_node_prompts import TEMPLATE_COMBINED
from .merge_generated_scripts_prompts import TEMPLATE_MERGE_SCRIPTS_PROMPT
from .reasoning_node_prompts import TEMPLATE_REASONING, TEMPLATE_REASONING_WITH_CONTEXT
from .robots_node_prompts import TEMPLATE_ROBOT
from .search_internet_node_prompts import TEMPLATE_SEARCH_INTERNET

__all__ = [
    "REGEN_ADDITIONAL_INFO",
    "TEMPLATE_CHUNKS",
    "TEMPLATE_CHUNKS_MD",
    "TEMPLATE_MERGE",
    "TEMPLATE_MERGE_MD",
    "TEMPLATE_NO_CHUNKS",
    "TEMPLATE_NO_CHUNKS_MD",
    "TEMPLATE_COMBINED",
    "TEMPLATE_MERGE_SCRIPTS_PROMPT",
    "TEMPLATE_REASONING",
    "TEMPLATE_REASONING_WITH_CONTEXT",
    "TEMPLATE_ROBOT",
    "TEMPLATE_SEARCH_INTERNET",
]
