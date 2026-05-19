# B1 Robustness Validation QA Review — 2026-05-19

> 只读审查。不修改文件。

---

## Files Inspected

`b1_cap_time_variation_diagnostic_20260519.md` (11:20), `b1_concentration_cap_diagnostic_20260519.md`, `b1_redefined_qa_review_20260519.md`, `b1_aw_ew_decomposition_20260518.md`, `b1_ew_only_diagnostic_20260518.md`, `HANDOFF.md`, `TASK.md`, `EXECUTION.md`

---

## 1. Is cap_20 Robust Enough?

**Evidence** (Validation 1 + 2):

| Metric | uncapped | cap_20 | Change |
|---|---|---|---|
| Ex-2025 RC | 1.57 | **0.63** | -60% |
| Ex-2025 Ann.Excess | 23.35% | 9.21% | -61% |
| Top3 share | 87.3% | 75.5% | -14% |
| Still > EW (0.31) | YES | YES | — |

**Cap_20 passes the minimum gate (RC 0.63 >= 0.5) but is the ONLY surviving parameter combination:**

| Config | Ex-2025 RC at cap_20 | Gate |
|---|---|---|
| LB60_Top3 | **0.63** | PASS |
| LB60_Top5 | 0.00 | FAIL |
| LB120_Top3 | 0.00 | FAIL |
| LB120_Top5 | 0.11 | FAIL |

**QA Judgment**: **Technically passes, operationally fragile.** The strategy depends on a single parameter combination (LB60_Top3). Any deviation from this — longer lookback, more industries — causes complete failure under cap_20. This is not "robust" in the ordinary sense.

---

## 2. MinStocks=5 Failure — Small-Industry Dependency?

**Evidence** (Validation 2):

| MinStk | Ex-2025 RC | vs EW | Effective Industries |
|---|---|---|---|
| 3 | 0.63 | Above | 39 |
| 5 | **0.24** | **Below EW** | 21 |
| 8 | 0.66 | Above | 7 |

**Interpretation**: The U-shape is revealing. MinStk=5 eliminates small industries (<=4 stocks) while keeping enough diversity for rotation. But the RC drops catastrophically from 0.63 to 0.24 — below EW holding. This means:

- The strategy's performance at MinStk=3 is loaded into small industries (3-4 stocks each)
- Eliminating them destroys the signal, not the noise
- Small industries (煤炭开采 5 stocks, 电信运营 3 stocks, 水力发电 3 stocks, etc.) are load-bearing

**QA Judgment**: **YES — the strategy depends on small-industry participation.** This is a fundamental structural fragility, not a parameter tuning issue.

---

## 3. MinStocks=8 — Degeneration to Large-Sector Momentum?

**Evidence** (Validation 2):

- 7 industries remain: {银行, 证券, 半导体, 电气设备, 元器件, 软件服务, 白酒}
- RC=0.66 — passes the gate
- Investable ratio: 91%

**Is this "industry rotation" anymore?**

No. With only 7 candidate industries (all large, all 7+ stocks), the strategy is selecting from the largest sectors. The word "rotation" implies meaningful choice among many alternatives. At MinStk=8, you are picking 3 from 7 — this is large-sector momentum allocation, not industry rotation.

**QA Judgment**: **MinStk=8 is not a viable path.** It passes the gate but invalidates the strategy's conceptual foundation.

---

## 4. Top 10%/20% Month Concentration

**Evidence** (Validation 2, Ex-2025, MinStk=3, cap_20):

| Statistic | Value |
|---|---|
| Positive/Negative months | 18/14 (56% win) |
| Top 10% months (3) contribution | **113.6%** of total excess |
| Top 20% months (6) contribution | **190.1%** of total excess |
| Max single month contribution | **46.5%** |
| Cap binding months | 32/32 (**100%**) |

**Interpretation**: The top 3 best months alone account for MORE than 100% of total excess. This means without those 3 months, cumulative excess would be NEGATIVE. The strategy's apparent success is concentrated in a tiny number of observations.

This also means: the 56% headline win rate overstates reliability. Most months contribute very little. A few months contribute everything.

**QA Judgment**: **This is the single most concerning finding across both validations.** The strategy is not "consistently outperforming" — it is occasionally winning big and mostly treading water. This is characteristic of a fragile signal, not a robust one.

---

## 5. Should B1 Stay CONDITIONAL PASS or Downgrade?

### Evidence Summary

| Dimension | Finding | Severity |
|---|---|---|
| Cap_20 RC gate | PASS (0.63) | — |
| Parameter robustness | Only LB60_Top3 survives | HIGH |
| MinStk=5 failure | Small-industry dependency | HIGH |
| MinStk=8 degeneration | Not meaningful rotation | HIGH |
| Top 10% concentration | 113.6% of total excess | **CRITICAL** |
| Cap always binding | 100% of months | MEDIUM |
| EW holding still beaten | cap_20 > EW in all splits | POSITIVE |

### QA Judgment

**DOWNGRADE TO OBSERVE/FRAGILE.**

CONDITIONAL PASS implies "passes minimum criteria with known caveats." The current evidence has crossed from "caveats" to "structural fragility":

1. **Single-point failure**: Only LB60_Top3_MinStk3 survives. Any parameter change breaks it.
2. **Time concentration**: Top 3 months = 113.6% of returns. This is not a strategy — it's 3 lucky months.
3. **Small-industry hostage**: Removing small industries (MinStk=5) destroys the signal.
4. **Cap effectiveness**: cap_20 reduces top3 share from 87.3% to 75.5% — a 14% improvement for a 60% RC loss. The concentration risk is barely addressed.

**The strategy works, but only in a very narrow configuration that looks increasingly like overfitting to 2022-2024 data.**

---

## 6. Allow Next Robustness Validation?

**NO — STOP EXPANDING.**

Additional robustness validations will not rescue a strategy whose performance is concentrated in 3 months and dependent on small industries. The path forward is not more tests — it is DESIGN.

---

## 7. Recommended Action

**Stop robustness validation. Design a conservative standard configuration as the final B1-redefined deliverable.**

Conservative standard config:

```text
Signal: EW industry momentum, LB60
Selection: Top3 industries
Holding: Capped AW (20% single-stock limit)
MinStocks: 3 (documented as load-bearing constraint)
Additional constraint: require >= 1 selected industry to have >= 8 stocks
  (ensures at least one large industry in the portfolio)
```

Or alternatively, acknowledge the fragility and:
- Keep B1 at OBSERVE
- Document the learning: industry rotation alpha exists but is thin and regime-dependent
- Pivot to a different signal structure (sector-neutral, multi-factor, etc.)

---

## 8. Verdict

| Dimension | Decision |
|---|---|
| Accept current B1 configuration | **CONDITIONALLY** — with fragility documented |
| Status | **OBSERVE / FRAGILE** (downgrade from CONDITIONAL PASS) |
| Allow next robustness validation | **NO** — stop expanding, pivot to design |
| Allow backtest | **NO** |
| Allow Paper Trading | **NO** |

### Next Minimum Task

Design conservative standard configuration and produce final B1-redefined summary report. No more diagnostics. No new scripts.

```text
QA Decision: DOWNGRADE CONDITIONAL PASS → OBSERVE/FRAGILE
Reason: Top 10% months = 113.6% of returns; single-parameter fragility; small-industry dependency
Safety: NO Paper Trading risk
Next: Design conservative config OR archive B1 with documented learnings
```
