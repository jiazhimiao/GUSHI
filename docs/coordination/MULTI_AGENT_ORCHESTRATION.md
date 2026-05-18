# MULTI_AGENT_ORCHESTRATION

## 1. 路由规则

| 任务 | Agent |
|---|---|
| 协调、拆任务 | `qts-main-orchestrator` |
| 数据源、schema、行业分类 | `qts-data-dev` |
| 回测和撮合 | `qts-backtest-dev` |
| 策略和因子研究 | `qts-strategy-dev` |
| 风控和执行 | `qts-risk-execution-dev` |
| QA 审查 | `qts-qa-reviewer` |
| 安全审查 | `qts-safety-reviewer` |
| 文档和交接 | `qts-doc-auditor` |

---

## 2. 执行模式选择

| 模式 | 使用场景 | 说明 |
|---|---|---|
| Single-session checklist | L0/L1、小范围顺序任务 | 主 Agent 按 checklist 执行 |
| Subagent | 单一领域子任务，需要隔离上下文 | 子任务完成后向主 Agent 汇报 |
| Agent Teams | L2/L3、多领域并行审查或独立排查 | 多个 Claude Code session，由 lead 协调 |

Agent Teams 不是默认模式。只有当并行审查能降低风险或提高效率时才启用。

---

## 3. L2/L3 推荐流程

```text
Main Orchestrator 制定计划
→ 判断是否需要 Agent Teams
→ Domain Agent / Teammate 执行
→ QA Reviewer 审查
→ Safety Reviewer（如涉及 token / broker / 删除 / 实盘）
→ Doc Auditor 更新文档
→ 用户确认 commit/push
```

如果 Claude Code 当前环境不启用 subagent 或 Agent Teams，则主 Agent 必须按同等 checklist 手工执行。

---

## 4. Agent Teams 分工规则

启用 Agent Teams 时：

```text
Lead 负责拆任务、分配 teammate、控制文件所有权、合并结论
Domain teammate 只处理分配范围
Reviewer teammate 默认只读
Safety teammate 默认只读
Doc teammate 只在阶段结束后更新文档
```

同一文件只能由一个 teammate 编辑。若一个任务涉及同一文件的多方意见，先由 reviewer 输出建议，再由 lead 或指定 owner 统一修改。

---

## 5. 启动提示模板

```text
请使用 Agent Teams 执行本轮任务。

先读取：
- CLAUDE.md
- TASK.md
- HANDOFF.md
- EXECUTION.md
- docs/coordination/AGENT_TEAMS.md

请按项目角色创建 teammates：
- qts-data-dev：数据/schema/复权/成分股/未来函数，默认只读
- qts-strategy-dev：策略逻辑、诊断脚本、指标计算，仅编辑 lead 指定文件
- qts-qa-reviewer：只读审查 diff、阈值、报告结论、是否夸大
- qts-safety-reviewer：仅在 token/broker/删除/data/raw/实盘时加入
- qts-doc-auditor：仅在需要更新文档/交接时加入

要求：
- 明确每个 teammate 的 allowed files / forbidden files
- 禁止多人同时编辑同一文件
- 所有 teammate 输出必须回传 lead
- lead 最终综合，不自动进入下一阶段
```
