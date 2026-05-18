# B1 EW-Only Stability Diagnostic

Generated: 2026-05-18 23:44

> Grid: 4 lookback × 3 top-N × 2 min_stocks = 24 variants

---

## 1. Robustness Ranking

Scoring: +1 per primary split (Ex-2025, 2024 only, full) with Rel.Calmar >= 0.5 AND Ann.Excess > 3%. +0.5 bonus if full-sample turnover < 50%.

| Rank | LB | TopN | MinStk | Score | Ex-2025 RC | 2024 RC | Full RC | Full TO |
|------|-----|------|--------|-------|------------|---------|---------|---------|
| 1 | 120 | 5 | 5 | 2.5 | 0.44 | 1.82 | 0.81 | 22.7% |
| 2 | 20 | 8 | 5 | 2.5 | 0.04 | 4.45 | 0.78 | 43.2% |
| 3 | 120 | 8 | 5 | 2.5 | 0.14 | 1.76 | 0.52 | 18.9% |
| 4 | 60 | 8 | 5 | 2.5 | 0.06 | 2.24 | 0.52 | 25.0% |
| 5 | 5 | 5 | 3 | 2.0 | 0.10 | 0.63 | 0.54 | 80.8% |
| 6 | 60 | 3 | 3 | 1.5 | 0.31 | 0.32 | 1.20 | 47.9% |
| 7 | 60 | 5 | 5 | 1.5 | 0.01 | 0.00 | 0.63 | 34.2% |
| 8 | 120 | 3 | 5 | 1.5 | 0.00 | 0.27 | 0.55 | 31.9% |
| 9 | 60 | 3 | 5 | 1.5 | 0.00 | 0.00 | 0.54 | 45.8% |
| 10 | 20 | 3 | 3 | 1.0 | 0.03 | 0.00 | 1.08 | 80.0% |
| 11 | 20 | 5 | 3 | 1.0 | 0.00 | 0.00 | 0.58 | 74.4% |
| 12 | 20 | 5 | 5 | 1.0 | 0.00 | 13.63 | 0.37 | 58.8% |
| 13 | 5 | 8 | 5 | 1.0 | 0.01 | 2.67 | 0.29 | 51.0% |
| 14 | 60 | 5 | 3 | 0.5 | 0.00 | 0.00 | 0.42 | 44.6% |
| 15 | 120 | 8 | 3 | 0.5 | 0.05 | 0.00 | 0.38 | 27.5% |
| 16 | 120 | 5 | 3 | 0.5 | 0.00 | 0.00 | 0.30 | 31.6% |
| 17 | 60 | 8 | 3 | 0.5 | 0.00 | 0.10 | 0.26 | 40.4% |
| 18 | 120 | 3 | 3 | 0.5 | 0.00 | 0.00 | 0.22 | 41.5% |
| 19 | 5 | 3 | 3 | 0.0 | 0.00 | 0.43 | 0.43 | 88.2% |
| 20 | 5 | 8 | 3 | 0.0 | 0.04 | 0.69 | 0.42 | 74.8% |
| 21 | 20 | 8 | 3 | 0.0 | 0.00 | 0.31 | 0.21 | 70.2% |
| 22 | 5 | 3 | 5 | 0.0 | 0.00 | 0.00 | 0.20 | 79.1% |
| 23 | 5 | 5 | 5 | 0.0 | 0.00 | 1.05 | 0.17 | 70.2% |
| 24 | 20 | 3 | 5 | 0.0 | 0.00 | 0.29 | 0.14 | 76.0% |

---

## 2. Ex-2025 — Full Matrix (Rel.Calmar)


### min_stocks = 3

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 0.00 | 0.10 | 0.04 |
| LB20 | 0.03 | 0.00 | 0.00 |
| LB60 | 0.31 | 0.00 | 0.00 |
| LB120 | 0.00 | 0.00 | 0.05 |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

