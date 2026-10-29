-- MySQL 8 结构（线上部署）。中文检索用 ngram 全文索引，与自研二元分词口径一致。
CREATE TABLE IF NOT EXISTS project (
  id VARCHAR(16) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  repo_url TEXT NOT NULL,
  local_path TEXT NOT NULL,
  source_kind VARCHAR(16) NOT NULL DEFAULT 'github',
  visibility VARCHAR(16) NOT NULL DEFAULT 'public',
  share_token VARCHAR(64) NOT NULL UNIQUE,
  head_sha VARCHAR(64) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  last_indexed_at DATETIME(6) NULL,
  last_analyzed_at DATETIME(6) NULL,
  token_budget INT DEFAULT 80000
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS snapshot (
  id VARCHAR(16) PRIMARY KEY,
  project_id VARCHAR(16) NOT NULL,
  head_sha VARCHAR(64) NULL,
  files_count INT NOT NULL DEFAULT 0,
  loc INT NOT NULL DEFAULT 0,
  languages_json LONGTEXT NOT NULL,
  deps_json LONGTEXT NOT NULL,
  entries_json LONGTEXT NOT NULL,
  config_json LONGTEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_snapshot_project (project_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chunk (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  snapshot_id VARCHAR(16) NOT NULL,
  kind VARCHAR(24) NOT NULL DEFAULT 'file_chunk',
  path VARCHAR(512) NOT NULL,
  start_line INT NOT NULL,
  end_line INT NOT NULL,
  text LONGTEXT NOT NULL,
  tok_text LONGTEXT NOT NULL,
  symbols TEXT NULL,
  lang VARCHAR(24) NOT NULL DEFAULT '',
  KEY idx_chunk_snap (snapshot_id),
  KEY idx_chunk_path (snapshot_id, path(191)),
  FULLTEXT KEY ft_chunk_tok (tok_text) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS finding (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  snapshot_id VARCHAR(16) NOT NULL,
  rule_id VARCHAR(48) NOT NULL,
  severity VARCHAR(12) NOT NULL,
  path VARCHAR(512) NOT NULL,
  line INT NOT NULL,
  evidence TEXT NOT NULL,
  suggestion TEXT NOT NULL,
  KEY idx_finding_snap (snapshot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS report (
  id VARCHAR(16) PRIMARY KEY,
  project_id VARCHAR(16) NOT NULL,
  snapshot_id VARCHAR(16) NOT NULL,
  template_version VARCHAR(12) NOT NULL,
  sections_json LONGTEXT NOT NULL,
  gaps_json LONGTEXT NOT NULL,
  metrics_json LONGTEXT NOT NULL,
  model VARCHAR(16) NOT NULL DEFAULT 'mock',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_report_project (project_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS search_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  query VARCHAR(512) NOT NULL,
  intent VARCHAR(24) NOT NULL DEFAULT '',
  hits INT NOT NULL DEFAULT 0,
  latency_ms DOUBLE NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
