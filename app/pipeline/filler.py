"""填槽：mock（零 key 可用，确定性）与 llm（真模型，受模板约束）两种实现。

mock 不是"假数据"：它从索引里确定性地抽取事实并挂引用，
所以零 key 演示出来的报告同样是可核查的，只是措辞朴素。
"""
import json
import re
from typing import Any

import httpx

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, MOCK_LLM
from app.pipeline.template import NON_GAP_SLOTS

MAX_CLAIM_CHARS = 118
CMD = re.compile(r"^\s*(?:\$\s*)?(go run|go build|npm |pnpm |yarn |pip |python |uv |docker |make |cargo |uvicorn|flask |php artisan|composer )", re.I)
DROP_CMD = re.compile(r"(pre-commit|golangci|eslint|prettier|husky|go vet|go test|npm test|pnpm test|pytest|coverage|lint)", re.I)
ENV_KEY = re.compile(r"(?:Getenv|getenv|environ\.get|process\.env\.|os\.getenv\()\s*[\[\"']?([A-Z][A-Z0-9_]{2,})")
YAML_KEY = re.compile(r"^([A-Za-z_][\w-]{1,30}):\s*\S")
CONST_KEY = re.compile(r"^\s*([A-Z][A-Za-z0-9_]{2,})\s*=\s*(\"[^\"]{0,40}\"|-?\d+|true|false)")


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_CLAIM_CHARS else text[:MAX_CLAIM_CHARS - 1] + "…"


def _first_sentence(text: str) -> str:
    flat = " ".join(text.split())
    flat = re.sub(r"^[#>*_\-\s]+", "", flat)
    flat = flat.replace("**", "").replace("`", "")
    m = re.search(r"[。.!?！？]\s", flat + " ")
    return _clip(flat[:m.end()] if m else flat)


def _cite(path: str, start: int, end: int | None = None) -> str:
    end = end or start
    return f"{path}#L{start}-L{end}"


