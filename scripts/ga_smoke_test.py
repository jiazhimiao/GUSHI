"""Small-sample smoke test for GA optimization pipeline.

Runs a tiny GA (pop=6, gen=3, short period) serially to verify
the complete pipeline works before launching a full multi-hour run.

Rule: any optimization task expected to run >30 minutes MUST
pass this smoke test first.

Usage:
    python scripts/ga_smoke_test.py
"""

import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log


# ── Mini smoke test config ──
POP_SIZE = 6
N_GENERATIONS = 3
SMOKE_TRAIN = ("2024-01-01", "2024-03-31")
SMOKE_VAL = ("2024-04-01", "2024-06-30")

# Same param bounds as full GA
PARAM_BOUNDS = {
    "w_breadth": (0.20, 0.60, 0.05, False),
    "w_trend": (0.10, 0.40, 0.05, False),
    "w_stability": (0.05, 0.25, 0.05, False),
    "w_volume": (0.05, 0.25, 0.05, False),
    "score_low": (0.10, 0.30, 0.01, False),
    "score_high": (0.50, 0.80, 0.01, False),
    "breakout_bull": (10, 20, 5, True),
    "breakout_bear": (30, 60, 5, True),
    "atr_bull": (2.0, 4.0, 0.5, False),
    "atr_bear": (1.0, 2.0, 0.5, False),
    "vol_ratio_bull": (0.4, 1.2, 0.2, False),
    "vol_ratio_bear": (0.6, 2.0, 0.2, False),
    "top_n_bull": (5, 8, 1, True),
    "top_n_bear": (0, 3, 1, True),
    "support_bull": (3, 10, 1, True),
    "support_bear": (10, 20, 1, True),
    "ma_bull": (15, 30, 5, True),
    "ma_bear": (30, 90, 5, True),
    "max_loss_pct": (0.05, 0.15, 0.01, False),
    "profit_lock_pct": (0.05, 0.25, 0.01, False),
    "atr_period": (10, 21, 1, True),
    "breadth_ma_days": (10, 60, 5, True),
    "strategy_max_dd": (0.10, 0.30, 0.01, False),
    "max_weight_per_stock": (0.08, 0.20, 0.01, False),
}


def random_genes():
    genes = {}
    for name, (lo, hi, step, is_int) in PARAM_BOUNDS.items():
        if is_int:
            vals = list(range(int(lo), int(hi) + 1, int(step)))
            genes[name] = float(random.choice(vals))
        else:
            genes[name] = round(random.uniform(lo, hi), 2)
    return genes


def genes_to_regime_kwargs(genes: dict) -> dict:
    return {
        "w_breadth": genes["w_breadth"],
        "w_trend": genes["w_trend"],
        "w_stability": genes["w_stability"],
        "w_volume": genes["w_volume"],
        "score_low": genes["score_low"],
        "score_high": genes["score_high"],
        "breakout_bull": int(genes["breakout_bull"]),
        "breakout_bear": int(genes["breakout_bear"]),
        "atr_bull": genes["atr_bull"],
        "atr_bear": genes["atr_bear"],
        "vol_ratio_bull": genes["vol_ratio_bull"],
        "vol_ratio_bear": genes["vol_ratio_bear"],
        "top_n_bull": int(genes["top_n_bull"]),
        "top_n_bear": int(genes["top_n_bear"]),
        "support_bull": int(genes["support_bull"]),
        "support_bear": int(genes["support_bear"]),
        "ma_days_bull": int(genes["ma_bull"]),
        "ma_days_bear": int(genes["ma_bear"]),
    }


