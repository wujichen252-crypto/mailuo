"""自研分词：标识符拆分 + CJK 二元切分。

不依赖 jieba / 任何外部模型 —— 评委机器上零安装即可跑，
且结果确定（同样输入永远同样 token），满足"可复现"要求。

实测依据（docs/search-engine.md §4）：
  - 中文整句（"如何启动项目"）若整串当一个 token → 0 命中
  - 2 字词与 3~4 字词需要不同切分策略 → 二元切分同时覆盖
"""
import re

CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
LATIN_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CAMEL = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")

STOP = {"the", "and", "for", "with", "from", "this", "that", "you", "are", "was",
        "have", "has", "not", "but", "all", "can", "will", "use", "using", "into",
        "the", "a", "an", "of", "to", "in", "on", "is", "it", "as", "or", "be"}


def _split_identifier(word: str) -> list[str]:
    parts = CAMEL.findall(word)
    if len(parts) <= 1:
        parts = [p for p in word.split("_") if p]
    return [p.lower() for p in parts if len(p) > 1]


def tokens(text: str, limit: int = 400) -> list[str]:
    """文本 -> 检索 token 序列（去重、保序、截断）。"""
    out: list[str] = []
    seen: set[str] = set()

    def push(tok: str) -> None:
        if len(tok) < 2 or tok in seen or tok in STOP:
            return
        seen.add(tok)
        out.append(tok)

    for m in LATIN_WORD.finditer(text):
        raw = m.group(0)
        push(raw.lower())
        for p in _split_identifier(raw):
            push(p)

    for m in CJK_RUN.finditer(text):
        run = m.group(0)
        if len(run) == 1:
            push(run)
        else:
            for i in range(len(run) - 1):
                push(run[i:i + 2])
            if len(run) <= 4:
                push(run)

    return out[:limit]


def to_index_text(text: str) -> str:
    """写进 FTS 的 token 串（用空格连接，unicode61 直接切）。"""
    return " ".join(tokens(text))


def to_fts_query(text: str, op: str = "OR", limit: int = 12) -> str:
    """查询串 -> FTS5 表达式，已转义引号，避免语法错误。"""
    toks = tokens(text, limit=limit)
    if not toks:
        return '""'
    safe = [t.replace('"', "") for t in toks]
    return f" {op} ".join(f'"{t}"' for t in safe)


def make_snippet(text: str, query: str, width: int = 170) -> str:
    """在原文里围绕首个命中 token 取窗口；找不到就从头部取。"""
    flat = " ".join(text.split())
    if not flat:
        return ""
    toks = [t for t in tokens(query) if len(t) >= 2]
    pos = -1
    for t in toks:
        pos = flat.lower().find(t.lower())
        if pos >= 0:
            break
    if pos < 0:
        return flat[:width] + ("…" if len(flat) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(flat), start + width)
    return ("…" if start > 0 else "") + flat[start:end] + ("…" if end < len(flat) else "")
