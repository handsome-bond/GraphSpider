# 我写了一个会「自我修复」的爬虫 Agent，三行代码爬任何网站

> 给个网址，说句话，它自己写代码、自己跑、报错了自己修。

---

做 AI 后训练和 RAG 的都知道，高质量语料比模型本身还难搞。网上明明有海量数据，但每次写爬虫都要 F12 翻 DOM、试 CSS 选择器、处理翻页、修各种 corner case。换个网站又要重来一遍。

我花了两周做了 **GraphSpider**——开源了，来体验一下。

## 它干了什么

```
你: "帮我提取豆瓣 Top250 的电影名称、评分和简介"
Agent:
  1. 打开浏览器 → 分析页面 DOM → 提取 .hd .title .rating_num 等选择器
  2. 生成 Playwright 爬虫脚本 → 沙箱执行 → 检查结果
  3. ✅ 成功 → 输出 JSON
  4. ❌ 失败 → 诊断哪写错了（选择器不存在？翻页逻辑不对？）
         → 带着诊断结果重新生成 → 再跑（最多 3 轮）
```

全程你只做一件事：**说一句话**。不用写一行爬虫代码。

## 三个让我自己都觉得爽的点

### 1. 真·自愈

不是 if-else 重试，是真的分析失败原因：

```
Round 1: TIMEOUT — 生成的脚本用了 div.wb-tables，页面根本没有这个 class
         Agent: "div.wb-tables ❌ 不存在。页面实际有: .ndm-item, .ndm-result-title ✅"
         带着诊断重新生成

Round 2: SUCCESS — LLM 用了 .ndm-item，正确提取数据
```

### 2. 跨站泛化

同一套代码，不修改，已验证可以跑：

- 加拿大统计局（政府数据门户，替换式分页）
- 豆瓣 Top250（传统静态分页）
- 知乎热榜（需登录 + AJAX 动态加载）

### 3. 登录网站自动处理

第一次爬知乎 → 自动弹浏览器 → 扫码 → 回车 → 登录态永久保存。之后每次自动复用，无需手动提取 Cookie。

## 怎么用

```bash
pip install graphspider
playwright install chromium

# 一行命令
graphspider --url https://movie.douban.com/top250 --prompt "提取电影标题和评分"
```

或 Python 三行：

```python
from scrapegraphai import AgentLoop

agent = AgentLoop(
    prompt="提取热门话题标题和描述",
    source="https://www.zhihu.com/hot",
)
result = agent.run()
```

## 架构

```
LangGraph 状态机 + Playwright + DeepSeek API

ReAct 循环: Generate → Execute → Evaluate → Reflect & Fix → Retry
                                                        │
                                        智能诊断(选择器对比 + 跨轮记忆)
```

砍掉了旧版用正则往脚本里「硬塞代码」的套路（那个太容易出缩进错误和变量名不匹配），改成了：告诉 LLM 真实 DOM 结构，让它自己改。

## GitHub

[https://github.com/handsome-bond/GraphSpider](https://github.com/handsome-bond/GraphSpider)

Star ⭐ 就是最好的鼓励。有问题提 Issue，需求提 PR。