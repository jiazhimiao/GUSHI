# EXECUTION.md — 本轮会话执行总结

> 会话: 2026-05-14 ~ 2026-05-15

## 用户本轮目标

1. 推进 paper trading 连续模拟 → paper-mode 日常运行
2. 使 replay 对齐 BacktestEngine
3. 实现 PaperBroker 执行层
4. 建立 paper-mode 每日状态持久化
5. 修复数据更新脚本

## 本轮实际完成

### 1. DataContext 统一 (`qts/backtest/data_context.py`)
- 创建统一数据上下文模块，pivot/breadth/cache 一次性计算
- BacktestEngine 和 replay 共享同一套缓存
- 消除了 regime_score 系统性偏差
- 修复 `pct_change(fill_method=None)` 确保回测结果不变

### 2. PaperBroker 执行层 (`qts/backtest/paper_broker.py`)
- 模拟 BrokerSimulator：quantity/lot_size/commission/stamp_tax/T+1
- check_and_execute_exits：每日 exit check 在 signal 前执行
- execute_weight_rebalance：weight → quantity 转换
- 交易事件与 BacktestEngine 100% 对齐（30/30 matching events）
- ATR exit 复现：688047 on 01-13 完全一致

### 3. paper-mode 日常工作流
- `--paper-mode --date YYYY-MM-DD`：单日生产运行
- 状态持久化：data/paper_trading/paper_state.json/papers/trades/NAV
- 安全检查：重复日期拒绝、data hash 校验、--force 覆写

### 4. Stale price tracking
- 持仓行情缺失时回退到最近可用收盘价
- paper_nav.csv：stale_position_count, stale_symbols, stale_position_value, price_status
- signal JSON：paper_positions_price_info（close/price_date/is_stale/stale_days/price_source）

### 5. 数据更新脚本整理
- incremental_update_data.py → 正式入口（增量/备份/dedup/完整性/hash）
- update_daily_data.py → LEGACY 标记（禁止日常使用）

### 6. Regime score 对齐
- 根因：报告用 p_slice 调 compute_score，策略用 _regime_raw_cache fast path
- 修复：报告复用 fast path，score 与策略完全一致

### 7. NAV position_value 修复
- price_map 从 bars_by_date 全量构建 + 缺价格时回退到最近收盘价

## 修改的文件

| 文件 | 操作 |
|------|------|
| qts/backtest/data_context.py | 新增 |
| qts/backtest/paper_broker.py | 新增 |
| scripts/generate_daily_signal.py | 大幅修改 |
| scripts/check_alignment.py | 新增 |
| scripts/diagnose_paper_trading.py | 新增 |
| scripts/diagnose_replay_vs_backtest.py | 新增 |
| scripts/incremental_update_data.py | 修改 |
| scripts/update_daily_data.py | 修改 |
| qts/backtest/engine.py | 修改 |
| .gitignore | 修改 |
| .claude/settings.local.json | 修改 |
| .claude/hooks/notify.ps1 | 新增 |

## 已验证结论

- BacktestEngine vs PaperBroker replay：交易事件 100% 对齐（30/30）
- Regime score：报告与策略一致
- 88% 一日持仓是真实策略行为（非 replay bug）
- 601689/603392 有真实行情（非停牌），本地缺失是更新脚本未拉取

## 未解决问题

- AKShare ProxyError：601689/603392 05-09~05-15 行情未补拉
- ATR exit 差异：3 笔 backtest exits 仅 1 笔被 PaperBroker 复现（entry_price 精度）
- 未提交修改较多（7 modified + 6 untracked files）
