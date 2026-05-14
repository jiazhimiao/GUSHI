---
name: quant-html-report
description: Use this skill when the user asks to generate, update, review, or standardize HTML reports for this quantitative trading project, including GA results, backtest results, single-parameter scans, candidate comparisons, baseline comparisons, parameter sensitivity analysis, experiment handoff reports, and project dashboard updates. Also use when the user talks about "HTML-first documentation", "project dashboard", "docs/index.html", or "handoff HTML" in the context of this project.
---

# Quant HTML-First Documentation Skill

## HTML-first documentation structure

This project uses HTML as the primary documentation format. The structure is:

```
README.md              ← minimal entry: project name, one-liner, link to docs/index.html
CLAUDE.md              ← minimal hard rules for agents (must not bloat)
HANDOFF.md             ← optional, minimal pointer to handoff/latest.html
docs/
  index.html           ← project dashboard (baseline, latest experiments, status)
reports/
  *.html               ← per-experiment reports (GA, backtest, scan, grid)
handoff/
  latest.html          ← latest context handoff (for new session recovery)
  YYYY-MM-DD.html      ← archived handoff snapshots
```

Markdown files (`README.md`, `CLAUDE.md`, `HANDOFF.md`) are kept minimal. Detailed context, evidence, and interactive review belong in HTML files.

## Core principle

- **Markdown** is for project memory and hard rules. Keep it short.
- **HTML** is for experiment evidence, interactive review, and project state.
- **CSV / JSON** is for raw data. Never edit manually.
- **Python** is for reproducible report generation. Prefer scripts over hand-edited HTML.

Every HTML page should help the user and future agents answer:

- What was tested?
- What was the baseline?
- Did any candidate beat the baseline?
- Is the improvement stable or likely noise?
- What risks or validation gaps remain?
- What should be done next?

## Scope boundaries

Allowed:

- Inspect experiment output directories
- Read CSV, JSON, Markdown, logs, and summary files
- Generate static HTML reports
- Generate `docs/index.html` project dashboard
- Generate `handoff/latest.html` context handoff pages
- Generate lightweight report scripts if explicitly requested
- Add or update report templates if explicitly requested
- Summarize findings from existing experiment outputs
- Review report correctness against raw data
- Update README.md only to point to docs/index.html
- Update HANDOFF.md only to point to handoff/latest.html

Not allowed unless explicitly requested:

- Modify strategy logic
- Modify backtest engine logic
- Modify GA optimization logic
- Change experiment results
- Rerun expensive experiments
- Delete existing result files
- Refactor unrelated project code
- Bloat CLAUDE.md with experiment details

---

## 1. Project Dashboard: `docs/index.html`

The dashboard is the single entry point for understanding the project state. Generate or update it when:

- A new experiment completes
- The baseline changes
- A handoff is requested
- The user says "update the dashboard" or "update docs/index.html"

### Dashboard sections

1. **Project header** — name, last updated timestamp, git branch
2. **Current baseline** — key metrics (total_return, max_drawdown, calmar, trades), data hash, verification command
3. **Latest experiment** — name, date, top result, whether it beat baseline
4. **Experiment history** — table of recent experiments with links to `reports/*.html`
5. **Active parameters** — current default switches (pullback_entry, rank_buffer, use_dow_filter)
6. **Known issues** — open problems, frozen experiments, risks
7. **Next step** — one recommended action
8. **Quick links** — CLAUDE.md, HANDOFF.md, latest handoff HTML, data directories

### Dashboard design

- Static HTML, no CDN, opens directly in browser
- Clear typography, good table formatting
- Green/red indicators for baseline comparison
- Links to all report files
- Simple enough to read in 30 seconds

---

## 2. Handoff Pages: `handoff/*.html`

### `handoff/latest.html`

When the user says "prepare for context clear" or "create handoff", generate or update this file. It replaces the old Markdown-only HANDOFF.md with a richer browser-readable format.

Required sections:

