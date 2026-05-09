"""MCP Server for local knowledge base search.

Provides AI tools to search, retrieve, and analyze knowledge/articles/ entries.
Communicates via JSON-RPC 2.0 over stdio. Zero third-party dependencies.
"""

import json
import sys
from pathlib import Path
from typing import Any

_script_dir = Path(__file__).resolve().parent
BASE_DIR = _script_dir
for _ in range(3):
    if (BASE_DIR / "knowledge" / "articles").is_dir():
        break
    BASE_DIR = BASE_DIR.parent
ARTICLES_DIR = BASE_DIR / "knowledge" / "articles"
PROTOCOL_VERSION = "2025-03-26"


def _read_message() -> dict[str, Any] | None:
    raw = sys.stdin.readline()
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return json.loads(raw)


def _send_message(msg: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _load_articles() -> list[dict[str, Any]]:
    if not ARTICLES_DIR.is_dir():
        return []
    articles: list[dict[str, Any]] = []
    for fpath in sorted(ARTICLES_DIR.iterdir()):
        if fpath.suffix != ".json":
            continue
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, list):
            articles.extend(data)
        else:
            articles.append(data)
    return articles


def _make_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _make_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_initialize(msg: dict[str, Any]) -> dict[str, Any]:
    return _make_result(msg["id"], {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "mcp-knowledge-server", "version": "0.1.0"},
    })


def _handle_tools_list(msg: dict[str, Any]) -> dict[str, Any]:
    return _make_result(msg["id"], {
        "tools": [
            {
                "name": "search_articles",
                "description": "Search knowledge articles by keyword in title and summary",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Search keyword (case-insensitive)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default 5)",
                            "default": 5,
                        },
                    },
                    "required": ["keyword"],
                },
            },
            {
                "name": "get_article",
                "description": "Get full article content by its ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "article_id": {
                            "type": "string",
                            "description": "Article ID (e.g. JetBrains_junie-20260508-001)",
                        },
                    },
                    "required": ["article_id"],
                },
            },
            {
                "name": "knowledge_stats",
                "description": "Get knowledge base statistics: total articles, source distribution, top tags",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ],
    })


def _handle_tools_call(msg: dict[str, Any]) -> dict[str, Any]:
    params = msg.get("params", {})
    name = params.get("name", "")
    args = params.get("arguments", {})
    articles = _load_articles()
    rid = msg["id"]

    if name == "search_articles":
        keyword = args.get("keyword", "").lower()
        limit = int(args.get("limit", 5))
        if not keyword:
            return _make_error(rid, -32602, "Missing required argument: keyword")
        matched = [
            a for a in articles
            if keyword in a.get("title", "").lower()
            or keyword in a.get("summary", "").lower()
        ][:limit]
        return _make_result(rid, {
            "content": [{"type": "text", "text": json.dumps(matched, ensure_ascii=False, indent=2)}],
        })

    if name == "get_article":
        article_id = args.get("article_id", "")
        if not article_id:
            return _make_error(rid, -32602, "Missing required argument: article_id")
        for a in articles:
            if a.get("id") == article_id:
                return _make_result(rid, {
                    "content": [{"type": "text", "text": json.dumps(a, ensure_ascii=False, indent=2)}],
                })
        return _make_result(rid, {
            "content": [{"type": "text", "text": json.dumps({"error": f"Article '{article_id}' not found"})}],
        })

    if name == "knowledge_stats":
        total = len(articles)
        source_dist: dict[str, int] = {}
        tag_counter: dict[str, int] = {}
        for a in articles:
            src = a.get("source_type", a.get("source", "unknown"))
            source_dist[src] = source_dist.get(src, 0) + 1
            for tag in a.get("tags", []):
                tag_counter[tag] = tag_counter.get(tag, 0) + 1
        top_tags = sorted(tag_counter.items(), key=lambda x: -x[1])[:10]
        return _make_result(rid, {
            "content": [{"type": "text", "text": json.dumps({
                "total_articles": total,
                "source_distribution": source_dist,
                "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            }, ensure_ascii=False, indent=2)}],
        })

    return _make_error(rid, -32601, f"Unknown tool: {name}")


_HANDLERS: dict[str, Any] = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
}


def main() -> None:
    while True:
        try:
            msg = _read_message()
        except (json.JSONDecodeError, EOFError):
            break
        if msg is None:
            break

        method = msg.get("method", "")
        handler = _HANDLERS.get(method)

        if handler:
            resp = handler(msg)
        else:
            resp = _make_error(msg.get("id"), -32601, f"Method not found: {method}")

        _send_message(resp)

        if method == "initialize":
            _send_message({"jsonrpc": "2.0", "method": "notifications/initialized"})


if __name__ == "__main__":
    main()
