"""节点函数实现包 — 每个节点独立文件，由 workflows.nodes 统一导出"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from workflows.state import CostTracker

logger = logging.getLogger(__name__)

DEFAULT_COST: CostTracker = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_cost_yuan": 0.0,
}

ARTICLES_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "articles"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


from workflows.nodes.collect import collect_node
from workflows.nodes.analyze import analyze_node
from workflows.nodes.organize import organize_node
from workflows.nodes.review import review_node
from workflows.nodes.save import save_node

__all__ = [
    "collect_node",
    "analyze_node",
    "organize_node",
    "review_node",
    "save_node",
]
