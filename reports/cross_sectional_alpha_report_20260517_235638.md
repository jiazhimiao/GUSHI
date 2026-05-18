# Cross-Sectional Alpha Phase 1 — Single-Factor IC Scan

Generated: 2026-05-17 23:56
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
| close_div_ma60 | -0.0373 | -0.151 | 43.7% | 1042 | -0.0710 | -0.0058 | -0.0101 |
| ma20_div_ma60 | -0.0348 | -0.141 | 40.9% | 1042 | -0.0549 | -0.0101 | -0.0231 |
| hl_range_20d | -0.0333 | -0.131 | 44.5% | 1042 | -0.0550 | -0.0671 | 0.0254 |
| ret_60d | -0.0312 | -0.120 | 42.3% | 1042 | -0.0400 | -0.0268 | -0.0213 |
| rs_60d | -0.0312 | -0.120 | 42.3% | 1042 | -0.0400 | -0.0268 | -0.0213 |
| vol_20d | -0.0246 | -0.097 | 45.9% | 1042 | -0.0524 | -0.0574 | 0.0424 |
| amount_rank_pct | -0.0186 | -0.094 | 45.0% | 1042 | -0.0446 | -0.0304 | 0.0298 |
| ret_20d | -0.0167 | -0.068 | 49.9% | 1042 | -0.0424 | -0.0067 | 0.0146 |
| rs_20d | -0.0167 | -0.068 | 49.9% | 1042 | -0.0424 | -0.0067 | 0.0146 |
| volume_ratio_5_20 | 0.0159 | 0.089 | 53.3% | 1042 | 0.0304 | -0.0080 | 0.0119 |
| amount_ratio_5_20 | 0.0115 | 0.063 | 51.6% | 1042 | 0.0203 | -0.0077 | 0.0129 |
| close_div_ma20 | -0.0088 | -0.037 | 51.5% | 1042 | -0.0300 | 0.0063 | 0.0116 |
| ret_5d | -0.0064 | -0.027 | 48.7% | 1042 | -0.0074 | -0.0111 | -0.0014 |

### Year-by-Year IC (fwd_ret_10d)

| Feature | 2022 | 2023 | 2024 | 2025 | 2026 |
|---------|------|------|------|------|------|
| close_div_ma60 | -0.1244 | -0.0181 | -0.0058 | -0.0200 | 0.0222 |
| ma20_div_ma60 | -0.0962 | -0.0140 | -0.0101 | -0.0237 | -0.0212 |
| hl_range_20d | -0.0093 | -0.1003 | -0.0671 | 0.0244 | 0.0288 |
| ret_60d | -0.0797 | -0.0005 | -0.0268 | -0.0286 | 0.0024 |
| rs_60d | -0.0797 | -0.0005 | -0.0268 | -0.0286 | 0.0024 |
| vol_20d | -0.0140 | -0.0904 | -0.0574 | 0.0483 | 0.0231 |
| amount_rank_pct | -0.0133 | -0.0757 | -0.0304 | 0.0281 | 0.0354 |
| ret_20d | -0.0726 | -0.0124 | -0.0067 | -0.0018 | 0.0678 |
| rs_20d | -0.0726 | -0.0124 | -0.0067 | -0.0018 | 0.0678 |
| volume_ratio_5_20 | 0.0357 | 0.0251 | -0.0080 | -0.0001 | 0.0509 |
| amount_ratio_5_20 | 0.0229 | 0.0177 | -0.0077 | -0.0000 | 0.0548 |
| close_div_ma20 | -0.0304 | -0.0295 | 0.0063 | -0.0009 | 0.0522 |
| ret_5d | -0.0063 | -0.0086 | -0.0111 | -0.0092 | 0.0240 |

### Mean IC Across All Labels