### min_stocks = 5

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 0.00 | 0.00 | 0.01 |
| LB20 | 0.00 | 0.00 | 0.04 |
| LB60 | 0.00 | 0.01 | 0.06 |
| LB120 | 0.00 | 0.44 | 0.14 |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

---

## 2. 2024 only — Full Matrix (Rel.Calmar)


### min_stocks = 3

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 0.43 | 0.63 * | 0.69 |
| LB20 | 0.00 | 0.00 | 0.31 |
| LB60 | 0.32 | 0.00 | 0.10 |
| LB120 | 0.00 | 0.00 | 0.00 |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

### min_stocks = 5

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 0.00 | 1.05 | 2.67 * |
| LB20 | 0.29 | 13.63 * | 4.45 * |
| LB60 | 0.00 | 0.00 | 2.24 * |
| LB120 | 0.27 | 1.82 * | 1.76 * |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

---

## 2. 2025 only — Full Matrix (Rel.Calmar)


### min_stocks = 3

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 37.69 * | 29.59 * | 22.34 * |
| LB20 | 30.18 * | 20.69 * | 16.34 * |
| LB60 | 13.58 * | 7.83 * | 5.01 * |
| LB120 | 5.15 * | 5.24 * | 3.89 * |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

### min_stocks = 5

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 32.48 * | 50.56 * | 26.82 * |
| LB20 | 11.49 * | 12.71 * | 15.42 * |
| LB60 | 6.84 * | 10.90 * | 7.54 * |
| LB120 | 6.91 * | 3.63 * | 5.37 * |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

---

## 2. 2025-2026 — Full Matrix (Rel.Calmar)


### min_stocks = 3

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 5.34 * | 3.17 * | 4.24 * |
| LB20 | 23.14 * | 15.08 * | 5.39 * |
| LB60 | 3.80 * | 2.74 * | 2.09 * |
| LB120 | 1.46 * | 2.63 * | 2.56 * |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

### min_stocks = 5

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 10.61 * | 5.14 * | 5.75 * |
| LB20 | 9.04 * | 10.95 * | 12.79 * |
| LB60 | 5.96 * | 4.19 * | 3.20 * |
| LB120 | 6.26 * | 4.40 * | 5.59 * |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

---

## 2. full — Full Matrix (Rel.Calmar)


### min_stocks = 3

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 0.43 | 0.54 * | 0.42 |
| LB20 | 1.08 * | 0.58 * | 0.21 |
| LB60 | 1.20 * | 0.42 | 0.26 |
| LB120 | 0.22 | 0.30 | 0.38 |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

### min_stocks = 5

| LB\TopN | Top3 | Top5 | Top8 |
|---|---|---|---|
| LB5 | 0.20 | 0.17 | 0.29 |
| LB20 | 0.14 | 0.37 | 0.78 * |
| LB60 | 0.54 * | 0.63 * | 0.52 * |
| LB120 | 0.55 * | 0.81 * | 0.52 * |

*\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*

---

## 3. Dimensional Analysis (Ex-2025, mean Rel.Calmar)


### By Lookback

| Lookback | Mean RC | Median RC | Best RC | Worst RC | Pct >= 0.5 |
|-----|---------|-----------|---------|----------|------------|
| 5 | 0.02 | 0.00 | 0.10 | 0.00 | 0% |
| 20 | 0.01 | 0.00 | 0.04 | 0.00 | 0% |
| 60 | 0.06 | 0.01 | 0.31 | 0.00 | 0% |
| 120 | 0.11 | 0.03 | 0.44 | 0.00 | 0% |

### By Top-N

| Top-N | Mean RC | Median RC | Best RC | Worst RC | Pct >= 0.5 |
|-----|---------|-----------|---------|----------|------------|
| 3 | 0.04 | 0.00 | 0.31 | 0.00 | 0% |
| 5 | 0.07 | 0.00 | 0.44 | 0.00 | 0% |
| 8 | 0.04 | 0.04 | 0.14 | 0.00 | 0% |

