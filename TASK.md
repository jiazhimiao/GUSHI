# TASK — 2026-05-18

## Next Task: B1 — Industry Rotation Offline Evaluation

### Goal
Evaluate whether industry-level momentum rotation on HS300 produces excess returns
over the HS300 benchmark, using the newly built industry classification map.

### Data Available
- `data/meta/industry_classification.csv` — 280/280 HS300, 65 labels, 39 effective
- `data/raw/HS300_daily.parquet` — daily OHLCV
- `data/raw/index/sh000300_daily.parquet` — HS300 index
- `data/historical_constituents.json` — quarterly constituents

### Allowed
- Build industry portfolios from HS300 constituents (equal-weight within industry)
- Compute industry-level features: momentum, volatility, volume ratio, relative strength
- Monthly rebalance simulation (signal at month-end, entry at T+1 open)
- Compare vs HS300 official index and HS300 equal-weight benchmark
- Generate offline evaluation report

### Not Allowed
- No strategy code changes (`qts/strategies/`)
- No backtest engine integration
- No GA optimization
- No Paper Trading
- No data/raw parquet writes
- No pair trading

### Required Reading (new session)
- `CLAUDE.md`
- `HANDOFF.md`
- `TASK.md` (this file)
- `reports/industry_classification_map_report_20260518.md`
- `reports/industry_classification_source_audit_20260518.md`
- `reports/industry_rotation_data_audit_plan_20260518.md`

### Pass Conditions
- Annualized excess > 3% after costs vs HS300
- Information Ratio > 0.3
- At least 3/5 years outperforming
- Max relative drawdown < 10%
- 2025-2026 does NOT fail (critical, Pair failed here)
- Monthly turnover < 50%

### Stop Conditions
- Excess ≤ 0 or IR < 0.1
- 2025-2026 excess negative
- Only 1-2 years effective
- Industry concentration (top 3 industries > 60% of positions)

### Expected Output
`reports/industry_rotation_offline_eval_202605XX.md`

### Do NOT
- git add / commit / push without explicit confirmation
- Run GA or Paper Trading
- Modify strategy code
