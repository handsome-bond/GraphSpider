"""
Smart Reflector — intelligent failure diagnosis for the GraphSpider Agent.

Unlike rule-based "if EMPTY_OUTPUT → regenerate", this module:
1. Re-fetches page HTML to get actual DOM structure
2. Extracts ALL CSS selectors from the generated script
3. Compares them against what actually exists in the HTML
4. Builds a detailed, structured diagnostic for the LLM
5. Tracks cross-round memory to prevent repeating mistakes
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class SelectorDiagnosis:
    """A selector extracted from the script, checked against the HTML."""
    selector: str
    exists_in_html: bool
    suggestion: str = ""


@dataclass
class SmartDiagnosis:
    """Complete diagnostic for a failed scraping attempt."""
    error_type: str
    stderr_summary: str
    stdout_summary: str

    # Selector analysis
    script_selectors: List[SelectorDiagnosis] = field(default_factory=list)
    html_selectors: List[str] = field(default_factory=list)
    hallucinated_selectors: List[str] = field(default_factory=list)
    missing_key_selectors: List[str] = field(default_factory=list)

    # Pagination analysis
    pagination_used: str = ""          # what the script tried
    pagination_available: str = ""     # what the HTML actually has

    # Memory
    previous_attempts: List[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format the diagnosis as a clear, actionable prompt for the LLM."""
        parts = [f"## DIAGNOSIS: Previous attempt FAILED\n"]
        parts.append(f"Error: {self.error_type}")
        parts.append(f"Stderr: {self.stderr_summary[:300]}\n")

        # ── Selector analysis ──
        if self.hallucinated_selectors:
            parts.append("### HALLUCINATED SELECTORS (DO NOT USE):")
            for s in self.hallucinated_selectors:
                parts.append(f"  ❌ {s} — does NOT exist in the page HTML")
            parts.append("")

        if self.html_selectors:
            parts.append("### SELECTORS THAT ACTUALLY EXIST IN THE PAGE:")
            for s in self.html_selectors[:25]:
                parts.append(f"  ✅ {s}")
            parts.append("")

        if self.missing_key_selectors:
            parts.append("### KEY SELECTORS YOU SHOULD USE BUT DIDN'T:")
            for s in self.missing_key_selectors:
                parts.append(f"  ⚠️ {s} — exists in HTML but not in your script")
            parts.append("")

        # ── Pagination ──
        if self.pagination_used and self.pagination_available:
            parts.append("### PAGINATION:")
            parts.append(f"  You tried: {self.pagination_used}")
            parts.append(f"  Actually available: {self.pagination_available}")
            parts.append("")

        # ── Memory: previous mistakes ──
        if self.previous_attempts:
            parts.append("### PREVIOUS ROUNDS — DO NOT REPEAT THESE MISTAKES:")
            for attempt in self.previous_attempts:
                parts.append(f"  ❌ Round: {attempt}")
            parts.append("")

        # ── Fix instruction ──
        parts.append("### YOUR TASK:")
        parts.append("Generate a NEW Playwright scraper script that:")
        parts.append("1. Uses ONLY the ✅ selectors listed above (from the actual HTML)")
        parts.append("2. NEVER uses the ❌ hallucinated selectors")
        parts.append(f"3. Uses the ACTUAL pagination mechanism: {self.pagination_available}")
        parts.append("4. Includes proxy support, skeleton filtering, and fingerprint pagination")
        parts.append("5. Output ONLY valid Python code — no markdown, no explanation\n")

        return "\n".join(parts)


def diagnose_failure(
    script: str,
    stderr: str,
    stdout: str,
    error_type: str,
    html_context: str = "",
    round_history: Optional[List[dict]] = None,
) -> SmartDiagnosis:
    """
    Analyze a failed scraping attempt and produce a structured diagnosis.
    """
    diag = SmartDiagnosis(
        error_type=error_type,
        stderr_summary=_summarize_stderr(stderr),
        stdout_summary=stdout[:300],
    )

    # ── Extract selectors from the script ──
    script_selectors = _extract_selectors(script)
    html_selectors = _extract_selectors_from_html(html_context) if html_context else []

    # ── Check each script selector against HTML ──
    for sel in script_selectors:
        exists = _selector_exists(sel, html_context) if html_context else None
        diag.script_selectors.append(SelectorDiagnosis(
            selector=sel,
            exists_in_html=exists if exists is not None else True,
            suggestion="" if (exists or exists is None) else f"Use one of: {html_selectors[:10]}",
        ))
        if exists is False and _is_likely_data_selector(sel):
            diag.hallucinated_selectors.append(sel)

    # ── Find selectors in HTML that the script missed ──
    if html_selectors:
        script_sel_set = {s.selector for s in diag.script_selectors}
        for hsel in html_selectors:
            if hsel not in script_sel_set and _is_likely_data_selector(hsel):
                diag.missing_key_selectors.append(hsel)

    diag.html_selectors = html_selectors[:30]

    # ── Pagination analysis ──
    diag.pagination_used = _detect_pagination_in_script(script)
    diag.pagination_available = _detect_pagination_in_script(html_context) if html_context else "unknown"

    # ── Memory ──
    if round_history:
        for r in round_history:
            err = r.get("error_type", "unknown")
            diag.previous_attempts.append(f"Round {r.get('round', '?')}: {err} → {r.get('fix_strategy', '?')}")

    return diag


