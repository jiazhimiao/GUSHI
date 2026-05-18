# B1-Redefined Final QA Review — 2026-05-19

> 只读审查。不修改文件，不跑回测，不进入 Paper Trading。

---

## Files Inspected

`b1_static_hold_diagnostic.md`, `b1_aw_ew_decomposition.md`, `b1_ew_only_diagnostic.md`, `b1_qa_review_20260518.md`, `industry_rotation_diagnostic_20260518.md`, `HANDOFF.md`, `TASK.md`, `EXECUTION.md`

---

## 1. Static Hold — Is the Block Removed?

**Evidence**: Rotation 4/4 splits > ex-ante static hold (Rule A/B/C).

| Split | Best Rotation | Rot Calmar | Best Static | Static Calmar |
|---|---|---|---|---|
| Split1 (2024-2025) | LB20_Top5_aw | 9.24 | Rule B annual | 1.67 |
| Split2 (2024 only) | LB60_Top3_aw | 2.45 | Rule B annual | 0.42 |
| Split3 (2025 only) | LB20_Top5_aw | 71.77 | Rule B annual | 3.67 |
| Split4 (2025-2026) | LB20_Top5_aw | 19.18 | Rule B annual | 2.35 |

**Nuance**: Rule B (annual rebalancing) is the closest static analog to rotation and the best static rule. Rotation's advantage over Rule B is real but the margin in 2024-only (2.45 vs 0.42 Calmar) is modest. Rule A and Rule C (train-period fixed hold) fail because 2022-2023 winners (coal) became 2024-2025 losers.

**QA Judgment**: **BLOCK REMOVED.** The original QA concern was based on hindsight (picking communications equipment after knowing it won). The ex-ante rules show rotation adds value.

---

## 2. AW/EW Decomposition — Does It Support EA as Standard?

**Evidence**: 2x2 Shapley decomposition across 5 splits, consistent finding:

| Component | Ex-2025 | 2024 only | 2025 only | full |
|---|---|---|---|---|
| Signal effect | 7% | 10% | 3% | 10% |
| Hold effect | **93%** | **90%** | **97%** | **90%** |
| Interaction | 0% | 0% | 0% | 0% |

**EA vs AA (Rel.Calmar)**:

| Split | AA | EA | Winner |
|---|---|---|---|
| Ex-2025 | 1.30 | **1.61** | EA |
| 2024 only | 2.45 | **2.62** | EA |
| 2025 only | 30.33 | **40.91** | EA |
| full | 2.67 | **3.17** | EA |

**QA Judgment**: **STRONGLY SUPPORTS EA as standard configuration.** Methodologically sound. EW signal is the better industry selector. AW holding provides 90% of the magnitude. Neither works well without the other — they are complementary.

---

## 3. Does EW-Only Failure Weaken EA?

**Evidence**: 0/24 EW variants pass Ex-2025 Rel.Calmar >= 0.5. Best = 0.44.

**But** EA (EW signal + AW holding) passes Ex-2025 RC = 1.61:

| Layer | Ex-2025 RC |
|---|---|
| EW signal + EW holding (EE) | 0.31 |
| EW signal + AW holding (EA) | **1.61** |
| AW signal + EW holding (AE) | 0.20 |
| AW signal + AW holding (AA) | 1.30 |

**QA Judgment**: **DOES NOT WEAKEN EA.** It strengthens the case for the paired configuration. The value comes from the interaction — EW signal selection + AW holding execution. This is genuine synergy.

---

## 4. Top3 Concentration 80%+ — Large-Cap Exposure?

**Evidence**:

| Split | Top1 Amt Share | Top3 Amt Share | Top3 Ret Contrib |
|---|---|---|---|
| Ex-2025 | 41.0% | 80.9% | 83.9% |
| full | 41.3% | 81.8% | 84.7% |

**QA Judgment**: **This IS the core structural risk.** A single stock can account for 41% of the industry weight. The top 3 stocks drive 84.7% of returns. This strategy is "large-cap momentum within top momentum industries" — not "diversified industry rotation."

The new name "EW+AWH Industry Momentum" is more honest than the original, but still understates concentration risk. A caveat is required.

**Recommendation**: Include "(highly concentrated)" in strategy description.

---

## 5. Should B1 Be Renamed?

**QA Judgment**: **YES.**

- Original: "Industry Rotation" — implied value from switching industries
- Evidence: 90% of value from within-industry cap-weighting, 10% from industry selection
- This is a composite strategy, not a pure rotation strategy

**Recommended name**: "EW Signal + AW Holding Industry Momentum" (EW+AWH-IM)

---

## 6. Current Status

**QA Judgment**: **CONDITIONAL PASS / REDEFINED — ACCEPTED.**

| Evidence | Verdict |
|---|---|
| Rotation > ex-ante static hold (4/4) | ✅ |
| EA > AA in risk-adjusted terms (4/5) | ✅ |
| EW signal + AW holding is synergistic | ✅ |
| Top3 concentration 80%+ | ⚠️ structural risk |
| 2025 dominates full-period metrics | ⚠️ acknowledged |
| Reports honest about limitations | ✅ |

Neither OBSERVE (too much evidence) nor full PASS (too many caveats). CONDITIONAL is correct.

---

## 7. Allow Robustness Validation?

**QA Judgment**: **YES — ALLOWED with conditions.**

| Allowed | Forbidden |
|---|---|
| Bounding AW concentration risk | Formal backtest |
| EW signal rolling-window stability | Paper Trading |
| Cap-weight sensitivity analysis | GA optimization |
| Min stocks threshold sensitivity | Strategy code changes |

---

## 8. Next Step (Minimum Task)

**Quantify and bound AW holding concentration risk:**

1. What happens to EA performance if single-stock weight is capped at 20%? 15%?
2. How many stocks per industry needed to reduce top3 concentration below 60%?
3. Does AW holding still add value over EW holding after concentration is bounded?

The 80%+ top3 concentration makes the strategy fragile to single-stock events. This must be quantified before any further promotion.

---

## 9. Verdict Summary

| Dimension | Decision |
|---|---|
| B1 redefinition accepted | **YES** — EW+AWH Industry Momentum |
| Static hold block removed | **YES** |
| EA as standard config | **YES** |
| EW-only failure weakens EA | **NO** — proves complementarity |
| Top3 concentration is material risk | **YES** — must bound |
| Allow robustness validation | **YES** — concentration focus |
| Allow backtest | **NO** |
| Allow Paper Trading | **NO** |

### Safety

| Check | Status |
|---|---|
| Paper Trading implications | NONE |
| Backtest claims | NONE |
| Overstatement risk | MODERATE — concentration risk understated |
| Token/credential exposure | NONE |
| **Safety Decision** | **APPROVE** |

### QA Summary

```text
Files inspected: 8
QA Decision: CONDITIONAL PASS / REDEFINED — ACCEPTED
Safety Decision: APPROVE
Rename: "Industry Rotation" → "EW+AWH Industry Momentum (highly concentrated)"
Standard config: LB60-120, Top3-5, MinStk3, EW signal + AW holding
Next: bound AW concentration risk before any further promotion
Do NOT allow: backtest, Paper Trading, GA, strategy code changes
```
