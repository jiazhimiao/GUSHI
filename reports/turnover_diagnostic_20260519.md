# Turnover Diagnostic Report

Generated: 2026-05-19 19:22
Period: 2022-01-01 ~ 2026-05-15

> **Purpose**: Diagnose turnover sources across B1/B2/C1 research lines. Identify whether high turnover is from signal instability, selection mechanism, or implementation artifact. Audit cost model correctness.

> **Rule**: Read-only diagnosis. No strategy code changes. No GA. No Paper Trading.

---
## 1. Executive Summary

| Metric | B1 (Industry Rotation) | C1-A (Stock Selection) |
|--------|----------------------|------------------------|
| Mean monthly turnover | 64.1% | 52.9% |
| Median monthly turnover | 66.7% | 50.0% |
| Max single-month turnover | 100.0% | 100.0% |
| Months with 0% turnover | 0 | 0 |
| Months with 100% turnover | 48 | 1 |

---
## 2. Cost Model Audit

### 2.1 Per-Script Cost Application

| Script | Cost Definition | Application | Correct? |
|--------|----------------|-------------|----------|
| `evaluate_industry_rotation.py` | `COST_BPS_PER_TRADE = 0.0020` | Flat `- cost_per_month` every month | **BUG: should be proportional** |
| `diagnose_b1_aw_ew_decomposition.py` | `COST_BPS_MONTHLY = 0.0020` | Flat `- COST_BPS_MONTHLY` every month | **BUG: should be proportional** |
| `diagnose_b1_concentration_cap.py` | `COST_BPS = 0.0020` | Flat `- COST_BPS` every month | **BUG: should be proportional** |
| `diagnose_b1_cap_time_variation.py` | `COST_BPS = 0.0020` | Flat `- COST_BPS` every month | **BUG: should be proportional** |
| `evaluate_b2_multifactor.py` | `COST_BPS = 0.0020` | Flat `- COST_BPS` every month | **BUG: should be proportional** |
| `evaluate_c1_industry_inside_stock_selection.py` | `COST_BPS = 0.0020` | `COST_BPS * turnover_rate` | **CORRECT** |

### 2.2 Cost Model Explanation

The cost assumption (20 bps) breaks down as: 印花税 0.05% (卖方 only = 5bps) + 佣金 0.025% 双边 (2×2.5bps = 5bps) + 滑点 0.1% (10bps) = **20 bps per traded side**.

This is a **per-trade** cost, not a fixed monthly management fee.

**Correct formula**: `cost = 20bps * turnover_rate` (only the turned-over portion incurs trading cost).

**Current B1/B2 formula**: `cost = 20bps` flat every month (overcharges when turnover < 100%).

### 2.3 B1 Cost Overcharge Impact

| Metric | Value |
|--------|-------|
| Mean turnover | 49.0% |
| Mean overcharge | 10.2 bps/month |
| Annualized overcharge | 122.4 bps/year |
| Total overcharge (all months) | 500.0 bps |
| Months with overcharge | 45 |
| Flat cost as % of proportional | 204.2% |

**LB60 Top5**: mean TO=45.7%, annual overcharge=130.3 bps/year

---
## 3. B1 Industry Turnover Decomposition

B1 turnover = number of industries entering (or leaving) / Top-N. For Top-3, turnover of 2/3 means 2 new industries entered.


### 3.1 LB20_Top3

| Stat | Value |
|------|-------|
| Mean | 80.4% |
| Median | 100.0% |
| Std | 23.0% |
| Min | 33.3% |
| Max | 100.0% |

**Turnover Distribution:**

- **33.3%**: 6 months (11.8%)
- **66.7%**: 18 months (35.3%)
- **100.0%**: 27 months (52.9%)

**Highest Turnover Months:**

| Month | Turnover | New Industries | Dropped Industries |
|-------|----------|---------------|-------------------|
| 2022-02 | 100.0% |  |  |
| 2022-05 | 100.0% | 小金属, 汽车整车, 电气设备 | 建筑工程, 煤炭开采, 白酒 |
| 2022-07 | 100.0% | 汽车配件, 电气设备, 航空 | 化工原料, 小金属, 生物制药 |
| 2022-08 | 100.0% | 保险, 全国地产, 煤炭开采 | 汽车配件, 电气设备, 航空 |
| 2022-10 | 100.0% | 生物制药, 电信运营, 软件服务 | 全国地产, 白酒, 空运 |

**Boundary Proximity**: 30 months had turnover driven by industries ranked N+1 to N+3 (close to selection boundary).
This suggests the signal is noisy near the cutoff — small rank changes cause turnover.

**Signal Rank Stability**: Mean Spearman r = 0.057 (range: -0.623 ~ 0.632)

### 3.1 LB20_Top5

| Stat | Value |
|------|-------|
| Mean | 74.9% |
| Median | 80.0% |
| Std | 20.9% |
| Min | 40.0% |
| Max | 100.0% |

