"""评测：Recall@5 / 引用回查 / 槽位命中 / 灰区率。

跑法：python scripts/eval.py
输出：markdown 表格（直接可贴技术文档）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ROOT  # noqa: E402
from app.core.indexer import build_snapshot  # noqa: E402
from app.core.retriever import search  # noqa: E402
from app.infra.db import connect  # noqa: E402
from app.pipeline.report import generate  # noqa: E402

# 标注：fixture 仓库 × 查询 -> 期望命中的路径片段（人工标注，≤60 条）
GOLDEN = [
    ("demo-go-service", "路由在哪", "route.go"),
    ("demo-go-service", "中间件怎么挂载", "route.go"),
    ("demo-go-service", "配置项有哪些", ".env.example"),
    ("demo-go-service", "怎么启动", "README.md"),
    ("demo-go-service", "许可", "LICENSE"),
    ("demo-go-service", "用户接口", "handler"),
    ("demo-vue-app", "接口地址在哪", "api.js"),
    ("demo-vue-app", "怎么启动", "README.md"),
    ("demo-vue-app", "依赖", "package.json"),
    ("demo-vue-app", "分页", "App.vue"),
]


def main() -> int:
    db = ROOT / "data" / "eval.sqlite"
    if db.exists():
        db.unlink()
    con = connect(db)

    snaps, reports, recall_hits = {}, {}, 0
    for name in {g[0] for g in GOLDEN}:
        root = ROOT / "fixtures" / "repos" / name
        info = build_snapshot(con, name, root, "eval")
        snaps[name] = info["snapshot_id"]
        reports[name] = generate(con, name, info["snapshot_id"], name)

    rows = []
    for name, q, expect in GOLDEN:
        res = search(con, snaps[name], q, k=5, log=False)
        hit = any(expect.lower() in r["path"].lower() for r in res["results"])
        recall_hits += int(hit)
        top = res["results"][0]["path"] if res["results"] else "-"
        rows.append((name, q, expect, hit, top, res["latency_ms"]))

    print("\n## 检索评测（Recall@5）\n")
    print("| 仓库 | 查询 | 期望命中 | 结果 | Top1 | 耗时 |")
    print("|---|---|---|---|---|---|")
    for name, q, expect, hit, top, ms in rows:
        print(f"| {name} | {q} | `{expect}` | {'✅' if hit else '❌'} | `{top}` | {ms}ms |")
    print(f"\n**Recall@5 = {recall_hits}/{len(GOLDEN)} = {recall_hits / len(GOLDEN):.2f}**\n")

    print("## 报告指标\n")
    print("| 项目 | 槽位命中 | 引用回查 | 有证据 | 灰区 | 障碍点 |")
    print("|---|---|---|---|---|---|")
    for name, rep in reports.items():
        m = rep["metrics"]
        print(f"| {name} | {m['slot_hit']}/{m['slot_total']} | {m['cite_resolve_rate']:.0%} | "
              f"{m['evidence_rate']:.0%} | {m['grey_claims']} | {m['findings']} |")

    ok = recall_hits / len(GOLDEN) >= 0.8 and all(
        r["metrics"]["cite_resolve_rate"] >= 0.99 for r in reports.values())
    print(f"\n结论：{'PASS' if ok else 'FAIL'}（门槛：Recall@5 ≥ 0.80 且引用回查 100%）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