1. **Project stage** — one sentence
2. **Current baseline** — metrics table + data hash + verification command
3. **Completed work this session** — bullet list of what was done and verified
4. **Experiment conclusions** — which experiments passed, failed, or are frozen
5. **Open problems** — what is still unresolved
6. **Next task** — the single recommended next action
7. **Git status summary** — modified files, untracked files
8. **New session prompt** — copy-paste ready prompt block for the next session
9. **File inventory** — paths of key files for session recovery

### Archival

After updating `latest.html`, optionally copy it to `handoff/YYYY-MM-DD.html` for history.

### HANDOFF.md

Keep it minimal:

```markdown
# HANDOFF

HTML-first project. See handoff/latest.html for full context.
```

---

## 3. Experiment Reports: `reports/*.html`

These follow the original quant-html-report rules. Keep all existing rules intact.

### Standard report sections

1. Title
2. Experiment path
3. Generation timestamp
4. Run configuration
5. Baseline summary
6. Best candidate summary
7. Baseline vs best candidate comparison
8. Top candidates table
9. Parameter difference table
10. Equity curve or performance summary
11. Drawdown / risk summary
12. Trade count and trade-quality notes
13. Validation status
14. Risk notes
15. Honest conclusion
16. Next-step recommendation
17. Raw file inventory

If a section cannot be filled, include it and mark as unavailable.

---

## 4. GA-specific reporting rules

For GA reports, prioritize:

- Baseline fitness
- Best candidate fitness
- Whether any candidate beats baseline
- Best fitness by generation
- Final top candidates
- Candidate convergence behavior
- Whether the population converged back toward baseline
- Whether the best candidate is identical or nearly identical to baseline
- Fitness improvement vs risk deterioration
- Calmar ratio changes, drawdown changes, return changes, trade count changes
- Whether low trade count makes the result unreliable
- Whether the improvement is broad or isolated

If no candidate beats baseline, state this clearly. Do not make weak results sound successful.

If the best candidate only matches baseline, say that the GA reproduced the baseline but did not improve it.

If a candidate has better fitness but worse drawdown, return, or trade count quality, explicitly flag the tradeoff.

---

## 5. Single-parameter scan rules

Prioritize:

- Parameter name, baseline value, tested values
- Metric values for each tested point
- Best tested value, delta vs baseline
- Whether the improvement is local, smooth, and stable
- Whether only one isolated value improves
- Whether results justify a two-parameter grid
- Whether results suggest abandoning this parameter
- Whether more samples or longer backtest windows are needed

Conclusion categories:

- Strong candidate for two-parameter grid
- Weak but worth retesting
- No evidence of improvement
- Likely noise
- Possible bug or data issue

Use caution if only one point improves. Do not recommend larger GA runs unless the scan shows evidence of useful signal.

---

## 6. Two-parameter grid rules

Prioritize:

- Parameter pair, baseline coordinate, tested grid range
- Best coordinate, local neighborhood stability
- Whether improvement forms a stable region
- Whether the best result is an isolated spike
- Whether the region makes strategy sense
- Whether the result should be validated out-of-sample

If there is no stable region around the best point, warn about overfitting.

---

## 7. Backtest report rules

Prioritize:

- Strategy name, data range, market / symbol / timeframe
- Initial capital if available
- Total return, max drawdown, calmar ratio, sharpe ratio if available
- Win rate, number of trades, average trade return, exposure if available
- Equity curve, drawdown curve if available
- Any known limitations

Always distinguish between: in-sample, out-of-sample, walk-forward, unknown validation status.

---

## 8. Visual design requirements

Prefer:

- Plain HTML, embedded CSS
- Optional lightweight JavaScript for sorting or filtering
- No external CDN by default
- Tables that are easy to copy
- Clear typography, section hierarchy, good spacing
- Sticky or visible summary area if useful
- Simple charts only when the underlying data is clear
- Report files that open directly in a browser

Avoid:

- Heavy frontend frameworks, complex build steps
- External dependencies unless explicitly requested
- Fake interactivity, AI-looking decoration, decorative 3D illustrations
- Charts that hide the raw data
- Unsupported claims, overly optimistic wording

