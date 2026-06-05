# Autonomous Web Scraping Agent — 实现方案

> 将 Scrapegraph-ai 从「单向流水线」升级为「闭环自修复 Agent」。
>
> 状态机：LangGraph · 路由模式：ReAct (Generate → Execute → Evaluate → Reflect & Fix → Retry)

---

## 一、目标架构

```
autonomous_test_entry.py          ← 用户唯一入口
        │
        ▼
┌─────────────────────────────────────────────────┐
│  AutonomousScraperGraph (LangGraph StateGraph)   │
│                                                   │
│   ┌──────────┐                                    │
│   │ GENERATE │  调 ScriptCreatorMultiGraph        │
│   │          │  生成爬虫脚本                       │
│   └────┬─────┘                                    │
│        │                                          │
│   ┌───▼──────┐                                    │
│   │ EXECUTE  │  ExecutorFactory → 沙箱执行脚本     │
│   │          │  捕获 stdout / stderr / exit_code    │
│   └────┬─────┘                                    │
│        │                                          │
│   ┌───▼──────┐     ┌──────────────────┐          │
│   │ EVALUATE │ ──▶ │ ✅ PASS          │ → END    │
│   │          │     │ ❌ FAIL          │          │
│   └────┬─────┘     │ 🔄 retry < 3    │          │
│        │           └──────────────────┘          │
│   ┌───▼──────┐                                    │
│   │ REFLECT  │  分析错误 → 生成修复策略            │
│   │  & FIX   │  sanitizer 快修 / LLM 重新生成     │
│   └────┬─────┘                                    │
│        │                                          │
│        └──→ GENERATE (retry)                      │
│                                                   │
│  State: {script, stdout, stderr, retry_count,     │
│          last_error, fix_strategy, ...}            │
└─────────────────────────────────────────────────┘
```

---

## 二、目录结构变更

```
Scrapegraph-ai/
├── autonomous_test_entry.py              # [★ 新增] 零代码 Agent 入口
│
└── scrapegraphai/
    │
    ├── config.py                          # [★ 新增] 全局配置 + ExecutionMode
    │
    ├── state/                             # [★ 新增] 状态管理
    │   ├── __init__.py
    │   └── autonomous_state.py            # AutonomousState TypedDict
    │
    ├── executors/                         # [★ 新增] 执行器引擎
    │   ├── __init__.py                    # ExecutorFactory
    │   ├── base_executor.py               # AbstractExecutor 基类
    │   ├── local_executor.py              # Subprocess 本地执行器
    │   ├── docker_executor.py             # [预留] Docker 沙箱
    │   └── e2b_cloud_executor.py          # [预留] E2B 云沙箱
    │
    ├── graphs/
    │   ├── autonomous_scraper_graph.py    # [★ 新增] LangGraph 循环图
    │   ├── script_creator_multi_graph.py  # [🔄 修改] 降级为 tool（被 Agent 调用）
    │   ├── script_creator_graph.py        # [不变]
    │   ├── smart_scraper_graph.py         # [不变]
    │   ├── smart_scraper_multi_graph.py   # [不变]
    │   ├── search_graph.py                # [不变]
    │   ├── abstract_graph.py              # [不变]
    │   └── base_graph.py                  # [不变]
    │
    ├── nodes/
    │   ├── execute_script_node.py         # [★ 新增] 动作节点：调 Executor 执行
    │   ├── evaluate_node.py               # [★ 新增] 质检节点：判 Pass/Fail
    │   ├── reflect_and_fix_node.py        # [★ 新增] 反思节点：分析错误 → 修复
    │   ├── generate_scraper_node.py       # [🔄 修改] 接收 reflection_context
    │   └── ... (其余 10 个节点不变)
    │
    ├── prompts/
    │   ├── reflect_node_prompts.py        # [★ 新增] 错误分析 prompt
    │   └── ... (其余 6 个模板不变)
    │
    └── utils/
        ├── error_classifier.py            # [★ 新增] 错误分类：超时/403/语法/
        ├── diff_applier.py                # [★ 新增] LLM 修改精准合入原脚本
        └── ... (其余 15 个工具不变)
```

