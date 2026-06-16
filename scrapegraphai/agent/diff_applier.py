"""
Diff applier — merges LLM-generated fixes back into the original script.

The LLM may return:
  1. A complete corrected script (import ... → use directly)
  2. A ```python ... ``` fenced code block (extract)
  3. A description + code fragment (best-effort extraction)
"""

import re


def apply_llm_fix(original: str, llm_output: str) -> str:
    """
    Extract a runnable Python script from the LLM's response.
    """

    # ── 1. Fenced code block ──
    code_match = re.search(
        r"```python\s*(.*?)\s*```", llm_output, re.DOTALL | re.IGNORECASE
    )
    if code_match:
        return code_match.group(1).strip()

    code_match = re.search(
        r"```\s*(.*?)\s*```", llm_output, re.DOTALL
    )
    if code_match:
        candidate = code_match.group(1).strip()
        if candidate.startswith("import") or candidate.startswith("from"):
            return candidate

    # ── 2. Complete script (starts with import / from) ──
    stripped = llm_output.strip()
    if stripped.startswith("import") or stripped.startswith("from"):
        return stripped

    # ── 3. Heuristic: find the longest contiguous block of Python-looking lines ──
    lines = stripped.splitlines()
    python_lines = []
    in_block = False
    for line in lines:
        if line.startswith("import") or line.startswith("from") or line.startswith("def "):
            in_block = True
        if in_block:
            python_lines.append(line)

    if len(python_lines) > 3:
        return "\n".join(python_lines)

    # ── 4. Fallback: return original ──
    return original
