"""A-Share Quantitative Trading System - Streamlit Dashboard.

Run with:
    streamlit run qts/app/streamlit_app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from qts.backtest.engine import BacktestEngine
from qts.backtest.performance import compute_metrics
from qts.backtest.report import generate_report
from qts.strategies.signal_strategy import MomentumValueStrategy
from qts.utils.logger import logger
from qts.utils.config import load_yaml, get_project_root
from qts.data.calendar import load_or_fetch_calendar
from qts.data.storage import load_bars
from qts.data.quality import check_bar_quality

st.set_page_config(
    page_title="QTS - 量化交易系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 QTS - A股量化交易系统")
st.caption("Quantitative Trading System MVP")

# Force browser date picker to use Chinese locale
st.markdown(
    """
    <script>
    // Force the document language to zh-CN so native date pickers show Chinese
    document.documentElement.lang = 'zh-CN';
    </script>
    """,
    unsafe_allow_html=True,
)

# --- Sidebar ---
st.sidebar.header("⚙️ 参数设置")

root = get_project_root()
strategy_type = st.sidebar.selectbox(
    "策略类型",
    ["趋势突破（右侧交易）", "多因子轮动（动量+波动率）"],
    index=0,
)
universe = st.sidebar.selectbox(
    "股票池", ["HS300", "CSI500"], index=0
)

start_date = st.sidebar.date_input("回测开始", pd.Timestamp("2024-01-01"), format="YYYY-MM-DD")
end_date = st.sidebar.date_input("回测结束", pd.Timestamp("2026-05-08"), format="YYYY-MM-DD")
initial_cash = st.sidebar.number_input(
    "初始资金", min_value=100_000, value=1_000_000, step=100_000
)
rebalance = st.sidebar.selectbox("调仓频率", ["daily", "weekly", "monthly"], index=0)
min_turnover = st.sidebar.slider(
    "调仓阈值", 0.0, 0.50, 0.0 if "趋势" in strategy_type else 0.20, 0.01,
    help="仅在持仓变化超过此比例时才调仓。0=每次检查都调。趋势策略建议0（由信号自行控制）"
)

# Strategy params
if "趋势" in strategy_type:
    st.sidebar.subheader("📈 入场条件")
    breakout_days = st.sidebar.slider("突破周期（日）", 10, 60, 20, 5,
        help="收盘价必须突破过去N个交易日的最高价，才算有效突破信号。\n"
             "20日=约1个月，较短，信号多但假突破也多；\n"
             "60日=约3个月，信号少但确定性高")
    ma_days_trend = st.sidebar.slider("均线周期（日）", 20, 120, 20, 10,
        help="突破当天收盘价必须站上N日均线，确保中期趋势向上。\n"
             "20日=短线趋势，60日=中线趋势，120日=长线趋势")
    volume_ratio = st.sidebar.slider("放量倍数", 1.0, 3.0, 1.5, 0.1,
        help="突破当天成交量必须≥过去N日均量的倍数。\n"
             "1.0=不需要放量，1.5=需要比平时多50%的量，2.0=必须明显放量。\n"
             "放量确认突破有效，缩量突破往往是假突破")

    st.sidebar.subheader("🛑 止损（五档优先级，从高到低依次执行）")
    st.sidebar.caption("①→②→③→④→⑤，触发任意一档就卖出，不会等到更低")
    support_days = st.sidebar.slider("①支撑止损（日）", 5, 30, 10, 5,
        help="【第一优先级】跌破过去N个交易日的最低价就卖。\n"
             "这是最敏感的止损，破了近期支撑说明短期趋势走坏")
    st.sidebar.caption("②均线止损：跌破均线就卖（下面入场条件里的均线）")
    st.sidebar.caption("——以上两档都没触发，才检查下面三档——")
    atr_multiple = st.sidebar.slider("③ATR止损倍数", 1.0, 4.0, 2.0, 0.5,
        help="ATR=平均真实波幅，衡量一只股票每天平均波动多少。\n"
             "比如ATR=0.5元，2倍ATR=1元，就是说允许股价回撤1元。\n"
             "波动大的股票ATR自动变大，止损自动放宽，不会被震出去。\n"
             "1倍=紧止损，4倍=宽止损，一般用2倍")
    atr_period = st.sidebar.slider("③ATR计算周期（日）", 7, 21, 14, 1,
        help="用过去N天计算ATR。14天=约3周，是标准设置")
    profit_lock_pct = st.sidebar.slider("④利润保护(%)", 0.0, 0.30, 0.15, 0.01,
        help="【第四优先级】如果已经赚了这么多（比如15%），\n"
             "就把止损线上移到你的买入价，保证这笔交易不亏钱。\n"
             "0=不启用利润保护")
    max_loss_pct = st.sidebar.slider("⑤硬止损底线(%)", 0.05, 0.30, 0.08, 0.01,
        help="【最后兜底】前面四档都没触发，但股价已经从最高点跌了这么多，\n"
             "无条件卖出。这是最后的保险，防止极端行情亏损失控")

    st.sidebar.subheader("📊 仓位管理")
    breadth_ma_days = st.sidebar.slider("广度均线（日）", 10, 60, 30, 5,
        help="计算'有多少比例的股票站上N日均线'时用的N。\n"
             "10日=非常灵敏，30日=适中，60日=较滞后。\n"
             "这个比例叫'市场广度'，反映市场整体健康程度")
    min_breadth = st.sidebar.slider("满仓广度阈值", 0.35, 0.70, 0.50, 0.01,
        help="广度超过此值→满仓运行（比如50%=一半以上股票站上均线）。\n"
             "调高=更保守，只在强势市场满仓")
    breadth_half = st.sidebar.slider("半仓广度下限", 0.15, 0.40, 0.30, 0.01,
        help="广度在此值和满仓阈值之间→半仓运行。\n"
             "广度低于此值→空仓。调高=更多时间空仓")
    strategy_max_dd = st.sidebar.slider("策略熔断(%)", 5, 30, 15, 1,
        help="策略净值从近期最高点回撤超过此比例→强制清仓+冷却10天。\n"
             "这是策略层面的保护，防止连续亏损。15%=比较均衡的设置")
    use_dow = st.sidebar.checkbox("道氏理论牛市过滤", value=True,
        help="开启后，只在道氏理论认定的牛市中交易。\n"
             "判断标准：前50大成交额股票中，≥40%处于'更高高点+更高低点'的上升趋势。\n"
             "熊市自动空仓，等趋势转牛再入场")
    top_n = st.sidebar.slider("满仓持股数", 5, 30, 15,
        help="满仓时最多同时持有多少只股票。半仓时按比例减少")
    max_weight = st.sidebar.slider("单票最大权重", 0.05, 0.20, 0.15, 0.01,
        help="单只股票占总投资的比例上限。\n"
             "5%=极度分散(20只)，20%=极度集中(5只)，一般建议8-12%")
    mom_weight = vol_weight = turn_weight = 0  # unused
else:
    st.sidebar.subheader("📊 多因子参数")
    top_n = st.sidebar.slider("持仓数量", 5, 50, 20)
    max_weight = st.sidebar.slider("单票最大权重", 0.05, 0.20, 0.08, 0.01)
    mom_weight = st.sidebar.slider("动量因子权重", -1.0, 1.0, 0.4, 0.1)
    vol_weight = st.sidebar.slider("波动率因子权重", -1.0, 1.0, -0.3, 0.1)
    turn_weight = st.sidebar.slider("换手率因子权重", -1.0, 1.0, 0.3, 0.1)
    breakout_days = support_days = ma_days_trend = volume_ratio = max_loss_pct = min_breadth = 0
    atr_multiple = atr_period = profit_lock_pct = breadth_half = breadth_ma_days = strategy_max_dd = 0
    use_dow = True

# Execution settings
st.sidebar.subheader("⏱ 执行设置")
execution_price = st.sidebar.selectbox(
    "执行模式",
    ["尾盘买入（14:30判断→收盘价成交）", "次日开盘（收盘判断→明早开盘成交）", "当日收盘（回测乐观·仅供参考）"],
    index=0,
    help="尾盘: 模拟2:30看数据→尾盘下单（日线用收盘价近似，+尾盘点差）\n次日开盘: 保守模式，隔夜跳空风险\n当日收盘: 无延迟，仅对比用"
)
intraday_spread = 0.0
if "尾盘" in execution_price:
    intraday_spread = st.sidebar.slider("尾盘点差(bps)", 0, 50, 15, 5,
        help="2:30发出信号到收盘前成交，中间可能追高一点。\n"
             "15bps=买贵0.15%，模拟尾盘追价的额外成本。\n"
             "bps=基点，1bp=万分之一=0.01%")

# Commission params
st.sidebar.subheader("交易成本")
commission_rate = st.sidebar.number_input("佣金费率(万分之)", 1.0, 5.0, 2.5, 0.5,
    help="券商收取的交易佣金，买卖双向各收一次。\n"
         "万2.5=每成交1万元收2.5元佣金。最低5元") / 10000
stamp_tax = st.sidebar.number_input("印花税(万分之)", 1.0, 10.0, 5.0, 0.5,
    help="国家征收的印花税，只在卖出时收取。\n"
         "万5=每卖出1万元收5元。A股实际是万5（0.05%）") / 10000
slippage = st.sidebar.number_input("滑点(bps)", 0, 50, 10, 5,
    help="滑点=你想买的价格和实际成交价格之间的差距。\n"
         "比如你挂单10.00元买入，但市场上卖单不够，\n"
         "最后10.01元才买够，这0.01元(0.1%)就是滑点。\n"
         "10bps=0.1%的滑点，对流动性好的大盘股比较合理。\n"
         "bps=基点，1bp=万分之一=0.01%")

run_bt = st.sidebar.button("🚀 运行回测", type="primary", use_container_width=True)

# Show recent backtest history
index_file = root / "data/backtest/_backtest_index.json"
if index_file.exists():
    import json
    index = json.loads(index_file.read_text())
    if index:
        with st.sidebar.expander("📋 历史回测记录"):
            for entry in reversed(index[-5:]):  # last 5
                st.caption(
                    f"**{entry['timestamp']}** | {entry['strategy']}\n"
                    f"{entry['date_range']}\n"
                    f"收益: {entry['return_pct']:.1f}% | 回撤: {entry['max_dd_pct']:.1f}% | 夏普: {entry['sharpe']:.3f}"
                )
                st.divider()

# --- Main area ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 收益概览", "📋 交易记录", "📊 持仓分析", "🌡️ 月度收益", "📐 数据质量"
])

if run_bt:
    with st.spinner("正在运行回测..."):
        import time
        t0 = time.time()
        # Load data
        bar_path = root / f"data/raw/{universe}_daily.parquet"
        cal_path = root / "data/raw/calendar.parquet"

        if not bar_path.exists():
            st.error(f"数据文件不存在: {bar_path}")
            st.info("请先运行: python scripts/update_daily_data.py")
            st.stop()

        # Calendar
        cal = load_or_fetch_calendar(
            str(start_date), str(end_date), str(cal_path)
        )

        # Validate date range against actual data
        bars_check = load_bars(str(bar_path))
        if not bars_check.empty:
            data_min = bars_check["trade_date"].min()
            data_max = bars_check["trade_date"].max()
            sd = str(start_date)
            ed = str(end_date)
            if sd < data_min:
                st.warning(f"开始日期 {sd} 早于数据最早日期 {data_min}，已自动调整")
                start_date = pd.Timestamp(data_min).date()
            if ed > data_max:
                st.warning(f"结束日期 {ed} 晚于数据最晚日期 {data_max}，已自动调整")
                end_date = pd.Timestamp(data_max).date()

        # Strategy
        if "趋势" in strategy_type:
            from qts.strategies.trend_breakout import TrendBreakoutStrategy
            strategy = TrendBreakoutStrategy(
                breakout_days=breakout_days,
                support_days=support_days,
                ma_days=ma_days_trend,
                volume_ratio=volume_ratio,
                max_loss_pct=max_loss_pct,
                min_breadth=min_breadth,
                breadth_half=breadth_half,
                atr_multiple=atr_multiple,
                atr_period=atr_period,
                profit_lock_pct=profit_lock_pct,
                top_n=top_n,
                max_weight_per_stock=max_weight,
                cash_buffer=0.02,
            )
            strategy.breadth_ma_days = breadth_ma_days
            strategy.strategy_max_dd = strategy_max_dd / 100
            strategy.use_dow_filter = use_dow
        else:
            strategy = MomentumValueStrategy(
                factor_weights={
                    "momentum_20d": mom_weight,
                    "volatility_60d": vol_weight,
                    "turnover_ratio": turn_weight,
                },
                filters={
                    "exclude_st": True,
                    "exclude_suspended": True,
                    "min_list_days": 120,
                    "min_turnover_amount": 50_000_000,
                },
                portfolio_config={
                    "top_n": top_n,
                    "max_weight_per_stock": max_weight,
                    "cash_buffer": 0.02,
                    "weighting": "equal",
                },
            )

        # Engine
        if "次日" in execution_price:
            execution_mode = "next_open"
        elif "尾盘" in execution_price:
            execution_mode = "intraday_close"
        else:
            execution_mode = "close"

        engine = BacktestEngine(
            bar_path=str(bar_path),
            calendar_path=str(cal_path),
            start_date=str(start_date),
            end_date=str(end_date),
            initial_cash=initial_cash,
            commission_rate=commission_rate,
            stamp_tax_rate=stamp_tax,
            slippage_bps=slippage,
            execution_price=execution_mode,
            intraday_spread_bps=intraday_spread,
        )

        results = engine.run(strategy=strategy, rebalance_freq=rebalance, min_turnover=min_turnover)
        metrics, nav_df, monthly_df = compute_metrics(
            results["nav"], results["trades"], initial_cash
        )
        if "error" in metrics:
            st.error(metrics["error"])
            st.stop()

        # Auto-save results to disk with timestamp and all parameters
        import json
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = root / "data/backtest"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Build full metadata
        params = {
            "strategy": strategy_type,
            "universe": universe,
            "date_range": f"{start_date} ~ {end_date}",
            "initial_cash": initial_cash,
            "rebalance": rebalance,
            "min_turnover": min_turnover,
            "commission_rate": commission_rate,
            "stamp_tax": stamp_tax,
            "slippage_bps": slippage,
            "execution_price": execution_mode,
            "intraday_spread_bps": intraday_spread,
        }
        if "趋势" in strategy_type:
            params.update({
                "breakout_days": breakout_days,
                "support_days": support_days,
                "ma_days": ma_days_trend,
                "volume_ratio": volume_ratio,
                "max_loss_pct": max_loss_pct,
                "min_breadth": min_breadth,
                "breadth_half": breadth_half,
                "atr_multiple": atr_multiple,
                "atr_period": atr_period,
                "profit_lock_pct": profit_lock_pct,
                "breadth_ma_days": breadth_ma_days,
                "top_n": top_n,
                "max_weight": max_weight,
            })
        else:
            params.update({
                "top_n": top_n,
                "max_weight": max_weight,
                "momentum_weight": mom_weight,
                "volatility_weight": vol_weight,
                "turnover_weight": turn_weight,
            })

        # Save NAV and trades with timestamp prefix
        nav_file = out_dir / f"{ts}_nav.csv"
        trades_file = out_dir / f"{ts}_trades.csv"
        results["nav"].to_csv(nav_file, index=False, encoding="utf-8-sig")
        results["trades"].to_csv(trades_file, index=False, encoding="utf-8-sig")

        # Save complete result with params
        report = generate_report(metrics, nav_df, results["trades"])
        report["params"] = params
        report["timestamp"] = ts
        with open(out_dir / f"{ts}_result.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        # Update index file
        index_file = out_dir / "_backtest_index.json"
        index = []
        if index_file.exists():
            index = json.loads(index_file.read_text())
        index.append({
            "timestamp": ts,
            "strategy": params["strategy"],
            "date_range": params["date_range"],
            "return_pct": metrics.get("total_return_pct", 0),
            "max_dd_pct": metrics.get("max_drawdown_pct", 0),
            "sharpe": metrics.get("sharpe_ratio", 0),
            "params": params,
        })
        index_file.write_text(json.dumps(index, indent=2, ensure_ascii=False, default=str))

        logger.info(f"[{ts}] {params['strategy']} | Return={metrics.get('total_return_pct', 0):.2f}% DD={metrics.get('max_drawdown_pct', 0):.2f}% Sharpe={metrics.get('sharpe_ratio', 0):.3f}")

    # Store in session state
    st.session_state["results"] = results
    st.session_state["metrics"] = metrics
    st.session_state["nav_df"] = nav_df
    st.session_state["monthly_df"] = monthly_df
    elapsed = time.time() - t0
    st.success(f"回测完成！耗时 {elapsed:.1f} 秒")

# Display results if available
if "results" in st.session_state:
    results = st.session_state["results"]
    metrics = st.session_state["metrics"]
    nav_df = st.session_state["nav_df"]
    monthly_df = st.session_state.get("monthly_df")

    # --- Tab 1: Performance Overview ---
    with tab1:
        def metric_with_help(label, value, help_text, delta=None, delta_color="normal"):
            """Display a metric with help text popup."""
            st.metric(label, value, delta=delta, delta_color=delta_color, help=help_text)

        col1, col2, col3, col4, col5 = st.columns(5)
        total_ret = metrics.get("total_return_pct", 0)
        with col1:
            col1.metric("累计收益", f"{total_ret:.2f}%",
                         delta=f"{total_ret:.1f}%",
                         help="整个回测期间的总收益率。\n比如100万变150万=累计收益50%")
        with col2:
            col2.metric("年化收益", f"{metrics.get('annual_return_pct', 0):.2f}%",
                         help="换算成每年的平均收益率。\n2年赚20%≈年化9.5%（复利）。\nA股量化策略年化15-30%算优秀")
        with col3:
            col3.metric("最大回撤", f"{metrics.get('max_drawdown_pct', 0):.2f}%",
                         delta=f"{metrics.get('max_drawdown_pct', 0):.2f}%",
                         delta_color="inverse",
                         help="从最高点到最低点的最大跌幅。\n比如净值从150万跌到100万=回撤33%。\n是衡量风险最重要的指标，一般控制在20-30%以内")
        with col4:
            col4.metric("夏普比率", f"{metrics.get('sharpe_ratio', 0):.3f}",
                         help="Sharpe Ratio=风险调整后收益。\n= (收益率-无风险利率) / 波动率。\n>1.0算不错，>1.5算优秀，>2.0很难得。\n衡量的是'每承担1%波动，赚了多少超额收益'")
        with col5:
            col5.metric("胜率", f"{metrics.get('win_rate_pct', 0):.2f}%",
                         help="交易盈利的比例。\n比如100笔交易中55笔盈利=胜率55%。\n趋势策略胜率通常40-50%，\n但盈亏比高（赚一次抵亏好几次）")

        col6, col7, col8, col9, col10 = st.columns(5)
        with col6:
            col6.metric("卡玛比率", f"{metrics.get('calmar_ratio', 0):.3f}",
                         help="Calmar Ratio=年化收益÷最大回撤。\n比如年化30%÷回撤20%=1.5。\n>1.0算不错，>2.0算优秀。\n衡量的是'每承受1%回撤赚了多少年化收益'")
        with col7:
            col7.metric("总交易次数", metrics.get("total_trades", 0),
                         help="整个回测期间买卖的总笔数。\n太多=过度交易、手续费高；\n太少=可能错过了机会")
        with col8:
            col8.metric("换手率", f"{metrics.get('turnover_ratio', 0):.4f}",
                         help="买卖总金额÷初始资金。\n比如换手率50x=买卖了50倍本金的量。\n换手率太高说明交易过于频繁，手续费吃利润")
        with col9:
            col9.metric("盈亏比", f"{metrics.get('profit_loss_ratio', 0):.2f}",
                         help="平均盈利 ÷ 平均亏损。\n比如1.5=每次盈利是每次亏损的1.5倍。\n>1.5算不错，>2.0优秀。\n趋势策略胜率低但盈亏比高")
        with col10:
            col10.metric("平均持仓(天)", metrics.get("avg_holding_days", 0),
                         help="买入到卖出的平均天数。\n太短=频繁交易，太长=资金效率低。\n趋势策略一般5-20天")

        col11, col12, col13, col14, col15 = st.columns(5)
        with col11:
            col11.metric("最终净值", f"{metrics.get('final_value', 0):,.0f}",
                         help=f"初始资金{metrics.get('initial_cash', 0):,.0f}最终变成多少")
        with col12:
            col12.metric("连续亏损天数", metrics.get("max_consecutive_losses", 0),
                         help="最长的连续亏损天数")
        with col13:
            col13.metric("最佳月份(%)", f"{metrics.get('best_month_pct', 0):.1f}",
                         help="收益最高的单月")
        with col14:
            col14.metric("最差月份(%)", f"{metrics.get('worst_month_pct', 0):.1f}",
                         help="亏损最多的单月")
        with col15:
            col15.metric("正收益月份", f"{metrics.get('positive_months_pct', 0):.1f}%",
                         help="盈利月份占比")

        # Yearly returns table
        yearly = metrics.get("yearly_returns")
        if yearly is not None and not yearly.empty:
            st.subheader("年度收益")
            yr = yearly.copy()
            yr["yearly_return_pct"] = yr["yearly_return_pct"].round(2)
            yr = yr.reset_index()
            yr.columns = ["年份", "年初净值", "年末净值", "年度收益(%)"]
            st.dataframe(yr, use_container_width=True, hide_index=True)

        # Equity curve
        st.subheader("净值曲线与回撤")
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
        )

        fig.add_trace(
            go.Scatter(
                x=nav_df["date"], y=nav_df["cum_return_pct"],
                mode="lines", name="累计收益(%)",
                line=dict(color="#1f77b4", width=2),
            ),
            row=1, col=1,
        )

        # Drawdown
        peak = nav_df["total_value"].cummax()
        dd = (nav_df["total_value"] - peak) / peak * 100
        fig.add_trace(
            go.Scatter(
                x=nav_df["date"], y=dd,
                mode="lines", name="回撤(%)",
                fill="tozeroy",
                line=dict(color="#d62728", width=1),
            ),
            row=2, col=1,
        )

        fig.update_layout(
            height=500,
            showlegend=True,
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="累计收益 (%)", row=1, col=1)
        fig.update_yaxes(title_text="回撤 (%)", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)

    # --- Tab 2: Trade Records ---
    with tab2:
        trades_df = results["trades"]
        if not trades_df.empty:
            st.subheader(f"交易明细 ({len(trades_df)} 笔)")

            buys = trades_df[trades_df["side"] == "BUY"]
            sells = trades_df[trades_df["side"] == "SELL"]
            st.write(f"买入: {len(buys)} 笔 | 卖出: {len(sells)} 笔")

            st.dataframe(
                trades_df.sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("无交易记录")

    # --- Tab 3: Position Analysis ---
    with tab3:
        pos_df = results["positions"]
        if not pos_df.empty:
            st.subheader("持仓变化")
            # Position count over time
            pos_count = pos_df.groupby("date")["symbol"].nunique().reset_index()
            pos_count.columns = ["date", "n_positions"]

            fig = px.line(pos_count, x="date", y="n_positions",
                          title="持仓数量变化")
            st.plotly_chart(fig, use_container_width=True)

            # Latest positions
            latest_date = pos_df["date"].max()
            latest_pos = pos_df[pos_df["date"] == latest_date].sort_values(
                "weight", ascending=False
            )
            st.subheader(f"最新持仓 ({latest_date})")

            fig2 = px.bar(
                latest_pos, x="symbol", y="weight",
                title="持仓权重分布",
                labels={"weight": "权重", "symbol": "股票"},
            )
            st.plotly_chart(fig2, use_container_width=True)

            st.dataframe(latest_pos, use_container_width=True, hide_index=True)
        else:
            st.info("无持仓数据")

    # --- Tab 4: Monthly Returns ---
    with tab4:
        if monthly_df is not None and not monthly_df.empty:
            st.subheader("月度收益热力图")

            mdf = monthly_df.copy()
            mdf["month_str"] = mdf.index.astype(str)
            mdf["year"] = mdf["month_str"].str[:4]
            mdf["month"] = mdf["month_str"].str[5:7]

            heatmap_data = mdf.pivot(
                index="year", columns="month", values="monthly_return_pct"
            )

            fig = px.imshow(
                heatmap_data,
                labels=dict(x="月份", y="年份", color="收益(%)"),
                x=[f"{i}月" for i in range(1, 13)],
                aspect="auto",
                color_continuous_scale="RdYlGn",
                text_auto=".1f",
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            # Monthly stats
            st.write(f"正收益月份比例: {metrics.get('positive_months_pct', 0):.1f}%")
            st.write(f"最佳月份: {metrics.get('best_month_pct', 0):.2f}%")
            st.write(f"最差月份: {metrics.get('worst_month_pct', 0):.2f}%")
        else:
            st.info("无月度收益数据")

    # --- Tab 5: Data Quality ---
    with tab5:
        st.subheader("数据质量检查")
        bar_path = root / f"data/raw/{universe}_daily.parquet"
        if bar_path.exists():
            bars = load_bars(str(bar_path), str(start_date), str(end_date))
            quality = check_bar_quality(bars)

            # Chinese labels with explanations
            labels = {
                "symbol_count": ("股票数量", "数据中的股票总数"),
                "date_range": ("日期范围", "数据覆盖的交易日区间"),
                "missing_dates_ratio": ("缺失日期比例", "每只股票缺失交易日的平均比例，越低越好"),
                "ohlc_valid": ("OHLC有效性", "开盘/最高/最低/收盘价是否满足 high≥max(open,close) 且 low≤min(open,close)"),
                "suspended_pct": ("停牌比例", "停牌日的占比"),
                "negative_prices": ("负价格检查", "是否存在<=0的价格，正常应为PASS"),
                "zero_volume_active": ("零成交量检查", "非停牌日是否出现成交量为0，正常应为PASS"),
            }

            cols = st.columns(2)
            for i, (k, v) in enumerate(quality.items()):
                if k in labels:
                    label, help_text = labels[k]
                else:
                    label, help_text = k, ""
                with cols[i % 2]:
                    st.metric(label, v, help=help_text)
        else:
            st.warning("数据文件不存在，请先更新数据")

else:
    st.info("👈 请在左侧设置参数后点击「运行回测」")
    st.markdown("""
    ### 快速开始
    1. 确保已运行 `python scripts/update_daily_data.py` 下载数据
    2. 在左侧选择股票池、回测区间和策略参数
    3. 点击「运行回测」查看结果
    """)