| Feature | fwd_ret_5d | fwd_ret_10d | fwd_ret_20d | mae_10d | hit_rate_10d |
|---------|------|------|------|------|------|
| close_div_ma60 | -0.0243 | -0.0373 | -0.0445 | 0.0833 | -0.0259 |
| ma20_div_ma60 | -0.0207 | -0.0348 | -0.0458 | 0.0723 | -0.0327 |
| hl_range_20d | -0.0274 | -0.0333 | -0.0538 | 0.3430 | -0.0206 |
| ret_60d | -0.0149 | -0.0312 | -0.0408 | 0.0814 | -0.0237 |
| rs_60d | -0.0149 | -0.0312 | -0.0408 | 0.0814 | -0.0237 |
| vol_20d | -0.0258 | -0.0246 | -0.0369 | 0.3024 | -0.0084 |
| amount_rank_pct | -0.0174 | -0.0186 | -0.0314 | 0.1729 | -0.0120 |
| ret_20d | -0.0099 | -0.0167 | -0.0327 | 0.0580 | -0.0114 |
| rs_20d | -0.0099 | -0.0167 | -0.0327 | 0.0580 | -0.0114 |
| volume_ratio_5_20 | 0.0019 | 0.0159 | 0.0029 | 0.0229 | 0.0130 |
| amount_ratio_5_20 | -0.0007 | 0.0115 | -0.0017 | 0.0302 | 0.0118 |
| close_div_ma20 | -0.0087 | -0.0088 | -0.0185 | 0.0477 | 0.0009 |
| ret_5d | -0.0072 | -0.0064 | -0.0035 | 0.0269 | 0.0040 |

---

## 3. Quantile Bucket Analysis (fwd_ret_10d)

Q1 = top 20% rank, Q5 = bottom 20% rank


### close_div_ma60

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46106 | 0.7304% | -0.3871% | 9.2852% | 47.2% | 5.6020% |
| Q2 | 45687 | 0.4852% | -0.1330% | 7.3346% | 48.7% | 4.4572% |
| Q3_mid | 45707 | 0.4654% | 0.0000% | 6.7310% | 49.0% | 4.1711% |
| Q4 | 45669 | 0.5104% | 0.0000% | 6.8163% | 49.6% | 4.2263% |
| Q5_bottom | 45271 | 0.7427% | 0.0518% | 7.6177% | 50.2% | 4.7024% |

  **Q1-Q5 spread**: -0.0122%  (t=-0.22)
  **MAE ratio Q1/Q5**: 1.19

### ma20_div_ma60

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46112 | 0.4850% | -0.5569% | 8.9170% | 46.3% | 5.6055% |
| Q2 | 45686 | 0.5421% | -0.1538% | 7.4955% | 48.4% | 4.4403% |
| Q3_mid | 45691 | 0.5476% | 0.0000% | 6.7978% | 49.5% | 4.1553% |
| Q4 | 45661 | 0.6276% | 0.0000% | 6.8618% | 49.9% | 4.1925% |
| Q5_bottom | 45290 | 0.7339% | 0.1099% | 7.8061% | 50.5% | 4.7655% |

  **Q1-Q5 spread**: -0.2489%  (t=-4.49)
  **MAE ratio Q1/Q5**: 1.18

### hl_range_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46303 | 1.0794% | -0.2517% | 10.7374% | 48.6% | 6.5777% |
| Q2 | 45915 | 0.4567% | -0.3891% | 8.0522% | 47.5% | 5.3200% |
| Q3_mid | 45905 | 0.4043% | -0.2529% | 6.8087% | 47.9% | 4.4969% |
| Q4 | 45896 | 0.4139% | 0.0000% | 5.9670% | 49.4% | 3.8080% |
| Q5_bottom | 45480 | 0.5772% | 0.1874% | 5.1695% | 51.3% | 2.9224% |

  **Q1-Q5 spread**: 0.5022%  (t=9.05)
  **MAE ratio Q1/Q5**: 2.25

