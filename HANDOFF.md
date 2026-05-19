# HANDOFF — QTS 当前交接

> 更新时间：2026-05-19  
> 当前阶段：B1 REDEFINED — EW Signal + AW Holding Amount-Weighted Industry Momentum

---

## 1. 当前状态

```text
trend_breakout v2：PAUSED
Candidate B：historical baseline only
Tushare provider：optional provider 已接入，默认仍 AKShare
Industry classification：已解决，280/280 HS300 覆盖
B1：OBSERVE / FRAGILE — EW+AWH-IM (research observation only)
B2：PAUSE / MARGINAL-FAIL（2026-05-19 B2 Phase 1 closeout）
  行业层多因子排序没有解决信号薄、时间集中、小行业依赖问题
C1：FAIL（2026-05-19 C1-A closeout）
  行业内相对动量选股假设被证伪，0/4 配置通过，alpha 方向为负（均值回归）
  C1-B/C1-C blocked
明确禁止：formal backtest / Paper Trading / GA / strategy code changes
下一步：暂停行业内相对动量路线，回到 B1 baseline 稳健性/入场信号质量或其他非行业内动量方向
```

当前工作区注意事项：

```text
main 可能 ahead origin/main by 1 commit: c7102d4
handoff/ 是本地备份目录，不提交
.env gitignored，不提交
```

**Cost Model 修正 (2026-05-19)**:

```text
旧 B1/B2 报告使用 flat monthly cost（每月固定扣 20bps），
已在 2026-05-19 修正为 turnover-proportional cost = 20bps * turnover_rate。
受影响报告: b1_ew_only, b1_concentration_cap, b1_cap_time_variation, 
  b1_static_hold, b1_aw_ew_decomposition, b2_multifactor_eval.
C1 报告已正确（始终使用 proportional cost），不受影响。
历史 closeout 结论不变 (OBSERVE/FRAGILE, PAUSE/MARGINAL-FAIL, FAIL)。
后续评估统一使用 proportional cost。
```

---

## 2. 已完成研究周期结论

| 方向 | 阶段 | 判定 | 结论 |
|---|---|---:|---|
| trend_breakout v2 | 5-round diagnosis | PAUSED | 单维度突破 alpha 不稳定，日内区分度不足 |
| HS300 横截面动量 | Phase 1 | MARGINAL / HOLD | IC 太弱，不进入复合模型 |
| 反转/防御横截面 | Audit | STOP | 无因子通过全部条件 |
| Event-driven | C0 | WAIT | 成分股事件数据无公告日/生效日/调出 |
| Pair long-only reversion | A0.5 walk-forward | FAIL | 2025-2026 失效，after-cost excess 转负 |
| Industry Rotation | B1 eval → 3 supplements → RV | **OBSERVE / FRAGILE** | EW+AWH-IM. Cap_20 fragile, top-3-month concentrated |
| Industry Multi-Factor (B2) | Phase 1 | **PAUSE / MARGINAL-FAIL** | B2-C RC>B1 but T10%=99%, MinStk5=0 pass. Signal too thin. |
| Industry-Inside Stock (C1) | C1-A Phase 1 | **FAIL** | Within-industry relative momentum falsified. 0/4 pass, negative alpha (mean-reversion). |

---

## 3. 关键数据资产

`data/meta/industry_classification.csv`

```text
全 A 股票：5515
HS300 覆盖：280/280
行业标签：65
有效行业：39
source：Tushare / jiaoch.site stock_basic
口径：Tushare industry label (Shenwan-style granular, not official Shenwan)
```

---

## 4. 关键脚本

| 脚本 | 用途 |
|---|---|
| `scripts/evaluate_cross_sectional_alpha.py` | 横截面单因子 IC 扫描 |
| `scripts/diagnose_pair_universe.py` | Pair universe A0 审计 |
| `scripts/diagnose_pair_walkforward.py` | Pair A0.5 walk-forward 复核 |
| `scripts/verify_industry_classification_source.py` | 行业分类源审计 |
| `scripts/build_industry_classification_map.py` | 构建行业分类 CSV |
| `scripts/evaluate_industry_rotation.py` | B1 行业轮动评估（relative calmar + Ex-2025） |
| `scripts/diagnose_b1_static_hold.py` | Static hold 事前对比诊断 |
| `scripts/diagnose_b1_aw_ew_decomposition.py` | AW/EW 2×2 分解（signal × holding） |
| `scripts/diagnose_b1_ew_only.py` | EW-only 24-variant 稳定性网格扫描 |
| `scripts/diagnose_turnover.py` | Turnover 分解 + cost model audit |