class MockFiller:
    """确定性抽取：只用索引里的事实，不做任何推测。"""

    name = "mock"

    def __init__(self, con, snapshot_id: str, meta: dict):
        self.con = con
        self.sid = snapshot_id
        self.meta = meta

    # ---- 工具 ----
    def _chunks(self, like: str | None = None, limit: int = 60) -> list[dict]:
        sql = "SELECT path,start_line,end_line,text,symbols,lang FROM chunk WHERE snapshot_id=?"
        args: list[Any] = [self.sid]
        if like:
            sql += " AND (path LIKE ? OR text LIKE ?)"
            args += [f"%{like}%", f"%{like}%"]
        sql += " ORDER BY path, start_line LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def _line_of(self, chunk: dict, needle: str) -> int:
        for i, line in enumerate(chunk["text"].splitlines()):
            if needle in line:
                return min(chunk["end_line"], chunk["start_line"] + i)
        return chunk["start_line"]

    def _dep_file_chunk(self) -> dict | None:
        for dep in self.meta["deps"]:
            for c in self._chunks():
                if c["path"] == dep["source"]:
                    return c
        return None

    # ---- 各槽位 ----
    def what(self) -> list[dict]:
        """取 README 的简介段：优先文件开头，跳过 badge/标题/列表/代码块/目录树/env 赋值。"""
        chunks = [c for c in self._chunks() if "readme" in c["path"].lower()]
        chunks.sort(key=lambda c: c["start_line"])
        passes = ([c for c in chunks if c["start_line"] == 1], chunks)
        for group in passes:
            for c in group:
                in_fence = False
                for i, line in enumerate(c["text"].splitlines()):
                    raw = line.strip()
                    if raw.startswith("```"):
                        in_fence = not in_fence
                        continue
                    if in_fence:
                        continue
                    if not raw or len(raw) < 24:
                        continue
                    if raw[0] in "-*+|>│├└─=#":
                        continue
                    if raw.startswith("[") or raw.startswith("!["):     # badge 行
                        continue
                    # 把 markdown 链接还原成文字，避免简介里有链接就被丢掉
                    clean = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw).strip()
                    if len(clean) < 24:
                        continue
                    if re.match(r"^[A-Z][A-Z0-9_]{2,}\s*=", raw):   # env 赋值行
                        continue
                    if re.match(r"^[a-z_]+:\s", raw):              # YAML 键值
                        continue
                    if re.match(r"^(git|npm|pnpm|yarn|go|pip|uv|docker|curl|cd|cp|mv|python|make|brew|apt|import|from)\b", clean, re.I):
                        continue
                    if "://" in clean or clean.startswith("./"):
                        continue
                    if clean.isupper() or clean.endswith(":") or clean.endswith("："):
                        continue
                    text = _first_sentence(clean)
                    # 至少要像一句话：含空格且 >= 6 个词，或中文 >= 12 字
                    latin_words = len(re.findall(r"[A-Za-z0-9]+", text))
                    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
                    if latin_words < 6 and cjk_chars < 12:
                        continue
                    ln = c["start_line"] + i
                    return [{"text": text, "citations": [_cite(c["path"], ln, ln)]}]
        return []

    def stack(self) -> list[dict]:
        langs = self.meta["languages"]
        total = sum(langs.values()) or 1
        top = sorted(langs.items(), key=lambda kv: -kv[1])[:3]
        lang_txt = "、".join(f"{k} {v * 100 // total}%" for k, v in top)
        def label(n: str) -> str:
            parts = n.split("/")
            last = parts[-1]
            if re.match(r"^v\d+$", last) and len(parts) > 1:
                last = parts[-2]
            return last.rsplit("@", 1)[0]

        deps = [label(d["name"]) for d in self.meta["deps"]][:3]
        if not deps:
            return []
        c = self._dep_file_chunk()
        if not c:
            return []
        return [{"text": _clip(f"{lang_txt}；主要依赖 {', '.join(deps)}"),
                 "citations": [_cite(c["path"], c["start_line"], min(c["end_line"], c["start_line"] + 6))]}]

    def run(self) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for c in self._chunks():
            low = c["path"].lower()
            fname = low.split("/")[-1]
            if "readme" not in low and fname not in {"makefile", "docker-compose.yml", "docker-compose.yaml", "setup.sh"}:
                continue
            in_fence = False
            for i, line in enumerate(c["text"].splitlines()):
                raw_line = line.strip()
                if raw_line.startswith("```"):
                    in_fence = not in_fence
                    continue
                if not in_fence and "readme" in low:
                    continue          # README 只认代码块里的命令，避免正文句子被当成命令
                m = CMD.match(raw_line)
                if not m:
                    continue
                raw = raw_line.strip("`")
                if DROP_CMD.search(raw):
                    continue
                cmd = _clip(raw)
                sig = " ".join(raw.split()).lower()
                if sig in seen:
                    continue
                seen.add(sig)
                ln = c["start_line"] + i
                out.append({"text": cmd, "citations": [_cite(c["path"], ln)]})
                if len(out) >= 4:
                    return out
        return out

    def layout(self) -> list[dict]:
        dirs: dict[str, list[dict]] = {}
        for c in self._chunks(limit=400):
            parts = c["path"].split("/")
            top = parts[0] if len(parts) > 1 else "(根目录)"
            bucket = dirs.setdefault(top, [])
            if all(x["path"] != c["path"] for x in bucket):
                bucket.append({"path": c["path"], "end": c["end_line"]})
        if not dirs:
            return []
        items = sorted(dirs.items(), key=lambda kv: -len(kv[1]))[:4]
        text = "顶层：" + "，".join(f"{k}/（{len(v)} 个取样文件）" for k, v in items)
        cites = [_cite(v[0]["path"], 1, min(3, int(v[0]["end"]))) for _, v in items[:3]]
        return [{"text": _clip(text), "citations": cites}]

    def entry(self) -> list[dict]:
        out = []
        for e in self.meta["entries"][:3]:
            routes = len(e.get("routes") or [])
            suffix = f"（{routes} 条路由）" if routes else ""
            line = (e["routes"][0]["line"] if routes else 1)
            out.append({"text": _clip(f"入口候选：{e['path']}{suffix}"),
                        "citations": [_cite(e["path"], line)]})
        return out

    def data(self) -> list[dict]:
        out = []
        for c in self._chunks():
            low = c["path"].lower()
            if any(k in low for k in ("model", "schema", "migration", "entity", ".sql")):
                out.append({"text": _clip(f"数据层：{c['path']}"),
                            "citations": [_cite(c["path"], c["start_line"], min(c["end_line"], c["start_line"] + 4))]})
                if len(out) >= 3:
                    break
        return out

    def config(self) -> list[dict]:
        keys = self.meta["config"]
        if keys:
            first = keys[0]
            shown = "、".join(k["key"] for k in keys[:3])
            more = f" 等 {len(keys)} 项" if len(keys) > 3 else ""
            return [{"text": _clip(f"启动前需配置 {shown}{more}"),
                     "citations": [_cite(first["path"], first["line"], keys[min(len(keys) - 1, 6)]["line"])]}]
        # 没有 .env.example -> 从 config/*.yaml 与常量定义反推（仍是真实文件行，不是猜测）
        found: list[tuple[str, str, int]] = []
        seen: set[str] = set()
        for c in self._chunks(limit=300):
            low = c["path"].lower()
            if not any(k in low for k in ("config", "const", "setting", "env")):
                continue
            for i, line in enumerate(c["text"].splitlines()):
                m = ENV_KEY.search(line)
                if m:
                    key = m.group(1)
                else:
                    m2 = YAML_KEY.match(line) or CONST_KEY.match(line)
                    key = m2.group(1) if m2 else ""
                if not key or key in seen or len(key) > 32:
                    continue
                seen.add(key)
                found.append((key, c["path"], c["start_line"] + i))
                if len(found) >= 6:
                    break
            if len(found) >= 6:
                break
        if not found:
            return []
        names = "、".join(k for k, _, _ in found[:6])
        return [{"text": _clip(f"配置项（未提供 .env.example，从 config/常量推断）：{names}"),
                 "citations": [_cite(p, ln) for _, p, ln in found[:3]]}]

    def integrations(self) -> list[dict]:
        known = ("redis", "mysql", "postgres", "mongo", "kafka", "rabbit", "s3", "minio",
                 "elastic", "httpx", "requests", "openai", "stripe", "aliyun", "wechat")
        hit = []
        for d in self.meta["deps"]:
            low = d["name"].lower()
            if any(k in low for k in known):
                hit.append(d["name"])
        if not hit:
            return []
        c = self._dep_file_chunk()
        if not c:
            return []
        return [{"text": _clip("外部集成依赖：" + ", ".join(hit[:5])),
                 "citations": [_cite(c["path"], c["start_line"], min(c["end_line"], c["start_line"] + 6))]}]

    def traps(self) -> list[dict]:
        out = []
        for f in self.meta["findings"][:5]:
            tag = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(f["severity"], "•")
            out.append({"text": _clip(f"{tag} {f['rule_id']}：{f['suggestion']}"),
                        "citations": [_cite(f["path"], f["line"])]})
        return out

    def start_point(self) -> list[dict]:
        out = []
        for c in self._chunks():
            low = c["path"].lower()
            if any(k in low for k in ("handler", "service", "controller", "api/", "route")):
                out.append({"text": _clip(f"改功能先看：{c['path']}"),
                            "citations": [_cite(c["path"], c["start_line"], min(c["end_line"], c["start_line"] + 4))]})
                if len(out) >= 3:
                    break
        if out:
            return out
        for e in self.meta["entries"][:2]:
            out.append({"text": _clip(f"从入口读起：{e['path']}"), "citations": [_cite(e["path"], 1)]})
        return out

    def meta_slot(self) -> list[dict]:
        for c in self._chunks():
            name = c["path"].lower().split("/")[-1]
            if name.startswith("license") or name.startswith("licence"):
                head = _first_sentence(c["text"])
                return [{"text": _clip(f"许可：{head}"), "citations": [_cite(c["path"], c["start_line"], min(c["end_line"], c["start_line"] + 5))]}]
        return []

    def fill(self) -> dict[str, list[dict]]:
        handlers = {
            "what": self.what, "stack": self.stack, "run": self.run, "layout": self.layout,
            "entry": self.entry, "data": self.data, "config": self.config,
            "integrations": self.integrations, "traps": self.traps,
            "start_point": self.start_point, "meta": self.meta_slot,
        }
        return {sid: handlers[sid]() for sid in handlers}


