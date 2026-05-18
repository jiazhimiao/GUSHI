# B1 — Industry Rotation Diagnostic Report

Generated: 2026-05-18 17:18
Period: 2022-01-01 ~ 2026-05-15
Cost assumption: 0.20% per monthly trade

> **Rule update 2026-05-18**: 最大相对回撤从 <10% 一票否决改为风险分层 + Relative Calmar >= 0.5。

---

## 1. Rule Change vs Previous Evaluation

| Rule | Old | New |
|------|-----|-----|
| 最大相对回撤 | < 10% (一票否决) | 风险分层 (<=10% excellent / 10-20% acceptable / 20-30% high risk / >30% fail) |
| Drawdown metric | Absolute threshold | Relative Calmar = 年化超额 / abs(最大相对回撤) |
| Calmar gate | None | >= 0.5 minimum, >= 1.0 good, >= 1.5 strong |
| Hard fail | N/A | 最大相对回撤 > 30% |

---

## 2. Data Summary

- Industries with >= 3 HS300 stocks: 39
- HS300 index data: 2022-01-01 ~ 2026-05-15

### Industry Coverage

| Industry | Avg Daily Stocks | Max Stocks | Min Stocks |
|----------|-----------------|------------|------------|
| 银行 | 20.9 | 23 | 20 |
| 证券 | 19.8 | 22 | 18 |
| 半导体 | 13.2 | 17 | 10 |
| 电气设备 | 12.4 | 15 | 8 |
| 元器件 | 9.2 | 14 | 8 |
| 建筑工程 | 7.8 | 8 | 7 |
| 白酒 | 7.0 | 7 | 7 |
| 软件服务 | 6.7 | 9 | 6 |
| 化学制药 | 5.6 | 7 | 5 |
| 化工原料 | 5.2 | 6 | 4 |
| 保险 | 5.0 | 5 | 5 |
| 小金属 | 5.0 | 5 | 5 |
| IT设备 | 5.0 | 5 | 4 |
| 医疗保健 | 5.0 | 6 | 4 |
| 汽车整车 | 4.6 | 6 | 4 |
| 煤炭开采 | 4.5 | 5 | 3 |
| 生物制药 | 4.4 | 5 | 4 |
| 家用电器 | 4.3 | 5 | 4 |
| 通信设备 | 4.2 | 7 | 3 |
| 汽车配件 | 4.2 | 5 | 3 |
| 空运 | 4.0 | 4 | 4 |
| 工程机械 | 4.0 | 4 | 3 |
| 航空 | 3.8 | 6 | 3 |
| 新型电力 | 3.0 | 4 | 3 |
| 全国地产 | 3.0 | 3 | 3 |
| 电信运营 | 3.0 | 3 | 3 |
| 食品 | 3.0 | 3 | 3 |
| 农药化肥 | 3.0 | 3 | 3 |
| 水力发电 | 3.0 | 3 | 3 |
| 中成药 | 3.0 | 3 | 3 |
| 石油开采 | 3.0 | 3 | 3 |
| 水运 | 3.0 | 3 | 3 |
| 火力发电 | 3.0 | 3 | 3 |
| 运输设备 | 3.0 | 3 | 3 |
| 铝 | 3.0 | 3 | 3 |
| 铜 | 3.0 | 3 | 3 |
| 黄金 | 3.0 | 3 | 3 |
| 仓储物流 | 3.0 | 3 | 3 |
| 港口 | 3.0 | 3 | 3 |

---

## 3. Known Limitations

1. **行业分类后见偏差**: 行业分类为 2026-05-18 快照。
2. **成分股生存偏差**: `historical_constituents.json` 遗漏 ~5-10% 被调出股票。
3. **复权口径**: adj_factor 全为 1.0，依赖 AKShare 默认 qfq。
4. **pre_close 缺失**: 收益通过 `close.pct_change()` 计算。
5. **ST/停牌过滤**: is_st 和 is_suspended 字段基本未填充。

---

## 4. Evaluation Results (All Variants)


### LB5_Top3_ew

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 12.09% | > 3% | PASS |
| 信息比率 | 0.66 | > 0.3 | PASS |
| 月度 win rate | 61.5% | > 55% | PASS |
| 最大相对回撤 | -27.93% (high risk) | > -30% | PASS |
| Relative Calmar | 0.43 (fail) | >= 0.5 | FAIL |
| 2025-2026 excess | 4.38% | > 0 | PASS |
| 月度换手率 | 88.2% | < 50% | FAIL |

