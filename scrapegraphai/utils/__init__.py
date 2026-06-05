"""
Utility modules for ScrapeGraphAI.
"""

from .cleanup_html import cleanup_html, clean_html_for_script_creator, reduce_html
from .convert_to_md import convert_to_md
from .copy import safe_deepcopy
from .llm_callback_manager import CustomLLMCallbackManager
from .logging import (
    get_logger,
    get_verbosity,
    set_formatting,
    set_handler,
    set_propagation,
    set_verbosity,
    set_verbosity_debug,
    set_verbosity_error,
    set_verbosity_fatal,
    set_verbosity_info,
    set_verbosity_warning,
    setDEFAULT_HANDLER,
    unset_formatting,
    unset_handler,
    unset_propagation,
    unsetDEFAULT_HANDLER,
    warning_once,
)
from .output_parser import get_pydantic_output_parser, get_structured_output_parser
from .proxy_rotation import Proxy, parse_or_search_proxy, search_proxy_servers
from .schema_trasform import transform_schema
from .split_text_into_chunks import split_text_into_chunks
from .sys_dynamic_import import dynamic_import, srcfile_import
from .tokenizer import num_tokens_calculus

__all__ = [
    "cleanup_html",
    "clean_html_for_script_creator",
    "reduce_html",
    "convert_to_md",
    "safe_deepcopy",
    "CustomLLMCallbackManager",
    # Logging
    "get_logger",
    "get_verbosity",
    "set_formatting",
    "set_handler",
    "set_propagation",
    "set_verbosity",
    "set_verbosity_debug",
    "set_verbosity_error",
    "set_verbosity_fatal",
    "set_verbosity_info",
    "set_verbosity_warning",
    "setDEFAULT_HANDLER",
    "unset_formatting",
    "unset_handler",
    "unset_propagation",
    "unsetDEFAULT_HANDLER",
    "warning_once",
    # Other utils
    "Proxy",
    "parse_or_search_proxy",
    "search_proxy_servers",
    "get_pydantic_output_parser",
    "get_structured_output_parser",
    "split_text_into_chunks",
    "dynamic_import",
    "srcfile_import",
    "num_tokens_calculus",
    "transform_schema",
]
