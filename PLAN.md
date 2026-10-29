# 交接书 Handover — v1 定稿（开源仓库 · 模板驱动 · 自研检索）

> 来源：江裕恒的设计（2026-10-28），已按两条修正收敛：
> **① 暂时不做私有仓库，只做开源仓库；② 报告必须由"我们设计的模板"驱动，且用"我们自己构建的搜索引擎"取证据。**
> 约束：传智杯 Vibe Coding 省赛，2026-11-18 截止，单人，业余 55h。

---

## 0. 一句话

**一个开源仓库只被索引一次，全平台共享、每天保鲜；AI 只能按我们设计的模板、从我们自研的检索引擎里取证据来填槽，填不满就标"信息缺失"。**

结构上的差异（不是功能差异）：
- 别人做"快照式 wiki"，我们做**每晚刷新的持续知识层**；
- 别人让 AI 自由发挥，我们让 AI **在模板 + 索引的约束下填槽**；
- 别人每次问都烧 token，我们**一次索引/分析、N 人复用**。

---

## 1. 数据流（一条主线，四次复用）

```text
开源仓库 URL
   ↓ ① 拉取 + 过滤（后缀白名单 / 排除 vendor,node_modules / 单文件 8KB / ≤40 文件）
   ↓ ② 建索引（自研检索引擎）：file_chunk · symbol · config_item · dep · rule_finding
   ↓ ③ 模板填槽：12 槽位 → 检索计划 → 证据包 → LLM 填槽（JSON）→ 引用回查 → 灰区降级
   ↓ ④ 产出：报告页（12 卡） + 检索入口（同一索引） + 坑清单
   ↑ 每晚 00:00 / 手动：sha 未变跳过；变了只重算变更文件与受影响槽位
```

**同一次索引服务三件事**：报告生成、用户检索问答、坑规则匹配。这就是"省 API"的实现路径。

---

## 2. 范围（v1）

**做**

| # | 能力 | 说明 |
|---|---|---|
| 1 | 开源仓库登记 | GitHub URL；公开可见；分享只读链接 |
| 2 | 自研检索引擎 | 5 类索引对象，双索引（jieba + trigram），多路召回 + RRF 融合，输出必带 path#Lx-Ly |
| 3 | 模板驱动报告 | `docs/report-template.md` 的 12 槽位 + 生成契约 JSON |
| 4 | 引用校验 + 灰区 | 无证据 claim 强制标"AI 推测"，缺失槽位进 gaps |
| 5 | 站内检索 + 问答 | 用户侧检索同一索引；问答只读报告，不回读全仓 |
| 6 | 定时保鲜 | APScheduler 每晚 + 「立即执行一次」按钮 + sha 去重 + 变更文件优先 |
| 7 | 种子库 | 8–10 个已分析开源项目的报告 + 索引快照，零外网演示 |

**不做（进 v2 路线）**

私有仓库（OAuth / zip 上传 / 敏感代码存储）、跨项目语义推荐、团队空间与权限体系、多语言 AST 全解析、调用链动图、PDF 导出、真跑构建沙箱。

> zip 上传只保留一个用途：**导入 fixture 做离线演示/评测**，不作为产品功能对外承诺。

---

## 3. 架构

```text
Vue3 SPA
 ├ 公开库（项目列表 + 分享链接）   ├ 报告页（12 槽位卡 + 引用抽屉 + 灰区标记）
 ├ 搜索页（结果带 path#Lx-Ly 跳转）├ 分析进度（SSE 阶段条）
 └ 演示视图（立即执行一次定时任务、查看 token 预算）
        │ REST + SSE
FastAPI
 ├ api/        projects · analyze · search · ask · share · admin
 ├ crawler/    github(URL) · filter · snapshot(zip, 仅 fixture)
 ├ indexer/    chunker · symbolizer · config_parser · dep_parser · rules
 │             + builder(jieba 双索引) · retriever(多路+RRF) · expander(中→英)
 ├ pipeline/   planner(槽位→检索计划) · filler(LLM 填槽) · citations(回查) · gaps
 └ scheduler/  APScheduler 00:00 · sha 去重 · 队列 · token 预算
```

数据模型（增量关键字段）：

```text
project(id, name, repo_url, visibility, share_token, head_sha, last_indexed_at,
        last_analyzed_at, token_budget)
snapshot(id, project_id, head_sha, files_count, loc, languages_json)
chunk(id, snapshot_id, kind, path, start_line, end_line, text, symbols, lang)   -- 索引基表
symbol(id, snapshot_id, path, line, name, kind, signature)
finding(id, snapshot_id, rule_id, severity, path, line, evidence, suggestion)
report(id, project_id, snapshot_id, template_version, sections_json, metrics_json)
search_log(id, query, intent, hits, latency_ms)     -- 用于调参与演示数据
```

