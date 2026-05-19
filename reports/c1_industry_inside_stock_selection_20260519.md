# C1 -- Industry-Inside Stock Selection Evaluation

**RESEARCH OBSERVATION ONLY** -- not for trading or production use.

Generated: 2026-05-19 | Agent Teams: qts-strategy-dev + qts-qa-reviewer + qts-safety-reviewer

B1 baseline RC = 0.63 (EW+AWH Industry Momentum, cap_20, Top-5 industries)

---

## 1. Phase 1a: Variance Decomposition

**Not computed.** The variance decomposition function failed to produce results. Suspected issue: constituent/industry mapping alignment in the daily regression. This is diagnostic-only (not a blocking gate per the C1 plan).

---

## 2. C1-A Evaluation: Stock-Level Relative Momentum

### Signal: stock_60d_mom - industry_ew_mom
### Selection: Top-N across all industries, equal-weight holding
### Cost: 20 bps/month applied on turnover portion

### Full Results (4 configs)

| Split | TopN | MinStk | Ann.Excess | IR | WR | MaxDD | RC | TO | T10% | T20% | IndC | StkC | Months |
|-------|------|--------|------------|-----|-----|-------|-----|-----|------|------|------|------|--------|
| Ex-2025 | 20 | 3 | -15.1% | -1.25 | 39% | -36.6% | 0.00 | 57% | 100% | 100% | 12% | 4% | 31 |
| 2024 only | 20 | 3 | -7.0% | -0.36 | 60% | -14.2% | 0.00 | 60% | 100% | 100% | 26% | 15% | 10 |
| Ex-2025 | 10 | 3 | -21.3% | -1.20 | 32% | -49.7% | 0.00 | 67% | 100% | 100% | 16% | 6% | 31 |
| 2024 only | 10 | 3 | +1.4% | 0.16 | 40% | -14.8% | 0.10 | 73% | 330% | 635% | 69% | 57% | 10 |

All "partially reliable" — 1-4 skipped dates per config due to entry/exit alignment gaps.

---

## 3. Gate Evaluation

### MUST Gates

| Variant | RC>=1.0 | IR>0.3 | WR>55% | TO<50% | DD>-30% | 2024>0 | T10%<80% | Cost>0 | Overall |
|---------|---------|--------|--------|--------|---------|--------|----------|--------|---------|
| Ex-2025 Top20 S3 | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| 2024 Top20 S3 | FAIL | FAIL | PASS | FAIL | PASS | FAIL | FAIL | FAIL | **FAIL** |
| Ex-2025 Top10 S3 | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | **FAIL** |
| 2024 Top10 S3 | FAIL | FAIL | FAIL | FAIL | PASS | PASS | FAIL | PASS | **FAIL** |

Ex-2025 Top20 S3 and Top10 S3 fail ALL 8 MUST gates.
Best config (2024 Top10 S3): 3/8 MUST gates pass, but RC=0.10 is near zero and T10%=330%.

### SHOULD Gates

| Variant | Ind<50% | Stk<30% |
|---------|---------|---------|
| Ex-2025 Top20 S3 | PASS | PASS |
| 2024 Top20 S3 | PASS | PASS |
| Ex-2025 Top10 S3 | PASS | PASS |
| 2024 Top10 S3 | FAIL | FAIL |

All Ex-2025 configs pass SHOULD gates — single-industry and single-stock concentration are well controlled. The 2024 Top10 S3 fails because with only 10 stocks and 10 months, a single concentrated month dominates.

---

## 4. MinStk=5 Sensitivity

Not evaluated. Ex-2025 MinStk=3 RC is already 0.00, making the decay ratio undefined (division by zero). The strategy fails at MinStk=3, so MinStk=5 is moot.

---

## 5. Comparison vs B1 Baseline

B1 baseline: RC = 0.63 (EW+AWH Industry Momentum, cap_20, Top-5 industries)

