# Cross-Sectional Alpha Ranking — 研究方案

> 版本: v1  
> 日期: 2026-05-17  
> 状态: 待评审，未实现

---

## 1. 研究动机

### 1.1 trend_breakout v2 失败根因

trend_breakout v2 的 5 轮诊断一致指向同一结论：

```
Stock-level alpha decay:  80.7% next-day-out
Within-day discrimination: 94.2% days N vs N+1 score gap ≈ 0
Daily rotation:            78% top_n changes every day
```

根因是 **单一维度评分公式** `breakout_pct × log(1+vol_boost)` 无法在同一天不同股票之间产生区分度。当仅有 ~4 只股票通过过滤器时，top_n=15 用近乎零分的垃圾填充，微小分数变化导致完整洗牌。

### 1.2 核心假设

**多维度横截面特征排序可以在每个交易日对 HS300 股票池产生有意义的 forward return 区分度。**

与 trend_breakout v2 的关键区别：

| 维度 | trend_breakout v2 | cross-sectional alpha |
|------|-------------------|----------------------|
| 信号来源 | 单维度 (breakout_pct) | 多维度 (动量/波动/量能/趋势/RS) |
| 排序方式 | 绝对阈值 → 小候选集 → 噪声排序 | 横截面 percentile rank |
| 候选池 | 突破股 (~4/天) | HS300 全部可交易股 (~294/天) |
| 区分度 | 94%天数分差≈0 | 预期每日有连续分布 |
| 稳定性 | 0.2天平均停留 | 预期 rank 持续性更高 |

---

## 2. 数据来源

### 2.1 日线行情

- 文件: `data/raw/HS300_daily.parquet`
- 形状: 5,301,302 rows × 14 cols
- 覆盖: 1990-2026, 2620 只 A 股
- 本分析使用: 2022-01-01 ~ 2026-05-15

| 字段 | 类型 | 用途 |
|------|------|------|
| symbol | str | 股票代码 |
| trade_date | str | 交易日 |
| open | float64 | 次日开盘参考 |
| high | float64 | ATR/high-low range |
| low | float64 | ATR/high-low range |
| close | float64 | 价格、动量、均线 |
| volume | float64 | 量比 |
| amount | float64 | 成交额排名 |
| adj_factor | float64 | 前复权（已 qfq） |
| is_suspended | bool | 停牌过滤 |
| limit_up | float64 | 涨停价 |
| limit_down | float64 | 跌停价 |
| is_st | bool | ST 过滤 |
| pre_close | float64 | 涨跌停判断 |

### 2.2 历史成分股

- 文件: `data/historical_constituents.json`
- 结构: `indices.HS300.quarterly` — 36 个季度快照 (2018Q1 ~ 2026Q4)
- 每个季度: 股票代码列表

### 2.3 指数行情 (RS 计算用)

- 文件: `data/raw/index/sh000300_daily.parquet`
- 覆盖: 2002-2026, 5902 行

### 2.4 交易日历

- 文件: `data/raw/calendar.parquet`
- 字段: `trade_date`, `is_trading_day`

---

## 3. 股票池与过滤

### 3.1 Universe

HS300 成分股，按季度快照切换。

### 3.2 日级过滤

每天在 universe 基础上排除：

| 过滤条件 | 实现 |
|----------|------|
| ST / *ST | `is_st == True` → 排除 |
| 停牌 | `is_suspended == True` → 排除 |
| 一字涨停 | `close >= limit_up - 1e-8` → 排除（买入不可成交） |
| 一字跌停 | `close <= limit_down + 1e-8` → 排除（卖出不可成交） |
| 上市不足 120 日 | 首次出现日期 < 120 自然日 → 排除 |
| 价格极端 | close < 2 or close > 300 → 排除 |

### 3.3 历史回溯过滤

特征计算需要历史窗口（最长 60 日），当天之前窗口内数据不足的股票在特征计算时标记 NaN，在 ranking 时排除。

---

## 4. 特征清单

所有特征基于当日收盘可得的日线数据计算，无未来函数。

### 4.1 动量 (Momentum)

| 特征名 | 公式 | 方向 |
|--------|------|------|
| ret_5d | close / close_5d_ago - 1 | higher=better |
| ret_20d | close / close_20d_ago - 1 | higher=better |
| ret_60d | close / close_60d_ago - 1 | higher=better |

### 4.2 波动率 (Volatility)

| 特征名 | 公式 | 方向 |
|--------|------|------|
| vol_20d | std(daily_ret) × sqrt(242), 20日窗口 | lower=better (?) |
| hl_range_20d | mean(high/low - 1) over 20d | lower=better |

> vol 的方向需离线验证：高波动可能含趋势动量，低波动可能是横盘。不做预设。

### 4.3 量能 (Volume/Turnover)

