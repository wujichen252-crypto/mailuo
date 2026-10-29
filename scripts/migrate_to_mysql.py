"""把 SQLite 导出（data/export/*.json）灌进 MySQL 并校验。

用法：
  python scripts/export_data.py                 # 先导出
  python scripts/migrate_to_mysql.py            # 再迁移（读取 .env 的 MAILUO_DB_URL）
  python scripts/migrate_to_mysql.py --dry-run  # 只打印将要插入的行数
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import DB_URL  # noqa: E402
from app.infra.db import MySQLConn  # noqa: E402

TABLES = ["project", "snapshot", "chunk", "finding", "report", "search_log"]

# 每个表的列顺序（与导出 JSON 的键一致；chunk.id 自增，不迁移原 id）
COLS = {
    "project": ["id", "name", "repo_url", "local_path", "source_kind", "visibility",
                "share_token", "head_sha", "created_at", "last_indexed_at",
                "last_analyzed_at", "token_budget"],
    "snapshot": ["id", "project_id", "head_sha", "files_count", "loc", "languages_json",
                 "deps_json", "entries_json", "config_json", "created_at"],
    "chunk": ["snapshot_id", "kind", "path", "start_line", "end_line", "text",
              "tok_text", "symbols", "lang"],
    "finding": ["snapshot_id", "rule_id", "severity", "path", "line", "evidence", "suggestion"],
    "report": ["id", "project_id", "snapshot_id", "template_version", "sections_json",
               "gaps_json", "metrics_json", "model", "created_at"],
    "search_log": ["query", "intent", "hits", "latency_ms", "created_at"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default="data/export")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = Path(a.export)
    if not src.is_dir():
        print(f"[x] 导出目录不存在：{src}（先跑 scripts/export_data.py）")
        return 1
    if not DB_URL.startswith("mysql://"):
        print("[x] .env 里 MAILUO_DB_URL 不是 mysql://")
        return 1

    payload = {}
    for t in TABLES:
        p = src / f"{t}.json"
        payload[t] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        print(f"[读] {t}: {len(payload[t])} 行")

    if a.dry_run:
        print("[dry-run] 不写入数据库")
        return 0

    con = MySQLConn(DB_URL)
    cur = con._con.cursor() if hasattr(con, "_con") else None
    # 清空目标表（保留结构），保证重复迁移幂等
    for t in reversed(TABLES):
        con.execute(f"DELETE FROM {t}")
    con.commit()

    for t in TABLES:
        cols = COLS[t]
        sql = f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join(['?'] * len(cols))})"
        rows = []
        for r in payload[t]:
            rows.append(tuple(r.get(c) for c in cols))
        if not rows:
            print(f"[写] {t}: 0")
            continue
        # pymysql 逐条执行即可（数据量 10^4 级，不必 executemany 优化）
        for row in rows:
            con.execute(sql, row)
        con.commit()
        print(f"[写] {t}: {len(rows)}")

    for t in TABLES:
        n = con.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        print(f"[校验] {t}: {n} 行")

    # 建全文索引自检
    try:
        hit = con.execute(
            "SELECT COUNT(*) AS n FROM chunk WHERE MATCH(tok_text) AGAINST (? IN BOOLEAN MODE)",
            ("启动",)).fetchone()["n"]
        print(f"[校验] FULLTEXT 可用，样例检索命中 {hit} 条")
    except Exception as exc:
        print(f"[!] FULLTEXT 检索失败：{exc}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
