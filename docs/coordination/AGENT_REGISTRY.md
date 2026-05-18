# AGENT_REGISTRY

| Agent | Role | Typical Level | Agent Teams 默认权限 |
|---|---|---:|---|
| qts-main-orchestrator | Task decomposition and coordination | L1-L3 | Lead / 只读协调 |
| qts-data-dev | Data sources, schema, storage | L1-L3 | 默认只读；仅在明确授权时改数据脚本/元数据 |
| qts-backtest-dev | Backtest and broker simulation | L2-L3 | 仅编辑 lead 指定的 backtest 文件 |
| qts-strategy-dev | Strategy and offline research | L1-L2 | 仅编辑 lead 指定的 research/script/report 文件 |
| qts-risk-execution-dev | Risk, paper mode, execution | L2-L3 | 仅编辑 lead 指定的 risk/execution 文件 |
| qts-qa-reviewer | QA review | L1-L3 | 只读 reviewer |
| qts-safety-reviewer | Safety review | L2-L3 | 只读 reviewer |
| qts-doc-auditor | Documentation and handoff | L0-L2 | 仅编辑文档和交接文件 |

## Agent Teams 使用说明

`.claude/agents/` 中的 qts-* 定义可同时作为 subagent 和 Agent Teams teammate 角色使用。

启用 Agent Teams 时，lead 必须为每个 teammate 指定：

```text
任务目标
allowed files
forbidden files
是否允许编辑
交付格式
```

Reviewer 类 agent 默认只读，不拥有文件。
