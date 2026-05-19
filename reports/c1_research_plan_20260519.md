# C1 — Industry-Inside Stock Selection 研究计划

> 2026-05-19 | Agent Teams 执行 | qts-strategy-dev + qts-qa-reviewer + qts-safety-reviewer

---

## 1. 执行模式

```
Execution mode: Agent Teams (3 independent spawns)
Lead: main session
Teammates:
  - qts-strategy-dev → PROCEED (有条件)
  - qts-qa-reviewer   → REQUEST_CHANGES (7项修正)
  - qts-safety-reviewer → NEEDS_SAFEGUARDS (4项修正)
```

---

## 2. 背景

- B1 = OBSERVE / FRAGILE（EW+AWH-IM，cap_20 RC=0.63，T10%=113.6%）
- B2 = PAUSE / MARGINAL-FAIL（多因子 RC=0.74 但 T10%=99%）
- 行业层 alpha 存在但太薄。转向行业内选股。
- 行业只作为上下文/分群维度，不直接交易行业。

---

## 3. 三个候选信号

### C1-A: 行业内相对强度（先测）
```
signal_i = stock_60d_mom - industry_ew_mom
选择: Top-20 / Top-10 跨行业, EW holding
```
- 最简单，直接对标 B1
- 1 个自由度（60d lookback）

### C1-B: 行业内趋势质量（C1-A 通过后才测）
```
趋势效率 + up-day ratio + 回撤恢复 → z-score → industry-relative
选择: Top-20 EW
```

### C1-C: 行业内量价确认（C1-A 通过后才测）
```
量价确认动量 + amount share trend → z-score → industry-relative
选择: Top-20 EW
```

---

## 4. 共同框架

| 维度 | 内容 |
|---|---|
| 股票池 | HS300 PIT 成分股（historical_constituents.json） |
| 频率 | 月末信号，T+1 open 建仓 |
| 成本 | 20 bps/月 |
| 基准 | HS300 equal-weight + B1 cap_20 (RC=0.63) |
| 过滤 | 无ST、无停牌(vol=0)、无涨跌停、上市≥60天、行业MinStk≥3 |
| 行业分类 | 已知偏差：当前快照用于历史期，需标注 |

---

## 5. 评估 Gate（修正后）

| Gate | 阈值 | 优先级 |
|---|---|---|
| Ex-2025 Rel.Calmar | >= 1.0 | MUST |
| 信息比率 | > 0.3 | MUST |
| 月度 win rate | > 55% | MUST |
| 月度 turnover | < 50% | MUST |
| 最大相对回撤 | > -30% hard fail | MUST |
| 2024-only excess | > 0% | MUST |
| T10% 月份贡献 | < 80% | MUST |
| 单行业贡献 | < 50% | SHOULD |
| 单股票贡献 | < 30% | SHOULD |
| MinStk=5 RC衰减 | > 50% of MinStk=3 RC | MUST |
| C1-A T10%>80% | 不进入 C1-B/C1-C | MUST |

---

## 6. 停止条件

```
任一触发则停止，不接回测/GA/Paper Trading：
- Ex-2025 RC < 1.0
- 2024-only excess <= 0
- T10% > 80%
- 收益集中在少数月份/股票/行业
- 成本后失效
- MinStk=5 RC 衰减 > 50%
- 不进入正式回测 / Paper Trading / GA
- 不改 qts/strategies/ / data/raw/
```

---

## 7. 执行顺序

```
Phase 1a: 方差分解诊断（行业 vs residual，不阻塞）
Phase 1b: C1-A Top-20
Phase 1c: C1-A Top-10
Phase 1d: C1-B Top-20（仅 C1-A 通过全部 gate）
Phase 1e: C1-C Top-20（仅 C1-A 通过全部 gate）
```

参数上限：每维度 ≤3 个值，总维度 ≤3，禁止 GA。

---

## 8. 修正来源

### QA Reviewer 要求（7项）
1. RC gate: 0.63 → >= 1.0
2. 行业分类 look-ahead 文档化
3. PIT 成分股过滤明确
4. 缺失 gate: IR, win rate, turnover, max DD, 行业聚类
5. MinStk=5 敏感性 gate
6. B2 教训 gate: C1-A T10%>80% → 不进入 composite
7. Phase 1a: 二元阻断 → 分层诊断

### Safety Reviewer 要求（4项）
1. C1 停止条件写入
2. 参数 ceiling 定义
3. research-only 标签
4. 写入隔离确认

---

## 9. 保留风险

1. 行业分类 look-ahead bias（当前快照用于历史期）
2. 小行业 z-score 不可靠（13/80 行业 3-4 只股票）
3. 行业内 alpha 可能不比行业间 alpha 强（核心假设未验证）
4. Phase 1a 方差分解可能显示行业因子主导（>60%）

---

## 10. 下一步

待用户确认修正后的 C1 计划。确认后开始 Phase 1a + C1-A 实现。