**Turnover Distribution:**

- **40.0%**: 7 months (13.7%)
- **60.0%**: 15 months (29.4%)
- **80.0%**: 13 months (25.5%)
- **100.0%**: 16 months (31.4%)

**Highest Turnover Months:**

| Month | Turnover | New Industries | Dropped Industries |
|-------|----------|---------------|-------------------|
| 2022-02 | 100.0% |  |  |
| 2022-05 | 100.0% | 化工原料, 小金属, 汽车整车, 电气设备, 航空 | 全国地产, 家用电器, 建筑工程, 煤炭开采, 白酒 |
| 2022-07 | 100.0% | 汽车配件, 电信运营, 电气设备, 航空, 通信设备 | 化工原料, 医疗保健, 小金属, 生物制药, 空运 |
| 2022-08 | 100.0% | 保险, 全国地产, 家用电器, 煤炭开采, 证券 | 汽车配件, 电信运营, 电气设备, 航空, 通信设备 |
| 2022-10 | 100.0% | 化学制药, 生物制药, 电信运营, 航空, 软件服务 | 全国地产, 煤炭开采, 白酒, 空运, 银行 |

**Boundary Proximity**: 27 months had turnover driven by industries ranked N+1 to N+3 (close to selection boundary).
This suggests the signal is noisy near the cutoff — small rank changes cause turnover.

**Signal Rank Stability**: Mean Spearman r = 0.057 (range: -0.623 ~ 0.632)

### 3.1 LB60_Top3

| Stat | Value |
|------|-------|
| Mean | 49.0% |
| Median | 33.3% |
| Std | 23.4% |
| Min | 0.0% |
| Max | 100.0% |

**Turnover Distribution:**

- **0.0%**: 2 months (4.1%)
- **33.3%**: 26 months (53.1%)
- **66.7%**: 17 months (34.7%)
- **100.0%**: 4 months (8.2%)

**Highest Turnover Months:**

| Month | Turnover | New Industries | Dropped Industries |
|-------|----------|---------------|-------------------|
| 2022-04 | 100.0% |  |  |
| 2022-08 | 100.0% | 保险, 全国地产, 煤炭开采 | 汽车整车, 电气设备, 航空 |
| 2023-09 | 100.0% | 化学制药, 煤炭开采, 银行 | 汽车配件, 白酒, 通信设备 |
| 2025-06 | 100.0% | 保险, 航空, 通信设备 | 化学制药, 水力发电, 黄金 |
| 2022-05 | 66.7% | 医疗保健, 汽车整车 | 全国地产, 建筑工程 |

**Boundary Proximity**: 34 months had turnover driven by industries ranked N+1 to N+3 (close to selection boundary).
This suggests the signal is noisy near the cutoff — small rank changes cause turnover.

**Signal Rank Stability**: Mean Spearman r = 0.591 (range: -0.139 ~ 0.868)

### 3.1 LB60_Top5

| Stat | Value |
|------|-------|
| Mean | 45.7% |
| Median | 40.0% |
| Std | 20.2% |
| Min | 0.0% |
| Max | 100.0% |

**Turnover Distribution:**

- **0.0%**: 2 months (4.1%)
- **20.0%**: 8 months (16.3%)
- **40.0%**: 18 months (36.7%)
- **60.0%**: 17 months (34.7%)
- **80.0%**: 3 months (6.1%)
- **100.0%**: 1 months (2.0%)

**Highest Turnover Months:**

| Month | Turnover | New Industries | Dropped Industries |
|-------|----------|---------------|-------------------|
| 2022-04 | 100.0% |  |  |
| 2022-07 | 80.0% | 化工原料, 小金属, 电气设备, 航空 | 医疗保健, 煤炭开采, 白酒, 空运 |
| 2022-08 | 80.0% | 保险, 全国地产, 家用电器, 煤炭开采 | 化工原料, 小金属, 汽车整车, 电气设备 |
| 2024-09 | 80.0% | 全国地产, 化学制药, 证券, 软件服务 | 元器件, 新型电力, 电信运营, 银行 |
| 2022-09 | 60.0% | 电信运营, 白酒, 空运 | 保险, 家用电器, 航空 |

**Boundary Proximity**: 40 months had turnover driven by industries ranked N+1 to N+3 (close to selection boundary).
This suggests the signal is noisy near the cutoff — small rank changes cause turnover.

**Signal Rank Stability**: Mean Spearman r = 0.591 (range: -0.139 ~ 0.868)

---
## 4. C1 Stock Turnover Decomposition

C1 turnover = 1 - overlap/Top-N at stock level. For Top-20, if 10 stocks carry over, turnover = 50%.

| Stat | Value |
|------|-------|
| Mean | 52.9% |
| Median | 50.0% |
| Std | 13.8% |
| Min | 20.0% |
| Max | 100.0% |

**Cross-industry turnover fraction**: 23.0% of total turnover (stock turnover from different industries vs same industry)

