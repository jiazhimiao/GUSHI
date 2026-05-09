"""Genetic Algorithm parameter optimizer with cycle-based train/val/test split.

Usage:
    python scripts/ga_optimizer.py                 # Quick run (small pop)
    python scripts/ga_optimizer.py --full          # Full run (slow, ~2-4 hours)

Algorithm:
    - Encoding: each param is a gene, individual = list of genes
    - Fitness: return% * 0.6 - |drawdown%| * 0.4 (risk-adjusted)
    - Selection: tournament (size=3)
    - Crossover: uniform crossover
    - Mutation: random reset within bounds (20% chance per gene)
    - Elite: top 20% preserved each generation
    - Early stop: no improvement for 5 generations

Cycle-based split:
    Train:   2022-01-01 to 2023-12-31  (bear + recovery)
    Validate: 2024-01-01 to 2025-06-30  (bull + consolidation)
    Test:    2025-07-01 to 2026-05-08  (out-of-sample, saved as final report)
"""
import sys
import json
import time
import random
from pathlib import Path
from dataclasses import dataclass, field
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.backtest.performance import compute_metrics
from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log


# Parameter bounds: {name: (min, max, step, is_int)}
PARAM_BOUNDS = {
    "breakout_days": (10, 40, 5, True),
    "support_days": (5, 25, 5, True),
    "ma_days": (15, 45, 5, True),
    "volume_ratio": (1.0, 2.5, 0.1, False),
    "max_loss_pct": (0.05, 0.20, 0.01, False),
    "min_breadth": (0.35, 0.65, 0.01, False),
    "breadth_half": (0.15, 0.40, 0.01, False),
    "atr_multiple": (1.0, 3.5, 0.5, False),
    "atr_period": (7, 21, 1, True),
    "profit_lock_pct": (0.0, 0.30, 0.01, False),
    "breadth_ma_days": (10, 60, 5, True),
    "strategy_max_dd": (0.10, 0.99, 0.01, False),
    "top_n": (3, 15, 1, True),
    "max_weight_per_stock": (0.05, 0.20, 0.01, False),
}

# Cycle-based periods
TRAIN_PERIOD = ("2022-01-01", "2023-12-31")
VAL_PERIOD = ("2024-01-01", "2025-06-30")
TEST_PERIOD = ("2025-07-01", "2026-05-08")


@dataclass
class Individual:
    genes: dict[str, float]
    fitness: float = 0.0
    train_return: float = 0.0
    train_dd: float = 0.0
    val_return: float = 0.0
    val_dd: float = 0.0

    def __hash__(self):
        return hash(tuple(sorted(self.genes.items())))


def random_individual() -> Individual:
    genes = {}
    for name, (lo, hi, step, is_int) in PARAM_BOUNDS.items():
        if is_int:
            vals = list(range(int(lo), int(hi) + 1, int(step)))
            genes[name] = float(random.choice(vals))
        else:
            genes[name] = round(random.uniform(lo, hi), 2)
    return Individual(genes=genes)


def mutate(genes: dict[str, float], rate: float = 0.20) -> dict[str, float]:
    new = genes.copy()
    for name, (lo, hi, step, is_int) in PARAM_BOUNDS.items():
        if random.random() < rate:
            if is_int:
                vals = list(range(int(lo), int(hi) + 1, int(step)))
                new[name] = float(random.choice(vals))
            else:
                new[name] = round(random.uniform(lo, hi), 2)
    return new


