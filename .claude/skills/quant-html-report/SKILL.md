---
name: quant-html-report
description: Use this skill when the user explicitly asks to generate, update, review, or standardize optional HTML reports for this quantitative trading project, including GA results, backtest results, parameter scans, candidate comparisons, baseline comparisons, experiment handoff HTML, local dashboards, docs/index.html, or browser-readable summaries. Do not use for ordinary Markdown project memory updates unless the user explicitly asks for HTML output.
---

# Quant Optional HTML Report Skill

## Purpose

Use this skill to create **optional browser-readable HTML reports** for the quantitative trading project.

Important project rule:

- Markdown is the canonical project memory.
- HTML is an optional presentation layer for experiment reports, dashboards, and browser-friendly handoffs.
- Do **not** convert the project into HTML-first documentation unless the user explicitly requests that mode.

Canonical Markdown files remain:

```text
README.md          project overview and entry links
CLAUDE.md          compact agent working rules
HANDOFF.md         current project state and session handoff
TASK.md            current task and acceptance criteria
EXECUTION.md       execution log and validation history
FILE_INVENTORY.md  file structure and file purpose map
docs/coordination/ multi-agent coordination documents
reports/           research evidence and experiment reports
```

HTML files may exist as optional review artifacts:

```text
docs/index.html       optional browser dashboard
reports/*.html        optional per-experiment reports
handoff/latest.html   optional browser-readable handoff
```

Do not replace Markdown state files with HTML pointers unless the user explicitly asks for an HTML-first documentation mode.

---

## Core principle

Every HTML report should help the user and future agents answer:

- What was tested?
- What was the baseline?
- Did any candidate beat the baseline?
- Is the improvement stable or likely noise?
- What risks or validation gaps remain?
- What should be done next?

Use direct, evidence-grounded language. Never make weak or noisy results sound successful.

---

## When to use

Use this skill when the user explicitly asks for:

- HTML report generation;
- HTML dashboard generation;
- `docs/index.html` updates;
- `handoff/latest.html` generation;
- browser-readable experiment summaries;
- GA / scan / grid / backtest HTML reports;
- reviewing whether an HTML report matches CSV / JSON / Markdown evidence.

Trigger examples:

- Generate an HTML report for this GA result directory.
- Turn this backtest output into a browser report.
- Make a report comparing baseline and the best candidate.
- Create a report for the Phase 1 single-parameter scan.
- Review whether this HTML report matches the CSV and JSON.
- Create a handoff HTML page before I clear context.
- Update the project dashboard.
- Update `docs/index.html`.

Do **not** use this skill for:

- ordinary Markdown handoff updates;
- ordinary README / TASK / EXECUTION updates;
- Phase A/B/C documentation restructuring;
- strategy logic changes;
- backtest engine changes;
- broker / order / execution changes;
- GA optimization changes;
- live trading integration;
- data pipeline implementation.

If generating or modifying Python report scripts, also apply `quant-code-quality-gate` to the code portion.

---

## Scope boundaries

Allowed:

- Inspect experiment output directories.
- Read CSV, JSON, Markdown, logs, and summary files.
- Generate static HTML reports.
- Generate optional `docs/index.html` project dashboard.
- Generate optional `handoff/latest.html` context handoff page.
- Generate lightweight report scripts if explicitly requested.
- Add or update report templates if explicitly requested.
- Summarize findings from existing experiment outputs.
- Review HTML correctness against raw evidence.

Not allowed unless explicitly requested:

- Modify strategy logic.
- Modify backtest engine logic.
- Modify broker execution semantics.
- Modify GA optimization logic.
- Change experiment results.
- Rerun expensive experiments.
- Delete existing result files.
- Refactor unrelated project code.
- Bloat `CLAUDE.md` with experiment details.
- Replace `README.md`, `HANDOFF.md`, `TASK.md`, `EXECUTION.md`, `FILE_INVENTORY.md`, or `docs/coordination/` with HTML pointers.

---

## Canonical Markdown compatibility

When doing HTML report work:

