# QTS 项目状态报告 — 2026-05-17

## 1. 当前项目状态

### Git

- 分支: `main`
- 工作区: clean
- 领先 origin/main: 1 commit
- 最新提交: `9b18600 data: add optional tushare provider for incremental updates`

### 策略状态

| 项目 | 状态 |
|------|:--:|
| trend_breakout v2 | **已暂停** |
| Candidate B (baseline) | 保留为 historical reference |
| Tushare provider | 已接入 `incremental_update_data.py`（可选，默认仍 akshare） |
| GA / Paper Trading | **禁止启动** |

### 当前基线: Candidate B

| 指标 | 值 |
|------|--:|
| total_return | 84.10% |
| annual_return | 7.90% |
| max_drawdown | -8.56% |
| GA fitness | 2.304 |
| total_trades | 1137 |
| exposure | 18.7% |
| avg_position | 3.92% |
| score_high | 0.80 |
| atr_bear | 0.89 |
| breakout_bear | 40 |
| enable_pullback_entry | False |
| enable_rank_buffer | False |
| use_dow_filter | False |

**Historical A Baseline（参考）**

| 指标 | 值 |
|------|--:|
| total_return | 83.07% |
| max_drawdown | -8.06% |
| Calmar | 0.97 |
| total_trades | 1231 |
| score_high | 0.72 |
| atr_bear | 1.19 |

---

## 2. trend_breakout v2 最终诊断结论

### 五轮诊断实验汇总

| Round | 主题 | 核心发现 |
|-------|------|----------|
| 1 | Entry Quality Diagnosis | Signal scarcity, 48.4% FB, 78% rotation |
| 2 | 9 个单因子实验 (A/B/C/D) | 全部未通过 stop conditions |
| 3 | Signal Count Taxonomy Audit | median=40 是 bug（CONST_PATH 错误），修正后 median=1 |
| 4 | Scoring Redesign Offline (5 variants) | 全部失败，within-day discrimination ≈ 0 |
| 5 | Day-Level Gate Audit | Good day=36.9%，day gates 最多 +10pp |

### Entry Quality Diagnosis（2026-05-17 核心数据）

```
Signal scarcity:    median 1 breakout/day, P25=0
Ranking noise:      94.2% days: N vs N+1 score gap ≈ 0 (meaningless)
Daily rotation:     78% of top_n changes every day
Next-day dropout:   80.7% of new entries gone next day
False breakouts:    48.4% fall below breakout level within 5d
Avg stay in top_n:  0.2 days
```

### 根因

1. **Stock-level**: breakout alpha 衰减极快（80.7% next-day-out）
2. **Within-day**: 评分公式 `breakout_pct × log(1+vol_boost)` 无法区分同日候选股（所有同天候选分数接近）
3. **Day-level**: 即使"好日子"的 top3 前向收益中位数仍 ≈ 0%
4. **RegimeEngine**: 压缩到 0-1 持仓，无分散化能力

### 结论

当前 trend_breakout v2 alpha 结构不足。不再继续参数优化、GA 或 Paper Trading。

---

## 3. 基础设施状态

| 模块 | 状态 |
|------|:--:|
| AKShare 日线数据 | 正常 |
| Tushare 可选 provider | 已接入 |
| Parquet 本地存储 | 正常 |
| 交易日历 | 正常 |
| 历史成分股 (2022-2026) | 正常 |
| 未来函数检查 | 3/3 PASS |
| 复权确认 (qfq) | OK |
| 参数敏感度分析 | 13 参数全部 LOW/MEDIUM |
| 21 项单元测试 | 全部通过 |
| 冒烟测试基础设施 | `scripts/ga_smoke_test.py` |
| 确定性修复 | cross-process reproducible baseline |
| 性能优化 | full backtest 1501s → 110s (-93%) |
| 分环境诊断 | `qts/diagnosis/` |
| Streamlit 看板 | 5 Tab + 历史记录 + 参数存档 |

---

## 4. 待补项（来自 README.md 合规清单）

### 回测可信度（第 14 节）

| 要求 | 状态 |
|------|:--:|
| 参数扰动 | ✅ |
| 时间切片 | ✅ |
| 样本外测试 | ✅ |
| 滑点加倍 | ❌ |
| 手续费加倍 | ❌ |
| 容量限制 | ❌ |
| 牛/熊/震荡分段 | ❌ |
| 收益来源拆解 | ❌ |
| 单票贡献分析 | ❌ |

### 风控规则（第 16 节）

| 要求 | 状态 |
|------|:--:|
| PreTradeRiskManager | ✅ |
| KillSwitch | ✅ |
| 策略状态机（5 模式） | ⚠️ 仅有正常/熔断两档 |
| max_daily_loss | ❌ |
| max_order_amount_ratio_to_volume | ❌ |

### 策略方向（第 11 节）

| 策略 | 状态 |
|------|:--:|
| 11.1 平台放量突破 | ✅ `trend_breakout.py` |
| 11.2 突破后缩量回踩 | ❌ |
| 11.3 均线趋势回踩 | ❌ |
| 11.4 低波动趋势 | ❌ |
| 11.5 假突破过滤器 | ❌ |

---

## 5. 下一阶段建议

### A. 新 alpha research 方向（推荐优先）

**当前最大教训**: 突破信号的日内区分度 ≈ 0。任何只依赖单一 breakout 维度的公式
都会遇到同样的 ranking noise 问题。

按优先级:

1. **多维度横截面打分** — 不只看突破，同时 cross-sectionally rank momentum、
   volatility、turnover、RS，让同一天不同股票之间拉开差距。这是解决
   "同天所有候选股分数一样"的根本手段。

2. **趋势回踩策略 (11.3)** — 不等突破当天，等突破后回踩缩量再入场。信号频率
   更低，但假突破率应显著下降。

3. **低波动趋势策略 (11.4)** — 换 alpha 维度，避开 breakout 的日内区分度问题。

### B. 数据管线后续验证

- Tushare provider 端到端回归测试（akshare vs tushare 同段数据一致性）
- 成分股切换回测对比（引擎已加载，未系统性验证）
- 确认 `update_daily_data.py --provider akshare` 默认路径正常

### C. 项目文档 / Roadmap

- HANDOFF.md / TASK.md / EXECUTION.md 已完整总结 trend_breakout v2 诊断周期
- README.md 合规清单可更新，低优先级
- 建议精力集中在 A 方向

### 推荐下一步

**A1 — 新 alpha 方向探索**: 选 1-2 个新 alpha 维度，在 2022-2026 数据上做
offline 横截面 ranking 分析，验证日内区分度和 forward return 单调性。
不改现有策略代码，纯研究。

---

## 6. 禁止事项

- 不跑 GA
- 不进入 Paper Trading
- 不修改 trend_breakout v2 代码
- 不重建 historical_constituents.json
- 不改撮合、风控、手续费、滑点、T+1、涨跌停
- 不为了 2023 年单独修策略
