"""符号与入口抽取（启发式，明确标注不是 AST）。"""
import re
from pathlib import Path

from app.core.chunker import ENTRY_NAMES

SYMBOL_PATTERNS = [
    (re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)"), "function"),
    (re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"), "func"),
    (re.compile(r"^\s*def\s+([A-Za-z_]\w*)"), "def"),
    (re.compile(r"^\s*class\s+([A-Za-z_]\w*)"), "class"),
    (re.compile(r"^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\("), "const_fn"),
    (re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:func|void|int|string)\s+([A-Za-z_]\w*)\s*\("), "method"),
]

ROUTE_PATTERNS = [
    re.compile(r"\.(?:GET|POST|PUT|DELETE|PATCH)\(\s*[\"']([^\"']+)"),
    re.compile(r"@(?:app|router|bp)\.(?:get|post|put|delete|patch)\(\s*[\"']([^\"']+)"),
    re.compile(r"(?:HandleFunc|Handle)\(\s*[\"']([^\"']+)"),
]


def extract_symbols(text: str, limit: int = 40) -> list[tuple[str, str, int]]:
    """返回 [(name, kind, line_no)]。"""
    out: list[tuple[str, str, int]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if len(out) >= limit:
            break
        if len(line) > 400:
            continue
        matched = False
        for pat, kind in SYMBOL_PATTERNS:
            m = pat.match(line)
            if m:
                out.append((m.group(1), kind, i))
                matched = True
                break
        if matched:
            continue
        for pat in ROUTE_PATTERNS:
            m = pat.search(line)
            if m:
                out.append((m.group(1), "route", i))
                break
    return out


def find_entries(paths: list[str], texts: dict[str, str]) -> list[dict]:
    """入口候选：文件名命中 ENTRY_NAMES，或文件内有路由注册。"""
    names = {n.lower() for n in ENTRY_NAMES}
    out: list[dict] = []
    for p in paths:
        name = Path(p).name.lower()
        text = texts.get(p, "")
        routes = []
        for i, line in enumerate(text.splitlines(), start=1):
            for pat in ROUTE_PATTERNS:
                m = pat.search(line)
                if m:
                    routes.append({"line": i, "route": m.group(1)})
                    break
            if len(routes) >= 6:
                break
        if name in names or routes:
            out.append({"path": p, "by_name": name in names, "routes": routes[:6]})
    out.sort(key=lambda x: (not x["by_name"], len(x["routes"]) == 0, x["path"]))
    return out[:8]
