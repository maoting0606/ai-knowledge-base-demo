"""采集节点：调用 GitHub Search API 采集 AI 相关仓库"""

import json
import logging
import os
from urllib.parse import quote
from urllib.request import Request, urlopen

from workflows.state import KBState, SourceEntry

from . import DEFAULT_COST, now

logger = logging.getLogger(__name__)


def collect_node(state: KBState) -> dict:
    print("[CollectNode] 开始采集 GitHub Trending AI 项目...")

    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    queries = [
        "topic:ai sort:stars",
        "topic:llm sort:stars",
        "topic:agent sort:stars",
        "topic:machine-learning sort:stars",
    ]

    seen_urls: set[str] = set()
    sources: list[SourceEntry] = []
    timestamp = now()

    for query in queries:
        url = f"https://api.github.com/search/repositories?q={quote(query)}&per_page=5"
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            for repo in data.get("items", []):
                html_url = repo["html_url"]
                if html_url in seen_urls:
                    continue
                seen_urls.add(html_url)
                sources.append({
                    "title": repo.get("full_name", ""),
                    "url": html_url,
                    "source_type": "github_trending",
                    "summary": (repo.get("description") or "")[:200],
                    "collected_at": timestamp,
                })
        except Exception as e:
            logger.warning("GitHub 查询失败 [%s]: %s", query, e)

    tracker = state.get("cost_tracker", DEFAULT_COST)
    print(f"[CollectNode] 采集完毕，共 {len(sources)} 条")
    return {"sources": sources, "cost_tracker": tracker}
