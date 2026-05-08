"""Four-step knowledge base automation pipeline.

Usage:
    python pipeline/pipeline.py --sources github,rss --limit 20
    python pipeline/pipeline.py --sources github --limit 5 --dry-run
    python pipeline/pipeline.py --sources rss --limit 10 --verbose
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from model_client import LLMResponse, chat_with_retry, create_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "knowledge" / "raw"
ARTICLES_DIR = BASE_DIR / "knowledge" / "articles"

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
RSS_URL = os.environ.get("RSS_FEED_URL", "https://hnrss.org/frontpage")

ANALYSIS_PROMPT = """Analyze the following tech article and return a JSON object with:
- "summary": Chinese summary (within 200 characters)
- "tags": array of 2-4 English keyword tags
- "score": integer 1-10 (technical relevance and quality)

Article title: {title}
Description: {desc}
Source: {source_url}

Return ONLY the JSON object, no markdown, no explanation."""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Knowledge Base Automation Pipeline",
    )
    parser.add_argument(
        "--sources",
        default="github,rss",
        help="Comma-separated source list (github, rss). Default: github,rss",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max items per source. Default: 20",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM analysis and file saving (print only)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    """Adjust root logger level based on verbosity."""
    if verbose:
        logging.getLogger("pipeline").setLevel(logging.DEBUG)
        logging.getLogger("model_client").setLevel(logging.DEBUG)


def collect_github(limit: int, client: httpx.Client) -> list[dict[str, Any]]:
    """Collect AI/LLM/Agent related repositories from GitHub Search API.

    Args:
        limit: Maximum number of results to return.
        client: Shared httpx client.

    Returns:
        List of raw item dicts with source_type='github_trending'.
    """
    query = "AI+OR+LLM+OR+Agent"
    per_page = min(limit, 100)
    params: dict[str, str | int] = {
        "q": query,
        "sort": "updated",
        "per_page": per_page,
        "page": 1,
    }
    logger.info("Fetching GitHub repos: q=%s limit=%d", query, limit)

    try:
        resp = client.get(GITHUB_SEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("GitHub API error (status %d): %s", exc.response.status_code, exc)
        return []

    data = resp.json()
    items = data.get("items", [])[:limit]
    now = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []

    for repo in items:
        results.append({
            "source_type": "github_trending",
            "source_url": repo.get("html_url", ""),
            "title": repo.get("full_name", ""),
            "description": repo.get("description") or "",
            "extra": {
                "stars": repo.get("stargazers_count", 0),
                "language": repo.get("language") or "",
                "topics": repo.get("topics", []),
            },
            "collected_at": now,
        })

    logger.info("Collected %d items from GitHub", len(results))
    return results


def collect_rss(limit: int, client: httpx.Client) -> list[dict[str, Any]]:
    """Collect articles from an RSS feed using regex parsing.

    Args:
        limit: Maximum number of entries to return.
        client: Shared httpx client.

    Returns:
        List of raw item dicts with source_type='hacker_news'.
    """
    logger.info("Fetching RSS feed: %s limit=%d", RSS_URL, limit)

    try:
        resp = client.get(RSS_URL, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("RSS fetch error: %s", exc)
        return []

    text = resp.text
    items: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    pattern = re.compile(
        r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<description>(.*?)</description>.*?<pubDate>(.*?)</pubDate>.*?</item>",
        re.DOTALL | re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        if len(items) >= limit:
            break
        title = _strip_html(match.group(1).strip())
        link = match.group(2).strip()
        desc = _strip_html(match.group(3).strip())
        pub_date = match.group(4).strip()
        items.append({
            "source_type": "hacker_news",
            "source_url": link,
            "title": title,
            "description": desc[:500],
            "extra": {"pub_date": pub_date},
            "collected_at": now,
        })

    if not items:
        logger.warning("No items parsed from RSS feed (regex may need tuning)")
    else:
        logger.info("Collected %d items from RSS", len(items))
    return items


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape common entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    return text


def save_raw(items: list[dict[str, Any]]) -> Path | None:
    """Persist collected raw items to knowledge/raw/ as a timestamped JSON file.

    Args:
        items: List of raw item dicts.

    Returns:
        Path to the saved file, or None if items is empty.
    """
    if not items:
        return None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = RAW_DIR / f"raw_{timestamp}.json"
    filepath.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %d raw items to %s", len(items), filepath)
    return filepath


def analyze_item(item: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """Analyze a single raw item via LLM: summary, tags, score.

    Args:
        item: Raw item dict with title / description / source_url.
        dry_run: If True, skip LLM call and use placeholder values.

    Returns:
        Item dict enriched with summary, tags, score, and status fields.
    """
    if dry_run:
        return {
            **item,
            "summary": "[DRY-RUN] 未执行 LLM 分析",
            "tags": ["dry-run"],
            "score": 0,
            "status": "draft",
        }

    prompt = ANALYSIS_PROMPT.format(
        title=item.get("title", ""),
        desc=item.get("description", "")[:1000],
        source_url=item.get("source_url", ""),
    )

    try:
        resp: LLMResponse = chat_with_retry(
            messages=[{"role": "user", "content": prompt}],
            provider=create_provider(),
            temperature=0.3,
            max_tokens=512,
        )
        parsed = _parse_llm_json(resp.content)
        return {
            **item,
            "summary": parsed.get("summary", ""),
            "tags": parsed.get("tags", []),
            "score": parsed.get("score", 5),
            "status": "pending",
        }
    except Exception as exc:
        logger.warning("LLM analysis failed for '%s': %s", item.get("title", ""), exc)
        return {
            **item,
            "summary": "[分析失败] " + str(exc),
            "tags": ["error"],
            "score": 0,
            "status": "draft",
        }


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from LLM response text (handles markdown fences)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM output as JSON: %.100s", text)
        return {}


def organize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by title, validate required fields, standardize format.

    Args:
        items: List of analyzed item dicts.

    Returns:
        Deduplicated and validated item list.
    """
    seen_titles: set[str] = set()
    validated: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for item in items:
        title = (item.get("title") or "").strip().lower()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        entry = _standardize_entry(item, now)
        if entry:
            validated.append(entry)

    logger.info(
        "Organize: %d unique / %d total items passed validation",
        len(validated),
        len(items),
    )
    return validated


