---
name: quant-code-quality-gate
description: Use this skill when modifying Python code or scripts in this quantitative trading project, including diagnostic scripts, data loaders, paper-mode, backtest, broker, replay tools, data update tools, and code that affects experiment results. Enforce small-step implementation, immediate validation, diff self-review, data-source alignment, reliability labeling, and stop-on-risk behavior. Do not use for ordinary discussion, pure HTML reports, handoff-only tasks, or documentation-only edits unless code/scripts are also modified.
---

# Quant Code Quality Gate

## Purpose

Use this skill to prevent late-stage code audits by checking quality while code is being written.

Required workflow:

1. Plan narrowly.
2. Modify one logical unit at a time.
3. Validate immediately.
4. Inspect the diff.
5. Stop when risk appears.
6. End with a compact verification summary.

This project is sensitive to subtle mistakes such as:

- using the wrong market data source;
- allowing non-constituent stocks into paper-mode or replay;
- confusing stale prices, skipped days, and low coverage;
- treating partial data as reliable strategy evidence;
- triggering provider bans with unsafe batch requests;
- missing untracked files because they do not appear in `git diff --stat`.

---

## When to use

Use this skill for:

- Python code changes;
- diagnostic scripts;
- data loaders and update scripts;
- paper-mode logic;
- backtest / replay logic;
- broker / fill / order logic;
- tools that produce NAV, trades, drawdown, reports, or experiment metrics;
- retry, rate-limit, failed-symbol, or circuit-breaker changes;
- preparing code changes for commit.

Do not use this skill for:

- pure discussion;
- pure HTML report generation;
- pure handoff generation;
- Markdown-only edits;
- summarizing existing output without code changes.

If a task includes both code and reports, use this skill for the code portion.

---

## Hard boundaries

Unless explicitly requested, do not modify:

- strategy entry / exit logic;
- backtest engine semantics;
- broker execution semantics;
- GA optimization logic;
- live trading / order execution;
- raw data files;
- raw experiment outputs.

Before editing, classify the change as one of:

- production code;
- diagnostic script;
- data update tool;
- report generator;
- documentation;
- local config;
- temporary scratch.

Do not let a diagnostic-only change become a production trading behavior change.

---

## Pre-change checklist

Before editing code:

```bash
git status --short
git diff --stat
```

Then state:

1. files to modify;
2. change category;
3. whether production behavior changes;
4. whether network access is needed;
5. smallest validation command;
6. whether relevant files are untracked.

If unrelated changes exist, keep the current task narrow.

---

## Small-patch rule

Do not make broad mixed changes.

Use this loop:

1. Edit one file or one logical unit.
2. Run the smallest safe check.
3. Inspect the diff.
4. Continue only if the check passes.

If more than three files are needed, group them by purpose:

- production fix;
- diagnostic tooling;
- data update / network safety;
- report / documentation;
- local config.

---

## Required validation

### Any Python file

Run:

```bash
python -m py_compile <changed_file>
```

Use the smallest no-network smoke test when compile is not enough.

Do not use large replay, backtest, or provider requests as first validation.

---

### Diagnostic scripts

Must check:

- correct input data source;
- no silent hiding of missing data;
- skipped days separate from stale positions;
- low coverage separate from fully skipped days;
- reliability label is present;
- no fallback to unfiltered universe unless explicitly intended.

---

### Data update scripts

Must preserve or add:

- dry-run mode;
- bounded symbol set;
- `--max-symbols` guard;
- rate limit;
- bounded retry count;
- consecutive-failure circuit breaker;
- separate failed and skipped symbols;
- clear provider failure reporting.

Never run all-market pulls unless explicitly requested.

---

### Paper-mode / replay logic

Must verify:

- candidate-day `market_data` matches production paper-mode source;
- `price_map` is built from the same filtered daily data;
- universe filtering is not bypassed;
- non-constituents cannot enter BUY, SELL, positions, NAV, or stale stats;
- stale days, skipped days, and low coverage days are distinct;
- NAV / Max DD / trades are not marked reliable when coverage is insufficient.

Project-specific rule:

- Do not use unfiltered `ctx.bars` as the candidate universe.
- `ctx.bars` may be used for ATR or historical calculations only if production uses it the same way.

---

### Broker / fill logic

Must verify:

- call sites remain compatible;
- default parameters are safe;
- BUY and SELL reasons are explicit;
- `reason` / `exit_reason` does not become NaN;
- order sizing and execution semantics do not change unless requested.

---

## Reliability labels

Any replay or diagnostic output must label reliability.

### Fully reliable

All must be true:

- skipped_days = 0;
- low_coverage_days = 0;
- stale days are zero or fully explained;
- data source matches production;
- no unfiltered universe contamination.

### Partially reliable

Use when:

- no full-day skips occurred;
- one or more low-coverage days exist;
- output validates code flow but not strategy performance.

### Not reliable

Use when:

- skipped_days ratio > 10%;
- severe low coverage affects the target period;
- data source inconsistency exists;
- provider/network failure affected results;
- unfiltered universe contamination exists.

Never present NAV, Max DD, trades, exposure, or holding-period stats as strategy evidence unless reliability is fully reliable.

---

## Network safety

For provider-backed data pulls:

- use dry-run first when possible;
- use `--max-symbols` for smoke tests;
- keep rate limits enabled;
- keep retry count bounded;
- stop after circuit breaker threshold;
- do not continue after signs of IP ban, provider blocking, RST, DNS failure, or persistent timeout;
- separate successful, failed, and skipped symbols.

If provider blocking is suspected, stop and report. Do not keep probing unless explicitly requested.

---

## Git hygiene

After modifications:

```bash
git status --short
git diff --stat
git diff --name-status
```

Remember:

- untracked files do not appear in normal `git diff --stat`;
- inspect untracked files explicitly before staging;
- never use `git add .` in a mixed working tree;
- stage files explicitly.

Do not stage:

- `.claude/hooks/`;
- hook logs;
- secrets or tokens;
- local scratch files;
- temporary backups;
- generated machine artifacts unless intentionally versioned;
- large report directories unless explicitly requested.

Do not push unless explicitly requested.

---

## Stop conditions

Stop and ask before continuing if:

- production trading behavior would change;
- strategy parameters would change;
- backtest engine semantics would change;
- broker execution behavior would change;
- GA logic would change;
- network validation is needed while provider is unstable;
- data coverage is insufficient for strategy evaluation;
- a result looks good because data was skipped or filtered unexpectedly;
- many unrelated files are modified;
- deletion of data, reports, or backups is required;
- a secret or credential appears.

When stopping, state:

1. reason;
2. risk;
3. safest next option;
4. exact approval needed.

---

## Final response format

At the end of a code-changing task, reply with:

1. What changed.
2. Why it changed.
3. Files modified.
4. Validation run.
5. Data completeness status.
6. Reliability label:
   - fully reliable;
   - partially reliable;
   - not reliable;
   - not applicable.
7. Git status summary.
8. Remaining risks.
9. One recommended next step.