---

## 4. 三个不可省的机制

1. **模板契约**：12 槽位 × 每槽 ≤5 claim × 每 claim ≤120 字 + 必带 citations → 结构校验不过就重试/降级。
   → 详见 `docs/report-template.md`
2. **引用回查**：`path#Lx-Ly` 必须能在该 snapshot 里回查成功；空引用 → 强制 `inferred`（前端灰底）。
   → 这是"报告不是 AI 废话"的物理保证。
3. **sha 去重 + 变更优先**：成本命门。1000 仓全量 ≈ ¥2280/月，增量 ≈ ¥456/月（按 ¥1/M 入、¥2/M 出估算）。
   → 每晚先比 `head_sha`，未变直接跳过；变了只重算变更文件的 chunk 与受影响槽位。

---

## 5. 与 DeepWiki 类的差异（开场 30 秒就要讲）

| | DeepWiki 类 | 交接书 |
|---|---|---|
| 刷新 | 一次性快照，代码变了报告过期 | 每晚重分析 + 手动触发，永远对应 HEAD |
| 生成方式 | LLM 自由发挥 | **我们设计的 12 槽位模板 + 自研检索取证** |
| 检索 | 通用问答 | **同一索引服务两用**：生成取证 + 用户检索，且结果必带行号 |
| 成本 | 每次问都烧 token | 一次索引/分析，N 人复用 + 增量刷新 |
| 失败表现 | 说得像真的 | 明确标"信息缺失/AI 推测" |

---

## 6. 21 天排期

| 日 | 任务 | 硬产出 |
|---|---|---|
| D1–D2 | 骨架 + docker + 拉取/过滤 + **种子库 fixture（8 个快照）** + 证据脚本 | 能起、能看库 |
| D3–D5 | **索引 S1**：chunker + jieba/trigram 双索引 + 输出契约 + 单测 | 检索有结果 |
| D6–D8 | **索引 S2**：symbol/config/dep 解析 + 规则引擎 + boost + 中英扩展 | 符号级命中 |
| D9–D11 | **模板填槽管道**：planner → filler → citations → gaps | 一份合规报告 |
| D12–D14 | 前端：公开库 / 报告 12 卡 / 检索页 / 引用抽屉 / 进度条 | 全流程可点 |
| D15–D16 | 定时器 + sha 去重 + 变更优先 + 「立即执行」+ 分享页 | 保鲜可演示 |
| D17 | `make eval`（Recall@5 / 引用回查 / 槽位命中）+ CI + 部署 | 指标表 |
| D18 | 内测 3 人（用报告接手一个仓库，记卡在第几步） | 反馈 |
| D19–D20 | README（10 分钟复现）+ PDF 技术文档 + 视频 | 三件套 |
| D21 | 干净环境复现演练 + 提交 | 提交截图 |

**D11 闸门**：模板填槽 + 引用回查没跑通 → 砍问答 SSE（只留检索页），保"报告 + 索引 + 定时"三件核心。

---

## 7. 验收指标

| 指标 | 目标 |
|---|---|
| 引用回查率 | 100% |
| 有证据 claim 占比 | ≥85% |
| 槽位命中率 | ≥9/12 |
| Recall@5（60 条标注 query） | ≥0.80 |
| 中文 query 命中率 | ≥7/10 |
| 单仓索引时间（≤40 文件） | ≤20s |
| 单仓分析 token | ≤70k |
| 零 key 可跑（MOCK_LLM=1 + 种子库） | 完整走通 |

---

## 8. 已知风险

| 风险 | 现状与对策 |
|---|---|
| 中文提问 × 英文代码的语义鸿沟 | 实测确认（`docs/search-engine.md` §4）：必做中→英关键词扩展 + 双索引 RRF |
| "详细报告"写成废话 | 模板 12 槽位 + 字数上限 + 引用强制，三道锁 |
| 冷启动（库太小搜不出） | 种子库 8–10 个项目 |
| 定时任务在评委机器上不触发 | 「立即执行一次」按钮 + 任务日志可见 |
| GitHub 限流 | 匿名 60/h 兜底；缓存 snapshot；可选 token |
| 21 天做不完 | D11 闸门降级路径已定 |

---

## 9. 下一步

1. 确认组别（普通本科 = B 组）与缴费，确保 11-18 前能看到提交入口。
2. 建仓 `handover`（Public），首个 commit 只放 README + 骨架 + `scripts/`。
3. D1–D2 先做种子库（8 个开源项目的报告 + 索引快照）——它是演示和复现的地基。
