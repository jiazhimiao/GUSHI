# FILE_INVENTORY.md — QTS 文件结构和用途

> 本文件是项目文件地图。新增、删除、重命名重要文件时必须同步更新。  
> README 只放总览，具体文件说明放这里。

---

## 1. 根目录文件

| 文件 | 用途 |
|---|---|
| `README.md` | 项目总览、当前主线、快速入口 |
| `CLAUDE.md` | Claude Code 工作宪法，只放长期规则 |
| `HANDOFF.md` | 当前状态、风险、下一步 |
| `TASK.md` | 当前唯一任务和验收标准 |
| `EXECUTION.md` | 最近执行记录和验证摘要 |
| `FILE_INVENTORY.md` | 本文件，项目文件地图 |
| `requirements.txt` | Python 依赖 |
| `.env` | 本地密钥，gitignored，不提交 |

---

## 2. docs/coordination/

| 文件 | 用途 |
|---|---|
| `README.md` | 多 Agent 协作入口说明 |
| `PROJECT_INDEX.md` | 项目入口索引和当前主线 |
| `TASK_LEVELS.md` | L0-L3 任务等级 |
| `MULTI_AGENT_ORCHESTRATION.md` | 多 Agent 路由和工作流 |
| `REVIEW_GATE.md` | QA / Safety / Doc review gate |
| `CHECKLISTS.md` | 数据、策略、回测、文档检查清单 |
| `FAILURE_RECOVERY.md` | 失败回流和恢复规则 |
| `TASK_GRAPH.md` | 当前任务图 |
| `AGENT_AUDIT_LOG.md` | 多 Agent 审计日志 |
| `SESSION_HANDOFF.md` | 会话交接模板 |
| `DECISIONS.md` | 关键决策记录 |
| `RISK_REGISTER.md` | 项目风险登记 |
| `ROADMAP.md` | 中长期路线图 |
| `SUBTASK_TEMPLATE.md` | 子任务交接模板 |
| `AGENT_REGISTRY.md` | Agent 注册表 |

---

## 3. .claude/

### .claude/agents/

| Agent | 用途 |
|---|---|
| `qts-main-orchestrator.md` | 主协调、任务拆分、边界控制 |
| `qts-data-dev.md` | 数据源、parquet、schema、行业/事件数据 |
| `qts-backtest-dev.md` | 回测、broker、撮合、费用、T+1 |
| `qts-strategy-dev.md` | 策略、因子、offline research |
| `qts-risk-execution-dev.md` | 风控、仓位、模拟盘、执行报告 |
| `qts-qa-reviewer.md` | diff、测试、未来函数、口径审查 |
| `qts-safety-reviewer.md` | token、实盘、危险命令、安全审查 |
| `qts-doc-auditor.md` | 文档、交接、任务图、审计日志 |

### .claude/skills/

| Skill | 用途 |
|---|---|
| `quant-multi-agent-workflow/` | 多 Agent 工作流 |
| `quant-session-handoff/` | 会话交接和上下文压缩 |

---

## 4. qts/ 核心库

```text
qts/data/        数据源、交易日历、storage、quality
qts/factors/     因子计算
qts/strategies/  策略逻辑，trend_breakout v2 已暂停
qts/backtest/    回测引擎、broker simulation、performance
qts/risk/        风控
qts/execution/   执行层和网关
qts/diagnosis/   诊断模块
qts/app/         Streamlit 看板
qts/utils/       配置、日志、时间工具
```

---

## 5. scripts/ 脚本分组

### 数据管线

```text
update_daily_data.py
incremental_update_data.py
build_historical_universe.py
build_industry_classification_map.py
verify_industry_classification_source.py
verify_tushare_alignment.py
```

### 回测与验证

```text
run_backtest.py
check_future_leak.py
check_candidate_b_repro.py
validate_candidate_b.py
verify_determinism.py
baseline_stability_check.py
```

### GA / 优化

```text
ga_optimizer.py
ga_optimizer_v2.py
ga_smoke_test.py
```

### trend_breakout v2 诊断

```text
diagnose_entry_quality.py
taxonomy_signal_count.py
audit_entry_experiments.py
run_entry_experiment.py
```

### 横截面 / Pair / Industry research

```text
evaluate_cross_sectional_alpha.py
diagnose_pair_universe.py
diagnose_pair_walkforward.py
# B1 若新增 evaluate_industry_rotation.py，需要同步本文件
```

---

## 6. data/

| 路径 | 用途 | 提交规则 |
|---|---|---|
| `data/raw/` | 主行情和指数数据 | 大文件谨慎提交；不要随意覆盖 |
| `data/meta/` | 小型元数据资产 | 可提交，如行业分类 CSV |
| `data/backtest/` | 回测结果 | 按任务确认 |
| `data/experiments/` | 实验产物 | 默认不提交 |
| `data/ga_results/` | GA 结果 | 按任务确认 |

明确不提交：

```text
临时交易明细 CSV
pair_walkforward_trades.csv
pair_walkforward_periods.csv
残缺行业分类 JSON
raw 数据备份
```

---

## 7. reports/

报告按研究方向分组：

```text
trend_breakout / entry quality
Tushare / data provider
cross-sectional alpha
reversal / defensive factors
event-driven membership audit
pair feasibility
industry classification
industry rotation
project status
```

报告是研究证据，不应塞入 CLAUDE.md。

---

## 8. tests/ 和 configs/

```text
tests/      单元测试和回归测试
configs/    策略和系统配置
```

涉及交易规则、撮合、费用、T+1、滑点的修改必须增加或更新测试。

---

## 9. 维护规则

新增文件时判断：

| 类型 | 应更新 |
|---|---|
| 新脚本 | `FILE_INVENTORY.md` |
| 新研究报告 | `FILE_INVENTORY.md` + `HANDOFF.md` 如影响状态 |
| 新任务状态 | `TASK.md` |
| 阶段完成 | `HANDOFF.md` + `EXECUTION.md` |
| 新多 Agent 文档 | `docs/coordination/` + 本文件 |
| 新 agent/skill | `.claude/` + 本文件 |
