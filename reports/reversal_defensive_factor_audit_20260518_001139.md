# Reversal / Defensive Factor Audit

Generated: 2026-05-18 00:11
Period: 2022-01-01 ~ 2026-05-15
Mode: FULL
Features evaluated: 13

---

## 1. Data Coverage

- All trading days in range: 1054
- Days with valid records: 1053
- Avg universe size (constituent): 234.5
- Avg eligible after filters: 221.5
- Daily tradable count (median): 231
- Daily tradable count (P25/P75): 210 / 258
- Daily tradable count (min/max): 4 / 279

### Exclusion Reason Counts (cumulative)

| Reason | Total Excluded |
|--------|---------------:|
| insufficient_history | 11291 |
| limit_up_T | 1286 |
| close_lt_2 | 745 |
| open_T1_missing | 554 |
| limit_down_T | 439 |
| limit_up_T1 | 172 |
| is_st | 0 |
| suspended | 0 |
| suspended_T1 | 0 |

---

## 2. Single-Factor IC Summary


### IC on fwd_ret_10d (primary label)

| Feature | Mean IC | IC IR | IC>0 Ratio | N Days | Train IC | Val IC | Test IC |
|---------|---------|-------|------------|--------|----------|--------|---------|
| low_close_div_ma60 | 0.0373 | 0.151 | 56.1% | 1042 | 0.0710 | 0.0058 | 0.0101 |
| low_ma20_div_ma60 | 0.0348 | 0.141 | 59.1% | 1042 | 0.0549 | 0.0101 | 0.0231 |
| low_hl_range_20d | 0.0333 | 0.131 | 55.3% | 1042 | 0.0550 | 0.0671 | -0.0254 |
| low_ret_60d | 0.0312 | 0.120 | 57.3% | 1042 | 0.0400 | 0.0268 | 0.0213 |
| low_rs_60d | 0.0312 | 0.120 | 57.3% | 1042 | 0.0400 | 0.0268 | 0.0213 |
| low_vol_20d | 0.0246 | 0.097 | 54.0% | 1042 | 0.0524 | 0.0574 | -0.0424 |
| low_amount_rank_pct | 0.0186 | 0.094 | 54.7% | 1042 | 0.0446 | 0.0304 | -0.0298 |
| low_ret_20d | 0.0167 | 0.068 | 49.7% | 1042 | 0.0424 | 0.0067 | -0.0146 |
| low_rs_20d | 0.0167 | 0.068 | 49.7% | 1042 | 0.0424 | 0.0067 | -0.0146 |
| volume_ratio_5_20 | 0.0159 | 0.089 | 53.3% | 1042 | 0.0304 | -0.0080 | 0.0119 |
| amount_ratio_5_20 | 0.0115 | 0.063 | 51.6% | 1042 | 0.0203 | -0.0077 | 0.0129 |
| low_close_div_ma20 | 0.0088 | 0.037 | 47.9% | 1042 | 0.0300 | -0.0063 | -0.0116 |
| low_ret_5d | 0.0064 | 0.027 | 51.2% | 1042 | 0.0074 | 0.0111 | 0.0014 |

### Year-by-Year IC (fwd_ret_10d)

| Feature | 2022 | 2023 | 2024 | 2025 | 2026 |
|---------|------|------|------|------|------|
| low_close_div_ma60 | 0.1244 | 0.0181 | 0.0058 | 0.0200 | -0.0222 |
| low_ma20_div_ma60 | 0.0962 | 0.0140 | 0.0101 | 0.0237 | 0.0212 |
| low_hl_range_20d | 0.0093 | 0.1003 | 0.0671 | -0.0244 | -0.0288 |
| low_ret_60d | 0.0797 | 0.0005 | 0.0268 | 0.0286 | -0.0024 |
| low_rs_60d | 0.0797 | 0.0005 | 0.0268 | 0.0286 | -0.0024 |
| low_vol_20d | 0.0140 | 0.0904 | 0.0574 | -0.0483 | -0.0231 |
| low_amount_rank_pct | 0.0133 | 0.0757 | 0.0304 | -0.0281 | -0.0354 |
| low_ret_20d | 0.0726 | 0.0124 | 0.0067 | 0.0018 | -0.0678 |
| low_rs_20d | 0.0726 | 0.0124 | 0.0067 | 0.0018 | -0.0678 |
| volume_ratio_5_20 | 0.0357 | 0.0251 | -0.0080 | -0.0001 | 0.0509 |
| amount_ratio_5_20 | 0.0229 | 0.0177 | -0.0077 | -0.0000 | 0.0548 |
| low_close_div_ma20 | 0.0304 | 0.0295 | -0.0063 | 0.0009 | -0.0522 |
| low_ret_5d | 0.0063 | 0.0086 | 0.0111 | 0.0092 | -0.0240 |

