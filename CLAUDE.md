# CLAUDE.md

本文件是 QTS - A股量化交易系统 的 Agent 工作规则。

适用对象：

```text
Claude Code
DeepSeek / DS coding agent
其他代码生成或代码修改工具
```

本文件不是普通 README，而是项目开发约束。  
任何 Agent 在本项目中工作时，必须优先遵守本文件。

---

## 0. 代码质量守门 (Code Quality Gate)

When modifying Python code, diagnostic scripts, data update scripts, paper-mode,
backtest, broker, replay tools, or any code that affects experiment results,
use the project skill `quant-code-quality-gate`.

---

## 1. 项目性质

本项目是一个 Python A 股量化交易系统，涉及：

```text
A 股数据
股票选择
因子计算
策略生成
回测
绩效分析
风控
模拟盘
未来实盘交易接口
交易看板
```

由于项目未来可能接入真实交易接口，所有代码修改必须保持：

```text
谨慎
可验证
可回滚
可解释
不夸大收益
不绕过风控
```

---

## 2. 当前项目状态

当前项目已经进入：

```text
MVP 1：本地回测系统 → Paper Trading 过渡阶段
```

### 当前基线: Candidate B (new_candidate_baseline)

```
total_return ≈ 84.10%     max_drawdown ≈ -8.56%     GA fitness = 2.304
total_trades = 1137        exposure ≈ 18.7%          avg_position ≈ 3.92%
score_high = 0.80          atr_bear = 0.89           breakout_bear = 40
enable_pullback_entry = False  enable_rank_buffer = False  use_dow_filter = False
data hash: historical_constituents MD5 = c79f9f1649895c897af28961e5d3c1fb
```

### Historical A Baseline（参考）

```
total_return ≈ 83.07%     max_drawdown ≈ -8.06%     Calmar ≈ 0.97
total_trades = 1231        score_high = 0.72         atr_bear = 1.19
```

### 重要边界

- pullback_entry / rank_buffer 默认关闭（research-only）
- F/D1/D2/D3 实验均未进入主策略
- 不要重建 historical_constituents.json
- 不要改撮合、风控、手续费、滑点、T+1、涨跌停
- 不要正式大 GA
- 不要为了 2023 年单独修策略（已知 B 在 2023 年弱于 A，是 score_high=0.80 的自然代价）

当前已有基础能力包括：

```text
数据接入（AKShare）
Parquet 本地存储 + 交易日历
因子计算（动量、波动率、换手率、ATR）
两套完整策略：
  - 多因子轮动（动量+波动率+换手率）
  - 趋势突破 v2（五档止损 + 三档仓位 + 道氏理论过滤 + 策略熔断）
三种执行模式（尾盘买入 / 次日开盘 / 当日收盘）
A 股日频回测
模拟撮合（T+1/手数/佣金/印花税/涨跌停/停牌/ST/滑点）
绩效指标（10+ 项）
Streamlit 看板（5 Tab + 历史记录 + 参数存档 + 全中文解释）
基础测试（21 项）
未来函数系统检查脚本
历史成分股数据（2022-2026）
参数敏感度 + 网格搜索脚本
参数优化路线图（PSO/GA）
git 仓库 + .gitignore
```

已经完成的验证：

1. ✅ 未来函数检查（突破检测、执行时序、广度计算）—— 全部 PASS
2. ✅ 复权确认（qfq 模式）
3. ✅ 参数敏感度分析（13 参数，全部 LOW/MEDIUM，无过拟合）
4. ✅ 历史成分股（2022: 294只, 2023: 298只, 2024-2026: 299只）

后续任务重点不是重新设计整个系统，而是：

1. 参数优化（网格搜索 / PSO / GA）。
2. 样本外 Walk-forward 测试。
3. 修正成分股幸存者偏差（运行时按年份切换成分股）。
4. 加强假突破过滤和回踩确认。
5. 为模拟盘和未来实盘接口预留结构。

除非用户明确要求，不要推翻当前架构，不要从零重写回测系统。

---

## 3. 长会话使用规则

用户通常会长期停留在同一个 Claude Code 会话里，不一定频繁新开会话。

因此：

1. 不要默认自己永远记得最新项目状态。
2. 如果用户中途修改了 `CLAUDE.md` 或 `README.md`，必须重新读取。
3. 长会话中每完成一个阶段，应主动建议做一次状态刷新。
4. 不要依赖很早之前的聊天记忆来判断当前代码状态。
5. 以当前文件系统、`git status`、`git diff`、测试结果为准。

