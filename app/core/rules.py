"""障碍规则引擎（纯规则，无 LLM —— 每条命中必须带 path:line）。

设计理由（写进技术文档）：坑必须可判、可复现、可单测；
让 AI 猜坑，每次结果不同，评委也无法复现。
"""
import json
import re
from pathlib import Path

ABS_PATH = re.compile(r"(/home/[A-Za-z0-9._-]+|/opt/[A-Za-z0-9._-]+|/usr/local/[A-Za-z0-9._-]+|[A-Za-z]:\\\\[A-Za-z0-9._\\-]+)")
PORT = re.compile(r"[:=]\s*(3000|5000|8000|8080|9000|3306|6379)\b")
ENV_USE = re.compile(r"(os\.getenv|process\.env|os\.environ|getenv\(|\.env\b)")
NPM_RUN = re.compile(r"\b(?:npm|pnpm|yarn)\s+run\s+([A-Za-z0-9:_-]+)")
PY_FRAMEWORK = re.compile(r"^\s*(?:from|import)\s+(fastapi|flask|django|tornado|aiohttp)\b", re.M)
TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")


def _finding(rule_id, severity, path, line, evidence, suggestion):
    return {"rule_id": rule_id, "severity": severity, "path": path, "line": line,
            "evidence": " ".join(str(evidence).split())[:180], "suggestion": suggestion}


def scan(files: list[str], texts: dict[str, str], has_env_example: bool) -> list[dict]:
    out: list[dict] = []
    code_ext = {".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".vue", ".sh", ".yaml", ".yml", ".toml", ".json", ".php", ".java"}
    pkg_scripts: dict[str, str] = {}

    for p in files:
        if Path(p).name == "package.json":
            try:
                data = json.loads(texts.get(p, "{}"))
                pkg_scripts = {k: str(v) for k, v in (data.get("scripts") or {}).items()}
            except json.JSONDecodeError:
                pkg_scripts = {}

    for p in files:
        text = texts.get(p, "")
        suffix = Path(p).suffix.lower()
        is_doc = suffix == ".md"
        for i, line in enumerate(text.splitlines(), start=1):
            if len(line) > 300:
                continue
            m = ABS_PATH.search(line)
            if m and not is_doc:
                out.append(_finding("R1_hardcoded_path", "high", p, i, line,
                                    "改用相对路径或环境变量，否则换机器/换用户必挂"))
                continue
            m = PORT.search(line)
            if m and not is_doc and len(out) < 60:
                out.append(_finding("R2_hardcoded_port", "medium", p, i, line,
                                    "端口写死会与同机其他服务冲突，改成配置项并读 env"))
                continue
            if is_doc:
                m = NPM_RUN.search(line)
                if m and pkg_scripts and m.group(1) not in pkg_scripts:
                    out.append(_finding("R4_readme_cmd_mismatch", "high", p, i, line,
                                        f"package.json 里没有脚本 {m.group(1)}，照 README 跑会直接报错"))
                    continue
            if suffix == ".py":
                m = PY_FRAMEWORK.match(line)
                if m and not any(Path(f).name in {"requirements.txt", "pyproject.toml"} for f in files):
                    out.append(_finding("R5_missing_dep_file", "high", p, i, line,
                                        "缺 requirements.txt / pyproject.toml，别人无法装依赖"))
                    continue
            m = TODO.search(line)
            if m and not is_doc:
                out.append(_finding("R6_todo", "low", p, i, line,
                                    "代码里留有未完成标记，交接时要问清是否影响主流程"))
                continue

    if not has_env_example:
        for p in files:
            if Path(p).suffix.lower() not in code_ext:
                continue
            for i, line in enumerate(texts.get(p, "").splitlines(), start=1):
                if ENV_USE.search(line):
                    out.append(_finding("R3_missing_env_example", "medium", p, i, line,
                                        "代码读环境变量但没有 .env.example，新人不知道要配哪些"))
                    break
            else:
                continue
            break

    # 去重 + 排序（severity 高在前）
    seen: set[tuple[str, str, int]] = set()
    uniq: list[dict] = []
    for f in out:
        key = (f["rule_id"], f["path"], f["line"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    order = {"high": 0, "medium": 1, "low": 2}
    uniq.sort(key=lambda f: (order.get(f["severity"], 9), f["path"], f["line"]))
    return uniq[:40]
