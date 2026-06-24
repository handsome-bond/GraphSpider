# GraphSpider — Autonomous Web Scraper Agent

Give it a URL and tell it what you want. It opens a browser, analyzes the page, generates a scraper, executes it, and auto-fixes any errors — all without writing crawling code.

## Quick Start

```bash
# 1. Install
pip install graphspider
playwright install chromium

# 2. Set your API key
# Windows:
$env:DEEPSEEK_API_KEY="sk-..."
# macOS/Linux:
export DEEPSEEK_API_KEY="sk-..."

# 3. Run (default: Zhihu hot topics)
python run.py
```

First time on a site requiring login, a browser opens — log in once, saved for all future runs.

## Usage

### CLI (one command)

```bash
graphspider --url https://movie.douban.com/top250 --prompt "Extract movie titles and ratings"
```

### Python API (3 lines)

```python
from scrapegraphai import AgentLoop

agent = AgentLoop(
    prompt="Extract product names and prices",
    source="https://books.toscrape.com/",
)
result = agent.run()
# result.success → bool
# result.data    → scraped JSON
```

### Customize target

```bash
# Windows:
$env:GRAPHSPIDER_URL="https://movie.douban.com/top250"
$env:GRAPHSPIDER_PROMPT="Extract titles, ratings, quotes"

# macOS/Linux:
export GRAPHSPIDER_URL="https://movie.douban.com/top250"
export GRAPHSPIDER_PROMPT="Extract titles, ratings, quotes"

python run.py
```

## Output

```text
output/
├── scripts/
│   └── douban_crawler.py        # generated Playwright scraper
└── results/
    └── douban_results.json      # scraped data

profiles/
└── douban/                      # browser session (auto-managed)
```

## Configuration

```python
config = {
    # ── LLM ──
    "llm": {
        "api_key": "sk-...",
        "model": "openai/deepseek-coder",
        "base_url": "https://api.deepseek.com/v1",  # omit for OpenAI
        "temperature": 0.0,
        "max_tokens": 4096,
    },

    # ── Output ──
    "output_file": "./output/scripts/crawler.py",   # script path
    "data_file": "./output/results/data.xlsx",       # data path
    "output_format": "xlsx",                         # json | csv | jsonl | txt | xlsx

    # ── Behavior ──
    "max_items": 50,            # stop after N items
    "max_rounds": 3,            # max self-healing retries
    "headless": False,          # True = browser hidden
    "verbose": False,           # True = debug output
    "execution_timeout": 120,   # seconds per execution attempt

    # ── Auth ──
    "user_data_dir": "./profiles/zhihu",  # persistent browser profile
    "wait_for_user": False,               # True = pause for manual login
}
```

## How It Works

```text
URL + Prompt
    │
    ▼
┌───────────────────────────────────────┐
│ 1. Generate:  LLM analyzes page HTML, │
│               writes Playwright script │
│ 2. Execute:   Sandbox runs the script │
│ 3. Evaluate:  Check results           │
│ 4. Reflect:   Diagnose failure,       │
│               regenerate smarter      │
└───────────────────────────────────────┘
    │        ▲
    └────────┘  (up to 3 rounds)
```

The agent automatically:

- Detects pagination type (URL-based / click-based / infinite scroll)
- Handles anti-bot protection (stealth browser, proxy via `HTTPS_PROXY`)
- Filters empty skeleton-screen nodes
- Auto-corrects hallucinated CSS selectors
- Supports persistent browser sessions (login once, reuse forever)

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | — |
| `HTTPS_PROXY` | Proxy address for anti-blocking | `127.0.0.1:7890` |
| `GRAPHSPIDER_URL` | Target website | `https://www.zhihu.com/hot` |
| `GRAPHSPIDER_PROMPT` | What to extract | `"Extract hot topics..."` |

## Supported Sites

Works on any website. Tested on:

- Government data portals (Statistics Canada)
- E-commerce / content sites (Douban, Books to Scrape)
- Login-required sites (Zhihu)
- JavaScript-heavy SPAs

## License

MIT
