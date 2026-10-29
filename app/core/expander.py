"""查询理解层：中文提问 × 英文代码 的跨语言扩展。

实测结论（docs/search-engine.md §4）：仓库代码基本是英文，
中文问题（"配置在哪""怎么部署"）在纯倒排里必然 0 命中。
v1 用**确定性术语表**做扩展（可单测、可复现），不依赖模型；
v2 可换成 LLM 扩展 + 缓存，但评测口径不变。
"""
import re

# 中文术语 -> 英文关键词（按命中优先级排列）
TERM_MAP: dict[str, list[str]] = {
    "中间件": ["middleware"],
    "路由": ["route", "router", "routes", "handler"],
    "接口": ["api", "endpoint", "handler", "controller"],
    "入口": ["main", "entry", "app"],
    "启动": ["run", "start", "boot", "server"],
    "运行": ["run", "start", "execute"],
    "安装": ["install", "requirement", "dependency"],
    "部署": ["deploy", "deployment", "docker", "compose", "nginx"],
    "构建": ["build", "compile", "make"],
    "配置": ["config", "settings", "env", "environment", "yaml"],
    "环境变量": ["env", "getenv", "environment"],
    "端口": ["port", "listen"],
    "数据库": ["database", "db", "sql", "mysql", "postgres"],
    "迁移": ["migration", "migrate", "schema"],
    "模型": ["model", "entity", "schema"],
    "缓存": ["cache", "redis"],
    "队列": ["queue", "kafka", "rabbit"],
    "认证": ["auth", "authentication", "login", "jwt", "token"],
    "鉴权": ["auth", "permission", "rbac"],
    "日志": ["log", "logger", "logging"],
    "测试": ["test", "spec", "pytest"],
    "定时": ["cron", "schedule", "timer"],
    "上传": ["upload", "file", "multipart"],
    "导出": ["export", "download", "csv"],
    "权限": ["permission", "role", "acl"],
    "分页": ["pagination", "page", "size", "offset", "limit"],
    "列表": ["list", "table", "items"],
    "表格": ["table", "grid", "columns"],
    "用户": ["user", "account", "member"],
    "地址": ["url", "base", "endpoint", "host"],
    "依赖": ["dependency", "require", "package"],
    "目录": ["directory", "structure", "tree", "folder"],
    "文档": ["readme", "docs", "documentation"],
    "许可": ["license"],
    "坑": ["todo", "fixme", "deprecated", "issue"],
    "报错": ["error", "exception", "panic", "fail"],
}

CJK = re.compile(r"[\u4e00-\u9fff]+")


def expand(query: str, limit: int = 10) -> list[str]:
    """返回与原查询并行的英文关键词（去重、保序）。"""
    out: list[str] = []
    seen: set[str] = set()
    for m in CJK.finditer(query):
        run = m.group(0)
        for term, words in TERM_MAP.items():
            if term in run:
                for w in words:
                    if w not in seen:
                        seen.add(w)
                        out.append(w)
    return out[:limit]


def expand_query(query: str) -> str:
    """把扩展词拼到原查询后面（检索用，展示仍用原查询）。"""
    extra = expand(query)
    return f"{query} {' '.join(extra)}" if extra else query
