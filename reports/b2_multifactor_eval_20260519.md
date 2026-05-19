# B2 — Industry Multi-Factor Ranking Phase 1

Generated: 2026-05-19 14:36

> B1 baseline RC = 0.63. Factors precomputed via pivot pipeline.

---
## 1. Factor Correlation

| | mom_60d | low_vol_60d | dd_recovery_120d | liq_trend | conc_penalty |
|---|---|---|---|---|---|
| mom_60d | 1.00 | -0.33 | -0.35 | -0.21 | -0.20 |
| low_vol_60d | -0.33 | 1.00 | -0.01 | 0.12 | -0.37 |
| dd_recovery_120d | -0.35 | -0.01 | 1.00 | 0.35 | 0.07 |
| liq_trend | -0.21 | 0.12 | 0.35 | 1.00 | 0.02 |
| conc_penalty | -0.20 | -0.37 | 0.07 | 0.02 | 1.00 |

Max cross-factor |r|: 0.37 — ✅ <0.7

---
## 2. Ex-2025 Results


### Holding: EW (pivot pipeline — capped_aw requires per-stock data, not available for B2 Phase 1)

| Version | TopN | MinStk | Ann.Excess | IR | RC | T10% | T20% | TO | vs B1 |
|---------|-------|--------|------------|-----|-----|------|------|-----|-------|
| B2-A | 3 | 3 | 0.39% | 0.10 | 0.03 | 592% | 956% | 48% | LOSE |
| B2-A | 3 | 5 | -9.28% | -0.43 | 0.00 | 100% | 100% | 46% | LOSE |
| B2-A | 5 | 3 | -0.15% | 0.06 | 0.00 | 948% | 1406% | 41% | LOSE |
| B2-A | 5 | 5 | 1.61% | 0.20 | 0.11 | 296% | 480% | 30% | LOSE |
| B2-B | 3 | 3 | -0.95% | 0.06 | 0.00 | 807% | 1522% | 55% | LOSE |
| B2-B | 3 | 5 | 3.69% | 0.29 | 0.16 | 233% | 375% | 44% | LOSE |
| B2-B | 5 | 3 | -2.75% | -0.05 | 0.00 | 100% | 100% | 43% | LOSE |
| B2-B | 5 | 5 | 1.33% | 0.17 | 0.07 | 380% | 610% | 42% | LOSE |
| B2-C | 3 | 3 | 4.10% | 0.30 | 0.21 | 187% | 338% | 68% | LOSE |
| B2-C | 3 | 5 | -10.74% | -0.40 | 0.00 | 100% | 100% | 62% | LOSE |
| B2-C | 5 | 3 | 9.48% | 0.60 | 0.74 | 99% | 189% | 64% | WIN |
| B2-C | 5 | 5 | -8.93% | -0.41 | 0.00 | 100% | 100% | 55% | LOSE |

---
## 3. Pass/Fail vs B1 Baseline

| Version | TopN | MinStk | Hold | RC>0.63 | T10<80% | MinStk5 | 2024>0 | PASS? |
|---------|-------|--------|------|---------|---------|---------|--------|-------|
| B2-A | 3 | 3 | ew | ❌ | ❌ | ❌ | ✅ | FAIL |
| B2-A | 5 | 3 | ew | ❌ | ❌ | ❌ | ✅ | FAIL |
| B2-B | 3 | 3 | ew | ❌ | ❌ | ❌ | ❌ | FAIL |
| B2-B | 5 | 3 | ew | ❌ | ❌ | ❌ | ❌ | FAIL |
| B2-C | 3 | 3 | ew | ❌ | ❌ | ❌ | ❌ | FAIL |
| B2-C | 5 | 3 | ew | ✅ | ❌ | ❌ | ✅ | FAIL |
| B2-A | 3 | 5 | ew | ❌ | ❌ | ❌ | ❌ | FAIL |
| B2-A | 5 | 5 | ew | ❌ | ❌ | ❌ | ✅ | FAIL |
| B2-B | 3 | 5 | ew | ❌ | ❌ | ❌ | ❌ | FAIL |
| B2-B | 5 | 5 | ew | ❌ | ❌ | ❌ | ❌ | FAIL |
| B2-C | 3 | 5 | ew | ❌ | ❌ | ❌ | ❌ | FAIL |
| B2-C | 5 | 5 | ew | ❌ | ❌ | ❌ | ✅ | FAIL |

---
## 4. Stop Condition Check

- Any RC > B1(0.63): ✅ YES (1 variants)
- All T10% > 80%: ⚠️ YES — time concentration unresolved
- MinStk=5 variants RC>=0.30: 0/6

---
## 5. Conclusion

**1 variant(s) beat B1 on RC (>0.63).**
Best: B2-C Top5 MinStk3 EW, RC=0.74


**MARGINAL/FAIL — B2-C improves RC but fails on:**
- T10%=99% >> 80% gate
- MinStk=5: 0 variants pass RC>=0.30

**Multi-factor ranking does not resolve B1's core fragility.**
Recommend: Pause B2. The problem is not factor selection — it is signal thinness at industry level.