def run_single_backtest(genes: dict, start: str, end: str, label: str):
    """Run a single backtest, print detailed diagnostics."""
    root = get_project_root()
    t0 = time.time()

    # Build regime engine
    regime_kwargs = genes_to_regime_kwargs(genes)
    regime = RegimeEngine(**regime_kwargs)

    # Build strategy
    s = TrendBreakoutStrategy(
        breakout_days=20,
        support_days=10,
        ma_days=30,
        volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"],
        min_breadth=0.50,
        breadth_half=0.30,
        atr_multiple=2.0,
        atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"],
        top_n=10,
        max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime
    s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}

    engine = BacktestEngine(
        bar_path=str(root / "data/raw/HS300_daily.parquet"),
        calendar_path=str(root / "data/raw/calendar.parquet"),
        start_date=start, end_date=end,
        initial_cash=1_000_000,
        execution_price="intraday_close",
        intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    metrics, _, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)

    elapsed = time.time() - t0
    ret = metrics.get("total_return_pct", 0)
    ann_ret = metrics.get("annual_return_pct", 0)
    dd = metrics.get("max_drawdown_pct", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    n_trades = len(results["trades"])

    logger.info(
        f"  [{label}] {elapsed:.0f}s | ann_ret={ann_ret:.1f}% ret={ret:.1f}% DD=-{dd:.1f}% "
        f"Sharpe={sharpe:.3f} trades={n_trades}"
    )
    metrics["annual_return_pct"] = ann_ret  # ensure available
    return metrics


def evaluate_individual(i: int, genes: dict):
    """Evaluate one individual (train + val), serial with full diagnostics."""
    logger.info(f"[{i+1}/{POP_SIZE}] genes: top_n={int(genes['top_n_bull'])}/{int(genes['top_n_bear'])} "
                f"ma={int(genes['ma_bull'])}/{int(genes['ma_bear'])} "
                f"brk={int(genes['breakout_bull'])}/{int(genes['breakout_bear'])} "
                f"w=({genes['w_breadth']:.2f},{genes['w_trend']:.2f},"
                f"{genes['w_stability']:.2f},{genes['w_volume']:.2f})")

    train_m = run_single_backtest(genes, *SMOKE_TRAIN, "TRAIN")
    val_m = run_single_backtest(genes, *SMOKE_VAL, "VAL  ")

    train_ar = train_m.get("annual_return_pct", 0)
    train_dd = train_m.get("max_drawdown_pct", 0)
    val_ar = val_m.get("annual_return_pct", 0)
    val_dd = val_m.get("max_drawdown_pct", 0)
    train_pr = train_m.get("total_return_pct", 0)
    val_pr = val_m.get("total_return_pct", 0)

    # Calmar fitness
    t_fit = train_ar / abs(train_dd) if abs(train_dd) > 0.5 else train_ar
    v_fit = val_ar / abs(val_dd) if abs(val_dd) > 0.5 else val_ar
    fit = t_fit * 0.5 + v_fit * 0.5

    logger.info(f"  -> fitness={fit:.2f} (train_ann={train_ar:.1f}%/-{train_dd:.1f}%, "
                f"val_ann={val_ar:.1f}%/-{val_dd:.1f}%)")
    return {
        "genes": genes,
        "fitness": fit,
        "train_annual_ret": train_ar,
        "train_dd": train_dd,
        "val_annual_ret": val_ar,
        "val_dd": val_dd,
        "train_return": train_pr,
        "val_return": val_pr,
    }


def main():
    setup_file_log()
    logger.info("=" * 60)
    logger.info("GA Smoke Test: verifying complete pipeline end-to-end")
    logger.info(f"  pop={POP_SIZE}, gen={N_GENERATIONS} (serial execution)")
    logger.info(f"  train={SMOKE_TRAIN}, val={SMOKE_VAL}")
    logger.info(f"  {len(PARAM_BOUNDS)} genes per individual")
    logger.info("=" * 60)

    t0 = time.time()

    # ── Step 1: Generate initial population ──
    logger.info("\n[Step 1] Generating initial population...")
    pop = [random_genes() for _ in range(POP_SIZE)]

    # ── Step 2: Evaluate initial population (serial) ──
    logger.info(f"\n[Step 2] Evaluating {POP_SIZE} individuals (serial, full diagnostics)...")
    evaluated = []
    for i, genes in enumerate(pop):
        result = evaluate_individual(i, genes)
        evaluated.append(result)

    pop = evaluated
    pop.sort(key=lambda x: x["fitness"], reverse=True)
    best = pop[0]
    logger.info(f"\nInitial best: fitness={best['fitness']:.2f} "
                f"train_ann={best['train_annual_ret']:.1f}%/-{best['train_dd']:.1f}% "
                f"val_ann={best['val_annual_ret']:.1f}%/-{best['val_dd']:.1f}%")

    # ── Step 3: Run mini GA ──
    for gen in range(1, N_GENERATIONS + 1):
        logger.info(f"\n[Step 3.{gen}] Generation {gen}/{N_GENERATIONS}...")

        # Keep best individual
        new_pop = [pop[0]]

        # Generate rest via simple mutation
        for j in range(1, POP_SIZE):
            parent = random.choice(pop[:3])  # tournament from top 3
            child_genes = parent["genes"].copy()
            # Mutate ~20% of genes
            for name, (lo, hi, step, is_int) in PARAM_BOUNDS.items():
                if random.random() < 0.20:
                    if is_int:
                        vals = list(range(int(lo), int(hi) + 1, int(step)))
                        child_genes[name] = float(random.choice(vals))
                    else:
                        child_genes[name] = round(random.uniform(lo, hi), 2)
            result = evaluate_individual(
                (gen - 1) * (POP_SIZE - 1) + j + POP_SIZE, child_genes
            )
            new_pop.append(result)

        pop = new_pop
        pop.sort(key=lambda x: x["fitness"], reverse=True)
        best = pop[0]
        logger.info(f"Gen {gen} best: fitness={best['fitness']:.2f} "
                    f"train_ann={best['train_annual_ret']:.1f}%/-{best['train_dd']:.1f}% "
                    f"val_ann={best['val_annual_ret']:.1f}%/-{best['val_dd']:.1f}%")

    # ── Step 4: Verify results ──
    elapsed = time.time() - t0
    logger.info("\n" + "=" * 60)
    logger.info(f"SMOKE TEST COMPLETE in {elapsed:.0f}s ({elapsed/60:.1f}m)")

    best = pop[0]
    logger.info(f"Best fitness: {best['fitness']:.1f}")
    logger.info(f"Best genes: {genes_to_regime_kwargs(best['genes'])}")

    # Assertions
    errors = []
    if best["fitness"] == -999.0:
        errors.append("Fitness is -999 (eval failed)")
    if len(pop) != POP_SIZE:
        errors.append(f"Population size mismatch: {len(pop)} != {POP_SIZE}")
    for i, ind in enumerate(pop):
        if ind["train_annual_ret"] == 0 and ind["train_dd"] == 0:
            errors.append(f"Individual {i}: zero return and zero DD (likely error)")

    if errors:
        logger.error("SMOKE TEST FAILED:")
        for e in errors:
            logger.error(f"  - {e}")
        sys.exit(1)
    else:
        logger.info("ALL CHECKS PASSED - pipeline is healthy, ready for full GA")
        sys.exit(0)


if __name__ == "__main__":
    main()
