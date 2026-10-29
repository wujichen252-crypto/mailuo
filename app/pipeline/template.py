"""报告模板 v1 —— 12 槽位生成契约（详见 docs/report-template.md）。

每个槽位声明：要回答什么、用哪些检索 query 取证、取不到时怎么降级。
AI 只能在这些槽位内、用检索引擎返回的证据说话。
"""

TEMPLATE_VERSION = "v1"

SLOTS = [
    {"id": "what", "title": "它是什么", "question": "一句话说明项目用途",
     "queries": ["{name} 项目 简介 用途 overview about"],
     "degrade": "仓库未提供项目说明（README 缺失或过短）", "max_claims": 2},
    {"id": "stack", "title": "技术栈", "question": "用了什么语言、框架、依赖",
     "queries": ["dependencies framework version package require"],
     "degrade": "未找到依赖清单，只能给出语言占比", "max_claims": 2},
    {"id": "run", "title": "怎么跑起来", "question": "本地启动需要哪些命令",
     "queries": ["install run start server command build"],
     "degrade": "未找到可执行的启动说明，接手前必须问作者", "max_claims": 4},
    {"id": "layout", "title": "目录与模块", "question": "顶层目录各负责什么",
     "queries": ["directory structure module 目录 结构"],
     "degrade": "目录结构无文档说明", "max_claims": 4},
    {"id": "entry", "title": "入口与请求链路", "question": "程序从哪进入、路由在哪注册",
     "queries": ["main entry router register handler middleware"],
     "degrade": "未识别到入口文件", "max_claims": 3},
    {"id": "data", "title": "数据与存储", "question": "有哪些模型、表、迁移",
     "queries": ["model schema migration table sql database"],
     "degrade": "未发现数据层", "max_claims": 3},
    {"id": "config", "title": "配置与环境变量", "question": "跑起来前要配哪些项",
     "queries": ["env config variable default settings 配置"],
     "degrade": "缺 .env 模板，配置项需从代码推断", "max_claims": 3},
    {"id": "integrations", "title": "外部依赖与集成", "question": "依赖哪些外部服务",
     "queries": ["redis mysql mongo client sdk api queue third-party"],
     "degrade": "未发现外部服务集成", "max_claims": 2},
    {"id": "traps", "title": "已知坑与限制", "question": "接手会踩什么坑",
     "queries": ["TODO FIXME error deprecated 注意"],
     "degrade": "未扫描到明显障碍", "max_claims": 5},
    {"id": "start_point", "title": "从哪开始改", "question": "加一个功能该动哪几个文件",
     "queries": ["service handler controller route 逻辑 接口"],
     "degrade": "无法推断改动入口，建议从入口文件开始读", "max_claims": 3},
    {"id": "meta", "title": "维护信息", "question": "许可、活跃度、贡献方式",
     "queries": ["license contributing 许可证 贡献"],
     "degrade": "未声明许可，商用前需确认", "max_claims": 2},
    {"id": "gaps", "title": "信息缺失清单", "question": "哪些槽位证据不足", "queries": [],
     "degrade": "", "max_claims": 0},
]

SLOT_IDS = [s["id"] for s in SLOTS]
NON_GAP_SLOTS = [s for s in SLOTS if s["id"] != "gaps"]


def queries_for(slot: dict, project_name: str) -> list[str]:
    return [q.format(name=project_name) for q in slot.get("queries", [])]
