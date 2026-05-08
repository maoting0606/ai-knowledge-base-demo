# 项目架构关系图

## 四层结构关系

```mermaid
flowchart TB
    subgraph Convention["📐 项目公约"]
        AGENTS[AGENTS.md<br/>编码规范 / 角色概览 / 红线规则]
    end

    subgraph Roles["📋 角色定义层<br/> .opencode/agents/"]
        COLLECTOR[collector.md<br/>采集 Agent<br/>WebFetch 抓取 → 输出 JSON]
        ANALYZER[analyzer.md<br/>分析 Agent<br/>读取 raw → 评分/标签/摘要]
        ORGANIZER[organizer.md<br/>整理 Agent<br/>去重 → 格式化 → 写入 articles]
    end

    subgraph Skills["🔧 技能方法层<br/> .opencode/skills/"]
        GH[github-trending<br/>7步采集流程<br/>搜索 → 过滤 → 排序 → 输出]
        TS[tech-summary<br/>4步分析流程<br/>读取 → 逐条分析 → 趋势 → 输出]
    end

    subgraph Data["🗄️ 数据存储层<br/> knowledge/"]
        RAW[knowledge/raw/<br/>原始采集数据]
        ANALYZED[knowledge/analyzed/<br/>分析中间结果]
        ARTICLES[knowledge/articles/<br/>最终知识条目]
    end

    AGENTS -->|定义角色框架| COLLECTOR
    AGENTS -->|定义角色框架| ANALYZER
    AGENTS -->|定义角色框架| ORGANIZER
    AGENTS -->|提供编码规范约束| Skills

    COLLECTOR -->|调用| GH
    ANALYZER -->|调用| TS

    GH -->|Step 7: 写入| RAW
    TS -->|Step 4: 写入| ANALYZED

    RAW -->|Step 1: 读取| ANALYZER
    ANALYZED -->|Step 1: 读取| ORGANIZER

    ORGANIZER -->|去重后写入| ARTICLES

    ARTICLES -.->|回溯查重| ORGANIZER
    RAW -.->|历史去重| COLLECTOR
```

## 关系说明

| 层级 | 角色 | 核心职责 |
|------|------|----------|
| **AGENTS.md** | 项目宪法 | 定义编码规范、角色分工、红线规则，是所有 Agent 的行为基准 |
| **agents/** | 组织架构 | 定义三个 Agent 的职责边界、权限声明、工作流程，解决"谁做什么" |
| **skills/** | 操作手册 | 提供可复用的任务级操作流程，解决"具体怎么做" |
| **knowledge/** | 数据仓库 | 按 raw → analyzed → articles 三级流水线存储，实现数据逐层加工 |

## 关键数据流

```
采集:  Collector + github-trending skill  → knowledge/raw/
分析:  Analyzer 读取 raw/ + tech-summary skill → knowledge/analyzed/
整理:  Organizer 读取 analyzed/ → 去重 → knowledge/articles/
```

## 关键控制流

```
AGENTS.md → agents/*.md（角色定义）→ skills/*/SKILL.md（操作方法）→ knowledge/（数据读写）
```