### Mean IC Across All Labels

| Feature | fwd_ret_5d | fwd_ret_10d | fwd_ret_20d | mae_10d | hit_rate_10d |
|---------|------|------|------|------|------|
| low_close_div_ma60 | 0.0243 | 0.0373 | 0.0445 | -0.0833 | 0.0259 |
| low_ma20_div_ma60 | 0.0207 | 0.0348 | 0.0458 | -0.0723 | 0.0327 |
| low_hl_range_20d | 0.0274 | 0.0333 | 0.0538 | -0.3430 | 0.0206 |
| low_ret_60d | 0.0149 | 0.0312 | 0.0408 | -0.0814 | 0.0237 |
| low_rs_60d | 0.0149 | 0.0312 | 0.0408 | -0.0814 | 0.0237 |
| low_vol_20d | 0.0258 | 0.0246 | 0.0369 | -0.3024 | 0.0084 |
| low_amount_rank_pct | 0.0174 | 0.0186 | 0.0314 | -0.1729 | 0.0120 |
| low_ret_20d | 0.0099 | 0.0167 | 0.0327 | -0.0580 | 0.0114 |
| low_rs_20d | 0.0099 | 0.0167 | 0.0327 | -0.0580 | 0.0114 |
| volume_ratio_5_20 | 0.0019 | 0.0159 | 0.0029 | 0.0229 | 0.0130 |
| amount_ratio_5_20 | -0.0007 | 0.0115 | -0.0017 | 0.0302 | 0.0118 |
| low_close_div_ma20 | 0.0087 | 0.0088 | 0.0185 | -0.0477 | -0.0009 |
| low_ret_5d | 0.0072 | 0.0064 | 0.0035 | -0.0269 | -0.0040 |

---

## 3. Quantile Bucket Analysis (fwd_ret_10d)

Q1 = top 20% rank, Q5 = bottom 20% rank


### low_close_div_ma60

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46088 | 0.7384% | 0.0397% | 7.6153% | 50.1% | 4.7003% |
| Q2 | 45669 | 0.5007% | 0.0000% | 6.7952% | 49.6% | 4.2236% |
| Q3_mid | 45707 | 0.4778% | 0.0000% | 6.7609% | 49.1% | 4.1701% |
| Q4 | 45687 | 0.4844% | -0.1477% | 7.3623% | 48.6% | 4.4652% |
| Q5_bottom | 45289 | 0.7326% | -0.3839% | 9.2861% | 47.3% | 5.6162% |

  **Q1-Q5 spread**: 0.0058%  (t=0.10)
  **MAE ratio Q1/Q5**: 0.84

### low_ma20_div_ma60

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46107 | 0.7337% | 0.1058% | 7.7942% | 50.5% | 4.7588% |
| Q2 | 45662 | 0.6230% | 0.0000% | 6.8466% | 50.0% | 4.1881% |
| Q3_mid | 45689 | 0.5496% | 0.0000% | 6.8134% | 49.5% | 4.1589% |
| Q4 | 45688 | 0.5364% | -0.1669% | 7.5039% | 48.3% | 4.4497% |
| Q5_bottom | 45294 | 0.4891% | -0.5552% | 8.9391% | 46.4% | 5.6189% |

  **Q1-Q5 spread**: 0.2446%  (t=4.41)
  **MAE ratio Q1/Q5**: 0.85

### low_hl_range_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46315 | 0.5766% | 0.1848% | 5.1756% | 51.3% | 2.9306% |
| Q2 | 45897 | 0.4030% | 0.0000% | 5.9721% | 49.3% | 3.8243% |
| Q3_mid | 45905 | 0.4111% | -0.2488% | 6.8282% | 48.0% | 4.5098% |
| Q4 | 45916 | 0.4649% | -0.3895% | 8.0923% | 47.5% | 5.3305% |
| Q5_bottom | 45466 | 1.0852% | -0.2497% | 10.7645% | 48.7% | 6.5965% |

  **Q1-Q5 spread**: -0.5086%  (t=-9.10)
  **MAE ratio Q1/Q5**: 0.44

