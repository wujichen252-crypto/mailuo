"""索引构建：文件 -> chunk -> FTS + 元数据 + 规则命中。"""
import json
import time
import uuid
from collections import Counter
from pathlib import Path

from app.core import rules, symbols
from app.core.chunker import iter_chunks, iter_files, lang_of, read_text
from app.core.tokenize import to_index_text
from app.infra.db import connect, now


def _parse_deps(root: Path, files: list[Path]) -> list[dict]:
    deps: list[dict] = []
    for p in files:
        name = p.name
        text = read_text(p)
        try:
            if name == "package.json":
                data = json.loads(text)
                for section in ("dependencies", "devDependencies"):
                    for k, v in (data.get(section) or {}).items():
                        deps.append({"name": k, "version": str(v), "source": p.relative_to(root).as_posix()})
            elif name == "go.mod":
                for line in text.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] not in {"module", "go", "require", ")", "("} and "v" in parts[1]:
                        deps.append({"name": parts[0], "version": parts[1], "source": p.relative_to(root).as_posix()})
            elif name == "requirements.txt":
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    deps.append({"name": line.split("==")[0].split(">=")[0], "version": line,
                                 "source": p.relative_to(root).as_posix()})
        except (json.JSONDecodeError, OSError):
            continue
    # 去重
    seen, out = set(), []
    for d in deps:
        if d["name"] in seen:
            continue
        seen.add(d["name"])
        out.append(d)
    return out[:40]


def _parse_config_keys(root: Path, files: list[Path]) -> list[dict]:
    keys: list[dict] = []
    for p in files:
        if p.name not in {".env.example", ".env.sample", ".env.template"}:
            continue
        rel = p.relative_to(root).as_posix()
        for i, line in enumerate(read_text(p).splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            keys.append({"key": line.split("=")[0].strip(), "path": rel, "line": i})
    return keys[:40]


def build_snapshot(con, project_id: str, root: Path, head_sha: str = "") -> dict:
    t0 = time.perf_counter()
    root = root.resolve()
    files = iter_files(root)
    texts = {p.relative_to(root).as_posix(): read_text(p) for p in files}
    rel_paths = list(texts.keys())

    snap_id = uuid.uuid4().hex[:12]
    lang_counter: Counter[str] = Counter()
    loc = 0
    chunk_n = 0

    con.execute("INSERT INTO snapshot(id, project_id, head_sha, created_at) VALUES(?,?,?,?)",
                (snap_id, project_id, head_sha, now()))
    if con.backend == "sqlite":
        con.execute("DELETE FROM chunk_fts WHERE rowid IN (SELECT id FROM chunk WHERE snapshot_id=?)", (snap_id,))

    for p in files:
        rel = p.relative_to(root).as_posix()
        text = texts.get(rel, "")
        loc += len(text.splitlines())
        lang = lang_of(p)
        for rel_path, start, end, body in iter_chunks(p, root):
            syms = symbols.extract_symbols(body)
            sym_text = " ".join(f"{n} {k}" for n, k, _ in syms)
            cur = con.execute(
                "INSERT INTO chunk(snapshot_id,kind,path,start_line,end_line,text,tok_text,symbols,lang)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (snap_id, "file_chunk", rel_path, start, end, body,
                 to_index_text(body + "\n" + sym_text), sym_text, lang))
            rid = cur.lastrowid
            if con.backend == "sqlite":
                con.execute("INSERT INTO chunk_fts(rowid,path,symbols,tok_text) VALUES(?,?,?,?)",
                            (rid, rel_path, sym_text, to_index_text(body + "\n" + sym_text)))
            chunk_n += 1
            lang_counter[lang] += 1

    deps = _parse_deps(root, files)
    config_keys = _parse_config_keys(root, files)
    entries = symbols.find_entries(rel_paths, texts)
    has_env = any(Path(p).name in {".env.example", ".env.sample", ".env.template"} for p in rel_paths)
    findings = rules.scan(rel_paths, texts, has_env)

    con.execute(
        "UPDATE snapshot SET files_count=?, loc=?, languages_json=?, deps_json=?, entries_json=?, config_json=? WHERE id=?",
        (len(files), loc, json.dumps(dict(lang_counter), ensure_ascii=False),
         json.dumps(deps, ensure_ascii=False), json.dumps(entries, ensure_ascii=False),
         json.dumps(config_keys, ensure_ascii=False), snap_id))

    for f in findings:
        con.execute(
            "INSERT INTO finding(snapshot_id,rule_id,severity,path,line,evidence,suggestion)"
            " VALUES(?,?,?,?,?,?,?)",
            (snap_id, f["rule_id"], f["severity"], f["path"], f["line"], f["evidence"], f["suggestion"]))

    con.commit()
    return {
        "snapshot_id": snap_id,
        "files": len(files),
        "chunks": chunk_n,
        "loc": loc,
        "languages": dict(lang_counter),
        "deps": len(deps),
        "findings": len(findings),
        "entries": len(entries),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
