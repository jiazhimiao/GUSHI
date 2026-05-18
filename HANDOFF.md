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
B1 Industry Rotation：CONDITIONAL PASS / REDEFINED（2026-05-19 三补充诊断闭环）
新名称：EW Signal + AW Holding Amount-Weighted Industry Momentum
标准配置：LB60-120, Top3-5, MinStk3, EW signal + AW holding
不进入 Paper Trading，不进入正式回测
下一步：B1-redefined QA review + AW 集中度风险评估
```

当前工作区注意事项：

```text
main 可能 ahead origin/main by 1 commit: c7102d4
handoff/ 是本地备份目录，不提交
.env gitignored，不提交
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
| Industry Rotation | B1 eval → 3 supplements | **CONDITIONAL PASS / REDEFINED** | EW+AWH. Rotation>static hold, EA>AA, EW-alone insufficient |

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

---

## 6. 当前风险

1. `handoff/` 为本地备份目录，不应提交。
2. `historical_constituents.json` 可用于回测股票池过滤，但不适合事件驱动研究。
3. 行业分类是当前标签快照，回看历史存在行业分类后见偏差。
4. **AW holding top-stock concentration**：top-3 股票占 AW 行业 80%+ 成交额，回报贡献 84%+。
5. **EW signal Ex-2025 Rel.Calmar**：0/24 variants >= 0.5，必须 paired with AW holding。
6. B1 已重定义为组合策略（EW signal + AW holding），不是独立运行的单一策略。

---

## 7. 下一步建议

1. B1-redefined QA review：新定义是否成立
2. AW holding 集中度风险量化
3. 设计更保守的 EA 标准配置

原则：

```text
不进入 Paper Trading
不进入正式回测
不跑 GA
不改策略代码
不写 data/raw parquet
```