### low_ret_60d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46321 | 0.7180% | 0.0426% | 7.6696% | 50.1% | 4.7067% |
| Q2 | 45921 | 0.5750% | 0.0000% | 6.7657% | 49.5% | 4.1198% |
| Q3_mid | 45931 | 0.4947% | 0.0000% | 7.0152% | 48.9% | 4.1758% |
| Q4 | 45905 | 0.5125% | -0.1618% | 7.2128% | 48.4% | 4.4497% |
| Q5_bottom | 45494 | 0.6547% | -0.3195% | 9.1920% | 47.8% | 5.7029% |

  **Q1-Q5 spread**: 0.0633%  (t=1.13)
  **MAE ratio Q1/Q5**: 0.83

### low_rs_60d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46321 | 0.7180% | 0.0426% | 7.6696% | 50.1% | 4.7067% |
| Q2 | 45921 | 0.5750% | 0.0000% | 6.7657% | 49.5% | 4.1198% |
| Q3_mid | 45931 | 0.4947% | 0.0000% | 7.0152% | 48.9% | 4.1758% |
| Q4 | 45905 | 0.5125% | -0.1618% | 7.2128% | 48.4% | 4.4497% |
| Q5_bottom | 45494 | 0.6547% | -0.3195% | 9.1920% | 47.8% | 5.7029% |

  **Q1-Q5 spread**: 0.0633%  (t=1.13)
  **MAE ratio Q1/Q5**: 0.83

### low_vol_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46418 | 0.4379% | 0.0678% | 5.0545% | 50.2% | 3.0994% |
| Q2 | 45996 | 0.3703% | -0.1327% | 6.2293% | 48.5% | 3.9430% |
| Q3_mid | 46024 | 0.4370% | -0.1735% | 6.9798% | 48.5% | 4.5434% |
| Q4 | 46009 | 0.5929% | -0.1973% | 8.0969% | 48.6% | 5.2369% |
| Q5_bottom | 45575 | 1.1054% | -0.2120% | 10.5755% | 48.8% | 6.3642% |

  **Q1-Q5 spread**: -0.6675%  (t=-12.18)
  **MAE ratio Q1/Q5**: 0.49

### low_amount_rank_pct

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46405 | 0.5882% | 0.0699% | 6.1526% | 50.3% | 3.7761% |
| Q2 | 46005 | 0.5481% | 0.0000% | 6.6552% | 49.2% | 4.1240% |
| Q3_mid | 46025 | 0.5340% | -0.1247% | 7.4222% | 48.7% | 4.5723% |
| Q4 | 45998 | 0.4832% | -0.1955% | 7.9429% | 48.3% | 4.9881% |
| Q5_bottom | 45568 | 0.7858% | -0.2749% | 9.4921% | 48.2% | 5.7128% |

  **Q1-Q5 spread**: -0.1976%  (t=-3.74)
  **MAE ratio Q1/Q5**: 0.66

### low_ret_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46349 | 0.5910% | -0.1106% | 7.6316% | 48.9% | 4.7852% |
| Q2 | 45962 | 0.4323% | 0.0000% | 6.8008% | 49.4% | 4.2875% |
| Q3_mid | 45947 | 0.5224% | 0.0000% | 6.7883% | 49.5% | 4.1587% |
| Q4 | 45967 | 0.5794% | 0.0000% | 7.4745% | 49.1% | 4.4472% |
| Q5_bottom | 45538 | 0.8180% | -0.3045% | 9.1565% | 47.8% | 5.4860% |

  **Q1-Q5 spread**: -0.2271%  (t=-4.08)
  **MAE ratio Q1/Q5**: 0.87

### low_rs_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46349 | 0.5910% | -0.1106% | 7.6316% | 48.9% | 4.7852% |
| Q2 | 45962 | 0.4323% | 0.0000% | 6.8008% | 49.4% | 4.2875% |
| Q3_mid | 45947 | 0.5224% | 0.0000% | 6.7883% | 49.5% | 4.1587% |
| Q4 | 45967 | 0.5794% | 0.0000% | 7.4745% | 49.1% | 4.4472% |
| Q5_bottom | 45538 | 0.8180% | -0.3045% | 9.1565% | 47.8% | 5.4860% |

  **Q1-Q5 spread**: -0.2271%  (t=-4.08)
  **MAE ratio Q1/Q5**: 0.87

