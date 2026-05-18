# quant-multi-agent-workflow

Use this skill for L2/L3 QTS tasks that require decomposition, domain work, QA, safety review, and documentation updates.

## Steps

1. Read `CLAUDE.md`, `TASK.md`, `HANDOFF.md`, `docs/coordination/TASK_LEVELS.md`.
2. Classify task level.
3. Route to appropriate domain agent or checklist:
   - data → qts-data-dev
   - backtest → qts-backtest-dev
   - strategy → qts-strategy-dev
   - risk/execution → qts-risk-execution-dev
   - docs → qts-doc-auditor
4. Require QA review for L2/L3.
5. Require Safety review if secrets, broker, deletion, raw data, or live trading are involved.
6. Update `HANDOFF.md`, `TASK.md`, `EXECUTION.md`, `FILE_INVENTORY.md`, and `docs/coordination/*` as needed.
7. Stop and wait for user confirmation before commit/push.

## Output

```text
Task level:
Agents/checklists used:
Files changed:
Validation commands:
Review decision:
Remaining risks:
Commit recommendation:
```
