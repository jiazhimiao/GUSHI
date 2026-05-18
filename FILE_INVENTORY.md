# 项目文件清单 — 2026-05-18

## 项目根目录

| 文件 | 用途 |
|------|------|
| `CLAUDE.md` | Claude Code 项目执行规则（长期有效） |
| `README.md` | 项目总览、快速开始、技术栈、路线图 |
| `HANDOFF.md` | 会话交接：当前状态、baseline、实验结论 |
| `TASK.md` | 下一步唯一任务 |
| `EXECUTION.md` | 本轮会话执行总结 |
| `FILE_INVENTORY.md` | 本文件 — 项目文件结构说明 |
| `OPTIMIZATION.md` | 参数优化路线图（PSO/GA） |
| `requirements.txt` | Python 依赖 |
| `.env` | TUSHARE_TOKEN（gitignored，不提交） |

---

## qts/ — 核心库

```
qts/
├── data/              数据层
│   ├── akshare_client.py    AKShare 数据接口
│   ├── tushare_provider.py  Tushare/jiaoch.site 数据接口（bulk daily）
│   ├── calendar.py          A股交易日历
│   ├── storage.py           Parquet 读写
│   └── quality.py           数据质量检查
│
├── factors/            因子层
│   ├── factor_engine.py     因子注册与批量计算
│   ├── momentum.py          动量因子
│   └── volatility.py        波动率因子
│
├── strategies/         策略层
│   ├── base.py              Strategy 抽象类
│   ├── signal_strategy.py   多因子信号策略
│   ├── trend_breakout.py    趋势突破策略 v2（五档止损 + 三档仓位）
│   ├── dow_filter.py        道氏理论牛市过滤
│   ├── regime_engine.py     市场状态引擎
│   └── portfolio.py         组合构建器
│
├── backtest/           回测引擎
│   ├── engine.py            回测主循环
│   ├── broker_sim.py        A股模拟撮合
│   ├── performance.py       绩效指标
│   ├── report.py            报告生成
│   ├── data_context.py      数据上下文（pivot/cache 统一入口）
│   └── paper_broker.py      模拟盘撮合
│
├── execution/          执行层
│   ├── base_gateway.py      BrokerGateway 抽象接口
│   ├── mock_gateway.py      模拟网关
│   └── order_manager.py     订单生命周期管理
│
├── risk/               风控层
│   ├── pre_trade.py         下单前风控
│   └── kill_switch.py       紧急熔断
│
├── diagnosis/          诊断模块
│   ├── market_regime.py     市场状态诊断
│   ├── regime_diagnostics.py 状态引擎诊断
│   └── signal_report.py     信号报告
│
├── app/
│   └── streamlit_app.py     Streamlit 看板（5 Tab）
│
└── utils/              工具
    ├── config.py            YAML + Pydantic 配置加载
    ├── logger.py            loguru 日志
    └── time.py              交易日历工具
```

---

## scripts/ — 运行脚本

### 数据管线

| 脚本 | 用途 |
|------|------|
| `update_daily_data.py` | 拉取日线数据（AKShare） |
| `incremental_update_data.py` | 增量更新（支持 Tushare 可选 provider） |
| `build_historical_universe.py` | 构建历史成分股快照 |
| `build_industry_classification_map.py` | 构建行业分类 CSV（Tushare stock_basic） |
| `fetch_extended_universe.py` | 拉取扩展股票池 |

### 回测与验证

| 脚本 | 用途 |
|------|------|
| `run_backtest.py` | 运行回测 |
| `check_future_leak.py` | 未来函数系统检测 |
| `check_candidate_b_repro.py` | Candidate B 可复现性检查 |
| `validate_candidate_b.py` | Candidate B 验证 |
| `verify_determinism.py` | 确定性检查 |
| `verify_tushare_alignment.py` | AKShare vs Tushare 数据一致性 |
| `baseline_stability_check.py` | Baseline 稳定性检查 |

### GA 优化

| 脚本 | 用途 |
|------|------|
| `ga_optimizer.py` | GA 优化器 v1 |
| `ga_optimizer_v2.py` | GA 优化器 v2 |
| `ga_smoke_test.py` | GA 冒烟测试 |

### 诊断 (trend_breakout v2)

| 脚本 | 用途 |
|------|------|
| `diagnose_entry_quality.py` | 入场信号质量诊断 |
| `diagnose_score_high_sensitivity.py` | score_high 敏感度 |
| `diagnose_pullback_funnel.py` | pullback 漏斗分析 |
| `diagnose_F_failure.py` | F 实验失败诊断 |
| `diagnose_d2_failure.py` | D2 实验失败诊断 |
| `diagnose_d3_prep.py` | D3 实验准备 |
| `diagnose_d3c_gate.py` | D3c gate 诊断 |
| `taxonomy_signal_count.py` | 信号链分类审计 |
| `audit_entry_experiments.py` | 入场实验审计 |
| `run_entry_experiment.py` | 入场实验运行 |
| `evaluate_scoring_redesign.py` | 评分重设计离线评估 |
| `day_level_gate_audit.py` | 日级 gate 审计 |

### 跨截面 alpha (本轮)

| 脚本 | 用途 |
|------|------|
| `evaluate_cross_sectional_alpha.py` | 单因子 IC 扫描（momentum + reversal 模式） |

### Pair 诊断 (本轮)

| 脚本 | 用途 |
|------|------|
| `diagnose_pair_universe.py` | A0 — 相关性 pair universe + 均值回归 |
| `diagnose_pair_walkforward.py` | A0.5 — walk-forward + 非重叠持仓模拟 |

