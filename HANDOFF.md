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
B1 Industry Rotation：OBSERVE / REQUEST_CHANGES（2026-05-18 QA 审查降级）
下一步：B1 补充诊断（static hold 事前对比 + AW/EW 差距分解 + EW-only 诊断）
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
| Industry Rotation | B1 eval → QA review | **OBSERVE** | CONDITIONAL PASS 降级，static hold 对比削弱轮动价值 |

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

1. `handoff/` 为本地备份目录，不应提交。
2. `historical_constituents.json` 可用于回测股票池过滤，但不适合事件驱动研究。
3. 行业分类是当前标签快照，回看历史存在行业分类后见偏差，B1 必须说明。
4. **B1 QA REQUEST_CHANGES**（2026-05-18）：
   - EW variants Ex-2025 基本失效（4/6 超额 < 3.05%）
   - 2025 对全期收益贡献过大
   - Static hold 通信设备（328%）碾压 rotation（~57%），削弱轮动价值
   - AW/EW 差距 2-3x 未解释，可能是大市值 beta 而非行业轮动 alpha

---

## 7. 下一步建议

执行 B1 补充诊断（TASK.md Section 8）：

1. Static hold 事前对比：月末仅用当时已知数据，rotation vs static hold
2. AW/EW 差距分解：行业选择 vs 大市值 beta 贡献
3. EW-only 诊断：如果仅 AW 可行，B1 前提已变质

原则：

```text
只做 offline evaluation
不改策略代码
不接回测
不跑 GA
不进入 Paper Trading
不写 data/raw parquet
如果 Ex-2025 不能证明 rotation > static hold，封存 B1
```
