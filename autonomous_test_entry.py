"""
GraphSpider Agent — zero-code autonomous web scraper entry point.

Usage:
    python autonomous_test_entry.py
"""

import os
from scrapegraphai.agent import AgentLoop


# ── Output paths ────────────────────────────────────────────────
OUTPUT_DIR = "./output"
SCRIPTS_DIR = os.path.join(OUTPUT_DIR, "scripts")
RESULTS_DIR = os.path.join(OUTPUT_DIR, "results")
PROFILES_DIR = "./profiles"

SITE = "zhihu"
SOURCE_URL = "https://www.zhihu.com/hot"
USER_DATA_DIR = os.path.join(PROFILES_DIR, SITE)


def main():
    # Ensure directories exist
    for d in [SCRIPTS_DIR, RESULTS_DIR, PROFILES_DIR]:
        os.makedirs(d, exist_ok=True)

    first_run = not os.path.exists(USER_DATA_DIR)

    if first_run:
        print(f"First run for {SITE} — please log in when the browser opens.")
        loader_cfg = {
            "user_data_dir": USER_DATA_DIR,
            "wait_for_user": True,
        }
    else:
        print(f"Reusing saved session: {USER_DATA_DIR}")
        loader_cfg = {"user_data_dir": USER_DATA_DIR}

    agent = AgentLoop(
        prompt=(
            "Extract the main dataset results list. "
            "Fields: title, product_info, release_date, description."
        ),
        source=SOURCE_URL,
        config={
            "llm": {
                "api_key": "sk-972f499a3b314aaaa722d78325ab3461",
                "model": "openai/deepseek-coder",
                "base_url": "https://api.deepseek.com/v1",
                "temperature": 0.0,
                "max_tokens": 4096,
            },
            "verbose": True,
            "headless": False,
            "delay": 15,
            "library": "playwright",
            "output_file": os.path.join(SCRIPTS_DIR, f"{SITE}_hot.py"),
            "data_file": os.path.join(RESULTS_DIR, f"{SITE}_hot.json"),
            "output_format": "json",
            "max_items": 50,
            "max_rounds": 3,
            "execution_timeout": 120,
            **loader_cfg,
        },
    )

    result = agent.run()

    print("\n" + "=" * 60)
    print(f"Success:     {result.success}")
    print(f"Rounds:      {result.total_rounds}")
    print(f"Error:       {result.error}")
    print("=" * 60)

    if result.history:
        print("\nRound history:")
        for r in result.history:
            print(f"  Round {r['round']}: {r['error_type']} → {r['fix_strategy']}")

    if result.success and result.data:
        print(f"\nScraped data ({len(result.data)} chars):")
        print(result.data[:500])


if __name__ == "__main__":
    main()
