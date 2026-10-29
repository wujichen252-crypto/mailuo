"""SQLite 存储层（零外部依赖：不装 PG / 不用 ORM）。"""
import json
import sqlite3
from pathlib import Path

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  repo_url TEXT NOT NULL,
  local_path TEXT NOT NULL,
  source_kind TEXT NOT NULL DEFAULT 'github',
  visibility TEXT NOT NULL DEFAULT 'public',
  share_token TEXT NOT NULL UNIQUE,
  head_sha TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_indexed_at TEXT,
  last_analyzed_at TEXT,
  token_budget INTEGER DEFAULT 80000
);

CREATE TABLE IF NOT EXISTS snapshot (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  head_sha TEXT,
  files_count INTEGER NOT NULL DEFAULT 0,
  loc INTEGER NOT NULL DEFAULT 0,
  languages_json TEXT NOT NULL DEFAULT '{}',
  deps_json TEXT NOT NULL DEFAULT '[]',
  entries_json TEXT NOT NULL DEFAULT '[]',
  config_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunk (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'file_chunk',
  path TEXT NOT NULL,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  text TEXT NOT NULL,
  tok_text TEXT NOT NULL,
  symbols TEXT NOT NULL DEFAULT '',
  lang TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
  path, symbols, tok_text,
  content='chunk', content_rowid='id', tokenize='unicode61'
);

CREATE TABLE IF NOT EXISTS finding (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  path TEXT NOT NULL,
  line INTEGER NOT NULL,
  evidence TEXT NOT NULL,
  suggestion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  template_version TEXT NOT NULL,
  sections_json TEXT NOT NULL,
  gaps_json TEXT NOT NULL DEFAULT '[]',
  metrics_json TEXT NOT NULL DEFAULT '{}',
  model TEXT NOT NULL DEFAULT 'mock',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT NOT NULL,
  intent TEXT NOT NULL DEFAULT '',
  hits INTEGER NOT NULL DEFAULT 0,
  latency_ms REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunk_snap ON chunk(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_chunk_path ON chunk(snapshot_id, path);
CREATE INDEX IF NOT EXISTS idx_finding_snap ON finding(snapshot_id);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    p = Path(db_path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def rebuild_fts(con: sqlite3.Connection) -> None:
    con.executescript("INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild');")
    con.commit()


def rows_to_json(rows) -> list[dict]:
    return [json.loads(json.dumps(dict(r))) for r in rows]
