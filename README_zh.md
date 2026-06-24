# GraphSpider — 智能网页信息采集 Agent

[English](README.md) | [简体中文](README_zh.md)

给它一个网址，告诉它你想要什么。它会自动打开浏览器、分析页面、生成爬虫脚本、沙箱执行、自我修复——全程零代码。

## 快速开始

```bash
# 1. 安装
pip install graphspider
playwright install chromium

# 2. 设置 API Key
# Windows:
$env:DEEPSEEK_API_KEY="sk-..."
# macOS/Linux:
export DEEPSEEK_API_KEY="sk-..."

# 3. 运行（默认爬取知乎热榜）
python run.py
```

首次爬取需要登录的网站时，浏览器会自动弹出——扫码或输入密码登录一次，之后永久复用。

## 使用方式

### 命令行（一行搞定）

```bash
graphspider --url https://movie.douban.com/top250 --prompt "提取电影标题和评分"
```

### Python API（三行代码）

```python
from scrapegraphai import AgentLoop

agent = AgentLoop(
    prompt="提取商品名称和价格",
    source="https://books.toscrape.com/",
)
result = agent.run()
# result.success → True / False
# result.data    → 爬取到的 JSON 数据
```

### 自定义目标

```bash
# Windows:
$env:GRAPHSPIDER_URL="https://movie.douban.com/top250"
$env:GRAPHSPIDER_PROMPT="提取电影标题、评分和简介"

# macOS/Linux:
export GRAPHSPIDER_URL="https://movie.douban.com/top250"
export GRAPHSPIDER_PROMPT="提取电影标题、评分和简介"

python run.py
```

## 输出目录

```text
output/
├── scripts/
│   └── douban_crawler.py        # 生成的爬虫脚本
└── results/
    └── douban_results.json      # 爬取的数据

profiles/
└── douban/                      # 浏览器登录态（自动管理）
```

## 配置参数

```python
config = {
    # ── 大模型 ──
    "llm": {
        "api_key": "sk-...",
        "model": "openai/deepseek-coder",
        "base_url": "https://api.deepseek.com/v1",  # 使用 OpenAI 可不填
        "temperature": 0.0,
        "max_tokens": 4096,
    },

    # ── 输出 ──
    "output_file": "./output/scripts/crawler.py",   # 脚本路径
    "data_file": "./output/results/data.xlsx",       # 数据路径
    "output_format": "xlsx",                         # json | csv | jsonl | txt | xlsx

    # ── 行为 ──
    "max_items": 50,            # 最多爬取多少条
    "max_rounds": 3,            # 最多自愈重试轮数
    "headless": False,          # True = 隐藏浏览器窗口
    "verbose": False,           # True = 显示调试信息
    "execution_timeout": 120,   # 每次执行超时（秒）

    # ── 登录 ──
    "user_data_dir": "./profiles/zhihu",  # 浏览器持久化目录
    "wait_for_user": False,               # True = 弹窗等待手动登录
}
```

## 工作原理

```text
URL + 需求描述
    │
    ▼
┌───────────────────────────────────────┐
│ 1. 生成：LLM 分析页面 HTML，生成脚本   │
│ 2. 执行：沙箱运行脚本                  │
│ 3. 评估：检查结果是否正确              │
│ 4. 反思：诊断失败原因，智能重试        │
└───────────────────────────────────────┘
    │        ▲
    └────────┘  （最多 3 轮）
```

Agent 自动处理：

- 检测分页类型（URL 跳转 / 按钮点击 / 无限滚动）
- 反爬保护（隐身浏览器、代理支持）
- 过滤空骨架屏节点
- 自动修正 LLM 幻觉的 CSS 选择器
- 持久化浏览器登录态（登录一次，永久复用）

## 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | — |
| `OPENAI_API_KEY` | OpenAI API Key（备选） | — |
| `HTTPS_PROXY` | 代理地址 | `127.0.0.1:7890` |
| `GRAPHSPIDER_URL` | 目标网址 | `https://www.zhihu.com/hot` |
| `GRAPHSPIDER_PROMPT` | 提取需求 | `"Extract hot topics..."` |

## 适用网站

任意网站均可使用。已验证：

- 政府数据门户（加拿大统计局）
- 电商 / 内容网站（豆瓣、Books to Scrape）
- 需登录网站（知乎）
- JavaScript 重度 SPA

## License

MIT