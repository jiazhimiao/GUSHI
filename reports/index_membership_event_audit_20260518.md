# Index Membership Event Data Audit — 2026-05-18

> 目标: 确认 `data/historical_constituents.json` 能否支持 C 方向（事件驱动指数调入/调出效应研究）

---

## 1. 文件结构审计

### 1.1 Top-Level

| Key | Type | Value |
|-----|------|-------|
| description | str | "Historical index constituents based on Sina inclusion dates" |
| method | str | "Current constituents filtered backwards by inclusion_date" |
| limitation | str | "Only tracks stocks that SURVIVED..." |
| generated_at | str | "2026-05-10" |
| indices | dict | 1 key: "HS300" |

### 1.2 HS300 Index Entry

| Key | Type | Value |
|-----|------|-------|
| index_code | str | "000300" |
| total_current | int | 300 |
| earliest_inclusion | str | "2005-04-08" (index-level, NOT per-stock) |
| latest_inclusion | str | "2025-12-15" (index-level, NOT per-stock) |
| quarterly | dict | 36 quarters, 2018-01-01 ~ 2026-10-01 |

### 1.3 Quarterly Snapshot Structure

- **每个 key**: `YYYY-MM-DD` 格式 (季度首日: Jan 1, Apr 1, Jul 1, Oct 1)
- **每个 value**: `list[str]` — 股票代码列表，**含重复项**（需去重）
- **每期去重后数量**: 122 ~ 280 只
- **元素类型**: 纯字符串股票代码，无结构化字段

### 1.4 覆盖率 (vs 实际 HS300=300 只)

| 年份 | 覆盖数 | 覆盖率 | 缺失 |
|------|--------|--------|------|
| 2018 | 122 | 40.7% | 178 |
| 2019 | 141 | 47.0% | 159 |
| 2020 | 154 | 51.3% | 146 |
| 2021 | 173 | 57.7% | 127 |
| 2022 | 197 | 65.7% | 103 |
| 2023 | 214 | 71.3% | 86 |
| 2024 | 233 | 77.7% | 67 |
| 2025 | 260 | 86.7% | 40 |
| 2026 | 280 | 93.3% | 20 |

缺失股票 = 历史上曾被纳入 HS300 但 2026-05-10 前已被调出的股票。

---

## 2. 事件检测能力

### 2.1 调入检测: ✅ YES

季度间对比可检测新增股票:

```
prev_quarter_set = set(Q[prev_key])
curr_quarter_set = set(Q[curr_key])
added = curr_quarter_set - prev_quarter_set
```

- 2018-2026 期间共检测到 **158 次调入事件**
- 分布: 2018(10), 2019(15), 2020(17), 2021(15), 2022(27), 2023(14), 2024(24), 2025(25), 2026(11)
- 2022 年调入事件最多 (HS300 加速扩容)

### 2.2 调出检测: ❌ NO

- 任意两季度之间 `removed = prev_set - curr_set` **始终为 0**
- 原因: 数据构建方法为"当前成分股按 inclusion_date 反向过滤"
- 已被调出的股票完全不在数据中，无法检测其调出时间
- long-range 验证: 2018-Q1 的 122 只股票全部出现在 2026-Q4 — 无调出

### 2.3 earliest_inclusion: ⚠️ INDEX-LEVEL ONLY

- `earliest_inclusion: "2005-04-08"` 是整个 HS300 指数中最早的单只股票纳入日期
- **不是**每个股票的 inclusion_date
- 构建脚本 (`build_historical_universe.py`) 调用了 `ak.index_stock_cons()` 获取每只股票的 inclusion_date，但**未保存到 JSON 中**
- 如果需要 per-stock inclusion_date，需要重新运行构建脚本并保存该字段

### 2.4 公告日: ❌ NO

- JSON 中无公告日字段
- 季度快照日期 (Jan 1/Apr 1/Jul 1/Oct 1) 不是公告日

### 2.5 生效日: ⚠️ IMPLIED BUT WRONG

- 季度快照日期可作为"已知成分股的日期"，但不是指数调整的生效日
- HS300 实际调整时间线:
  ```
  公告日: ~6月10日 / ~12月10日
  生效日: ~6月20日 / ~12月20日 (公告后第二个周五)
  季度快照: 7月1日 / 1月1日
  ```
- **检测延迟**: 9-12 个交易日后于实际生效日
- 此时市场已充分消化调入信息，alpha 大概率已被套利

---

## 3. 未来函数 / Lookahead 风险

### 3.1 严重风险: 季度快照 ≠ 可交易日

| 风险类型 | 严重程度 | 说明 |
|----------|:--------:|------|
| 调入检测滞后 | **HIGH** | 季度快照比实际生效日晚 9-12 个交易日 |
| 调出完全不可见 | **CRITICAL** | 无法做多空价差研究 |
| 早期覆盖率不足 | **HIGH** | 2018-2020 覆盖 < 55%，缺失样本非随机 |
| 幸存者偏差 | **CRITICAL** | 只包含持续到 2026 的成分股，系统性地剔除弱势股 |
| 无公告日 | **HIGH** | 无法区分公告效应和生效后效应 |

### 3.2 如果直接用季度日期做交易

假设在 2022-07-01 检测到某股票"调入"，买入:
- 该股票的实际公告日约为 2022-06-10，生效日约 2022-06-20
- 7 月 1 日买入时，该股票已经在 HS300 中交易了 ~2 周
- 调入带来的买入资金流已在生效日前后完成
- **如果你在 7 月 1 日后的 N 天看到了正的超额收益，它可能是幸存者偏差（因为缺失的调出股票表现更差），而不是可交易的 alpha**

---

## 4. 事件表设计

### 4.1 字段定义