class LLMFiller:
    """真模型填槽：只允许输出 JSON，证据用 E1..En 引用，服务端回查。"""

    name = "llm"

    def __init__(self, con, snapshot_id: str, meta: dict, evidence: dict[str, list[dict]]):
        self.con = con
        self.sid = snapshot_id
        self.meta = meta
        self.evidence = evidence

    def _prompt(self) -> str:
        slots = []
        for s in NON_GAP_SLOTS:
            ev = self.evidence.get(s["id"], [])
            lines = "\n".join(
                f"[E{i + 1}] {e['path']}#L{e['start_line']}-{e['end_line']}\n{e['text'][:400]}"
                for i, e in enumerate(ev))
            slots.append(f"### 槽位 {s['id']}（{s['title']}）：{s['question']}\n证据：\n{lines or '（无）'}")
        langs = json.dumps(self.meta["languages"], ensure_ascii=False)
        return f"""你在填一份固定模板的代码仓库交接报告。规则：
1) 只能使用下面给出的证据，不许引入外部知识；证据不足就跳过该槽位，不要编。
2) 每条 claim ≤ 60 字（中文），最多 5 条，必须给 evidence 编号。
3) 只输出 JSON，不要 markdown。
输出格式：{{"sections":[{{"id":"what","claims":[{{"text":"...","evidence":["E1"]}}]}}]}}

仓库语言分布：{langs}

{chr(10).join(slots)}"""

    def fill(self) -> dict[str, list[dict]]:
        if MOCK_LLM or not LLM_API_KEY:
            return {}
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": self._prompt()}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=LLM_TIMEOUT) as client:
                r = client.post(f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
                                headers={"Authorization": f"Bearer {LLM_API_KEY}"}, json=payload)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
        except Exception as exc:  # 网络/格式失败 -> 回退 mock，保证演示不中断
            print(f"[filler] LLM 失败，回退 mock：{exc}")
            return {}

        out: dict[str, list[dict]] = {}
        for sec in data.get("sections", []):
            sid = sec.get("id")
            if sid not in {s["id"] for s in NON_GAP_SLOTS}:
                continue
            claims = []
            for claim in (sec.get("claims") or [])[:5]:
                ev = self.evidence.get(sid, [])
                cites = []
                for tag in claim.get("evidence") or []:
                    m = re.match(r"E(\d+)", str(tag))
                    if not m:
                        continue
                    idx = int(m.group(1)) - 1
                    if 0 <= idx < len(ev):
                        e = ev[idx]
                        cites.append(_cite(e["path"], e["start_line"], e["end_line"]))
                claims.append({"text": _clip(claim.get("text", "")), "citations": cites})
            out[sid] = claims
        return out
