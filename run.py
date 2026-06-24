"""
GraphSpider — 3-line usage demo.

    $env:DEEPSEEK_API_KEY = "sk-..."   # Windows
    export DEEPSEEK_API_KEY="sk-..."   # macOS/Linux
    python run.py
"""

import os
from scrapegraphai import AgentLoop

# ── Config ──
API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("Set DEEPSEEK_API_KEY or OPENAI_API_KEY environment variable")

URL = os.environ.get("GRAPHSPIDER_URL", "https://www.zhihu.com/hot")
PROMPT = os.environ.get("GRAPHSPIDER_PROMPT", "Extract hot topics with titles and descriptions")

site = URL.split("//")[-1].split("/")[0].split(".")[0]
os.makedirs(f"./profiles/{site}", exist_ok=True)
os.makedirs("./output/scripts", exist_ok=True)
os.makedirs("./output/results", exist_ok=True)

agent = AgentLoop(
    prompt=PROMPT,
    source=URL,
    config={
        "llm": {
            "api_key": API_KEY,
            "model": "openai/deepseek-coder",
            "base_url": "https://api.deepseek.com/v1",
            "temperature": 0.0,
            "max_tokens": 4096,
        },
        "verbose": False,
        "headless": False,
        "library": "playwright",
        "output_file": f"./output/scripts/{site}_crawler.py",
        "data_file": f"./output/results/{site}_results.json",
        "output_format": "json",
        "max_items": 50,
        "max_rounds": 3,
        "execution_timeout": 120,
        "user_data_dir": f"./profiles/{site}",
        "wait_for_user": not os.path.exists(f"./profiles/{site}"),
    },
)

result = agent.run()
print(f"\nSuccess: {result.success} | Rounds: {result.total_rounds}")
if result.error:
    print(f"Error: {result.error}")
if result.data:
    print(result.data[:500])
