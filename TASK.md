# TASK.md — 当前任务状态

## 当前阶段: Paper Trading 日常运行 + 数据保障

### 已完成

- [x] DataContext 统一（`qts/backtest/data_context.py`）
- [x] PaperBroker 执行层模拟（`qts/backtest/paper_broker.py`）
- [x] Replay vs BacktestEngine 交易事件 100% 对齐
- [x] `--paper-mode` 每日运行（state/papers/trades/NAV 持久化）
- [x] Regime score 与策略完全对齐（使用 `_regime_raw_cache` fast path）
- [x] Stale price tracking（stale_days, price_source, DATA GAP 警告）
- [x] 数据更新脚本整理（`incremental_update_data.py` = 正式入口）

### 当前阻塞

- **AKShare ProxyError**：网络故障，无法补拉 2026-05-09 ~ 05-15 行情
- 601689 / 603392 在 05-11~05-15 有真实行情（AKShare 已确认），但本地 parquet 缺失
- 网络恢复后用 `incremental_update_data.py` 补拉后 paper-mode NAV 即可恢复正常

### 待办

- [ ] 网络恢复后：`python scripts/incremental_update_data.py --start 2026-05-09 --end 2026-05-15`
- [ ] 重跑 2026-05-08 → 2026-05-14 paper-mode 演示，验证 NAV 无 stale
- [ ] PaperBroker exit simulation 完善（当前复现 1/3 ATR exits）
- [ ] Paper-mode DataContext 缓存复用（避免每日重建，~60s → ~1s）

### 边界

- 不跑正式 GA
- 不改 Candidate B 参数
- 不改策略逻辑、撮合、风控、手续费、滑点
- 不接券商、不自动下单
- 不实现 hysteresis / cooldown / smoothing
- 禁止用 `update_daily_data.py` 覆盖 parquet

### 历史

- 2026-05-13: baseline control 对齐 + smoke + pilot
- 2026-05-14: Candidate B 验证 + 升级 + 稳定性检查
- 2026-05-14: daily signal workflow + 数据增量更新
- 2026-05-14: DataContext 统一 + PaperBroker 执行层
- 2026-05-15: paper-mode 日常工作流 + stale tracking + 数据脚本整理
