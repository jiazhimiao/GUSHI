# B2 — Industry Multi-Factor Ranking Research Plan

> 2026-05-19 | Status: PLAN | 只读设计，未实现

---

## 1. B1 Lessons → B2 Design Constraints

| B1 Finding | B2 Response |
|---|---|
| Single momentum 0/24 EW pass | Multi-factor composite scoring |
| Top 10% months = 113.6% excess | Require factor-level time stability |
| MinStk=5 RC drops to 0.24 | Target MinStk >= 5 viability |
| AW amplifies, EW signal matters | Keep EW signal foundation, test holding separately |
| Industry rotation alpha exists but thin | Broaden signal base instead of abandoning |

### B2 Core Hypothesis

**Single industry momentum is too thin. A composite of 2-3 orthogonal factors produces a more stable cross-sectional industry ranking, reducing time concentration and small-industry dependency.**

---

## 2. Three Candidate Scoring Versions

### B2-A: Momentum + Low Volatility

**Rationale**: Momentum captures trend; low volatility penalizes crowded/overbought industries. The two factors are negatively correlated in most regimes — when momentum chases hot sectors, low vol provides a brake.

**Factor 1 — Industry Momentum (50% weight)**:
```text
ind_ret_60d = industry EW cumulative return over past 60 trading days
Cross-sectional rank (0-1), higher = better
```

**Factor 2 — Industry Low Volatility (50% weight)**:
```text
ind_vol_60d = std(ind_daily_ret) over past 60 days, annualized
Cross-sectional rank (0-1), LOWER vol = higher rank
```

**Score**: `0.5 × rank(momentum) + 0.5 × rank(low_vol)`

**Future function risk**: None — both factors use T-day close data, entry at T+1 open.

**Hypothesis**: Momentum + Low Vol = better risk-adjusted returns than pure momentum. Low vol should reduce the drawdown spikes that caused B1's cap_20 RC collapse.

---

### B2-B: Momentum + Drawdown Recovery

**Rationale**: Industries that have recovered well from recent drawdowns may be in early trend stages. This captures "turnaround momentum" — different from pure price momentum.

**Factor 1 — Industry Momentum (50% weight)**:
```text
ind_ret_60d = as above
```

**Factor 2 — Drawdown Recovery Ratio (50% weight)**:
```text
max_dd_120d = max drawdown from peak over past 120 days
recovery_ratio = (current_price - min_price_120d) / (peak_price_120d - min_price_120d)
Cross-sectional rank (0-1), higher recovery = higher rank
```

**Score**: `0.5 × rank(momentum) + 0.5 × rank(recovery)`

**Future function risk**: None — max_dd and recovery are computed from historical data only.

**Hypothesis**: Recovery ratio adds a value/mean-reversion component that pure momentum lacks. Should improve performance in sideways/choppy regimes where momentum whipsaws.

---

### B2-C: Momentum + Liquidity Trend + Concentration Penalty

**Rationale**: Address B1's two structural flaws directly — liquidity trend ensures the industry is investable; concentration penalty reduces large-cap dominance.

**Factor 1 — Industry Momentum (40% weight)**:
```text
ind_ret_60d = as above
```

**Factor 2 — Liquidity Trend (30% weight)**:
```text
amt_ratio = avg(industry_daily_amount, 20d) / avg(industry_daily_amount, 60d)
Cross-sectional rank (0-1), higher = better (increasing interest)
```

**Factor 3 — Concentration Penalty (30% weight)**:
```text
top1_share = avg top1_stock_amount / total_industry_amount over 20d
Cross-sectional rank (0-1), LOWER concentration = higher rank
```

**Score**: `0.4 × rank(momentum) + 0.3 × rank(liquidity) + 0.3 × rank(concentration_penalty)`

**Future function risk**: None — all computed from T-day data. Concentration penalty uses current constituent weights, subject to same look-ahead caveat as industry classification.

