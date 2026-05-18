# Pair Walk-Forward Feasibility Recheck — 2026-05-18

> A0.5: Walk-forward pair selection + non-overlapping position simulation + beta/regime separation

---

## 1. Methodology Fixes vs A0

| 维度 | A0 (已淘汰) | A0.5 (本次) |
|------|------------|------------|
| Pair 选择 | 全样本 2022-2026 相关性 | 滚动 250 天 formation window |
| 重平衡 | 无 | 季度 (每 ~63 天) |
| 入场价 | 触发日收盘 | **T+1 open** |
| 持仓管理 | 重叠触发列表 | **非重叠 position state** |
| 退出规则 | 仅统计 | z-reversion / max-hold-60d / stop-loss -10% |
| 交易过滤 | 无 | ST / 停牌 / 涨跌停 / 流动性 / T+1 不可交易 |
| Beta 分离 | 无 | 逐笔 excess return vs HS300 |

---

## 2. Pair Universe (Walk-Forward)

### 2.1 Per-Period

| Period | Stocks | Pairs | Trades |
|--------|--------|-------|--------|
| 2023-01 | 214 | 342 | 308 |
| 2023-04 | 214 | 253 | 290 |
| 2023-07 | 220 | 225 | 126 |
| 2023-10 | 220 | 260 | 243 |
| 2024-01 | 233 | 212 | 231 |
| 2024-04 | 233 | 230 | 260 |
| 2024-07 | 244 | 256 | 304 |
| 2024-10 | 244 | 384 | 458 |
| 2025-01 | 260 | 594 | 365 |
| 2025-04 | 261 | 641 | 623 |
| 2025-07 | 267 | 814 | 910 |
| 2025-10 | 268 | 747 | 748 |
| 2026-01 | 279 | 309 | 310 |
| 2026-04 | 279 | 306 | 218 |

### 2.2 Universe 规模

| 指标 | 值 |
|------|-----|
| 总 periods | 14 (2023-01 ~ 2026-04) |
| Avg pairs/period | **398** |
| Total unique pairs traded | **1523** |
| Total trades | **5394** |

> Pair universe 数量充足 (avg 398/period >> 50 threshold)。Walk-forward 不会导致 pair 消失。

---

## 3. Trade Statistics

### 3.1 Overall

| 指标 | Raw | Excess (vs HS300) |
|------|-----|-------------------|
| N trades | 5394 | 5394 |
| Mean return | +1.41% | **+0.21%** |
| Median return | — | **-0.41%** |
| Win rate | 48.9% | **45.8%** |
| Mean hold days | 29.6 | — |
| Median hold days | 26.0 | — |

### 3.2 After Cost (30bps round-trip)

| 指标 | 值 |
|------|-----|
| Mean excess | **-0.09%** |
| Win rate | **43.7%** |

> 扣除成本后 excess 转负。信号太弱，无法覆盖基本交易成本。

### 3.3 Exit Reason

| Reason | N | Pct |
|--------|---|-----|
| period_end (窗口结束强制平仓) | 2015 | 37.4% |
| z_reversion (\|Z\|<0.5) | 1798 | 33.3% |
| max_hold (60天到期) | 931 | 17.3% |
| stop_loss (-10%) | 650 | 12.1% |

> 仅 33.3% 的交易因均值回归自然退出。37.4% 在窗口结束时被强制平仓 —— 说明持有期可能不够长，或者 z-score 回归阈值太严。

---

## 4. Year / Regime Separation

### 4.1 Year-by-Year

| Year | N | Mean Excess | Win Rate | Mean Raw |
|------|---|-------------|----------|----------|
| 2023 | 964 | **+1.31%** | **55.6%** | -0.09% |
| 2024 | 1255 | **+1.03%** | **53.9%** | +1.77% |
| 2025 | 2639 | **-0.41%** | **42.1%** | +1.65% |
| 2026 | 536 | **-1.03%** | **27.4%** | +0.18% |

### 4.2 Regime

| Regime | N | Mean Excess | Win Rate | Mean Raw |
|--------|---|-------------|----------|----------|
| 2023 Mixed | 964 | **+1.31%** | 55.6% | -0.09% |
| 2024 Pre-924 | 767 | **+1.49%** | 57.1% | +3.70% |
| 2024 Post-924 | 488 | +0.32% | 49.0% | +0.19% |
| 2025-26 Bull | 3175 | **-0.49%** | 39.7% | +1.50% |

### 4.3 Long A vs Long B

| Direction | N | Mean Excess | Win Rate |
|-----------|----|-------------|----------|
| Long A | 2758 | +0.22% | 46.2% |
| Long B | 2636 | +0.20% | 45.4% |