---

## 三、逐个文件设计

### 3.1 `scrapegraphai/config.py` — 全局配置

```python
from enum import Enum

class ExecutionMode(str, Enum):
    LOCAL = "local"       # 本机 subprocess（默认）
    DOCKER = "docker"     # [未来] Docker 沙箱
    E2B = "e2b"           # [未来] 云端沙箱

class FixStrategy(str, Enum):
    SANITIZE = "sanitize"       # 正则快速修（不调 LLM）
    REGENERATE = "regenerate"   # 调 LLM 重新生成
    STEALTH_BOOST = "stealth"   # 加强反爬后重生成

DEFAULT_CONFIG = {
    "max_rounds": 3,
    "execution_timeout": 60,
    "execution_mode": ExecutionMode.LOCAL,
}
```

### 3.2 `scrapegraphai/state/autonomous_state.py` — 全局状态

```python
from typing import TypedDict, List, Optional

class AutonomousState(TypedDict):
    # 输入
    prompt: str
    source: str
    config: dict

    # 当前脚本
    script: str                          # 最新脚本代码
    script_history: List[str]            # 所有版本的脚本

    # 执行结果
    stdout: str                          # 爬虫打印的输出
    stderr: str                          # 爬虫的错误输出
    exit_code: int                       # 进程退出码
    timed_out: bool                      # 是否超时

    # 评估结果
    is_success: bool                     # 本轮成功？
    error_type: str                      # "TIMEOUT" / "JS_SYNTAX" / ...
    error_summary: str                   # 人类可读的错误摘要
    failure_reason: str                  # 失败的具体原因

    # 控制
    retry_count: int                     # 当前是第几轮 (0-based)
    max_rounds: int                      # 最大轮数
    fix_strategy: str                    # "sanitize" / "regenerate"
    round_history: List[dict]            # 每轮的完整记录
```

### 3.3 `scrapegraphai/executors/` — 执行器引擎

#### `base_executor.py`
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool

class AbstractExecutor(ABC):
    @abstractmethod
    def execute(self, script: str, timeout: int = 60) -> ExecutionResult:
        ...
```

#### `local_executor.py`
```python
import subprocess, tempfile, os