当用户说：

```text
刷新状态
恢复当前项目状态
先别改文件
看看现在做到哪了
```

等同于执行：

```text
读取 CLAUDE.md、README.md、git status、git diff 和当前项目结构。
不要改代码。
总结当前已完成、未完成、未提交修改和下一步计划。
```

---

## 4. 默认工作流：Plan-Execute

对于以下任务，不允许直接开始改代码：

```text
新增核心功能
修改项目架构
修改数据结构
修改回测逻辑
修改策略逻辑
修改股票选择逻辑
修改风控逻辑
接入交易接口
接入外部数据源
修改数据库表结构
修改自动下单相关代码
```

必须按 plan-execute 工作流：

1. 先读取项目结构和相关文件。
2. 先说明对需求的理解。
3. 先给设计方案。
4. 等用户确认后，再写执行计划。
5. 执行计划必须拆成小步骤。
6. 每一步必须说明：
   - 要修改哪些文件
   - 为什么修改
   - 如何验证
   - 预期结果是什么
7. 执行时每完成一步都要验证。
8. 不允许一次性大面积重构。
9. 不允许未经确认改动实盘交易、风控、密钥、账户配置。

---

## 5. 可以直接执行的小任务

以下任务可以直接执行，不需要完整 plan-execute：

```text
查看 git status
查看 git diff
解释代码
修复明确的小 bug
补充注释
修改 README 小段内容
运行已有测试
格式化代码
检查 import 是否正常
查看项目目录
```

但即使是小任务，也不能执行危险命令。

---

## 6. 命令执行规则

### 6.1 优先使用清晰命令

优先使用：

```bash
python -m pytest
python -m compileall qts
pytest tests/ -v
git status
git diff
dir
ls
type
cat
python scripts/check_future_leak.py
python scripts/param_robustness.py --mode sensitivity
python scripts/param_robustness.py --mode grid
python scripts/build_historical_universe.py
```

### 6.2 少用长 `python -c`

不要频繁使用长的：

```bash
python -c "..."
```

原因：

```text
python -c 可以执行任意 Python 代码。
它不透明，不利于审查，也容易触发 Claude Code 权限确认。
```

只有检查依赖版本时，才允许使用短的 `python -c`，例如：

```bash
python -c "import pandas; print(pandas.__version__)"
```

复杂验证应优先使用：

```text
pytest
scripts/*.py
临时测试文件
python -m compileall
```

### 6.3 Streamlit 启动规则

不要反复使用复杂复合命令重启 Streamlit，例如：

```bash
taskkill ... ; sleep ... ; cd ... && streamlit run ... 2>&1
```

优先使用更清晰的方式：

```bash
streamlit run qts/app/streamlit_app.py
```

如果需要重启服务，应先解释要关闭哪个进程，再执行。

### 6.4 禁止危险命令

未经用户明确确认，不允许执行：

```bash
rm -rf
del /s
rmdir /s
git reset --hard
git clean -fd
git checkout .
pip install --upgrade *
curl | bash
powershell -ExecutionPolicy Bypass
taskkill /F /IM *
```

### 6.5 不要隐藏错误

不要无理由使用：

```bash
2>/dev/null
2>&1
```

调试时应尽量保留错误输出。

### 6.6 实验输出与结果读取规范

长任务、回测、GA、实验、诊断必须把结果保存到项目目录下的结构化文件。

**结果必须保存为项目文件**：

优先保存为：
- `summary.csv` / `summary.json`
- `candidates.json`
- `report.md`
- `metrics.json`
- `config.json`
- `progress.json`

不允许只打印到终端，不允许只有临时文件。

**GA / 回测 / 大实验必须保存**：
- config、seed、data hash
- candidate genes、metrics、fitness decomposition
- report、timestamp、output path

**读取实验结果时，优先读取项目内正式输出文件**。

禁止反复解析类似以下路径的临时文件：
```
C:\Users\...\AppData\Local\Temp\claude\...\tasks\*.output
```

**查看长任务进度时，不要解析 Claude 临时 task output**。
长任务脚本应周期性写入：
- `progress.json`
- `latest_status.txt`
- `running_summary.md`

**尽量避免复杂 shell 组合命令**，尤其是：
- `$()`、复杂管道 `|`、多层引号嵌套
- `cygpath`
- 对 Claude 临时目录的动态路径解析