def _standardize_entry(item: dict[str, Any], collected_at: str) -> dict[str, Any] | None:
    """Convert a raw/analyzed item into the standard knowledge entry format.

    Args:
        item: Raw or analyzed item dict.
        collected_at: ISO-8601 timestamp for the collection time.

    Returns:
        Standardized entry dict, or None if validation fails.
    """
    source_url = (item.get("source_url") or "").strip()
    title = (item.get("title") or "").strip()
    summary = (item.get("summary") or "").strip()

    if not source_url or not title:
        return None

    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:60]
    entry_id = f"{slug}-{datetime.now().strftime('%Y%m%d')}-001"

    return {
        "id": entry_id,
        "title": title,
        "source_url": source_url,
        "source_type": item.get("source_type", "unknown"),
        "summary": summary,
        "tags": item.get("tags", []),
        "score": item.get("score", 5),
        "status": item.get("status", "draft"),
        "collected_at": collected_at,
        "published_at": None,
    }


def save_articles(entries: list[dict[str, Any]], dry_run: bool) -> int:
    """Save each entry as an individual JSON file to knowledge/articles/.

    Args:
        entries: List of standardized entry dicts.
        dry_run: If True, log intent without writing.

    Returns:
        Number of files saved.
    """
    if dry_run:
        logger.info("DRY-RUN: would save %d articles to %s", len(entries), ARTICLES_DIR)
        return 0

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0

    for entry in entries:
        entry_id = entry.get("id", str(uuid.uuid4()))
        filepath = ARTICLES_DIR / f"{entry_id}.json"
        filepath.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        saved += 1
        logger.debug("Saved article %s", filepath)

    logger.info("Saved %d articles to %s", saved, ARTICLES_DIR)
    return saved


def run_pipeline(args: argparse.Namespace) -> int:
    """Execute the full four-step pipeline.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success).
    """
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    logger.info(
        "Pipeline start sources=%s limit=%d dry_run=%s",
        sources,
        args.limit,
        args.dry_run,
    )

    all_items: list[dict[str, Any]] = []

    with httpx.Client() as client:
        if "github" in sources:
            all_items.extend(collect_github(args.limit, client))
        if "rss" in sources:
            all_items.extend(collect_rss(args.limit, client))

    if not all_items:
        logger.warning("No items collected from any source")
        return 1

    raw_path = save_raw(all_items)
    if raw_path and not args.dry_run:
        logger.info("Raw data persisted at %s", raw_path)

    logger.info("Step 2: Analyzing %d items via LLM...", len(all_items))
    analyzed: list[dict[str, Any]] = []
    for i, item in enumerate(all_items):
        title_preview = item.get("title", "")[:40]
        logger.info("  Analyzing [%d/%d] %s", i + 1, len(all_items), title_preview)
        analyzed.append(analyze_item(item, args.dry_run))
        time.sleep(0.5)

    logger.info("Step 3: Organizing (dedup + validate)...")
    organized = organize(analyzed)

    logger.info("Step 4: Saving %d articles...", len(organized))
    saved = save_articles(organized, args.dry_run)

    logger.info(
        "Pipeline complete collected=%d analyzed=%d organized=%d saved=%d",
        len(all_items),
        len(analyzed),
        len(organized),
        saved,
    )
    return 0


def main() -> None:
    """Entry point: parse args and run pipeline."""
    args = parse_args()
    setup_logging(args.verbose)
    try:
        sys.exit(run_pipeline(args))
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(130)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
