"""审核节点：LLM 四维度评分，超限强制通过"""

import json
import logging

from workflows.model_client import accumulate_usage, chat_json
from workflows.state import KBState

from . import DEFAULT_COST

logger = logging.getLogger(__name__)


def review_node(state: KBState) -> dict:
    print("[ReviewNode] 开始审核知识条目...")

    articles = state.get("articles", [])
    iteration = state.get("iteration", 0) + 1
    tracker = state.get("cost_tracker", DEFAULT_COST)

    # 迭代次数 >= 2 强制通过
    if iteration >= 2:
        print(f"[ReviewNode] 已达最大审核轮次 ({iteration})，强制通过")
        return {
            "review_feedback": "强制通过：已达审核上限。",
            "review_passed": True,
            "iteration": iteration,
            "cost_tracker": tracker,
        }

    if not articles:
        return {
            "review_feedback": "空条目列表，无需审核。",
            "review_passed": True,
            "iteration": iteration,
            "cost_tracker": tracker,
        }

    articles_preview = [
        {
            "title": a["title"],
            "summary": a["summary"],
            "tags": a["tags"],
            "source_type": a["source_type"],
        }
        for a in articles
    ]

    prompt = (
        f"请从以下四个维度对知识条目进行质量评分（1-10 分）：\n\n"
        f"1. summary_quality（摘要质量）：摘要是否准确、清晰、简洁\n"
        f"2. tag_accuracy（标签准确）：标签是否贴切、覆盖关键信息\n"
        f"3. category_reasonableness（分类合理）：来源类型归类是否合理\n"
        f"4. consistency（一致性）：条目内部信息是否一致无矛盾\n\n"
        f"条目列表（共 {len(articles)} 条）：\n"
        f"{json.dumps(articles_preview, ensure_ascii=False, indent=2)}\n\n"
        f"输出 JSON 格式：\n"
        f"{{\n"
        f'  "scores": {{\n'
        f'    "summary_quality": int,\n'
        f'    "tag_accuracy": int,\n'
        f'    "category_reasonableness": int,\n'
        f'    "consistency": int\n'
        f"  }},\n"
        f'  "overall_score": float,\n'
        f'  "passed": bool,\n'
        f'  "feedback": str\n'
        f"}}"
    )
    try:
        result, usage = chat_json(
            prompt,
            system="你是严格的质量审核员，用 JSON 输出评分结果。",
        )
        tracker = accumulate_usage(tracker, usage)
    except Exception as e:
        logger.warning("审核 LLM 调用失败: %s", e)
        result = {"scores": {}, "overall_score": 0, "passed": False, "feedback": "审核模型调用异常，请重试。"}

    scores = result.get("scores", {})
    overall = float(result.get("overall_score", 0))
    passed = bool(result.get("passed", False))
    feedback = str(result.get("feedback", ""))

    print(f"[ReviewNode] 评分={overall:.1f}, 通过={passed}, 轮次={iteration}")
    return {
        "review_feedback": feedback,
        "review_passed": passed,
        "iteration": iteration,
        "cost_tracker": tracker,
    }