Windows 环境下优先使用 Python `pathlib` 处理路径，不依赖 `cygpath`。

**需要统计输出时，优先写成项目内 Python 脚本**：
- `scripts/report_ga_results.py`
- `scripts/summarize_experiment.py`
- `scripts/check_baseline.py`

**临时脚本必须及时清理**（`tmp_*.py`、`_sweep_*.txt`、`_raw_output.txt` 等）。

如确实必须运行复杂 shell 命令，先解释用途，并优先改为简单、可静态分析的命令或项目内脚本。

默认不要为了读取结果而触发用户权限确认。正确做法是让实验脚本直接把结果写入项目文件，再读取这些文件。

---

## 7. 项目分层原则

系统必须保持分层：

```text
数据层
因子层
股票选择层
策略层
组合层
回测层
风控层
执行层
看板层
```

必须遵守：

```text
策略不能直接调用实盘接口。
股票选择不能直接下单。
回测逻辑不能污染实盘逻辑。
实盘下单前必须经过风控模块。
配置和代码必须分离。
研究和实盘必须分离。
```

---

## 8. 数据规则

### 8.1 禁止未来函数

所有数据、因子和策略必须遵守：

```text
不能使用未来价格。
不能使用未来财务数据。
不能使用未来指数成分。
不能使用未来 ST 状态。
不能用未来最高点、最低点定义过去的支撑压力。
财务数据必须考虑公告日或可获得日。
指数成分必须使用当时实际成分，而不是当前成分倒推历史。
```

如有必要，数据表必须区分：

```text
trade_date        交易日期
ann_date          公告日期
available_date    数据可使用日期
created_at        数据入库时间
```

### 8.2 数据质量检查

涉及行情数据时必须检查：

```text
OHLC 关系是否正确
成交量 / 成交额是否缺失
复权因子是否正确
停牌数据是否正确
涨跌停价是否正确
交易日历是否正确
是否存在重复数据
是否存在缺失交易日
是否存在异常价格
```

---

## 9. 股票选择规则

股票选择必须分成三层：

```text
股票池 Universe
过滤条件 Filter
排序 / 打分 Ranking
```

不允许在策略代码中随意硬编码股票列表，除非用户明确指定研究样本。

### 9.1 股票池

支持方向：

```text
全 A 股
沪深 300
中证 500
中证 1000
创业板
科创板
自定义股票池
行业股票池
主题股票池
人工观察池
```

第一阶段优先支持：

```text
沪深 300
中证 500
中证 1000
自定义股票池
```

### 9.2 默认过滤规则

默认必须过滤：

```text
ST 股票
*ST 股票
退市整理股票
停牌股票
上市不足 120 个交易日的股票
过去 20 日平均成交额过低的股票
过去 20 日成交天数不足的股票
价格异常的股票
长期一字涨停或一字跌停股票
财务数据明显异常的股票
```

推荐配置：

```yaml
filters:
  exclude_st: true
  exclude_suspended: true
  exclude_delisting: true
  min_list_days: 120
  min_avg_amount_20d: 50000000
  min_trade_days_20d: 15
  min_price: 2.0
  max_price: 300.0
```

### 9.3 流动性过滤

实盘策略必须考虑流动性。

```yaml
liquidity:
  min_avg_amount_20d: 50000000
  min_avg_turnover_20d: 0.005
  max_order_amount_ratio: 0.02
```

含义：

```text
过去 20 日平均成交额不能太低。
单笔买入金额不能超过当日成交额的一定比例。
避免小票买不进、卖不出、滑点过大。
```

### 9.4 趋势过滤

如果策略偏趋势或突破，默认应加入趋势过滤。

可选条件：

```yaml
trend:
  close_above_ma20: true
  close_above_ma60: true
  ma20_above_ma60: true
  ma60_slope_positive: true
```

### 9.5 量能过滤

如果策略涉及突破、回踩、强势股，必须计算量能指标：

```text
volume_ratio_5d
volume_ratio_20d
amount_ratio_20d
turnover_ratio_20d
```

示例：

```yaml
volume:
  volume_ratio_20d_min: 1.5
  amount_ratio_20d_min: 1.3
```

### 9.6 支撑压力与突破

传统交易经验必须转化为可计算规则。

压力位可以定义为：

```text
过去 N 日最高价
前高
平台上沿
成交密集区上沿
```

支撑位可以定义为：

