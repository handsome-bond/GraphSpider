# ScrapeGraphAI 项目结构

> 零代码网页爬虫脚本生成器。输入 URL + 需求描述，输出可运行的 Playwright 爬虫脚本。

---

## 根目录

```
Scrapegraph-ai/
├── .git/                         # Git 版本控制
├── .github/                      # CI/CD 工作流
├── .gitattributes                # Git 属性配置
├── .gitignore                    # Git 忽略规则
├── LICENSE                       # 开源协议
├── README.md                     # 项目说明
├── pyproject.toml                # Python 包配置（依赖、版本、构建）
├── pytest.ini                    # Pytest 测试配置
├── PROJECT_STRUCTURE.md          # 本文件：完整目录结构说明
├── test_new_architecture.py      # 零代码使用 Demo（ZERO-CODE ENTRY POINT）
├── statcan_v2_generated_crawler.py      # 生成的爬虫脚本（运行时产物）
└── scrapegraphai/                # 核心库
```

---

## `scrapegraphai/` — 核心库（70 个 `.py` 文件）

### `scrapegraphai/graphs/` — 图（7 文件）

图是 ScrapeGraphAI 的核心抽象——每个"图"是一个固定的节点管道，定义了一种爬虫工作流。

| 文件 | 功能 |
|------|------|
| `abstract_graph.py` | **抽象基类**。LLM 初始化、模型 token 计算、通用配置 |
| `base_graph.py` | **图执行引擎**。节点按 DAG 顺序执行，状态在节点间传递 |
| `script_creator_graph.py` | **单页脚本生成器**。Fetch → Parse → GenerateScraper，为单个 URL 生成爬虫脚本 |
| `script_creator_multi_graph.py` | **多页脚本生成器（★ 主力图）**。GraphIterator → MergeScripts。零代码入口，自动 prompt 增强、CSS 提取、markdown 清洗、文件保存 |
| `smart_scraper_graph.py` | **单页数据抓取器**。直接返回 JSON 数据（非脚本），支持 reasoning / html_mode |
| `smart_scraper_multi_graph.py` | **多页数据抓取器**。GraphIterator(SmartScraperGraph) → MergeAnswers |
| `search_graph.py` | **搜索引擎抓取器**。搜互联网 → 取前 N 条结果 → SmartScraperGraph 抓详情 |

### `scrapegraphai/nodes/` — 节点（12 文件）

节点是图管道中的处理单元，每个节点负责一个确定性的步骤。

| 文件 | 功能 |
|------|------|
| `base_node.py` | **节点基类**。定义 input/output key 解析、配置合并、日志 |
| `fetch_node.py` | **页面抓取**。ChromiumLoader 打开网页 → 获取 HTML → `script_creator=True` 时调用 `clean_html_for_script_creator()` 清洗 |
| `parse_node.py` | **HTML 解析**。DOM 感知分块（`_chunk_html_by_dom`），支持 `parse_html` / `parse_urls` 模式 |
| `generate_scraper_node.py` | **脚本生成（★ 核心）**。HTML 分析 → 分页类型检测 → prompt 模板 + CSS hints → 调 LLM → 9 个 sanitizer 后处理 |
| `generate_answer_node.py` | **答案生成**。多 chunk 并行调 LLM 提取数据 → 合并结果 |
| `graph_iterator_node.py` | **并行迭代**。为每个 URL 创建独立图实例，async 并发执行 |
| `merge_generated_scripts_node.py` | **脚本合并**。多 URL 脚本 → LLM 合并为单脚本（单 URL 直接短路跳过 LLM） |
| `merge_answers_node.py` | **答案合并**。多 URL 抓取结果 → LLM 合并去重 |
| `search_internet_node.py` | **搜索引擎查询**。调 search engine API 获取 URL 列表 |
| `conditional_node.py` | **条件分支**。根据表达式评估结果决定下一步 |
| `reasoning_node.py` | **推理节点**。迭代式 LLM 推理，多轮提取更准确 |
| `robots_node.py` | **robots.txt 检查**。解析 robots.txt，提取允许/禁止的路径 |

### `scrapegraphai/prompts/` — 提示词模板（7 文件）

