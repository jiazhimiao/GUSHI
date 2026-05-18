---
name: quant-code-quality-gate
description: Use this skill when modifying Python code or scripts in this quantitative trading project, including diagnostic scripts, data loaders, paper-mode, backtest, broker, replay tools, data update tools, report-generation scripts, and code that affects experiment results. Enforce small-step implementation, immediate validation, diff self-review, data-source alignment, reliability labeling, network safety, token safety, and stop-on-risk behavior. Do not use for ordinary discussion, pure handoff-only tasks, or Markdown-only documentation edits unless code/scripts are also modified.
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
- mixing qfq / raw / hfq price assumptions;
- allowing non-constituent stocks into paper-mode, replay, or research outputs;
- confusing stale prices, skipped days, and low coverage;
- treating partial data as reliable strategy evidence;
- triggering provider bans with unsafe batch requests;
- leaking provider tokens into scripts, reports, logs, or commits;
- committing temporary research CSVs or local cache files;
- missing untracked files because they do not appear in normal `git diff --stat`.

---

## When to use

Use this skill for:

- Python code changes;
- diagnostic scripts;
- report-generation scripts;
- data loaders and update scripts;
- metadata builders, including `data/meta` asset builders;
- paper-mode logic;
- backtest / replay logic;
- broker / fill / order logic;
- tools that produce NAV, trades, drawdown, reports, or experiment metrics;
- retry, rate-limit, failed-symbol, or circuit-breaker changes;
- preparing code changes for commit.

Do not use this skill for:

- pure discussion;
- Markdown-only edits;
- handoff-only tasks;
- Phase A/B/C documentation restructuring unless Python code or scripts are modified;
- pure HTML report generation when no Python script is changed.

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
- metadata builder;
- report generator;
- documentation;
- local config;
- temporary scratch.

Do not let a diagnostic-only change become a production trading behavior change.

Do not let a metadata task silently become a strategy, backtest, or data-pipeline behavior change.

---

## Pre-change checklist

Before editing code:

```bash
git status --short
git diff --stat
git diff --name-status
```

Then state:

1. files to modify;
2. change category;
3. whether production behavior changes;
4. whether network access is needed;
5. smallest validation command;
6. whether relevant files are untracked;
7. whether any untracked files are unrelated and must be ignored.

If unrelated changes exist, keep the current task narrow and do not stage them.

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
- metadata asset generation;
- report generation;
- documentation;
- local config.

---

## Required validation

### Any Python file

Run:

```bash
python -m py_compile <changed_file>
```

Use the smallest no-network smoke test when compile is not enough.

Do not use large replay, backtest, full-market update, or provider requests as first validation.

---

### Diagnostic scripts

Must check:

- correct input data source;
- explicit adjusted/raw/qfq assumptions;
- no silent hiding of missing data;
- skipped days separate from stale positions;
- low coverage separate from fully skipped days;
- reliability label is present;
- no fallback to unfiltered universe unless explicitly intended;
- sample size and coverage are reported;
- output cannot be mistaken for live-trading evidence.

---

### Data update scripts

Must preserve or add:

- dry-run mode;
- bounded symbol set;
- `--max-symbols` or equivalent guard;
- rate limit;
- bounded retry count;
- consecutive-failure circuit breaker;
- separate failed and skipped symbols;
- clear provider failure reporting;
- no token printing beyond `token exists` or `token_len`.

Never run all-market pulls unless explicitly requested.

Stop when provider blocking is suspected.

---

### Metadata asset builders

Use this section for files such as:

```text
data/meta/industry_classification.csv
```

Rules:

- Metadata assets under `data/meta/` may be versioned only when explicitly approved.
- `data/raw/*` remains protected and must not be overwritten.
- Metadata builder scripts must be reproducible.
- Reports must include source, timestamp, row count, coverage, missing items, and field definitions.
- If using a provider token, do not write it to scripts, reports, CSVs, logs, or committed files.
- It is acceptable to print `token exists` or `token_len`; never print token value.
- If the metadata is incomplete, label it incomplete and do not promote it as a permanent asset.

