"""种子库：离线导入 fixtures/repos 下的样例仓库。

作用：解决冷启动——评委第一次打开就有项目可看、可搜，
不依赖外网、不依赖 API Key（默认 mock 模式）。
"""
from pathlib import Path

from app.config import ROOT
from app.service import create_and_analyze, list_projects


def seed_fixtures(con, fixtures_dir: str | None = None) -> dict:
    base = Path(fixtures_dir or (ROOT / "fixtures" / "repos"))
    if not base.is_dir():
        return {"error": f"fixture 目录不存在：{base}"}

    existing = {p["name"] for p in list_projects(con)}
    added, skipped, failed = [], [], []

    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        if d.name in existing:
            skipped.append(d.name)
            continue
        try:
            out = create_and_analyze(con, local_path=str(d), name=d.name)
            added.append({"name": d.name, "project_id": out["project"]["id"],
                          "chunks": out["index"]["chunks"], "metrics": out["report"]["metrics"]})
        except Exception as exc:
            failed.append({"name": d.name, "error": str(exc)[:200]})

    return {"added": added, "skipped": skipped, "failed": failed,
            "total_projects": len(list_projects(con))}
