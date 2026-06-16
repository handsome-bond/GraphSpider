"""
GraphSpider Autonomous Agent — closed-loop self-healing web scraper.

Usage:
    from scrapegraphai.agent import AgentLoop

    agent = AgentLoop(prompt="...", source="https://...", config={...})
    result = agent.run()
"""

from .agent_loop import AgentLoop

__all__ = ["AgentLoop"]
