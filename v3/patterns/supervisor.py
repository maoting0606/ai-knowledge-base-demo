"""
Supervisor 模式 — Worker 生产 + Supervisor 审核循环

核心思想：
1. Worker Agent 接收任务，输出 JSON 格式的分析报告
2. Supervisor Agent 对报告进行质量审核（准确性/深度/格式）
3. 通过则返回结果，不通过则带反馈重做（最多 N 轮）
4. 超过最大轮数则强制返回并附加警告

适用场景: 需要保证输出质量的场景，如内容审核、报告生成、代码审查等。
"""

import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflows.model_client import chat

logger = logging.getLogger(__name__)

WORKER_SYSTEM_PROMPT = (
    "你是一个专业的 AI 技术分析师。请分析用户给定的任务，"
    "输出 JSON 格式的分析报告，包含以下字段：\n"
    "- summary: 分析摘要（50 字以内）\n"
    "- analysis: 详细分析内容\n"
    "- key_points: 关键要点列表\n"
    "- conclusion: 结论\n\n"
    "请确保输出是有效的、无格式错误的 JSON。"
)

SUPERVISOR_SYSTEM_PROMPT = (
    "你是一个质量审核员。请对 Worker 输出的分析报告进行评分。\n\n"
    "评分维度（各 1-10 分）：\n"
    "- accuracy: 分析是否准确、有依据\n"
    "- depth: 分析是否深入、全面\n"
    "- format: JSON 结构是否完整、规范\n\n"
    "输出 JSON 格式，包含以下字段：\n"
    "{\n"
    '  "accuracy": int,\n'
    '  "depth": int,\n'
    '  "format": int,\n'
    '  "score": int,        // 三维度平均分，四舍五入取整\n'
    '  "passed": bool,      // score >= 7 为通过\n'
    '  "feedback": str      // 未通过时给出具体改进建议\n'
    "}\n\n"
    "请确保输出是有效的、无格式错误的 JSON。"
)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        text = text[brace_start : brace_end + 1]
    return json.loads(text)


def _invoke_worker(task: str, feedback: str | None = None) -> str:
    """调用 Worker Agent 生成分析报告。"""
    prompt = f"任务：{task}\n\n请输出 JSON 格式的分析报告。"
    if feedback:
        prompt += f"\n\n**上一轮审核反馈**（请据此改进）：\n{feedback}"
    text, _ = chat(prompt=prompt, system=WORKER_SYSTEM_PROMPT)
    return text


def _invoke_supervisor(task: str, worker_output: str) -> dict:
    """调用 Supervisor Agent 进行质量审核。"""
    prompt = (
        f"任务：{task}\n\n"
        f"Worker 的分析报告：\n{worker_output}\n\n"
        f"请从准确性、深度、格式三个维度评分，输出 JSON 格式的审核结果。"
    )
    text, _ = chat(prompt=prompt, system=SUPERVISOR_SYSTEM_PROMPT)
    return _extract_json(text)


def supervisor(task: str, max_retries: int = 3) -> dict:
    """执行 Supervisor 监督循环：Worker 生产 → Supervisor 审核 → 迭代改进。

    Args:
        task: 待分析的任务描述。
        max_retries: 最大重试次数（默认 3）。

    Returns:
        包含以下字段的字典：
        - output: 最终 Worker 输出文本
        - attempts: 实际执行轮数
        - final_score: 最终评分
        - warning（可选）: 超过最大重试次数时的警告信息
    """
    feedback: str | None = None
    last_output = ""
    last_score = 0

    for attempt in range(1, max_retries + 1):
        logger.info("第 %d 轮 Worker 执行中...", attempt)
        last_output = _invoke_worker(task, feedback)

        try:
            review = _invoke_supervisor(task, last_output)
        except Exception as e:
            logger.error("Supervisor 审核解析失败 (第%d轮): %s", attempt, e)
            feedback = "请确保分析报告是有效的 JSON 格式，并提高分析质量。"
            continue

        last_score = review.get("score", 0)
        passed = review.get("passed", False)

        if passed:
            logger.info("第 %d 轮审核通过 (score=%d)", attempt, last_score)
            return {
                "output": last_output,
                "attempts": attempt,
                "final_score": last_score,
            }

        feedback = review.get("feedback", "请改进分析质量。")
        logger.info("第 %d 轮未通过 (score=%d), 反馈: %.60s", attempt, last_score, feedback)

    logger.warning("超过最大重试次数 (%d), 强制返回结果", max_retries)
    return {
        "output": last_output,
        "attempts": max_retries,
        "final_score": last_score,
        "warning": f"超过最大重试次数（{max_retries}），结果已强制返回。",
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    test_tasks = [
        "请分析 2024 年 AI Agent 领域的主要技术趋势",
        "比较 Transformer 和 Mamba 架构的异同",
    ]

    for i, task in enumerate(test_tasks, 1):
        print(f"\n{'='*60}")
        print(f"  任务 {i}: {task}")
        print(f"{'='*60}")
        result = supervisor(task, max_retries=3)
        print(f"\n  尝试次数: {result['attempts']}")
        print(f"  最终评分: {result['final_score']}")
        if "warning" in result:
            print(f"  ⚠ {result['warning']}")
        print(f"\n  最终输出:\n{result['output']}")
