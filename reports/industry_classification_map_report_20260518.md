# Industry Classification Map Report — 2026-05-18

Generated: 2026-05-18 14:42
Source: Tushare (jiaoch.site) stock_basic endpoint

---

## 1. Data Asset

- File: `data/meta/industry_classification.csv`
- Rows: **5515**
- Size: **639.7 KB**
- Encoding: UTF-8 BOM
- Fields: symbol, ts_code, name, area, market, industry_raw, industry_l1, industry_l2, source, updated_at
- Token in file: **NO**
- Token in report: **NO**

---

## 2. HS300 Coverage

- HS300 constituents (latest quarter): 280
- Covered: **280/280 (100.0%)**
- Missing: **0**

---

## 3. Industry Distribution

- Unique industry labels: **65**
- Effective industries (>=3 stocks in HS300): **39**

### Top 30 Industries (HS300)

| Industry | Count |
|----------|------:|
| 银行 | 23 |
| 证券 | 22 |
| 半导体 | 17 |
| 电气设备 | 15 |
| 元器件 | 14 |
| 软件服务 | 9 |
| 建筑工程 | 8 |
| 通信设备 | 7 |
| 白酒 | 7 |
| 化学制药 | 7 |
| 汽车整车 | 6 |
| 航空 | 6 |
| 化工原料 | 6 |
| 医疗保健 | 6 |
| 家用电器 | 5 |
| 汽车配件 | 5 |
| 生物制药 | 5 |
| IT设备 | 5 |
| 煤炭开采 | 5 |
| 小金属 | 5 |
| 保险 | 5 |
| 工程机械 | 4 |
| 新型电力 | 4 |
| 空运 | 4 |
| 全国地产 | 3 |
| 农药化肥 | 3 |
| 中成药 | 3 |
| 铜 | 3 |
| 铝 | 3 |
| 食品 | 3 |

---

## 4. Classification Notes

- Industry labels are **Tushare-style granular labels** (Shenwan-like, not official Shenwan)
- Examples: 银行, 证券, 白酒, 半导体, 电气设备
- These are more granular than CSRC Level 1 (19 categories)
- industry_l1 = industry_raw (no official L1/L2 hierarchy available)
- industry_l2 is empty
- If official Shenwan/CITIC classification is needed, a separate mapping table would be required

---

## 5. Re-open Assessment

- **B Industry Rotation**: **YES** — 39 effective industries (>=3 stocks), sufficient for monthly rotation
- **A Pair Trading (same-industry)**: **YES** — industry labels available for all 280 HS300 stocks
- **C Event-Driven**: **STILL WAIT** — industry data does not help with missing announcement/effective dates

---

## 6. Reproducibility

- Script: `scripts/build_industry_classification_map.py`
- Requires: TUSHARE_TOKEN in `.env`
- Output: `data/meta/industry_classification.csv`
- Regenerate: `python scripts/build_industry_classification_map.py`