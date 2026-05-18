# TASK — 当前唯一任务

## B1 — Industry Rotation Offline Evaluation

### 目标

验证行业级别月频轮动是否能在 HS300 股票池上产生稳定超额收益。

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
