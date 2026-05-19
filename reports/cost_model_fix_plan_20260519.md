# Cost Model 修正计划

> 2026-05-19 | L1 代码修正 | Agent Teams 三 teammate 审计完成

---

## Execution Mode

**Agent Teams** — 3 independent teammates spawned (not inline simulated)

| Teammate | Agent ID | Role | Verdict |
|---|---|---|---|
| qts-backtest-dev | a8c5fadf | 审计 8 个脚本 cost 逻辑 | 7 BUG + 1 CORRECT |
| qts-qa-reviewer | a1fc96f7 | 审查历史报告影响 | 无结论需改变，建议加 disclaimer |
| qts-safety-reviewer | afe59799 | 安全检查 | L1，全部 PASS，可安全执行 |

---

## 1. 受影响文件

| # | 脚本 | 当前行号 | 当前行为 | 修正为 |
|---|---|---|---|---|
| 1 | `evaluate_industry_rotation.py` | L376-378 | `cost_per_month = COST_BPS_PER_TRADE` 每月固定扣 | `COST_BPS_PER_TRADE * turnover_rate` |
| 2 | `diagnose_b1_aw_ew_decomposition.py` | L247 | `portfolio_ret = np.mean(ind_rets) - COST_BPS_MONTHLY` | `- COST_BPS_MONTHLY * turnover_rate` |
| 3 | `diagnose_b1_concentration_cap.py` | L264 | `port_ret = cum_port - 1 - COST_BPS`（窗口级 flat） | tracking turnover 后按比例扣 |
| 4 | `diagnose_b1_cap_time_variation.py` | L223 | `port_ret = cum - 1 - COST_BPS`（窗口级 flat） | 同上 |
| 5 | `diagnose_b1_ew_only.py` | L165 | `port_ret = np.mean(rets) - COST_BPS` | tracking turnover 后按比例扣 |
| 6 | `evaluate_b2_multifactor.py` | L231 | `port_ret = cum - 1 - COST_BPS` | 同上 |
| 7 | `diagnose_b1_static_hold.py` | L267 | `portfolio_ret = np.mean(ind_rets) - cost_bps`（rotation 路径） | 同上 |
| — | `evaluate_c1_industry_inside_stock_selection.py` | L510 | 已使用 `COST_BPS * turnover_rate` | **不修改** |

---

## 2. 是否改变历史报告结论

**全部 NO。** QA reviewer 定量分析：

| 报告 | 影响 | 结论改变？ |
|---|---|---|
| B1 EW-Only | "0/24 pass" → "1/24 pass"（LB120_Top5_MinStk5 RC 0.44→0.59） | **No** — 23/24 仍 fail |
| B1 Concentration Cap | cap_15 RC 0.48→0.56 | **No** — cap_20 是标准 |
| B1 Final Summary | Ann.Excess 略升 ~1% | **No** — OBSERVE/FRAGILE 基于结构性原因 |
| B2 Multi-factor | Ann.Excess 略升 ~0.9% | **No** — PAUSE 基于 T10%=99% |
| B1 AW/EW Decomposition | **完全不受影响**（同 turnover 对内 cost 抵消） | **No** |
| C1 | 已正确 | N/A |

**历史 closeout 报告不重建，不修改。**

---

## 3. 最小验证命令

```bash
python -m py_compile scripts/evaluate_industry_rotation.py
python -m py_compile scripts/diagnose_b1_aw_ew_decomposition.py
python -m py_compile scripts/diagnose_b1_concentration_cap.py
python -m py_compile scripts/diagnose_b1_cap_time_variation.py
python -m py_compile scripts/diagnose_b1_ew_only.py
python -m py_compile scripts/diagnose_b1_static_hold.py
python -m py_compile scripts/evaluate_b2_multifactor.py

python scripts/evaluate_industry_rotation.py --smoke
```

---

## 4. 需要更新的文档

| 文件 | 操作 |
|---|---|
| `HANDOFF.md` | 加 disclaimer："旧 B1/B2 报告使用 flat monthly cost，后续评估统一改为 turnover-proportional cost。" |
| `EXECUTION.md` | 追加 cost model fix 执行记录 |
| 历史报告 | **不修改**。HANDOFF 统一标注即可。 |

---

## 5. 不修改的内容

- 策略代码（`qts/strategies/`）
- 回测引擎（`qts/backtest/`）
- 风控（`qts/risk/`）
- 执行层（`qts/execution/`）
- `data/raw/` 任何文件
- 历史 closeout 报告
- C1 脚本（已正确）

---

## 6. 风险等级

**L1** — 小型脚本修正，低风险。Safety reviewer 全部检查项 PASS。

---

## 7. 待确认

是否按此计划执行修正？
