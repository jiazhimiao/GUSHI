# SESSION_HANDOFF

## New Session Prompt Template

```text
这是 QTS A 股量化项目的新会话。请先只读恢复状态，不要改代码。

请读取：
- CLAUDE.md
- TASK.md
- HANDOFF.md
- EXECUTION.md
- README.md
- FILE_INVENTORY.md
- git status
- git log --oneline -5

然后回复：
1. 当前阶段
2. 当前唯一任务
3. 已冻结方向
4. 当前数据资产
5. git 状态
6. 下一步建议

禁止：不改代码、不跑 GA、不进 Paper Trading、不 git add、不 commit。
```

## Agent Teams Startup Prompt Template

```text
这是 QTS A 股量化项目。请使用 Agent Teams，但先只读恢复状态。

Lead 先读取：
- CLAUDE.md
- TASK.md
- HANDOFF.md
- EXECUTION.md
- docs/coordination/AGENT_TEAMS.md

然后按需要创建 teammates：
- qts-data-dev
- qts-strategy-dev
- qts-qa-reviewer
- qts-safety-reviewer（仅涉及 token/broker/删除/data/raw/实盘时）
- qts-doc-auditor（仅需要更新文档/交接时）

要求：
1. 先输出任务等级和 teammate 分工。
2. 明确 allowed files / forbidden files。
3. 禁止多个 teammate 同时编辑同一个文件。
4. reviewer 默认只读。
5. lead 汇总后再决定是否写文件。
6. L2/L3 完成后停止，等待我确认。
```
