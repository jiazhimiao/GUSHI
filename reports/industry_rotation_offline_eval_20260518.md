# B1 — Industry Rotation Offline Evaluation

Generated: 2026-05-18 16:34
Period: 2022-01-01 ~ 2026-05-15
Mode: FULL
Cost assumption: 0.20% per monthly trade

> **Superseded note**: This initial evaluation used the old max-relative-drawdown <10% hard gate. It is retained as historical evidence. The current B1 conclusion is in `reports/industry_rotation_diagnostic_20260518.md`, which uses Relative Calmar and drawdown tiering.

---

## 1. Data Summary

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

## 2. Known Limitations

1. **行业分类后见偏差**: 行业分类为 2026-05-18 快照，回看历史时假设行业归属不变。A 股蓝筹行业变更率 < 5%/年。
2. **成分股生存偏差**: `historical_constituents.json` 仅追踪存活到当前的股票，遗漏 ~5-10% 被调出股票。
3. **复权口径**: adj_factor 全为 1.0，依赖 AKShare 默认 qfq 前复权行为。
4. **pre_close 缺失**: 几乎全部为 null，收益通过 `close.pct_change()` 计算。
5. **ST/停牌过滤**: is_st 和 is_suspended 字段基本未填充，仅依赖成分股列表过滤。

---

## 3. Evaluation Results


### LB5_Top3_ew

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| 年化超额 (扣成本) | 12.09% | > 3% | PASS |
| 信息比率 | 0.66 | > 0.3 | PASS |
| 月度 win rate | 61.5% | > 55% | PASS |
| 最大相对回撤 | -27.93% | < 10% | FAIL |
| 2025-2026 excess | 4.38% | > 0 | PASS |
| 月度换手率 | 88.2% | < 50% | FAIL |

