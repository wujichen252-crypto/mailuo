"""定时保鲜：每晚扫描 + sha 去重（不引入 APScheduler，避免多一个依赖）。"""
import threading
import time
from datetime import datetime, timedelta

from app.config import ENABLE_SCHEDULER, SCHEDULE_HOUR
from app.service import list_projects, refresh_project

_state = {"last_run": None, "last_result": None}
_lock = threading.Lock()


def run_due(con, force: bool = False) -> dict:
    """对所有 github 项目跑一次刷新；sha 未变的会被跳过。"""
    results = []
    for p in list_projects(con):
        if p["source_kind"] != "github" or not p["repo_url"]:
            continue
        try:
            r = refresh_project(con, p["id"], force=force)
        except Exception as exc:  # 单个失败不影响整体
            r = {"error": str(exc)[:200]}
        results.append({"project": p["name"], "id": p["id"], **r})
    out = {"ran_at": datetime.now().isoformat(timespec="seconds"),
           "total": len(results),
           "skipped": sum(1 for r in results if r.get("skipped")),
           "results": results}
    _state["last_run"] = out["ran_at"]
    _state["last_result"] = out
    return out


def _loop(con) -> None:
    while True:
        now = datetime.now()
        nxt = now.replace(hour=SCHEDULE_HOUR, minute=0, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        time.sleep(max(30, (nxt - now).total_seconds()))
        with _lock:
            try:
                run_due(con)
            except Exception as exc:
                print(f"[scheduler] 失败：{exc}")


def start_scheduler(con) -> None:
    if not ENABLE_SCHEDULER:
        return
    t = threading.Thread(target=_loop, args=(con,), daemon=True, name="mailuo-scheduler")
    t.start()


def status() -> dict:
    return dict(_state)