| 文件 | 包含的模板 |
|------|-----------|
| `generate_answer_node_prompts.py` | `TEMPLATE_CHUNKS`、`TEMPLATE_NO_CHUNKS`、`TEMPLATE_MERGE` 及其 Markdown 变体、`REGEN_ADDITIONAL_INFO` |
| `merge_answer_node_prompts.py` | `TEMPLATE_COMBINED` — 合并多页抓取结果 |
| `merge_generated_scripts_prompts.py` | `TEMPLATE_MERGE_SCRIPTS_PROMPT` — 合并多个生成脚本（含反幻觉 URL 约束） |
| `reasoning_node_prompts.py` | `TEMPLATE_REASONING`、`TEMPLATE_REASONING_WITH_CONTEXT` |
| `robots_node_prompts.py` | `TEMPLATE_ROBOT` — robots.txt 解析 prompt |
| `search_internet_node_prompts.py` | `TEMPLATE_SEARCH_INTERNET` — 搜索关键词生成 prompt |
| `__init__.py` | 统一导出所有模板 |

### `scrapegraphai/utils/` — 工具（16 文件 + 1 子目录）

| 文件 | 功能 |
|------|------|
| `cleanup_html.py` | **HTML 清洗（★ 重要修改）**。`clean_html_for_script_creator()` — 去 script/style/head/注释/隐藏元素，保留 CSS 选择器属性，minify；`reduce_html()` — 三级压缩 |
| `convert_to_md.py` | HTML → Markdown 转换 |
| `copy.py` | `safe_deepcopy()` — 安全深拷贝，支持配置独立复制 |
| `custom_callback.py` | LangChain 自定义回调，Token 计数和时间统计 |
| `llm_callback_manager.py` | LLM 回调管理器，统一管理多个回调实例 |
| `logging.py` | 日志系统，支持多级别、格式化、Handler 管理 |
| `model_costs.py` | 各模型 token 价格表 |
| `output_parser.py` | Pydantic schema 输出解析器，兼容 V1/V2 |
| `proxy_rotation.py` | 代理服务器管理，`Proxy` 类、`parse_or_search_proxy()` |
| `research_web.py` | 多搜索引擎查询（Google、Bing、DuckDuckGo、Serper） |
| `schema_trasform.py` | Schema 格式转换 |
| `split_text_into_chunks.py` | 文本分块（semchunk + 回退 token 分块） |
| `sys_dynamic_import.py` | 动态模块导入（`dynamic_import`、`srcfile_import`） |
| `tokenizer.py` | Token 计数，统一 OpenAI tokenizer 接口 |
| `tokenizers/tokenizer_openai.py` | OpenAI tiktoken tokenizer 封装 |
| `__init__.py` | 统一导出（含 `clean_html_for_script_creator`） |

### `scrapegraphai/docloaders/` — 文档加载器（4 文件）

| 文件 | 功能 |
|------|------|
| `chromium.py` | **Playwright 浏览器加载器（★ 重要修改）**。支持 proxy、delay、自定义 UA/viewport/headers/timezone、navigator.webdriver 抹除、反检测启动参数 |
| `browser_base.py` | BrowserBase 云浏览器集成（可选） |
| `plasmate.py` | Plasmate 无头浏览器集成（可选） |
| `scrape_do.py` | Scrape.do 代理抓取集成（可选） |

### `scrapegraphai/models/` — LLM 适配器（8 文件）

每个文件封装一个 LLM 提供商的 ChatModel，统一 LangChain 接口。

| 文件 | 提供商 |
|------|--------|
| `deepseek.py` | DeepSeek（支持 `deepseek-coder`、`deepseek-chat`） |
| `openai_itt.py` | OpenAI Image-to-Text（视觉模型） |
| `openai_tts.py` | OpenAI Text-to-Speech |
| `oneapi.py` | OneAPI 统一网关 |
| `nvidia.py` | NVIDIA NIM |
| `clod.py` | CLoD |
| `minimax.py` | MiniMax |
| `xai.py` | xAI (Grok) |

### `scrapegraphai/helpers/` — 辅助模块（5 文件）

| 文件 | 功能 |
|------|------|
| `models_tokens.py` | 各模型默认 token 上限映射表 |
| `schemas.py` | 通用 Pydantic Schema 定义 |
| `default_filters.py` | 默认过滤规则（图片扩展名等） |
| `robots.py` | robots.txt 解析逻辑 |
| `nodes_metadata.py` | 节点元数据注册表 |

### `scrapegraphai/integrations/` — 集成（2 文件）

