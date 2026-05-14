# EXECUTION.md — 本轮已完成工作总结

> 更新: 2026-05-14

## Candidate B 稳定性验证

- 3 次跨进程运行 Candidate B，全部指标、nav_hash、trades_hash 完全一致
- 稳定性检查: **PASSED**
- 结果保存在 `data/ga_results/candidate_b_final_check_20260514_124500/`

## 确定性修复

- 问题: `set` 迭代顺序受 PYTHONHASHSEED 影响，跨进程回测不可复现
- 修复: engine.py 三处 `set` 运算加 `sorted()`；trend_breakout.py 所有 score 排序加 symbol tie-breaker
- 验证: 3 次跨进程 A 运行全部一致（83.07%, 1231 trades）

## 实验矩阵 (F/D1/D2/D3)

| 实验 | 结论 |
|:--:|------|
| F (rank buffer) | holding_scores 方向错误，收益崩溃，冻结 |
| D1 (pullback V1) | 分支未进入（regime条件bug），无效 |
| D2 (pullback no gate) | 组合层失败，伤害2023/2024，冻结 |
| D3 (pullback + gate) | gate 平台稳定但未优于A，不通过 |

## 性能优化

| 阶段 | 耗时 | 累计降幅 |
|------|--:|--:|
| 原始 | 1501s (25m) | — |
| P0 (日期索引) | 554s (9.2m) | -63% |
| P1a (调仓日过滤) | 110s (1.8m) | **-93%** |
| P2 | 暂缓 | 收益递减 |

## GA v2 开发

### Baseline 对齐

- **问题**: `BASELINE_GENES` 中 5 个策略参数使用了 TrendBreakoutStrategy 类默认值而非 JSON best_genes 优化值
- **修复**: 对齐为 GA JSON 中的真实 best_genes 值
- **验证**: `ga_optimizer_v2.py --baseline-only` 完全复现 A baseline

### Smoke 验证

- 两次 `--smoke --seed 42` 完全可复现
- baseline fitness = 1.656

### Pilot GA

- 配置: pop=12, gen=3, workers=4, seed=42
- 结论: 无 candidate 超过 baseline (fitness=1.656)
- 加入 gene_hash 去重/缓存

## 局部搜索

### Phase 1a: 单参数邻域扫描 (10 params, 45 candidates)

- **发现**: breakout_bear=35 是最强单参数改进 (fitness=1.960, +0.304)
- 多个参数存在贴边最优

### Phase 1b: 边界外扩 + 验证 (6+1 params, 27 candidates)

- **发现**: score_high=0.80 超越 breakout_bear 成为 #1 (fitness=2.017, +0.361)
- 但 score_high=0.80 仍贴 PARAM_BOUNDS 上界

### Phase 1c: score_high 外扩 + support_bear 深探 (2 params, 15 candidates)

- **确认**: score_high=0.80 是明确的内部最优（外扩到 0.90 后趋势下降）
- support_bear=3 小幅改善 (+0.053)

### Phase 2-mini: Top 3 三维网格 (3×3×3=27 combos)

- **发现**: sh=0.80 + ab=0.89 双参数组合 fitness=2.304 (+0.648)
- Calmar 从 1.244 提升到 1.720 (+38%)
- breakout_bear=35 与 score_high=0.80 冲突（单独好但组合差）

## Candidate B 验证

### 标准验证

| 指标 | A baseline | Candidate B | Δ |
|---|:---:|:---:|:---:|
| total_return | 83.07% | 84.10% | +1.03% |
| annual_return | 7.82% | 7.90% | +0.08% |
| max_drawdown | -8.06% | -8.56% | -0.50% |
| GA fitness | 1.656 | 2.304 | +0.648 |
| no_2024 | 14.91% | 17.96% | +3.05% |
| trades | 1231 | 1137 | -94 |

### 压力测试

所有压力测试（手续费×2、滑点×2、两者×2）B 均优于 A，且优势在极端压力下扩大。

### 2023 专项诊断

- B 在 2023 年退步 -2.64%（A +0.93% vs B -1.71%）
- 根因: 2023 年 2 月差异 -2.66%，score_high=0.80 过滤掉了反弹票
- 不是 bug，是更严格过滤的自然代价
- 不为此单独修策略

## Candidate B 升级

- A baseline → historical_baseline
- Candidate B → new_candidate_baseline
- 参数: score_high=0.80, atr_bear=0.89, breakout_bear=40

## CLAUDE.md 更新

- 新增 §6.6 实验输出与结果读取规范

## 当前未解决问题

1. Candidate B 需要最终稳定性检查
2. 2023 年 B 弱于 A 是已知代价，无需修补
3. pullback entry 在 D3 中未能稳定优于 A
4. 2019/2020 exposure 极低

## 关键文件

```
qts/backtest/engine.py                  — P0+P1a+determinism
qts/strategies/trend_breakout.py         — pullback/rank buffer (default off)
scripts/ga_optimizer_v2.py               — smoke + pilot + Phase 1a/1b/1c + Phase 2-mini
scripts/validate_candidate_b.py          — Candidate B 验证（含压力测试）
scripts/diagnose_2023.py                 — 2023 专项诊断
data/historical_constituents.json         — MD5 locked
data/ga_results/local_search_phase1c_*   — score_high 外扩结果
data/ga_results/local_search_phase2mini_* — 三维网格结果
data/ga_results/candidate_b_validation_* — B 验证包
data/ga_results/candidate_b_2023_diagnosis_* — 2023 诊断
```
