"""从 knowledge/analyzed/ 读取分析结果，去重后写入 knowledge/articles/。"""
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta

ANALYZED_DIR = "knowledge/analyzed"
ARTICLES_DIR = "knowledge/articles"
TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00")
DATE = NOW[:10]
SOURCE_MAP = {"github_trending": "gh", "hacker_news": "hn"}


def load_analyzed():
    files = sorted(os.listdir(ANALYZED_DIR))
    if not files:
        raise SystemExit("No analyzed files found.")
    return json.load(open(os.path.join(ANALYZED_DIR, files[-1]), encoding="utf-8"))


def load_existing():
    titles, urls = set(), set()
    for f in os.listdir(ARTICLES_DIR):
        if not f.endswith(".json"):
            continue
        try:
            e = json.load(open(os.path.join(ARTICLES_DIR, f), encoding="utf-8"))
            if e.get("title"):
                titles.add(e["title"])
            if e.get("source_url"):
                urls.add(e["source_url"])
        except Exception:
            pass
    return titles, urls


def make_slug(title):
    return re.sub(r"[^a-z0-9-]", "", re.sub(r"[/\s]+", "-", title.lower()))


def build_entry(item):
    slug = make_slug(item["title"])
    source_abbr = SOURCE_MAP.get(item["source_type"], "unknown")
    fname = f"{DATE}-{source_abbr}-{slug}.json"

    entry = {
        "id": str(uuid.uuid4()),
        "title": item["title"],
        "source_url": item["source_url"],
        "source_type": item["source_type"],
        "summary": item["summary"],
        "tags": item.get("tags", []),
        "status": "published",
        "collected_at": NOW,
        "published_at": NOW,
    }
    return fname, entry


def main():
    data = load_analyzed()
    existing_titles, existing_urls = load_existing()

    created, skipped = 0, 0
    for item in data:
        if item["title"] in existing_titles or item["source_url"] in existing_urls:
            print(f"Skipped (duplicate): {item['title']}")
            skipped += 1
            continue

        fname, entry = build_entry(item)
        json.dump(
            entry,
            open(os.path.join(ARTICLES_DIR, fname), "w", encoding="utf-8"),
            ensure_ascii=False,
            indent=2,
        )
        print(f"Created: {fname}  tags={entry['tags']}")
        created += 1

    print(f"\nDone. Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
