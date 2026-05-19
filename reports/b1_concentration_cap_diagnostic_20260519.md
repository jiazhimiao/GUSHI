# B1 Concentration Cap Diagnostic — Robustness Validation 1

Generated: 2026-05-19 01:25

> Standard config: EW signal + capped-AW holding. LB60/120, Top3/5, MinStk3.
> Caps: uncapped (baseline), 30%, 20%, 15%, 10% single-stock weight limit.

---

## 1. Concentration Reduction

### Ex-2025 — LB60_Top3

| Cap | Ann.Excess | IR | Rel.Calmar | Top1 Share | Top3 Share | Top3 Contrib |
|-----|------------|-----|------------|------------|------------|--------------|
| uncapped | 23.35% | 0.96 | 1.57 | 43.3% | 87.3% | 2.0% |
| cap_30 | 13.96% | 0.69 | 0.94 | 30.5% | 82.4% | 1.8% |
| cap_20 | 9.21% | 0.51 | 0.63 | 25.5% | 75.5% | 1.6% |
| cap_15 | 7.16% | 0.43 | 0.48 | 24.6% | 73.5% | 1.5% |
| cap_10 | 5.73% | 0.37 | 0.37 | 24.2% | 72.5% | 1.5% |

---

## 2. Cap Impact by Split — EA (LB60_Top3)


### Ex-2025

| Cap | Ann.Excess | IR | Max DD | Rel.Calmar | Win Rate | TO | Top1 | Top3 | T3Cont |
|-----|------------|-----|--------|------------|----------|-----|------|------|--------|
| uncapped | 23.35% | 0.96 | -14.85% | 1.57 | 62.5% | 50.5% | 43.3% | 87.3% | 2.0% |
| cap_30 | 13.96% | 0.69 | -14.80% | 0.94 | 59.4% | 50.5% | 30.5% | 82.4% | 1.8% |
| cap_20 | 9.21% | 0.51 | -14.65% | 0.63 | 56.2% | 50.5% | 25.5% | 75.5% | 1.6% |
| cap_15 | 7.16% | 0.43 | -14.81% | 0.48 | 56.2% | 50.5% | 24.6% | 73.5% | 1.5% |
| cap_10 | 5.73% | 0.37 | -15.51% | 0.37 | 53.1% | 50.5% | 24.2% | 72.5% | 1.5% |

### 2024 only

| Cap | Ann.Excess | IR | Max DD | Rel.Calmar | Win Rate | TO | Top1 | Top3 | T3Cont |
|-----|------------|-----|--------|------------|----------|-----|------|------|--------|
| uncapped | 29.96% | 1.11 | -12.35% | 2.43 | 63.6% | 46.7% | 43.4% | 88.2% | 1.8% |
| cap_30 | 22.76% | 0.99 | -11.23% | 2.03 | 63.6% | 46.7% | 30.7% | 82.4% | 1.6% |
| cap_20 | 16.49% | 0.80 | -11.70% | 1.41 | 54.5% | 46.7% | 25.8% | 75.3% | 1.4% |
| cap_15 | 11.11% | 0.60 | -12.08% | 0.92 | 54.5% | 46.7% | 24.7% | 73.4% | 1.4% |
| cap_10 | 6.96% | 0.42 | -12.65% | 0.55 | 45.5% | 46.7% | 23.9% | 71.6% | 1.3% |

### 2025 only

| Cap | Ann.Excess | IR | Max DD | Rel.Calmar | Win Rate | TO | Top1 | Top3 | T3Cont |
|-----|------------|-----|--------|------------|----------|-----|------|------|--------|
| uncapped | 177.08% | 2.42 | -4.22% | 41.98 | 81.8% | 40.0% | 38.0% | 79.7% | 2.1% |
| cap_30 | 151.12% | 2.41 | -4.60% | 32.87 | 72.7% | 40.0% | 29.1% | 76.7% | 2.0% |
| cap_20 | 109.31% | 2.22 | -5.55% | 19.69 | 72.7% | 40.0% | 23.7% | 69.1% | 1.7% |
| cap_15 | 91.67% | 2.11 | -5.98% | 15.32 | 72.7% | 40.0% | 22.0% | 65.5% | 1.5% |
| cap_10 | 85.69% | 2.11 | -5.93% | 14.46 | 72.7% | 40.0% | 21.2% | 63.7% | 1.4% |

### full

