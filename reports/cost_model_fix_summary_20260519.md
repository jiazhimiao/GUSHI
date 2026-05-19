# Cost Model 修正 — 执行总结

> 2026-05-19 | L1 代码修正 | Agent Teams 三 teammate 审计 + Lead 执行

---

## Execution Mode

**Agent Teams** — 3 independent teammates spawned + Lead execution

| Teammate | Agent ID | Role |
|---|---|---|
| qts-backtest-dev | a8c5fadf | 审计 8 脚本 cost 逻辑 |
| qts-qa-reviewer | a1fc96f7 | 审查历史报告影响 |
| qts-safety-reviewer | afe59799 | 安全检查 |

---

## 1. 修改文件

| # | 脚本 | 改动 |
|---|---|---|
| 1 | `scripts/evaluate_industry_rotation.py` | L55 cost 注释更新; L375-393 重排 turnover 计算到 cost 之前，新增 `df["turnover_rate"]` 列; L434-435 复用 turnover_rate; L622 cost assumption 文案 |
| 2 | `scripts/diagnose_b1_aw_ew_decomposition.py` | L43 cost 注释; L247 移除 flat cost; L260-268 turnover 前置计算 + proportional cost |
| 3 | `scripts/diagnose_b1_concentration_cap.py` | L32 cost 注释; L264 移除 flat cost; L276-285 turnover 前置 + proportional cost |
| 4 | `scripts/diagnose_b1_cap_time_variation.py` | L30 cost 注释; L223 移除 flat cost; L234-243 同上 |
| 5 | `scripts/diagnose_b1_ew_only.py` | L31 cost 注释; L165 移除 flat cost; L177-186 同上 |
| 6 | `scripts/evaluate_b2_multifactor.py` | L36 cost 注释; L231 移除 flat cost; L243-254 同上 |
| 7 | `scripts/diagnose_b1_static_hold.py` | L38-39 cost 注释更新; L267 移除 flat cost; L285-296 同上（rotation 路径; static/annual 路径不变） |
| — | `scripts/evaluate_c1_industry_inside_stock_selection.py` | **不修改**（已正确使用 proportional cost） |

### 文档更新

| 文件 | 改动 |
|---|---|
| `HANDOFF.md` | 添加 cost model disclaimer |
| `EXECUTION.md` | 追加 cost model fix 执行记录 (+39 行) |
| `reports/industry_rotation_diagnostic_20260518.md` | smoke test 重写（cost assumption 文案更新） |

### 不修改

- 策略代码 (`qts/strategies/`)
- 回测引擎 (`qts/backtest/`)
- 风控 (`qts/risk/`)
- 执行层 (`qts/execution/`)
- `data/raw/`
- 历史 closeout 报告（B1/B2/C1 结论全部不变）

---

## 2. 每个脚本 Cost Model 修正摘要

### evaluate_industry_rotation.py

```text
Before: df["excess_after_cost"] = df["excess_vs_hs300ew"] - COST_BPS_PER_TRADE
After:  df["excess_after_cost"] = df["excess_vs_hs300ew"] - COST_BPS_PER_TRADE * df["turnover_rate"]
        where turnover_rate = n_changed / len(curr_s) per month, first_month = 1.0
```

### diagnose_b1_aw_ew_decomposition.py

```text
Before: portfolio_ret = np.mean(ind_rets) - COST_BPS_MONTHLY
After:  cost = COST_BPS_MONTHLY * turnover_rate (computed from prev/curr selection)
        monthly_excess.append(portfolio_ret - cost - ew_ret)
```

### diagnose_b1_concentration_cap.py

```text
Before: port_ret = cum_port - 1 - COST_BPS
After:  turnover_rate from prev/curr selection; cost = COST_BPS * turnover_rate
        monthly_excess.append(port_ret - cost - ew_ret)
```

### diagnose_b1_cap_time_variation.py

```text
Before: port_ret = cum - 1 - COST_BPS
After:  Same pattern as concentration_cap
```

### diagnose_b1_ew_only.py

```text
Before: port_ret = np.mean(rets) - COST_BPS
After:  Same pattern
```

### evaluate_b2_multifactor.py

```text
Before: port_ret = cum - 1 - COST_BPS
After:  Same pattern
```

### diagnose_b1_static_hold.py

```text
Before: portfolio_ret = np.mean(ind_rets) - cost_bps  (rotation path)
After:  monthly_cost = cost_bps * turnover_rate
        rotation path proportional; static/annual path unchanged (full rebalance = 100% turnover)
```

---

## 3. 验证结果

```bash
# py_compile: ALL 7 PASS
python -m py_compile scripts/evaluate_industry_rotation.py          → OK
python -m py_compile scripts/diagnose_b1_aw_ew_decomposition.py     → OK
python -m py_compile scripts/diagnose_b1_concentration_cap.py       → OK
python -m py_compile scripts/diagnose_b1_cap_time_variation.py      → OK
python -m py_compile scripts/diagnose_b1_ew_only.py                 → OK
python -m py_compile scripts/evaluate_b2_multifactor.py             → OK
python -m py_compile scripts/diagnose_b1_static_hold.py             → OK

# Smoke test: PASS (2024 only, LB20 Top3 EW, 11 months)
python scripts/evaluate_industry_rotation.py --smoke → "Cost assumption: 0.20% per traded side, applied proportionally to monthly turnover"
```

---

## 4. Git Status

```
Modified (10 files):
 M EXECUTION.md
 M HANDOFF.md
 M reports/industry_rotation_diagnostic_20260518.md  (smoke test overwrite)
 M scripts/diagnose_b1_aw_ew_decomposition.py
 M scripts/diagnose_b1_cap_time_variation.py
 M scripts/diagnose_b1_concentration_cap.py
 M scripts/diagnose_b1_ew_only.py
 M scripts/diagnose_b1_static_hold.py
 M scripts/evaluate_b2_multifactor.py
 M scripts/evaluate_industry_rotation.py

Untracked (4 files, from prior turnover diagnostic task):
 ?? reports/cost_model_fix_plan_20260519.md
 ?? reports/turnover_diagnostic_20260519.md
 ?? reports/turnover_diagnostic_summary_20260519.md
 ?? scripts/diagnose_turnover.py
```

## 5. Diff Stats

```
10 files changed, 291 insertions(+), 672 deletions(-)
```

672 deletions are from the smoke test overwriting the old diagnostic report format.

---

## 6. 结论

- 7 个脚本 cost model 全部从 flat monthly 修正为 turnover-proportional
- C1 不修改（已正确）
- 历史 closeout 报告结论不变
- 不改变策略/回测/风控/执行逻辑
- **不 git add, 不 commit**（按用户要求）
