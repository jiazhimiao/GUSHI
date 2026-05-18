# quant-multi-agent-workflow

Use this skill for L2/L3 QTS tasks that require decomposition, domain work, QA, safety review, documentation updates, or Agent Teams coordination.

## Steps

1. Read `CLAUDE.md`, `TASK.md`, `HANDOFF.md`, `docs/coordination/TASK_LEVELS.md`.
2. Classify task level.
3. Decide execution mode:
   - L0/L1 → single-session checklist unless user asks otherwise
   - L2 → subagent or Agent Teams when parallel review adds value
   - L3 → user confirmation + QA + Safety, Agent Teams only if explicitly useful
4. If Agent Teams is used, read `docs/coordination/AGENT_TEAMS.md` and assign teammate file ownership.
5. Route to appropriate domain agent or checklist:
   - data → qts-data-dev
   - backtest → qts-backtest-dev
   - strategy → qts-strategy-dev
   - risk/execution → qts-risk-execution-dev
   - docs → qts-doc-auditor
6. Require QA review for L2/L3.
7. Require Safety review if secrets, broker, deletion, raw data, or live trading are involved.
8. Update `HANDOFF.md`, `TASK.md`, `EXECUTION.md`, `FILE_INVENTORY.md`, and `docs/coordination/*` as needed.
9. Stop and wait for user confirmation before commit/push.

## Agent Teams constraints

```text
Lead owns final synthesis and write decisions.
Reviewer teammates are read-only.
Same file cannot be edited by multiple teammates.
Teammates must not rely on lead conversation history; they must read assigned files.
```

## Output

```text
Task level:
Execution mode:
Agents / teammates used:
File ownership:
Files changed:
Validation commands:
Review decision:
Safety decision:
Remaining risks:
Commit recommendation:
```
