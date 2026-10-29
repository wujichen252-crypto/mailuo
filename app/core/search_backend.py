"""检索后端：SQLite FTS5 与 MySQL FULLTEXT(ngram) 两套实现，对外同一个接口。

差异（这是两种数据库的客观差别，不是我们的选择）：
  - SQLite：FTS5 + bm25() 打分，值越小越相关；索引是独立的 chunk_fts 影子表
  - MySQL ：FULLTEXT ... WITH PARSER ngram，MATCH ... AGAINST 打分，值越大越相关
  - 查询语法：SQLite 用 `"a" OR "b"`；MySQL BOOLEAN 模式用 `a b`（隐式 OR）与 `+a +b`（AND）
"""
from app.core.tokenize import tokens

FETCH = 24


def build_expr(query: str, op: str, backend: str) -> str:
    toks = [t.replace('"', "") for t in tokens(query, limit=12)]
    if not toks:
        return ""
    if backend == "mysql":
        if op == "AND":
            return " ".join(f"+{t}" for t in toks)
        return " ".join(toks)
    joiner = " OR " if op == "OR" else " AND "
    expr = joiner.join(f'"{t}"' for t in toks)
    return f'"{toks[0]}"' if len(toks) == 1 else expr


def _sqlite(con, snapshot_id: str, expr: str, limit: int) -> list[dict]:
    if not expr:
        return []
    try:
        rows = con.execute(
            """
            SELECT c.id, c.path, c.start_line, c.end_line, c.text, c.symbols, c.lang,
                   bm25(chunk_fts, 1.5, 1.3, 1.0) AS score
            FROM chunk_fts JOIN chunk c ON c.id = chunk_fts.rowid
            WHERE chunk_fts MATCH ? AND c.snapshot_id = ?
            ORDER BY score LIMIT ?
            """, (expr, snapshot_id, limit)).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def _mysql(con, snapshot_id: str, expr: str, limit: int) -> list[dict]:
    if not expr:
        return []
    try:
        rows = con.execute(
            """
            SELECT c.id, c.path, c.start_line, c.end_line, c.text, c.symbols, c.lang,
                   MATCH(c.tok_text) AGAINST (? IN BOOLEAN MODE) AS score
            FROM chunk c
            WHERE c.snapshot_id = ? AND MATCH(c.tok_text) AGAINST (? IN BOOLEAN MODE)
            ORDER BY score DESC LIMIT ?
            """, (expr, snapshot_id, expr, limit)).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def query(con, snapshot_id: str, text: str, op: str, limit: int = FETCH) -> list[dict]:
    expr = build_expr(text, op, con.backend)
    return _mysql(con, snapshot_id, expr, limit) if con.backend == "mysql" \
        else _sqlite(con, snapshot_id, expr, limit)