---

## 5. 关键报告

| 报告 | 结论 |
|---|---|
| `reports/cross_sectional_alpha_report_20260517_235638.md` | 横截面动量弱 |
| `reports/reversal_defensive_factor_audit_20260518_001139.md` | 反转/防御停止 |
| `reports/index_membership_event_audit_20260518.md` | Event-driven WAIT |
| `reports/pair_walkforward_feasibility_recheck_20260518.md` | Pair FAIL |
| `reports/industry_classification_source_audit_20260518.md` | 行业源可用 |
| `reports/industry_classification_map_report_20260518.md` | 280/280 HS300 覆盖 |
| `reports/industry_rotation_offline_eval_20260518.md` | B1 初版评估（旧阈值 <10% DD） |
| `reports/industry_rotation_diagnostic_20260518.md` | B1 诊断报告（新阈值 Rel.Calmar） |
| `reports/b1_qa_review_20260518.md` | B1 QA 独立审查报告 |
| `reports/b1_static_hold_diagnostic_20260518.md` | Static hold ex-ante 诊断 |
| `reports/b1_aw_ew_decomposition_20260518.md` | AW/EW 2×2 decomposition |
| `reports/b1_ew_only_diagnostic_20260518.md` | EW-only 24-variant stability |
| `reports/turnover_diagnostic_20260519.md` | Turnover 分解诊断 + cost model audit |

---

## 6. 当前风险

1. `handoff/` 为本地备份目录，不应提交。
2. `historical_constituents.json` 可用于回测股票池过滤，但不适合事件驱动研究。
3. 行业分类是当前标签快照，回看历史存在行业分类后见偏差。
4. **AW holding top-stock concentration**：top-3 股票占 AW 行业 80%+ 成交额，回报贡献 84%+。
5. **EW signal Ex-2025 Rel.Calmar**：0/24 variants >= 0.5，必须 paired with AW holding。
6. B1 已重定义为组合策略（EW signal + AW holding），不是独立运行的单一策略。

---

## 7. Turnover 诊断结果（2026-05-19）

### 已完成

- **Cost model bug 发现**：B1/B2/decomposition 五脚本将 20bps 按 flat monthly 扣减，应改为 `20bps * turnover_rate`。C1 正确。
- **B1 LB60 Top3 turnover = 49.0%**（median 33.3%），主要来源：信号排名边界噪声 + Top-N boundary crossing。
- **B1 LB20 全部 > 74%**，LB20 排名极不稳定（Spearman r ~ 0.06），不建议使用。
- **C1 Top20 turnover = 52.9%**，77% 为行业内 rank churn，23% 为跨行业。
- **过收费影响**：LB60 Top3 年均多扣 122 bps，不改变 FAIL/OBSERVE 结论但需修正。
- 脚本：`scripts/diagnose_turnover.py`，报告：`reports/turnover_diagnostic_20260519.md`。

### Turnover 来源归因

| 来源 | B1 | C1 |
|---|---|---|
| 信号排名噪声 | 主因 | 主因 |
| Top-N 边界穿透 | 主因 | — |
| Lookback 窗口 | LB20 >> LB60 | — |
| 行业内 rank churn | — | 77% |
| 行业集合变化 | 可忽略 | 可忽略 |

## 8. 下一步建议

1. ~~Turnover 诊断~~ → **已完成**。Turnover 是结构性问题（信号噪声），非实现 bug。
2. 入场信号质量 — 月末 snapshot 信号是否过于粗糙；周频/双周频是否能改善
3. 转向非行业内相对动量方向（不以行业 membership 做 de-meaning）
4. B1 baseline 稳健性再审查（可选，已被 turnover 诊断部分覆盖）

原则：

```text
不进入 Paper Trading
不进入正式回测
不跑 GA
不改策略代码
不写 data/raw parquet
```
