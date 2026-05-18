# B1 Static Hold Ex-Ante Diagnostic

Generated: 2026-05-18 19:09

> **Purpose**: Compare monthly industry rotation to ex-ante static hold rules.
> All static hold rules use only information available at decision time — no look-ahead.

---

## 1. Rules and Splits

### Static Hold Rules
| Rule | Decision Logic | Rebalancing | Cost |
|------|---------------|-------------|------|
| **Rule A** | Train-period top-1 industry | Hold entire eval period | One-time entry cost (20bps) |
| **Rule B** | Each year: prior year's best industry | Annual rebalance | Annual cost (20bps/rebalance) |
| **Rule C** | Train-period top-3 industries, EW | Hold entire eval period | One-time entry cost (20bps) |

### Rotation Variants (recomputed)
| Variant | Signal | Top-N | Weight | Cost |
|---------|--------|-------|--------|------|
| LB60_Top3_aw | 60d momentum | 3 | amount-weight | 20bps/month |
| LB60_Top5_aw | 60d momentum | 5 | amount-weight | 20bps/month |
| LB20_Top5_aw | 20d momentum | 5 | amount-weight | 20bps/month |
| LB60_Top3_ew | 60d momentum | 3 | equal-weight | 20bps/month |

### Evaluation Splits
| Split | Train | Eval | Note |
|-------|-------|------|------|
| Split1 | 2022-01~2023-12 | 2024-01~2025-12 | train 2022-2023, eval 2024-2025 |
| Split2 | 2022-01~2023-12 | 2024-01~2024-12 | train 2022-2023, eval 2024 only |
| Split3 | 2022-01~2023-12 | 2025-01~2025-12 | train 2022-2023, eval 2025 only |
| Split4 | 2022-01~2024-12 | 2025-01~2026-05 | train 2022-2024, eval 2025-2026 partial* |

---

## 2. Results by Split


### Split1: train 2022-2023, eval 2024-2025

| Strategy | Category | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|----------|------------|-----|----------|--------|------------|----------|
| LB20_Top5_aw | rotation | 75.03% | 2.06 | 69.6% | -8.12% | 9.24 | 74.5% |
| LB60_Top3_aw | rotation | 92.13% | 1.74 | 69.6% | -13.83% | 6.66 | 47.0% |
| LB60_Top5_aw | rotation | 56.99% | 1.66 | 65.2% | -13.43% | 4.24 | 47.3% |
| LB60_Top3_ew | rotation | 33.76% | 1.20 | 56.5% | -12.21% | 2.76 | 43.9% |
| Rule B (annual rebal) (annual best) | static_hold | 58.41% | 1.50 | 49.3% | -34.90% | 1.67 | 100.0% |
| Rule A (EW top-1) (煤炭开采) | static_hold | -14.59% | -0.48 | 46.1% | -44.71% | 0.00 | 0.0% |
| Rule A (AW top-1) (煤炭开采) | static_hold | -0.98% | -0.03 | 47.7% | -39.21% | 0.00 | 0.0% |
| Rule C (EW top-3) (煤炭开采,电信运营,水力发电) | static_hold | -10.39% | -0.52 | 50.0% | -33.65% | 0.00 | 0.0% |

**Best overall**: LB20_Top5_aw (Rel.Calmar=9.24)
**Best rotation**: LB20_Top5_aw (Rel.Calmar=9.24)
**Best static hold**: Rule B (annual rebal) (Rel.Calmar=1.67)

✅ Rotation OUTPERFORMS static hold in Split1

### Split2: train 2022-2023, eval 2024 only