### 行业分类 (本轮)

| 脚本 | 用途 |
|------|------|
| `verify_industry_classification_source.py` | 行业分类数据源审计 |
| `build_industry_classification_map.py` | 构建行业分类静态 CSV |

### 其他

| 脚本 | 用途 |
|------|------|
| `param_robustness.py` | 参数敏感度 + 网格搜索 |
| `compute_fitness_decomposition.py` | Fitness 分解 |
| `profile_backtrack.py` / `v2` | 回测性能分析 |
| `experiment_matrix.py` | 实验矩阵 |
| `sweep_pb_gate.py` / `v2` | pullback gate sweep |
| `generate_daily_signal.py` | 每日信号生成 |
| `diagnose_paper_replay.py` | 模拟盘重放诊断 |
| `diagnose.py` | 通用诊断入口 |
| `diagnose_2023.py` | 2023 年专项诊断 |

---

## data/ — 数据文件

### data/raw/ — 原始数据

| 文件 | 大小 | 用途 |
|------|------|------|
| `HS300_daily.parquet` | 123 MB | 全 A 股日线 OHLCV（2022+ 覆盖 HS300） |
| `calendar.parquet` | 37 KB | A股交易日历 |
| `index/sh000300_daily.parquet` | 268 KB | HS300 指数日线 |

### data/meta/ — 元数据

| 文件 | 大小 | 用途 |
|------|------|------|
| `industry_classification.csv` | 640 KB | 5515 只 A 股行业分类（Tushare） |

### data/backtest/ — 回测结果

| 文件 | 用途 |
|------|------|
| `result.json` | 最新回测结果 |
| `trades.csv` | 最新交易明细 |
| `nav.csv` | 最新净值曲线 |
| `*/` | 历史回测归档（按时间戳） |

### data/ga_results/ — GA 优化结果

| 目录 | 用途 |
|------|------|
| `candidate_b_validation_*/` | Candidate B 验证 |
| `candidate_b_final_check_*/` | B 最终检查 |
| `exit_loosen_*/` | 止损放松实验 |
| `hold_winner_*/` | 持有赢家实验 |
| `risk_budget_*/` | 风险预算实验 |
| `candidate_c_safe_*/` | C_safe 候选 |
| `local_search_phase*/` | 局部搜索 |
| `v2_smoke_*/` | GA 冒烟测试 |
| `v2_pilot_*/` | GA 试点 |

### data/experiments/ — 实验矩阵结果

| 内容 | 用途 |
|------|------|
| `experiment_matrix_*/` | 入场质量单因子实验 (A/B/C/D/F) |

### 其他

| 文件 | 用途 |
|------|------|
| `historical_constituents.json` | HS300 历史成分股季度快照（36 季） |
| `universe_codes.json` | 扩展股票池代码 |
| `paper_trading/` | 模拟盘状态/持仓/交易 |
| `data/diagnosis/` | 诊断输出 |
| `data/stability_check/` | 稳定性检查 |

---

## reports/ — 研究报告

### 跨截面 alpha

| 文件 | 内容 |
|------|------|
| `cross_sectional_alpha_plan_20260517.md` | 研究方案 |
| `cross_sectional_alpha_report_*235638.md` | Phase 1 全量结果（MARGINAL） |
| `reversal_defensive_factor_audit_*001139.md` | 反转/防御审计（STOP） |

### 新结构研究

| 文件 | 内容 |
|------|------|
| `next_structure_research_plan_20260518.md` | 三方向研究方案（v2） |
| `index_membership_event_audit_20260518.md` | C0 事件数据审计（WAIT） |
| `pair_universe_feasibility_audit_20260518.md` | A0 pair 可行性 |
| `pair_walkforward_feasibility_recheck_20260518.md` | A0.5 walk-forward（FAIL） |
| `industry_rotation_data_audit_plan_20260518.md` | B0 方案 |
| `industry_rotation_data_audit_20260518.md` | B0 审计（WAIT→已解决） |
| `industry_classification_source_audit_20260518.md` | 行业分类数据源审计（A） |
| `industry_classification_map_report_20260518.md` | 行业分类映射验证 |

### 项目状态

| 文件 | 内容 |
|------|------|
| `project_status_20260517.md` | 项目状态快照 |

### trend_breakout v2

| 文件 | 内容 |
|------|------|
| `diagnose_entry_quality_*.txt` | 入场质量诊断 |
| `entry_quality_experiment_summary_*.txt` | 实验总结 |
| `scoring_redesign_eval_*.txt` | 评分重设计评估 |
| `day_level_gate_audit_*.txt` | 日级 gate 审计 |
| `signal_count_taxonomy_audit_*.txt` | 信号分类审计 |
| `post_experiment_audit_v2_*.txt` | 实验后审计 |

### Tushare

| 文件 | 内容 |
|------|------|
| `tushare_alignment_report_*.md` | AKShare vs Tushare 对齐 |
| `tushare_*_discrepancy_diagnosis.md` | 偏差诊断 |

---

## 其他目录

| 目录 | 用途 |
|------|------|
| `configs/` | YAML 配置（data/broker/risk/strategies） |
| `tests/` | pytest 测试（broker rules, future leak, data quality） |
| `docs/` | 项目文档（index.html, PARAM_OPTIMIZATION.md） |
| `handoff/` | 本地备份（bundle，不提交） |
| `.claude/` | Claude Code 设置和 skills |
