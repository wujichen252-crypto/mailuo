"""检索编排：多路召回 + RRF 融合 + 路径/符号/意图加权（与数据库后端无关）。

打分语义由 search_backend 吸收：SQLite 的 bm25 越小越好、MySQL 的 MATCH 越大越好，
这里只使用**排名**做 RRF，所以两套后端行为一致。
"""
import time

from app.core import search_backend as sb
from app.core.expander import expand_query
from app.core.tokenize import make_snippet, tokens

INTENTS = [
    ("run", ["跑", "运行", "启动", "安装", "命令", "run", "start", "install", "build", "deploy", "怎么用"]),
    ("config", ["配置", "环境变量", "env", "config", "setting", "参数", "端口"]),
    ("where", ["在哪", "哪里", "哪个文件", "入口", "路由", "handler", "middleware", "哪个"]),
    ("deps", ["依赖", "库", "框架", "dependency", "framework", "package"]),
    ("trap", ["坑", "问题", "报错", "失败", "error", "bug", "冲突"]),
]


def classify_intent(q: str) -> str:
    low = q.lower()
    best, hits = "general", 0
    for name, kws in INTENTS:
        n = sum(1 for k in kws if k in low)
        if n > hits:
            best, hits = name, n
    return best


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def search(con, snapshot_id: str, query: str, k: int = 8, log: bool = True) -> dict:
    t0 = time.perf_counter()
    intent = classify_intent(query)
    expanded = expand_query(query) if _has_cjk(query) else query

    loose = sb.query(con, snapshot_id, expanded, "OR")
    strict = sb.query(con, snapshot_id, expanded, "AND")

    merged: dict[int, dict] = {}
    for rank_list, tag in ((strict, "strict"), (loose, "loose")):
        for rank, row in enumerate(rank_list):
            cid = row["id"]
            if cid not in merged:
                merged[cid] = dict(row)
                merged[cid]["rrf"] = 0.0
                merged[cid]["why"] = []
            merged[cid]["rrf"] += 1.0 / (60 + rank + 1)
            merged[cid]["why"].append(tag)

    terms = [t for t in tokens(expanded, limit=12)]
    for row in merged.values():
        boost = 0.0
        low_path = row["path"].lower()
        low_sym = (row["symbols"] or "").lower()
        for t in terms:
            if t in low_path:
                boost += 0.012
            if t in low_sym:
                boost += 0.010
        if intent == "config" and ".env" in low_path:
            boost += 0.020
        if intent == "run" and any(x in low_path for x in ("readme", "makefile", "docker-compose")):
            boost += 0.010
        if intent == "where" and any(x in low_path for x in ("handler", "route", "controller", "api/")):
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

    latency = round((time.perf_counter() - t0) * 1000, 1)
    if log:
        from app.infra.db import now
        con.execute("INSERT INTO search_log(query,intent,hits,latency_ms,created_at) VALUES(?,?,?,?,?)",
                    (query, intent, len(results), latency, now()))
        con.commit()
    return {"query": query, "intent": intent, "latency_ms": latency,
            "hits": len(results), "results": results}
