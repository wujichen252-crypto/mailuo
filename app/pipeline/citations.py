"""引用校验：path#Lx-Ly 必须能在该 snapshot 里回查成功。

这是"报告不是 AI 废话"的物理保证：
  - 路径必须真实存在于索引
  - 行号区间必须落在文件行数内
  - （可选）片段必须包含 claim 中的关键数字/路径
"""
import re

CITE = re.compile(r"^(?P<path>.+?)#L(?P<start>\d+)(?:-L?(?P<end>\d+))?$")


def parse(cite: str) -> tuple[str, int, int] | None:
    m = CITE.match((cite or "").strip())
    if not m:
        return None
    start = int(m.group("start"))
    end = int(m.group("end") or m.group("start"))
    if end < start:
        start, end = end, start
    return m.group("path"), start, end


def file_line_counts(con, snapshot_id: str) -> dict[str, int]:
    rows = con.execute(
        "SELECT path, MAX(end_line) AS n FROM chunk WHERE snapshot_id=? GROUP BY path",
        (snapshot_id,)).fetchall()
    return {r["path"]: int(r["n"]) for r in rows}


def resolve(con, snapshot_id: str, cite: str, line_counts: dict[str, int] | None = None) -> dict:
    parsed = parse(cite)
    if parsed is None:
        return {"cite": cite, "ok": False, "reason": "格式错误"}
    path, start, end = parsed
    counts = line_counts if line_counts is not None else file_line_counts(con, snapshot_id)
    total = counts.get(path)
    if total is None:
        # 容忍 ./ 前缀与大小写差异
        alt = {k.lower().lstrip("./"): v for k, v in counts.items()}
        total = alt.get(path.lower().lstrip("./"))
        if total is None:
            return {"cite": cite, "ok": False, "reason": "文件不在索引内"}
    if start < 1 or end > total:
        return {"cite": cite, "ok": False, "reason": f"行号越界（文件共 {total} 行）"}
    return {"cite": cite, "ok": True, "path": path, "start": start, "end": end}


def snippet_of(con, snapshot_id: str, path: str, start: int, end: int) -> str:
    row = con.execute(
        "SELECT text, start_line FROM chunk WHERE snapshot_id=? AND path=? AND start_line<=? AND end_line>=? "
        "ORDER BY start_line DESC LIMIT 1", (snapshot_id, path, start, end)).fetchone()
    if not row:
        return ""
    block = row["text"].splitlines()
    offset = max(0, start - row["start_line"])
    span = max(1, end - start + 1)
    return "\n".join(block[offset:offset + span])[:600]