- Do not automatically edit `CLAUDE.md`.
- Do not automatically edit `TASK.md`.
- Do not automatically edit `EXECUTION.md`.
- Do not automatically edit `FILE_INVENTORY.md`.
- Do not automatically edit `docs/coordination/*`.
- Do not reduce `README.md` to a pointer to `docs/index.html`.
- Do not reduce `HANDOFF.md` to a pointer to `handoff/latest.html`.

If the user asks to update project state after generating HTML, update Markdown canonical files separately and explicitly.

Recommended pattern:

```text
HTML report = browser-readable presentation
Markdown report / HANDOFF / TASK / EXECUTION = canonical project memory
```

---

## Optional Project Dashboard: `docs/index.html`

Generate or update `docs/index.html` only when the user asks for a dashboard or browser project overview.

Suggested dashboard sections:

1. Project header — name, last updated timestamp, git branch.
2. Current stage — concise project status.
3. Current baseline or active research direction.
4. Latest experiment — name, date, verdict.
5. Experiment history — table with links to reports.
6. Data assets — data hash or metadata status where relevant.
7. Known issues — open problems, frozen experiments, risks.
8. Next step — one recommended action.
9. Quick links — README, HANDOFF, TASK, EXECUTION, FILE_INVENTORY, reports.

Dashboard design:

- Static HTML, no external CDN by default.
- Opens directly in a browser.
- Clear typography and table formatting.
- Green/red indicators only when grounded in data.
- Simple enough to understand in 30 seconds.

---

## Optional Handoff HTML: `handoff/latest.html`

Generate `handoff/latest.html` only when the user explicitly asks for HTML handoff or browser-readable handoff.

Required sections:

1. Project stage — one sentence.
2. Current baseline or current active research direction.
3. Completed work this session.
4. Experiment conclusions — passed, failed, frozen, or wait.
5. Open problems.
6. Next task — one recommended next action.
7. Git status summary.
8. New session prompt — copy-paste ready.
9. File inventory — key paths for recovery.

Markdown rule:

- `HANDOFF.md` remains canonical.
- `handoff/latest.html` is an optional browser view.

---

## Experiment HTML Reports: `reports/*.html`

Standard report sections:

1. Title.
2. Experiment path.
3. Generation timestamp.
4. Run configuration.
5. Baseline summary, if available.
6. Best candidate or main result summary.
7. Baseline vs candidate comparison, if applicable.
8. Tables of candidates, buckets, or results.
9. Parameter difference table, if applicable.
10. Equity curve or performance summary, if available.
11. Drawdown / risk summary.
12. Trade count and trade-quality notes.
13. Validation status.
14. Risk notes.
15. Honest conclusion.
16. Next-step recommendation.
17. Raw file inventory.

If a section cannot be filled, include it and mark it as `Unavailable` or `Not applicable`.

---

## GA-specific reporting rules

For GA reports, prioritize:

- baseline fitness;
- best candidate fitness;
- whether any candidate beats baseline;
- best fitness by generation;
- final top candidates;
- convergence behavior;
- whether the population converged back toward baseline;
- whether the best candidate is identical or nearly identical to baseline;
- fitness improvement vs risk deterioration;
- Calmar ratio, drawdown, return, trade count, exposure;
- whether low trade count makes the result unreliable;
- whether improvement is broad or isolated.

If no candidate beats baseline, state this clearly.

If the best candidate only matches baseline, say that the GA reproduced the baseline but did not improve it.

If a candidate has better fitness but worse drawdown, return, trade count quality, or cost robustness, explicitly flag the tradeoff.

---

## Single-parameter scan rules

Prioritize:

- parameter name, baseline value, tested values;
- metric values for each tested point;
- best tested value, delta vs baseline;
- whether the improvement is local, smooth, and stable;
- whether only one isolated value improves;
- whether results justify a two-parameter grid;
- whether results suggest abandoning this parameter;
- whether more samples or longer windows are needed.

Conclusion categories:

- Strong candidate for two-parameter grid.
- Weak but worth retesting.
- No evidence of improvement.
- Likely noise.
- Possible bug or data issue.

Use caution if only one point improves. Do not recommend larger GA runs unless the scan shows evidence of useful signal.

