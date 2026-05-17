# TASK — 2026-05-17 (FINAL)

## Status: trend_breakout v2 PAUSED

### Completed (this session)
1. Entry quality diagnosis + 9 single-factor experiments (A/B/C/D)
2. Post-experiment audit (fitness reconciliation, taxonomy, FB rate)
3. Scoring redesign offline evaluation (5 variants, 8113 candidates)
4. Day-level gate audit (2027 trading days)
5. Signal count taxonomy (L0-L10 hierarchy)

### Final Conclusions
- No experiment passes both stop conditions (overlap≥40% AND FB≤35%)
- All 5 score variants fail offline evaluation
- Day-level gating cannot fix stock-level alpha decay
- RegimeEngine improvements have limited upside (max +5-10pp good_day)
- Current alpha structure insufficient for GA or Paper Trading

### Next Task
Open new alpha research direction. Do NOT continue modifying trend_breakout v2.

### Preserved
- Candidate B as historical baseline (ann=7.90%, dd=-8.56%, trades=1137)
- All experiment reports in reports/
- All diagnostic scripts in scripts/