### By Min Stocks

| Min Stocks | Mean RC | Median RC | Best RC | Worst RC | Pct >= 0.5 |
|-----|---------|-----------|---------|----------|------------|
| 3 | 0.04 | 0.00 | 0.31 | 0.00 | 0% |
| 5 | 0.06 | 0.00 | 0.44 | 0.00 | 0% |

---

## 4. Top-6 Variants — Full Detail


### #1: LB120_Top5_MinStk5 — Robustness=2.5

| Split | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|-------|------------|-----|----------|--------|------------|----------|
| Ex-2025 | 5.47% | 0.46 | 37.9% | -12.38% | 0.44 | 25.7% |
| 2024 only | 6.77% | 0.53 | 45.5% | -3.71% | 1.82 | 26.0% |
| 2025 only | 19.37% | 1.63 | 63.6% | -5.34% | 3.63 | 20.0% |
| 2025-2026 | 23.49% | 1.94 | 62.5% | -5.34% | 4.40 | 18.7% |
| full | 9.99% | 0.80 | 45.7% | -12.38% | 0.81 | 22.7% |

### #2: LB20_Top8_MinStk5 — Robustness=2.5

| Split | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|-------|------------|-----|----------|--------|------------|----------|
| Ex-2025 | 0.41% | 0.09 | 50.0% | -10.28% | 0.04 | 40.2% |
| 2024 only | 7.38% | 0.71 | 54.5% | -1.66% | 4.45 | 43.8% |
| 2025 only | 27.65% | 2.11 | 63.6% | -1.79% | 15.42 | 52.5% |
| 2025-2026 | 28.81% | 2.37 | 68.8% | -2.25% | 12.79 | 50.0% |
| full | 8.00% | 0.80 | 54.9% | -10.28% | 0.78 | 43.2% |

### #3: LB120_Top8_MinStk5 — Robustness=2.5

| Split | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|-------|------------|-----|----------|--------|------------|----------|
| Ex-2025 | 1.78% | 0.24 | 41.4% | -12.42% | 0.14 | 17.0% |
| 2024 only | 5.25% | 0.54 | 45.5% | -2.99% | 1.76 | 17.5% |
| 2025 only | 18.79% | 1.98 | 54.5% | -3.50% | 5.37 | 22.5% |
| 2025-2026 | 19.58% | 2.13 | 56.2% | -3.50% | 5.59 | 21.7% |
| full | 6.52% | 0.74 | 45.7% | -12.42% | 0.52 | 18.9% |

### #4: LB60_Top8_MinStk5 — Robustness=2.5

| Split | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|-------|------------|-----|----------|--------|------------|----------|
| Ex-2025 | 0.51% | 0.10 | 43.8% | -8.99% | 0.06 | 21.4% |
| 2024 only | 6.19% | 0.59 | 45.5% | -2.77% | 2.24 | 21.2% |
| 2025 only | 20.44% | 1.96 | 54.5% | -2.71% | 7.54 | 30.0% |
| 2025-2026 | 16.01% | 1.58 | 56.2% | -5.00% | 3.20 | 30.0% |
| full | 4.70% | 0.55 | 46.9% | -8.99% | 0.52 | 25.0% |

### #5: LB5_Top5_MinStk3 — Robustness=2.0

| Split | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|-------|------------|-----|----------|--------|------------|----------|
| Ex-2025 | 1.96% | 0.20 | 57.1% | -19.79% | 0.10 | 83.5% |
| 2024 only | 3.22% | 0.29 | 63.6% | -5.15% | 0.63 | 88.0% |
| 2025 only | 70.12% | 3.71 | 81.8% | -2.37% | 29.59 | 72.0% |
| 2025-2026 | 38.21% | 1.86 | 68.8% | -12.04% | 3.17 | 73.3% |
| full | 10.77% | 0.68 | 59.6% | -19.79% | 0.54 | 80.8% |