### volume_ratio_5_20

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46309 | 0.7487% | 0.0000% | 8.1895% | 49.3% | 4.8725% |
| Q2 | 45921 | 0.6487% | 0.0000% | 7.4881% | 49.7% | 4.5908% |
| Q3_mid | 45903 | 0.5451% | -0.0895% | 7.4424% | 48.8% | 4.5493% |
| Q4 | 45908 | 0.5410% | -0.1042% | 7.4894% | 48.8% | 4.5456% |
| Q5_bottom | 45458 | 0.4497% | -0.2036% | 7.4267% | 48.1% | 4.5973% |

  **Q1-Q5 spread**: 0.2990%  (t=5.80)
  **MAE ratio Q1/Q5**: 1.06

### amount_ratio_5_20

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46312 | 0.7552% | -0.0226% | 8.3079% | 49.3% | 4.9458% |
| Q2 | 45919 | 0.6479% | 0.0000% | 7.5728% | 49.5% | 4.5917% |
| Q3_mid | 45897 | 0.5469% | -0.0839% | 7.3523% | 48.8% | 4.5081% |
| Q4 | 45913 | 0.5213% | -0.1116% | 7.4660% | 48.7% | 4.5368% |
| Q5_bottom | 45458 | 0.4618% | -0.1789% | 7.3194% | 48.3% | 4.5722% |

  **Q1-Q5 spread**: 0.2934%  (t=5.68)
  **MAE ratio Q1/Q5**: 1.08

### low_close_div_ma20

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46300 | 0.5622% | -0.1849% | 7.5601% | 48.4% | 4.8328% |
| Q2 | 45923 | 0.4445% | 0.0000% | 6.7956% | 49.2% | 4.2700% |
| Q3_mid | 45888 | 0.5055% | 0.0000% | 6.7766% | 49.2% | 4.1583% |
| Q4 | 45910 | 0.6065% | 0.0000% | 7.5696% | 49.4% | 4.4554% |
| Q5_bottom | 45478 | 0.8195% | -0.2235% | 9.1401% | 48.3% | 5.4474% |

  **Q1-Q5 spread**: -0.2573%  (t=-4.64)
  **MAE ratio Q1/Q5**: 0.89

### low_ret_5d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46383 | 0.5390% | -0.2423% | 7.8808% | 48.0% | 5.0098% |
| Q2 | 45972 | 0.5447% | 0.0000% | 7.0235% | 49.2% | 4.3003% |
| Q3_mid | 45993 | 0.5237% | 0.0000% | 6.8699% | 49.3% | 4.1263% |
| Q4 | 45988 | 0.6447% | 0.0000% | 7.4030% | 49.6% | 4.3595% |
| Q5_bottom | 45550 | 0.6811% | -0.1799% | 8.7540% | 48.6% | 5.3646% |

  **Q1-Q5 spread**: -0.1421%  (t=-2.59)
  **MAE ratio Q1/Q5**: 0.93

---

## 4. Volatility Features — Bidirectional Assessment


---

## 5. Cross-Sectional Rank Discrimination

- **low_close_div_ma60**: Q1-Q5 spread=0.0058%, IC CV=6.64, IC>0=56.1%
- **low_ma20_div_ma60**: Q1-Q5 spread=0.2446%, IC CV=7.11, IC>0=59.1%
- **low_hl_range_20d**: Q1-Q5 spread=-0.5086%, IC CV=7.63, IC>0=55.3%
- **low_ret_60d**: Q1-Q5 spread=0.0633%, IC CV=8.31, IC>0=57.3%
- **low_rs_60d**: Q1-Q5 spread=0.0633%, IC CV=8.31, IC>0=57.3%

### Rank Autocorrelation (Top20% Stay Rate)