**Hypothesis**: Adding liquidity and concentration dimensions directly addresses B1's fragility sources.

---

## 3. Evaluation Design

### Shared Configuration

```text
Signal:     Composite score (version-dependent)
Selection:  Top-3 / Top-5 industries by score
Holding:    EW (primary) + capped AW 20% (comparison)  
MinStocks:  3 (baseline) and 5 (robustness)
Lookback:   60 trading days (momentum), 120 days (drawdown/vol)
Rebalance:  Monthly, T-day signal, T+1 open entry
Cost:       20 bps/month
Period:     2022-01 to 2026-05
Benchmark:  HS300 equal-weight
B1 baseline: B1 conservative config (LB60, Top3, capped AW 20%, MinStk3)
```

### Evaluation Splits

```text
Ex-2025:   2022-2024
2024 only: 2024
2025 only: 2025 (reference only)
Full:      2022-2026
```

### Metrics (same as B1)

```text
Ann.Excess, IR, Win Rate, Max Rel DD, Relative Calmar
Turnover, Top 10% month contribution, Top 20% month contribution
MinStk=5 survival, Industry selection overlap with B1
```

---

## 4. Pass Criteria (vs B1 Conservative Config)

| Criterion | Threshold | Rationale |
|---|---|---|
| Ex-2025 Rel.Calmar | **> 0.63** (B1 cap_20) | Must beat B1 best |
| Top 10% month contribution | **< 80%** | Must reduce time concentration |
| MinStk=5 survival | **RC >= 0.30** | Not collapse without small industries |
| 2024-only positive | **Ann.Excess > 0** | Not 2025-dependent |
| Parameter range | **>= 2 of {top3, top5, LB60, LB120} pass** | Not single-point |
| Top-3 share (capped AW) | **< 80%** | Concentration improvement |

---

## 5. Stop Conditions

| Condition | Action |
|---|---|
| All 3 versions Ex-2025 RC < B1 baseline (0.63) | Pause B2, document |
| Top 10% months > 80% in all versions | Signal too thin for multi-factor rescue |
| MinStk=5 fails in all versions | Small-industry dependency not resolved |
| Single-parameter pass only | Same fragility as B1 |
| Factor correlation > 0.7 (factors not orthogonal) | Composite adds no diversification |

---

## 6. Implementation Scope (Phase 1)

### Single script: `scripts/evaluate_b2_multifactor.py`

```text
~500 lines
Implements: B2-A, B2-B, B2-C scoring
Reuses: industry daily returns from evaluate_industry_rotation.py data pipeline
Output: reports/b2_multifactor_eval_20260519.md
```

### What it does NOT do

```text
❌ Grid search over factor weights
❌ GA optimization
❌ Parameter tuning beyond the 3 fixed versions
❌ New data sources
❌ Strategy code changes
```

---

## 7. Recommended Execution Order

**Start with B2-A (Momentum + Low Vol)** as the first implementation:

1. Simplest 2-factor composite — easiest to validate
2. Low vol is the most established complementary factor to momentum in academic literature
3. If B2-A fails, B2-B and B2-C are unlikely to work (weaker theoretical basis)
4. If B2-A passes, B2-B and B2-C can be added as sensitivity checks

### Expected Files

```text
新增: scripts/evaluate_b2_multifactor.py
新增: reports/b2_multifactor_eval_20260519.md
修改: 无（纯新增）
```

---

## 8. Agent Teams Recommendation

**Not needed for Phase 1.** B2-A is a single-script evaluation with clear scope. QA review can follow after results are generated. Agent Teams would add overhead without parallelization benefit at this stage.

---

## 9. Pre-Implementation Checklist

- [ ] User confirms B2-A as first implementation
- [ ] User confirms pass/stop criteria
- [ ] User confirms no GA / no grid search constraint
- [ ] Script written → py_compile → smoke run → full run
- [ ] Report generated → QA review → state update