class LocalExecutor(AbstractExecutor):
    def execute(self, script: str, timeout: int = 60) -> ExecutionResult:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            tmp_path = f.name

        try:
            proc = subprocess.run(
                ["python", tmp_path],
                capture_output=True, text=True, timeout=timeout
            )
            return ExecutionResult(
                stdout=proc.stdout, stderr=proc.stderr,
                exit_code=proc.returncode, timed_out=False
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(stdout="", stderr="TimeoutExpired",
                                   exit_code=-1, timed_out=True)
        finally:
            os.unlink(tmp_path)
```

#### `__init__.py` — 工厂
```python
from ..config import ExecutionMode

class ExecutorFactory:
    @staticmethod
    def create(mode: ExecutionMode) -> AbstractExecutor:
        if mode == ExecutionMode.LOCAL:
            from .local_executor import LocalExecutor
            return LocalExecutor()
        # docker / e2b 未来实现
        raise ValueError(f"Unsupported mode: {mode}")
```

### 3.4 `scrapegraphai/utils/error_classifier.py` — 错误分类器

```python
import re
from dataclasses import dataclass

@dataclass
class ErrorClassification:
    error_type: str
    severity: str       # "FATAL" | "RECOVERABLE"
    suggestion: str

class ErrorClassifier:
    PATTERNS = [
        # (regex, error_type, severity, suggestion)
        (r"Timeout \d+ms exceeded.*waiting for locator",
         "TIMEOUT", "RECOVERABLE", "选择器未匹配，需检查页面 DOM"),

        (r"SyntaxError.*", "JS_SYNTAX", "FATAL",
         "JavaScript 语法错误，需要 escape 特殊字符"),

        (r"NameError: name '(\w+)' is not defined",
         "NAME_ERROR", "FATAL", "变量名拼写错误"),

        (r"IndentationError", "INDENT_ERROR", "FATAL",
         "缩进错误"),

        (r"403|Forbidden|Access Denied",
         "HTTP_403", "RECOVERABLE", "被反爬拦截，需加强代理/指纹"),

        (r"ERR_TUNNEL_CONNECTION_FAILED|ERR_PROXY_CONNECTION",
         "PROXY_ERROR", "RECOVERABLE", "代理连接失败，检查 Clash"),

        (r"^\s*\[\s*\]\s*$", "EMPTY_RESULT", "RECOVERABLE",
         "爬取成功但数据为空，选择器可能不匹配"),
    ]

    @classmethod
    def classify(cls, stderr: str, stdout: str) -> ErrorClassification:
        for pattern, etype, severity, suggestion in cls.PATTERNS:
            if re.search(pattern, stderr + stdout, re.IGNORECASE | re.DOTALL):
                return ErrorClassification(etype, severity, suggestion)
        if not stdout.strip():
            return ErrorClassification("EMPTY_OUTPUT", "RECOVERABLE", "无任何输出")
        return ErrorClassification("UNKNOWN", "RECOVERABLE", "未匹配已知错误模式")
```

### 3.5 `scrapegraphai/utils/diff_applier.py` — 差异合并

```python
import re

def apply_llm_fix(original: str, llm_output: str) -> str:
    """
    LLM 输出可能是完整脚本或带 diff 标记的片段。
    1. 如果 LLM 返回完整脚本 → 直接使用
    2. 如果 LLM 返回 ```python ... ``` → 提取
    3. 如果 LLM 返回带注释的修复 → 尝试合并
    """
    # 提取代码块
    code_match = re.search(r"```python\s*(.*?)\s*```", llm_output, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()

    # 如果 LLM 返回的是完整脚本（import 开头），直接用
    if llm_output.strip().startswith("import"):
        return llm_output.strip()

    # 否则当作片段：尝试把 FIX 描述后的代码块找出来
    return llm_output.strip()
```

### 3.6 `scrapegraphai/prompts/reflect_node_prompts.py` — 反思 prompt

```python
TEMPLATE_ERROR_ANALYSIS = """
You are an expert Python debugger for Playwright web scrapers.

The scraper script below FAILED with the following error:
  ERROR TYPE: {error_type}
  STDERR: {stderr}
  STDOUT: {stdout}

The CURRENT script is:
```python
{script}
```

Your job: fix the script so it runs successfully and extracts the data.

RULES:
1. If the error is a NameError (undefined variable) → fix the variable name
2. If the error is a Timeout (selector not found) → the CSS selector is wrong.
   Look at what selectors ARE available and use those instead.
3. If the error is 403 Forbidden → add stronger anti-detection measures
4. If the output is empty → the CSS selectors don't match. Fix them.
5. NEVER change the target URL unless it's clearly a typo in the code.
6. Output ONLY the complete corrected Python script — no explanation.
"""
```

### 3.7 `scrapegraphai/nodes/execute_script_node.py` — 执行节点

```python
from ..executors import ExecutorFactory
from ..state.autonomous_state import AutonomousState

def execute_script_node(state: AutonomousState) -> AutonomousState:
    executor = ExecutorFactory.create(state["config"].get("execution_mode"))
    result = executor.execute(state["script"], state["config"].get("execution_timeout", 60))
    state["stdout"] = result.stdout
    state["stderr"] = result.stderr
    state["exit_code"] = result.exit_code
    state["timed_out"] = result.timed_out
    return state
```

### 3.8 `scrapegraphai/nodes/evaluate_node.py` — 质检节点

```python
from ..utils.error_classifier import ErrorClassifier
from ..state.autonomous_state import AutonomousState

def evaluate_node(state: AutonomousState) -> dict:
    """Returns LangGraph routing decision."""
    classification = ErrorClassifier.classify(state["stderr"], state["stdout"])

    state["error_type"] = classification.error_type
    state["error_summary"] = classification.suggestion

    if not state["stderr"] and state["stdout"].strip():
        # 检查输出是否包含有效 JSON / 数据
        if "[]" not in state["stdout"] or len(state["stdout"]) > 10:
            state["is_success"] = True
            return {"next": "END"}                    # → 成功结束

    state["is_success"] = False
    state["retry_count"] += 1

    if state["retry_count"] >= state["max_rounds"]:
        return {"next": "END"}                        # → 超过最大轮数

    return {"next": "reflect_and_fix"}                 # → 进入修复
```

### 3.9 `scrapegraphai/nodes/reflect_and_fix_node.py` — 反思修复

```python
from langchain_core.prompts import PromptTemplate

from ..prompts.reflect_node_prompts import TEMPLATE_ERROR_ANALYSIS
from ..utils.diff_applier import apply_llm_fix
from ..state.autonomous_state import AutonomousState
from ..nodes.generate_scraper_node import correct_urls_in_code


def reflect_and_fix_node(state: AutonomousState) -> AutonomousState:
    error_type = state["error_type"]

    # ── 轻量级修复（不调 LLM）─────────────────────────────
    if error_type in ("NAME_ERROR", "INDENT_ERROR"):
        # 直接调 sanitizer 管道
        from ..nodes.generate_scraper_node import GenerateScraperNode
        # 复用已有的 9 个 sanitizer
        state["fix_strategy"] = "sanitize"
        state["script"] = _apply_sanitizers(state["script"], state["source"])
        return state

    # ── 重量级修复（调 LLM）───────────────────────────────
    state["fix_strategy"] = "regenerate"

    prompt = PromptTemplate(
        template=TEMPLATE_ERROR_ANALYSIS,
        input_variables=["error_type", "stderr", "stdout", "script"],
    )
    chain = prompt | state["config"]["llm"] | StrOutputParser()
    llm_response = chain.invoke({
        "error_type": error_type,
        "stderr": state["stderr"],
        "stdout": state["stdout"],
        "script": state["script"],
    })

    new_script = apply_llm_fix(state["script"], llm_response)
    new_script = correct_urls_in_code(new_script, state["source"])
    state["script_history"].append(state["script"])
    state["script"] = new_script

    return state
```

### 3.10 `scrapegraphai/graphs/autonomous_scraper_graph.py` — 主图

```python
from langgraph.graph import StateGraph, END

from ..state.autonomous_state import AutonomousState
from ..nodes.execute_script_node import execute_script_node
from ..nodes.evaluate_node import evaluate_node
from ..nodes.reflect_and_fix_node import reflect_and_fix_node
from .script_creator_multi_graph import ScriptCreatorMultiGraph


def _generate_node(state: AutonomousState) -> AutonomousState:
    """第 1 轮：调 ScriptCreatorMultiGraph 生成初始脚本。
       后续轮：用 reflect_and_fix 修复后的脚本。"""
    if state["retry_count"] == 0:
        graph = ScriptCreatorMultiGraph(
            prompt=state["prompt"],
            source=state["source"],
            config=state["config"],
        )
        state["script"] = graph.run()
        state["script_history"] = [state["script"]]
    # retry_count > 0 → 脚本已经在 reflect_and_fix 中更新
    return state


def build_autonomous_graph() -> StateGraph:
    workflow = StateGraph(AutonomousState)

    workflow.add_node("generate", _generate_node)
    workflow.add_node("execute", execute_script_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("reflect_and_fix", reflect_and_fix_node)

    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "execute")
    workflow.add_edge("execute", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        lambda s: s.get("next", "reflect_and_fix"),
        {
            "reflect_and_fix": "reflect_and_fix",
            "END": END,
        },
    )

    workflow.add_edge("reflect_and_fix", "generate")

    return workflow.compile()
```

### 3.11 `autonomous_test_entry.py` — 用户入口

```python
from scrapegraphai.config import ExecutionMode
from scrapegraphai.graphs.autonomous_scraper_graph import build_autonomous_graph


def main():
    graph = build_autonomous_graph()

    result = graph.invoke({
        "prompt": "Extract dataset results. Fields: title, product_info, date, description.",
        "source": "https://www150.statcan.gc.ca/n1/en/type/data?MM=1",
        "config": {
            "llm": {"api_key": "...", "model": "openai/deepseek-coder",
                    "base_url": "https://api.deepseek.com/v1"},
            "output_file": "statcan_crawler.py",
            "output_format": "json",
            "max_items": 50,
            "max_rounds": 3,
            "execution_mode": ExecutionMode.LOCAL,
            "execution_timeout": 60,
        },
        "retry_count": 0,
        "max_rounds": 3,
        "script": "",
        "script_history": [],
    })

    print(f"Success: {result['is_success']}")
    print(f"Rounds: {result['retry_count']}")
    print(f"Final script:\n{result['script']}")


if __name__ == "__main__":
    main()
```

---

## 四、路由决策逻辑

```
                ┌─────────┐
                │ GENERATE │
                └────┬─────┘
                     │
                ┌────▼─────┐
                │ EXECUTE  │
                └────┬─────┘
                     │
                ┌────▼─────┐
                │ EVALUATE │
                └────┬─────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    stderr 为空  exit_code=0  stderr 非空
    stdout 有数据  stdout 非空  或 exit_code≠0
         │           │           │
         ▼           ▼           ▼
       ✅ PASS    ⚠️ EMPTY     ❌ FAIL
         │           │           │
        END      retry<3?    retry<3?
                    │           │
                    ▼           ▼
              REFLECT & FIX  REFLECT & FIX
              (LLM 重生成)   (查错误分类)
                    │           │
                    │      ┌────┴────┐
                    │      │ NAME_ERR │  TIMEOUT
                    │      │ INDENT   │  HTTP_403
                    │      └────┬────┘
                    │           │
                    │      ┌────┴────────────┐
                    │      ▼                 ▼
                    │  sanitizer 快修    LLM 重生成
                    │  (不调 LLM)       (调 LLM)
                    │      │                 │
                    └──────┴─────────────────┘
                           │
                      → GENERATE
```

---

## 五、实现顺序

| 阶段 | 文件 | 依赖 | 预估工作量 |
|------|------|------|-----------|
| **Phase 1**: 基础设施 | `config.py`、`state/`、`executors/`、`error_classifier.py` | 无 | 轻 |
| **Phase 2**: 新节点 | `execute_script_node.py`、`evaluate_node.py` | Phase 1 | 轻 |
| **Phase 3**: 反思循环 | `reflect_node_prompts.py`、`reflect_and_fix_node.py`、`diff_applier.py` | Phase 2 | 中 |
| **Phase 4**: 主编排 | `autonomous_scraper_graph.py` | Phase 1-3 | 中 |
| **Phase 5**: 修改现有 | `generate_scraper_node.py`（加 reflection_context）、`script_creator_multi_graph.py`（降级） | Phase 3 | 轻 |
| **Phase 6**: 入口 + 测试 | `autonomous_test_entry.py` | Phase 1-5 | 轻 |

---

## 六、关键设计权衡

| 决策 | 选择 | 理由 |
|------|------|------|
| 状态管理框架 | LangGraph | 原生支持 conditional edges + typed state，比手写 while 循环更可维护 |
| 执行器抽象 | `ExecutorFactory` + 策略模式 | 现在只用 local，但预留 Docker/E2B 接口不用改 Agent 代码 |
| 错误分类 | 正则 + 启发式 | 不调 LLM，零延迟零成本。覆盖 90%+ 常见错误 |
| 修复策略 | 两级：sanitize（快）→ regenerate（贵） | 语法错误 sanitizer 修，选择器/逻辑错误调 LLM 修 |
| 最大轮数 | 3 | 多数 bug 在 2 轮内修复；超过 3 轮说明有根本性问题 |
| 现有图兼容 | ScriptCreatorMultiGraph 作为 tool 被调用 | 不破坏现有功能，Agent 是外层包装 |
