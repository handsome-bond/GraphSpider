"""
GenerateScraperNode Module
"""

import re
from typing import List, Optional

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate

from ..utils.tokenizer import num_tokens_calculus
from .base_node import BaseNode


# Regexes for detecting and correcting hallucinated URLs in generated scripts.
# Matches .goto("..."), browser.goto('...'), page.goto("..."),
# requests.get("..."), driver.get("..."), and httpx.get("...").
# Matches ANY string argument (not just http* — the LLM may output "h" or
# some other fragment when the URL is missing from its context).
_GOTO_RE = re.compile(
    r'(\.goto\s*\(\s*["\'])([^"\']*)(["\'])',
    re.IGNORECASE,
)
_GET_RE = re.compile(
    r'((?:requests|httpx|http\.client)\.get\s*\(\s*["\'])([^"\']*)(["\'])',
    re.IGNORECASE,
)
_SELENIUM_GET_RE = re.compile(
    r'(\.get\s*\(\s*["\'])([^"\']*)(["\'])',
    re.IGNORECASE,
)

# Only replace URLs that look wrong (not already the correct URL).
# This avoids touching variable references like .goto(url) — those
# don't use quotes and are not matched by the regexes above.


def correct_urls_in_code(code: str, correct_url: str) -> str:
    """
    Replace any hallucinated URLs in goto() / get() calls with the
    correct source URL.  Only touches URL positionals inside calls;
    CSS selectors, variable names, and string literals are left alone.

    Can be called from any node that produces scraping scripts.
    """
    if not correct_url or not code:
        return code

    def _replace(match):
        prefix = match.group(1)
        url = match.group(2)
        suffix = match.group(3)
        if url.rstrip("/") != correct_url.rstrip("/"):
            return f"{prefix}{correct_url}{suffix}"
        return match.group(0)

    code = _GOTO_RE.sub(_replace, code)
    code = _GET_RE.sub(_replace, code)
    code = _SELENIUM_GET_RE.sub(_replace, code)
    return code