### ret_60d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46332 | 0.6573% | -0.3155% | 9.1739% | 47.8% | 5.6886% |
| Q2 | 45907 | 0.5097% | -0.1563% | 7.1893% | 48.4% | 4.4372% |
| Q3_mid | 45926 | 0.4877% | -0.0154% | 7.0036% | 48.9% | 4.1729% |
| Q4 | 45921 | 0.5790% | 0.0000% | 6.7765% | 49.5% | 4.1258% |
| Q5_bottom | 45486 | 0.7222% | 0.0507% | 7.6839% | 50.2% | 4.7124% |

  **Q1-Q5 spread**: -0.0649%  (t=-1.16)
  **MAE ratio Q1/Q5**: 1.21

### rs_60d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46332 | 0.6573% | -0.3155% | 9.1739% | 47.8% | 5.6886% |
| Q2 | 45907 | 0.5097% | -0.1563% | 7.1893% | 48.4% | 4.4372% |
| Q3_mid | 45926 | 0.4877% | -0.0154% | 7.0036% | 48.9% | 4.1729% |
| Q4 | 45921 | 0.5790% | 0.0000% | 6.7765% | 49.5% | 4.1258% |
| Q5_bottom | 45486 | 0.7222% | 0.0507% | 7.6839% | 50.2% | 4.7124% |

  **Q1-Q5 spread**: -0.0649%  (t=-1.16)
  **MAE ratio Q1/Q5**: 1.21

### vol_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46402 | 1.0976% | -0.2099% | 10.5484% | 48.8% | 6.3526% |
| Q2 | 46009 | 0.5854% | -0.2047% | 8.0709% | 48.6% | 5.2206% |
| Q3_mid | 46023 | 0.4315% | -0.1733% | 6.9579% | 48.5% | 4.5387% |
| Q4 | 45995 | 0.3781% | -0.1222% | 6.2117% | 48.6% | 3.9255% |
| Q5_bottom | 45593 | 0.4391% | 0.0664% | 5.0522% | 50.2% | 3.0910% |

  **Q1-Q5 spread**: 0.6585%  (t=12.11)
  **MAE ratio Q1/Q5**: 2.06

### amount_rank_pct

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46397 | 0.7818% | -0.2683% | 9.4658% | 48.2% | 5.7023% |
| Q2 | 45999 | 0.4819% | -0.1984% | 7.9377% | 48.2% | 4.9829% |
| Q3_mid | 46025 | 0.5262% | -0.1316% | 7.4088% | 48.7% | 4.5658% |
| Q4 | 46004 | 0.5564% | 0.0000% | 6.6458% | 49.3% | 4.1145% |
| Q5_bottom | 45576 | 0.5894% | 0.0701% | 6.1499% | 50.3% | 3.7731% |

  **Q1-Q5 spread**: 0.1924%  (t=3.66)
  **MAE ratio Q1/Q5**: 1.51

### ret_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46368 | 0.8158% | -0.3023% | 9.1312% | 47.9% | 5.4702% |
| Q2 | 45965 | 0.5717% | 0.0000% | 7.4687% | 49.1% | 4.4448% |
| Q3_mid | 45948 | 0.5267% | 0.0000% | 6.7704% | 49.5% | 4.1508% |
| Q4 | 45966 | 0.4274% | 0.0000% | 6.8153% | 49.3% | 4.2958% |
| Q5_bottom | 45516 | 0.5975% | -0.1062% | 7.6406% | 48.9% | 4.7906% |

  **Q1-Q5 spread**: 0.2183%  (t=3.93)
  **MAE ratio Q1/Q5**: 1.14

### rs_20d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46368 | 0.8158% | -0.3023% | 9.1312% | 47.9% | 5.4702% |
| Q2 | 45965 | 0.5717% | 0.0000% | 7.4687% | 49.1% | 4.4448% |
| Q3_mid | 45948 | 0.5267% | 0.0000% | 6.7704% | 49.5% | 4.1508% |
| Q4 | 45966 | 0.4274% | 0.0000% | 6.8153% | 49.3% | 4.2958% |
| Q5_bottom | 45516 | 0.5975% | -0.1062% | 7.6406% | 48.9% | 4.7906% |

  **Q1-Q5 spread**: 0.2183%  (t=3.93)
  **MAE ratio Q1/Q5**: 1.14

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

