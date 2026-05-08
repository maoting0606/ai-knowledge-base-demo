# AI Knowledge Base Assistant — AGENTS.md

## 项目概述

自动从 GitHub Trending 和 Hacker News 采集 AI/LLM/Agent 领域的技术动态，经大模型分析后结构化存储为 JSON，并通过 Telegram / 飞书等多渠道分发的智能化知识库助手。

## 技术栈

| 类别 | 工具 |
|------|------|
| 运行时 | Python 3.12 |
| Agent 框架 | OpenCode + 国产大模型 |
| 工作流引擎 | LangGraph |
| 爬虫框架 | OpenClaw |
| 数据存储 | JSON 文件系统 |

## 编码规范

- **风格**：遵循 PEP 8，标识符使用 `snake_case`
- **文档**：Google 风格 docstring（含 Args / Returns / Raises）
- **日志**：使用 `logging` 模块，禁止裸 `print()`
- **类型**：所有函数签名必须标注类型注解
- **导入**：按标准库 → 第三方 → 本地模块分组，每组间空一行

## 项目结构

```
v1/
├── .opencode/
│   ├── agents/         # Agent 定义与提示词
│   ├── skills/         # 可复用的 Skill 模块
│   └── package.json
├── knowledge/
│   ├── raw/            # 未加工的原始采集数据
│   └── articles/       # AI 分析后的结构化知识条目
└── AGENTS.md           # 本文件
```

## 知识条目 JSON 格式

```json
{
  "id": "uuid-v4",
  "title": "string",
  "source_url": "string",
  "source_type": "github_trending | hacker_news",
  "summary": "string（AI 生成的中文摘要，200 字以内）",
  "tags": ["string"],
  "status": "pending | published | archived",
  "collected_at": "ISO-8601 datetime",
  "published_at": "ISO-8601 datetime | null"
}
```

## Agent 角色概览

| 角色 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Collector**（采集） | 定时爬取 GitHub Trending / Hacker News，过滤 AI/LLM/Agent 相关条目 | 外部信源 | `knowledge/raw/` 原始数据 |
| **Analyst**（分析） | 调用大模型对原始数据进行摘要、打标签、质量评分 | `knowledge/raw/` JSON | `knowledge/articles/` 结构化条目 |
| **Organizer**（整理） | 按策略编排分发渠道，控制推文频率与去重 | `knowledge/articles/` 数据 | Telegram / 飞书 消息 |

## 红线（绝对禁止）

1. **严禁** 在代码或配置中硬编码 Token / Secret / API Key
2. **严禁** 提交 `.env`、`credentials.json`、`*.key` 到版本控制
3. **严禁** 在 Agent 的 system prompt 中泄露项目内部路径或凭据
4. **严禁** 采集未经 robots.txt 许可的站点，或对目标施加过高频率的请求
5. **严禁** 跳过 lint / type-check 直接提交代码
