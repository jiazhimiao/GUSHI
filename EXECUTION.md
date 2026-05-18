# EXECUTION — 最近执行记录

> 本文件记录最近阶段执行摘要。详细证据见 `reports/`。

---

## 2026-05-17 ~ 2026-05-18：Alpha Research Cycle

### 1. trend_breakout v2 封存

- Candidate B 保留为 historical baseline。
- trend_breakout v2 不继续 GA，不进入 Paper Trading。
- 关键问题：信号稀缺、rotation 高、假突破高、日内评分无区分度。

### 2. Tushare provider

- 新增可选 Tushare / jiaoch.site provider。
- 默认 provider 仍为 AKShare。
- verify-only 支持不写 parquet 的口径验证。

### 3. HS300 横截面研究

- `scripts/evaluate_cross_sectional_alpha.py`
- 动量/趋势/量能单因子扫描：信号弱。
- 反转/防御因子审计：无因子通过全部条件。

### 4. Event-driven C0

- `historical_constituents.json` 无公告日、真实生效日、调出数据。
- C 方向 WAIT。

### 5. Pair A0 / A0.5

- A0 全样本 pair 发现存在未来函数风险。
- A0.5 修正为 walk-forward、T+1 open、非重叠交易、excess 分离。
- 结论：2025-2026 失效，after-cost excess 转负，Pair 暂停。

### 6. Industry Classification

- Tushare stock_basic 可用。
- 构建 `data/meta/industry_classification.csv`。
- 5515 A 股，280/280 HS300，65 行业标签，39 有效行业。
- 行业分类阻塞解除。

---

## 最新提交记录参考

```text
c7102d4 data: add industry classification map (280/280 HS300, 65 labels)
74f679f research: archive cross-sectional and structure feasibility studies
9b18600 data: add optional tushare provider for incremental updates
70f40de docs: update project status after trend breakout diagnostics
8a36b95 research: archive trend_breakout v2 diagnostic cycle
```

如本地 ahead origin/main，先尝试 push；网络阻断时保留本地 bundle，不要 reset。

---

## 2026-05-18：B1 QA Review

- QA 独立审查 B1 诊断报告。
- 结论：**REQUEST_CHANGES**。CONDITIONAL PASS 降级为 OBSERVE。
- 发现：
  1. Static hold 通信设备（328%）碾压 rotation（~57%），削弱轮动价值
  2. EW variants Ex-2025 基本失效（4/6 < 3.05%）
  3. AW/EW 差距 2-3x 未解释，可能是大市值 beta
- 不允许进入正式回测和 Paper Trading。
- 下一步：B1 补充诊断（TASK.md Section 8）。

---

## 当前未完成

```text
B1 Industry Rotation — OBSERVE（QA REQUEST_CHANGES）
B1 补充诊断（static hold 事前对比 + AW/EW 差距分解 + EW-only）
```

禁止直接进入回测、GA、Paper Trading。
