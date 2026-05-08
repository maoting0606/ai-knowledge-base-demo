"""5-dimension quality scoring for knowledge entry JSON files.

Usage:
    python hooks/check_quality.py <json_file> [json_file2 ...]

Exits with code 1 if any entry scores grade C (< 60), 0 otherwise.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


TECH_KEYWORDS = {
    "llm", "agent", "ai", "machine learning", "deep learning",
    "nlp", "rag", "mcp", "api", "open source", "cli", "gpu",
    "transformer", "embedding", "fine-tuning", "vector",
    "langchain", "langgraph", "autonomous", "multi-agent",
    "rag", "knowledge graph", "inference", "token",
    "大模型", "智能体", "多模态", "推理", "向量",
    "检索", "生成", "微调", "预训练", "知识图谱",
}

STANDARD_TAGS = {
    "llm", "agent", "ai", "machine-learning", "deep-learning",
    "nlp", "rag", "mcp", "api", "open-source", "cli", "gpu",
    "transformer", "embedding", "fine-tuning", "vector-database",
    "langchain", "langgraph", "multi-agent", "knowledge-graph",
    "inference", "token", "training", "prompt", "tool-use",
    "python", "typescript", "rust", "go", "javascript",
    "docker", "kubernetes", "aws", "azure", "gcp",
    "security", "testing", "devops", "database", "frontend",
    "backend", "fullstack", "react", "vue", "node",
    "tensorflow", "pytorch", "jax", "huggingface",
    "opensource", "saas", "self-hosted", "local-first",
    "automation", "workflow", "pipeline", "orchestration",
    "tutorial", "demo", "example", "template",
    "chatbot", "copilot", "code-generation", "code-review",
    "documentation", "search", "recommendation",
    "大模型", "智能体", "多模态", "推理", "向量",
    "检索", "生成", "微调", "预训练", "知识图谱",
    "金融", "医疗", "法律", "教育", "编程",
    "Anthropic", "OpenAI", "Google", "Meta", "Microsoft",
}

BUZZWORDS_CN = [
    "赋能", "抓手", "闭环", "打通", "全链路",
    "底层逻辑", "颗粒度", "对齐", "拉通", "沉淀",
    "强大的", "革命性的",
]

BUZZWORDS_EN = [
    "groundbreaking", "revolutionary", "game-changing", "cutting-edge",
    "next-generation", "state-of-the-art", "best-in-class",
    "world-class", "industry-leading",
]

BUZZWORD_PATTERNS: list[re.Pattern] = [
    re.compile(re.escape(w), re.IGNORECASE) for w in BUZZWORDS_CN + BUZZWORDS_EN
]

TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
)
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+-\d{8}-\d{3}$")
URL_PATTERN = re.compile(r"^https?://\S+$")
VALID_STATUSES = {"draft", "review", "published", "archived"}


@dataclass
class DimensionScore:
    name: str
    score: float
    max_score: float
    detail: str = ""


@dataclass
class QualityReport:
    record_id: str
    title: str
    dimensions: list[DimensionScore] = field(default_factory=list)
    total_score: float = 0.0
    grade: str = ""

    def __post_init__(self) -> None:
        if not self.total_score:
            self.total_score = sum(d.score for d in self.dimensions)
        if not self.grade:
            if self.total_score >= 80:
                self.grade = "A"
            elif self.total_score >= 60:
                self.grade = "B"
            else:
                self.grade = "C"

    def has_c(self) -> bool:
        return self.grade == "C"


def _progress_bar(current: int, total: int, width: int = 30) -> str:
    fraction = current / total if total else 0
    filled = int(fraction * width)
    bar = "#" * filled + "." * (width - filled)
    pct = int(fraction * 100)
    return f"[{bar}] {pct:3d}%"


def _count_tech_keywords(text: str) -> int:
    lower = text.lower()
    return sum(1 for kw in TECH_KEYWORDS if kw.lower() in lower)


def score_summary(summary: str) -> DimensionScore:
    length = len(summary)
    if length < 20:
        return DimensionScore("摘要质量", 0, 25, f"摘要过短({length}字)")

    base = 10 if length >= 20 else 0
    base = 20 if length >= 50 else base

    bonus = min(_count_tech_keywords(summary), 5)
    total = min(base + bonus, 25)
    detail = f"{length}字, 技术关键词+{bonus}" if bonus else f"{length}字"
    return DimensionScore("摘要质量", total, 25, detail)


def score_depth(record: dict) -> DimensionScore:
    score_val = record.get("score")
    if score_val is None:
        return DimensionScore("技术深度", 0, 25, "无score字段")

    if not isinstance(score_val, (int, float)):
        return DimensionScore("技术深度", 0, 25, f"score类型错误: {type(score_val).__name__}")

    if score_val < 1 or score_val > 10:
        return DimensionScore("技术深度", 0, 25, f"score超出1-10范围: {score_val}")

    mapped = round((score_val - 1) / 9 * 25, 1)
    detail = f"score={score_val} -> {mapped}分"
    return DimensionScore("技术深度", mapped, 25, detail)


def score_format(record: dict) -> DimensionScore:
    score = 0.0
    detail_parts: list[str] = []

    if isinstance(record.get("id"), str) and ID_PATTERN.match(record["id"]):
        score += 4
    else:
        detail_parts.append("id异常")

    if isinstance(record.get("title"), str) and len(record["title"].strip()) > 0:
        score += 4
    else:
        detail_parts.append("title异常")

    if isinstance(record.get("source_url"), str) and URL_PATTERN.match(record["source_url"]):
        score += 4
    else:
        detail_parts.append("source_url异常")

    if isinstance(record.get("status"), str) and record["status"] in VALID_STATUSES:
        score += 4
    else:
        detail_parts.append("status异常")

    ts_ok = 0
    for ts_field in ("collected_at", "published_at"):
        val = record.get(ts_field)
        if isinstance(val, str) and TIMESTAMP_PATTERN.match(val):
            ts_ok += 1
    score += ts_ok * 2
    if ts_ok < 2:
        detail_parts.append(f"时间戳({ts_ok}/2)")

    detail = "; ".join(detail_parts) if detail_parts else "全部合规"
    return DimensionScore("格式规范", score, 20, detail)


def score_tags(tags: list) -> DimensionScore:
    if not isinstance(tags, list):
        return DimensionScore("标签精度", 0, 15, "tags非列表")

    if len(tags) == 0:
        return DimensionScore("标签精度", 0, 15, "无标签")

    valid_count = sum(1 for t in tags if isinstance(t, str) and t in STANDARD_TAGS)
    total_tags = len(tags)
    ratio = valid_count / total_tags if total_tags else 0

    if total_tags == 1 and ratio >= 1:
        score = 15.0
    elif total_tags == 2 and ratio >= 0.5:
        score = 15.0
    elif total_tags == 3 and ratio >= 0.5:
        score = 13.0
    elif total_tags <= 5:
        score = 8.0 + ratio * 5
    else:
        score = max(5.0, ratio * 10)

    score = max(0, min(15, score))
    detail = f"{valid_count}/{total_tags}合规标签"
    return DimensionScore("标签精度", round(score, 1), 15, detail)


def score_buzzwords(text: str) -> DimensionScore:
    if not text:
        return DimensionScore("空洞词检测", 15, 15, "无文本(满分)")

    matches: list[str] = []
    for pattern in BUZZWORD_PATTERNS:
        found = pattern.findall(text)
        matches.extend(found)

    if not matches:
        return DimensionScore("空洞词检测", 15, 15, "未检出空洞词")

    penalty = min(len(matches) * 3, 15)
    score = 15 - penalty
    unique = sorted(set(m.lower() for m in matches))
    detail = f"检出空洞词: {', '.join(unique)}"
    return DimensionScore("空洞词检测", round(score, 1), 15, detail)


def evaluate_record(record: dict) -> QualityReport:
    record_id = record.get("id", "unknown")
    title = record.get("title", "untitled")
    summary = record.get("summary", "")
    tags = record.get("tags", [])

    text_for_buzz = f"{title} {summary}"

    dims = [
        score_summary(summary),
        score_depth(record),
        score_format(record),
        score_tags(tags),
        score_buzzwords(text_for_buzz),
    ]

    return QualityReport(
        record_id=record_id,
        title=title,
        dimensions=dims,
    )


def _print_report(report: QualityReport) -> None:
    print(f"  [{report.grade}] 总分: {report.total_score:.1f}")
    for d in report.dimensions:
        pct = d.score / d.max_score * 100 if d.max_score else 0
        bar = "#" * int(pct // 5) + "." * (20 - int(pct // 5))
        print(f"    {d.name:8s}  {d.score:5.1f}/{d.max_score:<5.1f}  {bar}  {d.detail}")


def process_file(filepath: Path) -> tuple[int, int]:
    try:
        raw = filepath.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"\n{filepath}")
        print(f"  FAILED: {exc}")
        return 0, 1

    try:
        records = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"\n{filepath}")
        print(f"  FAILED: {exc}")
        return 0, 1

    if not isinstance(records, list):
        records = [records]

    passed = 0
    failed = 0

    for idx, record in enumerate(records):
        report = evaluate_record(record)
        rid = record.get("id", f"index={idx}")
        print(f"\n{filepath}  [{rid}]")

        _print_report(report)

        if report.has_c():
            failed += 1
        else:
            passed += 1

    return passed, failed


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <json_file> [json_file2 ...]")
        sys.exit(1)

    files: list[Path] = []
    for pattern in sys.argv[1:]:
        matched = list(Path.cwd().glob(pattern))
        if matched:
            files.extend(matched)
        else:
            files.append(Path(pattern))

    total = len(files)
    total_passed = 0
    total_failed = 0

    processed = 0
    for filepath in files:
        processed += 1
        print(f"\n[{_progress_bar(processed, total)}]  {filepath}")
        if not filepath.is_file():
            print(f"  FAILED: file not found")
            total_failed += 1
            continue
        passed, failed = process_file(filepath)
        total_passed += passed
        total_failed += failed

    print(f"\n{'='*50}")
    print(f"Summary: {total_passed} passed (A/B), {total_failed} failed (C)")
    print(f"Total entries: {total_passed + total_failed}")

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