| Strategy | Category | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|----------|------------|-----|----------|--------|------------|----------|
| LB60_Top3_aw | rotation | 33.94% | 1.03 | 63.6% | -13.83% | 2.45 | 50.0% |
| LB20_Top5_aw | rotation | 19.19% | 0.99 | 45.5% | -8.12% | 2.36 | 78.0% |
| LB60_Top5_aw | rotation | 17.17% | 0.78 | 54.5% | -13.43% | 1.28 | 46.0% |
| LB60_Top3_ew | rotation | 3.96% | 0.29 | 45.5% | -12.21% | 0.32 | 46.7% |
| Rule B (annual rebal) (annual best) | static_hold | 10.06% | 0.51 | 45.2% | -24.22% | 0.42 | 100.0% |
| Rule A (AW top-1) (煤炭开采) | static_hold | 11.07% | 0.20 | 52.3% | -29.64% | 0.37 | 0.0% |
| Rule C (EW top-3) (煤炭开采,电信运营,水力发电) | static_hold | 0.62% | 0.00 | 53.9% | -20.98% | 0.03 | 0.0% |
| Rule A (EW top-1) (煤炭开采) | static_hold | -3.42% | -0.15 | 51.9% | -31.43% | 0.00 | 0.0% |

**Best overall**: LB60_Top3_aw (Rel.Calmar=2.45)
**Best rotation**: LB60_Top3_aw (Rel.Calmar=2.45)
**Best static hold**: Rule B (annual rebal) (Rel.Calmar=0.42)

✅ Rotation OUTPERFORMS static hold in Split2

### Split3: train 2022-2023, eval 2025 only

| Strategy | Category | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|----------|------------|-----|----------|--------|------------|----------|
| LB20_Top5_aw | rotation | 167.24% | 3.13 | 90.9% | -2.33% | 71.77 | 68.0% |
| LB60_Top3_aw | rotation | 192.11% | 2.41 | 72.7% | -6.33% | 30.33 | 46.7% |
| LB60_Top5_aw | rotation | 118.84% | 2.48 | 72.7% | -5.65% | 21.03 | 48.0% |
| LB60_Top3_ew | rotation | 83.79% | 2.07 | 72.7% | -6.17% | 13.58 | 40.0% |
| Rule B (annual rebal) (annual best) | static_hold | 128.01% | 2.18 | 53.3% | -34.90% | 3.67 | 100.0% |
| Rule A (EW top-1) (煤炭开采) | static_hold | -28.55% | -1.02 | 40.1% | -24.01% | 0.00 | 0.0% |
| Rule A (AW top-1) (煤炭开采) | static_hold | -15.82% | -0.41 | 43.0% | -22.13% | 0.00 | 0.0% |
| Rule C (EW top-3) (煤炭开采,电信运营,水力发电) | static_hold | -24.84% | -1.42 | 46.3% | -21.53% | 0.00 | 0.0% |

**Best overall**: LB20_Top5_aw (Rel.Calmar=71.77)
**Best rotation**: LB20_Top5_aw (Rel.Calmar=71.77)
**Best static hold**: Rule B (annual rebal) (Rel.Calmar=3.67)

✅ Rotation OUTPERFORMS static hold in Split3

### Split4: train 2022-2024, eval 2025-2026 partial*

| Strategy | Category | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |
|----------|----------|------------|-----|----------|--------|------------|----------|
| LB20_Top5_aw | rotation | 128.38% | 2.84 | 87.5% | -6.69% | 19.18 | 69.3% |
| LB60_Top3_aw | rotation | 142.21% | 2.22 | 68.8% | -9.24% | 15.39 | 48.9% |
| LB60_Top5_aw | rotation | 80.98% | 2.07 | 68.8% | -8.45% | 9.59 | 48.0% |
| LB60_Top3_ew | rotation | 55.33% | 1.51 | 62.5% | -14.56% | 3.80 | 42.2% |
| Rule B (annual rebal) (annual best) | static_hold | 81.85% | 2.44 | 54.0% | -34.90% | 2.35 | 100.0% |
| Rule A (AW top-1) (煤炭开采) | static_hold | 10.63% | 0.44 | 45.0% | -22.13% | 0.48 | 0.0% |
| Rule A (EW top-1) (煤炭开采) | static_hold | -5.34% | 0.01 | 41.9% | -24.01% | 0.00 | 0.0% |
| Rule C (EW top-3) (煤炭开采,电信运营,银行) | static_hold | -9.45% | -0.30 | 51.7% | -19.14% | 0.00 | 0.0% |