| 文件 | 功能 |
|------|------|
| `burr_bridge.py` | Burr 工作流引擎桥接（可选的状态追踪/可视化） |
| `scrapegraph_py_compat.py` | ScrapeGraph API 兼容层 |

### `scrapegraphai/telemetry/` — 遥测（2 文件）

| 文件 | 功能 |
|------|------|
| `telemetry.py` | 匿名使用统计上报（版本、图类型、token 消耗） |
| `__init__.py` | 导出 `log_graph_execution`、`log_event`、`disable_telemetry` |

### `scrapegraphai/__init__.py` — 顶层入口

日志初始化，设置默认 verbosity。

---

## `ScriptCreatorMultiGraph` 数据流全景

```
test_new_architecture.py
│  prompt + URL + config
│
└─→ ScriptCreatorMultiGraph.__init__()
    │  ├─ _is_detailed_prompt() → _enrich_prompt()
    │  │   自动注入 CRITICAL RULES / MULTI-PAGE / PROXY / SAVE
    │  └─ _create_graph()
    │
    └─→ run()
        │
        ├─ [Node 1] GraphIteratorNode
        │   └→ ScriptCreatorGraph (per URL)
        │      ├─ FetchNode: Playwright → HTML → clean_html_for_script_creator()
        │      ├─ ParseNode: _chunk_html_by_dom() → DOM 分块
        │      └─ GenerateScraperNode:
        │         ├─ _build_context() → 头+中+尾 分块采样
        │         ├─ _analyze_pagination() → URL/Click + Replace/Append
        │         ├─ _extract_css_hints() → class/id 列表
        │         ├─ PromptTemplate → LLM 生成脚本
        │         └─ _sanitize_script() → 9 个修复器:
        │            ├─ url_correction        URL 幻觉 → 正确 URL
        │            ├─ networkidle_removal   去掉 wait_until="networkidle"
        │            ├─ count_pagination      count 检测 → fingerprint 检测
        │            ├─ js_escape             JS 注入修复 (json.dumps)
        │            ├─ env_var_hallucination  URL-as-key → HTTPS_PROXY
        │            ├─ disabled_check        父 <li> disabled class 检测
        │            ├─ skeleton_filter       骨架屏空节点过滤
        │            ├─ proxy_injection       缺失代理自动注入
        │            └─ save_to_file          打印 → 文件保存
        │
        ├─ [Node 2] MergeGeneratedScriptsNode
        │   └→ 单 URL: 短路直传 + URL 修正
        │      多 URL: LLM 合并 + URL 修正
        │
        └─ 返回: _strip_markdown() → _save_script() → return code
```

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 图结构固定（不是 Agent） | 流程确定，LLM 只在关键决策点被嵌入，成本可控 |
| 9 个 sanitizer 后处理 | LLM 不可靠，正则后处理兜底——不依赖 LLM 听话 |
| 分块策略：≤5 块全保留 | 关键词过滤会把数据块误丢弃（CSS class 名 ≠ 可见文字） |
| CSS class 提取注入 prompt | 从 HTML 抽取真实的 class 列表，防止 LLM 幻觉选择器 |
| 合并节点单 URL 短路 | 避免 LLM 重生成脚本时 undo sanitizer 修复 |
| Fingerprint 替换 count 检测 | 政府/企业网站多用替换型分页，count 不会增加 |
| headless=False + proxy | 反爬不止靠 header，IP 和浏览器指纹同样重要 |

---

## 生成的爬虫脚本特性

通过 `ScriptCreatorMultiGraph` 生成的脚本自动包含：

- ✅ 代理支持（`HTTPS_PROXY` 环境变量 + Clash 默认 127.0.0.1:7890）
- ✅ 反检测（`headless=False`、真实 UA、navigator.webdriver 抹除、`--disable-blink-features`）
- ✅ DOM 稳定性（`wait_for_selector` + 随机延迟，不依赖盲等 timeout）
- ✅ 替换型分页检测（fingerprint 文本变化，而非 count 增加）
- ✅ 分页按钮 disabled 检测（检查父 `<li>` 的 Bootstrap class）
- ✅ 多选择器回退链（8 个 Next 按钮选择器）
- ✅ 骨架屏过滤（跳过空文本节点）
- ✅ 文件保存（JSON/CSV/JSONL/TXT，可配置）
- ✅ MAX_ITEMS 上限控制