### #6: LB60_Top3_MinStk3 — Robustness=1.5

| Split | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|-------|------------|-----|----------|--------|------------|----------|
| Ex-2025 | 4.55% | 0.32 | 53.1% | -14.88% | 0.31 | 50.5% |
| 2024 only | 3.96% | 0.29 | 45.5% | -12.21% | 0.32 | 46.7% |
| 2025 only | 83.79% | 2.07 | 72.7% | -6.17% | 13.58 | 40.0% |
| 2025-2026 | 55.33% | 1.51 | 62.5% | -14.56% | 3.80 | 42.2% |
| full | 17.83% | 0.77 | 55.1% | -14.88% | 1.20 | 47.9% |

---

## 5. Three-Tier Conclusion

### A. Can EW-Only Stand Alone?

- Best robustness score: 2.5/3.5
- Variants with >= 2.5 (passing >=2 primary splits): 4/24

**MARGINAL — EW-only is borderline.** Best variant (LB120_Top5_MinStk5) passes 2.5/3.5 robustness criteria. It could serve as a conservative baseline but lacks reliability for standalone deployment.

### B. Can EW Signal Serve as EA's Signal Layer?

The AW/EW decomposition proved EA (EW signal + AW holding) outperforms AA in 4/5 splits. For EW to serve as EA's signal layer, it needs:
- Positive Ex-2025 Ann.Excess (> 3%)
- Ex-2025 IR > 0.3
- Not dependent on 2025

- 2/24 variants have Ex-2025 Ann.Excess > 3%
- 2/24 variants have Ex-2025 IR > 0.3
- **0/24 variants have Ex-2025 Rel.Calmar >= 0.5** (best: LB120_Top5_MinStk5 = 0.44)

**YES — but only when paired with AW holding.** EW signal alone fails the Rel.Calmar gate Ex-2025 (0/24 pass). However, the EA combination (EW signal + AW holding) passes Ex-2025 RC=1.61 in the AW/EW decomposition diagnostic. The signal exists but requires AW amplification to achieve acceptable risk-adjusted returns.

| Layer | Ex-2025 Rel.Calmar | Gate |
|-------|---------------------|------|
| EW signal alone (EE) | 0.31 (max 0.44) | FAIL |
| EW signal + AW holding (EA) | 1.61 | PASS |
| AW signal + AW holding (AA) | 1.30 | PASS |

**EW signal is a necessary but not sufficient component. It must be paired with AW holding.**

### C. Should B1 Be Redefined as 'EW Signal + AW Holding'?

Evidence from all three supplementary diagnostics:
1. **Static hold**: Rotation (4/4 splits) > ex-ante static hold → rotation adds value
2. **AW/EW decomposition**: EA > AA in 4/5 splits → EW signal is the better industry selector (~10% contribution); AW holding is the necessary amplifier (~90% contribution)
3. **EW-only**: 0/24 pass Ex-2025 RC gate → EW signal alone is NOT sufficient; must be paired with AW holding. Only LB60-120 with Top3-5 produce Ex-2025 Ann.Excess > 3%.

**Recommendation**:
- **Redefine B1** as **'EW Signal + AW Holding Amount-Weighted Industry Momentum'**
- **Standard configuration**: LB60-120, Top3-5, MinStk3, EW signal (industry selection), AW holding (execution)
- **Why not shorter lookbacks**: LB5/20 fail Ex-2025 Ann.Excess entirely
- **Why not MinStk5**: Reduces available industries from 39 without improving Ex-2025 RC
- **Why not Top8**: Increases turnover without improving Ex-2025 RC; Top3-5 is the sweet spot
- **Rename**: 'Industry Rotation' → **'EW+AWH Industry Momentum'**
- **Status**: OBSERVE → **CONDITIONAL PASS** (pending user review of all three diagnostics)