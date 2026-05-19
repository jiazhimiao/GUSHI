# Turnover 诊断 — 完成总结

> 2026-05-19 | L2 诊断任务 | 只读审计 + 诊断脚本

---

## 1. 读取的文件

| 文件 | 角色 |
|---|---|
| `HANDOFF.md` / `TASK.md` / `EXECUTION.md` / `CLAUDE.md` | 项目状态和规则 |
| `scripts/evaluate_industry_rotation.py` | B1 评估脚本（全文，1110 行） |
| `scripts/diagnose_b1_aw_ew_decomposition.py` | B1 分解脚本（全文，626 行） |
| `scripts/evaluate_c1_industry_inside_stock_selection.py` | C1 评估脚本（全文，1069 行） |
| `scripts/evaluate_b2_multifactor.py` | B2 评估脚本（部分） |
| `scripts/diagnose_b1_concentration_cap.py` | B1 浓度上限脚本（部分） |
| `FILE_INVENTORY.md` | 文件清单 |

---

## 2. 新增/修改的文件

| 文件 | 状态 | 说明 |
|---|---|---|
| `scripts/diagnose_turnover.py` | **新增** | Turnover 分解 + cost model audit 诊断脚本 |
| `reports/turnover_diagnostic_20260519.md` | **新增** | 诊断报告 |
| `EXECUTION.md` | 修改 (+58 行) | 追加 Turnover Diagnostic 执行记录 |
| `HANDOFF.md` | 修改 (+28 行) | 追加诊断结果和下一步更新 |

---

## 3. 核心发现

### 3.1 Cost Model Bug（已确认）

B1/B2/decomposition 五个脚本将 20bps 按 **flat monthly cost** 扣减，但 20bps = 印花税 5bps + 佣金 5bps + 滑点 10bps = **per-trade 成本**，应对 turnover portion 按比例扣减。

- 正确公式：`cost = 20bps * turnover_rate`
- 当前 B1/B2：`cost = 20bps` 每月固定扣除
- C1 正确使用了 proportional cost

**影响**：LB60 Top3 年均多扣 ~122 bps。不改变 FAIL/OBSERVE 结论，但应在任何正式回测前修正。

### 3.2 Turnover 主要来源

| 来源 | B1 (LB60 Top3, TO=49%) | C1 (Top20, TO=53%) |
|---|---|---|
| 信号排名噪声 | **主因** — Spearman r=0.59 | **主因** |
| Top-N boundary crossing | **主因** — 72% 月份有 boundary 穿透 | — |
| Lookback 选择 | LB20 >> LB60 (80% vs 49%) | — |
| 行业内 rank churn | — | **77%** of turnover |
| 跨行业漂移 | — | 23% |
| 行业集合变化 | 可忽略 | 可忽略 |

### 3.3 Turnover 是结构性问题，非实现 bug

Turnover 来自信号排名不够稳定 + Top-N 硬切边界。不是计算口径错误。降低 turnover 需要信号设计改进（EMA 平滑、hysteresis buffer、最低持有期）。

### 3.4 LB20 不可用

LB20 排名稳定性极低（Spearman r ~ 0.06），turnover 74-80%。LB60 是最低可用 lookback。

---

## 4. 未发现计算口径 bug

Turnover 计算本身正确（`n_changed / top_n` for B1, `1 - overlap/top_n` for C1）。唯一问题是 cost model 应用方式（flat vs proportional），已在 3.1 中记录。

---

## 5. 下一步建议

1. 入场信号质量诊断 — 月末 snapshot 是否过于粗糙，周频/双周频是否能改善
2. 转向非行业内相对动量方向 — 不以行业 membership 做 de-meaning
3. Cost model 修正 — 在下一轮正式评估前修改五个脚本的 cost 扣减方式（本次已审计但未修改策略逻辑）
