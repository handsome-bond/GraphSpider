"""
GraphSpider CLI — one command to scrape anything.

    graphspider --url https://www.zhihu.com/hot --prompt "Extract hot topics"

Or with Python:

    from scrapegraphai import AgentLoop
    agent = AgentLoop(prompt="Extract data", source="https://example.com")
    result = agent.run()
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="GraphSpider — autonomous web scraper agent"
    )
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--prompt", required=True, help="What to extract")
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--max-items", type=int, default=50)
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()

    # API key from environment
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Set DEEPSEEK_API_KEY or OPENAI_API_KEY environment variable.")
        sys.exit(1)

    # Auto-detect model provider
    if os.environ.get("DEEPSEEK_API_KEY"):
        model = "openai/deepseek-coder"
        base_url = "https://api.deepseek.com/v1"
    else:
        model = os.environ.get("GRAPHSPIDER_MODEL", "openai/gpt-4o")
        base_url = os.environ.get("GRAPHSPIDER_BASE_URL")

    site = args.url.split("//")[-1].split("/")[0].split(".")[0]
    os.makedirs(f"{args.output}/scripts", exist_ok=True)
    os.makedirs(f"{args.output}/results", exist_ok=True)
    os.makedirs("./profiles", exist_ok=True)

    from scrapegraphai import AgentLoop

    agent = AgentLoop(
        prompt=args.prompt,
        source=args.url,
        config={
            "llm": {
                "api_key": api_key,
                "model": model,
                "base_url": base_url,
                "temperature": 0.0,
                "max_tokens": 4096,
            },
            "verbose": not args.quiet,
            "headless": args.headless,
            "library": "playwright",
            "output_file": f"{args.output}/scripts/{site}_crawler.py",
            "data_file": f"{args.output}/results/{site}_results.json",
            "output_format": "json",
            "max_items": args.max_items,
            "max_rounds": args.max_rounds,
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
