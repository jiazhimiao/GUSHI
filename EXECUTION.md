# EXECUTION — 最近执行记录

> 本文件记录最近阶段执行摘要。详细证据见 `reports/`。

---

## 2026-05-17 ~ 2026-05-18：Alpha Research Cycle

### 1. trend_breakout v2 封存

- Candidate B 保留为 historical baseline。
- trend_breakout v2 不继续 GA，不进入 Paper Trading。
- 关键问题：信号稀缺、rotation 高、假突破高、日内评分无区分度。

### 2. Tushare provider

- 新增可选 Tushare / jiaoch.site provider。
- 默认 provider 仍为 AKShare。
- verify-only 支持不写 parquet 的口径验证。

### 3. HS300 横截面研究

- `scripts/evaluate_cross_sectional_alpha.py`
- 动量/趋势/量能单因子扫描：信号弱。
- 反转/防御因子审计：无因子通过全部条件。

### 4. Event-driven C0

- `historical_constituents.json` 无公告日、真实生效日、调出数据。
- C 方向 WAIT。

### 5. Pair A0 / A0.5

- A0 全样本 pair 发现存在未来函数风险。
- A0.5 修正为 walk-forward、T+1 open、非重叠交易、excess 分离。
- 结论：2025-2026 失效，after-cost excess 转负，Pair 暂停。

### 6. Industry Classification

- Tushare stock_basic 可用。
- 构建 `data/meta/industry_classification.csv`。
- 5515 A 股，280/280 HS300，65 行业标签，39 有效行业。
- 行业分类阻塞解除。

---

## 最新提交记录参考

```text
c7102d4 data: add industry classification map (280/280 HS300, 65 labels)
74f679f research: archive cross-sectional and structure feasibility studies
9b18600 data: add optional tushare provider for incremental updates
70f40de docs: update project status after trend breakout diagnostics
8a36b95 research: archive trend_breakout v2 diagnostic cycle
```

如本地 ahead origin/main，先尝试 push；网络阻断时保留本地 bundle，不要 reset。

---

## 2026-05-18：B1 QA Review

- QA 独立审查 B1 诊断报告。
- 结论：**REQUEST_CHANGES**。CONDITIONAL PASS 降级为 OBSERVE。
- 发现：
  1. Static hold 通信设备（328%）碾压 rotation（~57%），削弱轮动价值
  2. EW variants Ex-2025 基本失效（4/6 < 3.05%）
  3. AW/EW 差距 2-3x 未解释，可能是大市值 beta
- 不允许进入正式回测和 Paper Trading。
- 下一步：B1 补充诊断（TASK.md Section 8）。

---

## 2026-05-19：B1 三补充诊断完成

### Static Hold Ex-Ante
- Rotation 4/4 splits 优于 ex-ante static hold。
- 2022-2023 训练期最强行业在 2024-2025 全部失效，rotation 动态适应。
- 脚本：`diagnose_b1_static_hold.py`，报告：`b1_static_hold_diagnostic_20260518.md`

### AW/EW 2×2 Decomposition
- Holding weight effect 主导（87-97%），signal effect 仅 3-13%。
- EA (EW signal + AW holding) > AA in 4/5 splits（Rel.Calmar）。
- Top-3 stocks account for 80%+ of AW industry amount。
- 脚本：`diagnose_b1_aw_ew_decomposition.py`，报告：`b1_aw_ew_decomposition_20260518.md`

### EW-Only Stability
- 24 variants × 5 splits 网格扫描。
- 0/24 pass Ex-2025 Rel.Calmar >= 0.5（best: LB120_Top5_MinStk5=0.44）。
- EW-alone insufficient；must pair with AW holding。
- 脚本：`diagnose_b1_ew_only.py`，报告：`b1_ew_only_diagnostic_20260518.md`

### 阶段性判断

```text
B1 REDEFINED: EW Signal + AW Holding Amount-Weighted Industry Momentum
Status: OBSERVE → CONDITIONAL PASS
EW-only does not pass independently, but EW signal + AW holding is viable for continued research.
```

---

## 2026-05-19：B1-Redefined QA Review

