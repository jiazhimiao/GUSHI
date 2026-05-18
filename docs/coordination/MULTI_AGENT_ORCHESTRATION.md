# MULTI_AGENT_ORCHESTRATION

## 路由规则

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

## L2/L3 推荐流程

```text
Main Orchestrator 制定计划
→ Domain Agent 执行
→ QA Reviewer 审查
→ Safety Reviewer（如涉及 token / broker / 删除 / 实盘）
→ Doc Auditor 更新文档
→ 用户确认 commit/push
```

如果 Claude Code 当前环境不启用 subagent，则主 Agent 必须按同等 checklist 手工执行。
