"""
MergeAnswersNode Module
"""

from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..prompts import TEMPLATE_MERGE_SCRIPTS_PROMPT
from .base_node import BaseNode
from .generate_scraper_node import correct_urls_in_code


class MergeGeneratedScriptsNode(BaseNode):
    """
    A node responsible for merging scripts generated.
    Attributes:
        llm_model: An instance of a language model client, configured for generating answers.
        verbose (bool): A flag indicating whether to show print statements during execution.
    Args:
        input (str): Boolean expression defining the input keys needed from the state.
        output (List[str]): List of output keys to be updated in the state.
        node_config (dict): Additional configuration for the node.
        node_name (str): The unique identifier name for the node, defaulting to "GenerateAnswer".
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "MergeGeneratedScripts",
    ):
        super().__init__(node_name, "node", input, output, 2, node_config)

        self.llm_model = node_config["llm_model"]
        self.verbose = (
            False if node_config is None else node_config.get("verbose", False)
        )
        source_urls = node_config.get("source_urls", []) if node_config else []
        # Normalize: a bare string would be iterated character-by-character.
        if isinstance(source_urls, str):
            source_urls = [source_urls]
        self.source_urls = source_urls

    def execute(self, state: dict) -> dict:
        """
        Executes the node's logic to merge the answers from multiple graph instances into a
        single answer.
        Args:
            state (dict): The current state of the graph. The input keys will be used
                            to fetch the correct data from the state.
        Returns:
            dict: The updated state with the output key containing the generated answer.
        Raises:
            KeyError: If the input keys are not found in the state, indicating
                      that the necessary information for generating an answer is missing.
        """

        self.logger.info(f"--- Executing {self.node_name} Node ---")

        input_keys = self.get_input_keys(state)

        input_data = [state[key] for key in input_keys]

        user_prompt = input_data[0]
        scripts = input_data[1]

        # Short-circuit: a single script doesn't need merging.
        # Passing it through the LLM will only re-introduce bugs that the
        # GenerateScraperNode sanitizers already fixed.
        if isinstance(scripts, list) and len(scripts) == 1:
            answer = scripts[0]
            # Still apply URL correction as a safety net.
            for url in self.source_urls:
                answer = correct_urls_in_code(answer, url)
            state.update({self.output[0]: answer})
            return state

        scripts_str = ""
        for i, script in enumerate(scripts):
            scripts_str += "-----------------------------------\n"
            scripts_str += f"SCRIPT URL {i + 1}\n"
            scripts_str += "-----------------------------------\n"
            scripts_str += script

        # Build the source URLs block for the prompt so the LLM knows
        # exactly which URLs to use.
        urls_block = ""
        if self.source_urls:
            urls_block = "\n".join(
                f"  URL {i + 1}: {url}" for i, url in enumerate(self.source_urls)
            )
        else:
            urls_block = "  (preserve the URL(s) from the input scripts — do NOT change them)"

        prompt_template = PromptTemplate(
            template=TEMPLATE_MERGE_SCRIPTS_PROMPT,
            input_variables=["user_prompt"],
            partial_variables={
                "scripts": scripts_str,
                "source_urls": urls_block,
            },
        )

        merge_chain = prompt_template | self.llm_model | StrOutputParser()
        answer = merge_chain.invoke({"user_prompt": user_prompt})

        # Post-merge URL correction — the merge LLM can re-hallucinate URLs.
        # Apply correction for every known source URL.
        for url in self.source_urls:
            corrected = correct_urls_in_code(answer, url)
            if corrected != answer:
                self.logger.warning(
                    f"{self.node_name}: Hallucinated URL corrected back to {url}"
                )
                answer = corrected

        state.update({self.output[0]: answer})
        return state
