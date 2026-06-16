"""
Error classifier — regex-based, zero-latency error diagnosis.

Categorises scraper failures so the agent can choose the right fix
strategy without calling an LLM for classification.
"""

import re
from dataclasses import dataclass


@dataclass
class ErrorClassification:
    error_type: str       # "TIMEOUT" | "HTTP_403" | "NAME_ERROR" | ...
    severity: str         # "FATAL" | "RECOVERABLE"
    suggestion: str       # human-readable fix hint


class ErrorClassifier:
    """Classify scraper script failures from stderr / stdout patterns."""

    PATTERNS = [
        # (regex, error_type, severity, suggestion)
        (
            r"Timeout \d+ms exceeded.*waiting for",
            "TIMEOUT", "RECOVERABLE",
            "选择器未匹配，需检查页面 DOM",
        ),
        (
            r"SyntaxError.*",
            "JS_SYNTAX", "FATAL",
            "JavaScript 语法错误，需要 escape 特殊字符",
        ),
        (
            r"NameError: name '(\w+)' is not defined",
            "NAME_ERROR", "FATAL",
            "变量名拼写错误，sanitizer 可自动修复",
        ),
        (
            r"IndentationError",
            "INDENT_ERROR", "FATAL",
            "缩进错误，sanitizer 可自动修复",
        ),
        (
            r"403|Forbidden|Access Denied",
            "HTTP_403", "RECOVERABLE",
            "被反爬拦截，需加强代理/指纹",
        ),
        (
            r"ERR_TUNNEL_CONNECTION_FAILED|ERR_PROXY_CONNECTION",
            "PROXY_ERROR", "RECOVERABLE",
            "代理连接失败，检查 Clash 是否运行",
        ),
        (
            r"^\s*\[\s*\]\s*$",
            "EMPTY_RESULT", "RECOVERABLE",
            "爬取成功但数据为空，选择器可能不匹配",
        ),
        (
            r"Cannot navigate to invalid URL",
            "URL_INVALID", "FATAL",
            "URL 格式错误，需要 urljoin 拼接",
        ),
    ]

    @classmethod
    def classify(cls, stderr: str, stdout: str) -> ErrorClassification:
        combined = stderr + "\n" + stdout

        for pattern, etype, severity, suggestion in cls.PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE | re.DOTALL):
                return ErrorClassification(etype, severity, suggestion)

        if stderr.strip() and not stdout.strip():
            return ErrorClassification(
                "RUNTIME_ERROR", "RECOVERABLE",
                f"脚本运行出错: {stderr.strip()[:200]}"
            )

        if not stdout.strip() and not stderr.strip():
            return ErrorClassification(
                "EMPTY_OUTPUT", "RECOVERABLE",
                "无任何输出，脚本可能未执行或提前退出"
            )

        return ErrorClassification(
            "UNKNOWN", "RECOVERABLE",
            "未匹配已知错误模式"
        )

    @classmethod
    def is_fatal(cls, classification: ErrorClassification) -> bool:
        return classification.severity == "FATAL"

    @classmethod
    def can_sanitize(cls, classification: ErrorClassification) -> bool:
        """Errors that the existing sanitizer pipeline can fix without LLM."""
        return classification.error_type in (
            "NAME_ERROR", "INDENT_ERROR", "JS_SYNTAX", "URL_INVALID"
        )