```text
event_id           唯一标识，如 "HS300_add_2022Q3_000301"
event_date         检测到事件的季度首日 (YYYY-MM-DD)
event_type         "added" (暂不支持 "removed")
symbol             股票代码
current_snapshot   当前季度日期 (YYYY-MM-DD)
previous_snapshot  前一季度日期 (YYYY-MM-DD)
detection_lag_days 距离实际 HS300 生效日的估算延迟天数
known_rebalance_month  推定的调整月份 (6 或 12)
is_quarter_start   True (始终为季度首日)
can_trade_on_event_date  需验证 open(T+N) 是否可交易
lookahead_risk     HIGH (始终为 HIGH — 检测日期晚于实际事件)
survivorship_note  "Only stocks surviving to 2026-05-10 are captured"
```

### 4.2 示例记录

```text
event_id:               HS300_add_2022Q3_000301
event_date:             2022-07-01
event_type:             added
symbol:                 000301
current_snapshot:       2022-07-01
previous_snapshot:      2022-04-01
detection_lag_days:     ~12 (June 2022 rebalance)
known_rebalance_month:  6
is_quarter_start:       True
can_trade_on_event_date: unknown (need T+1 open data)
lookahead_risk:         HIGH
survivorship_note:      "Only stocks surviving to 2026-05-10 are captured"
```

### 4.3 建议的扩展字段（如重新拉取数据）

```text
announcement_date       公告日 (需外部数据)
effective_date          生效日 (需外部数据)
inclusion_date          每只股票的纳入日期 (需保存 build 脚本的原始字段)
```

---

## 5. C1 可行性判定

### 判定: D — 数据不足，暂不做 C 方向（事件驱动）

### 判定理由

| 标准 | 评估 |
|------|------|
| 能做公告后效应研究？ | ❌ 无公告日 |
| 能做生效后效应研究？ | ⚠️ 可做，但检测滞后 9-12 天，且幸存者偏差严重 |
| 能做描述性统计？ | ⚠️ 可做，但结论不能用于交易 |
| 能做交易研究？ | ❌ 早期覆盖不足 + 无调出 + 无公告日 |

### 能否升级为 A/B/C？

**可以升级到 B**，如果:

1. 重新运行 `build_historical_universe.py`，保存每只股票的 `inclusion_date` 字段
2. 从外部来源补充 HS300 调整公告日期 (Wind/东方财富/中证指数公司)
3. 接受"只能做调入效应"的限制（调出数据永远不可得）

但即使升级后，核心限制仍然存在:
- **永远无法获取调出数据** — AKShare Sina API 只返回当前成分股
- **样本量有限** — 158 次调入事件，远小于横截面因子的大样本优势
- **检测总是滞后** — inclusion_date 本身就是生效日，不是公告日

### 替代路径

如果未来可以获取:
- 中证指数公司官方调整公告 (含公告日和生效日)
- Wind/Choice 终端的成分股变更历史

则可以重新评估 C 方向。目前不阻碍此方向进入等待队列。

---

## 6. 如果强行做 C1 (仅供记录)

以下方案仅作记录，**不建议实施**。如果未来数据升级后可以重新打开。

### 最小离线验证

```
1. 构造事件表 (158 次调入):
   - event_date = 季度首日
   - 前面 20 日 / 后面 60 日的日线 OHLCV
   
2. 对每个 event:
   - CAR(-20, -1): 事件前 20 日超额收益 (是否提前反应)
   - CAR(+5): 事件后 5 日
   - CAR(+20): 事件后 20 日
   - CAR(+60): 事件后 60 日
   - 超额收益 = stock_ret - HS300_index_ret

3. 统计:
   - mean CAR, median CAR
   - win rate (CAR > 0)
   - t-test (H0: mean CAR = 0)
   - year-by-year CAR

4. 对照:
   - 调入后收益 vs HS300 基准
   - 调入后 2024 是否主导
```

### 在当前数据下预期结果

- 事件前 20 日: 大概率正超额（市场提前买入）
- 事件后 5/20 日: 接近 0 或轻微负（均值回归）
- 事件后 60 日: 无统计显著性
- 样本量 (158) 不足以支撑稳健结论

---

## 7. 对 Next-Structure Research Plan 的修正

### 7.1 C 方向降级

C (Event-Driven) 从 ★★★ 降至 **WAIT** — 需要数据升级后才能评估。

如果重新拉取数据并保存 per-stock inclusion_date，可从 D 升级到 B。

### 7.2 A 方向修正 (Pair Trading)

在 next_structure_research_plan 中补充:
- A-share 无个股做空工具 → pair trading 的"做多弱势侧"是 long-only，不等同于多空对冲
- 需要明确: 仅做多 Z-score 超跌的一侧，不构建完整多空 pair
- 行业分类不得用代码前缀推断 — 必须通过 AKShare 获取申万行业分类

### 7.3 优先级调整

修正后:
1. **A (Pair Trading)**: ★★★ — 使用现有数据，范式最不同
2. **B (Industry Rotation)**: ★★☆ — 需要行业分类数据
3. **C (Event-Driven)**: WAIT — 需要数据升级

---

## 8. 结论

1. `historical_constituents.json` 是为**回测成分股过滤**目的构建的，不适合事件驱动研究。
2. 可以检测 158 次调入，但检测滞后 9-12 天，早期覆盖率 < 55%。
3. 无法检测调出，无法获取公告日。
4. **判定: D — 数据不足，暂不做 C 方向。**
5. 优先推进 A (Pair Trading)，需要行业分类数据 + 明确 long-only 约束。
6. 如需重新打开 C，第一步是重新运行 `build_historical_universe.py` 并保存每只股票的 inclusion_date。