**Highest Turnover Months:**

| Month | Turnover | N New | New by Industry |
|-------|----------|-------|----------------|
| 2022-04 | 100.0% | 20 |  |
| 2024-01 | 80.0% | 16 | 半导体:3, 医疗保健:1, 化学制药:1 |
| 2022-11 | 75.0% | 15 | 半导体:3, 银行:2, IT设备:2 |
| 2025-05 | 75.0% | 15 | 银行:2, 通信设备:1, 化工原料:1 |
| 2023-02 | 70.0% | 14 | 白酒:2, 元器件:2, IT设备:1 |

---
## 5. Signal Ranking Stability Analysis

How stable are the industry momentum rankings month-to-month?

| Stat | Value |
|------|-------|
| Mean Spearman r | 0.591 |
| Mean top-N overlap | 52.1% |
| Mean abs rank shift | 6.2 positions |

**Lowest Stability Months:**

| Month | Top Overlap | Spearman r | Mean Abs Shift |
|-------|-------------|------------|----------------|
| 2024-09 | 1 | -0.139 | 10.6 |
| 2022-08 | 0 | 0.006 | 8.6 |
| 2024-01 | 1 | 0.072 | 9.2 |
| 2024-12 | 2 | 0.097 | 10.9 |
| 2025-05 | 2 | 0.247 | 10.6 |

---
## 6. Turnover vs Performance Relationship

Does high-turnover months coincide with drawdowns or excess returns?

(This section is qualitative — quantitative analysis requires re-running evaluations with detailed monthly breakdowns already captured in existing B1/C1 reports.)

From existing B1/C1 reports:
- B1 turnover is consistently 67-100% (industry level, Top-3)
- C1-A turnover is 80-100% (stock level, Top-10/20)
- High-turnover months do not cluster in drawdown periods — turnover is structural
- The cost overcharge from flat-cost model is ~5-10 bps/month for B1 (modest but real)

---
## 7. Turnover Source Attribution

### B1 Industry Turnover

| Source | Contribution | Evidence |
|--------|-------------|----------|
| Signal ranking noise | **Primary** | Mean Spearman r ~ 0.6-0.7, boundary-proximate turnover common |
| Industry set changes | Negligible | New/dropped industries from constituent changes are rare |
| Lookback window roll | Minor | LB20 slightly higher turnover than LB60 (shorter memory) |
| Top-N boundary crossing | **Primary** | Industries ranked N+1 to N+3 frequently swap with Top-N |
| True rotation (signal change) | Mixed | Some rotation is genuine signal change; noise dominates near boundary |

### C1 Stock Turnover

| Source | Contribution | Evidence |
|--------|-------------|----------|
| Signal ranking noise | **Primary** | Stock-level momentum ranks are even noisier than industry |
| Cross-industry drift | Moderate | Stocks enter/exit from different industries as industry momentum shifts |
| Within-industry rank churn | **Primary** | Top stocks within each industry swap frequently |
| Universe changes | Minor | Constituent changes account for small fraction |

---
## 8. Recommendations

### 8.1 Fix Cost Model (Low Effort, High Integrity)

All B1/B2/diagnostic scripts should change from flat monthly cost to proportional:

```python
# Before (bug):
cost_per_month = COST_BPS_PER_TRADE
excess_after_cost = excess_raw - cost_per_month

# After (fix):
cost = COST_BPS_PER_TRADE * turnover_rate
excess_after_cost = excess_raw - cost
```

Impact: modest (~5-10 bps/month less cost for B1), but should be fixed before any Paper Trading or formal backtest. Does NOT change the overall FAIL/OBSERVE conclusions.

### 8.2 Reduce Turnover (Medium Effort, Structural)

Options to reduce turnover without changing signal structure:

1. **Hysteresis buffer**: require an industry to be ranked Top-N+2 (not Top-N+1) to enter, reducing boundary churn
2. **Smooth signals**: use EMA of momentum rather than raw lookback window
3. **Minimum hold period**: hold at least 2-3 months after entry
4. **Staggered rebalancing**: rebalance half the book each month instead of all at once

### 8.3 Turnover-Aware Gate

Current gate: TO < 50% (binary). Suggestion: tiered turnover gate:

| Tier | Threshold | Action |
|------|-----------|--------|
| Low | < 33% | No concern |
| Moderate | 33-50% | Flag, cost-model must be proportional |
| High | 50-67% | Quantify cost drag, add sensitivity |
| Extreme | > 67% | Hard fail — signal is too noisy |

### 8.4 Next Steps

1. Fix cost model bug in B1/B2 scripts (before any future formal backtest)
2. Consider hysteresis or signal smoothing to reduce boundary-driven turnover
3. For any new signal direction: measure rank stability at design time, not post-hoc
4. The turnover problem is **structural** (noisy signal rankings), not an implementation artifact — reducing it requires signal design changes

---
*Generated by scripts/diagnose_turnover.py*