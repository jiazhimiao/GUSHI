# HANDOFF.md — QTS 项目交接文档

> 更新: 2026-05-15

---

## 1. 当前项目阶段

```
MVP 1：本地回测系统 → Paper Trading 过渡
├── ✅ deterministic A baseline 锁定（历史）
├── ✅ 性能优化 P0/P1a 完成 (1501s → 110s)
├── ✅ 分环境诊断系统
├── ✅ F/D1/D2/D3 实验完成（均冻结）
├── ✅ GA v2 baseline control 对齐
├── ✅ Candidate B 升级为 new_candidate_baseline
├── ✅ DataContext 统一 (qts/backtest/data_context.py)
├── ✅ PaperBroker 执行层 (qts/backtest/paper_broker.py)
├── ✅ Replay vs BacktestEngine 交易事件 100% 对齐
├── ✅ --paper-mode 日常运行 (state/papers/trades/NAV)
├── ✅ Stale price tracking
├── ⬜ 补拉 05-09~05-15 行情 (AKShare ProxyError)
└── ⬜ Paper-mode NAV 最终验证
├── ✅ Candidate B 3次跨进程稳定性验证通过
└── ⬜ 正式大 GA 暂缓
```

---

## 2. Current Baseline: Candidate B (new_candidate_baseline)

| 指标 | 值 |
|------|--:|
| total_return | **84.10%** |
| annual_return | **7.90%** |
| max_drawdown | -8.56% |
| calmar | 0.923 |
| total_trades | **1137** |
| exposure | 18.7% |
| avg_position | 3.92% |
| GA fitness | **2.304** |
| no_2024 | 17.96% |
| max_year_profit_pct | 72.3% |
| failed_entry_rate | 20.1% |
| **score_high** | **0.80** |
| **atr_bear** | **0.89** |
| breakout_bear | 40 (unchanged) |
| enable_pullback_entry | **False** |
| enable_rank_buffer | **False** |

### Candidate B 参数变动（vs A baseline）

| 参数 | A (historical) | B (current) |
|---|:---:|:---:|
| score_high | 0.72 | **0.80** |
| atr_bear | 1.19 | **0.89** |
| 其余 22 参数 | — | 不变 |

### 参考: Historical A Baseline

| 指标 | 值 |
|------|--:|
| total_return | 83.07% |
| annual_return | 7.82% |
| max_drawdown | -8.06% |
| calmar | 0.97 |
| total_trades | 1231 |
| GA fitness | 1.656 |

### Candidate B 升级原因

- Phase 1a/1b/1c 单参数扫描发现 score_high=0.80 是内部最优 (+0.361 fitness)
- Phase 2-mini 三维网格确认 sh=0.80 + ab=0.89 双参数组合 fitness=2.304 (+0.648)
- 所有压力测试（手续费×2 / 滑点×2 / 两者×2）B 均优于 A
- 2022 熊市回撤改善 (-6.19% → -4.92%)
- 2020 改善 (-1.61% → -0.58%)
- no_2024 改善 (14.91% → 17.96%)
- max_year_profit_pct 下降 (76.6% → 72.3%)，依赖度降低

### 已知风险

- 2023 年 B 弱于 A（+0.93% vs -1.71%，差异 -2.64%），根因是 score_high=0.80 过滤掉了 2023 年 2 月反弹票
- 这是更严格确认机制的自然代价，不为此单独修策略
- max_drawdown 微升 (-8.06% → -8.56%)，但所有年份 DD 均改善

### 数据快照

```
historical_constituents.json:  MD5 c79f9f1649895c897af28961e5d3c1fb
HS300_daily.parquet:          MD5 24a4f235925fa4de5edc9ed8fba6777f (last: 2026-05-14, 5,299,377 rows)
calendar.parquet:             MD5 e37638f5f3ac61a29603c051ceec013b
```

旧 HS300 parquet hash: `69a78859fcd6d7599aad6dbccf8da535` (last: 2026-05-08)。2026-05-14 增量更新 +1211 行，旧数据 0 变化。

### 当前阻塞

- **AKShare ProxyError**：网络故障（2026-05-15），无法拉取行情
- **601689 / 603392** 在 2026-05-11~05-15 有真实行情（AKShare 已验证 close=66.96/46.18 等），但本地 parquet 缺失（被调出 HS300 后不再拉取）
- **网络恢复后执行**：
  ```bash
  python scripts/incremental_update_data.py --start 2026-05-09 --end 2026-05-15
  ```
  此脚本自动包含 `paper_positions.json` 中的持仓股票
- **禁止**用 `update_daily_data.py` 覆盖 parquet

### 新增模块

| 模块 | 用途 |
|------|------|
| `qts/backtest/data_context.py` | 统一数据上下文（BacktestEngine + replay 共享） |
| `qts/backtest/paper_broker.py` | Paper trading broker（exit check + lot_size + T+1） |
| `scripts/incremental_update_data.py` | **正式增量更新入口**（备份/dedup/完整性/hash） |
| `data/paper_trading/` | 运行时状态目录（不提交 git）