---

## 9. Preferred file layout

```
docs/
  index.html                              ← project dashboard

reports/
  ga_pilot_YYYY-MM-DD.html               ← GA pilot report
  phase1_scan_YYYY-MM-DD.html            ← Phase 1 scan report
  phase1b_scan_YYYY-MM-DD.html           ← Phase 1b scan report
  phase2_grid_YYYY-MM-DD.html            ← Phase 2 grid report (future)

handoff/
  latest.html                             ← latest context handoff
  YYYY-MM-DD.html                        ← archived snapshots

scripts/
  generate_ga_html_report.py
  generate_scan_html_report.py
  generate_dashboard.py
  generate_handoff_html.py
```

Do not create this full structure unless needed. Start with a simple script per report type.

```
python scripts/generate_dashboard.py
python scripts/generate_ga_html_report.py <experiment_dir>
python scripts/generate_handoff_html.py
```

---

## 10. Data integrity rules

Never invent numbers. Never silently substitute missing data. Never overwrite raw experiment outputs. Never delete old reports unless explicitly asked. When a metric is unavailable, display `Unavailable`. When a file is missing, list it in a missing-data note. When data appears inconsistent, stop and report the inconsistency.

---

## 11. Conclusion-writing rules

Every report must include a short, honest conclusion. Use direct language.

Good:

- No candidate exceeded baseline in this run.
- The GA converged back toward the baseline but did not discover a better configuration.
- The best candidate improves fitness, but the improvement may be unreliable because trade count is low.
- The scan shows a stable local region around the tested value, so a two-parameter grid may be justified.
- The result is likely noise and should not be promoted to the next phase.

Bad:

- The model performed excellently.
- The result proves the strategy is profitable.
- This parameter is optimal.
- The GA succeeded.
- The system is ready for live trading.

Only say a system is ready for live trading with explicit evidence for live data, order safety, risk controls, paper trading, and deployment checks.

---

## 12. Next-step recommendation rules

Every report should end with one recommended next step grounded in the report data. Options:

- Continue single-parameter scan
- Expand to two-parameter grid
- Rerun with larger sample or more generations
- Validate out-of-sample
- Investigate possible data issue or bug
- Reject this parameter direction
- Freeze current baseline
- Prepare paper trading integration
- Do not proceed to live trading yet

---

## 13. Live trading caution

HTML reports must not imply live trading readiness unless all required safety checks are explicitly verified. Flag missing safety layers: live market data validation, broker API integration, order sizing, max position, stop-loss/kill-switch, duplicate order prevention, paper trading validation, logging/audit trail, error handling, reconnection behavior, manual emergency stop.

---

## 14. Review checklist

Before finishing any report-related task:

- Can the report be opened locally in a browser?
- Are all numbers grounded in existing files?
- Is baseline comparison present if baseline data exists?
- Are missing fields clearly marked?
- Is the conclusion honest?
- Is the next step actionable?
- Did we avoid modifying unrelated project files?
- Did we avoid claiming live-trading readiness without evidence?
- Did we preserve raw experiment outputs?

---

## 15. Trigger examples

Should trigger:

- Generate an HTML report for this GA result directory.
- Turn this backtest output into a browser report.
- Make a report comparing baseline and the best candidate.
- Create a report for the Phase 1 single-parameter scan.
- Review whether this HTML report matches the CSV and JSON.
- Create a handoff report before I clear context.
- Summarize this experiment in an interactive local HTML page.
- Show which candidates beat baseline.
- Update the project dashboard.
- Update docs/index.html.
- Create a handoff HTML page.
- Generate the handoff/latest.html file.

Should NOT trigger:

- Modify the strategy entry logic.
- Fix the backtest engine.
- Optimize GA mutation.
- Connect to broker API. Place real trades.
- Refactor the project.
- Update README.md for non-documentation reasons.
- Update CLAUDE.md for non-documentation reasons.
