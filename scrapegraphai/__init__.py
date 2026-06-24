"""
GraphSpider — autonomous web scraper agent.

    from scrapegraphai import AgentLoop
    agent = AgentLoop(prompt="Extract data", source="https://example.com")
    result = agent.run()
"""

from .agent import AgentLoop
from .utils.logging import get_logger, set_verbosity_info

logger = get_logger(__name__)
set_verbosity_info()

__all__ = ["AgentLoop"]
