"""文件遍历 + 切块。

优先级：README > 入口/构建文件 > 文档 > 其他；
同优先级按路径深度浅者优先。硬上限 MAX_FILES，保证大仓也不爆。
"""
from pathlib import Path

from app.config import (CHUNK_LINES, CHUNK_OVERLAP, MAX_FILE_BYTES, MAX_FILES,
                        SKIP_DIRS, WHITELIST)

ENTRY_NAMES = {"main.go", "app.py", "main.py", "__main__.py", "index.ts", "index.tsx",
               "server.go", "server.ts", "app.ts", "manage.py", "cmd/app.go"}
BUILD_NAMES = {"package.json", "go.mod", "requirements.txt", "pyproject.toml",
               "docker-compose.yml", "docker-compose.yaml", "makefile", "Makefile"}
# 没有后缀但必须索引的关键文件（go.mod / LICENSE / Dockerfile 等）
SPECIAL_NAMES = {"go.mod", "go.sum", "makefile", "dockerfile", "license", "licence",
                 "copying", "notice", "gemfile", "procfile", "cargo.toml", "pom.xml",
                 ".env.example", ".env.sample", ".env.template", ".env"}
DOC_HINT = ("README", "readme", "docs/", "doc/", "CONTRIBUTING", ".env.example")


def _priority(path: str) -> int:
    low = path.lower()
    name = Path(low).name
    if low.startswith("readme") or "/readme" in low:
        return 0
    if name in {n.lower() for n in ENTRY_NAMES}:
        return 1
    if name in {n.lower() for n in BUILD_NAMES} or name in {n.lower() for n in SPECIAL_NAMES}:
        return 2
    if any(h.lower() in low for h in DOC_HINT):
        return 3
    return 4


def iter_files(root: Path, max_files: int = MAX_FILES) -> list[Path]:
    found: list[tuple[int, int, str, Path]] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = set(part.lower() for part in p.parts)
        if parts & SKIP_DIRS:
            continue
        if p.suffix.lower() not in WHITELIST and p.name.lower() not in SPECIAL_NAMES:
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES or p.stat().st_size == 0:
                continue
        except OSError:
            continue
        rel = p.relative_to(root).as_posix()
        found.append((_priority(rel), rel.count("/"), rel, p))

    found.sort(key=lambda x: (x[0], x[1], x[2]))
    return [p for _, _, _, p in found[:max_files]]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def iter_chunks(path: Path, root: Path):
    """产出 (rel_path, start_line, end_line, text)。行号 1-based，供引用回查。"""
    text = read_text(path)
    if not text.strip():
        return
    rel = path.relative_to(root).as_posix()
    lines = text.splitlines()
    step = max(1, CHUNK_LINES - CHUNK_OVERLAP)
    total = len(lines)
    for start in range(0, total, step):
        block = lines[start:start + CHUNK_LINES]
        if not block:
            break
        body = "\n".join(block).strip()
        if len(body) < 40:
            continue
        yield rel, start + 1, min(start + len(block), total), body


def lang_of(path: Path) -> str:
    return {".go": "Go", ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
            ".js": "JavaScript", ".jsx": "JavaScript", ".vue": "Vue", ".md": "Markdown",
            ".sql": "SQL", ".sh": "Shell", ".java": "Java", ".php": "PHP",
            ".rs": "Rust", ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
            ".toml": "TOML", ".txt": "Text", ".env": "Config"}.get(path.suffix.lower(), "Other")
