# HANDOFF — 2026-05-18 (RESEARCH CYCLE END)

## Phase: All Directions Resolved → Awaiting Data Infrastructure Upgrade

### Research Cycle: 2026-05-17 ~ 2026-05-18

6 个 alpha 研究方向全部完成第一轮可行性判断。

---

### Final Conclusions

| # | 方向 | 阶段 | 判定 | 阻塞类型 |
|---|------|------|:--:|------|
| 1 | trend_breakout v2 | 5-round diag | PAUSED | 策略结构: 单维度区分度≈0 |
| 2 | HS300 横截面 (动量 13feat) | Phase 1 | MARGINAL | alpha: max IC IR=0.089 |
| 3 | HS300 横截面 (反转 11feat) | Audit | STOP | alpha: max IC IR=0.151 |
| 4 | Event-Driven 指数调入 (C) | C0 Audit | WAIT | 数据: 无公告日/生效日/调出 |
| 5 | Pair long-only reversion (A) | A0.5 WF | FAIL | 2025-2026 excess=−0.41% |
| 6 | Industry Rotation (B) | B0 Audit | WAIT | 数据: 行业覆盖 37.9% |

### Key Metrics for Fast Recall

```
Cross-sectional (momentum):
  Best factor: volume_ratio_5_20  IC=0.016  IC IR=0.089
  Verdict: MARGINAL, no Phase 2

Cross-sectional (reversal):
  Best factor: low_close_div_ma60  IC=0.037  IC IR=0.151
  Verdict: STOP, 0/13 pass all criteria

Pair A0.5 Walk-Forward:
  5394 trades, 1523 pairs, 14 periods
  Mean excess +0.21%, median -0.41%, after-cost -0.09%
  Win rate 45.8% (excess)
  2023: +1.31% | 2024: +1.03% | 2025: -0.41% | 2026: -1.03%
  Verdict: FAIL

Industry Rotation B0:
  HS300 coverage: 106/280 (37.9%)
  Effective industries: 3/19 (C制造业73, J金融9, I信息技术6)
  SH blue-chips: 0/177 covered
  Verdict: WAIT (data insufficient)
```

### Watchlist Factor
- low_ma20_div_ma60: 5/5 years positive IC (only cross-year consistent factor found)

### Active Baseline (preserved)
Candidate B: fitness=2.304, ann=7.90%, dd=-8.56%, trades=1137

---

### Scripts Added This Research Cycle

| Script | Purpose |
|--------|---------|
| `scripts/evaluate_cross_sectional_alpha.py` | Single-factor IC scanner (momentum + reversal modes) |
| `scripts/diagnose_pair_universe.py` | A0: correlation-based pair universe + mean reversion |
| `scripts/diagnose_pair_walkforward.py` | A0.5: walk-forward pair + non-overlap trade simulation |

### Reports Generated

| Report | Phase | Verdict |
|--------|-------|---------|
| `reports/project_status_20260517.md` | Status snapshot | — |
| `reports/cross_sectional_alpha_plan_20260517.md` | Phase 1 plan | — |
| `reports/cross_sectional_alpha_report_20260517_235638.md` | Phase 1 results | MARGINAL |
| `reports/reversal_defensive_factor_audit_20260518_001139.md` | Reversal audit | STOP |
| `reports/index_membership_event_audit_20260518.md` | Event data audit | WAIT |
| `reports/next_structure_research_plan_20260518.md` | 3-direction plan (v2) | — |
| `reports/pair_universe_feasibility_audit_20260518.md` | A0 pair feasibility | MARGINAL |
| `reports/pair_walkforward_feasibility_recheck_20260518.md` | A0.5 walk-forward | **FAIL** |
| `reports/industry_rotation_data_audit_plan_20260518.md` | B0 plan | — |
| `reports/industry_rotation_data_audit_20260518.md` | B0 data audit | **WAIT** |

### Data Limitations Discovered

1. HS300 daily bars: only 5/197 constituents have pre-2022 data; most start 2022-01-04
2. Industry classification: all AKShare endpoints rate-limited; only CSRC level-1 (SZ-only) available
3. historical_constituents.json: survivorship-biased; no announcement/effective dates; no removals

---

### Next Research Cycle

**Priority 0**: Solve industry classification data source.
Options (in order of feasibility):
1. **TuShare token** — project has tushare installed; `stock_basic()` returns Shenwan/CITIC industries
2. Static industry CSV — from JoinQuant / RiceQuant / Wind export
3. AKShare API recovery — retry in off-peak hours
4. Wind/Choice terminal access

Once industry data is available:
- Re-open B (Industry Rotation) — 28+ industries, monthly rebalance
- Potentially re-open A (Pair Trading) — same-industry pairs only
- Re-open C (Event-Driven) — if inclusion_date per stock is saved

### Not Modified
broker, engine, data pipeline, GA optimizer, all strategy code