**Verdict: FAIL** (4/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 0.04% | 50.0% |
| 2023 | 12 | -9.10% | 58.3% |
| 2024 | 12 | -6.33% | 58.3% |
| 2025 | 12 | 115.13% | 91.7% |

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
| 最大相对回撤 | -26.59% | < 10% | FAIL |
| 2025-2026 excess | 7.72% | > 0 | PASS |
| 月度换手率 | 87.6% | < 50% | FAIL |

**Verdict: FAIL** (5/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 10.67% | 50.0% |
| 2023 | 12 | 1.14% | 41.7% |
| 2024 | 12 | 8.21% | 58.3% |
| 2025 | 12 | 217.06% | 83.3% |

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
| 最大相对回撤 | -19.79% | < 10% | FAIL |
| 2025-2026 excess | 2.86% | > 0 | PASS |
| 月度换手率 | 80.8% | < 50% | FAIL |

**Verdict: FAIL** (4/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 7.54% | 58.3% |
| 2023 | 12 | -4.41% | 50.0% |
| 2024 | 12 | -1.59% | 58.3% |
| 2025 | 12 | 75.02% | 83.3% |

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
| 最大相对回撤 | -18.19% | < 10% | FAIL |
| 2025-2026 excess | 5.85% | > 0 | PASS |
| 月度换手率 | 83.1% | < 50% | FAIL |

**Verdict: FAIL** (5/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 12 | 23.55% | 75.0% |
| 2023 | 12 | 7.49% | 58.3% |
| 2024 | 12 | 25.00% | 66.7% |
| 2025 | 12 | 154.39% | 91.7% |

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
| 最大相对回撤 | -23.75% | < 10% | FAIL |
| 2025-2026 excess | 6.41% | > 0 | PASS |
| 月度换手率 | 80.0% | < 50% | FAIL |

**Verdict: FAIL** (3/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -6.43% | 54.5% |
| 2023 | 12 | 13.19% | 50.0% |
| 2024 | 12 | -4.89% | 33.3% |
| 2025 | 12 | 138.47% | 83.3% |

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
| 最大相对回撤 | -24.71% | < 10% | FAIL |
| 2025-2026 excess | 8.31% | > 0 | PASS |
| 月度换手率 | 84.7% | < 50% | FAIL |

**Verdict: FAIL** (4/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -14.85% | 27.3% |
| 2023 | 12 | 33.95% | 58.3% |
| 2024 | 12 | 25.98% | 41.7% |
| 2025 | 12 | 191.86% | 75.0% |

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
| 最大相对回撤 | -26.48% | < 10% | FAIL |
| 2025-2026 excess | 4.59% | > 0 | PASS |
| 月度换手率 | 74.4% | < 50% | FAIL |

**Verdict: FAIL** (4/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -14.10% | 36.4% |
| 2023 | 12 | 18.12% | 58.3% |
| 2024 | 12 | -10.60% | 41.7% |
| 2025 | 12 | 95.47% | 91.7% |

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
| 最大相对回撤 | -18.36% | < 10% | FAIL |
| 2025-2026 excess | 7.47% | > 0 | PASS |
| 月度换手率 | 74.4% | < 50% | FAIL |

**Verdict: FAIL** (5/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 11 | -3.40% | 45.5% |
| 2023 | 12 | 44.32% | 66.7% |
| 2024 | 12 | 18.76% | 50.0% |
| 2025 | 12 | 177.67% | 91.7% |

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
| 最大相对回撤 | -14.88% | < 10% | FAIL |
| 2025-2026 excess | 4.13% | > 0 | PASS |
| 月度换手率 | 47.9% | < 50% | PASS |

**Verdict: FAIL** (5/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | -10.51% | 55.6% |
| 2023 | 12 | 18.09% | 58.3% |
| 2024 | 12 | -0.03% | 41.7% |
| 2025 | 12 | 102.65% | 75.0% |

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
| 最大相对回撤 | -21.15% | < 10% | FAIL |
| 2025-2026 excess | 8.32% | > 0 | PASS |
| 月度换手率 | 46.5% | < 50% | PASS |

**Verdict: PASS** (6/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | 8.65% | 55.6% |
| 2023 | 12 | 37.65% | 75.0% |
| 2024 | 12 | 30.86% | 66.7% |
| 2025 | 12 | 200.74% | 75.0% |

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
| 最大相对回撤 | -16.44% | < 10% | FAIL |
| 2025-2026 excess | 2.50% | > 0 | PASS |
| 月度换手率 | 44.6% | < 50% | PASS |

**Verdict: FAIL** (4/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | -23.77% | 44.4% |
| 2023 | 12 | 22.35% | 66.7% |
| 2024 | 12 | -9.38% | 41.7% |
| 2025 | 12 | 58.12% | 66.7% |

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
| 最大相对回撤 | -19.53% | < 10% | FAIL |
| 2025-2026 excess | 5.42% | > 0 | PASS |
| 月度换手率 | 45.4% | < 50% | PASS |

**Verdict: PASS** (6/7 checks passed)


#### Year-by-Year

| Year | N Months | Ann. Excess | Win Rate |
|------|----------|-------------|----------|
| 2022 | 9 | 7.97% | 55.6% |
| 2023 | 12 | 28.13% | 50.0% |
| 2024 | 12 | 15.78% | 58.3% |
| 2025 | 12 | 117.81% | 75.0% |

#### Regime Analysis

| Regime | N | Mean Excess | Win Rate |
|--------|---|-------------|----------|
| 2022 Bear | 9 | 0.74% | 55.6% |
| 2023 Mixed | 12 | 2.38% | 50.0% |
| 2024 Pre-924 | 9 | 0.41% | 44.4% |
| 2024 Post-924 | 3 | 4.48% | 100.0% |
| 2025-2026 Bull | 16 | 5.42% | 68.8% |

---

## 4. Variant Comparison

| Variant | Ann. Excess | IR | Win Rate | Max Rel DD | Turnover | Verdict |
|---------|------------|-----|----------|------------|----------|---------|
| LB5_Top3_ew | 12.09% | 0.66 | 61.5% | -27.93% | 88.2% | FAIL |
| LB5_Top3_aw | 35.52% | 1.18 | 59.6% | -26.59% | 87.6% | FAIL |
| LB5_Top5_ew | 10.77% | 0.68 | 59.6% | -19.79% | 80.8% | FAIL |
| LB5_Top5_aw | 37.00% | 1.47 | 71.2% | -18.19% | 83.1% | FAIL |
| LB20_Top3_ew | 25.68% | 1.07 | 54.9% | -23.75% | 80.0% | FAIL |
| LB20_Top3_aw | 45.29% | 1.28 | 52.9% | -24.71% | 84.7% | FAIL |
| LB20_Top5_ew | 15.40% | 0.82 | 56.9% | -26.48% | 74.4% | FAIL |
| LB20_Top5_aw | 45.99% | 1.52 | 64.7% | -18.36% | 74.4% | FAIL |
| LB60_Top3_ew | 17.83% | 0.77 | 55.1% | -14.88% | 47.9% | FAIL |
| LB60_Top3_aw | 56.55% | 1.39 | 67.3% | -21.15% | 46.5% | PASS |
| LB60_Top5_ew | 6.85% | 0.44 | 53.1% | -16.44% | 44.6% | FAIL |
| LB60_Top5_aw | 35.58% | 1.29 | 59.2% | -19.53% | 45.4% | PASS |

---

## 5. Industry Selection Frequency (Best Variant)

| Industry | Times Selected | Pct of Months |
|----------|---------------|---------------|
| 通信设备 | 15 | 29.4% |
| 软件服务 | 14 | 27.5% |
| 元器件 | 13 | 25.5% |
| 小金属 | 13 | 25.5% |
| 半导体 | 12 | 23.5% |
| 煤炭开采 | 12 | 23.5% |
| 化工原料 | 11 | 21.6% |
| 化学制药 | 11 | 21.6% |
| IT设备 | 10 | 19.6% |
| 电气设备 | 10 | 19.6% |
| 汽车配件 | 10 | 19.6% |
| 生物制药 | 10 | 19.6% |
| 汽车整车 | 9 | 17.6% |
| 银行 | 8 | 15.7% |
| 电信运营 | 8 | 15.7% |

---

## 6. Stop Conditions Check


### LB5_Top3_ew

- ✅ No stop conditions triggered

### LB5_Top3_aw

- ✅ No stop conditions triggered

### LB5_Top5_ew

- ✅ No stop conditions triggered

### LB5_Top5_aw

- ✅ No stop conditions triggered

### LB20_Top3_ew

- ✅ No stop conditions triggered

### LB20_Top3_aw

- ✅ No stop conditions triggered

### LB20_Top5_ew

- ✅ No stop conditions triggered

### LB20_Top5_aw

- ✅ No stop conditions triggered

### LB60_Top3_ew

- ✅ No stop conditions triggered

### LB60_Top3_aw

- ✅ No stop conditions triggered

### LB60_Top5_ew

- ✅ No stop conditions triggered

### LB60_Top5_aw

- ✅ No stop conditions triggered

---

## 7. Critical Review — 2025 Excess Concentration Risk

### 7.1 The 2025 Problem

All 12 variants show **extreme annualized excess in 2025** (58-218%), far exceeding any reasonable expectation for a monthly industry rotation strategy. This requires explanation.

| Variant | 2022 Ann.Excess | 2023 Ann.Excess | 2024 Ann.Excess | 2025 Ann.Excess | 2025 Contribution |
|---------|----------------|----------------|----------------|----------------|-------------------|
| LB5_Top3_ew | 0.04% | -9.10% | -6.33% | **115.13%** | dominant |
| LB5_Top3_aw | 10.67% | 1.14% | 8.21% | **217.06%** | dominant |
| LB20_Top3_ew | -6.43% | 13.19% | -4.89% | **138.47%** | dominant |
| LB60_Top3_aw | 8.65% | 37.65% | 30.86% | **200.74%** | dominant |
| LB60_Top5_aw | 7.97% | 28.13% | 15.78% | **117.81%** | dominant |

**2022-2024 monthly mean excess (regime analysis) is in the 0-3% range**, yet the annualized figures explode to 100%+ in 2025. This is mathematically possible only if the monthly compounding and high win rates in 2025 amplify modest monthly excesses through geometric effects — OR if the signal is massively concentrated in the year's best-performing sectors.

### 7.2 Possible Explanations

1. **Sector concentration (most likely)**: 2025 was dominated by AI/semiconductor/tech and "中特估" themes. If the momentum signal consistently selected these sectors, the excess is real but represents **sector timing, not rotation alpha**. A top-3 strategy that picks 半导体 + 元器件 + IT设备 every month in 2025 is not "rotating" — it's sector-concentrated.

2. **Look-ahead bias from 2026 industry classification**: Stocks that performed well in 2025 may have been reclassified into "hot" industries by Tushare in 2026, creating an artificial alignment between historical returns and future labels.

3. **Survivorship bias**: The constituent data only tracks stocks that survived to 2026, systematically excluding stocks that were removed from HS300 (likely underperformers).

4. **Compounding overstatement**: Monthly excess compounding at 5-10%/month for 12 months yields 80-214% annualized. If 8/12 months have excess > 0 and some months have >15% excess, the geometric product can be very large.

### 7.3 Ex-2025 Sensitivity

If we conservatively cap 2025 contribution or exclude it entirely:

| Variant | Full Ann.Excess | Ex-2025 (est.) | Full IR | Ex-2025 IR |
|---------|----------------|----------------|---------|------------|
| LB60_Top3_aw | 56.55% | ~7-15% | 1.39 | ~0.3-0.5 |
| LB60_Top5_aw | 35.58% | ~3-8% | 1.29 | ~0.2-0.4 |

Without 2025, the excess returns compress dramatically and several stop conditions (S2, S3) may trigger.

### 7.4 Verdict on 2025

**The 2025 results are not trustworthy for decision-making.** The magnitude of excess (100-218% annualized) exceeds any reasonable prior for a monthly rotation strategy and is likely driven by:
- Sector concentration in AI/tech themes
- Survivorship + look-ahead bias amplification
- A single extraordinary year dominating multi-year statistics

### 7.5 Recommendations

1. **DO NOT** treat the PASS verdict on LB60_Top3_aw and LB60_Top5_aw as validation
2. **Exclude 2025** from the primary evaluation and report "Ex-2025" results as the main figures
3. **Check 2025 industry selection overlap** — compute how many months the top-3 included 半导体, 元器件, IT设备, 通信设备, 软件服务 (the 2025 tech winners)
4. **Compare to buy-and-hold 半导体 industry** — if rotation underperforms simply holding semiconductors, it's not adding value

---

## 8. Overall Verdict

**MARGINAL — FAIL** with critical reservations.

- **2/12 variants technically pass** (LB60_Top3_aw, LB60_Top5_aw), but both are **2025-dominated**
- **ALL variants fail max relative drawdown < 10%** (best: -14.88%, worst: -27.93%)
- **Short-lookback variants (5d, 20d) fail turnover < 50%** (74-88%)
- **2025 excess of 58-218% is implausible** and likely driven by sector concentration + biases
- **Ex-2025 results are modest** (estimated 3-15% annualized excess) with marginal IR

### Stop Conditions Triggered (re-evaluated)

| Condition | Status | Detail |
|-----------|--------|--------|
| S6: excess集中在1-2个行业 | **⚠️ LIKELY** | 2025 科技赛道集中 |
| S2: excess <= 0 (ex-2025) | **⚠️ MARGINAL** | EW variants negative in 2022/2024 |
| S3: IR < 0.1 (ex-2025) | **⚠️ MARGINAL** | Some variants near threshold |

### Recommended Action

**Do not proceed to formal backtest.** The industry rotation signal in its current form (simple momentum → top-K) does not produce reliable excess returns independent of 2025's extraordinary tech sector rally.

**Before re-evaluation**, the following must be addressed:
1. Run the evaluation excluding 2025 as primary results
2. Decompose 2025 excess by industry contribution
3. Compare top-3 rotation to static 半导体 buy-and-hold
4. Consider sector-neutral momentum (rank within sectors, not across)
5. Test reversal signals (short-term mean reversion) as alternatives