---

## 3. 性能优化

| 阶段 | 改动 | 耗时 | 降幅 |
|------|------|--:|--:|
| 原始 | — | 1501s | — |
| P0 | `_bars_by_date` 日期索引 | 554s | -63% |
| P1a | 调仓日仅过滤当天 bars | 110s | -93% |
| P2 | execute_rebalance 优化 | — | 暂缓 |

P0 改动: `engine.py` 构建 `self._bars_by_date` dict（按日期分组 bars），替换 5 处 `self.bars[self.bars["trade_date"] == date]`

P1a 改动: `use_dow_filter=False` 时，`market_data_filtered` 从当天 bars 过滤（`today_bars[today_bars["symbol"].isin(allowed)]`）而非全量 5.3M 行

---

## 4. 实验结论

| 实验 | 状态 | 说明 |
|:--:|:--:|------|
| A | ✅ baseline | 83.07% / -8.06% / 0.97 |
| F | ❌ 冻结 | rank buffer 延长持仓但收益崩溃 |
| D1 | ❌ 无效 | pullback 分支未进入（regime 条件错误） |
| D2 | ❌ 冻结 | pullback 无 gate 伤害组合 |
| D3 | ❌ 不通过 | gate 平台稳定但未优于 A |

---

## 5. GA v2 baseline control 已对齐 ✅

**问题** (已修复): GA v2 `BASELINE_GENES` 中 5 个策略参数使用了 TrendBreakoutStrategy 类默认值而非 JSON best_genes 优化值：

| 参数 | 旧值（类默认） | 新值（JSON best_genes） |
|---|:---:|:---:|
| max_loss_pct | 0.08 | 0.14 |
| profit_lock_pct | 0.15 | 0.16 |
| atr_period | 14 | 19 |
| breadth_ma_days | 30 | 35 |
| strategy_max_dd | 0.15 | 0.18 |

**对齐后**: `ga_optimizer_v2.py --baseline-only` 完全复现 A baseline（83.07% / -8.06% / 0.97 / 1231 trades）。

**Baseline fitness (对齐后)**: `final_fitness = 1.656`（旧值 ~1.241 来自未对齐前的旧参数）。

### Smoke 验证 ✅

两次 `--smoke --seed 42` 完全可复现：排名、genes、fitness、raw_metrics 全部一致。

### Pilot GA ✅

`--pilot --pop 12 --gen 3 --workers 4 --seed 42` 完成，34 次评估，30 个唯一基因。
**结论: 无 candidate 超过 baseline (fitness=1.656)。**
非基线 candidate 试图通过提高 no_2024/recovery 得分，但 Calmar 大幅下降 + bear penalty 上升，综合 fitness 均低于 baseline。

**下一步**: 对 new_candidate_baseline 做最终稳定性检查和交接整理。

---

## 6. 新会话启动提示词

```
请读取 HANDOFF.md、CLAUDE.md、TASK.md、git status、git diff。
当前 baseline: Candidate B (score_high=0.80, atr_bear=0.89, fitness=2.304)。
已有 DataContext (qts/backtest/data_context.py) + PaperBroker (qts/backtest/paper_broker.py)。
已有 paper-mode 日常工作流 (scripts/generate_daily_signal.py --paper-mode)。
当前阻塞: AKShare ProxyError，601689/603392 05-11~05-15 行情缺失。
网络恢复后补拉: python scripts/incremental_update_data.py --start 2026-05-09 --end 2026-05-15
禁止用 update_daily_data.py 覆盖 parquet。
不要启动正式大 GA，不要扩大搜索边界，不要改策略逻辑。
目标: 按 TASK.md 继续。
```

---

## 7. Git Status

```
modified:  engine.py (P0+P1a+determinism+BUY reason)
modified:  trend_breakout.py (pullback_entry+rank_buffer+holding_scores, all default-off)
modified:  CLAUDE.md, README.md
modified:  historical_constituents.json (Sina API, quarterly)
modified:  logger.py (UTF-8 fix)
新增:     qts/diagnosis/, qts/strategies/regime_engine.py
          scripts/diagnose.py, diagnose_*.py, experiment_matrix.py
          scripts/ga_optimizer.py, ga_optimizer_v2.py, ga_smoke_test.py
          scripts/baseline_stability_check.py, verify_determinism.py
          scripts/profile_backtest.py, profile_backtest_v2.py
          scripts/compute_fitness_decomposition.py
          scripts/sweep_pb_gate.py, sweep_pb_gate_v2.py
          scripts/diagnose_pullback_funnel.py, diagnose_d2_failure.py
          scripts/diagnose_d3_prep.py, diagnose_d3c_gate.py
          data/experiments/, data/ga_results/, data/diagnosis/
```