**Best overall**: LB20_Top5_aw (Rel.Calmar=19.18)
**Best rotation**: LB20_Top5_aw (Rel.Calmar=19.18)
**Best static hold**: Rule B (annual rebal) (Rel.Calmar=2.35)

✅ Rotation OUTPERFORMS static hold in Split4

---

## 3. Cross-Split Summary

| Split | Best Rotation | Rot Calmar | Best Static | Static Calmar | Rot Wins? |
|-------|--------------|------------|-------------|---------------|-----------|
| Split1 | LB20_Top5_aw | 9.24 | Rule B (annual rebal) | 1.67 | YES |
| Split2 | LB60_Top3_aw | 2.45 | Rule B (annual rebal) | 0.42 | YES |
| Split3 | LB20_Top5_aw | 71.77 | Rule B (annual rebal) | 3.67 | YES |
| Split4 | LB20_Top5_aw | 19.18 | Rule B (annual rebal) | 2.35 | YES |

---

## 4. Key Questions


### Q1: Does rotation significantly beat ex-ante static hold?

Rotation wins: 4/4 splits
Static hold wins: 0/4 splits

**Answer**: Rotation outperforms static hold in most splits.

### Q2: Is rotation just higher-frequency momentum?

Rule A (train-period winner, hold) is the simplest momentum strategy possible — pick one industry based on past returns and hold. Rule B adds annual rebalancing. If rotation (monthly rebalancing) does not materially outperform these simpler rules, then rotation's added complexity and turnover are not justified.

### Q3: Should B1 degrade from OBSERVE to PAUSE/ARCHIVE?


**Recommendation**: Continue to AW/EW decomposition. Rotation shows evidence of adding value over static hold.

### Q4: Any future-function risk in this diagnostic?

- Rule A/C: Training period ends before eval period starts. ✅ No look-ahead.
- Rule B: Each year uses only prior year's data. ✅ No look-ahead.
- Rotation: Same as B1 (T-day signal, T+1 entry). ✅ No look-ahead beyond known B1 limitations.
- All static rules use the same industry returns and benchmarks as rotation. ✅ Consistent.

---

## 5. Interpretation — Why Rotation Wins

The static hold rules consistently underperform because **2022-2023 training period winners failed in 2024-2025**:

| Training Winner (2022-2023) | 2024-2025 Fate |
|---|---|
| 煤炭开采 | -14.59% ann. excess in Split1 |
| 电信运营 | Part of top-3, underperformed |
| 水力发电 | Part of top-3, underperformed |

This is exactly the scenario where rotation adds value: **when the training-period leader becomes the evaluation-period loser, static hold is trapped, but rotation adapts.**

Rule B (annual rebalancing) partially mitigates this. It's the closest static equivalent to rotation, and it performs decently (Calmar 0.42-3.67). But monthly rotation still beats it 4/4 splits.

**This result VINDICATES rotation against the QA charge that "static hold dominates."** When using ex-ante (not hindsight) rules, rotation is the better strategy.

## 6. Caveats

1. **Split dependency**: All splits 1-3 use 2022-2023 training. In a different training period, the static hold picks different industries and the comparison could flip.
2. **Rule A/C zero Calmar**: "0.00" means negative cumulative excess (ann_excess <= 0), not zero risk.
3. **Rotation turnover cost**: Rotation still has 43-78% monthly turnover vs static hold 0-100% annual. The cost differential is real but rotation's alpha overcomes it.
4. **2025 dominance persists**: Rotation's win is amplified by 2025 (Split3 Rel.Calmars 13-71). Split2 (2024 only) shows more modest rotation advantage (Calmar 0.32-2.45 vs static 0.00-0.42).

## 7. Recommendation

**The static hold comparison does NOT close B1. Rotation survives this diagnostic.**

However, Split2 (2024 only) shows the rotation advantage is thin without 2025:
- Best rotation (LB60_Top3_aw): Calmar=2.45
- Best static (Rule B): Calmar=0.42

**Continue to AW/EW decomposition (Supplemental Diagnostic 2) AND EW-only diagnostic (Supplemental Diagnostic 3).** The static hold evidence no longer blocks B1, but the AW/EW gap and EW's weakness in 2024 remain unresolved.