"""检索：多路召回 + RRF 融合 + 路径/符号加权。"""
import time

from app.core.expander import expand_query
from app.core.tokenize import make_snippet, to_fts_query

INTENTS = [
    ("run", ["跑", "运行", "启动", "安装", "命令", "run", "start", "install", "build", "deploy", "怎么用"]),
    ("config", ["配置", "环境变量", "env", "config", "setting", "参数", "端口"]),
    ("where", ["在哪", "哪里", "哪个文件", "入口", "路由", "handler", "middleware", "哪个"]),
    ("deps", ["依赖", "库", "框架", "dependency", "framework", "package"]),
    ("trap", ["坑", "问题", "报错", "失败", "error", "bug", "冲突"]),
]

FETCH = 24


def classify_intent(q: str) -> str:
    low = q.lower()
    best, hits = "general", 0
    for name, kws in INTENTS:
        n = sum(1 for k in kws if k in low)
        if n > hits:
            best, hits = name, n
    return best


def _fts(con, snapshot_id: str, expr: str, limit: int) -> list[dict]:
    if not expr or expr == '""':
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


def search(con, snapshot_id: str, query: str, k: int = 8, log: bool = True) -> dict:
    t0 = time.perf_counter()
    intent = classify_intent(query)
    expanded = expand_query(query) if any("\u4e00" <= ch <= "\u9fff" for ch in query) else query
    loose = _fts(con, snapshot_id, to_fts_query(expanded, "OR"), FETCH)
    strict = _fts(con, snapshot_id, to_fts_query(expanded, "AND"), FETCH)

    # RRF 融合（两个召回通道）
    merged: dict[int, dict] = {}
    for rank_list in (strict, loose):
        for rank, row in enumerate(rank_list):
            cid = row["id"]
            if cid not in merged:
                merged[cid] = dict(row)
                merged[cid]["rrf"] = 0.0
                merged[cid]["why"] = []
            merged[cid]["rrf"] += 1.0 / (60 + rank + 1)
            merged[cid]["why"].append("strict" if rank_list is strict else "loose")

    # 路径/符号加权（意图命中文件名是最强信号）
    terms = [t for t in to_fts_query(query, "OR").replace('"', "").split(" OR ") if t]
    for row in merged.values():
        boost = 0.0
        low_path = row["path"].lower()
        low_sym = (row["symbols"] or "").lower()
        for t in terms:
            if t in low_path:
                boost += 0.012
            if t in low_sym:
                boost += 0.010
        # 意图感知的路径先验（可单测、可解释：问"配置"就该优先 .env.example）
        if intent == "config" and ".env" in low_path:
            boost += 0.020
        if intent == "run" and any(k in low_path for k in ("readme", "makefile", "docker-compose")):
            boost += 0.010
        if intent == "where" and any(k in low_path for k in ("handler", "route", "controller", "api/")):
            boost += 0.010
        row["boost"] = boost
        row["final"] = row["rrf"] + boost

    ordered = sorted(merged.values(), key=lambda r: -r["final"])[:k]
    results = [{
        "path": r["path"],
        "start_line": r["start_line"],
        "end_line": r["end_line"],
        "lang": r["lang"],
        "snippet": make_snippet(r["text"], query),
        "score": round(r["final"], 4),
        "why": "/".join(sorted(set(r["why"]))) or "path-boost",
        "cited": f'{r["path"]}#L{r["start_line"]}-L{r["end_line"]}',
    } for r in ordered]

    intent = classify_intent(query)
    latency = round((time.perf_counter() - t0) * 1000, 1)
    if log:
        con.execute("INSERT INTO search_log(query,intent,hits,latency_ms) VALUES(?,?,?,?)",
                    (query, intent, len(results), latency))
        con.commit()
    return {"query": query, "intent": intent, "latency_ms": latency,
            "hits": len(results), "results": results}
