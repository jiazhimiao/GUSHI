# B1 Cap Binding Time-Variation + Industry Size Diagnostic — Robustness Validation 2

Generated: 2026-05-19 11:20

> Config: LB60, Top3, cap_20. MinStocks = 3/5/8.

---

## 1. Industry Size Minimum Test

| Split | MinStk | Ann.Excess | IR | Rel.Calmar | Win Rate | N Industries | N Months | Invest Ratio |
|-------|--------|------------|-----|------------|----------|-------------|----------|-------------|
| Ex-2025 | 3 | 9.21% | 0.51 | 0.63 | 56.2% | 39 | 32/35 | 91% |
| 2024 only | 3 | 16.49% | 0.80 | 1.41 | 54.5% | 39 | 11/11 | 100% |
| 2025 only | 3 | 109.31% | 2.22 | 19.69 | 72.7% | 39 | 11/11 | 100% |
| full | 3 | 25.38% | 0.95 | 1.73 | 57.1% | 39 | 49/52 | 94% |
| Ex-2025 | 5 | 5.45% | 0.36 | 0.24 | 62.5% | 21 | 32/35 | 91% |
| 2024 only | 5 | 9.05% | 0.56 | 1.09 | 54.5% | 21 | 11/11 | 100% |
| 2025 only | 5 | 72.62% | 1.78 | 9.96 | 81.8% | 21 | 11/11 | 100% |
| full | 5 | 21.34% | 0.92 | 0.95 | 67.3% | 21 | 49/52 | 94% |
| Ex-2025 | 8 | 10.05% | 0.60 | 0.66 | 71.9% | 7 | 32/35 | 91% |
| 2024 only | 8 | 25.91% | 1.00 | 2.68 | 81.8% | 7 | 11/11 | 100% |
| 2025 only | 8 | 47.49% | 1.81 | 14.61 | 72.7% | 7 | 11/11 | 100% |
| full | 8 | 14.79% | 0.81 | 0.98 | 67.3% | 7 | 49/52 | 94% |

### vs EW Holding Baseline (Ex-2025)

| MinStk | Cap_20 RC | vs EW RC=0.31 | Gate >= 0.5 |
|--------|-----------|----------------|-------------|
| 3 | 0.63 | Above | PASS |
| 5 | 0.24 | Below | FAIL |
| 8 | 0.66 | Above | PASS |

---

## 2. Cap Binding Time-Variation — Ex-2025, MinStk3

- Months: 32
- Positive months: 18, Negative months: 14 (56% win)
- Mean monthly excess: 0.93%
- Top 10% months (3) contribution: 113.6% of total excess
- Top 20% months (6) contribution: 190.1% of total excess
- Max single month contribution: 46.5%
- Cap binding months: 32/32 (100.0%)
- Avg cap bind ratio per industry-day: 98.3%

### Monthly Detail (first 15 months)

| Month | Selected | NStk Mean | Cap Bind% | Top1 Post | Top3 Post | Excess |
|-------|----------|-----------|-----------|-----------|-----------|--------|
| 2022-04 | 煤炭开采,全国地产,建筑工程 | 4 | 100% | 28.9% | 85.1% | -7.07% |
| 2022-05 | 煤炭开采,汽车整车,医疗保健 | 4 | 100% | 27.8% | 83.3% | 5.76% |
| 2022-06 | 汽车整车,煤炭开采,白酒 | 5 | 100% | 23.3% | 68.5% | -2.19% |
| 2022-07 | 汽车整车,电气设备,航空 | 5 | 99% | 26.1% | 76.2% | -7.70% |
| 2022-08 | 全国地产,保险,煤炭开采 | 4 | 100% | 26.1% | 78.3% | 9.77% |
| 2022-09 | 煤炭开采,全国地产,空运 | 4 | 100% | 27.8% | 83.3% | -13.34% |
| 2022-10 | 软件服务,煤炭开采,电信运营 | 4 | 100% | 26.1% | 77.9% | 0.19% |
| 2022-11 | 电信运营,软件服务,保险 | 5 | 100% | 24.4% | 72.9% | 2.89% |
| 2022-12 | 软件服务,电信运营,工程机械 | 4 | 100% | 26.1% | 77.6% | 7.75% |
| 2023-01 | 白酒,电信运营,保险 | 5 | 100% | 24.4% | 72.3% | 4.57% |
| 2023-02 | IT设备,白酒,电信运营 | 5 | 100% | 24.4% | 72.2% | 13.83% |
| 2023-03 | IT设备,软件服务,电信运营 | 5 | 100% | 24.4% | 73.0% | -0.76% |
| 2023-04 | IT设备,通信设备,建筑工程 | 5 | 100% | 24.4% | 72.8% | 0.03% |
| 2023-05 | IT设备,通信设备,水力发电 | 4 | 100% | 28.9% | 86.7% | 4.77% |
| 2023-06 | 汽车配件,通信设备,保险 | 4 | 100% | 26.1% | 78.3% | -0.76% |

### Industry Stock Count Distribution

- Mean stocks per selected industry: 5.0
- Min stocks in any selected industry: 3
- Months with any selected industry <= 5 stocks: 32/32
- Months with any selected industry <= 3 stocks: 26/32

---

## 3. Key Questions

### Q1: Does cap_20 pass depend on a few lucky months?

- Top 10% months contribute 113.6% of total excess
- Top 20% months contribute 190.1% of total excess
- Max single month contributes 46.5% of total excess
- 18 positive / 14 negative months (56% win rate)

⚠️ **YES — top 10% months drive 114% of returns.** The pass is fragile.

### Q2: Does cap_20 pass depend on small industries?

- Months where selected industry has <= 5 stocks: 32/32
- Mean stocks per selected industry: 5.0
⚠️ **YES — 100% of months include small industries.**

### Q3: Does min_stocks=5 still pass?

- Ex-2025 RC: 0.24 — FAIL
- Still > EW: NO
- Industries: 21 (vs 39 at min_stocks=3)
- Investable ratio: 91% (32/35 months)

### Q4: Does min_stocks=8 still pass?

- Ex-2025 RC: 0.66 — PASS
- Industries: 7 (vs 39 at min_stocks=3) — **severe coverage loss**
- Investable ratio: 91% (32/35 months)
- ⚠️ Only 7 industries — not meaningful 'rotation'. This is large-sector momentum, not industry rotation.

### Q5: Should B1 keep CONDITIONAL PASS or downgrade to OBSERVE?

**CONDITIONAL PASS — with min_stocks=3 constraint.** Cap_20 fails at min_stocks=5. The strategy requires small-industry participation. This is a material fragility.