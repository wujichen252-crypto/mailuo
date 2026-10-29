"""仓库接入：GitHub URL 浅克隆 / 本地目录（fixture 与内测用）。"""
import re
import shutil
import subprocess
from pathlib import Path

from app.config import REPOS


def normalize_url(url: str) -> str:
    url = url.strip()
    url = re.sub(r"\.git$", "", url)
    return url.rstrip("/")


def repo_slug(url: str) -> str:
    path = normalize_url(url).split("://")[-1]
    parts = [p for p in path.split("/") if p and p not in {"github.com", "gitee.com", "www.github.com"}]
    slug = "-".join(parts[-2:])
    return re.sub(r"[^A-Za-z0-9._-]", "-", slug)[:60] or "repo"


def clone(url: str, project_id: str) -> tuple[Path, str]:
    dest = REPOS / project_id
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", "--single-branch", "--quiet", normalize_url(url), str(dest)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:400] or "git clone 失败")
    return dest, head_sha(dest)


def head_sha(path: Path) -> str:
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=20)
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def remote_sha(url: str) -> str:
    """不做完整拉取的远端 HEAD 探测（定时刷新用）。"""
    try:
        proc = subprocess.run(["git", "ls-remote", normalize_url(url), "HEAD"],
                              capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return ""
        return proc.stdout.split()[0] if proc.stdout.strip() else ""
    except (subprocess.SubprocessError, OSError):
        return ""