- 独立审查三补充诊断 + 重定义提案。
- 结论：**CONDITIONAL PASS / REDEFINED — ACCEPTED**。
- 新名称：EW+AWH Industry Momentum (highly concentrated)。
- 关键发现：
  1. Static hold block removed — rotation 4/4 > ex-ante static hold
  2. EA > AA in 4/5 splits — EW signal + AW holding is synergistic
  3. EW-only 0/24 pass Ex-2025 RC — proves complementarity, not weakness
  4. Top3 concentration 80%+ — core structural risk, must bound
- 允许：Robustness Validation（concentration bounding only）
- 禁止：formal backtest / Paper Trading / GA / strategy code changes
- 报告：`reports/b1_redefined_qa_review_20260519.md`

---

## 2026-05-19：B1 Robustness Validation + Final Summary

### Robustness Validation 1 — Concentration Cap
- cap_20: RC 0.63 (PASS), only LB60_Top3 survives
- cap_15: RC 0.48 (FAIL)
- RC drops 60% from uncapped; top3 concentration drops only 14%

### Robustness Validation 2 — Time Variation + MinStocks
- MinStk=5: RC 0.24 (FAIL, below EW holding)
- MinStk=8: RC 0.66 but only 7 industries (not meaningful rotation)
- Top 10% months = 113.6% of total excess — strategy concentrated in 3 months
- Cap binds 100% of months

### QA Review #3
- **DOWNGRADE: CONDITIONAL PASS → OBSERVE/FRAGILE**
- Reason: top-3-month concentration, single-parameter fragility, small-industry dependency
- Stop expanding robustness validation

### Final Summary
- Conservative standard config designed (research observation only)
- B1 evolution: Industry Rotation → EW+AWH-IM → OBSERVE/FRAGILE
- Report: `reports/b1_redefined_final_summary_20260519.md`

---

---

## 2026-05-19：B2 Multi-Factor Ranking Phase 1 + Closeout

- 实现 3 个固定评分版本：B2-A/B/C
- B2-C Top5 MinStk3 EW: RC=0.74 > B1 baseline (0.63)
- 但 T10%=99%，MinStk=5 0/6 pass
- Factor correlation max |r|=0.37 — factors orthogonal but alpha too thin
- QA 修正：移除 capped_aw 重复行，修复 stop condition 文案歧义
- **结论：PAUSE / MARGINAL-FAIL。行业层多因子不解决核心脆弱性。**
- 脚本：`scripts/evaluate_b2_multifactor.py`
- 报告：`reports/b2_multifactor_eval_20260519.md`

---

## 当前未完成

```text
B1 — OBSERVE / FRAGILE（closeout complete）
B2 — PAUSE / MARGINAL-FAIL（closeout complete）
C1 — FAIL（closeout complete，C1-B/C1-C blocked）
下一步：暂停行业层及行业内相对动量路线，回到 B1 baseline 稳健性/入场信号质量/非行业内动量方向
```

禁止直接进入回测、GA、Paper Trading。

---

## 2026-05-19：C1 Industry-Inside Stock Selection + Closeout

### Phase 1a: Variance Decomposition
- Pre-check failed to compute（诊断性缺口，非阻塞）

### C1-A Evaluation
- Signal: stock_60d_mom - industry_ew_mom, Top-20/Top-10 EW
- 4 configs tested (Ex-2025/2024 × Top20/Top10)
- 0/4 pass all MUST gates
- Ex-2025 Top20 S3: RC=0.00 (B1=0.63), IR=-1.25, WR=39%, DD=-36.6%, T10%=100%
- Best config (2024 Top10 S3): RC=0.10, T10%=330%

### QA + Safety Review
- QA (ac56ebc): CONFIRM_FAIL — 假设被证伪，信号选出后续均值回归，非实现 bug
- Safety (a98b752): SAFE — 零违规，L2 边界完整

### 结论
- **C1-A: FAIL — hypothesis falsified.**
- 行业内相对动量选出过去跑赢同行的股票，这些股票下个月均值回归（alpha 方向为负）
- C1-B/C1-C blocked（C1-A 未通过全部 MUST gate）
- 脚本：`scripts/evaluate_c1_industry_inside_stock_selection.py`
- 报告：`reports/c1_industry_inside_stock_selection_20260519.md`
- 研究计划：`reports/c1_research_plan_20260519.md`

---

## 2026-05-19：Turnover Diagnostic

### Cost Model Audit

- **发现 cost model bug**：B1/B2/decomposition 全部脚本将 20bps 按 flat monthly cost 扣减，但 20bps 是 per-trade 成本（印花税+佣金+滑点），应对 turnover portion 按比例扣减。
- C1 正确使用了 `COST_BPS * turnover_rate`。

