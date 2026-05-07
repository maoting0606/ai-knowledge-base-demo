# Memory 对 AI 生成代码质量的影响对比

通过 AGENTS.md 给 AI 提供项目上下文（"有 Memory"），与完全无上下文（"无 Memory"）两种场景下，AI 生成代码的差异对比。

## 对比表格

| 维度 | 有 Memory | 无 Memory |
|------|-----------|-----------|
| **命名风格** | 遵循项目约定的 `snake_case` + PEP 8，标识符含义清晰且与项目术语一致，如 `fetch_repo_info`、`repo_full_name` | 命名随意，可能出现 `getData`、`do_it_123`、`temp_func` 等风格不统一的标识符 |
| **docstring** | Google 风格，严格按 `Args` / `Returns` / `Raises` 三段式编写，每行都有类型标注 | 缺失 docstring，或用 `#` 行注释简单代替，无固定格式 |
| **日志方式** | 统一使用 `logging.getLogger(__name__)` 模块，区分 `info` / `warning` / `error` 级别 | 混用 `print()` 或 `print(f"...")`，难以控制日志级别与输出目标 |
| **错误处理** | 细粒度异常捕获：区分 `HTTPError(404/403)`、`URLError`、`JSONDecodeError` 等，有降级策略 | 仅包一层 `try-except Exception`，甚至完全不处理，出错直接崩溃 |
| **文件位置** | 按项目约定放入 `utils/` 工具目录，与项目结构一致 | 任意放置（如 `main.py` 末尾、根目录单文件），缺乏模块化意识 |

## 示例对比（GitHub API 获取仓库信息）

```python
# ========== 无 Memory ==========
def getRepo(name):
    import requests
    r = requests.get(f"https://api.github.com/repos/{name}")
    data = r.json()
    print(f"Stars: {data['stargazers_count']}")
    return data

# ========== 有 Memory ==========
def fetch_repo_info(repo_full_name: str) -> Optional[dict]:
    """获取指定 GitHub 仓库的基本信息。

    Args:
        repo_full_name: 仓库全名，格式为 "owner/repo"。

    Returns:
        {"stars": int, "forks": int, ...}，失败返回 None。
    """
    import urllib.request

    try:
        with urllib.request.urlopen(...) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"stars": data.get("stargazers_count", 0), ...}
    except urllib.error.HTTPError as e:
        logger.error("HTTP %d: %s", e.code, repo_full_name)
        return None
```

## 结论

有 Memory 的代码生成质量显著优于无 Memory 的场景，核心收益有三点：

1. **一致性** — 命名风格、文档格式、日志方式全部与项目现有代码对齐，无需人工 review 调整就能融入项目。
2. **健壮性** — 细粒度的错误处理和日志分级让代码具备生产级别的可观测性与容错能力，而非一次性脚本。
3. **可维护性** — Google docstring 提供清晰的接口契约，类型注解让调用方在 IDE 中即可获得智能提示，后续改动风险大幅降低。

对于持续演进的项目，AGENTS.md 是成本最低但回报最高的"记忆载体"——只需一次编写，各 Agent 多轮对话均可受益。