For industry classification assets, verify at minimum:

- total rows;
- unique symbols;
- HS300 coverage;
- missing HS300 symbols;
- unique industry labels;
- effective industries by minimum stock count;
- source label and update date;
- whether classification is official or provider-specific.

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

### Report-generation scripts

If generating or modifying Python scripts that produce HTML, Markdown, CSV, or JSON reports:

- compile the script;
- run a smallest-input smoke test if possible;
- verify output path is under `reports/` or an explicitly approved path;
- never overwrite raw experiment outputs;
- do not fabricate missing metrics;
- label missing fields clearly;
- ensure report conclusion is evidence-grounded;
- do not claim live-trading readiness unless safety checks are explicitly verified.

For pure HTML tasks with no Python changes, use `quant-html-report` instead.

---

## Reliability labels

Any replay, diagnostic, or research output must label reliability.

### Fully reliable

All must be true:

- skipped_days = 0;
- low_coverage_days = 0;
- stale days are zero or fully explained;
- data source matches production or the intended research source;
- no unfiltered universe contamination;
- no provider failure affected the result;
- no lookahead bias is present.

### Partially reliable

Use when:

- no full-day skips occurred;
- one or more low-coverage days exist;
- output validates code flow but not strategy performance;
- research uses incomplete but explicitly labeled data.

### Not reliable

Use when:

- skipped_days ratio > 10%;
- severe low coverage affects the target period;
- data source inconsistency exists;
- provider/network failure affected results;
- unfiltered universe contamination exists;
- lookahead bias is possible or confirmed;
- stale, incomplete, or biased data drives the conclusion.

Never present NAV, Max DD, trades, exposure, hit rate, or holding-period stats as strategy evidence unless reliability is fully reliable.

---

## Network safety

For provider-backed data pulls:

- use dry-run first when possible;
- use bounded symbol or date ranges for smoke tests;
- keep rate limits enabled;
- keep retry count bounded;
- stop after circuit breaker threshold;
- do not continue after signs of IP ban, provider blocking, RST, DNS failure, persistent timeout, or repeated RemoteDisconnected;
- separate successful, failed, and skipped symbols;
- report provider instability clearly.

If provider blocking is suspected, stop and report. Do not keep probing unless explicitly requested.

---

## Token and secret safety

Provider tokens and credentials must not appear in:

- Python scripts;
- Markdown reports;
- HTML reports;
- CSV / JSON outputs;
- logs;
- git diffs;
- committed files.

Allowed outputs:

```text
token exists
token_len = <length>
```

Not allowed:

```text
token = actual_value
Authorization header value
API key value
.env contents
```

Before staging code or report files after token-related work, run a targeted secret check such as:

```bash
grep -R "token\|TOKEN\|api_key\|password\|sk-" -n <changed_paths> 2>/dev/null
```

If a secret appears, stop and remove it before continuing.

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

- `.env` or secrets;
- `handoff/git_backup/`;
- backup bundles;
- `.claude/hooks/`;
- hook logs;
- local scratch files;
- temporary backups;
- generated machine artifacts unless intentionally versioned;
- intermediate research CSVs such as pair trades, period trades, diagnostics caches, or smoke outputs;
- incomplete industry maps or classification caches;
- large report directories unless explicitly requested;
- `data/raw/*` unless explicitly approved.

Usually commit:

- reproducible scripts;
- concise summary reports;
- approved metadata assets under `data/meta/`;
- documentation updates that match the current project state.

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
- lookahead bias is possible;
- many unrelated files are modified;
- deletion of data, reports, or backups is required;
- a secret or credential appears;
- a temporary research artifact would need to be committed to make results reproducible.

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
8. Untracked file summary.
9. Remaining risks.
10. One recommended next step.
