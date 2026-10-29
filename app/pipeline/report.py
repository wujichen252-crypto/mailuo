"""报告编排：检索取证 -> 填槽 -> 引用校验 -> 缺口 -> 指标。

三条硬约束在这里落地（docs/report-template.md §2）：
  P1 结构：槽位合法、claim 数上限、字数上限
  P2 引用：citations 必须回查成功，失败即降级
  P3 分级：无引用 -> confidence=inferred（前端灰底）
"""
import json
import time
import uuid

from app.config import MOCK_LLM, TEMPLATE_VERSION
from app.core.retriever import search
from app.pipeline import citations
from app.pipeline.filler import LLMFiller, MockFiller
from app.pipeline.template import NON_GAP_SLOTS, queries_for


def build_meta(con, snapshot_id: str) -> dict:
    snap = con.execute("SELECT * FROM snapshot WHERE id=?", (snapshot_id,)).fetchone()
    if not snap:
        raise ValueError(f"snapshot 不存在：{snapshot_id}")
    findings = [dict(r) for r in con.execute(
        "SELECT rule_id,severity,path,line,evidence,suggestion FROM finding WHERE snapshot_id=? "
        "ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, path, line",
        (snapshot_id,)).fetchall()]
    return {
        "languages": json.loads(snap["languages_json"] or "{}"),
        "deps": json.loads(snap["deps_json"] or "[]"),
        "entries": json.loads(snap["entries_json"] or "[]"),
        "config": json.loads(snap["config_json"] or "[]"),
        "findings": findings,
        "files_count": snap["files_count"],
        "loc": snap["loc"],
    }


def gather_evidence(con, snapshot_id: str, project_name: str, per_slot: int = 6) -> dict[str, list[dict]]:
    packs: dict[str, list[dict]] = {}
    for slot in NON_GAP_SLOTS:
        hits: list[dict] = []
        seen: set[str] = set()
        for q in queries_for(slot, project_name):
            res = search(con, snapshot_id, q, k=per_slot, log=False)
            for r in res["results"]:
                if r["cited"] in seen:
                    continue
                seen.add(r["cited"])
                hits.append(r)
        packs[slot["id"]] = hits[:per_slot]
    return packs


def generate(con, project_id: str, snapshot_id: str, project_name: str) -> dict:
    t0 = time.perf_counter()
    meta = build_meta(con, snapshot_id)
    evidence = gather_evidence(con, snapshot_id, project_name)

    filler = MockFiller(con, snapshot_id, meta)
    raw = filler.fill()
    model_used = "mock"

    if not MOCK_LLM:
        llm_raw = LLMFiller(con, snapshot_id, meta, evidence).fill()
        if llm_raw:
            raw = {**raw, **llm_raw}
            model_used = "llm"

    line_counts = citations.file_line_counts(con, snapshot_id)
    sections: list[dict] = []
    gaps: list[dict] = []
    claims_total = claims_cited = cites_ok = cites_total = grey = 0

    for slot in NON_GAP_SLOTS:
        claims_in = (raw.get(slot["id"]) or [])[: slot["max_claims"]]
        claims_out: list[dict] = []
        for c in claims_in:
            text = (c.get("text") or "").strip()
            if not text:
                continue
            resolves = [citations.resolve(con, snapshot_id, cite, line_counts) for cite in (c.get("citations") or [])]
            good = [r for r in resolves if r["ok"]]
            cites_total += len(resolves)
            cites_ok += len(good)
            confidence = "evidence" if good else "inferred"
            if confidence == "inferred":
                grey += 1
            claims_total += 1
            if good:
                claims_cited += 1
            claims_out.append({
                "text": text,
                "citations": [r["cite"] for r in good],
                "confidence": confidence,
                "resolved": [{"path": r["path"], "start": r["start"], "end": r["end"]} for r in good],
            })
        if not claims_out:
            gaps.append({"section": slot["id"], "title": slot["title"], "reason": slot["degrade"]})
        sections.append({"id": slot["id"], "title": slot["title"], "question": slot["question"],
                         "claims": claims_out, "missing": not claims_out})

    metrics = {
        "slot_hit": sum(1 for s in sections if s["claims"]),
        "slot_total": len(sections),
        "slot_hit_rate": round(sum(1 for s in sections if s["claims"]) / max(1, len(sections)), 3),
        "claims_total": claims_total,
        "claims_cited": claims_cited,
        "evidence_rate": round(claims_cited / max(1, claims_total), 3),
        "cite_resolve_rate": round(cites_ok / max(1, cites_total), 3),
        "grey_claims": grey,
        "grey_rate": round(grey / max(1, claims_total), 3),
        "findings": len(meta["findings"]),
        "files": meta["files_count"],
        "loc": meta["loc"],
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }

    report = {
        "report_id": uuid.uuid4().hex[:12],
        "project_id": project_id,
        "project": project_name,
        "snapshot_id": snapshot_id,
        "template_version": TEMPLATE_VERSION,
        "model": model_used,
        "sections": sections,
        "gaps": gaps,
        "metrics": metrics,
    }
    con.execute(
        "INSERT INTO report(id,project_id,snapshot_id,template_version,sections_json,gaps_json,metrics_json,model)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (report["report_id"], project_id, snapshot_id, TEMPLATE_VERSION,
         json.dumps(sections, ensure_ascii=False), json.dumps(gaps, ensure_ascii=False),
         json.dumps(metrics, ensure_ascii=False), model_used))
    con.commit()
    return report


def latest(con, project_id: str) -> dict | None:
    row = con.execute(
        "SELECT * FROM report WHERE project_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (project_id,)).fetchone()
    if not row:
        return None
    return {
        "report_id": row["id"],
        "project_id": row["project_id"],
        "snapshot_id": row["snapshot_id"],
        "template_version": row["template_version"],
        "model": row["model"],
        "sections": json.loads(row["sections_json"]),
        "gaps": json.loads(row["gaps_json"]),
        "metrics": json.loads(row["metrics_json"]),
        "created_at": row["created_at"],
    }