---

## Two-parameter grid rules

Prioritize:

- parameter pair, baseline coordinate, tested grid range;
- best coordinate, local neighborhood stability;
- whether improvement forms a stable region;
- whether the best result is an isolated spike;
- whether the region makes strategy sense;
- whether the result should be validated out-of-sample.

If there is no stable region around the best point, warn about overfitting.

---

## Backtest report rules

Prioritize:

- strategy name, data range, market / symbol / timeframe;
- initial capital if available;
- total return, annual return, max drawdown, Calmar, Sharpe if available;
- win rate, number of trades, average trade return, exposure if available;
- equity curve and drawdown curve if available;
- costs, slippage, turnover, and capacity assumptions;
- known limitations.

Always distinguish between:

- in-sample;
- out-of-sample;
- walk-forward;
- unknown validation status.

---

## Visual design requirements

Prefer:

- plain HTML with embedded CSS;
- optional lightweight JavaScript for sorting/filtering;
- no external CDN by default;
- copy-friendly tables;
- clear typography and section hierarchy;
- simple charts only when underlying data is clear;
- files that open directly in a browser.

Avoid:

- heavy frontend frameworks;
- complex build steps;
- external dependencies unless explicitly requested;
- fake interactivity;
- decorative AI-looking graphics;
- charts that hide raw data;
- unsupported claims;
- overly optimistic wording.

---

## Data integrity rules

Never invent numbers.

Never silently substitute missing data.

Never overwrite raw experiment outputs.

Never delete old reports unless explicitly asked.

When a metric is unavailable, display `Unavailable`.

When a file is missing, list it in a missing-data note.

When data appears inconsistent, stop and report the inconsistency.

HTML reports must be grounded in files, commands, or explicitly provided user data.

---

## Conclusion-writing rules

Every report must include a short, honest conclusion.

Good:

- No candidate exceeded baseline in this run.
- The GA converged back toward the baseline but did not discover a better configuration.
- The best candidate improves fitness, but the improvement may be unreliable because trade count is low.
- The scan shows a stable local region around the tested value, so a two-parameter grid may be justified.
- The result is likely noise and should not be promoted.
- The data source is insufficient, so this direction should remain WAIT.

Bad:

- The model performed excellently.
- The result proves the strategy is profitable.
- This parameter is optimal.
- The GA succeeded.
- The system is ready for live trading.

Only say a system is ready for live trading with explicit evidence for live data validation, broker integration, order safety, risk controls, paper trading, deployment checks, logging, and emergency stop.

---

## Next-step recommendation rules

Every report should end with one grounded next step.

Possible recommendations:

- continue single-parameter scan;
- expand to two-parameter grid;
- rerun with larger sample;
- validate out-of-sample;
- investigate possible data issue;
- reject this parameter direction;
- freeze current baseline;
- prepare paper trading integration;
- improve data source coverage;
- build a reusable data asset;
- do not proceed to live trading yet.

---

## Live trading caution

HTML reports must not imply live-trading readiness unless all required safety checks are explicitly verified.

Flag missing safety layers:

- live market data validation;
- broker API integration;
- order sizing;
- max position;
- stop-loss / kill-switch;
- duplicate order prevention;
- paper trading validation;
- logging / audit trail;
- error handling;
- reconnection behavior;
- manual emergency stop.

---

## Review checklist

Before finishing any HTML report task:

- Can the report be opened locally in a browser?
- Are all numbers grounded in existing files?
- Is baseline comparison present if baseline data exists?
- Are missing fields clearly marked?
- Is the conclusion honest?
- Is the next step actionable?
- Did we avoid modifying unrelated project files?
- Did we preserve Markdown canonical project memory?
- Did we avoid claiming live-trading readiness without evidence?
- Did we preserve raw experiment outputs?
- If Python report scripts changed, did `quant-code-quality-gate` apply?

---

## Final response format

At the end of an HTML report task, reply with:

1. What was generated or updated.
2. Source files used.
3. Output HTML path(s).
4. Validation performed.
5. Any missing data or caveats.
6. Honest conclusion.
7. One recommended next step.
8. Git status summary.
