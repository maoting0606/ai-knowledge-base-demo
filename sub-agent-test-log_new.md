# 三个 Agent 联调测试记录（第二版）

测试日期：2026-05-07
测试场景：采集 → 分析 → 整理 全流程

---

## 一、Collector（采集 Agent）

### 角色执行情况

| 职责 | 执行结果 | 说明 |
|------|----------|------|
| WebFetch 抓取 GitHub Trending | ✅ 通过 | 成功抓取 weekly 排行页，获取 15 条原始仓库信息 |
| 信息提取 | ✅ 通过 | 提取 title / url / source / popularity / summary |
| 初步筛选 | ✅ 通过 | 剔除 maigret（OSINT）、Scrapling（爬虫）、docuseal（文档签名）等非 AI 条目 |
| 按热度排序 | ✅ 通过 | 按 weekly stars 降序排列 |

### 越权检查

| 行为 | 判定 | 说明 |
|------|------|------|
| 返回 JSON 给主流程 | ✅ 合规 | 职责是搜集与输出结构化数据 |
| 直接写文件到 `knowledge/raw/` | ⚠️ 注意 | 第一次采集时用户明确要求"保存到文件"，属用户指令覆盖，非自主越权 |

### 产出质量

- 输出 10 条，字段完整，URL 真实，summary 为中文且 <= 50 字
- 无重复条目，已正确过滤非 AI 项目

### 需要调整

- [ ] 质量清单 ">= 15 条" 过于刚性，建议改为软性建议，避免与用户指定数量冲突

---

## 二、Analyzer（分析 Agent）

### 角色执行情况

| 职责 | 执行结果 | 说明 |
|------|----------|------|
| 读取 raw 数据 | ✅ 通过 | 读取最新采集文件 |
| 摘要生成（200 字内） | ✅ 通过 | 全中文，均在 200 字以内 |
| 亮点提炼（50 字内） | ✅ 通过 | 全中文，均在 50 字以内 |
| 质量评分（1-10） | ✅ 通过 | 按 4 档标准打分，附评分理由 |
| 标签推荐（2-5 个） | ✅ 通过 | 每条推荐 4 个标签，与内容高度相关 |

### 越权检查

| 行为 | 判定 | 说明 |
|------|------|------|
| 仅返回 JSON，未写文件 | ✅ 合规 | 严格遵循"分析结果由 Organizer 统一写入"的约束 |

### 产出质量

- 条目数量与输入一致（10 条），无遗漏
- 评分合理：8 分（3 条）/ 7 分（4 条）/ 6 分（3 条），均为直接有帮助或值得了解级别
- 未编造原文不存在的信息

### 需要调整

- 无重大调整项

---

## 三、Organizer（整理 Agent）

### 角色执行情况

| 职责 | 执行结果 | 说明 |
|------|----------|------|
| 去重检查 | ✅ 通过 | articles/ 为空，无重复 |
| 格式校验 | ✅ 通过 | 生成标准知识条目 JSON，9 个字段完整 |
| 命名规范 | ✅ 通过 | `{date}-{source}-{slug}.json` 格式 |
| 写入文件 | ✅ 通过 | 10 个文件成功写入 |

### 越权检查

| 行为 | 判定 | 说明 |
|------|------|------|
| 写文件到 `knowledge/articles/` | ✅ 合规 | 这是 Organizer 的核心职责 |
| 用 Bash 批量生成文件 | ⚠️ 工具选择争议 | 写文件是本职，Bash 只是手段。但没有现成脚本的情况下，不用 Bash 就只能逐文件调用 Write 工具 10 次 |

### 产出质量

- 命名合规、UUID 真实、status 统一为 `published`
- **首次产出问题**：tags 字段为空，因为 Organizer 直接从 `knowledge/raw/` 读数据，跳过了 Analyzer
- **已修复**：引入 `knowledge/analyzed/` 中间层 + 项目脚本 `publish_articles.py`，第二次生成 tags 已正确填充

### 需要调整

- [ ] 数据流：应当 `Collector → knowledge/raw/ → Analyzer → knowledge/analyzed/ → Organizer → articles/`
- [ ] `publish_articles.py` 应纳入版本管理，作为 Organizer 的标准工具

---

## 四、改进后的数据流

```
Collector → knowledge/raw/{date}-{source}.json
    → Analyzer → knowledge/analyzed/{date}-analyzed.json（含 tags/highlight/score）
    → Organizer → knowledge/articles/{date}-{source}-{slug}.json（最终条目）
```

第一个版本的 Organizer 直接从 `knowledge/raw/` 读数据，导致 Analyzer 产出的 tags / highlight / score 全部丢失。加入中间层后，Organizer 消费的是 Analyzer 处理过的富化数据。

---

## 五、总结

| Agent | 角色合规 | 越权 | 产出质量 | 优先级 |
|-------|----------|------|----------|--------|
| Collector | ✅ | 无自主越权 | 良好 | 低（微调条目数要求）|
| Analyzer | ✅ | 无 | 优秀 | 无 |
| Organizer | ✅（首次缺 tags） | 无功能越权，仅手段争议 | 良好（已修复） | **中（固化脚本）** |

**核心经验**：三个 Agent 的职责分工是合理的——真正的断裂点不在权限，而在**数据流的衔接**。Analyzer 的产出没有落地为中间文件，导致 Organizer 无法消费。引入 `knowledge/analyzed/` 中间目录后，流水线才算真正打通。
