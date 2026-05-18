# QTS — A 股量化交易系统

> Quantitative Trading System for A-share daily / medium-frequency research.  
> 目标是建立可信、可复现、可验证、可扩展的量化研究与交易基础设施。

---

## 1. 项目定位

QTS 不是简单的自动买卖脚本，而是一套覆盖以下环节的量化交易系统：

```text
数据接入 → 本地存储 → 因子计算 → 策略研究 → 回测验证
→ 风控 → 模拟盘 → 看板 → 未来小资金实盘
```

当前重点是：**先完成可靠数据和离线研究闭环，不急于进入 Paper Trading 或实盘。**

---

## 2. 当前状态

当前阶段：

```text
Industry Classification Solved → Ready for B1 Industry Rotation Offline Evaluation
```

核心状态：

| 模块 | 状态 |
|---|---|
| trend_breakout v2 | 已暂停，Candidate B 仅 historical baseline |
| HS300 横截面动量/反转 | 已暂停，信号太弱 |
| Pair long-only reversion | 已暂停，walk-forward 后 2025-2026 失效 |
| Event-driven | WAIT，成分股事件数据不足 |
| Industry Rotation | READY，行业分类已解决 |
| Tushare provider | 已作为可选 provider 接入，默认仍 AKShare |
| 行业分类数据资产 | `data/meta/industry_classification.csv`，5515 A 股，280/280 HS300 |

详细状态见：`HANDOFF.md`。当前唯一任务见：`TASK.md`。

---

## 3. 重要入口文件

| 文件 | 用途 |
|---|---|
| `CLAUDE.md` | Claude Code 工作宪法，只放长期规则 |
| `HANDOFF.md` | 当前项目状态、风险、下一步 |
| `TASK.md` | 当前唯一任务、验收标准、禁止事项 |
| `EXECUTION.md` | 最近执行记录和验证结果 |
| `FILE_INVENTORY.md` | 文件结构和重要文件用途 |
| `docs/coordination/` | 多 Agent / Agent Teams 编排、审计、Review Gate |
| `.claude/agents/` | Claude Code subagents 定义，也可作为 Agent Teams teammate 角色 |
| `.claude/skills/` | 可复用工作流 skill |
| `reports/` | 研究报告和历史证据 |

---

## 4. 项目核心结构

```text
qts/data/        数据源、calendar、parquet storage、数据质量
qts/factors/     因子计算
qts/strategies/  策略逻辑，trend_breakout v2 已暂停
qts/backtest/    回测引擎、broker simulation、performance
qts/risk/        风控
qts/execution/   执行层和模拟网关
qts/diagnosis/   诊断模块
scripts/         数据、回测、诊断、研究脚本
data/meta/       元数据资产，如行业分类
reports/         研究报告
configs/         配置
tests/           测试
```

详细文件清单见：`FILE_INVENTORY.md`。

---

## 5. 数据资产

当前关键数据资产：

| 资产 | 说明 |
|---|---|
| `data/raw/HS300_daily.parquet` | 日线行情，项目主行情数据 |
| `data/raw/index/sh000300_daily.parquet` | HS300 指数行情 |
| `data/historical_constituents.json` | 历史成分股快照，用于股票池过滤，不适合事件驱动 |
| `data/meta/industry_classification.csv` | 行业分类映射，Tushare industry label，280/280 HS300 覆盖 |

行业分类字段不是官方申万字段，当前标注为：

```text
Tushare industry label (Shenwan-style granular, not official Shenwan)
```

---

## 6. 当前可信 baseline

Candidate B 保留为 historical baseline，不升级 Paper Trading：

| 指标 | 值 |
|---|---:|
| annual_return | 7.90% |
| max_drawdown | -8.56% |
| fitness | 2.304 |
| trades | 1137 |

该策略结构已暂停，不继续 GA，不进入 Paper Trading。

---

## 7. 当前主线任务

当前主线：**B1 Industry Rotation Offline Evaluation**。

目标：用行业分类数据构建行业组合，评估行业级别月频轮动是否能产生稳定超额收益。

详细任务和验收标准见：`TASK.md`。

---

## 8. 基本运行示例

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest -q

# 未来函数检查
python scripts/check_future_leak.py

# 数据增量更新，默认 AKShare
python scripts/incremental_update_data.py --provider akshare

# Tushare verify-only，不写 parquet
python scripts/incremental_update_data.py --provider tushare --verify-only
```

实际命令以当前脚本帮助和 TASK.md 为准。

---

## 9. 协作原则

- 不使用 `git add .`
- 不提交 `.env`、token、backup bundle、临时 CSV、smoke/debug 报告
- L2/L3 任务必须先计划、后执行、再 Review
- 研究失败必须保留报告，不得隐藏
- 新增重要文件时同步 `FILE_INVENTORY.md`

多 Agent 工作流见：`docs/coordination/README.md`。启用 Claude Code Agent Teams 时，先读 `docs/coordination/AGENT_TEAMS.md`，并按项目角色创建 teammates。