### close_div_ma20

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46314 | 0.8145% | -0.2269% | 9.1175% | 48.3% | 5.4343% |
| Q2 | 45909 | 0.6021% | 0.0000% | 7.5521% | 49.5% | 4.4477% |
| Q3_mid | 45890 | 0.5097% | 0.0000% | 6.7752% | 49.3% | 4.1549% |
| Q4 | 45921 | 0.4438% | 0.0000% | 6.7985% | 49.2% | 4.2788% |
| Q5_bottom | 45465 | 0.5636% | -0.1825% | 7.5723% | 48.4% | 4.8372% |

  **Q1-Q5 spread**: 0.2509%  (t=4.54)
  **MAE ratio Q1/Q5**: 1.12

### ret_5d

| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |
|--------|---|----------|------------|-----|----------|-----|
| Q1_top | 46386 | 0.6765% | -0.1771% | 8.7322% | 48.6% | 5.3489% |
| Q2 | 45974 | 0.6434% | 0.0000% | 7.3898% | 49.5% | 4.3549% |
| Q3_mid | 46000 | 0.5288% | 0.0000% | 6.8803% | 49.3% | 4.1263% |
| Q4 | 45987 | 0.5384% | 0.0000% | 7.0205% | 49.2% | 4.3066% |
| Q5_bottom | 45539 | 0.5436% | -0.2402% | 7.8949% | 48.0% | 5.0178% |

  **Q1-Q5 spread**: 0.1330%  (t=2.42)
  **MAE ratio Q1/Q5**: 1.07

---

## 4. Volatility Features — Bidirectional Assessment


### vol_20d
- Mean IC: -0.0246 → **low-vol preferred (negative IC)**
- IC IR: -0.097
- IC>0 ratio: 45.9%

### hl_range_20d
- Mean IC: -0.0333 → **low-vol preferred (negative IC)**
- IC IR: -0.131
- IC>0 ratio: 44.5%

---

## 5. Cross-Sectional Rank Discrimination

- **close_div_ma60**: Q1-Q5 spread=-0.0122%, IC CV=6.64, IC>0=43.7%
- **ma20_div_ma60**: Q1-Q5 spread=-0.2489%, IC CV=7.11, IC>0=40.9%
- **hl_range_20d**: Q1-Q5 spread=0.5022%, IC CV=7.63, IC>0=44.5%
- **ret_60d**: Q1-Q5 spread=-0.0649%, IC CV=8.31, IC>0=42.3%
- **rs_60d**: Q1-Q5 spread=-0.0649%, IC CV=8.31, IC>0=42.3%

### Rank Autocorrelation (Top20% Stay Rate)

| Feature | Avg Top20% Overlap | Median | P25 |
|---------|-------------------|--------|-----|
| ret_5d | 66.4% | 66.4% | 60.0% |
| ret_20d | 82.7% | 83.7% | 79.1% |
| ret_60d | 89.2% | 90.2% | 86.5% |
| vol_20d | 90.7% | 92.3% | 88.6% |
| hl_range_20d | 92.9% | 93.9% | 90.9% |
| volume_ratio_5_20 | 77.9% | 78.2% | 73.8% |
| amount_rank_pct | 80.0% | 80.5% | 76.6% |
| amount_ratio_5_20 | 78.4% | 78.8% | 74.4% |
| rs_20d | 82.7% | 83.7% | 79.1% |
| rs_60d | 89.2% | 90.2% | 86.5% |
| close_div_ma20 | 78.4% | 79.1% | 74.4% |
| close_div_ma60 | 86.6% | 87.5% | 83.8% |
| ma20_div_ma60 | 94.8% | 95.7% | 93.6% |

