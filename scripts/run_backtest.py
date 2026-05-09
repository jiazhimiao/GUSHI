"""Run a backtest from the command line.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --config configs/strategies/hs300_momentum.yaml
    python scripts/run_backtest.py --strategy hs300_momentum --start 2022-01-01 --end 2024-12-31
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qts.utils.logger import logger, setup_file_log
from qts.utils.config import load_yaml, get_project_root
from qts.data.calendar import load_or_fetch_calendar
from qts.backtest.engine import BacktestEngine
from qts.backtest.performance import compute_metrics
from qts.backtest.report import generate_report
from qts.strategies.signal_strategy import MomentumValueStrategy


def main():
    parser = argparse.ArgumentParser(description="Run A-share strategy backtest")
    parser.add_argument(
        "--config",
        default="configs/strategies/hs300_momentum.yaml",
        help="Strategy config YAML path",
    )
    parser.add_argument("--start", default="2022-01-01", help="Backtest start date")
    parser.add_argument("--end", default="2024-12-31", help="Backtest end date")
    parser.add_argument("--universe", default="HS300", help="Stock universe")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    parser.add_argument("--output", default="data/backtest/result.json")
    args = parser.parse_args()

    setup_file_log()
    root = get_project_root()

    # Load strategy config
    config_path = root / args.config
    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        sys.exit(1)

    config = load_yaml(config_path)
    logger.info(f"Loaded strategy: {config['strategy_name']}")

    # Load calendar
    cal = load_or_fetch_calendar(
        args.start, args.end, str(root / "data/raw/calendar.parquet")
    )

    # Build strategy from config
    strategy = MomentumValueStrategy(
        factor_weights={
            name: f["weight"]
            for name, f in config.get("factors", {}).items()
        },
        filters=config.get("filters", {}),
        portfolio_config=config.get("portfolio", {}),
    )

    # Data path
    bar_path = str(root / f"data/raw/{args.universe}_daily.parquet")
    cal_path = str(root / "data/raw/calendar.parquet")

    if not Path(bar_path).exists():
        logger.error(f"Bar data not found: {bar_path}")
        logger.error("Run 'python scripts/update_daily_data.py' first!")
        sys.exit(1)

    # Build broker config from broker.yaml
    broker_cfg = load_yaml(root / "configs/broker.yaml")

    # Run backtest
    engine = BacktestEngine(
        bar_path=bar_path,
        calendar_path=cal_path,
        start_date=args.start,
        end_date=args.end,
        initial_cash=args.initial_cash,
        commission_rate=broker_cfg.get("commission_rate", 0.00025),
        stamp_tax_rate=broker_cfg.get("stamp_tax_rate", 0.0005),
        min_commission=broker_cfg.get("min_commission", 5.0),
        slippage_bps=broker_cfg.get("slippage_bps", 10.0),
        lot_size=broker_cfg.get("lot_size", 100),
    )

    results = engine.run(
        strategy=strategy,
        rebalance_freq=config.get("rebalance", "daily"),
        min_turnover=config.get("min_turnover", 0.20),
    )

    # Compute metrics
    metrics, nav_df, monthly_df = compute_metrics(
        results["nav"], results["trades"], args.initial_cash
    )

    # Print summary
    print("\n" + "=" * 50)
    print("Backtest Results")
    print("=" * 50)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    # Generate report
    output_path = root / args.output
    report = generate_report(metrics, nav_df, results["trades"], str(output_path))

    # Save detailed results
    nav_csv = output_path.parent / "nav.csv"
    trades_csv = output_path.parent / "trades.csv"
    results["nav"].to_csv(nav_csv, index=False, encoding="utf-8-sig")
    results["trades"].to_csv(trades_csv, index=False, encoding="utf-8-sig")

    logger.info(f"NAV saved to {nav_csv}")
    logger.info(f"Trades saved to {trades_csv}")
    logger.info(f"Report saved to {output_path}")


if __name__ == "__main__":
    main()
