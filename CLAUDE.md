# CLAUDE.md — QTS Agent 工作宪法

> 本文件是 Claude Code 在本项目中的长期工作规则，不是项目百科。  
> 当前项目状态以 `HANDOFF.md` / `TASK.md` / `EXECUTION.md` 为准。  
> 文件结构以 `FILE_INVENTORY.md` 为准。详细研究结论以 `reports/` 为准。

---

## 0. 项目性质

QTS 是 A 股量化交易系统，覆盖：数据、因子、策略、回测、风控、模拟盘、看板和未来可能的实盘接口。

所有 Agent 必须遵守：

```text
谨慎
可验证
可回滚
可解释
不夸大收益
不绕过风控
不为了回测收益修改交易假设
```

---

## 1. 必读文件顺序

每个新会话或复杂任务开始前读取：

```text
CLAUDE.md
TASK.md
HANDOFF.md
EXECUTION.md
README.md
FILE_INVENTORY.md（按需）
docs/coordination/PROJECT_INDEX.md（多 Agent 任务必读）
docs/coordination/TASK_LEVELS.md（多 Agent 任务必读）
docs/coordination/AGENT_TEAMS.md（启用 Agent Teams 时必读）
```

如果这些文件之间存在冲突，优先级为：

```text
用户当前指令 > TASK.md > HANDOFF.md > EXECUTION.md > CLAUDE.md > README.md > 历史 reports
```

---

## 2. 当前状态入口

不要在本文件寻找最新研究结论。当前状态请读取：

```text
HANDOFF.md      当前阶段、已完成、风险、下一步
TASK.md         当前唯一任务、验收标准、禁止事项
EXECUTION.md    最近执行记录、命令、验证结果
FILE_INVENTORY.md 文件结构和重要文件用途
reports/        历史研究报告和证据
```

---

## 3. 任务等级

| 等级 | 定义 | 是否可直接改文件 | Review 要求 |
|---|---|---:|---|
| L0 | 只读查询、状态恢复、解释 | 否 | 无 |
| L1 | 小型文档/脚本修正，低风险 | 可，需说明 | 自查 |
| L2 | 影响数据、回测、研究结果、重要文档体系 | 先计划后执行 | QA review |
| L3 | 影响实盘、安全、资金、凭证、删除、交易假设 | 必须用户确认 | QA + Safety review |

L2/L3 应优先使用 `.claude/agents/` 的 domain agent；若任务适合并行审查且 Claude Code 已启用 Agent Teams，可按 `docs/coordination/AGENT_TEAMS.md` 创建 named teammates。若当前环境不启用 subagent / Agent Teams，则 Main agent 必须按同等 checklist 执行。

---

## 4. 默认工作流

```text
1. 读取当前任务和状态文件
2. 判断任务等级
3. 输出计划和影响范围
4. 只修改任务允许范围内的文件
5. 运行最小验证
6. 输出 diff/stat/风险/下一步
7. 等用户确认后再 commit/push
```

L2/L3 任务禁止一边探索一边大范围改代码。先做只读审计，再执行。

---

## 5. 多 Agent 路由

| 任务类型 | 推荐 agent |
|---|---|
| 任务拆解、协调、边界控制 | `qts-main-orchestrator` |
| 数据源、parquet、schema、行业/事件数据 | `qts-data-dev` |
| 回测引擎、broker、撮合、费用、T+1 | `qts-backtest-dev` |
| 策略、因子、offline research | `qts-strategy-dev` |
| 风控、仓位、模拟盘、执行报告 | `qts-risk-execution-dev` |
| diff 审查、测试、未来函数、口径 | `qts-qa-reviewer` |
| token、实盘、危险命令、删除 | `qts-safety-reviewer` |
| 文档、交接、任务图、审计日志 | `qts-doc-auditor` |

详见：

```text
docs/coordination/MULTI_AGENT_ORCHESTRATION.md
docs/coordination/AGENT_TEAMS.md
```

### Agent Teams 使用边界

Agent Teams 是可选执行模式，不是默认模式。仅当 L2/L3 任务存在并行审查、独立排查或多模块分工价值时启用。

必须遵守：

```text
Lead 统一拆任务和合并结论
Teammates 使用 .claude/agents/ 中的 qts-* 角色定义
Teammate 不依赖 lead 当前聊天历史，必须读取任务所需文件
同一文件不得由多个 teammate 同时编辑
Reviewer 默认只读
最终写入和阶段推进由 lead 负责
```

禁止把 Agent Teams 当作自动升级机制。指标 PASS 不等于策略可交易，也不等于可进入 Paper Trading。

### Agent Teams 强制执行规则

当用户明确说 "按 Agent Teams 规则执行" 或任务为 L2/L3 且需要多角色审查时：

