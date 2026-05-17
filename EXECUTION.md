# EXECUTION — 2026-05-17 (FINAL)

## Completed: Full trend_breakout v2 Diagnostic Cycle

### Code Changes (this session, uncommitted)
- `qts/strategies/trend_breakout.py`: +breakout_pct_min, +confirmation_days, +dynamic_top_n,
  sell_rank_multiplier int→float, +_signal_log, +reset(), +_log_signal(),
  +_process_confirmations(), int(sell_top_n) fix
- `scripts/run_entry_experiment.py` (new): unified experiment runner
- `scripts/diagnose_entry_quality.py` (new): entry signal diagnosis + FB rate
- `scripts/audit_entry_experiments.py` (new): 4-task post-experiment audit
- `scripts/taxonomy_signal_count.py` (new): L0-L10 signal chain taxonomy
- `scripts/evaluate_scoring_redesign.py` (new): offline scoring evaluation (5 variants)
- `scripts/day_level_gate_audit.py` (new): day-level gate analysis

### Bugs Found & Fixed
- CONST_PATH: historical_constituents.json at wrong path → audit median=40 was wrong
- sell_rank_multiplier: int→float for rank_buffer experiments
- top_n: diagnose default 15→10 (Candidate B uses 10)
- top20% overlap: set(symbols) bug → row-level join (100% sanity check)

### 5-Round Diagnostic Cycle

| Round | Topic | Key Finding |
|-------|-------|-------------|
| 1 | Entry quality diagnosis | Signal scarcity, 48.4% FB, 78% rotation |
| 2 | 9 single-factor experiments | A/B/C/D all fail stop conditions |
| 3 | Taxonomy audit | median=40 bug found & fixed; correct median=1 |
| 4 | Scoring redesign | 5 variants fail offline; within-day discrimination ≈0 |
| 5 | Day-level gate audit | Good day=36.9%; day gates add ≤10pp max |

### Final Verdict
trend_breakout v2 alpha structure PAUSED.
Stock-level alpha decay (80.7% next-day-out) dominates all improvements.
Do NOT GA. Do NOT Paper Trading. Open new alpha research.

### Not Modified
broker, engine, data pipeline, GA optimizer
