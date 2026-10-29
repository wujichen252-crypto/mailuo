"""把当前 SQLite 数据导出为 JSON（迁移到 MySQL/PostgreSQL 前的中间格式）。

用法：
  python scripts/export_data.py                 # 默认导出到 data/export/
  python scripts/export_data.py --db data/mailuo.sqlite --out data/export

设计说明：导出的是"行"，不含 SQLite 特有的 FTS5 索引表；
目标库会用 FULLTEXT / tsvector 重建索引，而不是搬倒排表。
"""
import argparse
import json
import sqlite3
from pathlib import Path

TABLES = ["project", "snapshot", "chunk", "finding", "report", "search_log"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/mailuo.sqlite")
    ap.add_argument("--out", default="data/export")
    a = ap.parse_args()

    db = Path(a.db)
    if not db.exists():
        print(f"[x] 数据库不存在：{db}")
        return 1
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    summary = {}
    for t in TABLES:
        try:
            rows = [dict(r) for r in con.execute(f"SELECT * FROM {t}")]
        except sqlite3.OperationalError as exc:
            print(f"[!] {t}: {exc}")
            continue
        (out / f"{t}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        summary[t] = len(rows)
        print(f"[ok] {t}: {len(rows)} 行")

    (out / "_summary.json").write_text(
        json.dumps({"source_db": str(db), "tables": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    con.close()
    print(f"\n导出完成 -> {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
