"""连通性探测：读取 .env 里的 MAILUO_DB_URL，连 MySQL 并打印服务端信息。

用法：python scripts/db_probe.py
"""
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("MAILUO_DB_URL",):
        if os.getenv(k):
            env[k] = os.environ[k]
    return env


def main() -> int:
    env = load_env()
    url = env.get("MAILUO_DB_URL", "")
    if not url.startswith("mysql://"):
        print("MAILUO_DB_URL 不是 mysql:// 形式")
        return 1
    u = urlparse(url)
    host, port = u.hostname, u.port or 3306
    print(f"[1] 目标 {host}:{port}  库 {u.path.lstrip('/')}  用户 {u.username}")

    try:
        with socket.create_connection((host, port), timeout=8):
            print("[2] TCP 可达 ✅")
    except OSError as exc:
        print(f"[2] TCP 不可达 ❌ {exc}")
        return 2

    try:
        import pymysql
        conn = pymysql.connect(host=host, port=port, user=u.username,
                               password=unquote(u.password or ""),
                               database=u.path.lstrip("/"), charset="utf8mb4",
                               connect_timeout=8, read_timeout=10)
    except Exception as exc:
        print(f"[3] 认证/选库失败 ❌ {exc}")
        return 3

    with conn.cursor() as cur:
        cur.execute("SELECT VERSION(), DATABASE(), @@character_set_database, @@collation_database")
        ver, db, cs, coll = cur.fetchone()
        cur.execute("SHOW TABLES")
        tables = [r[0] for r in cur.fetchall()]
    print(f"[3] 登录成功 ✅ MySQL {ver} / 库 {db} / {cs} / {coll}")
    print(f"[4] 现有表 {len(tables)}: {tables[:8]}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
