---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能
allowed-tools: Read, Grep, Glob, WebFetch
---

# GitHub Trending 采集技能

从 GitHub Trending 页面抓取本周/本月最热门的 AI/LLM/Agent 领域开源项目，过滤、排序后输出结构化 JSON 到 `knowledge/raw/`。

## 使用场景

- 每日/每周采集 GitHub 热门 AI 项目
- 需要追踪 AI/LLM/Agent 领域的最新开源动态
- 为知识库补充原始采集数据

## 执行步骤

### Step 1：搜索热门仓库

使用 `WebFetch` 抓取 GitHub Trending 页面：

```
https://github.com/trending?since=weekly
```

若页面加载不全可尝试 `https://api.github.com/search/repositories?q=...&sort=stars&order=desc` 作为补充。

### Step 2：提取信息

从每条结果中提取以下字段：

- `name` — 仓库全名（`owner/repo`）
- `url` — 仓库链接
- `description` — 项目描述
- `stars` — 本周获得 Star 数
- `language` — 主要编程语言
- `topics` — 项目标签（如 `ai`, `llm`, `agent`）

### Step 3：过滤

**纳入标准（满足任一即可）：**

- 项目标题或描述包含 `AI` / `LLM` / `Agent` / `GPT` / `Transformer` / `RAG` / `Copilot` / `Claude` / `LangChain` 等关键词
- 项目与机器学习、自然语言处理、智能体、AI 开发工具相关
- 项目描述明确提到使用大模型或 AI 能力

**排除标准：**

- Awesome 列表（标题以 `awesome-` 开头或描述包含 "A curated list of"）—— 此类项目为资源汇总而非原创工具，价值密度低
- 非 AI 领域的热门项目（如前端框架、操作系统、数据库等）

### Step 4：去重

与 `knowledge/raw/` 中已有的历史采集记录对比，剔除重复的 `name` 和 `url`。

### Step 5：撰写中文摘要

为每条通过过滤的项目撰写中文摘要（50 字以内），遵循以下公式：

```
项目名 + 做什么 + 为什么值得关注
```

**示例：**
- ✅ `mattpocock/skills` — Claude Code 实战技能集合，来自顶级工程师的开源配置，可即插即用
- ❌ `mattpocock/skills` 是一个包含 Claude Code 技能的项目 — 太笼统，缺少"为什么关注"

### Step 6：排序取 Top 15

按本周获得 Star 数从高到低降序排列，截取前 15 条。

### Step 7：输出 JSON

将结果写入 `knowledge/raw/github-trending-YYYY-MM-DD.json`，其中 `YYYY-MM-DD` 为执行日期。

## 输出格式

```json
{
  "source": "github_trending",
  "skill": "github-trending",
  "collected_at": "2026-05-07T12:00:00+08:00",
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "项目名 + 做什么 + 为什么值得关注（中文，50 字以内）",
      "stars": 20777,
      "language": "Python",
      "topics": ["ai", "llm", "agent"]
    }
  ]
}
```

## 注意事项

1. **频率控制** — 避免单次任务中多次请求 GitHub Trending 页面，建议每日最多采集一次
2. **网络容错** — 若 WebFetch 返回空或报错，等待 10 秒后重试一次；仍失败则终止并报告原因
3. **中文摘要** — summary 必须为中文，严格遵循"项目名 + 做什么 + 为什么关注"公式，不超过 50 字
4. **数字原始值** — `stars` 字段存原始整数值（如 `20777`），而非格式化字符串（如 `"20.8k"`），便于下游排序与聚合
5. **绝不编造** — 所有 URL 必须为真实可访问链接，禁止虚构仓库名或伪造数据
6. **合规** — 使用 GitHub 公开页面，遵循 `robots.txt`，不发送过高频率请求
