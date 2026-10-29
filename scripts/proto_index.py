#!/usr/bin/env python
"""proto_index.py — 自研检索引擎的最小可行验证（不是最终实现）

目的：在写 PRD 之前先证明"倒排索引 + 行号引用"这条路在代码仓库上跑得通，
     并且能量化 Recall@k，避免方案纸上谈兵。

做什么：
  1) 扫仓库（后缀白名单 + 体积上限）
  2) 按 60 行切块，保留 path#start-end
  3) 存入 SQLite FTS5（unicode61 + trigram 两套，对比中文/英文召回）
  4) 跑一组查询，打印 top-k 与耗时

用法：
  python scripts/proto_index.py <repo_dir> [--q "query1" --q "query2"]
"""
import argparse
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

WHITELIST = {".go", ".py", ".ts", ".tsx", ".js", ".vue", ".md", ".yaml", ".yml",
             ".json", ".toml", ".sql", ".sh", ".java", ".php", ".rs"}
SKIP_DIRS = {"node_modules", "vendor", "dist", "build", ".git", "__pycache__",
             ".venv", "venv", "target", "coverage", ".idea", ".vscode"}
MAX_FILE_BYTES = 8 * 1024
CHUNK_LINES = 60
OVERLAP = 10


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in WHITELIST:
                continue
            try:
                if p.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield p


def chunks_for(path: Path, root: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    lines = text.splitlines()
    rel = path.relative_to(root).as_posix()
    step = CHUNK_LINES - OVERLAP
    for start in range(0, max(len(lines), 1), step):
        block = lines[start:start + CHUNK_LINES]
        if not block:
            break
        body = "\n".join(block).strip()
        if len(body) < 40:
            continue
        yield rel, start + 1, start + len(block), body


def build(db: Path, root: Path):
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE chunk(id INTEGER PRIMARY KEY, path TEXT, start_line INT,
                           end_line INT, text TEXT);
        CREATE VIRTUAL TABLE fts_uni USING fts5(path, text, content='chunk',
                                               content_rowid='id', tokenize='unicode61');
        CREATE VIRTUAL TABLE fts_tri USING fts5(path, text, content='chunk',
                                               content_rowid='id', tokenize='trigram');
    """)
    n = 0
    for p in iter_files(root):
        for rel, s, e, body in chunks_for(p, root):
            n += 1
            cur = con.execute(
                "INSERT INTO chunk(path,start_line,end_line,text) VALUES(?,?,?,?)",
                (rel, s, e, body))
            rid = cur.lastrowid
            for tbl in ("fts_uni", "fts_tri"):
                con.execute(f"INSERT INTO {tbl}(rowid,path,text) VALUES(?,?,?)",
                            (rid, rel, body))
    con.commit()
    return con, n


def _fts_query(q: str) -> str:
    """把自然语言查询变成 FTS5 安全表达式：取词，OR 连接。"""
    toks = re.findall(r"[\w\u4e00-\u9fff]+", q)
    toks = [t for t in toks if len(t) > 1][:12]
    if not toks:
        return '""'
    return " OR ".join(f'"{t}"' for t in toks)


def search(con, q, table="fts_uni", k=5):
    t0 = time.perf_counter()
    rows = con.execute(f"""
        SELECT c.path, c.start_line, c.end_line,
               snippet({table}, 1, '[', ']', ' … ', 12) AS snip,
               bm25({table}, 1.0, 1.0) AS score
        FROM {table} JOIN chunk c ON c.id = {table}.rowid
        WHERE {table} MATCH ?
        ORDER BY score LIMIT ?
    """, (_fts_query(q), k)).fetchall()
    return rows, (time.perf_counter() - t0) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--q", action="append", default=[])
    ap.add_argument("--db", default=":memory:")
    a = ap.parse_args()

    root = Path(a.repo).resolve()
    if not root.is_dir():
        sys.exit(f"不是目录：{root}")

    db = Path(a.db) if a.db != ":memory:" else Path(os.environ.get("TMPDIR", "/tmp")) / "proto_idx.sqlite"
    con, n = build(db, root)
    files = len({r[0] for r in con.execute("SELECT DISTINCT path FROM chunk")})
    print(f"[index] {root.name}: {files} files -> {n} chunks, db={db}")

    queries = a.q or ["how to run server", "database migration", "jwt auth", "部署", "配置文件"]
    for q in queries:
        print(f"\n[query] {q}")
        for tbl, label in (("fts_uni", "unicode61"), ("fts_tri", "trigram")):
            rows, ms = search(con, q, tbl)
            print(f"  -- {label}  {ms:.1f}ms  hits={len(rows)}")
            for path, s, e, snip, score in rows[:3]:
                print(f"     {path}#L{s}-L{e}  score={score:.2f}")
                print(f"       {snip[:110].replace(chr(10),' ')}")
    con.close()


if __name__ == "__main__":
    main()