| Feature | Avg Top20% Overlap | Median | P25 |
|---------|-------------------|--------|-----|
| low_ret_5d | 64.8% | 65.4% | 57.8% |
| low_ret_20d | 81.5% | 82.5% | 77.6% |
| low_ret_60d | 88.3% | 89.3% | 85.7% |
| low_vol_20d | 91.2% | 92.9% | 89.4% |
| low_hl_range_20d | 95.1% | 95.7% | 93.6% |
| low_amount_rank_pct | 80.7% | 81.4% | 77.2% |
| low_close_div_ma20 | 79.6% | 80.5% | 75.5% |
| low_close_div_ma60 | 87.7% | 88.6% | 85.4% |
| low_ma20_div_ma60 | 95.4% | 95.9% | 94.3% |
| low_rs_20d | 81.5% | 82.5% | 77.6% |
| low_rs_60d | 88.3% | 89.3% | 85.7% |
| volume_ratio_5_20 | 77.9% | 78.2% | 73.8% |
| amount_ratio_5_20 | 78.4% | 78.8% | 74.4% |

---

## 6. Comparison with trend_breakout v2


### 6.1 Within-day Discrimination
trend_breakout v2: 94.2% days N vs N+1 score gap ≈ 0
cross-sectional: Percentile rank guarantees uniform distribution per day.
Key question: Does rank translate to fwd_ret difference?
- low_close_div_ma60: IC=0.0373, IC>0=56.1% → BETTER
- low_ma20_div_ma60: IC=0.0348, IC>0=59.1% → BETTER
- low_hl_range_20d: IC=0.0333, IC>0=55.3% → BETTER

### 6.2 Next-day Stability (vs 80.7% dropout)
trend_breakout v2: 80.7% new entries gone next day, avg stay=0.2d
- low_ret_5d: Top20% avg overlap=64.8% → MUCH BETTER
- low_ret_20d: Top20% avg overlap=81.5% → MUCH BETTER
- low_ret_60d: Top20% avg overlap=88.3% → MUCH BETTER

### 6.3 Year Stability
trend_breakout v2: B weak in 2023 (score_high=0.80 cost)
cross-sectional: checking if IC consistent across years...
- low_close_div_ma60: 4/5 years IC>0 → STABLE
- low_ma20_div_ma60: 5/5 years IC>0 → STABLE
- low_hl_range_20d: 3/5 years IC>0 → MIXED

---

## 7. Pass / Stop Verdict


### Passing Features

None.

### Marginal Features

- **low_close_div_ma60**: IC=0.0373 — C5: t-stat=0.10 < 1.5
- **low_ma20_div_ma60**: IC=0.0348 — C2: |IC IR|=0.141 < 0.15

### Failing Features

- **low_hl_range_20d**: C2: |IC IR|=0.131 < 0.15; C3: test IC=-0.0254 <= 0; C5: spread=-0.5086% <= 0
- **low_ret_60d**: C2: |IC IR|=0.120 < 0.15; C5: t-stat=1.13 < 1.5
- **low_rs_60d**: C2: |IC IR|=0.120 < 0.15; C5: t-stat=1.13 < 1.5
- **low_vol_20d**: C2: |IC IR|=0.097 < 0.15; C3: test IC=-0.0424 <= 0; C5: spread=-0.6675% <= 0
- **low_amount_rank_pct**: C1: |IC|=0.0186 < 0.02; C2: |IC IR|=0.094 < 0.15; C3: test IC=-0.0298 <= 0; C5: spread=-0.1976% <= 0
- **low_ret_20d**: C1: |IC|=0.0167 < 0.02; C2: |IC IR|=0.068 < 0.15; C3: test IC=-0.0146 <= 0; C5: spread=-0.2271% <= 0
- **low_rs_20d**: C1: |IC|=0.0167 < 0.02; C2: |IC IR|=0.068 < 0.15; C3: test IC=-0.0146 <= 0; C5: spread=-0.2271% <= 0
- **volume_ratio_5_20**: C1: |IC|=0.0159 < 0.02; C2: |IC IR|=0.089 < 0.15; C3: val IC=-0.0080 <= 0
- **amount_ratio_5_20**: C1: |IC|=0.0115 < 0.02; C2: |IC IR|=0.063 < 0.15; C3: val IC=-0.0077 <= 0
- **low_close_div_ma20**: C1: |IC|=0.0088 < 0.02; C2: |IC IR|=0.037 < 0.15; C3: val IC=-0.0063 <= 0; C3: test IC=-0.0116 <= 0; C5: spread=-0.2573% <= 0
- **low_ret_5d**: C1: |IC|=0.0064 < 0.02; C2: |IC IR|=0.027 < 0.15; C5: spread=-0.1421% <= 0

