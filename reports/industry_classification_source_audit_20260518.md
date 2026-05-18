# Industry Classification Source Audit — 2026-05-18

Generated: 2026-05-18 14:38
HS300 constituents (latest quarter): 280

---

## 1. Tushare (jiaoch.site)

- Endpoint: http://jiaoch.site/stock_basic
- HTTP status: 200
- API code: 0
- API msg: success
- Token status: **SET (60 chars)**
- Available: **YES**
- Fields: ['ts_code', 'symbol', 'name', 'area', 'industry', 'market', 'list_date']
- Total A-share stocks: **5515**
- Classification: Tushare industry label (Shenwan-style granular, not official Shenwan)
- HS300 coverage: **280/280 (100.0%)**
- HS300 missing: **0**
- Unique industries (in HS300): **65**
- Effective industries (>=3 stocks): **39**

### HS300 Industry Distribution (Top 20)

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

---

## 2. AKShare CSRC (stock_info_sz_name_code)

- Classification: CSRC Level 1
- Total SZ stocks: 2892
- Unique industries: 19
- HS300 coverage: **103/280 (36.8%)**
- HS300 missing (SH-listed): 177
- Missing sample: ['600009', '600010', '600011', '600015', '600016', '600018', '600019', '600023', '600025', '600026']
- Available: **YES**

### Industry Distribution (HS300 SZ stocks only)

| Industry | Count |
|----------|------:|
| C 制造业 | 73 |
| J 金融业 | 9 |
| I 信息技术 | 6 |
| K 房地产 | 2 |
| B 采矿业 | 2 |
| G 运输仓储 | 2 |
| A 农林牧渔 | 2 |
| M 科研服务 | 2 |
| F 批发零售 | 1 |
| L 商务服务 | 1 |
| D 水电煤气 | 1 |
| Q 卫生 | 1 |
| R 文化传播 | 1 |

- Effective industries (>=3 stocks): **3**

WARNING: 'C 制造业' dominates with 73/103 stocks. This category spans liquor, semiconductors, automobiles, and pharmaceuticals — not a tradable 'sector' for rotation purposes.

---

## 3. AKShare Shenwan L2 (stock_individual_info_em)

- Classification: Shenwan Level 2
- Tested: 5 SH stocks
- Success: 0
- Errors: 5
- Available: **NO**
- Reason: Severe rate-limiting: 5 consecutive errors after 0 successes

---

## 4. AKShare Eastmoney (stock_zh_a_spot_em)

- Classification: Eastmoney industry
- Total stocks: N/A
- Industry columns: N/A
- Unique industries: N/A
- Available: **NO**
- Reason: ProxyError: HTTPSConnectionPool(host='82.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=1

---

## 5. Summary

| Source | Classification | HS300 Coverage | Available |
|--------|---------------|---------------|:---------:|
| Tushare (jiaoch.site) | Tushare industry label (Shenwan-style granular, not official Shenwan) | 100.0% | YES |
| CSRC Level 1 (SZ only) | CSRC Level 1 | 36.8% | YES |
| Shenwan L2 (per-stock) | Shenwan Level 2 | 0/5 sample | NO |
| Eastmoney | Eastmoney industry | N/A | NO |

---

## 6. Verdict

**A: Industry classification data available. Can proceed with formal integration.**

- Tushare/jiaoch.site provides 100% HS300 coverage with 39 effective industries
- 65 unique industry labels — sufficient granularity for rotation

### Recommended next steps:
1. Create `data/meta/industry_classification.csv` — static mapping: symbol, industry, source, updated_at
2. Re-open B (Industry Rotation) — monthly rebalance, 28+ effective industries
3. Re-open A (Pair Trading) — same-industry filtering now possible
4. Commit the industry map as a reusable project asset

---

## 7. Recommendations

1. **Completed**: `data/meta/industry_classification.csv` created (5515 A-shares, 639.7 KB)
2. **Completed**: Industry labels confirmed as Tushare-style granular (Shenwan-like, not official Shenwan)
3. **Optional upgrade**: Official Shenwan/CITIC classification via Tushare Pro or Wind for L1/L2 hierarchy
4. **Do NOT**: Use stock code prefix to infer industry
5. **Re-open**: B Industry Rotation + A Pair Trading (same-industry filter) now feasible