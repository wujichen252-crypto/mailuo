"""命令行入口：不经 Web 也能跑通全链路（演示与调试都靠它）。

python -m app.cli index  <dir>
python -m app.cli report <dir>
python -m app.cli search <dir> "怎么跑起来"
python -m app.cli serve
"""
import argparse
import json
import sys

from app.infra.db import connect
from app.service import (analyze_project, create_and_analyze, ensure_project,
                         get_project, index_project, list_projects)


def _ensure_local(con, path: str, name: str | None) -> dict:
    for p in list_projects(con):
        if p["source_kind"] == "local" and p["local_path"].endswith(path.rstrip("/").replace("/", "\\").split("\\")[-1]):
            return p
    return ensure_project(con, local_path=path, name=name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="shitu")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="只建索引")
    p_index.add_argument("path")
    p_index.add_argument("--name")

    p_report = sub.add_parser("report", help="建索引并生成报告")
    p_report.add_argument("path")
    p_report.add_argument("--name")
    p_report.add_argument("--out")

    p_search = sub.add_parser("search", help="在已索引项目里检索")
    p_search.add_argument("path")
    p_search.add_argument("query")
    p_search.add_argument("-k", type=int, default=6)

    sub.add_parser("serve", help="启动 Web 服务")
    sub.add_parser("list", help="列出项目")
    sub.add_parser("seed", help="导入种子库（fixtures/repos 下的离线样例）")

    args = ap.parse_args(argv)
    con = connect()

    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
        return 0

    if args.cmd == "list":
        print(json.dumps(list_projects(con), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "seed":
        from app.seed import seed_fixtures
        out = seed_fixtures(con)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    proj = _ensure_local(con, args.path, getattr(args, "name", None))

    if args.cmd == "index":
        print(json.dumps(index_project(con, proj["id"]), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "report":
        report = analyze_project(con, proj["id"])
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"报告已写入 {args.out}")
        else:
            print(text)
        return 0

    if args.cmd == "search":
        from app.core.retriever import search
        snap = con.execute("SELECT id FROM snapshot WHERE project_id=? ORDER BY rowid DESC LIMIT 1",
                           (proj["id"],)).fetchone()
        if not snap:
            print("该项目还没有索引，先跑 index")
            return 1
        res = search(con, snap["id"], args.query, k=args.k)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