| 特征名 | 公式 | 方向 |
|--------|------|------|
| volume_ratio_5_20 | avg_vol_5d / avg_vol_20d | higher=better |
| amount_rank_pct | 当日成交额在 pool 中 percentile | higher=better |
| turnover_20d | avg(volume / total_shares) proxy via amount_rank | higher=better |

### 4.4 相对强度 (Relative Strength)

| 特征名 | 公式 | 方向 |
|--------|------|------|
| rs_20d | stock_ret_20d - index_ret_20d | higher=better |
| rs_60d | stock_ret_60d - index_ret_60d | higher=better |

### 4.5 趋势质量 (Trend Quality)

| 特征名 | 公式 | 方向 |
|--------|------|------|
| close_div_ma20 | close / sma(close, 20) | higher=better |
| close_div_ma60 | close / sma(close, 60) | higher=better |
| ma20_div_ma60 | sma(close, 20) / sma(close, 60) | higher=better |

### 4.6 合计

共 13 个原始特征。

不预设合成方式。首轮用每个特征独立的 cross-sectional rank 做单因子 IC 评估，筛选方向稳定、IC 显著的子集后再考虑复合。

---

## 5. 标签定义

以交易日 T 为基础，T 的收盘信息已知：

| 标签 | 定义 | 单位 |
|------|------|------|
| fwd_ret_5d | close(T+5) / close(T+1) - 1 | % |
| fwd_ret_10d | close(T+10) / close(T+1) - 1 | % |
| fwd_ret_20d | close(T+20) / close(T+1) - 1 | % |
| mae_10d | max(1 - low(T+i) / close(T+1)) for i=1..10 | % |
| hit_rate_10d | I(fwd_ret_10d > 0) | 0/1 |

> 从 close(T+1) 起算，模拟次日开盘买入。避免使用 close(T) → close(T+N) 的"当日收盘买入"假设（A 股尾盘买入更接近次日开盘成本）。

对于涨停无法买入的股票：如果 T 日涨停，T 日不入选（过滤规则已排除）。如果 T+1 涨停，该股当日无法买入，标记为"不可交易"，在主分析中排除但仍做敏感性统计。

---

## 6. 离线评估方法

### 6.1 单因子流程 (每个特征独立)

```
For each trade_date T (2022-01-01 ~ 2026-05-15):
    1. 确定当日 HS300 成分股 (季度快照)
    2. 日级过滤 (ST/停牌/涨跌停/新上市/低价)
    3. 历史回溯过滤 (≥60 日数据)
    4. 计算 13 个特征值
    5. 计算 5 个标签值 (T+5, T+10, T+20 前向收益等)
    6. 对每个特征做 cross-sectional percentile rank (0~1)
    7. 存储: (trade_date, symbol, feature_ranks, labels)

产出: feature_rank_df parquet
```

### 6.2 单因子 IC 分析

对每个特征：

```
每日 Rank IC = corr(feature_rank_t, label_t, method='spearman')
  对每个标签分别计算

输出:
  - 全期 mean IC, IC_IR (mean/std)
  - 年度 IC 均值
  - IC > 0 比例
  - top/bottom quantile fwd_ret spread (mean, t-stat)
  - IC 累积曲线
```

### 6.3 Quantile Bucket 分析

将每日 cross-sectional rank 分成 5 组：

```
Q1: top 20%  (rank 0.8~1.0)
Q2: 60-80%
Q3: 40-60%  (middle)
Q4: 20-40%
Q5: bottom 20% (rank 0~0.2)
```

对每组统计：

```
- mean/median fwd_ret_5d, 10d, 20d
- hit_rate (fwd_ret_10d > 0)
- mean MAE_10d
- Q1-Q5 spread (long-short 收益)
- 年度一致性
```

### 6.4 多特征复合（第二阶段）

仅通过单因子筛选的特征进入复合评估。

复合方式（不预设，离线比较）：
- 等权平均 rank
- IC-weighted 平均 rank
- 简单线性回归系数（在 train 期拟合，val/test 验证）

### 6.5 时间划分

| 数据集 | 时间范围 | 用途 |
|--------|----------|------|
| Train | 2022-01 ~ 2023-12 | 特征筛选、权重拟合 |
| Validation | 2024-01 ~ 2024-12 | 复合方式选择 |
| Test | 2025-01 ~ 2026-05 | 最终评估 |

### 6.6 必须对照 trend_breakout v2

对每个评估指标，必须和 trend_breakout v2 的对应指标对照：

| v2 已知问题 | cross-sectional 对应验证 |
|-------------|-------------------------|
| 94.2% 天数分差≈0 | 检查每日 rank 分布是否连续、有区分度 |
| 80.7% next-day-out | 检查 top20% rank 是否在 T+1 持续（rank autocorrelation） |
| 48.4% FB | N/A (本方法不依赖突破位) |
| 0.2 天平均停留 | 检查 top bucket 的跨日稳定性 |
| 排序噪声 | 检查相邻 rank 的实际 fwd_ret 差异是否 monotonic |

