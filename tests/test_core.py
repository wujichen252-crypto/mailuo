"""核心单测：分词 / 扩展 / 引用解析 / 规则 / 索引+检索端到端。

跑法：python -m pytest -q
"""
import json
from pathlib import Path

import pytest

from app.config import ROOT
from app.core import rules
from app.core.expander import expand
from app.core.indexer import build_snapshot
from app.core.retriever import search
from app.core.tokenize import to_fts_query, tokens
from app.infra.db import connect
from app.pipeline import citations

FIXTURE = ROOT / "fixtures" / "repos" / "demo-go-service"


def test_cjk_bigram_tokens():
    toks = tokens("如何启动项目")
    assert "启动" in toks
    assert "项目" in toks
    # 整句不能被当成一个 token（历史 bug：整串命中 0）
    assert "如何启动项目" not in toks


def test_identifier_split():
    toks = tokens("func GetUserByID()")
    assert "get" in toks and "user" in toks


def test_fts_query_escapes_quotes():
    expr = to_fts_query('say "hi"')
    assert expr.count('"') % 2 == 0


def test_expander_bridges_cn_to_code():
    assert "config" in expand("配置在哪")
    assert "middleware" in expand("中间件怎么注册")


def test_citation_parse():
    path, start, end = citations.parse("internal/route/route.go#L12-L20")
    assert (path, start, end) == ("internal/route/route.go", 12, 20)
    assert citations.parse("bad-format") is None


def test_citation_resolve_out_of_range():
    counts = {"a.go": 10}
    res = citations.resolve(None, "snap", "a.go#L8-L20", counts)
    assert res["ok"] is False and "越界" in res["reason"]
    ok = citations.resolve(None, "snap", "a.go#L2-L5", counts)
    assert ok["ok"] is True


def test_rules_detect_hardcoded_path(tmp_path: Path):
    (tmp_path / "main.go").write_text('package main\nconst p = "/home/jiangyh/app.log"\n', encoding="utf-8")
    findings = rules.scan(["main.go"], {"main.go": 'package main\nconst p = "/home/jiangyh/app.log"\n'}, True)
    assert any(f["rule_id"] == "R1_hardcoded_path" for f in findings)
    assert findings[0]["line"] == 2


def test_rules_readme_script_mismatch(tmp_path: Path):
    readme = "run it:\n\n```bash\nnpm run start:prod\n```\n"
    pkg = json.dumps({"scripts": {"dev": "vite"}})
    findings = rules.scan(["README.md", "package.json"],
                          {"README.md": readme, "package.json": pkg}, True)
    assert any(f["rule_id"] == "R4_readme_cmd_mismatch" for f in findings)


@pytest.fixture()
def indexed(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    snap = build_snapshot(con, "p1", FIXTURE, "abc123")
    return con, snap["snapshot_id"]


def test_index_and_search_cn(indexed):
    con, snap = indexed
    res = search(con, snap, "路由在哪", k=3, log=False)
    assert res["hits"] > 0
    assert any("route" in r["path"].lower() for r in res["results"])


def test_report_citations_resolve():
    from app.pipeline.report import generate
    con = connect(FIXTURE.parents[3] / "data" / "test_report.sqlite")
    snap = build_snapshot(con, "p1", FIXTURE, "abc123")
    rep = generate(con, "p1", snap["snapshot_id"], "demo-go-service")
    assert rep["metrics"]["cite_resolve_rate"] == 1.0
    assert rep["metrics"]["slot_hit"] >= 6
    first = next(s for s in rep["sections"] if s["claims"])
    assert first["claims"][0]["citations"]
