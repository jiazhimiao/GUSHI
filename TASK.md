# TASK.md — 下一会话任务

## 标题: 推进至 paper trading 连续模拟

### 背景

- Candidate B 为当前 new_candidate_baseline (fitness=2.304)
- 单日 daily signal 已实现 (`scripts/generate_daily_signal.py`)
- 10 日 dry-run 通过，信号行为合理
- 数据已更新至 2026-05-14

### 任务

1. 实现 `--replay-last-n` 的连续持仓传递模式
2. 添加 `positions.json` 自动更新（每日信号生成后更新持仓）
3. 接入更新数据 → 生成信号 → 更新持仓的日常流程
4. 验证连续模拟 30 天以上的持仓/信号一致性

### 边界

- 不跑正式 GA
- 不改 Candidate B 参数
- 不改策略逻辑、撮合、风控、手续费、滑点
- 不接券商、不自动下单
- pullback_entry=False, rank_buffer=False

### 历史

- 2026-05-13: baseline control 对齐 + smoke + pilot
- 2026-05-13/14: Phase 1a/1b/1c + Phase 2-mini
- 2026-05-14: Candidate B 验证 + 升级 + 稳定性检查
- 2026-05-14: daily signal workflow + 数据增量更新