```text
过去 N 日最低价
前低
平台下沿
20 日均线
60 日均线
成交密集区下沿
```

突破规则示例：

```yaml
breakout:
  lookback_days: 60
  breakout_pct_min: 0.01
  volume_ratio_20d_min: 1.5
  require_close_breakout: true
```

### 9.7 回踩确认

突破后不一定马上买，可以等待回踩确认。

```yaml
pullback:
  enabled: true
  max_days_after_breakout: 5
  max_pullback_pct: 0.03
  volume_shrink_required: true
  close_back_above_support: true
```

### 9.8 假突破过滤

必须尽量避免追高假突破。

假突破特征包括：

```text
突破日长上影
突破日放巨量但收盘涨幅不强
突破后次日低开
突破后 3 日内跌回平台
突破时板块不配合
大盘环境弱
高位连续加速后再放量
```

---

## 10. 策略设计规则

每个策略必须明确：

```text
策略名称
适用市场
适用周期
股票池
过滤条件
入场条件
加仓条件
减仓条件
止损条件
止盈条件
退出条件
最大持仓数
单票最大仓位
最大总仓位
回测参数
实盘风险
最怕的市场环境
```

不允许只写：

```text
看到突破就买
趋势好就买
量能不错就买
```

必须变成可计算规则。

---

## 11. 推荐第一批策略方向

第一阶段优先实现：

### 11.1 平台放量突破策略

核心逻辑：

```text
长期横盘
波动收窄
压力位明确
放量突破
趋势确认
跌回平台止损
```

### 11.2 突破后缩量回踩策略

核心逻辑：

```text
不追突破当天
等待回踩
缩量不破
重新转强买入
```

### 11.3 均线趋势回踩策略

核心逻辑：

```text
中期趋势向上
回踩均线
缩量企稳
重新放量上攻
```

### 11.4 低波动趋势策略

核心逻辑：

```text
趋势向上
波动不大
慢慢上涨
减少妖股和剧烈波动票
```

### 11.5 假突破过滤器

不是独立策略，而是过滤模块，用于减少追高失败。

---

## 12. 因子设计规则

因子是交易经验的数字化表达。

每个因子必须包含：

```text
因子名称
计算公式
输入数据
输出字段
是否需要复权
是否存在未来函数风险
适用频率
缺失值处理
极值处理
标准化方法
排序方向
```

常用因子：

```text
momentum_20d
momentum_60d
volatility_20d
volume_ratio_20d
amount_ratio_20d
turnover_20d
breakout_60d
distance_to_ma20
distance_to_ma60
drawdown_60d
relative_strength_to_index
```

---

## 13. 回测规则

任何策略回测必须输出：

```text
累计收益
年化收益
最大回撤
夏普比率
卡玛比率
胜率
盈亏比
平均持仓天数
换手率
交易次数
手续费
滑点成本
月度收益
年度收益
最大连续亏损
最长回撤修复时间
持仓明细
交易明细
```

不允许只展示收益曲线。

---

## 14. 回测可信度和鲁棒性

至少包括：

```text
参数扰动
时间切片
样本外测试
滑点加倍
手续费加倍
成交延迟
容量限制
牛市 / 熊市 / 震荡市分段表现
收益来源拆解
单票贡献分析
年度稳定性分析
```

如果参数轻微变化后收益大幅崩溃，必须标记为：

```text
疑似过拟合，不建议实盘。
```

如果没有考虑 A 股关键交易规则，必须标记为：

```text
仅为粗略研究结果，不可用于实盘。
```

---

## 15. A 股交易规则

回测和模拟盘必须考虑：

```text
T+1 卖出限制
100 股整数手
停牌不可交易
涨停通常不可买入
跌停通常不可卖出
ST 股票风险
新股上市初期异常波动
退市风险
印花税
佣金
过户费
滑点
成交额容量限制
交易日历
复权因子
```

---

## 16. 风控规则

任何实盘或模拟盘策略必须经过风控。

默认风控方向：

```yaml
risk:
  max_position_per_stock: 0.08
  max_total_position: 0.8
  max_industry_position: 0.3
  max_daily_loss: 0.03
  max_strategy_drawdown: 0.12
  max_order_amount: 100000
  max_order_amount_ratio_to_volume: 0.02
  stop_trading_after_order_failures: 3
```

必须支持以下策略状态：

```text
正常运行
降权运行
暂停开新仓
只卖不买
完全停止
```

---

## 17. 实盘交易规则

