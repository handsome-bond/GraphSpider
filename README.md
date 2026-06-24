# GraphSpider — Autonomous Web Scraper Agent

Give it a URL and tell it what you want. It generates a scraper, runs it in a sandbox, checks the results, and auto-fixes errors — all without writing a single line of crawling code.

## Quick Start

```bash
pip install graphspider
playwright install chromium

# Set your API key
export DEEPSEEK_API_KEY="sk-..."

# Scrape anything
graphspider --url https://www.zhihu.com/hot --prompt "Extract hot topics with titles and descriptions"
```

First time you run on a site requiring login, a browser opens — log in once, and it's saved for all future runs.

## Python API

```python
from scrapegraphai import AgentLoop

agent = AgentLoop(
    prompt="Extract product names, prices, and ratings",
    source="https://books.toscrape.com/",
)

result = agent.run()
# result.success → True
# result.data    → '[{"title": "...", "price": "..."}]'
```

## How It Works

```
URL + Prompt
    │
    ▼
┌─────────────────────────────────┐
│  Generate:  LLM writes scraper  │
│  Execute:   Sandbox runs it     │
│  Evaluate:  Check results       │
│  Reflect:   Diagnose failure,   │
│             re-generate smarter │
└─────────────────────────────────┘
    │        ▲
    └────────┘  (up to 3 rounds)
```

The agent automatically:
- Detects pagination type (URL-based / click-based / infinite scroll)
- Handles anti-bot protection (stealth browser, proxy support)
- Filters empty skeleton-screen nodes
- Saves results as JSON/CSV/JSONL

## Configuration

```python
config = {
    "llm": {
        "api_key": "sk-...",
        "model": "openai/deepseek-coder",
        "base_url": "https://api.deepseek.com/v1",
    },
    "output_file": "crawler.py",      # Save generated script
    "data_file": "results.json",      # Save scraped data
    "output_format": "json",          # json | csv | jsonl | txt
    "max_items": 50,                  # Stop after N items
    "max_rounds": 3,                  # Max self-healing retries
    "headless": False,                # Show browser window
    "verbose": True,                  # Print diagnostic logs
}
```

## License

MIT