class GenerateScraperNode(BaseNode):
    """
    Generates a python script for scraping a website using the specified library.
    It takes the user's prompt and the scraped content as input and generates a python script
    that extracts the information requested by the user.

    Attributes:
        llm_model: An instance of a language model client, configured for generating answers.
        library (str): The python library to use for scraping the website.
        source (str): The website to scrape.

    Args:
        input (str): Boolean expression defining the input keys needed from the state.
        output (List[str]): List of output keys to be updated in the state.
        node_config (dict): Additional configuration for the node.
        library (str): The python library to use for scraping the website.
        website (str): The website to scrape.
        node_name (str): The unique identifier name for the node, defaulting to "GenerateScraper".

    """

    TEMPLATE = """
    PROMPT:
    You are a website scraper script creator. Below is the cleaned HTML source
    of a website (scripts, styles, and non-essential attributes already removed).
    The HTML is split into chunks; each chunk is a valid HTML fragment from the page body.

    Write a COMPLETE Python script for extracting the information requested by the
    user question. Output ONLY Python code — no markdown, no comments, no explanation.

    ═══ MANDATORY RULES ═══

    1. EXACT URL: Use {source} as the starting URL. Never change it.

    2. PROXY + STEALTH (gov sites block by IP):
       import os, random
       PROXY = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7890")
       browser = await p.chromium.launch(headless=False,
           proxy={{"server": PROXY}} if PROXY else None,
           args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
       context = await browser.new_context(
           viewport={{"width": 1920, "height": 1080}},
           user_agent="...Chrome/131...",
           locale="en-CA", timezone_id="America/Toronto",
           extra_http_headers={{"Accept-Language": "en-CA,en;q=0.9"}})
       await page.add_init_script('''Object.defineProperty(navigator,"webdriver",{{get:()=>undefined}})''')
       Add random 1-3s waits between actions.

    3. CSS SELECTORS — USE THESE EXACT SELECTORS FROM THE HTML:
       {css_hints}
       EVERY selector in your script MUST come from this list or from the HTML
       chunks below.  NEVER invent class names that don't appear above.

    4. PAGINATION — {pagination_instruction}

    5. DOM STABILITY: After any click / navigation, re-query ALL selectors fresh.
       Never reuse element handles from a previous page.

    6. LOOP TERMINATION:
       - Check if the Next button has disabled/aria-disabled attribute → break
       - If the first item's text hasn't changed after clicking → break (last page)
       - If user specified a max-items limit → break when reached

    LIBRARY: {library}
    SOURCE: {source}
    CONTEXT: {context}
    USER QUESTION: {question}
    SCHEMA INSTRUCTIONS: {schema_instructions}
    """

    # Common English stopwords used for keyword filtering
    _STOPWORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "in", "on", "at", "to",
        "for", "of", "and", "or", "not", "no", "but", "if", "then", "else",
        "when", "where", "why", "how", "who", "whom", "which", "what",
        "all", "any", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "only", "own", "same", "so", "than",
        "too", "very", "just", "about", "above", "after", "again",
        "below", "between", "from", "into", "through", "during", "before",
        "with", "within", "without", "this", "that", "these", "those",
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
        "they", "them", "also", "now", "up", "out", "here", "there",
    })

    def __init__(
        self,
        input: str,
        output: List[str],
        library: str,
        website: str,
        node_config: Optional[dict] = None,
        node_name: str = "GenerateScraper",
    ):
        super().__init__(node_name, "node", input, output, 2, node_config)

        self.llm_model = node_config["llm_model"]
        self.library = library
        self.source = website
        self.model_token = node_config.get("model_token", 128000)
        self.user_data_dir = node_config.get("user_data_dir")

        self.verbose = (
            False if node_config is None else node_config.get("verbose", False)
        )

        self.additional_info = node_config.get("additional_info")

    def execute(self, state: dict) -> dict:
        """
        Generates a python script for scraping a website using the specified library.
        Uses all available HTML chunks, filtering by relevance when necessary.

        Args:
            state (dict): The current state of the graph.

        Returns:
            dict: The updated state with the output key containing the generated answer.
        """

        self.logger.info(f"--- Executing {self.node_name} Node ---")

        input_keys = self.get_input_keys(state)

        input_data = [state[key] for key in input_keys]

        user_prompt = input_data[0]
        doc = input_data[1]

        # Resolve the target URL dynamically from the graph state.
        # The graph may have been created with an empty source (GraphIteratorNode
        # creates instances with source="" then updates .source later — but by
        # then _create_graph() has already run and bound website="" here).
        # state["url"] / state["local_dir"] carries the actual URL from FetchNode.
        effective_source = (
            state.get("url")
            or state.get("local_dir")
            or self.source
        )

        if self.node_config.get("schema", None) is not None:
            output_schema = JsonOutputParser(pydantic_object=self.node_config["schema"])
        else:
            output_schema = JsonOutputParser()

        format_instructions = output_schema.get_format_instructions()

        context = self._build_context(doc, user_prompt)

        # Analyze the HTML to determine pagination type.
        # _analyze_pagination() also stores self._pagination_mode / _pagination_style
        # for sanitizers to conditionally enable/disable injections.
        pagination_instruction = self._analyze_pagination(context, effective_source)

        # Extract CSS class names / IDs from the HTML so the LLM knows
        # EXACTLY which selectors exist — prevents selector hallucination.
        css_hints = self._extract_css_hints(context)

        template = self.TEMPLATE
        if self.additional_info is not None:
            template += self.additional_info

        prompt = PromptTemplate(
            template=template,
            input_variables=["question"],
            partial_variables={
                "context": context,
                "library": self.library,
                "source": effective_source,
                "schema_instructions": format_instructions,
                "pagination_instruction": pagination_instruction,
                "css_hints": css_hints,
            },
        )
        map_chain = prompt | self.llm_model | StrOutputParser()

        answer = map_chain.invoke({"question": user_prompt})

        # Post-generation: run ALL sanitizers on the LLM output.
        answer = self._sanitize_script(answer, effective_source)

        state.update({self.output[0]: answer})
        return state

    def _sanitize_script(self, code: str, source_url: str) -> str:
        """Run all post-generation fixes on the LLM output."""
        for fix_name, fix_fn in [
            ("url_correction", lambda c: self._correct_urls(c, source_url)),
            ("networkidle_removal", self._remove_networkidle),
            ("count_pagination", self._sanitize_pagination),
            ("js_escape", self._sanitize_js_injection),
            ("env_var_hallucination", self._sanitize_env_var),
            ("disabled_check", self._sanitize_disabled_check),
            ("skeleton_filter", self._sanitize_skeleton_nodes),
            ("proxy_injection", self._inject_proxy),
            ("save_to_file", self._inject_file_save),
            ("wait_function_safety", self._sanitize_wait_function),
            ("persistent_context", self._inject_persistent_context),
        ]:
            fixed = fix_fn(code)
            if fixed != code:
                self.logger.warning(f"{self.node_name}: {fix_name} applied")
                code = fixed
        return code

    def _correct_urls(self, code: str, correct_url: str) -> str:
        """Replace hallucinated URLs in goto()/get() calls."""
        return correct_urls_in_code(code, correct_url)

    def _remove_networkidle(self, code: str) -> str:
        """Strip wait_until=networkidle which hangs on modern sites."""
        return re.sub(r',\s*wait_until\s*=\s*["\']networkidle["\']', '', code)

    # ── Sanitizer: fix JS injection of unescaped fingerprint text ──

    # Matches innerText !== "{var}" or innerText !== '{var}' — the raw Python
    # variable in a JS string literal causes SyntaxError when it has newlines.
    _JS_INJECTION_RE = re.compile(
        r"""innerText\s*!==?\s*['"]\{([^}]+)\}['"]"""
    )

    def _sanitize_js_injection(self, code: str) -> str:
        """
        Fix JS syntax errors: LLMs embed raw Python variables into JS strings,
        which breaks when the value has newlines or quotes.
        Replace  innerText !== '{var}'  with  innerText !== {json.dumps(var)}
        so the Python variable is JSON-escaped before reaching JavaScript.
        Catches both single-quote and double-quote JS string patterns.
        """
        return self._JS_INJECTION_RE.sub(
            r'innerText !== {json.dumps(\1)}', code
        )

    # ── Sanitizer: fix URL used as environment variable key ──

    _URL_AS_ENV_KEY_RE = re.compile(
        r'os\.environ\.get\(\s*["\']https?://[^"\']+["\']'
    )

    def _sanitize_env_var(self, code: str) -> str:
        """
        Fix LLM hallucination where the target URL is passed as the
        environment variable name instead of HTTPS_PROXY.
        """
        return self._URL_AS_ENV_KEY_RE.sub(
            'os.environ.get("HTTPS_PROXY"', code
        )

    # ── Sanitizer: fix disabled-check on <a> instead of parent <li> ──

    _DISABLED_ON_A_RE = re.compile(
        r'(disabled\s*=\s*await\s+\w+\.get_attribute\("disabled"\))'
    )

    def _sanitize_disabled_check(self, code: str) -> str:
        """
        Add parent-<li> Bootstrap disabled check — ONLY for click-based or
        complex pagination.  Simple URL-based sites (Douban-style) don't
        need this: the Next link simply disappears on the last page.
        """
        # Skip for simple URL-based pagination (no Bootstrap, no buttons)
        if getattr(self, "_pagination_mode", "") == "URL-BASED":
            return code

        if "classList.contains('disabled')" in code:
            return code

        # Skip if code uses Locator API (complex structure, regex unsafe)
        if "page.locator" in code or ".first" in code:
            return code

        var_match = re.search(
            r'(\w+)\s*=\s*None\s*\n\s*for\s+sel\s+in\s+next_selectors', code
        )
        if not var_match:
            return code  # can't find the pattern safely
        var_name = var_match.group(1)

        parent_check = (
            f'            # Check parent <li> for Bootstrap disabled class\n'
            f'            is_parent_disabled = await {var_name}.evaluate(\n'
            f'                "(node) => node.closest(\'li\')?.classList'
            f".contains('disabled') || false\"\n"
            f'            )\n'
        )
        code = re.sub(
            r'^([ \t]*)disabled = await ',
            parent_check + r'\1disabled = await ',
            code,
            count=1,
            flags=re.MULTILINE,
        )

        for pat in [
            r'(if\s+disabled\s+or\s+aria_disabled\s*==\s*"true"\s*)',
            r'(if\s+disabled\s+is\s+not\s+None\s+or\s+aria_disabled\s*==\s*"true"\s*)',
        ]:
            code = re.sub(pat, r'\1or is_parent_disabled ', code)

        return code

    # ── Sanitizer: filter empty skeleton-screen nodes ──

    def _sanitize_skeleton_nodes(self, code: str) -> str:
        """
        Add a guard that skips empty/skeleton-screen placeholders.
        Only targets data-extraction loops — NOT pagination selector loops.
        """
        if 'skip empty' in code.lower() or 'skip hidden' in code.lower():
            return code

        def _insert_guard(match):
            full_match = match.group(0)
            leading = match.group(1)
            indent1 = leading + "    "
            indent2 = indent1 + "    "
            return (
                f"{full_match}\n"
                f"{indent1}# Skip hidden skeleton-screen / empty placeholder nodes\n"
                f"{indent1}if not (await item.inner_text()).strip():\n"
                f"{indent2}continue\n"
            )

        # Only match item-extraction loops, NOT pagination-selector loops.
        # Pagination loops use words like "selector", "sel", "next".
        _PAGINATION_LOOP_WORDS = frozenset({
            "selector", "selectors", "sel", "next_sel",
        })
        for pattern in [
            r'([ \t]*)(for\s+(\w+)\s+in\s+(\w+)\s*:)',
        ]:
            for m in re.finditer(pattern, code):
                loop_var = m.group(3).lower()
                loop_iter = m.group(4).lower()
                if loop_var in _PAGINATION_LOOP_WORDS:
                    continue
                if loop_iter in _PAGINATION_LOOP_WORDS:
                    continue
                # Found a data-extraction loop — inject the guard
                code = code.replace(
                    m.group(0),
                    _insert_guard(m),
                    1,  # only first match to avoid double-injection
                )
                return code
        return code

    # ── Post-generation script sanitizers ───────────────────────────

    # Any wait_for_function that checks .length — this is ALWAYS wrong for
    # replacement pagination (where count stays the same across pages).
    _ANY_COUNT_WAIT_RE = re.compile(
        r'(await\s+page\.wait_for_function\(\s*\n?\s*)'
        r'f"document\.querySelectorAll\([^)]+\)\.length\s*[><=!]+\s*\{?\w+\}?"\s*,?\s*\n?\s*'
        r'(timeout\s*=\s*\d+)',
    )
    # Any .length comparison with a count variable (e.g. new_count == old_count).
    _ANY_COUNT_COMPARE_RE = re.compile(
        r'(\w*coun\w*)\s*=\s*len\(await\s+page\.query_selector_all\([^)]+\)\)\s*\n\s*'
        r'if\s+\1\s*==\s*(\w+)\s*:\s*\n\s*break',
    )
    # Any assignment like xxx_count = len(await page.query_selector_all(...))
    _ANY_COUNT_CAPTURE_RE = re.compile(
        r'(\w+)\s*=\s*len\(await\s+page\.query_selector_all\(([^)]+)\)\)'
    )

    def _sanitize_pagination(self, code: str) -> str:
        """
        Aggressively remove ALL count-based pagination logic and replace with
        fingerprint-based detection.  Count comparison (.length > old_count)
        is ALWAYS wrong for replacement pagination (gov/enterprise sites).
        """
        if not code:
            return code

        changes = 0

        # ── Step 1: Replace count capture with fingerprint capture ──
        def _add_fingerprint_after_count(m):
            changes_count[0] += 1
            return (
                f'{m.group(0)}  # FINGERPRINT: capture first item text '
                f'for replacement-pagination detection\n'
                f'        first_item = await page.query_selector('
                f'{m.group(2)})\n'
                f'        old_text = await first_item.inner_text() '
                f'if first_item else ""'
            )
        changes_count = [0]
        code = self._ANY_COUNT_CAPTURE_RE.sub(_add_fingerprint_after_count, code)
        changes += changes_count[0]

        # ── Step 2: Replace count-based wait_for_function ──
        def _replace_count_wait(m):
            changes_wait[0] += 1
            return (
                f'{m.group(1)}'
                f'f\'\'\'() => {{ const items = document.querySelectorAll'
                f'("li.ndm-item"); return items.length > 0 && items[0].innerText'
                f' !== {{json.dumps(old_text)}}; }}\'\'\',\n'
                f'            {m.group(3)}'
            )
        changes_wait = [0]
        code = self._ANY_COUNT_WAIT_RE.sub(_replace_count_wait, code)
        changes += changes_wait[0]

        # ── Step 3: Replace count-comparison break ──
        def _replace_count_break(m):
            changes_break[0] += 1
            return (
                f'{m.group(0)}\n'
                f'            first_item = await page.query_selector("li.ndm-item")\n'
                f'            new_text = await first_item.inner_text() if first_item else ""\n'
                f'            if new_text == old_text:\n'
                f'                break  # fingerprint unchanged — last page'
            )
        changes_break = [0]
        code = self._ANY_COUNT_COMPARE_RE.sub(_replace_count_break, code)
        changes += changes_break[0]

        # ── Step 4: If ANY count pattern was replaced, add import json ──
        if changes > 0:
            if "import json" not in code:
                code = code.replace("import asyncio", "import asyncio\nimport json", 1)
            self.logger.info(
                f"_sanitize_pagination: fixed {changes} count-based patterns "
                f"(capture={changes_count[0]}, wait={changes_wait[0]}, "
                f"break={changes_break[0]})"
            )

        return code

    def _inject_proxy(self, code: str) -> str:
        """
        If the generated script doesn't include proxy support, inject it.
        Government sites block by IP; proxy is essential.
        """
        if not code or "PROXY" in code or "proxy" in code:
            return code

        # Add import os if missing.
        if "import os" not in code:
            code = code.replace(
                "import random",
                "import os\nimport random",
                1,
            )
            if "import os" not in code:
                code = code.replace(
                    "import asyncio",
                    "import asyncio\nimport os",
                    1,
                )

        # Inject PROXY variable and proxy param into browser.launch().
        proxy_setup = (
            '    PROXY = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7890")\n'
        )
        # Insert PROXY line before browser = await p.chromium.launch
        code = re.sub(
            r'(    browser = await p\.chromium\.launch\()',
            proxy_setup + r'\g<1>',
            code,
        )

        # Add proxy= parameter if headless=False is present (first arg after launch()
        code = re.sub(
            r'(launch\(\s*\n\s*headless=False,)',
            r'\g<1>\n            proxy={"server": PROXY},',
            code,
        )

        self.logger.info("_inject_proxy: proxy support injected into script")
        return code

    def _build_context(self, chunks: list, user_prompt: str) -> str:
        """
        Build the context string from HTML chunks.

        Strategy:
        1. If all chunks fit within the context budget, use all of them.
        2. If too many chunks, prioritize those whose visible text overlaps
           with keywords from the user's query.
        3. Always preserve original DOM order for the selected chunks.

        Args:
            chunks: List of HTML chunk strings.
            user_prompt: The user's scraping request.

        Returns:
            A concatenated context string ready for the prompt template.
        """
        if not chunks:
            return ""

        if isinstance(chunks, list) and len(chunks) == 1 and isinstance(chunks[0], list):
            # Nested list from some parse paths — flatten
            chunks = chunks[0]

        # Reserve ~40% of model capacity for the prompt template and response
        context_budget = max(int(self.model_token * 0.55), 4000)

        chunk_tokens = [num_tokens_calculus(c) for c in chunks]
        total_tokens = sum(chunk_tokens)

        if total_tokens <= context_budget:
            if len(chunks) > 1:
                self.logger.info(
                    f"All {len(chunks)} chunks fit in context "
                    f"({total_tokens}/{context_budget} tokens)"
                )
            return "\n\n<!-- HTML chunk -->\n\n".join(chunks)

        self.logger.info(
            f"Context budget {context_budget} tokens, "
            f"have {total_tokens} across {len(chunks)} chunks. "
            f"Filtering by keyword relevance."
        )

        return self._select_relevant_chunks(chunks, chunk_tokens, context_budget, user_prompt)

    def _select_relevant_chunks(
        self, chunks: list, chunk_tokens: list, budget: int, user_prompt: str
    ) -> str:
        """
        Keep a representative sample of chunks so the LLM can see both the
        page STRUCTURE and the DATA content.

        Keyword-only filtering is dangerous — data chunks often don't contain
        the user's query keywords (e.g. ''title'' is a CSS class, not visible
        text), causing the LLM to hallucinate selectors.

        Strategy: always keep first + last chunk(s)；if there are ≤5 chunks
        keep ALL；if more, spread the budget across head / middle / tail.
        """
        n = len(chunks)
        if n <= 1:
            return "\n\n<!-- HTML chunk -->\n\n".join(chunks)

        # For small numbers of chunks, keep everything — keyword filtering is
        # more likely to discard the data chunks than to help.
        if n <= 5:
            total = sum(chunk_tokens)
            self.logger.info(
                f"Keeping all {n} chunks ({total}/{budget} tokens) — "
                f"too few chunks for safe filtering"
            )
            return "\n\n<!-- HTML chunk -->\n\n".join(chunks)

        # ── For many chunks: head / middle / tail sampling ──
        # Always keep: first chunk (page structure / header)
        # Always keep: 1-2 last chunks (pagination / footer)
        # Always keep: 1 chunk from the middle (usually the data area)
        anchor = set()
        anchor.add(0)                        # first
        anchor.add(n - 1)                    # last
        if n >= 3:
            anchor.add(n // 2)               # middle

        anchor_tokens = sum(chunk_tokens[i] for i in anchor)
        remaining_budget = budget - anchor_tokens

        # Fill remaining budget with chunks from the front (structure) and
        # around the middle (more data).
        remaining_indices = [i for i in range(n) if i not in anchor]
        selected = []
        used = 0
        for i in remaining_indices:
            if used + chunk_tokens[i] <= remaining_budget:
                selected.append(i)
                used += chunk_tokens[i]

        all_indices = sorted(anchor | set(selected))
        self.logger.info(
            f"Selected {len(all_indices)}/{n} chunks "
            f"({used + anchor_tokens}/{budget} tokens) — "
            f"head+middle+tail sampling"
        )

        separator = "\n\n<!-- HTML chunk -->\n\n"
        return separator.join(chunks[i] for i in all_indices)

    # ── Sanitizer: make wait_for_function non-breaking ───────────────

    def _sanitize_wait_function(self, code: str) -> str:
        """
        For URL-based pagination, page.goto() already provides the navigation
        guarantee — the fingerprint wait_for_function is redundant and can
        timeout, breaking the loop.  Make its except-block non-breaking.
        For click-based pagination, the fingerprint wait IS needed.
        """
        # For simple URL-based sites, change except: break → except: pass
        if getattr(self, "_pagination_mode", "") == "URL-BASED":
            code = re.sub(
                r'(wait_for_function\([^)]+\)[\s\S]*?except\s*(?:Exception)?\s*:\s*\n\s*)break',
                r'\1pass  # timeout, page.goto already loaded new content',
                code,
            )
        return code

    # ── Sanitizer: persistent context fallback ───────────────────────

    def _inject_persistent_context(self, code: str) -> str:
        """
        Emergency fallback: if the LLM ignored the persistent context
        instruction in the prompt, do a best-effort replacement.
        """
        if not self.user_data_dir:
            return code
        if "launch_persistent_context" in code:
            return code  # LLM got it right, no fallback needed
        if "browser.launch" not in code:
            return code  # already using persistent context or different API

        # Best-effort: replace browser.launch → launch_persistent_context
        # This is intentionally minimal to avoid breaking the script
        code = re.sub(
            r"browser\s*=\s*await\s+p\.chromium\.launch\(",
            f'context = await p.chromium.launch_persistent_context(\n'
            f'            user_data_dir="{self.user_data_dir}",\n'
            f'            ',
            code,
        )
        code = code.replace("await browser.close()", "await context.close()")
        return code

    # ── Sanitizer: inject save-to-file logic ─────────────────────────

    def _inject_file_save(self, code: str) -> str:
        """
        If the script only outputs to stdout (print), inject code to also
        save results to a JSON file alongside printing.
        """
        if "with open(" in code or "json.dump(" in code.replace("json.dumps", ""):
            return code  # already has file saving

        save_block = (
            '\n'
            '    output_file = "scraped_results.json"\n'
            '    with open(output_file, "w", encoding="utf-8") as f:\n'
            '        json.dump(all_results, f, indent=2, ensure_ascii=False)\n'
            '    print(f"Results saved to {output_file}")\n'
        )
        # Insert before the final print statement or before browser.close()
        code = re.sub(
            r'(\n    await browser\.close\(\))',
            save_block + r'\1',
            code,
        )
        # Also try inserting before print(json.dumps(...))
        if "with open(" not in code:
            code = re.sub(
                r'(print\(json\.dumps\()',
                save_block + r'    \1',
                code,
            )
        return code

    # ── Pagination analysis ──────────────────────────────────────────

    _PAGINATION_URL_PATTERNS = (
        r'href\s*=\s*["\'][^"\']*[?&](?:page|p|pagenum|start|offset|pg)=',
        r'href\s*=\s*["\']/[^"\']*/page/\d+',
    )
    _PAGINATION_CLICK_INDICATORS = (
        r'href\s*=\s*["\']#["\']',
        r'<button[^>]*>(?:Next|next|>)',
        r'role\s*=\s*["\']button["\']',
        r'onclick\s*=',
    )
    _APPEND_INDICATORS = (
        'load-more', 'load more', 'show-more', 'show more',
        'infinite-scroll', 'infinite scroll', 'lazy-load',
    )

    def _analyze_pagination(self, html_context: str, source_url: str) -> str:
        """
        Analyze HTML chunks to determine pagination type and generate a
        short, specific instruction for the LLM.

        Returns a concrete instruction string that replaces the generic
        "figure out the pagination" text in the prompt template.
        """
        ctx_lower = html_context.lower()
        has_url_pagination = any(
            re.search(pat, html_context, re.IGNORECASE)
            for pat in self._PAGINATION_URL_PATTERNS
        )
        has_click_pagination = any(
            re.search(pat, html_context, re.IGNORECASE)
            for pat in self._PAGINATION_CLICK_INDICATORS
        )
        is_append_style = any(
            indicator in ctx_lower
            for indicator in self._APPEND_INDICATORS
        )

        # ── Build the instruction ──────────────────────────────────

        if has_url_pagination:
            mode = "URL-BASED"
            nav_how = (
                "Extract the href from the Next link.  If the href is relative "
                "(starts with /), resolve it with urljoin(target_url, href) from "
                "urllib.parse.  Then call page.goto(full_url, wait_until="
                '"domcontentloaded").'
            )
        elif has_click_pagination:
            mode = "CLICK-BASED (AJAX)"
            nav_how = (
                "Click the Next button with await next_btn.click().  Do NOT "
                "construct new URLs — the URL in the address bar stays the same."
            )
        else:
            mode = "UNKNOWN"
            nav_how = (
                "Try clicking the Next button first.  If the button has a real "
                "href (not #), use urljoin() and page.goto() instead."
            )

        if is_append_style:
            style = "APPEND"
            detect_how = (
                "Count items before and after — the total count INCREASES as "
                "new items are appended."
            )
        else:
            style = "REPLACEMENT"
            detect_how = (
                "Capture a FINGERPRINT of the first item's inner_text() BEFORE "
                "navigating/clicking.  After loading, wait for the first item's "
                "text to CHANGE using page.wait_for_function().  Do NOT check "
                "the item count — replacement pagination keeps the same number "
                "of items per page (count never changes)."
            )

        instruction = (
            f"PAGINATION TYPE: {mode} | STYLE: {style}\n"
            f"How to navigate: {nav_how}\n"
            f"How to detect new content: {detect_how}\n"
            "Use a FALLBACK CHAIN of 8 selectors to find the Next button:\n"
            '  ["<best-from-HTML>", "a[rel=\'next\']", "li.next a",\n'
            '   "a:has-text(\'Next\')", "a:has-text(\'>\')", "a:has-text(\'»\')",\n'
            '   "[aria-label=\'Next\']", "[aria-label=\'next page\']"]'
        )

        self.logger.info(
            f"Pagination analysis: {mode} / {style} "
            f"(url={has_url_pagination}, click={has_click_pagination}, "
            f"append={is_append_style})"
        )

        # Store for sanitizers to conditionally enable/disable injections
        self._pagination_mode = mode
        self._pagination_style = style

        return instruction

    # ── CSS class extraction (anti-hallucination) ───────────────────

    _CLASS_RE = re.compile(r'class\s*=\s*["\']([^"\']+)["\']')
    _ID_RE = re.compile(r'id\s*=\s*["\']([^"\']+)["\']')

    def _extract_css_hints(self, html_context: str) -> str:
        """
        Extract all CSS class names and IDs from the HTML context and
        format them as a hint for the LLM.  This prevents selector
        hallucination — the LLM can only use selectors that actually exist.
        """
        classes: set[str] = set()
        ids: set[str] = set()

        for m in self._CLASS_RE.finditer(html_context):
            for c in m.group(1).split():
                c = c.strip()
                if c and len(c) > 1:
                    classes.add(f".{c}")

        for m in self._ID_RE.finditer(html_context):
            i = m.group(1).strip()
            if i and len(i) > 1:
                ids.add(f"#{i}")

        # Limit to a reasonable number
        top_classes = sorted(classes)[:30]
        top_ids = sorted(ids)[:10]

        parts = []
        if top_classes:
            parts.append("Classes: " + ", ".join(top_classes))
        if top_ids:
            parts.append("IDs: " + ", ".join(top_ids))

        if not parts:
            return "(no class names or IDs found in the HTML)"

        return "\n       ".join(parts)
