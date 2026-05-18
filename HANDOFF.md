# HANDOFF — QTS 当前交接

> 更新时间：2026-05-18  
> 当前阶段：Industry Classification Solved → Ready for B1 Industry Rotation

---

## 1. 当前状态

```text
trend_breakout v2：PAUSED
Candidate B：historical baseline only
Tushare provider：optional provider 已接入，默认仍 AKShare
Industry classification：已解决，280/280 HS300 覆盖
下一步：B1 Industry Rotation Offline Evaluation
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
| Industry Rotation | B0 data | READY | 行业分类数据已解决 |

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

---

## 6. 当前风险

1. `c7102d4` 如未 push，需要网络恢复后推送。
2. `handoff/` 为本地备份目录，不应提交。
3. Industry Rotation 还没有做 B1 离线评估，不得进入 Paper Trading。
4. `historical_constituents.json` 可用于回测股票池过滤，但不适合事件驱动研究。
5. 行业分类是当前标签快照，回看历史存在行业分类后见偏差，B1 必须说明。

---

## 7. 下一步建议

执行 `TASK.md`：B1 Industry Rotation Offline Evaluation。

原则：

```text
只做 offline evaluation
不改策略代码
不接回测
不跑 GA
不进入 Paper Trading
不写 data/raw parquet
```