def _extract_selectors(code: str) -> List[str]:
    """Extract all CSS selectors used in query_selector / wait_for_selector calls."""
    selectors = set()
    for m in re.finditer(
        r"""(?:query_selector(?:_all)?|wait_for_selector|locator)\s*\(\s*["']([^"']{2,})["']""",
        code,
    ):
        selectors.add(m.group(1))
    return sorted(selectors)


def _extract_selectors_from_html(html: str) -> List[str]:
    """Extract CSS-usable class names and IDs from raw HTML."""
    selectors = set()
    # class="foo bar" → .foo, .bar
    for m in re.finditer(r'class\s*=\s*["\']([^"\']+)["\']', html):
        for cls in m.group(1).split():
            cls = cls.strip()
            if cls and len(cls) > 1:
                selectors.add(f".{cls}")
    # id="foo" → #foo
    for m in re.finditer(r'id\s*=\s*["\']([^"\']+)["\']', html):
        id_ = m.group(1).strip()
        if id_ and len(id_) > 1:
            selectors.add(f"#{id_}")
    # Common element selectors
    for tag in ("li", "a", "div", "section", "article", "table", "tr", "td",
                 "h1", "h2", "h3", "h4", "span", "p", "button", "ul", "ol"):
        if f"<{tag}" in html.lower():
            selectors.add(tag)
    return sorted(selectors)


def _selector_exists(selector: str, html: str) -> Optional[bool]:
    """Check if a CSS selector pattern appears in the HTML."""
    if not html:
        return None
    html_lower = html.lower()
    # Simple class-based check: .classname → class="classname" or class='classname'
    classes = re.findall(r'\.([\w-]+)', selector)
    for cls in classes:
        if f'class="{cls}"' not in html and f"class='{cls}'" not in html and \
           f'class="' not in html.replace(f'class="{cls}"', ''):
            # Loose check: the class name appears somewhere in HTML
            if cls not in html_lower:
                return False
    # ID-based check
    ids = re.findall(r'#([\w-]+)', selector)
    for id_ in ids:
        if f'id="{id_}"' not in html and f"id='{id_}'" not in html:
            return False
    # Tag-based check: pure tag name (li, div, etc.)
    if re.match(r'^[a-z][a-z0-9]*$', selector):
        if f'<{selector}' not in html_lower:
            return False
    return True


def _is_likely_data_selector(selector: str) -> bool:
    """Is this selector likely targeting data content (not nav/footer)?"""
    noise = {"nav", "footer", "header", "sidebar", "menu", "breadcrumb", "pagination"}
    sel_lower = selector.lower()
    return not any(n in sel_lower for n in noise)


def _detect_pagination_in_script(code: str) -> str:
    """Summarize the pagination approach used in the script."""
    if "page.goto(" in code and ("urljoin" in code or "next_url" in code):
        return "URL-based (page.goto + urljoin)"
    if "click()" in code and "next" in code.lower():
        return "Click-based (click Next button)"
    if "wait_for_function" in code:
        return "Fingerprint wait (wait_for_function)"
    return "none detected"


def _summarize_stderr(stderr: str) -> str:
    """Extract the most relevant error lines from stderr."""
    lines = stderr.strip().split("\n")
    key_lines = []
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in (
            "error", "timeout", "traceback", "exception", "failed",
            "cannot", "invalid", "not found", "missing",
        )):
            key_lines.append(line.strip()[:200])
    if key_lines:
        return "\n".join(key_lines[-5:])
    return "\n".join(lines[-3:])[:500]
