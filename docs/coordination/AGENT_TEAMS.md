# AGENT_TEAMS — Claude Code Agent Teams 使用规则

> 适用范围：仅在 Claude Code 已启用 Agent Teams 时使用。未启用时，仍按 `.claude/agents/` subagent 或主 Agent checklist 执行。

---

## 1. 什么时候启用

Agent Teams 只用于 L2/L3 且并行审查有价值的任务：

```text
数据/schema/复权/成分股口径审计
策略结果异常诊断
回测或研究结果升级前 QA review
多假设并行排查
大模块重构前方案评审
```

不要用于：

```text
L0 状态恢复
单文件小改
线性顺序任务
多人同时编辑同一文件
用户只要求总结/解释
```

---

## 2. 推荐团队结构

| Teammate | 角色 | 默认权限 |
|---|---|---|
| `qts-main-orchestrator` | lead 协调、拆任务、合并结论 | 只读协调 |
| `qts-data-dev` | 数据口径、schema、coverage、未来函数 | 默认只读 |
| `qts-strategy-dev` | 信号、指标、诊断脚本、研究报告 | 仅编辑分配文件 |
| `qts-backtest-dev` | 回测假设、撮合、费用、T+1 | 仅编辑分配文件 |
| `qts-qa-reviewer` | diff、阈值、结论、未来函数审查 | 只读 |
| `qts-safety-reviewer` | token、broker、删除、实盘安全 | 只读 |
| `qts-doc-auditor` | HANDOFF/TASK/EXECUTION/FILE_INVENTORY | 仅编辑文档 |

---

## 3. Lead 必须做的事

```text
1. 先读取 CLAUDE.md / TASK.md / HANDOFF.md / EXECUTION.md。
2. 判断是否真的需要 Agent Teams。
3. 明确每个 teammate 的任务、允许文件、禁止文件。
4. 禁止两个 teammate 同时编辑同一个文件。
5. 要求 reviewer 默认只读。
6. 所有 teammate 结果回传 lead 后，由 lead 统一综合。
7. L2/L3 完成后停止，等待用户确认是否 commit/push。
```

---

## 4. 启动模板

```text
请使用 Agent Teams 执行本轮任务。

Lead 负责：
- 拆任务
- 分配 teammate
- 控制文件所有权
- 汇总结果
- 最终写入决策

请按项目角色创建 teammates：
1. qts-data-dev：只读审计数据/schema/复权/成分股/未来函数风险。
2. qts-strategy-dev：负责策略逻辑、诊断脚本、指标计算；只允许编辑 lead 指定文件。
3. qts-qa-reviewer：只读审查 diff、阈值、报告结论、是否夸大结果。
4. 如涉及 token/broker/删除/data/raw/实盘，再加入 qts-safety-reviewer。
5. 如产生新报告或阶段状态变化，再加入 qts-doc-auditor。

要求：
- 先读取 CLAUDE.md、TASK.md、HANDOFF.md、EXECUTION.md、docs/coordination/AGENT_TEAMS.md。
- 同一文件只能由一个 teammate 拥有。
- reviewer 默认不改文件。
- 所有 teammate 输出必须包含：Files inspected / Findings / Risks / Decision。
- 不要自动进入下一阶段。
```

---

## 5. 文件冲突规则

```text
同一时间，一个文件只能有一个 owner。
Reviewer 不拥有文件，只读。
Doc Auditor 只在 domain agent 完成后更新文档。
Lead 不直接覆盖 teammate 输出，必须先综合差异。
若发生冲突，以用户当前指令和 TASK.md 为准。
```

---

## 6. 禁止 Inline 模拟 + 按任务动态路由

当用户要求 "按 Agent Teams 规则执行" 时，**禁止**以下行为：

```text
❌ 主 session 自己依次扮演 qts-qa-reviewer、qts-safety-reviewer、qts-strategy-dev
❌ 在单线程中写完 QA 审查、Safety 审查、策略分析后声称 "已使用 Agent Teams"
❌ 用 checklist 模拟替代实际 spawn 独立 teammate
```

### 6.1 必须做

```text
✅ Agent(subagent_type="qts-*", ...) spawn 独立 teammate
✅ 或 TeamCreate + Agent(team_name=..., ...) 创建 named teammate
✅ L2/L3 任务默认至少 spawn 2 个独立 teammate；复杂任务可 3-4 个
✅ 每个 teammate 读取自己的文件、输出自己的结论
✅ Lead 汇总各 teammate 结果后统一输出
```

### 6.2 按任务类型动态路由

| 任务类型 | 默认 teammate | 何时加 reviewer |
|---|---|---|
| 研究/策略信号 | qts-strategy-dev + qts-qa-reviewer | 涉及交易升级时加 qts-safety-reviewer |
| 数据/schema/复权/成分股 | qts-data-dev + qts-qa-reviewer | 涉及外部数据源/token/网络拉取时加 qts-safety-reviewer |
| 回测/指标/评估脚本 | qts-backtest-dev + qts-qa-reviewer | 涉及交易结论时加 qts-safety-reviewer |
| 风控/执行/交易接口 | qts-risk-execution-dev + qts-safety-reviewer + qts-qa-reviewer | 默认含 safety |
| 文档/交接/项目状态 | qts-doc-auditor + qts-main-orchestrator | 通常不需要 safety |
| 大型阶段任务 | qts-main-orchestrator (lead) + 2-4 specialists | 按子任务类型选择 |

qts-qa-reviewer 和 qts-safety-reviewer 默认只读。Lead 负责最终写入和汇总。

### 6.3 工具不可用时

如果 Agent 工具不可用，必须显式声明：

```text
⚠️ Agent Teams unavailable in this environment.
Fallback to single-session checklist.
  以下角色仅为 checklist 模拟，不是独立 teammate：
  - qts-qa-reviewer: [simulated by lead]
  - qts-safety-reviewer: [simulated by lead]
  - (按实际任务列出所有模拟角色)
```

---

## 7. 结论格式

Agent Teams 任务结束时，lead 必须输出：

```text
Execution mode: Agent Teams / subagent / single-session checklist
Teammates used:
Files changed:
Files intentionally not changed:
Validation commands:
QA decision:
Safety decision:
Remaining risks:
Next step:
```
