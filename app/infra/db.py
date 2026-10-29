"""存储层：SQLite（默认，评委复现）与 MySQL（线上）双后端。

统一 API：
  con.execute(sql, params) -> cursor(fetchone/fetchall/lastrowid)
  con.commit() / con.close() / con.backend -> "sqlite" | "mysql"

约定：业务 SQL 一律用 `?` 占位符；MySQL 后端在 execute 里转成 `%s`。
时间戳不用数据库函数（`datetime('now')` 是 SQLite 专有），统一由 `now()` 传参。
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.config import DB_BACKEND, DB_PATH, DB_URL, ROOT

SQLITE_SCHEMA = """
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


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class SQLiteConn:
    backend = "sqlite"

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.executescript(SQLITE_SCHEMA)

    def execute(self, sql: str, params=()):
        return self._con.execute(sql, params)

    def executescript(self, sql: str):
        return self._con.executescript(sql)

    def commit(self):
        self._con.commit()

    def close(self):
        self._con.close()


class MySQLConn:
    backend = "mysql"

    def __init__(self, url: str):
        import pymysql
        from pymysql.cursors import DictCursor
        u = urlparse(url)
        if not u.hostname:
            raise ValueError("MAILUO_DB_URL 格式错误，应为 mysql://user:pass@host:port/db")
        self._con = pymysql.connect(
            host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""),
            password=unquote(u.password or ""), database=u.path.lstrip("/"),
            charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
            connect_timeout=10, read_timeout=30)
        self._ensure_schema()

    def _ensure_schema(self):
        schema = (ROOT / "app" / "infra" / "schema_mysql.sql").read_text(encoding="utf-8")
        with self._con.cursor() as cur:
            for stmt in [s.strip() for s in schema.split(";") if s.strip()]:
                cur.execute(stmt)
        self._con.commit()

    def execute(self, sql: str, params=()):
        cur = self._con.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def executescript(self, sql: str):
        with self._con.cursor() as cur:
            for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
                cur.execute(stmt)
        self._con.commit()

    def commit(self):
        self._con.commit()

    def close(self):
        self._con.close()


def connect(db_path: Path | None = None):
    """按 MAILUO_DB 选择后端：sqlite（默认）/ mysql。"""
    if DB_BACKEND.lower() == "mysql":
        if not DB_URL:
            raise RuntimeError("MAILUO_DB=mysql 时必须提供 MAILUO_DB_URL")
        return MySQLConn(DB_URL)
    return SQLiteConn(db_path or DB_PATH)


def rebuild_fts(con) -> None:
    if con.backend == "sqlite":
        con.executescript("INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild');")
        con.commit()
