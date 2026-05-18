# TASK — 当前唯一任务

## B1 — Industry Rotation Offline Evaluation

> **状态更新 2026-05-18**: QA Review → REQUEST_CHANGES。CONDITIONAL PASS 降级为 OBSERVE。需要补充诊断。

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

## 8. B1 补充诊断（QA REQUEST_CHANGES 后）

> 2026-05-18 QA 审查结论： CONDITIONAL PASS → OBSERVE。需要补充以下诊断才能重新评估。

### 8.1 Static Hold 事前对比

```text
问题：诊断报告 Section 8 显示通信设备 static hold（328%）碾压 rotation（~57%）
      但这是事后视角 — 当时无法知道通信设备会是 2024-2025 最强行业
要求：
  - 月末仅用当时已知数据选择"最优 static hold 行业"（高动量行业）
  - 对比 rotation top-3/top-5 vs 持有单一最佳行业
  - 如果 rotation 在事前视角下仍然跑输 static hold，则 rotation 不增加价值
```

### 8.2 AW/EW 差距分解

```text
问题：AW 超额是 EW 的 2-3x，未解释
      银行（23 只）+ 证券（22 只）在 AW 中权重远高于 EW
要求：
  - 分解 AW 超额中的行业选择贡献 vs 大市值 beta 贡献
  - 对比 AW rotation vs HS300 官方指数（市值加权）
  - 如果 AW 超额主要来自大市值行业集中，则不属于轮动 alpha
```

### 8.3 EW-only 诊断

```text
问题：EW 变体 Ex-2025 几乎全部失败（4/6 超额 < 3.05%）
      B1 前提是"行业级别收益序列信噪比 > 个股级别"
      如果 EW（最纯粹的行业 beta）不行，前提动摇
要求：
  - EW 变体 Ex-2025 是否在统计上显著 > 0
  - EW 是否在任一单一 regime 中可靠
  - 如果仅 AW 可行，B1 的"行业轮动"标签应改为"大市值行业动量"
```

### 8.4 封存条件

```text
如果以上三项诊断无法证明：
  1. rotation 在事前视角下优于 static hold
  2. EW 在 Ex-2025 有独立 alpha
  3. AW 超额不是单纯的大市值 beta
则封存 B1，写入 HANDOFF.md，不接回测。
```
