# 报告模板 v1（生成契约）

> 这份模板不是"写作风格要求"，是**生成契约**：每个槽位声明"我需要哪类证据"，检索不到就降级为"信息缺失"，禁止编。
> AI 的唯一工作 = 按槽位去自研检索引擎取证据，再把证据讲成人话。

---

## 1. 模板结构（12 个槽位）

| # | 槽位 ID | 标题（用户看到） | 要回答的问题 | 需要的证据类型 | 检索 query 模板 | 缺失时降级 |
|---|---|---|---|---|---|---|
| 1 | `what` | 它是什么 | 一句话 + 解决什么问题 | README 首段、项目描述、main 文件注释 | `{name} 项目简介 用途` | "仓库未提供项目说明" |
| 2 | `stack` | 技术栈 | 用了什么语言/框架/库 | 依赖清单（go.mod / package.json / requirements.txt）、后缀分布 | `dependencies framework version` | 只列"检测到的语言占比" |
| 3 | `run` | 怎么跑起来 | 本地跑通的命令序列 | README 运行段、Makefile、脚本、`.env.example` | `install run start server command` | 标"未找到可执行启动说明"（红） |
| 4 | `layout` | 目录与模块 | 每个顶层目录负责什么 | 目录树 + 目录内代表文件 | `directory structure module` | 只给树，不解释 |
| 5 | `entry` | 入口与请求链路 | 从哪进、请求怎么走 | main/app 文件、路由注册、中间件 | `main entry router register handler` | 标"入口未识别" |
| 6 | `data` | 数据与存储 | 表/模型/存储方式 | model/schema/migration/sql 文件 | `model schema migration table` | 标"未发现数据层" |
| 7 | `config` | 配置与环境变量 | 有哪些开关、必填哪些 | `.env.example`、config 文件、常量 | `env config variable default` | 标"缺 .env 模板"（红，常见坑） |
| 8 | `integrations` | 外部依赖与集成 | 依赖哪些外部服务 | http client、sdk 调用、docker-compose 服务 | `client sdk api third-party service` | "未发现外部集成" |
| 9 | `traps` | 已知坑与限制 | 接手会踩什么 | 规则引擎命中（硬编码路径、端口写死、缺 env、命令不一致）+ TODO/FIXME | 规则命中项反查 | 空则写"未扫描到明显障碍" |
| 10 | `start_point` | 从哪开始改 | 加一个功能该动哪几个文件 | 路由→handler→service→model 链路 | `{需求关键词} handler service` | 退化为"列出 3 个最常被 import 的文件" |
| 11 | `meta` | 维护信息 | 许可、活跃度、贡献方式 | LICENSE、CONTRIBUTING、最近 commit | `license contributing` | "未声明许可"（黄，需注意合规） |
| 12 | `gaps` | 信息缺失清单 | 哪些槽位证据不足 | 上表降级结果汇总 | — | — |

> 12 个槽位是上限。**每个槽位最多 5 条 claim，每条 claim 最多 120 字**——这是防"详细但没用"的硬约束。

---

## 2. 生成契约（AI 必须输出这个 JSON，不是散文）

```json
{
  "project": {"name": "ginstarter", "one_liner": "Go REST API 脚手架"},
  "sections": [
    {
      "id": "run",
      "title": "怎么跑起来",
      "claims": [
        {"text": "先复制 .env.example，再 go run main.go 启动 HTTP 服务",
         "citations": ["readme.md#L101-L160", "main.go#L1-L45"],
         "confidence": "evidence"}
      ]
    }
  ],
  "gaps": [
    {"section": "config", "reason": "未找到 .env.example，配置项需从 consts 推断"}
  ]
}
```

**服务端校验（不可省）**

```text
P1 结构：每个 section.id 在模板 12 个内；claims ≤5；text ≤120 字
P2 引用：citations 全部能解析到文件且行号区间存在；text 的可疑数字/路径必须在片段内出现
P3 分级：citations 为空 → confidence 强制改 "inferred"（前端灰底 + "AI 推测"标记）
P4 缺失：section 无 claim → 必须写进 gaps，且前端显示为"信息缺失"，不许留空
```

---

## 3. 前端呈现（模板即 UI）

```text
报告页 = 12 个槽位卡片，按"接手顺序"排列：
  它是什么 → 技术栈 → 怎么跑 → 目录 → 入口链路 → 数据 → 配置 → 外部依赖 → 坑 → 从哪开始改 → 维护信息
每张卡：标题 + 1~5 条 claim + 每条 claim 右侧 [E3] 引用角标
点 [E3] → 抽屉显示 path#Lx-Ly 原文高亮；灰底 claim 显示"AI 推测 · 无证据"
底部：信息缺失清单（缺口 = 下一步要问作者的问题）
```

---

## 4. 模板的可测性（答辩用）

| 指标 | 口径 |
|---|---|
| 槽位命中率 | 12 个槽位里有证据支撑的比例（≥9/12 为合格） |
| claim 引用率 | 有 citation 的 claim 占比（目标 ≥85%） |
| 引用回查率 | 引用的 path#Lx-Ly 能回查通过（目标 100%） |
| 模板违反率 | 结构校验失败次数 / 生成次数（目标 <2%） |

> 这套指标让"AI 写得像不像人话"这种主观问题，变成三个可跑的数字。