### Overall Verdict

**C: Stop** — No reversal/defensive factor passes all criteria. Cross-sectional alpha on HS300 insufficient. Consider pivoting to alternative strategy structures (e.g., event-driven, pair-trading, multi-universe).

---

## 7b. Extra Robustness Checks


### 7b.1 Excluding 2024 (924 market shock)

| Feature | Full IC | IC excl 2024 | Stable? |
|---------|---------|-------------|---------|
| low_close_div_ma60 | 0.0373 | 0.0351 | YES |
| low_ma20_div_ma60 | 0.0348 | 0.0388 | YES |
| low_hl_range_20d | 0.0333 | 0.0141 | WEAK |
| low_ret_60d | 0.0312 | 0.0266 | YES |
| low_rs_60d | 0.0312 | 0.0266 | YES |
| low_vol_20d | 0.0246 | 0.0083 | WEAK |
| low_amount_rank_pct | 0.0186 | 0.0064 | WEAK |
| low_ret_20d | 0.0167 | 0.0048 | YES |
| low_rs_20d | 0.0167 | 0.0048 | YES |
| volume_ratio_5_20 | 0.0159 | 0.0279 | YES |
| amount_ratio_5_20 | 0.0115 | 0.0238 | YES |
| low_close_div_ma20 | 0.0088 | 0.0022 | YES |
| low_ret_5d | 0.0064 | 0.0000 | YES |

### 7b.2 Regime Separation: 2022 Bear vs 2025-2026

| Feature | 2022 IC | 2025 IC | 2026 IC | Bear→Bull Consistent? |
|---------|---------|---------|---------|----------------------|
| low_close_div_ma60 | 0.1244 | 0.0200 | -0.0222 | FLIPS |
| low_ma20_div_ma60 | 0.0962 | 0.0237 | 0.0212 | YES |
| low_hl_range_20d | 0.0093 | -0.0244 | -0.0288 | FLIPS |
| low_ret_60d | 0.0797 | 0.0286 | -0.0024 | FLIPS |
| low_rs_60d | 0.0797 | 0.0286 | -0.0024 | FLIPS |
| low_vol_20d | 0.0140 | -0.0483 | -0.0231 | FLIPS |
| low_amount_rank_pct | 0.0133 | -0.0281 | -0.0354 | FLIPS |
| low_ret_20d | 0.0726 | 0.0018 | -0.0678 | FLIPS |
| low_rs_20d | 0.0726 | 0.0018 | -0.0678 | FLIPS |
| volume_ratio_5_20 | 0.0357 | -0.0001 | 0.0509 | FLIPS |
| amount_ratio_5_20 | 0.0229 | -0.0000 | 0.0548 | FLIPS |
| low_close_div_ma20 | 0.0304 | 0.0009 | -0.0522 | FLIPS |
| low_ret_5d | 0.0063 | 0.0092 | -0.0240 | FLIPS |

### 7b.3 Low-Volatility: Alpha or Just Low Risk?


**low_vol_20d**:
- Q1 (low vol): ret=0.4379%, MAE=3.0994%, ret/MAE=0.1413, hit=50.2%
- Q5 (high vol): ret=1.1054%, MAE=6.3642%, ret/MAE=0.1737, hit=48.8%
- **High-vol better**: risk-adjusted return favors high-vol

**low_hl_range_20d**:
- Q1 (low vol): ret=0.5766%, MAE=2.9306%, ret/MAE=0.1968, hit=51.3%
- Q5 (high vol): ret=1.0852%, MAE=6.5965%, ret/MAE=0.1645, hit=48.7%
- **Alpha**: low-vol has better risk-adjusted return

---

## 8. Key Diagnostic Metrics (vs trend_breakout v2)

| Metric | trend_breakout v2 | cross-sectional | Verdict |
|--------|-------------------|-----------------|---------|
| Avg daily candidates | ~4 | 231 | BETTER |
| Within-day discrimination | 94% gap≈0 | Uniform rank | GUARANTEED BETTER |
| Next-day turnover | 78% | See autocorr above | — |
| False signal rate | 48.4% FB | N/A (no breakout) | DIFFERENT PARADIGM |