# 数据库：SQLite 与 MySQL 双后端

## 为什么要两套

| 场景 | 后端 | 理由 |
|---|---|---|
| 评委复现 / 本地开发 / 评测 | **SQLite**（默认） | 零外部服务，`docker compose up` 或 `python -m app.cli serve` 就能跑，10 分钟内完成 |
| 线上部署 | **MySQL 8** | 多实例、备份、1Panel 统一运维；中文全文用 ngram 索引 |

切换只改一个环境变量，业务代码不分叉。

## 配置

`.env`（已被 `.gitignore` 排除，不入库）：

```dotenv
# 默认 sqlite
MAILUO_DB=sqlite
MAILUO_SQLITE_PATH=data/mailuo.sqlite

# 线上 mysql
# MAILUO_DB=mysql
# MAILUO_DB_URL=mysql://user:pass@host:3306/dbname?charset=utf8mb4
```

## 检索在两套后端上的差异

| | SQLite | MySQL 8 |
|---|---|---|
| 索引 | FTS5 影子表 `chunk_fts`（unicode61） | `chunk.tok_text` 上的 `FULLTEXT ... WITH PARSER ngram` |
| 打分 | `bm25()`，越小越相关 | `MATCH ... AGAINST`，越大越相关 |
| 查询语法 | `"a" OR "b"` / `"a" AND "b"` | BOOLEAN：`a b`（隐式 OR）/ `+a +b` |
| 中文 | 自研二元分词写入 `tok_text` | 同一份 `tok_text` + ngram(2) 分词，口径一致 |

RRF 融合只用**排名**，不用原始分数，所以两种后端行为一致（`app/core/search_backend.py`）。

## 迁移步骤（SQLite → MySQL）

```bash
python scripts/export_data.py        # 导出 data/export/*.json（不含 FTS 倒排表）
python scripts/db_probe.py           # 可选：先验证连通性
python scripts/migrate_to_mysql.py   # 建表 + 灌数据 + 校验 FULLTEXT
```

迁移脚本是**幂等**的：先按依赖倒序 `DELETE`，再写入，最后逐表 `COUNT(*)` 校验。

## 注意事项

- `chunk.id` 是自增主键，迁移时不保留原 id（外键关系靠 `snapshot_id`/`path` 维系）。
- MySQL 需要 `utf8mb4`；`tok_text` 用 `LONGTEXT`，`FULLTEXT` 建在它上面。
- 远程 MySQL 会让检索从「亚毫秒」变成「百毫秒级」，报告生成整体仍在 3 秒内。
- 评测（`scripts/eval.py`）与单测（`tests/conftest.py`）**强制 SQLite**，不会写线上库。