---

## 6. Comparison with trend_breakout v2


### 6.1 Within-day Discrimination
trend_breakout v2: 94.2% days N vs N+1 score gap ≈ 0
cross-sectional: Percentile rank guarantees uniform distribution per day.
Key question: Does rank translate to fwd_ret difference?
- close_div_ma60: IC=-0.0373, IC>0=43.7% → NO BETTER
- ma20_div_ma60: IC=-0.0348, IC>0=40.9% → NO BETTER
- hl_range_20d: IC=-0.0333, IC>0=44.5% → NO BETTER

### 6.2 Next-day Stability (vs 80.7% dropout)
trend_breakout v2: 80.7% new entries gone next day, avg stay=0.2d
- ret_5d: Top20% avg overlap=66.4% → MUCH BETTER
- ret_20d: Top20% avg overlap=82.7% → MUCH BETTER
- ret_60d: Top20% avg overlap=89.2% → MUCH BETTER

### 6.3 Year Stability
trend_breakout v2: B weak in 2023 (score_high=0.80 cost)
cross-sectional: checking if IC consistent across years...
- close_div_ma60: 1/5 years IC>0 → UNSTABLE
- ma20_div_ma60: 0/5 years IC>0 → UNSTABLE
- hl_range_20d: 2/5 years IC>0 → UNSTABLE

---

## 7. Pass / Stop Verdict


### Passing Features

- **volume_ratio_5_20**: IC=0.0159, IC IR=0.089
- **amount_ratio_5_20**: IC=0.0115, IC IR=0.063

### Marginal Features

- **close_div_ma20**: IC=-0.0088 — P3: Only 2/5 years IC>0

### Failing Features

- **close_div_ma60**: P1: t-stat=-0.22 < 1.5; P2: IC>0 ratio=43.7%; P3: Only 1/5 years IC>0
- **ma20_div_ma60**: P1: t-stat=-4.49 < 1.5; P2: IC>0 ratio=40.9%; P3: Only 0/5 years IC>0
- **hl_range_20d**: P2: IC>0 ratio=44.5%; P3: Only 2/5 years IC>0; P4: Q1 MAE (0.0658) >> Q5 MAE (0.0292)
- **ret_60d**: P1: t-stat=-1.16 < 1.5; P2: IC>0 ratio=42.3%; P3: Only 1/5 years IC>0
- **rs_60d**: P1: t-stat=-1.16 < 1.5; P2: IC>0 ratio=42.3%; P3: Only 1/5 years IC>0
- **vol_20d**: P2: IC>0 ratio=45.9%; P3: Only 2/5 years IC>0; P4: Q1 MAE (0.0635) >> Q5 MAE (0.0309)
- **amount_rank_pct**: P2: IC>0 ratio=45.0%; P3: Only 2/5 years IC>0; P4: Q1 MAE (0.0570) >> Q5 MAE (0.0377)
- **ret_20d**: P2: IC>0 ratio=49.9%; P3: Only 1/5 years IC>0
- **rs_20d**: P2: IC>0 ratio=49.9%; P3: Only 1/5 years IC>0
- **ret_5d**: P2: IC>0 ratio=48.7%; P3: Only 1/5 years IC>0

### Overall Verdict

**MARGINAL** — Only 2 features pass. Phase 2 may have limited upside but still worth exploring composite with passing features.

Recommended Phase 2 features: volume_ratio_5_20, amount_ratio_5_20

---

## 8. Key Diagnostic Metrics (vs trend_breakout v2)

| Metric | trend_breakout v2 | cross-sectional | Verdict |
|--------|-------------------|-----------------|---------|
| Avg daily candidates | ~4 | 231 | BETTER |
| Within-day discrimination | 94% gap≈0 | Uniform rank | GUARANTEED BETTER |
| Next-day turnover | 78% | See autocorr above | — |
| False signal rate | 48.4% FB | N/A (no breakout) | DIFFERENT PARADIGM |