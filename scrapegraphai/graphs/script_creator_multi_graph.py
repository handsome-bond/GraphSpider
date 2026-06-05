"""
ScriptCreatorMultiGraph Module — zero-code web scraper script generator.

Usage (minimal):
    >>> from scrapegraphai.graphs import ScriptCreatorMultiGraph
    >>> graph = ScriptCreatorMultiGraph(
    ...     prompt="Extract the dataset list",
    ...     source="https://example.com/data",
    ...     config={
    ...         "llm": {"api_key": "...", "model": "openai/deepseek-coder",
    ...                 "base_url": "https://api.deepseek.com/v1"},
    ...         "output_file": "crawler.py",
    ...         "max_items": 50,
    ...     },
    ... )
    >>> code = graph.run()  # generates script, saves to crawler.py, returns code
"""

import os
import re
from copy import deepcopy
from typing import List, Optional, Type

from pydantic import BaseModel

from ..nodes import GraphIteratorNode, MergeGeneratedScriptsNode
from ..utils.copy import safe_deepcopy
from .abstract_graph import AbstractGraph
from .base_graph import BaseGraph
from .script_creator_graph import ScriptCreatorGraph


class ScriptCreatorMultiGraph(AbstractGraph):
    """
    Zero-code scraper script generator.  Give it a URL + a description of what
    you want, and it produces a ready-to-run Python scraper.

    All the hard-learned rules (proxy, anti-detection, fingerprint pagination,
    CSS-selector discipline) are baked into the enriched prompt automatically —
    no need to write them yourself.

    Config keys (all optional):
        output_file (str):   Save the generated script to this path.
        max_items  (int):    Stop after collecting this many items (default 50).
        library    (str):    Scraping library for the generated script (default "playwright").
    """

    def __init__(
        self,
        prompt: str,
        source: List[str],
        config: dict,
        schema: Optional[Type[BaseModel]] = None,
    ):
        self.copy_config = safe_deepcopy(config)
        self.copy_schema = deepcopy(schema)

        # ── extract zero-code config keys ──
        self._output_file = config.get("output_file")           # the .py script
        self._output_format = config.get("output_format", "json")
        self._max_items = config.get("max_items", 50)
        self._library = config.get("library", "playwright")

        # Data file: where the scraper saves results.  Default: derive from
        # output_file name.  e.g. "crawler.py" → "crawler_results.json"
        if "data_file" in config:
            self._data_file = config["data_file"]
        elif self._output_file:
            base = self._output_file.rsplit(".", 1)[0]
            self._data_file = f"{base}_results.{self._output_format}"
        else:
            self._data_file = f"scraped_results.{self._output_format}"

        # Normalize source to list.
        if isinstance(source, str):
            source = [source]

        # Enrich the user prompt with hard-learned constraints unless the
        # user has already supplied detailed instructions.
        if not self._is_detailed_prompt(prompt):
            prompt = self._enrich_prompt(prompt, source, self._max_items)

        super().__init__(prompt, config, source, schema)

    # ── Prompt enrichment ──────────────────────────────────────────

    @staticmethod
    def _is_detailed_prompt(prompt: str) -> bool:
        """Heuristic: does the prompt already contain multi-page / selector rules?"""
        indicators = (
            "MULTI-PAGE", "MAX LIMIT", "CRITICAL RULES",
            "CSS CLASSES", "HALLUCINATIONS", "MUST use the exact",
        )
        return any(ind in prompt for ind in indicators)

    def _enrich_prompt(self, prompt: str, urls: list, max_items: int) -> str:
        """Append battle-tested constraints to a simple prompt."""
        fmt = self._output_format.lower()
        if fmt == "csv":
            save_rule = (
                f'6. SAVE TO CSV: after scraping, write results to '
                f'"{self._data_file}" using csv.DictWriter. '
                f'Import csv at the top.'
            )
        elif fmt == "jsonl":
            save_rule = (
                f'6. SAVE TO JSONL: after scraping, write each result as a JSON '
                f'line to "{self._data_file}".'
            )
        elif fmt == "txt":
            save_rule = (
                f'6. SAVE TO TXT: after scraping, write results as plain text to '
                f'"{self._data_file}".'
            )
        else:  # json (default)
            save_rule = (
                f'6. SAVE TO JSON: after scraping, write results to '
                f'"{self._data_file}" using json.dump '
                f'with indent=2 and ensure_ascii=False.'
            )

        rules = (
            f'\n\n'
            f'Generate a complete Python {self._library} script.\n\n'
            f'CRITICAL RULES (NO HALLUCINATIONS):\n'
            f'1. EXACT URL: Use the exact target URL. DO NOT change it.\n'
            f'2. CSS CLASSES from HTML only: look at the HTML chunks to find '
            f'real class names. Never invent BEM-style classes.\n'
            f'3. WAIT FOR DOM: always wait for the main item selector '
            f'before scraping.\n'
            f'4. MULTI-PAGE: if the page has pagination, scrape ALL pages. '
            f'Stop when you have collected exactly {max_items} items '
            f'or when the "Next" button is disabled/missing.\n'
            f'5. PROXY: use os.environ.get("HTTPS_PROXY", '
            f'"http://127.0.0.1:7890") for the browser proxy.\n'
            f'{save_rule}\n'
        )
        return (prompt + rules).strip()

    # ── Graph construction ─────────────────────────────────────────

    def _create_graph(self) -> BaseGraph:
        graph_iterator_node = GraphIteratorNode(
            input="user_prompt & urls",
            output=["scripts"],
            node_config={
                "graph_instance": ScriptCreatorGraph,
                "scraper_config": self.copy_config,
            },
            schema=self.copy_schema,
        )

        merge_scripts_node = MergeGeneratedScriptsNode(
            input="user_prompt & scripts",
            output=["merged_script"],
            node_config={
                "llm_model": self.llm_model,
                "schema": self.schema,
                "source_urls": self.source,
            },
        )

        return BaseGraph(
            nodes=[graph_iterator_node, merge_scripts_node],
            edges=[(graph_iterator_node, merge_scripts_node)],
            entry_point=graph_iterator_node,
            graph_name=self.__class__.__name__,
        )

    # ── Execution ──────────────────────────────────────────────────

    def run(self) -> str:
        """
        Generate the scraper script, strip markdown wrappers, and optionally
        save to disk.

        Returns:
            str: The generated Python script (clean, ready to run).
        """
        inputs = {"user_prompt": self.prompt, "urls": self.source}
        self.final_state, self.execution_info = self.graph.execute(inputs)

        code = self.final_state.get("merged_script", "")
        if not code or code.startswith("Failed"):
            return code

        # Strip ```python / ``` markdown wrappers.
        code = self._strip_markdown(code)

        # Auto-save if requested.
        if self._output_file:
            self._save_script(code, self._output_file)

        return code

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _strip_markdown(code: str) -> str:
        """Remove ```python / ``` fences that LLMs often wrap code in."""
        code = re.sub(r"^```python\s*", "", code, flags=re.IGNORECASE)
        code = re.sub(r"^```\s*", "", code)
        code = re.sub(r"\s*```$", "", code)
        return code.strip()

    def _save_script(self, code: str, path: str) -> None:
        """Write the generated script to disk."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        if self.verbose:
            print(f"[ScriptCreatorMultiGraph] Script saved → {path}")
