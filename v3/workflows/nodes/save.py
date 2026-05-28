"""保存节点：将 articles 写入 JSON 文件并更新索引"""

import json
import logging

from workflows.state import KBState

from . import ARTICLES_DIR, DEFAULT_COST

logger = logging.getLogger(__name__)


def save_node(state: KBState) -> dict:
    print("[SaveNode] 开始保存知识条目...")

    articles = state.get("articles", [])
    tracker = state.get("cost_tracker", DEFAULT_COST)

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    for article in articles:
        file_path = ARTICLES_DIR / f"{article['id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        index.append({
            "id": article["id"],
            "title": article["title"],
            "source_url": article["source_url"],
            "source_type": article["source_type"],
            "status": article["status"],
            "tags": article["tags"],
            "collected_at": article["collected_at"],
        })

    index_path = ARTICLES_DIR / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"[SaveNode] 保存完成，共 {len(articles)} 个文件 + index.json")
    return {"cost_tracker": tracker}
