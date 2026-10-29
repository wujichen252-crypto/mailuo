"""FastAPI 入口：REST + 静态前端。"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import service
from app.config import MOCK_LLM, ROOT
from app.core.retriever import search as do_search
from app.infra.db import connect
from app.pipeline import citations
from app.pipeline.report import latest
from app.scheduler.jobs import run_due, start_scheduler

app = FastAPI(title="脉络 mailuo", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

con = connect()
start_scheduler(con)


class RepoIn(BaseModel):
    repo_url: str
    name: str | None = None


class LocalIn(BaseModel):
    path: str
    name: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "mock_llm": MOCK_LLM, "projects": len(service.list_projects(con))}


@app.post("/api/projects")
def add_project(body: RepoIn):
    try:
        out = service.create_and_analyze(con, repo_url=body.repo_url, name=body.name)
        return {"ok": True, "project": out["project"], "index": out["index"],
                "report_id": out["report"]["report_id"], "metrics": out["report"]["metrics"]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/local")
def add_local(body: LocalIn):
    try:
        out = service.create_and_analyze(con, local_path=body.path, name=body.name)
        return {"ok": True, "project": out["project"], "index": out["index"],
                "report_id": out["report"]["report_id"], "metrics": out["report"]["metrics"]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects")
def projects():
    return {"ok": True, "items": service.list_projects(con)}


@app.get("/api/projects/{project_id}")
def project(project_id: str):
    proj = service.get_project(con, project_id)
    if not proj:
        raise HTTPException(404, "项目不存在")
    return {"ok": True, "project": proj, "report": latest(con, project_id)}


@app.get("/api/projects/{project_id}/report")
def report(project_id: str):
    rep = latest(con, project_id)
    if not rep:
        raise HTTPException(404, "还没有报告，先调用 analyze")
    return {"ok": True, "report": rep}


@app.post("/api/projects/{project_id}/analyze")
def analyze(project_id: str):
    try:
        return {"ok": True, "report": service.analyze_project(con, project_id)}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/projects/{project_id}/refresh")
def refresh(project_id: str, force: bool = False):
    try:
        return {"ok": True, "result": service.refresh_project(con, project_id, force=force)}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=1), project_id: str | None = None, k: int = 8):
    if project_id:
        snap = con.execute(
            "SELECT id FROM snapshot WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
            (project_id,)).fetchone()
        if not snap:
            raise HTTPException(404, "该项目还没有索引")
        return {"ok": True, "project_id": project_id, **do_search(con, snap["id"], q, k=k)}
    # 跨项目：对每个项目最新快照各查一次，合并
    merged: list[dict] = []
    for p in service.list_projects(con):
        snap = con.execute("SELECT id FROM snapshot WHERE project_id=? ORDER BY rowid DESC LIMIT 1",
                           (p["id"],)).fetchone()
        if not snap:
            continue
        res = do_search(con, snap["id"], q, k=3, log=False)
        for r in res["results"]:
            r["project_id"] = p["id"]
            r["project"] = p["name"]
            merged.append(r)
    return {"ok": True, "cross": True, "query": q, "hits": len(merged), "results": merged[:k]}


@app.get("/api/cite")
def api_cite(snapshot_id: str, cite: str):
    ok = citations.resolve(con, snapshot_id, cite)
    if not ok["ok"]:
        return {"ok": False, "reason": ok.get("reason")}
    return {"ok": True, "cite": cite, "snippet": citations.snippet_of(con, snapshot_id, ok["path"], ok["start"], ok["end"])}


@app.get("/api/share/{token}")
def share(token: str):
    proj = service.get_by_token(con, token)
    if not proj:
        raise HTTPException(404, "分享链接无效")
    return {"ok": True, "project": proj, "report": latest(con, proj["id"])}


@app.post("/api/admin/run-schedule")
def run_schedule():
    return {"ok": True, "result": run_due(con)}


WEB_DIST = ROOT / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(WEB_DIST / "index.html")

    @app.get("/{path:path}")
    def spa(path: str):
        target = WEB_DIST / path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(WEB_DIST / "index.html")
else:
    @app.get("/")
    def index_placeholder():
        return JSONResponse({"ok": True, "msg": "前端未构建（web/dist 不存在）。API 见 /docs"})
