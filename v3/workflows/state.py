"""
共享状态 — LangGraph 工作流的节点间通信契约

所有字段遵循"报告式通信"原则：存储的是结构化摘要而不是原始数据，
确保每个节点只需读取上游的产出摘要即可作出决策，无需重新处理全量数据。
"""

from typing import TypedDict


class CostTracker(TypedDict):
    """Token 用量与成本追踪"""
    prompt_tokens: int           # 累计输入 token 数
    completion_tokens: int       # 累计输出 token 数
    total_cost_yuan: float       # 估算总费用（元）


class SourceEntry(TypedDict):
    """单条采集源的摘要信息"""
    title: str                   # 标题
    url: str                     # 原文链接
    source_type: str             # 来源类型：github_trending / hacker_news
    summary: str                 # 自动摘要（采集阶段，50 字以内）
    collected_at: str            # 采集时间（ISO-8601）


class AnalysisResult(TypedDict):
    """LLM 单条分析结果"""
    index: int                   # 对应 sources 中的序号
    summary: str                 # AI 生成的中文摘要（200 字以内）
    tags: list[str]              # 标签列表
    quality_score: float         # 质量评分（0-1）
    analysis_detail: str         # 详细分析说明


class KnowledgeArticle(TypedDict):
    """最终知识条目（去重、格式化后）"""
    id: str                      # UUID v4
    title: str                   # 标题
    source_url: str              # 原文链接
    source_type: str             # 来源类型
    summary: str                 # AI 摘要
    tags: list[str]              # 标签
    status: str                  # pending / published / archived
    collected_at: str            # 采集时间
    published_at: str | None     # 发布时间（可为 null）
    dedup_group: str             # 去重分组标识


class KBState(TypedDict):
    """LangGraph 工作流共享状态

    每个字段都是上游节点处理后输出的结构化摘要，下游节点基于这些摘要
    做路由决策或进一步加工，无需访问原始数据。
    """
    sources: list[SourceEntry]              # 采集阶段：原始信源摘要列表
    analyses: list[AnalysisResult]          # 分析阶段：LLM 结构化分析结果列表
    articles: list[KnowledgeArticle]        # 整理阶段：格式化去重后的知识条目列表
    review_feedback: str                    # 审核阶段：Supervisor 审核反馈意见
    review_passed: bool                     # 审核阶段：审核是否通过
    iteration: int                          # 审核阶段：当前审核循环次数（最大 3）
    cost_tracker: CostTracker               # 全流程：累计 Token 用量与成本追踪
