"""全局配置（全部可用环境变量覆盖，便于 10 分钟复现）。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """极简 .env 加载（不引入 python-dotenv）：已存在的环境变量优先。"""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

DATA = Path(os.getenv("MAILUO_DATA", str(ROOT / "data")))
REPOS = DATA / "repos"
DB_PATH = Path(os.getenv("MAILUO_SQLITE_PATH", str(DATA / "mailuo.sqlite")))

# LLM：默认 mock（评委零 key 也能完整跑通）
MOCK_LLM = os.getenv("MOCK_LLM", "1") == "1"
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "90"))

# 数据库后端：sqlite（默认、零依赖、评委复现用）| mysql（线上部署用）
DB_BACKEND = os.getenv("MAILUO_DB", "sqlite")
DB_URL = os.getenv("MAILUO_DB_URL", "")

# 索引范围（硬上限，防大仓爆炸）
WHITELIST = {".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".md", ".yaml", ".yml",
             ".json", ".toml", ".sql", ".sh", ".java", ".php", ".rs", ".txt", ".env", ".mod", ".sum"}
SKIP_DIRS = {"node_modules", "vendor", "dist", "build", ".git", "__pycache__", ".venv",
             "venv", "target", "coverage", ".idea", ".vscode", ".next", "out"}
MAX_FILE_BYTES = 8 * 1024
MAX_FILES = 40
CHUNK_LINES = 60
CHUNK_OVERLAP = 10

TEMPLATE_VERSION = "v1"

# 定时刷新
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "0"))
TOKEN_BUDGET_PER_PROJECT = int(os.getenv("TOKEN_BUDGET_PER_PROJECT", "80000"))
