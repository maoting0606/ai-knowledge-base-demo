"""分析节点：调用 LLM 对每条采集数据生成中文摘要、标签与评分"""

import logging

from workflows.model_client import accumulate_usage, chat_json
from workflows.state import KBState, AnalysisResult

from . import DEFAULT_COST

logger = logging.getLogger(__name__)


def analyze_node(state: KBState) -> dict:
    print("[AnalyzeNode] 开始逐条分析采集数据...")

    sources = state.get("sources", [])
    tracker = state.get("cost_tracker", DEFAULT_COST)
    analyses: list[AnalysisResult] = []

    for i, src in enumerate(sources):
        prompt = (
            f"请分析以下 AI 技术动态：\n\n"
            f"标题：{src['title']}\n"
            f"简介：{src['summary']}\n"
            f"来源：{src['source_type']}\n"
            f"链接：{src['url']}\n\n"
            f"输出 JSON，字段：\n"
            f"- summary：中文摘要（200 字以内）\n"
            f"- tags：标签列表（3-5 个）\n"
            f"- quality_score：质量评分 0-1（基于技术深度、时效性、原创性）\n"
            f"- analysis_detail：详细分析"
        )
        try:
            result, usage = chat_json(
                prompt,
                system="你是 AI 技术分析师，用 JSON 格式输出结构化分析结果。",
            )
            tracker = accumulate_usage(tracker, usage)
        except Exception as e:
            logger.warning("第 %d 条分析失败: %s", i, e)
            result = {"summary": "", "tags": [], "quality_score": 0.0, "analysis_detail": ""}

        analyses.append({
            "index": i,
            "summary": (result.get("summary") or "")[:200],
            "tags": result.get("tags", []),
            "quality_score": float(result.get("quality_score", 0.0)),
            "analysis_detail": result.get("analysis_detail", ""),
        })

    print(f"[AnalyzeNode] 分析完成，共 {len(analyses)} 条")
    return {"analyses": analyses, "cost_tracker": tracker}