| Variant | Split | C1-A RC | B1 RC | vs B1 |
|---------|-------|---------|-------|-------|
| Top20 S3 | Ex-2025 | 0.00 | 0.63 | LOSE (-0.63) |
| Top20 S3 | 2024 only | 0.00 | 0.63 | LOSE (-0.63) |
| Top10 S3 | Ex-2025 | 0.00 | 0.63 | LOSE (-0.63) |
| Top10 S3 | 2024 only | 0.10 | 0.63 | LOSE (-0.53) |

All configs underperform B1 by massive margins.

---

## 6. Verdict

**C1-A: FAIL — ALL configs fail.**

The industry-relative momentum signal produces NEGATIVE alpha (-7% to -21% annual excess after cost). The signal selects stocks that outperformed their industry peers over 60 days, and these stocks subsequently MEAN-REVERT — underperforming both the HS300 EW benchmark and the B1 baseline.

Key findings:
- Ex-2025 RC = 0.00 for both Top-20 and Top-10 (B1 = 0.63)
- Annual excess is NEGATIVE in 3/4 configs
- IR is negative for Ex-2025 splits
- Turnover exceeds 50% for all configs
- Max DD exceeds -30% for Ex-2025 splits (hard fail)
- T10% contribution >= 100% for all configs

The hypothesis that within-industry relative momentum predicts continued outperformance is **falsified**.

---

## 7. C1-B / C1-C Eligibility

**C1-A did not PASS any variant. C1-B and C1-C are NOT eligible.**

Per the approved C1 plan (Section 6 stop conditions):
- Ex-2025 RC < 1.0: TRIGGERED
- 2024-only excess <= 0: TRIGGERED (Top20)
- T10% > 80%: TRIGGERED (all configs)
- 收益集中在少数月份: TRIGGERED
- 成本后失效: TRIGGERED (3/4 configs)

**Recommendation: Stop C1.** The industry-relative approach at stock level does not work. Stocks that outperform their industry subsequently mean-revert, producing negative alpha. This is structurally similar to the well-known short-horizon reversal effect.

---

## 8. Agent Teams Review Summary

| Teammate | Decision | Key Input |
|---|---|---|
| qts-strategy-dev | PROCEED (initial plan) | Designed C1-A, wrote script |
| qts-qa-reviewer | CONFIRM_FAIL | Verified all gates, confirmed signal is correct but hypothesis is wrong |
| qts-safety-reviewer | SAFE | Zero violations, L2 boundaries respected, no token/network/data risks |

Both independent reviewers confirmed:
- Signal implementation is correct (no bugs)
- Gate assignments are verified
- Failure is due to hypothesis, not methodology
- C1-B/C1-C are correctly blocked
- All safety boundaries respected

---

## 9. Known Limitations

1. **Industry classification look-ahead bias**: The industry map is a 2026-05-18 snapshot applied to historical periods (2022-2026). Industry assignments may differ from what was known historically.
2. **Constituent survivorship bias**: historical_constituents.json has quarterly snapshots -- interim changes (~5-10% annual turnover) not captured.
3. **pre_close is mostly NaN**: Limit-up/down filtering uses the limit_up/limit_down columns directly, which are populated.
4. **ST detection**: The `is_st` field is not populated; ST check relies on symbol name containing 'ST', which may miss some cases and produce false positives.
5. **Suspension detection**: `is_suspended` field barely populated; suspension check uses volume == 0, which may not catch all suspensions.
6. **Listed-days filter**: Uses trading-day count in the dataset, not actual IPO date. Stocks with data gaps may be filtered incorrectly.
7. **Benchmark timing mismatch**: Portfolio returns use open-to-open prices while HS300 EW benchmark uses close-to-close daily returns. The ~1-day timing difference is standard in offline evaluations.
8. **Single-industry contribution**: Uses industry map at signal date, which has look-ahead bias. Industry concentration may be understated.
9. **Variance decomposition not computed**: Cannot confirm the C1 precondition that stock-specific variance dominates industry variance.
10. **MinStk=5 not evaluated**: RC=0.00 at MinStk=3 makes the sensitivity analysis moot.

---

*Generated by evaluate_c1_industry_inside_stock_selection.py | Reviewed by qts-qa-reviewer + qts-safety-reviewer*