---

## 7. 通过条件

以下条件必须全部满足：

| # | 条件 | 阈值 |
|---|------|------|
| P1 | top20% fwd_ret_10d 明显高于 bottom20% | mean(Q1)-mean(Q5) > 0, t > 1.5 |
| P2 | Rank IC 多数年份为正 | ≥ 3/4 年份 IC > 0 |
| P3 | 至少 3 个自然年度方向一致 | 符号一致，量级合理 |
| P4 | top bucket MAE 不显著恶化 | Q1 MAE ≤ Q5 MAE × 1.2 |
| P5 | 信号覆盖率足够 | 日均 ≥ 50 只有效 rank 的股票 |
| P6 | 不依赖 2024 单一年份 | 去除 2024 后结论不变 |

---

## 8. 停止条件

任一条件触发则停止，不继续复合或调参：

| # | 条件 |
|---|------|
| S1 | top/bottom fwd_ret spread 接近 0 或方向不稳定（IC IR < 0.2） |
| S2 | IC 无方向或在 train/val/test 之间大幅翻转（符号翻转 ≥ 2 次） |
| S3 | 只有单一年份有效，其他年份失效 |
| S4 | top bucket MAE 显著更大（Q1 MAE > Q5 MAE × 1.5） |
| S5 | 日均有效样本 < 30 只 |

---

## 9. 预期风险

| 风险 | 概率 | 缓解 |
|------|------|------|
| A 股横截面 alpha 本身就弱 | 中 | 降低预期，只追求 >0 的稳健 IC |
| HS300 成分股太少（~294只）导致统计力不足 | 中低 | daily pooling 可累积足够样本 |
| 2022 熊市 + 2024 924 行情极端 | 中高 | 分年评估，要求跨年一致性 |
| 部分特征含未来函数（如用全期标准化） | 低 | 每日独立 rank，不跨天 |
| 幸存者偏差（成分股 snap 可能含后见之明） | 中 | 用季度快照而非实时成分 |
| 涨停不可买但统计时未排除 | 低 | 明确标记 T 日涨停股为不可交易 |

---

## 10. 输出文件规划

| 文件 | 内容 |
|------|------|
| `reports/cross_sectional_alpha_plan_20260517.md` | 本方案（当前文档） |
| `scripts/evaluate_cross_sectional_alpha.py` | 离线 evaluator 脚本 |
| `data/research/cs_alpha_feature_ranks.parquet` | 中间结果（可选保留） |
| `data/research/cs_alpha_ic_results.csv` | IC 汇总表 |
| `data/research/cs_alpha_quantile_results.csv` | Quantile bucket 统计 |
| `reports/cross_sectional_alpha_report_YYYYMMDD_HHMMSS.md` | 最终评估报告 |

---

## 11. 实施建议

### 11.1 推荐下一步

实现 `scripts/evaluate_cross_sectional_alpha.py`，分两阶段：

**Phase 1 — 单因子 IC 扫描** (~预计运行 5-10 分钟)
- 计算 13 特征 × 5 标签 × 每日 rank
- 输出 IC 汇总 + quantile bucket
- 判断是否满足 P2/P3/S1/S2

**Phase 2 — 复合评估** (仅 Phase 1 通过后)
- 等权 rank 复合
- IC-weighted 复合
- Train/val/test 评估

### 11.2 冒烟测试

参考 CLAUDE.md 第 20.1 条，正式运行前先做小样本冒烟：
- 只跑 1 个月数据 (2022-01)
- 验证 pipeline 无 KeyError / NaN / 数据对齐错误
- 输出 2-3 个特征的 IC 确认方向大致合理

### 11.3 不属于本方案的范围

- 不修改任何策略代码 (`qts/strategies/`)
- 不接入回测引擎
- 不优化参数
- 不生成交易信号
- 不写入 Parquet 数据库（仅可选中间结果）
- 纯 offline 数据分析

---

## 12. 和 trend_breakout v2 的关键差异总结

| | trend_breakout v2 | cross-sectional alpha |
|---|---|---|
| Universe | 突破股 (~4/天) | HS300 全部可交易 (~294/天) |
| Signal | single-dimension absolute score | multi-dimension relative rank |
| Discrimination | within-day score gap ≈ 0 | daily percentile → continuous distribution |
| Stability | 0.2d avg stay | rank 持续性待验证 |
| Frequency | daily rotation 78% | 待验证 |
| Alpha source | breakout only | momentum + vol + volume + trend + RS |
| Output | trade signal | ranking research → 后续可接策略 |
