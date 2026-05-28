"""工作流节点 — 统一导出入口

每个节点是纯函数：接收 KBState，返回部分状态更新的 dict。
"""

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