**Verdict: FAIL** (5/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 0.04% | 50.0% |
| 2023 | 12 | -9.10% | 58.3% |
| 2024 | 12 | -6.33% | 58.3% |
| 2025 | 12 | 115.13% | 91.7% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | -5.21% |
| IR | -0.22 |
| Win Rate | 55.6% |
| Relative Calmar (ex-2025) | 0.19 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 12 | 0.16% | 50.0% |
| 2023 Mixed | 12 | -0.65% | 58.3% |
| 2024 Pre-924 | 9 | 0.68% | 66.7% |
| 2024 Post-924 | 3 | -3.92% | 33.3% |
| 2025-2026 Bull | 16 | 4.38% | 75.0% |

### LB5_Top3_aw

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 35.52% | > 3% | PASS |
| 信息比率 | 1.18 | > 0.3 | PASS |
| 月度 win rate | 59.6% | > 55% | PASS |
| 最大相对回撤 | -26.59% (high risk) | > -30% | PASS |
| Relative Calmar | 1.34 (good) | >= 0.5 | PASS |
| 2025-2026 excess | 7.72% | > 0 | PASS |
| 月度换手率 | 87.6% | < 50% | FAIL |

**Verdict: PASS** (7/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 10.67% | 50.0% |
| 2023 | 12 | 1.14% | 41.7% |
| 2024 | 12 | 8.21% | 58.3% |
| 2025 | 12 | 217.06% | 83.3% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 6.59% |
| IR | 0.38 |
| Win Rate | 50.0% |
| Relative Calmar (ex-2025) | 0.25 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 12 | 1.06% | 50.0% |
| 2023 Mixed | 12 | 0.42% | 41.7% |
| 2024 Pre-924 | 9 | 1.41% | 66.7% |
| 2024 Post-924 | 3 | -1.07% | 33.3% |
| 2025-2026 Bull | 16 | 7.72% | 81.2% |

### LB5_Top5_ew

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 10.77% | > 3% | PASS |
| 信息比率 | 0.68 | > 0.3 | PASS |
| 月度 win rate | 59.6% | > 55% | PASS |
| 最大相对回撤 | -19.79% (acceptable) | > -30% | PASS |
| Relative Calmar | 0.54 (minimum) | >= 0.5 | PASS |
| 2025-2026 excess | 2.86% | > 0 | PASS |
| 月度换手率 | 80.8% | < 50% | FAIL |

**Verdict: FAIL** (6/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 7.54% | 58.3% |
| 2023 | 12 | -4.41% | 50.0% |
| 2024 | 12 | -1.59% | 58.3% |
| 2025 | 12 | 75.02% | 83.3% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 0.39% |
| IR | 0.10 |
| Win Rate | 55.6% |
| Relative Calmar (ex-2025) | 0.02 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 12 | 0.73% | 58.3% |
| 2023 Mixed | 12 | -0.28% | 50.0% |
| 2024 Pre-924 | 9 | 0.59% | 66.7% |
| 2024 Post-924 | 3 | -2.00% | 33.3% |
| 2025-2026 Bull | 16 | 2.86% | 68.8% |

### LB5_Top5_aw

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 37.00% | > 3% | PASS |
| 信息比率 | 1.47 | > 0.3 | PASS |
| 月度 win rate | 71.2% | > 55% | PASS |
| 最大相对回撤 | -18.19% (acceptable) | > -30% | PASS |
| Relative Calmar | 2.03 (strong) | >= 0.5 | PASS |
| 2025-2026 excess | 5.85% | > 0 | PASS |
| 月度换手率 | 83.1% | < 50% | FAIL |

**Verdict: PASS** (7/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 23.55% | 75.0% |
| 2023 | 12 | 7.49% | 58.3% |
| 2024 | 12 | 25.00% | 66.7% |
| 2025 | 12 | 154.39% | 91.7% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 18.40% |
| IR | 1.04 |
| Win Rate | 66.7% |
| Relative Calmar (ex-2025) | 1.01 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 12 | 1.92% | 75.0% |
| 2023 Mixed | 12 | 0.74% | 58.3% |
| 2024 Pre-924 | 9 | 2.39% | 77.8% |
| 2024 Post-924 | 3 | 0.71% | 33.3% |
| 2025-2026 Bull | 16 | 5.85% | 81.2% |

### LB20_Top3_ew

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 25.68% | > 3% | PASS |
| 信息比率 | 1.07 | > 0.3 | PASS |
| 月度 win rate | 54.9% | > 55% | FAIL |
| 最大相对回撤 | -23.75% (high risk) | > -30% | PASS |
| Relative Calmar | 1.08 (good) | >= 0.5 | PASS |
| 2025-2026 excess | 6.41% | > 0 | PASS |
| 月度换手率 | 80.0% | < 50% | FAIL |

**Verdict: FAIL** (5/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -6.43% | 54.5% |
| 2023 | 12 | 13.19% | 50.0% |
| 2024 | 12 | -4.89% | 33.3% |
| 2025 | 12 | 138.47% | 83.3% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 0.44% |
| IR | 0.12 |
| Win Rate | 45.7% |
| Relative Calmar (ex-2025) | 0.02 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 11 | -0.26% | 54.5% |
| 2023 Mixed | 12 | 1.19% | 50.0% |
| 2024 Pre-924 | 9 | -0.52% | 33.3% |
| 2024 Post-924 | 3 | 0.20% | 33.3% |
| 2025-2026 Bull | 16 | 6.41% | 75.0% |

### LB20_Top3_aw

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 45.29% | > 3% | PASS |
| 信息比率 | 1.28 | > 0.3 | PASS |
| 月度 win rate | 52.9% | > 55% | FAIL |
| 最大相对回撤 | -24.71% (high risk) | > -30% | PASS |
| Relative Calmar | 1.83 (strong) | >= 0.5 | PASS |
| 2025-2026 excess | 8.31% | > 0 | PASS |
| 月度换手率 | 84.7% | < 50% | FAIL |

**Verdict: FAIL** (6/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -14.85% | 27.3% |
| 2023 | 12 | 33.95% | 58.3% |
| 2024 | 12 | 25.98% | 41.7% |
| 2025 | 12 | 191.86% | 75.0% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 13.75% |
| IR | 0.57 |
| Win Rate | 42.9% |
| Relative Calmar (ex-2025) | 0.56 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 11 | -1.01% | 27.3% |
| 2023 Mixed | 12 | 2.95% | 58.3% |
| 2024 Pre-924 | 9 | 0.39% | 33.3% |
| 2024 Post-924 | 3 | 7.56% | 66.7% |
| 2025-2026 Bull | 16 | 8.31% | 75.0% |

### LB20_Top5_ew

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 15.40% | > 3% | PASS |
| 信息比率 | 0.82 | > 0.3 | PASS |
| 月度 win rate | 56.9% | > 55% | PASS |
| 最大相对回撤 | -26.48% (high risk) | > -30% | PASS |
| Relative Calmar | 0.58 (minimum) | >= 0.5 | PASS |
| 2025-2026 excess | 4.59% | > 0 | PASS |
| 月度换手率 | 74.4% | < 50% | FAIL |

**Verdict: FAIL** (6/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -14.10% | 36.4% |
| 2023 | 12 | 18.12% | 58.3% |
| 2024 | 12 | -10.60% | 41.7% |
| 2025 | 12 | 95.47% | 91.7% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | -2.86% |
| IR | -0.07 |
| Win Rate | 45.7% |
| Relative Calmar (ex-2025) | 0.11 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 11 | -1.04% | 36.4% |
| 2023 Mixed | 12 | 1.51% | 58.3% |
| 2024 Pre-924 | 9 | -1.37% | 33.3% |
| 2024 Post-924 | 3 | 0.59% | 66.7% |
| 2025-2026 Bull | 16 | 4.59% | 81.2% |

### LB20_Top5_aw

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 45.99% | > 3% | PASS |
| 信息比率 | 1.52 | > 0.3 | PASS |
| 月度 win rate | 64.7% | > 55% | PASS |
| 最大相对回撤 | -18.36% (acceptable) | > -30% | PASS |
| Relative Calmar | 2.51 (strong) | >= 0.5 | PASS |
| 2025-2026 excess | 7.47% | > 0 | PASS |
| 月度换手率 | 74.4% | < 50% | FAIL |

**Verdict: PASS** (7/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -3.40% | 45.5% |
| 2023 | 12 | 44.32% | 66.7% |
| 2024 | 12 | 18.76% | 50.0% |
| 2025 | 12 | 177.67% | 91.7% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 18.99% |
| IR | 0.85 |
| Win Rate | 54.3% |
| Relative Calmar (ex-2025) | 1.03 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 11 | -0.09% | 45.5% |
| 2023 Mixed | 12 | 3.40% | 66.7% |
| 2024 Pre-924 | 9 | 0.25% | 33.3% |
| 2024 Post-924 | 3 | 5.51% | 100.0% |
| 2025-2026 Bull | 16 | 7.47% | 87.5% |

### LB60_Top3_ew

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 17.83% | > 3% | PASS |
| 信息比率 | 0.77 | > 0.3 | PASS |
| 月度 win rate | 55.1% | > 55% | PASS |
| 最大相对回撤 | -14.88% (acceptable) | > -30% | PASS |
| Relative Calmar | 1.20 (good) | >= 0.5 | PASS |
| 2025-2026 excess | 4.13% | > 0 | PASS |
| 月度换手率 | 47.9% | < 50% | PASS |

**Verdict: PASS** (7/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | -10.51% | 55.6% |
| 2023 | 12 | 18.09% | 58.3% |
| 2024 | 12 | -0.03% | 41.7% |
| 2025 | 12 | 102.65% | 75.0% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 3.05% |
| IR | 0.25 |
| Win Rate | 51.5% |
| Relative Calmar (ex-2025) | 0.21 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 9 | -0.66% | 55.6% |
| 2023 Mixed | 12 | 1.51% | 58.3% |
| 2024 Pre-924 | 9 | -0.06% | 33.3% |
| 2024 Post-924 | 3 | 0.71% | 66.7% |
| 2025-2026 Bull | 16 | 4.13% | 62.5% |

### LB60_Top3_aw

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 56.55% | > 3% | PASS |
| 信息比率 | 1.39 | > 0.3 | PASS |
| 月度 win rate | 67.3% | > 55% | PASS |
| 最大相对回撤 | -21.15% (high risk) | > -30% | PASS |
| Relative Calmar | 2.67 (strong) | >= 0.5 | PASS |
| 2025-2026 excess | 8.32% | > 0 | PASS |
| 月度换手率 | 46.5% | < 50% | PASS |

**Verdict: PASS** (8/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | 8.65% | 55.6% |
| 2023 | 12 | 37.65% | 75.0% |
| 2024 | 12 | 30.86% | 66.7% |
| 2025 | 12 | 200.74% | 75.0% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 26.69% |
| IR | 0.91 |
| Win Rate | 66.7% |
| Relative Calmar (ex-2025) | 1.26 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 9 | 0.92% | 55.6% |
| 2023 Mixed | 12 | 3.19% | 75.0% |
| 2024 Pre-924 | 9 | 1.53% | 55.6% |
| 2024 Post-924 | 3 | 6.00% | 100.0% |
| 2025-2026 Bull | 16 | 8.32% | 68.8% |

### LB60_Top5_ew

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 6.85% | > 3% | PASS |
| 信息比率 | 0.44 | > 0.3 | PASS |
| 月度 win rate | 53.1% | > 55% | FAIL |
| 最大相对回撤 | -16.44% (acceptable) | > -30% | PASS |
| Relative Calmar | 0.42 (fail) | >= 0.5 | FAIL |
| 2025-2026 excess | 2.50% | > 0 | PASS |
| 月度换手率 | 44.6% | < 50% | PASS |

**Verdict: FAIL** (5/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | -23.77% | 44.4% |
| 2023 | 12 | 22.35% | 66.7% |
| 2024 | 12 | -9.38% | 41.7% |
| 2025 | 12 | 58.12% | 66.7% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | -3.58% |
| IR | -0.12 |
| Win Rate | 51.5% |
| Relative Calmar (ex-2025) | 0.22 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 9 | -2.11% | 44.4% |
| 2023 Mixed | 12 | 1.79% | 66.7% |
| 2024 Pre-924 | 9 | -0.83% | 44.4% |
| 2024 Post-924 | 3 | -0.29% | 33.3% |
| 2025-2026 Bull | 16 | 2.50% | 56.2% |

### LB60_Top5_aw

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 35.58% | > 3% | PASS |
| 信息比率 | 1.29 | > 0.3 | PASS |
| 月度 win rate | 59.2% | > 55% | PASS |
| 最大相对回撤 | -19.53% (acceptable) | > -30% | PASS |
| Relative Calmar | 1.82 (strong) | >= 0.5 | PASS |
| 2025-2026 excess | 5.42% | > 0 | PASS |
| 月度换手率 | 45.4% | < 50% | PASS |

**Verdict: PASS** (8/8 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | 7.97% | 55.6% |
| 2023 | 12 | 28.13% | 50.0% |
| 2024 | 12 | 15.78% | 58.3% |
| 2025 | 12 | 117.81% | 75.0% |

#### Ex-2025 (2022-2024 only)

| Metric | Value |
|--------|-------|
| 年化超额 | 17.86% |
| IR | 0.83 |
| Win Rate | 54.5% |
| Relative Calmar (ex-2025) | 0.91 |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 9 | 0.74% | 55.6% |
| 2023 Mixed | 12 | 2.38% | 50.0% |
| 2024 Pre-924 | 9 | 0.41% | 44.4% |
| 2024 Post-924 | 3 | 4.48% | 100.0% |
| 2025-2026 Bull | 16 | 5.42% | 68.8% |

---

## 5. Variant Comparison Matrix

| Variant | Ann. Excess | IR | Win Rate | Max Rel DD | Tier | Rel.Calmar | C-Tier | Turnover | Verdict |
|---------|------------|-----|----------|------------|------|------------|--------|----------|---------|
| LB5_Top3_ew | 12.09% | 0.66 | 61.5% | -27.93% | high risk | 0.43 | fail | 88.2% | FAIL |
| LB5_Top3_aw | 35.52% | 1.18 | 59.6% | -26.59% | high risk | 1.34 | good | 87.6% | PASS |
| LB5_Top5_ew | 10.77% | 0.68 | 59.6% | -19.79% | acceptable | 0.54 | minimum | 80.8% | FAIL |
| LB5_Top5_aw | 37.00% | 1.47 | 71.2% | -18.19% | acceptable | 2.03 | strong | 83.1% | PASS |
| LB20_Top3_ew | 25.68% | 1.07 | 54.9% | -23.75% | high risk | 1.08 | good | 80.0% | FAIL |
| LB20_Top3_aw | 45.29% | 1.28 | 52.9% | -24.71% | high risk | 1.83 | strong | 84.7% | FAIL |
| LB20_Top5_ew | 15.40% | 0.82 | 56.9% | -26.48% | high risk | 0.58 | minimum | 74.4% | FAIL |
| LB20_Top5_aw | 45.99% | 1.52 | 64.7% | -18.36% | acceptable | 2.51 | strong | 74.4% | PASS |
| LB60_Top3_ew | 17.83% | 0.77 | 55.1% | -14.88% | acceptable | 1.20 | good | 47.9% | PASS |
| LB60_Top3_aw | 56.55% | 1.39 | 67.3% | -21.15% | high risk | 2.67 | strong | 46.5% | PASS |
| LB60_Top5_ew | 6.85% | 0.44 | 53.1% | -16.44% | acceptable | 0.42 | fail | 44.6% | FAIL |
| LB60_Top5_aw | 35.58% | 1.29 | 59.2% | -19.53% | acceptable | 1.82 | strong | 45.4% | PASS |

---

## 6. Ex-2025 Analysis — Removing the Tech Rally

All variants are 2025-dominated (annualized excess 58-217%). This section presents 2022-2024 only.

| Variant | Ex-2025 Ann.Excess | Ex-2025 IR | Ex-2025 Win | Ex-2025 Calmar | Full Calmar |
|---------|-------------------|------------|-------------|----------------|-------------|
| LB5_Top3_ew | -5.21% | -0.22 | 55.6% | 0.19 | 0.43 |
| LB5_Top3_aw | 6.59% | 0.38 | 50.0% | 0.25 | 1.34 |
| LB5_Top5_ew | 0.39% | 0.10 | 55.6% | 0.02 | 0.54 |
| LB5_Top5_aw | 18.40% | 1.04 | 66.7% | 1.01 | 2.03 |
| LB20_Top3_ew | 0.44% | 0.12 | 45.7% | 0.02 | 1.08 |
| LB20_Top3_aw | 13.75% | 0.57 | 42.9% | 0.56 | 1.83 |
| LB20_Top5_ew | -2.86% | -0.07 | 45.7% | 0.11 | 0.58 |
| LB20_Top5_aw | 18.99% | 0.85 | 54.3% | 1.03 | 2.51 |
| LB60_Top3_ew | 3.05% | 0.25 | 51.5% | 0.21 | 1.20 |
| LB60_Top3_aw | 26.69% | 0.91 | 66.7% | 1.26 | 2.67 |
| LB60_Top5_ew | -3.58% | -0.12 | 51.5% | 0.22 | 0.42 |
| LB60_Top5_aw | 17.86% | 0.83 | 54.5% | 0.91 | 1.82 |

---

## 7. 2025 Industry Concentration Check

Checking whether excess is concentrated in 1-2 industries (TASK.md stop condition S6).

| Industry | Total Selections (all variants) |
|----------|-------------------------------|
| 通信设备 | 70 |
| 小金属 | 64 |
| 元器件 | 55 |
| 铜 | 46 |
| 化学制药 | 44 |
| 铝 | 34 |
| 半导体 | 34 |
| 黄金 | 30 |
| 软件服务 | 27 |
| 化工原料 | 27 |

**Top 2 industries account for 26.1% of 2025 selections.**
✅ S6 not triggered (< 60%).

---

## 8. Static Sector Hold Comparison

Does rotation add value vs simply holding the best-performing sectors?

| Sector | 2024 Ann.Ret | 2025 Ann.Ret | 2024-2025 Cum.Ret |
|--------|-------------|-------------|--------------------|
| 半导体 | 35.89% | 41.57% | 87.71% |
| 元器件 | 40.59% | 56.40% | 113.48% |
| 通信设备 | 61.94% | 179.68% | 328.31% |
| 软件服务 | 9.28% | 5.40% | 14.56% |
| IT设备 | 33.16% | 15.07% | 50.74% |
| 电气设备 | 8.17% | 36.73% | 45.80% |

**Comparison**: Static hold of top tech sectors vs rotation top-3.
If rotation underperforms static hold of 半导体 or 通信设备, it is not adding timing value.

---

## 9. Stop Conditions Check (Re-evaluated)


### LB5_Top3_aw

- ✅ No stop conditions triggered

### LB5_Top5_aw

- ✅ No stop conditions triggered

### LB20_Top5_aw

- ✅ No stop conditions triggered

### LB60_Top3_ew

- ✅ No stop conditions triggered

### LB60_Top3_aw

- ✅ No stop conditions triggered

### LB60_Top5_aw

- ✅ No stop conditions triggered

---

## 10. Final Verdict (Two-Tier)

### Tier 1: Technical Pass (New Thresholds)

6/12 variants pass under revised rules:

- **LB5_Top3_aw**: Ann.Excess=35.52%, Rel.Calmar=1.34, Ex-2025=6.59%
- **LB5_Top5_aw**: Ann.Excess=37.00%, Rel.Calmar=2.03, Ex-2025=18.40%
- **LB20_Top5_aw**: Ann.Excess=45.99%, Rel.Calmar=2.51, Ex-2025=18.99%
- **LB60_Top3_ew**: Ann.Excess=17.83%, Rel.Calmar=1.20, Ex-2025=3.05%
- **LB60_Top3_aw**: Ann.Excess=56.55%, Rel.Calmar=2.67, Ex-2025=26.69%
- **LB60_Top5_aw**: Ann.Excess=35.58%, Rel.Calmar=1.82, Ex-2025=17.86%

### Tier 2: Ex-2025 Sustainability Assessment

Does the strategy work when we remove the extraordinary 2025 tech rally?

6 variants show sustainable Ex-2025 performance:

- **LB5_Top3_aw**: Ex-2025 Ann.Excess=6.59%, Ex-2025 IR=0.38
- **LB5_Top5_aw**: Ex-2025 Ann.Excess=18.40%, Ex-2025 IR=1.04
- **LB20_Top3_aw**: Ex-2025 Ann.Excess=13.75%, Ex-2025 IR=0.57
- **LB20_Top5_aw**: Ex-2025 Ann.Excess=18.99%, Ex-2025 IR=0.85
- **LB60_Top3_aw**: Ex-2025 Ann.Excess=26.69%, Ex-2025 IR=0.91
- **LB60_Top5_aw**: Ex-2025 Ann.Excess=17.86%, Ex-2025 IR=0.83
### Overall Assessment

**CONDITIONAL PASS** — 6 variants pass technical criteria, 6 show Ex-2025 sustainability.
Recommendation: proceed with caution, focus on sustainable variants.

---

## Appendix: Threshold Reference

### Relative Calmar Tiers
| Tier | Range | Meaning |
|------|-------|---------|
| strong | >= 1.5 | 每1%回撤换1.5%+年化超额 |
| good | >= 1.0 | 回撤回报比合理 |
| minimum | >= 0.5 | 最低可研究门槛 |
| fail | < 0.5 | 回撤过大/超额不足 |

### Drawdown Tiers
| Tier | Range | Meaning |
|------|-------|---------|
| excellent | <= 10% | 回撤控制优秀 |
| acceptable | 10-20% | 研究阶段可接受 |
| high risk | 20-30% | 需说明风险 |
| fail | > 30% | 硬失败 |