| Cap | Ann.Excess | IR | Max DD | Rel.Calmar | Win Rate | TO | Top1 | Top3 | T3Cont |
|-----|------------|-----|--------|------------|----------|-----|------|------|--------|
| uncapped | 47.20% | 1.33 | -14.85% | 3.18 | 65.3% | 47.9% | 42.8% | 86.4% | 2.1% |
| cap_30 | 34.89% | 1.13 | -14.80% | 2.36 | 59.2% | 47.9% | 30.4% | 82.3% | 1.9% |
| cap_20 | 25.38% | 0.95 | -14.65% | 1.73 | 57.1% | 47.9% | 25.6% | 75.6% | 1.7% |
| cap_15 | 20.99% | 0.85 | -14.81% | 1.42 | 57.1% | 47.9% | 24.5% | 73.4% | 1.6% |
| cap_10 | 19.01% | 0.80 | -15.51% | 1.23 | 55.1% | 47.9% | 24.1% | 72.2% | 1.5% |

### EW Holding Baseline (for comparison)

| Split | Ann.Excess | IR | Rel.Calmar |
|-------|------------|-----|------------|
| Ex-2025 | 4.55% | 0.32 | 0.31 |
| 2024 only | 3.96% | 0.29 | 0.32 |
| 2025 only | 83.79% | 2.07 | 13.58 |
| full | 17.83% | 0.77 | 1.20 |

---

## 3. Cap Stability Across Parameters — Ex-2025

| Config | uncapped RC | cap_20 RC | cap_15 RC | cap_10 RC | RC Change (cap20) |
|--------|------------|-----------|-----------|-----------|-------------------|
| LB60_Top3 | 1.57 | 0.63 | 0.48 | 0.37 | -0.94 |
| LB60_Top5 | 0.72 | 0.00 | 0.00 | 0.00 | -0.72 |
| LB120_Top3 | 0.39 | 0.00 | 0.00 | 0.00 | -0.39 |
| LB120_Top5 | 0.72 | 0.11 | 0.02 | 0.00 | -0.61 |

---

## 4. Key Questions

### Q1: Does EA survive cap_20 in Ex-2025?

- Rel.Calmar: 0.63 (vs uncapped 1.57) — PASS
- Top3 share: 75.5% (vs uncapped 87.3%)
- Still > EW holding: YES (cap20=0.63 vs EW=0.31)

### Q2: Does EA survive cap_15 in Ex-2025?

- Rel.Calmar: 0.48 — FAIL
- Still > EW holding: YES

### Q3: Can top3 concentration be reduced below 60%?

- cap_20: top3 share = 75.5% ❌ >= 60%
- cap_15: top3 share = 73.5% ❌ >= 60%
- cap_10: top3 share = 72.5% ❌ >= 60%

### Q4: Does bounded AW still beat EW holding?

- cap_15 RC=0.48 vs EW RC=0.31
- YES — bounded AW retains advantage

### Q5: Is current performance driven by few large-cap stocks?

- uncapped top1 share: 43.3%
- uncapped top3 share: 87.3%
**YES — current performance is heavily concentrated.**

### Q6: If capped returns collapse, should B1 return to OBSERVE?

**YES — cap_20 causes 60% RC drop.** Strategy value is highly dependent on concentration. Consider OBSERVE downgrade.

### Q7: Allow next robustness validation?

**YES — but scope is now constrained.** Key findings:

1. **EA survives cap_20** (RC 0.63 > 0.5 gate) in Ex-2025. This is the minimum acceptable robustness level.
2. **EA fails cap_15** (RC 0.48 < 0.5). The buffer between minimum viable cap (20%) and failure (15%) is only 5 percentage points.
3. **Top3 concentration cannot be reduced below 60%** even at cap_10 (72.5%). Concentration is structural, not a parameter choice.
4. **LB60_Top3 is the only surviving parameter combination** under cap constraints. LB120 and Top5 both fail.
5. **bounded AW always beats EW** (cap_15 RC=0.48 > EW RC=0.31), but the margin is thin.

**Recommended next robustness validation**:
- Cap = 20% as standard (hard gate)
- Narrow parameter space: LB60 only, Top3 only
- Test cap_time_variation: does cap bind more in certain regimes?
- Test industry_size minimum: require >= 5 stocks to ensure diversification within industry

**If the next validation also confirms fragility, downgrade to OBSERVE.**

### Final Assessment

| Metric | uncapped | cap_20 | cap_15 | cap_10 |
|---|---|---|---|---|
| Ex-2025 RC | 1.57 | **0.63** ✅ | 0.48 ❌ | 0.37 ❌ |
| Top3 share | 87.3% | 75.5% | 73.5% | 72.5% |
| Still > EW? | YES | YES | YES | YES |
| RC drop vs uncapped | — | -60% | -69% | -76% |

**Strategy is viable at cap_20 but heavily degraded.** The 60% RC drop quantifies how much performance comes from large-cap concentration. The strategy trades alpha for robustness at cap_20 — acceptable but material.