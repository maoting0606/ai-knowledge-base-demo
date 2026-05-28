"""
LangGraph 工作流编排

流程：collect → analyze → organize → review ─True→ save → END
                                           └False→ organize（修正重试）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.graph import END, StateGraph

from workflows.nodes import (
    analyze_node,
    collect_node,
    organize_node,
    review_node,
    save_node,
)
from workflows.state import KBState


def _review_router(state: KBState) -> str:
    """审核条件路由：通过则存档，否则回退到整理节点修正"""
    return "save" if state.get("review_passed", False) else "organize"


def build_graph() -> StateGraph:
    graph = StateGraph(KBState)

    graph.add_node("collect", collect_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("organize", organize_node)
    graph.add_node("review", review_node)
    graph.add_node("save", save_node)

    graph.set_entry_point("collect")

    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "organize")
    graph.add_edge("organize", "review")

    graph.add_conditional_edges(
        "review",
        _review_router,
        {"save": "save", "organize": "organize"},
    )

    graph.add_edge("save", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# 命令行入口：流式执行并打印各节点关键产出
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    app = build_graph()

    initial: KBState = {
        "sources": [],
        "analyses": [],
        "articles": [],
        "review_feedback": "",
        "review_passed": False,
        "iteration": 0,
        "cost_tracker": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost_yuan": 0.0,
        },
    }

    print("=" * 60)
    print("  AI 知识库采集工作流启动")
    print("=" * 60)

    for event in app.stream(initial):
        for node_name, update in event.items():
            if node_name == "collect":
                count = len(update.get("sources", []))
                print(f"\n  ▶ {node_name}: 采集到 {count} 条原始数据")
            elif node_name == "analyze":
                count = len(update.get("analyses", []))
                print(f"\n  ▶ {node_name}: 分析了 {count} 条数据")
            elif node_name == "organize":
                count = len(update.get("articles", []))
                print(f"\n  ▶ {node_name}: 整理出 {count} 条知识条目")
            elif node_name == "review":
                passed = update.get("review_passed", False)
                iteration = update.get("iteration", 0)
                print(f"\n  ▶ {node_name}: 审核通过={passed}, 轮次={iteration}")
            elif node_name == "save":
                print(f"\n  ▶ {node_name}: 条目已写入 knowledge/articles/")

    print("\n" + "=" * 60)
    print("  工作流执行完毕")
    print("=" * 60)