> 方向对称性良好 —— 两个方向的表现几乎相同。

---

## 5. Critical Findings

### 5.1 The Signal Degrades Over Time

**2023-2024 vs 2025-2026 的断层是最关键的发现**:

```
2023-2024: mean excess = +1.16%, win rate = 54.6%
2025-2026: mean excess = -0.54%, win rate = 39.4%
```

这不是参数过拟合（walk-forward 已消除全样本偏差）。可能原因:
1. **市场结构变化**: 2025 年后 A 股进入强趋势行情，均值回归策略系统性失效
2. **因子拥挤**: 2023-2024 信号有效 → 更多资金参与 → alpha 衰减
3. **HS300 扩容**: 成分股从 ~200 增加到 ~280，新进股票破坏历史相关性

### 5.2 Mean Raw Return >> Mean Excess

Raw return (1.41%) 远超 excess (0.21%)。大部分收益来自市场 beta:
- 扣除 HS300 同期收益后，几乎不剩 alpha
- Win rate 45.8% 甚至低于抛硬币

### 5.3 2023-2024 "成功" 可能只是噪声

- 2024 Pre-924 的 raw return 高达 3.70%，但 HS300 本身同期大涨
- Excess 1.49% 中可能包含因子暴露（如价值/市值），而非真正的 pair alpha

### 5.4 2025-2026 完全失效

- Win rate 39.7% (远低于 50%)
- Excess -0.49%
- **这是最关键的红旗**: walk-forward 的最近数据不支持 pair 策略

---

## 6. Pass/Fail Assessment

| # | Check | Threshold | Actual | Result |
|---|-------|-----------|--------|:------:|
| 1 | >=50 pairs/period | >=50 | 398 | PASS |
| 2 | >=3/5 yrs excess>0 | >=3 | **2/4** | FAIL |
| 3 | 2022 bear excess not neg | >0 | **N/A** | FAIL |
| 4 | Win rate > 52% (excess) | >52% | **45.8%** | FAIL |
| 5 | Mean excess > 0 after cost | >0 | **-0.09%** | FAIL |
| 6 | Avg hold <= 30d | <=30 | 29.6d | PASS |
| 7 | Top5 pairs < 30% | <30% | 1.5% | PASS |
| 8 | Non-2024 excess positive | >0 | **-0.05%** | FAIL |

**Result: 3/8 PASS**

---

## 7. Verdict

## C — FAIL. Pair direction not viable with current approach.

### 建议: 转向 B Industry Rotation

### 决策逻辑

1. Walk-forward 暴露了 A0 全样本相关性的未来函数问题
2. 2025-2026 完全失效 (excess=-0.49%, win rate=39.7%) 是最关键的红旗
3. 扣除成本后 excess 转负 (-0.09%)
4. 33% 的强制平仓率 (period_end) 说明持仓期不够或 z-score 回归不稳定
5. Pair universe 规模充足 (398 avg)，但信号质量不支持

### 什么情况下可以重新打开

如果以下任一条件满足:
- 缩短 formation window (125d) + 更频繁重建 (monthly) → 需验证是否改善 2025-2026
- 使用 cointegration test (ADF) 替代 correlation 做 pair 选择
- 行业数据补全 → 只做同行业 pair（避免跨行业伪相关）
- 加入 fundamental 约束 (同行业 + 相近市值 + 相近估值)

### 不建议继续优化的理由

- 5 个核心条件全部 FAIL
- 2025-2026 的失败不是参数微调可以修复的
- 均值回归在强趋势市场天然失效 → 需要时序判断/趋势过滤，但这回到了 v2 的失败模式

---

## 8. 产出文件

| 文件 | 状态 |
|------|:--:|
| `scripts/diagnose_pair_walkforward.py` | 新增 |
| `data/pair_walkforward_trades.csv` | 5394 trades |
| `data/pair_walkforward_periods.csv` | 14 periods |
| `reports/pair_walkforward_feasibility_recheck_20260518.md` | 当前文件 |

---

## 9. 下一阶段

**转向 B Industry Rotation**。行业级别的信噪比应高于个股 pair:

- 候选数: 28-31 行业 vs 398 pairs vs 280 个股
- 行业 beta 分解: 行业收益 = 市场 beta + 行业 alpha（无个股噪声）
- 月度频率: 匹配行业轮动节奏，降低 turnover
- 没有 pair 非重叠持仓的复杂性

或保持当前 session 收尾，将 A/B/C 方向研讨留到新 session。