def crossover(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    child = {}
    for name in PARAM_BOUNDS:
        child[name] = a[name] if random.random() < 0.5 else b[name]
    return child


def genes_to_params(genes: dict[str, float]) -> dict:
    return {
        "breakout_days": int(genes["breakout_days"]),
        "support_days": int(genes["support_days"]),
        "ma_days": int(genes["ma_days"]),
        "volume_ratio": genes["volume_ratio"],
        "max_loss_pct": genes["max_loss_pct"],
        "min_breadth": genes["min_breadth"],
        "breadth_half": genes["breadth_half"],
        "atr_multiple": genes["atr_multiple"],
        "atr_period": int(genes["atr_period"]),
        "profit_lock_pct": genes["profit_lock_pct"],
        "breadth_ma_days": int(genes["breadth_ma_days"]),
        "strategy_max_dd": genes["strategy_max_dd"],
        "top_n": int(genes["top_n"]),
        "max_weight_per_stock": genes["max_weight_per_stock"],
    }


def _run_backtest(params: dict, start: str, end: str):
    """Run a single backtest and return metrics."""
    root = get_project_root()
    s = TrendBreakoutStrategy(**params)
    s.use_dow_filter = False
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
    return metrics


def _eval_one(params: dict) -> tuple:
    """Evaluate one individual (train + val). Standalone for ProcessPoolExecutor."""
    train_m = _run_backtest(params, *TRAIN_PERIOD)
    val_m = _run_backtest(params, *VAL_PERIOD)
    return (
        train_m.get("total_return_pct", 0),
        train_m.get("max_drawdown_pct", 0),
        val_m.get("total_return_pct", 0),
        val_m.get("max_drawdown_pct", 0),
    )


def fitness(return_pct: float, dd_pct: float) -> float:
    """Balanced score: reward return, penalize drawdown."""
    return return_pct * 0.6 - abs(dd_pct) * 0.4


class GAOptimizer:
    def __init__(
        self,
        pop_size: int = 40,
        n_generations: int = 25,
        mutation_rate: float = 0.20,
        elite_ratio: float = 0.20,
        early_stop_gens: int = 5,
    ):
        self.pop_size = pop_size
        self.n_generations = n_generations
        self.mutation_rate = mutation_rate
        self.elite_ratio = elite_ratio
        self.early_stop_gens = early_stop_gens
        self.history: list[dict] = []

    def evaluate_population(self, individuals: list[Individual]):
        """Evaluate multiple individuals in parallel via ProcessPoolExecutor."""
        from concurrent.futures import ProcessPoolExecutor, as_completed

        # Build task list
        tasks = {}
        for ind in individuals:
            if ind.fitness != 0.0:  # already evaluated (elite)
                continue
            params = genes_to_params(ind.genes)
            tasks[ind] = params

        if not tasks:
            return

        with ProcessPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(_eval_one, p): ind
                for ind, p in tasks.items()
            }
            for fut in as_completed(futures):
                ind = futures[fut]
                try:
                    train_ret, train_dd, val_ret, val_dd = fut.result()
                    ind.train_return = train_ret
                    ind.train_dd = train_dd
                    ind.val_return = val_ret
                    ind.val_dd = val_dd
                    ind.fitness = (
                        fitness(train_ret, train_dd) * 0.5 +
                        fitness(val_ret, val_dd) * 0.5
                    )
                except Exception as e:
                    logger.error(f"Eval failed: {e}")
                    ind.fitness = -999.0

    def run(self):
        # Init population
        pop = [random_individual() for _ in range(self.pop_size)]
        logger.info(f"Evaluating initial population ({self.pop_size} individuals, 4 workers)...")
        self.evaluate_population(pop)
        for i, ind in enumerate(sorted(pop, key=lambda x: x.fitness, reverse=True)):
            logger.info(f"  [{i+1}/{self.pop_size}] fitness={ind.fitness:.1f} "
                        f"train={ind.train_return:.1f}%/-{ind.train_dd:.1f}% "
                        f"val={ind.val_return:.1f}%/-{ind.val_dd:.1f}%")

        best = max(pop, key=lambda x: x.fitness)
        best_fitness = best.fitness
        stale = 0
        n_elite = max(1, int(self.pop_size * self.elite_ratio))

        for gen in range(1, self.n_generations + 1):
            # Sort by fitness
            pop.sort(key=lambda x: x.fitness, reverse=True)
            elites = [deepcopy(pop[i]) for i in range(n_elite)]

            # Selection + crossover + mutation
            new_pop = elites[:]  # keep elites
            while len(new_pop) < self.pop_size:
                # Tournament selection
                t1 = random.sample(pop, min(3, len(pop)))
                t2 = random.sample(pop, min(3, len(pop)))
                p1 = max(t1, key=lambda x: x.fitness)
                p2 = max(t2, key=lambda x: x.fitness)
                # Crossover
                child_genes = crossover(p1.genes, p2.genes)
                # Mutation
                child_genes = mutate(child_genes, self.mutation_rate)
                new_pop.append(Individual(genes=child_genes))

            # Evaluate new individuals in parallel (skip elites)
            self.evaluate_population(new_pop[n_elite:])

            pop = new_pop
            gen_best = max(pop, key=lambda x: x.fitness)

            logger.info(f"Gen {gen}: best fitness={gen_best.fitness:.1f} "
                        f"train={gen_best.train_return:.1f}%/-{gen_best.train_dd:.1f}% "
                        f"val={gen_best.val_return:.1f}%/-{gen_best.val_dd:.1f}% "
                        f"genes: top_n={int(gen_best.genes['top_n'])} "
                        f"ma={int(gen_best.genes['ma_days'])} "
                        f"brk={int(gen_best.genes['breakout_days'])} "
                        f"w={gen_best.genes['max_weight_per_stock']:.2f}")

            self.history.append({
                "generation": gen,
                "fitness": gen_best.fitness,
                "train_return": gen_best.train_return,
                "train_dd": gen_best.train_dd,
                "val_return": gen_best.val_return,
                "val_dd": gen_best.val_dd,
                "genes": genes_to_params(gen_best.genes),
            })

            if gen_best.fitness > best_fitness + 0.5:
                best_fitness = gen_best.fitness
                best = gen_best
                stale = 0
            else:
                stale += 1
                if stale >= self.early_stop_gens:
                    logger.info(f"Early stop at generation {gen}")
                    break

        # Final best individual
        best = max(pop, key=lambda x: x.fitness)
        params = genes_to_params(best.genes)

        # Out-of-sample test
        logger.info("Running out-of-sample test...")
        test_m = _run_backtest(params, *TEST_PERIOD)
        logger.info(f"TEST: return={test_m.get('total_return_pct',0):.1f}% "
                    f"DD=-{test_m.get('max_drawdown_pct',0):.1f}% "
                    f"Sharpe={test_m.get('sharpe_ratio',0):.3f}")

        result = {
            "best_params": params,
            "train_return": best.train_return,
            "train_dd": best.train_dd,
            "val_return": best.val_return,
            "val_dd": best.val_dd,
            "test_return": test_m.get("total_return_pct", 0),
            "test_dd": test_m.get("max_drawdown_pct", 0),
            "test_sharpe": test_m.get("sharpe_ratio", 0),
            "fitness": best.fitness,
            "history": self.history,
        }

        # Save
        root = get_project_root()
        out = root / "data" / "ga_optimization_result.json"
        with open(out, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Results saved to {out}")

        return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Full run (pop=80, gen=40)")
    args = parser.parse_args()

    setup_file_log()
    t0 = time.time()

    if args.full:
        opt = GAOptimizer(pop_size=80, n_generations=40)
    else:
        opt = GAOptimizer(pop_size=30, n_generations=15)

    result = opt.run()

    elapsed = time.time() - t0
    logger.info(f"Done in {elapsed:.0f}s")
    logger.info(f"Best: {result['best_params']}")
    logger.info(f"Train: {result['train_return']:.1f}%/-{result['train_dd']:.1f}%")
    logger.info(f"Val: {result['val_return']:.1f}%/-{result['val_dd']:.1f}%")
    logger.info(f"Test (OOS): {result['test_return']:.1f}%/-{result['test_dd']:.1f}% Sharpe={result['test_sharpe']:.3f}")


if __name__ == "__main__":
    main()