受影响脚本：

```text
evaluate_industry_rotation.py          — flat -COST_BPS_PER_TRADE 每月
diagnose_b1_aw_ew_decomposition.py     — flat -COST_BPS_MONTHLY 每月
diagnose_b1_concentration_cap.py       — flat -COST_BPS 每月
diagnose_b1_cap_time_variation.py      — flat -COST_BPS 每月
evaluate_b2_multifactor.py             — flat -COST_BPS 每月
```

### Turnover Decomposition Results

| Variant | Mean TO | Median TO | Key Driver |
|---|---|---|---|
| B1 LB20 Top3 | 80.4% | 100.0% | Signal noise (LB20 ranks unstable) |
| B1 LB20 Top5 | 74.9% | 80.0% | Signal noise |
| B1 LB60 Top3 | 49.0% | 33.3% | Boundary crossing dominates |
| B1 LB60 Top5 | 45.7% | 40.0% | Boundary crossing dominates |
| C1 Top20 | 52.9% | 50.0% | Within-industry rank churn (77%) |

### Cost Overcharge Impact (LB60 Top3)

- Mean overcharge: 10.2 bps/month
- Annualized: 122.4 bps/year
- Flat cost = 204% of correct proportional cost

### Signal Stability

- Mean Spearman r = 0.591 (LB60) — moderate, explains ~50% boundary churn
- LB20 rank stability very low (r ~ 0.06) — explains LB20's 80%+ turnover
- Mean abs rank shift = 6.2 positions/month

### Key Findings

1. **Cost model bug confirmed**: B1/B2 overcharge ~10 bps/month. Does NOT change overall FAIL/OBSERVE conclusions.
2. **Turnover is structural, not implementation**: Primary source is signal ranking noise + boundary proximity, not calculation error.
3. **C1 turnover is ~53% stock-level** (better than B1 estimates suggested), but still above 50% gate.
4. **LB60 is the minimum viable lookback** — shorter lookbacks produce extreme turnover.
5. **77% of C1 turnover is within-industry rank churn**, 23% is cross-industry.

### Recommendations

1. Fix cost model in all B1/B2 scripts (before any future formal backtest)
2. Consider hysteresis buffer or signal smoothing to reduce boundary-driven turnover
3. For new signal directions: measure rank stability at design time

脚本：`scripts/diagnose_turnover.py`
报告：`reports/turnover_diagnostic_20260519.md`

---

## 2026-05-19：Cost Model Fix — Flat → Turnover-Proportional

### 修正内容

将 7 个脚本的 cost model 从 flat monthly 改为 turnover-proportional：

```text
cost = COST_BPS * turnover_rate  (per-trade, not flat per month)
```

第一月 turnover_rate = 1.0（建仓），之后按 `len(set(curr) - set(prev)) / len(curr)` 计算。

### 修改文件

| 脚本 | 修改行 | 改动 |
|---|---|---|
| `evaluate_industry_rotation.py` | L55, L375-393, L434-435, L622 | 重排 turnover 计算到 cost 之前，df["turnover_rate"] 列，proportional cost |
| `diagnose_b1_aw_ew_decomposition.py` | L43, L247, L260-268 | turnover 前置计算，cost 按比例 |
| `diagnose_b1_concentration_cap.py` | L32, L264, L276-285 | 同上 |
| `diagnose_b1_cap_time_variation.py` | L30, L223, L234-243 | 同上 |
| `diagnose_b1_ew_only.py` | L31, L165, L177-186 | 同上 |
| `evaluate_b2_multifactor.py` | L36, L231, L243-254 | 同上 |
| `diagnose_b1_static_hold.py` | L38-39, L267, L285-296 | 同上（rotation 路径；static/annual 路径不变） |

### 不修改

- `evaluate_c1_industry_inside_stock_selection.py`（已正确使用 proportional cost）
- 历史 closeout 报告
- `data/raw/`
- 策略/回测/风控/执行代码

### 验证

```bash
python -m py_compile (all 7 scripts)  → ALL PASS
python scripts/evaluate_industry_rotation.py --smoke → PASS (11 months, proportional cost)
```

### Disclaimer

旧 B1/B2 报告使用 flat monthly cost。后续评估统一使用 turnover-proportional cost。历史结论不变。