```text
1. 必须实际 spawn 独立 teammate：
     - TeamCreate + Agent(team_name=..., subagent_type="qts-*")，或
     - Agent(subagent_type="qts-*") 直接 spawn 子 agent

2. 禁止只在主 session 内 inline 模拟 qts-* 角色后声称已使用 Agent Teams。

3. L2/L3 任务默认至少 spawn 2 个独立 teammate；复杂任务可 spawn 3-4 个。

4. 按任务类型动态选择 agent：

   研究/策略信号：
     qts-strategy-dev + qts-qa-reviewer
     涉及交易升级时加 qts-safety-reviewer

   数据/schema/复权/成分股：
     qts-data-dev + qts-qa-reviewer
     涉及外部数据源/token/网络拉取时加 qts-safety-reviewer

   回测/指标/评估脚本：
     qts-backtest-dev + qts-qa-reviewer
     涉及交易结论时加 qts-safety-reviewer

   风控/执行/交易接口：
     qts-risk-execution-dev + qts-safety-reviewer + qts-qa-reviewer

   文档/交接/项目状态：
     qts-doc-auditor + qts-main-orchestrator
     通常不需要 safety，除非文档会改变交易升级状态

   大型阶段任务：
     qts-main-orchestrator 作为 lead
     再按任务选择 2-4 个 specialist

5. qts-qa-reviewer 和 qts-safety-reviewer 默认只读。

6. qts-main-orchestrator / lead 负责最终写入和汇总。

7. 如果 Agent 工具不可用，必须显式说明：
     - Agent Teams unavailable in this environment
     - Fallback to single-session checklist
     - 列明哪些角色只是 checklist 模拟，不是独立 teammate
```

---

## 6. Git 规则

必须遵守：

```text
不要 git add .
不要擅自 commit
不要擅自 push
不要提交 .env / token / key / password
不要提交 handoff/ 或 backup bundle
不要提交临时 CSV / debug / smoke 报告
不要提交大型 raw 数据，除非它已经是明确 tracked 的项目资产
```

提交前必须输出：

```bash
git status --short
git diff --stat
git diff --cached --stat
```

commit 前必须列出允许 staged 的文件清单。push 失败时不要 reset，不要重复 commit。

---

## 7. 数据规则

数据任务必须说明：

```text
数据源
时间范围
股票池
复权口径：raw / qfq / hfq
字段 schema
缺失和异常处理
是否存在未来函数
是否写 data/raw
是否可复现
```

禁止：

```text
混用 raw/qfq/hfq 但不标注
用未来成分股/未来行业分类做历史交易结论但不说明风险
覆盖 raw parquet
把 token 写入代码、报告、日志、CSV
```

行业、事件、成分股数据必须先做数据审计，再进入策略研究。

---

## 8. 回测和交易假设规则

不得为了提高收益修改：

```text
T+1
手续费
印花税
滑点
涨跌停
停牌
ST 过滤
买入价格口径
卖出价格口径
可交易性过滤
```

研究信号使用 T 日收盘计算时，默认真实交易口径为 T+1 open 入场。若使用其他口径，必须明确说明并作为敏感性分析。

---

## 9. 策略研究规则

策略研究必须先 offline 验证，再考虑回测接入。

必须检查：

```text
分年稳定性
样本外 / validation / test
成本敏感度
回撤和 MAE
换手率
样本量
是否依赖单一年份
是否有未来函数
```

失败结论必须保留，不允许把弱信号包装成 alpha。研究失败应写入 `reports/` 和 `HANDOFF.md`。

---

## 10. 实盘和安全规则

默认禁止：

```text
真实下单
连接真实券商 API
自动开启 live trading
保存 broker 凭证
绕过风控
删除 raw 数据
执行破坏性命令
```

任何 L3 行为必须先获得用户明确确认，并由 `qts-safety-reviewer` 审查。

---

## 11. 测试和验证规则

长任务先冒烟：

```text
小时间段
少股票
少参数
只读/verify-only 模式
```

常用验证：

```bash
python -m py_compile <changed_py_files>
pytest -q
python scripts/check_future_leak.py
```

无法运行测试时必须说明原因，不允许声称已通过。

---

## 12. 文档更新规则

阶段结束必须同步：

```text
HANDOFF.md      当前状态和下一步
TASK.md         当前唯一任务
EXECUTION.md    执行记录
FILE_INVENTORY.md 新增/删除/重命名重要文件时更新
docs/coordination/* 多 Agent 任务时更新
reports/        研究报告和证据
```

README 只做项目总览和入口链接，不放长篇实验细节。

---

## 13. 停止规则

完成一个 L2/L3 子任务后停止，输出：

```text
做了什么
改了哪些文件
运行了哪些验证
结果是否通过
剩余风险
是否建议 commit
下一步建议
```

不要自动进入下一个研究方向，除非用户明确要求。
