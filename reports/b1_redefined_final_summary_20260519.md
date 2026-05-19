# B1-Redefined Final Summary — 2026-05-19

> B1 从 "Industry Rotation" 到 "EW+AWH Industry Momentum (highly concentrated)" 再到 OBSERVE/FRAGILE 的完整演化链路。

---

## 1. Evolution Chain

| Phase | Date | Conclusion |
|---|---|---|
| B0 Data Audit | 2026-05-18 | 行业分类数据可用 (Tushare, 280/280 HS300) |
| B1 Initial Eval | 2026-05-18 | 旧阈值 <10% DD → 初版评估 |
| B1 Diagnostic | 2026-05-18 | Relative Calmar + 回撤分层 → CONDITIONAL PASS |
| QA Review #1 | 2026-05-18 | REQUEST_CHANGES → OBSERVE |
| Supp. Diag 1 | 2026-05-18 | Static hold: rotation 4/4 > ex-ante → block removed |
| Supp. Diag 2 | 2026-05-18 | AW/EW 2×2: EA > AA, 90% hold effect → redefined |
| Supp. Diag 3 | 2026-05-19 | EW-only 24-variant: 0/24 pass Ex-2025 RC → must pair |
| QA Review #2 | 2026-05-19 | ACCEPTED: EW+AWH Industry Momentum (highly concentrated) |
| Robustness Val 1 | 2026-05-19 | cap_20: RC 0.63, only LB60_Top3 survives |
| Robustness Val 2 | 2026-05-19 | MinStk=5 fail, top 10% months = 113.6% of excess |
| QA Review #3 | 2026-05-19 | DOWNGRADE: CONDITIONAL PASS → OBSERVE/FRAGILE |

---

## 2. Three Supplementary Diagnostics

### 2.1 Static Hold Ex-Ante
Rotation (4/4 splits) > ex-ante static hold rules (Rule A/B/C).
2022-2023 training winners (coal) failed in 2024-2025 — rotation adapted, static hold did not.

### 2.2 AW/EW 2×2 Decomposition
Holding weight effect = 87-97% of AW/EW gap.
EA (EW signal + AW holding) > AA in 4/5 splits (Rel.Calmar).
EW signal = better industry selector; AW holding = necessary amplifier.

### 2.3 EW-Only Stability
24 variants × 4 lookbacks × 3 top-N × 2 min_stocks.
0/24 pass Ex-2025 Rel.Calmar >= 0.5 (best: 0.44).
EW signal alone insufficient — must pair with AW holding.

---

## 3. Robustness Validation 1 — Concentration Cap

| Cap | Ex-2025 RC | Top3 Share | Gate |
|---|---|---|---|
| uncapped | 1.57 | 87.3% | PASS |
| cap_30 | 0.94 | 82.4% | PASS |
| **cap_20** | **0.63** | 75.5% | PASS |
| cap_15 | 0.48 | 73.5% | FAIL |
| cap_10 | 0.37 | 72.5% | FAIL |

Only LB60_Top3 survives cap_20. LB60_Top5, LB120_Top3, LB120_Top5 all fail.
Cap_20 reduces RC by 60% vs uncapped. Top3 concentration drops only 14% (87.3→75.5%).

---

## 4. Robustness Validation 2 — Time Variation + MinStocks

### MinStocks U-Shape

| MinStk | Industries | Ex-2025 RC | Gate |
|---|---|---|---|
| 3 | 39 | 0.63 | PASS |
| 5 | 21 | 0.24 | FAIL (below EW) |
| 8 | 7 | 0.66 | PASS* |

*MinStk=8: only 7 industries — not meaningful "rotation"

### Time Concentration (Ex-2025, MinStk3, cap_20)

| Metric | Value |
|---|---|
| Top 10% months (3) contribution | **113.6%** |
| Top 20% months (6) contribution | **190.1%** |
| Max single month | 46.5% |
| Positive/Negative months | 18/14 (56%) |
| Cap binding months | 32/32 (100%) |

---

## 5. Why Downgrade: CONDITIONAL PASS → OBSERVE/FRAGILE

| Issue | Severity |
|---|---|
| Top 3 months = 113.6% of total excess — strategy does not work without them | **CRITICAL** |
| Only LB60_Top3_MinStk3 survives cap_20 — single-point failure risk | HIGH |
| MinStk=5 eliminates small industries → RC drops to 0.24 (below EW) | HIGH |
| Cap_20 reduces concentration only 14% for 60% RC loss | MEDIUM |
| Cap binds in 100% of months — always active constraint | MEDIUM |
| EW holding still beaten in all splits (cap_20 > EW) | POSITIVE |

The strategy works but is fragile: dependent on a narrow parameter window, a few outlier months, and small-industry diversity. These are not characteristics of a robust alpha signal.

---

## 6. Final Conservative Standard Configuration

```text
Signal:     EW industry momentum, lookback 60 trading days
Selection:  Top 3 industries by signal rank
Holding:    Capped amount-weighted, 20% single-stock limit
MinStocks:  3 (documented as load-bearing constraint)
Additional: Require >= 1 selected industry to have >= 8 constituent stocks
Cost:       20 bps per monthly rebalance
Benchmark:  HS300 equal-weight index

Status:     RESEARCH OBSERVATION ONLY
            NOT a trading strategy
            NOT for backtest
            NOT for Paper Trading
```

This configuration represents the narrow window where the strategy shows positive risk-adjusted excess. It is preserved as a research artifact, not promoted as a candidate.

---

## 7. Explicit Prohibitions

```text
❌ Paper Trading
❌ Formal backtest
❌ GA optimization
❌ Strategy code changes
❌ Live trading
❌ Broker integration
```

---

## 8. Forward Options

### Option A: Pause B1, pivot to new signal structure
- The industry momentum signal exists but is thin and regime-dependent
- Explore sector-neutral momentum, multi-factor industry ranking, or reversal signals
- B1's learnings inform the next attempt

### Option B: Keep as observation benchmark
- Preserve EW+AWH-IM config as a research baseline
- Revisit only after new data (2026 full year) or when a superior signal is found
- Do not actively develop

**Recommended**: Option A. The signal is real but insufficient for standalone deployment.
Keep the configuration as a benchmark for future comparisons.

---

## 9. Key Reports

| Report | Purpose |
|---|---|
| `b1_static_hold_diagnostic_20260518.md` | Static hold ex-ante comparison |
| `b1_aw_ew_decomposition_20260518.md` | AW/EW 2×2 signal×holding decomposition |
| `b1_ew_only_diagnostic_20260518.md` | EW-only 24-variant stability scan |
| `b1_concentration_cap_diagnostic_20260519.md` | Concentration cap 0-30% scan |
| `b1_cap_time_variation_diagnostic_20260519.md` | Cap binding time-variation + MinStocks |
| `b1_redefined_qa_review_20260519.md` | QA acceptance of redefinition |
| `b1_robustness_qa_review_20260519.md` | QA downgrade to OBSERVE/FRAGILE |
| `b1_redefined_final_summary_20260519.md` | This report |
