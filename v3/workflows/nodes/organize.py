"""整理节点：过滤低分、按 URL 去重，并根据审核反馈定向修正"""

import json
import logging
import uuid

from workflows.model_client import accumulate_usage, chat_json
from workflows.state import KBState, AnalysisResult, KnowledgeArticle

from . import DEFAULT_COST, now

logger = logging.getLogger(__name__)


def organize_node(state: KBState) -> dict:
    print("[OrganizeNode] 开始整理分析结果...")

    sources = state.get("sources", [])
    analyses = state.get("analyses", [])
    feedback = state.get("review_feedback", "")
    iteration = state.get("iteration", 0)
    tracker = state.get("cost_tracker", DEFAULT_COST)

    # 1. 过滤 quality_score < 0.6 的低质量条目
    filtered = [a for a in analyses if a["quality_score"] >= 0.6]

    # 2. 按 source_url 去重，保留最高分
    url_best: dict[str, AnalysisResult] = {}
    for a in filtered:
        idx = a["index"]
        if idx >= len(sources):
            continue
        url = sources[idx]["url"]
        if url not in url_best or a["quality_score"] > url_best[url]["quality_score"]:
            url_best[url] = a

    # 3. 构建 KnowledgeArticle 列表
    articles: list[KnowledgeArticle] = []
    timestamp = now()
    for a in url_best.values():
        idx = a["index"]
        src = sources[idx]
        articles.append({
            "id": str(uuid.uuid4()),
            "title": src["title"],
            "source_url": src["url"],
            "source_type": src["source_type"],
            "summary": a["summary"],
            "tags": a["tags"],
            "status": "pending",
            "collected_at": src["collected_at"],
            "published_at": None,
            "dedup_group": src["url"],
        })

    # 4. 审核反馈定向修正（仅在有 feedback 的下游重试轮执行）
    if iteration > 0 and feedback.strip() and articles:
        preview = [
            {"title": a["title"], "summary": a["summary"], "tags": a["tags"]}
            for a in articles
        ]
        prompt = (
            f"以下是审核反馈意见：\n{feedback}\n\n"
            f"请根据反馈修正以下知识条目。只返回 JSON 数组，"
            f"每个元素包含 title / summary / tags 三个字段。\n\n"
            f"条目列表：\n{json.dumps(preview, ensure_ascii=False, indent=2)}"
        )
        try:
            fixed_list, usage = chat_json(
                prompt,
                system="你是内容编辑，根据审核反馈定向修正知识条目。只返回 JSON。",
            )
            tracker = accumulate_usage(tracker, usage)
            if isinstance(fixed_list, list):
                for i, fixed in enumerate(fixed_list):
                    if i < len(articles) and isinstance(fixed, dict):
                        articles[i]["title"] = fixed.get("title", articles[i]["title"])
                        articles[i]["summary"] = fixed.get("summary", articles[i]["summary"])
                        articles[i]["tags"] = fixed.get("tags", articles[i]["tags"])
        except Exception as e:
            logger.warning("审核反馈修正失败: %s", e)

    print(f"[OrganizeNode] 整理完成，共 {len(articles)} 条")
    return {"articles": articles, "cost_tracker": tracker}
