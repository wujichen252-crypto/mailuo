"""项目服务层：登记 / 索引 / 生成报告 / 刷新。"""
import secrets
import shutil
import uuid
from pathlib import Path

from app.config import REPOS
from app.core import crawler
from app.core.indexer import build_snapshot
from app.infra.db import connect, now
from app.pipeline.report import generate, latest


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def ensure_project(con, repo_url: str | None = None, local_path: str | None = None,
                   name: str | None = None, visibility: str = "public") -> dict:
    if not repo_url and not local_path:
        raise ValueError("必须提供 repo_url 或 local_path")

    pid = _new_id()
    if repo_url:
        url = crawler.normalize_url(repo_url)
        path, sha = crawler.clone(url, pid)
        proj_name = name or crawler.repo_slug(url)
        kind = "github"
    else:
        src = Path(local_path).resolve()
        if not src.is_dir():
            raise ValueError(f"目录不存在：{src}")
        path = REPOS / pid
        shutil.copytree(src, path, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("node_modules", ".git", "dist", "vendor", "__pycache__"))
        sha = crawler.head_sha(src)
        proj_name = name or src.name
        kind = "local"

    token = secrets.token_urlsafe(8)
    con.execute(
        "INSERT INTO project(id,name,repo_url,local_path,source_kind,visibility,share_token,head_sha)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (pid, proj_name, repo_url or "", str(path), kind, visibility, token, sha))
    con.commit()
    return get_project(con, pid)


def get_project(con, project_id: str) -> dict | None:
    row = con.execute("SELECT * FROM project WHERE id=?", (project_id,)).fetchone()
    return dict(row) if row else None


def get_by_token(con, token: str) -> dict | None:
    row = con.execute("SELECT * FROM project WHERE share_token=?", (token,)).fetchone()
    return dict(row) if row else None


def list_projects(con) -> list[dict]:
    rows = con.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM chunk c JOIN snapshot s ON s.id=c.snapshot_id "
        "WHERE s.project_id=p.id) AS chunks FROM project p ORDER BY p.created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        rep = latest(con, d["id"])
        d["has_report"] = bool(rep)
        d["metrics"] = (rep or {}).get("metrics", {})
        snap = con.execute(
            "SELECT languages_json, files_count, loc FROM snapshot WHERE project_id=? "
            "ORDER BY created_at DESC LIMIT 1", (d["id"],)).fetchone()
        if snap:
            import json as _json
            d["languages"] = _json.loads(snap["languages_json"] or "{}")
            d["files_count"] = snap["files_count"]
            d["loc"] = snap["loc"]
        else:
            d["languages"] = {}
        out.append(d)
    return out


def index_project(con, project_id: str) -> dict:
    proj = get_project(con, project_id)
    if not proj:
        raise ValueError("项目不存在")
    root = Path(proj["local_path"])
    sha = proj["head_sha"] or crawler.head_sha(root)
    info = build_snapshot(con, project_id, root, sha)
    con.execute("UPDATE project SET last_indexed_at=?, head_sha=? WHERE id=?", (now(), sha, project_id))
    con.commit()
    return info


def analyze_project(con, project_id: str) -> dict:
    proj = get_project(con, project_id)
    if not proj:
        raise ValueError("项目不存在")
    snap = con.execute(
        "SELECT id FROM snapshot WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
        (project_id,)).fetchone()
    if not snap:
        info = index_project(con, project_id)
        snap_id = info["snapshot_id"]
    else:
        snap_id = snap["id"]
    report = generate(con, project_id, snap_id, proj["name"])
    con.execute("UPDATE project SET last_analyzed_at=? WHERE id=?", (now(), project_id))
    con.commit()
    return report


def refresh_project(con, project_id: str, force: bool = False) -> dict:
    """定时任务的核心：sha 未变直接跳过（成本命门）。"""
    proj = get_project(con, project_id)
    if not proj:
        raise ValueError("项目不存在")
    if proj["source_kind"] == "github" and proj["repo_url"] and not force:
        remote = crawler.remote_sha(proj["repo_url"])
        if remote and remote == proj["head_sha"]:
            return {"skipped": True, "reason": "head_sha 未变", "head_sha": remote}
    if proj["source_kind"] == "github" and proj["repo_url"]:
        path, sha = crawler.clone(proj["repo_url"], project_id)
        con.execute("UPDATE project SET local_path=?, head_sha=? WHERE id=?", (str(path), sha, project_id))
        con.commit()
    info = index_project(con, project_id)
    report = analyze_project(con, project_id)
    return {"skipped": False, "index": info, "report_id": report["report_id"],
            "metrics": report["metrics"]}


def create_and_analyze(con, repo_url: str | None = None, local_path: str | None = None,
                       name: str | None = None) -> dict:
    proj = ensure_project(con, repo_url=repo_url, local_path=local_path, name=name)
    info = index_project(con, proj["id"])
    report = analyze_project(con, proj["id"])
    return {"project": get_project(con, proj["id"]), "index": info, "report": report}
