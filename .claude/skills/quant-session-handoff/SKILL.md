# quant-session-handoff

Use this skill before context reset or after a major task.

## Required updates

- `HANDOFF.md`: current phase, completed work, risks, next step.
- `TASK.md`: current only task and acceptance criteria.
- `EXECUTION.md`: commands, validation, failed attempts, commit status.
- `FILE_INVENTORY.md`: new/removed/renamed important files.
- `docs/coordination/TASK_GRAPH.md`: task state.
- `docs/coordination/AGENT_AUDIT_LOG.md`: L2/L3 agent audit entry.

## Handoff prompt

Generate a copyable prompt that tells the next session:

```text
what to read
current git status
current phase
current only task
frozen directions
forbidden actions
```

Never include token or .env content.
