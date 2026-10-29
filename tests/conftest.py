"""测试一律跑 SQLite 后端，避免把用例数据写进线上 MySQL。"""
import os
import sys
from pathlib import Path

os.environ["MAILUO_DB"] = "sqlite"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