实盘相关代码必须极其谨慎。

未经用户明确确认，不允许：

```text
自动提交实盘订单
自动撤单
自动全仓买入
自动清仓
修改券商账户配置
保存明文账户密码
保存明文 token
绕过风控下单
```

实盘下单前必须经过：

```text
策略信号
目标持仓
订单生成
下单前风控
用户确认或自动化权限检查
交易接口
订单状态回报
成交回报
账户同步
日志记录
```

---

## 18. 密钥和配置安全

不得把以下信息写入代码：

```text
Tushare token
券商账号
券商密码
数据库密码
API key
服务器密码
交易接口密钥
```

必须使用：

```text
.env
环境变量
本地配置文件
密钥管理工具
```

`.env`、本地账户配置、交易配置必须加入 `.gitignore`。

---

## 19. 日志规则

必须记录：

```text
数据更新时间
策略运行时间
生成信号
目标持仓
订单
成交
风控拒绝原因
异常错误
账户净值
持仓变化
```

日志必须能回答：

```text
这笔交易为什么买？
这笔交易为什么卖？
当时用了哪些数据？
当时风控是否通过？
实际成交价是多少？
和回测预期差多少？
```

---

## 20. 测试规则

核心逻辑必须有测试。

优先测试：

```text
A 股 T+1
100 股手数
手续费 / 印花税
涨跌停不可成交
停牌不可成交
未来函数防穿越
数据质量检查
策略信号是否只使用历史数据
风控是否能拒绝违规订单
回测是否可复现
```

不允许为了让测试通过而删除测试。

### 20.1 长时间运行任务必须先冒烟测试

任何预计运行超过 30 分钟的优化/训练/批量任务，必须遵循：

```text
1. 先编写一个小样本冒烟测试脚本
2. 最小参数运行（pop=6, gen=3, 短周期）
3. 串行执行，打印每步诊断信息
4. 验证完整 pipeline 无报错（无 KeyError、无 NaN、无 import 错误）
5. 冒烟测试通过后才允许启动正式任务
6. 正式任务启动后监控首批结果确认正常
```

原因：

```text
GA 优化曾因 bug 跑了 2 次都提前终止（11+5 小时白跑）。
冒烟测试 5 分钟就能暴露同样的问题。
禁止跳过冒烟测试直接跑正式任务。
```

实现参考：

```bash
python scripts/ga_smoke_test.py  # 小样本冒烟测试（~5 分钟）
```

冒烟测试必须覆盖的环节：

```text
配置生成 → 策略初始化 → 回测引擎 → 数据处理 → 
绩效计算 → fitness 评分 → 结果汇总
```

---

## 21. 不允许的行为

不允许：

```text
为了让测试通过而删除测试
为了让回测好看而降低手续费
为了提高收益而忽略涨跌停
为了提高收益而忽略停牌
为了提高收益而使用未来数据
为了提高收益而删除亏损样本
为了提高收益而只保留当前还活着的股票
把策略参数调到只适合历史某一段
只展示最优参数结果
隐藏失败回测
在没有风控的情况下接实盘
```

---

## 22. 和用户沟通规则

当需求不清楚时，先说明假设。

当发现风险时，必须直接指出。

当策略可能过拟合时，必须提醒。

当回测结果不可信时，必须说明原因。

当涉及实盘下单时，必须提醒用户确认。

不要把回测收益描述成确定收益。

不要承诺策略未来一定赚钱。

---

## 23. 默认口令

当用户说：

```text
按项目规则来
```

等同于：

```text
读取 CLAUDE.md，使用 plan-execute 工作流，先给方案，不要直接改代码。
```

当用户说：

```text
先别改文件
```

必须只读文件、分析、给方案，不允许写入。

当用户说：

```text
可以执行
```

才可以根据计划改代码。

当用户说：

```text
检查风险
```

必须重点检查：

```text
未来函数
回测假设
交易成本
涨跌停
停牌
T+1
滑点
实盘下单风险
密钥泄露
```

---

## 24. 阶段性收尾规则

每完成一批开发后，必须建议执行：

```text
git status
git diff
pytest tests/ -v
```

并总结：

```text
改了哪些文件
完成了什么
测试结果如何
还剩什么风险
下一步最小任务是什么
```

---

## 25. 最终目标

本项目目标是建立一套完整的 A 股量化生产系统：

```text
数据可信
逻辑可解释
回测可复现
风险可控制
实盘可暂停
代码可维护
```
