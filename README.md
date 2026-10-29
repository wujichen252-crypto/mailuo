# 脉络 mailuo · 开源项目的接手说明书

> **一个仓库只索引一次，全平台共享、每晚保鲜。**
> AI 只能按我们设计的 12 槽位模板、从自研检索引擎里取证据来填槽；取不到就标"信息缺失"，不编。

比赛：传智杯 2026 · 全国高校 Vibe Coding 开发挑战赛（省赛作品）
作者：江裕恒（wujichen）

---

## 10 分钟极速复现

### 方式 A：Docker（推荐）

```bash
git clone <仓库地址> mailuo && cd mailuo
cp .env.example .env          # 默认 MOCK_LLM=1，不需要任何 API Key
docker compose up -d --build
open http://localhost:8080    # Windows: start http://localhost:8080
```

### 方式 B：本机 Python（没有 Docker 时）

```bash
python -m venv .venv && . .venv/Scripts/activate     # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
python -m app.cli seed                # 导入种子库（8 个项目，离线可用）
python -m app.cli serve               # http://localhost:8000
```

### 验证是否成功

1. 打开首页 → 应该看到种子库里的项目
2. 点任意项目 → 报告页 12 张槽位卡，每张卡的 claim 右侧有 `path#Lx-Ly` 角标
3. 点任意角标 → 右侧抽屉显示**原文片段**（说明引用可回查）
4. 顶部「检索」→ 搜 `配置在哪` → 结果带行号

### 常见问题

| 现象 | 原因与处理 |
|---|---|
| 端口被占用 | 改 `docker-compose.yml` 的映射端口，或 `python -m app.cli serve --port 8010` |
| 首页空白 | 前端 `web/dist` 未提交/未构建：`cd web && pnpm install && pnpm build` |
| 报告里出现"AI 推测"灰底句 | 正常：说明该句没有通过引用回查，系统主动降级，而不是编造 |
| 拉取 GitHub 失败 | 匿名 API/克隆有频率限制；改用本地目录导入 `python -m app.cli report <本地路径>` |
| 没有 API Key | 默认就是 mock 模式，完整可跑；要真模型把 `.env` 的 `MOCK_LLM=0` 并填 Key |

---

## 它解决了什么

接手一个陌生仓库，真正贵的是"第一小时"：它怎么跑、入口在哪、改哪里、会踩什么坑。
现有 AI 仓库问答（DeepWiki 类）给的是**一次性的百科快照**；脉络给的是**可核查、每天保鲜的接手说明书**：

| | DeepWiki 类 | 脉络 |
|---|---|---|
| 刷新 | 一次生成，代码变了就过期 | 每晚重分析 + 手动触发，永远对应 HEAD |
| 生成 | 模型自由发挥 | **12 槽位模板 + 自研检索引擎取证** |
| 检索 | 通用问答 | 同一索引两用：生成取证 + 用户检索，结果必带行号 |
| 成本 | 每次提问都烧 token | 一次索引/分析、N 人复用 + sha 去重增量 |

---

## 架构

```text
Vue3 SPA (web/dist, 由 FastAPI 直接托管)
  ├ 公开库 / 报告页（12 槽位 + 引用抽屉）/ 检索页
  │        REST + JSON
FastAPI (app/)
  ├ api        /api/projects /api/search /api/cite /api/share /api/admin
  ├ core       crawler · chunker · tokenize · symbols · rules · expander · retriever
  ├ indexer    chunk -> FTS5(双 token) + 快照元数据 + 规则命中
  ├ pipeline   template(12 槽位) · filler(mock|llm) · citations(回查) · report
  └ scheduler  每晚 00:00 · sha 去重 · 变更优先
SQLite（零外部依赖：FTS5 倒排 + 元数据）
```

**五层机制**（技术文档"意图控制"章的同源）：

| 层 | 谁做 | 确定性保证 |
|---|---|---|
| L1 结构盘点 | 纯静态 | 全是事实，可单测 |
| L2 障碍规则引擎 | 纯规则 | 每条命中必带 `path:line` |
| L3 模板填槽 | LLM | 12 槽位 + 字数上限 + 引用必填 |
| L4 引用回查 | 服务端 | `path#Lx-Ly` 必须能回查，失败即降级灰区 |
| L5 增量刷新 | 纯算法 | sha 未变跳过 |

---

## 目录

```
app/           后端（FastAPI + SQLite FTS5）
web/           前端（Vue3 + Vite；dist 已提交，评委无需 Node）
scripts/       证据归档 / 检索原型 / 种子库
docs/          方案、模板、检索引擎 spec
fixtures/      种子库快照（离线演示）
tests/         单测
```

## 评测（可复现）

```bash
make eval        # Recall@5 / 引用回查率 / 槽位命中 / 灰区率
```

指标口径见 `docs/search-engine.md` 与 `docs/report-template.md`。

## License

MIT
