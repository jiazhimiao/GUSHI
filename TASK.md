# TASK — 当前唯一任务

## B1 / B2 — Closeout

> **状态更新 2026-05-19**: B1→OBSERVE/FRAGILE, B2→PAUSE/MARGINAL-FAIL。
> 行业层路线（momentum / multi-factor ranking）未解决信号薄、时间集中、小行业依赖。
> 暂停行业层方向。不进入回测或 Paper Trading。

### 当前状态

B1 (Industry Rotation → EW+AWH-IM) 和 B2 (Multi-Factor Ranking) 两个行业层方向均已 closeout。
结论：行业级别 alpha 存在但太薄，不足以支撑稳定的可交易策略。
下一步：转向个股层/行业内结构化信号，或全新方向。

---

## 1. 输入数据

```text
data/meta/industry_classification.csv
data/raw/HS300_daily.parquet
data/raw/index/sh000300_daily.parquet
data/historical_constituents.json
```

必读报告：

```text
reports/industry_classification_source_audit_20260518.md
reports/industry_classification_map_report_20260518.md
reports/industry_rotation_data_audit_plan_20260518.md
```

---

## 2. 允许事项

```text
构建 HS300 行业组合收益序列
行业内等权收益
成交额加权版本作为对照
计算行业动量、相对强度、波动率、宽度、量能
月末信号，T+1 open 建仓
月频 top-3 / top-5 行业 offline evaluation
对比 official HS300 和 HS300 equal-weight benchmark
生成 reports/industry_rotation_offline_eval_YYYYMMDD.md
```

---

## 3. 禁止事项

```text
不改 qts/strategies/
不接正式回测引擎
不跑 GA
不进入 Paper Trading
不进入正式回测（QA 已拒绝）
不写 data/raw parquet
不继续 Pair 参数优化
不使用 git add .
不 commit / push，除非用户明确确认
```

---

## 4. 评估要求

必须输出：

```text
行业数量和覆盖率
行业日收益序列质量
等权 vs 成交额加权对比
official HS300 benchmark
HS300 equal-weight benchmark
月度换手率
成本后收益
分年结果
2022 熊市
2024 924 前后
2025-2026 近期表现
最大相对回撤
信息比率
```

---

## 5. 通过条件

| 条件 | 阈值 |
|---|---:|
| 年化超额收益 | > 3%，扣成本后 |
| 信息比率 | > 0.3 |
| 分年跑赢 | 至少 3/5 年 |
| 最大相对回撤 | 风险分层，非一票否决 |
| Relative Calmar | >= 0.5 |
| 2025-2026 | 不失效，excess 不为负 |
| 月度 win rate | > 55% |
| 月度换手 | < 50% |
| 行业集中度 | top3 行业不得长期占 > 60% |

### 最大相对回撤风险分层

| 层级 | 范围 | 判定 |
|---|---|---|
| excellent | <= 10% | 回撤控制优秀 |
| acceptable | 10% ~ 20% | 研究阶段可接受 |
| high risk | 20% ~ 30% | 需说明风险 |
| fail | > 30% | 硬失败，停止 |

### Relative Calmar 分层

Relative Calmar = 年化超额(扣成本) / abs(最大相对回撤)

| 层级 | 阈值 | 判定 |
|---|---|---|
| 最低可研究 | >= 0.5 | 每 1% 回撤至少换 0.5% 年化超额 |
| 较好 | >= 1.0 | 回撤回报比合理 |
| 强 | >= 1.5 | 回撤回报比优秀 |

---

## 6. 停止条件

任一触发则停止，不接回测：

```text
excess <= 0
IR < 0.1
2025-2026 excess < 0
只在单一年份有效
收益集中在 1-2 个行业
成本后失效
最大相对回撤 > 30%
数据覆盖/行业组合质量不足
```

---

## 7. 预期输出

```text
reports/industry_rotation_offline_eval_YYYYMMDD.md
必要时新增 scripts/evaluate_industry_rotation.py
```

若新增脚本，必须同步 `FILE_INVENTORY.md`。

---

## 8. 补充诊断完成（2026-05-19 三诊断闭环）

### 8.1 Static Hold Ex-Ante ✅
- Rotation 4/4 splits 优于 ex-ante static hold
- Static hold 不再阻塞 B1
- 脚本：`scripts/diagnose_b1_static_hold.py`
- 报告：`reports/b1_static_hold_diagnostic_20260518.md`

### 8.2 AW/EW 2×2 Decomposition ✅
- AW/EW gap 87-97% 来自 holding weight effect
- EA (EW signal + AW holding) > AA in 4/5 splits
- EW signal 是更好的行业选择器，AW holding 是必要放大器
- 脚本：`scripts/diagnose_b1_aw_ew_decomposition.py`
- 报告：`reports/b1_aw_ew_decomposition_20260518.md`

### 8.3 EW-Only Stability ✅
- 0/24 variants pass Ex-2025 Rel.Calmar >= 0.5
- EW signal alone insufficient → must pair with AW holding
- LB60-120 + Top3-5 + MinStk3 is the viable region
- 脚本：`scripts/diagnose_b1_ew_only.py`
- 报告：`reports/b1_ew_only_diagnostic_20260518.md`

### 8.4 综合判定

```text
✅ Rotation > static hold (ex-ante)
✅ EA > AA (EW signal + AW holding 最优)
❌ EW-only 不独立通过 Ex-2025 Calmar gate
→ B1 REDEFINED as EW Signal + AW Holding
→ CONDITIONAL PASS，不封存
```

---

## 9. B1 Final Summary

> 2026-05-19: robustness QA → OBSERVE/FRAGILE。B1 演化结束。

## 10. B2 Closeout

> 2026-05-19: B2 Phase 1 QA → PAUSE / MARGINAL-FAIL。

### 结果

| 指标 | 值 |
|---|---|
| 最佳变体 | B2-C Top5 MinStk3 EW, RC=0.74 |
| vs B1 baseline | WIN on RC (0.74 > 0.63) |
| T10% 月份贡献 | 99% >> 80% gate |
| MinStk=5 通过 | 0/6 variants |
| MinStk=3 通过 | 1/6 variants |

### 结论

多因子排名没有解决行业层信号薄、时间集中、小行业依赖的核心问题。因子确实正交（max |r|=0.37），但 alpha 本身太弱，无法通过因子组合弥补。

### 禁止事项

```text
不继续 B2 参数扩展
不补 capped_aw 版本
不跑 GA
不进入 Paper Trading
不进入正式回测
```

### 下一步

暂停行业层路线（B1+B2）。转向个股层/行业内结构化信号，或全新方向。

### 保守标准配置（research observation only）

```text
Signal:     EW industry momentum, LB60
Selection:  Top3 industries
Holding:    capped AW, 20% single-stock limit
MinStocks:  3 (load-bearing constraint)
Additional: require >= 1 selected industry to have >= 8 stocks
Cost:       20 bps/month
Benchmark:  HS300 equal-weight
Status:     RESEARCH OBSERVATION — NOT a trading strategy
```

### 后续选择

```text
Option A: 暂停 B1，转向新信号结构
Option B: 保留该配置作为观察 benchmark，不主动开发
```

### 禁止事项

```text
不进入正式回测
不进入 Paper Trading
不跑 GA
不继续 robustness validation
不改 data/raw
不改策略代码
```
