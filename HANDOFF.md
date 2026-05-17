# HANDOFF — 2026-05-17 (FINAL)

## Phase: trend_breakout v2 — PAUSED

### Final Status
trend_breakout v2 当前结构已暂停。不升级 Paper Trading。不继续 GA。

### Active Baseline (historical, preserved)
Candidate B: fitness=2.304, ann=7.90%, dd=-8.56%, trades=1137

### Experiment Conclusions (5 rounds, all completed)

**Round 1 — Entry Quality Diagnosis**
- Signal scarcity confirmed: median=1, P25=0, mean=4.1 raw candidates/day
- Rotation 78%, next-day-out 80.7%, false breakout 48.4%
- Root cause: breakout_pct × log(1+vol_boost) score compression

**Round 2 — Entry Quality Single-Factor Filters (A/B/C/D)**
- A (dynamic_topn): no effect (RegimeEngine covers it)
- B (breakout_pct_min 0.5/0.75/1.0): FB 48.5→44.8→43.2→42.0%, overlap +0.3pp max
- C (confirmation_delay 1/2d): disaster (ann negative)
- D (rank_buffer 1.5/2.0/3.0): overlap 40.3-40.6% but ann -62%
- No experiment passes both stop conditions (overlap≥40% AND FB≤35%)

**Round 3 — Signal Count Taxonomy Audit**
- median=40 was a bug: missing constituent filter (wrong CONST_PATH)
- Correct raw candidates: median=1, P25=0, mean≈4.0 (matches original diagnosis)
- Baseline reproduction: tri-metrics (ann/dd/trades) confirmed
- Fitness gap (1.943 vs 2.304) explained: train/val nav split vs independent backtests

**Round 4 — Scoring Redesign Offline Evaluation**
- 5 score variants (baseline, v1-v4) on 8113 raw candidates
- Global decile: FB monotonic (26-75%) but top decile fwd return WORSE
- Daily ranking: no improvement over baseline (all ±0.2pp)
- Within-day score variation too small → ranking noise (94.2% gap≈0)
- No variant passes all 6 conditions

**Round 5 — Day-Level Gate Audit**
- 2027 trading days, 1060 candidate days (52.3%)
- Good day rate (top3 fwd5d>0 AND FB<35%): 36.9%
- RegimeEngine: +9.1pp improvement but misses 254 good days, passes 177 bad
- Best day filter (cc≥3): 41.2% good_day — but top3 fwd5d median still ≈0%
- Day-level gating cannot fix stock-level alpha decay

### Root Cause
1. Stock-level: breakout alpha decays extremely fast (80.7% next-day-out)
2. Within-day: score formula cannot discriminate (all same-day candidates similar)
3. Day-level: even "good days" have barely positive fwd returns
4. RegimeEngine: compresses to 0-1 positions → no diversification

### Verdict
Current trend_breakout v2 alpha structure insufficient.
Do NOT continue parameter optimization, GA, or Paper Trading on this structure.

### Next Phase
Open new alpha research direction. DO NOT modify current trend_breakout v2 further.
