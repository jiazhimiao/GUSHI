"""GA Optimizer v2 — multi-objective fitness with Calmar + no_2024 + penalties.

Usage:
    python scripts/ga_optimizer_v2.py --smoke   # pop=4, gen=1, serial
    python scripts/ga_optimizer_v2.py --full    # future: formal GA
"""

import sys, json, time, random, os, copy, hashlib
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.diagnosis.signal_report import fifo_match
from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log

ROOT = get_project_root()
TRAIN = ("2018-01-01", "2021-12-31")
VAL   = ("2022-01-01", "2024-12-31")
FULL  = ("2018-01-01", "2026-05-08")

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

BASELINE_GENES = {
    "w_breadth": 0.23, "w_trend": 0.20, "w_stability": 0.06, "w_volume": 0.12,
    "score_low": 0.30, "score_high": 0.72,
    "breakout_bull": 10.0, "breakout_bear": 40.0,
    "atr_bull": 3.36, "atr_bear": 1.19,
    "vol_ratio_bull": 1.11, "vol_ratio_bear": 1.83,
    "top_n_bull": 5.0, "top_n_bear": 1.0,
    "support_bull": 7.0, "support_bear": 13.0,
    "ma_bull": 25.0, "ma_bear": 60.0,
    "max_loss_pct": 0.14, "profit_lock_pct": 0.16,
    "atr_period": 19.0, "breadth_ma_days": 35.0,
    "strategy_max_dd": 0.18, "max_weight_per_stock": 0.16,
}


def genes_to_regime_kwargs(genes):
    return {
        "w_breadth": genes["w_breadth"], "w_trend": genes["w_trend"],
        "w_stability": genes["w_stability"], "w_volume": genes["w_volume"],
        "score_low": genes["score_low"], "score_high": genes["score_high"],
        "breakout_bull": int(genes["breakout_bull"]), "breakout_bear": int(genes["breakout_bear"]),
        "atr_bull": genes["atr_bull"], "atr_bear": genes["atr_bear"],
        "vol_ratio_bull": genes["vol_ratio_bull"], "vol_ratio_bear": genes["vol_ratio_bear"],
        "top_n_bull": int(genes["top_n_bull"]), "top_n_bear": int(genes["top_n_bear"]),
        "support_bull": int(genes["support_bull"]), "support_bear": int(genes["support_bear"]),
        "ma_days_bull": int(genes["ma_bull"]), "ma_days_bear": int(genes["ma_bear"]),
    }


def _run_period(genes, period):
    regime = RegimeEngine(**genes_to_regime_kwargs(genes))
    s = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"], min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"], top_n=10,
        max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime; s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
    s.enable_rank_buffer = False; s.enable_pullback_entry = False

    engine = BacktestEngine(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=period[0], end_date=period[1], initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    metrics, nav, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)
    return metrics, nav, results["trades"]


def compute_fitness(train_m, val_m, full_m, nav_full, trades_full):
    M = {}
    # Calmar
    M["train_calmar"] = round(train_m.get("calmar_ratio", 0), 3)
    M["val_calmar"] = round(val_m.get("calmar_ratio", 0), 3)

    # no_2024
    full_ret = full_m["total_return_pct"]
    nf = nav_full.copy()
    nf["date_dt"] = pd.to_datetime(nf["date"]); nf["year"] = nf["date_dt"].dt.year
    sn24 = nf[nf["year"] == 2024]
    ret_2024 = ((sn24["total_value"].iloc[-1] / sn24["total_value"].iloc[0] - 1) * 100) if len(sn24) >= 2 else 0
    M["full_no_2024_pct"] = round(((1 + full_ret/100) / (1 + ret_2024/100) - 1) * 100, 2) if ret_2024 > -99 else full_ret

    val_ret = val_m["total_return_pct"]
    nv = nf[nf["date_dt"].between("2022-01-01","2024-12-31")].copy()
    sv24 = nv[nv["date_dt"].dt.year == 2024] if "date_dt" in nv.columns else pd.DataFrame()
    ret_2024v = ((sv24["total_value"].iloc[-1] / sv24["total_value"].iloc[0] - 1) * 100) if len(sv24) >= 2 else 0
    M["val_no_2024_pct"] = round(((1 + val_ret/100) / (1 + ret_2024v/100) - 1) * 100, 2) if ret_2024v > -99 else val_ret

    # Yearly from FULL
    nf["position_weight"] = nf["position_value"] / nf["total_value"]
    for yr in [2018, 2019, 2020, 2021, 2022, 2023, 2024]:
        sn = nf[nf["year"] == yr]
        if len(sn) >= 2:
            M[f"ret_{yr}"] = round((sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100, 2)
            peak = sn["total_value"].cummax()
            M[f"dd_{yr}"] = round((sn["total_value"] - peak).div(peak).min() * 100, 2)
        else:
            M[f"ret_{yr}"] = 0; M[f"dd_{yr}"] = 0
    # Exposure / avg position
    total_days = len(nf)
    with_positions = int((nf["n_positions"] > 0).sum()) if "n_positions" in nf.columns else 0
    M["exposure"] = round(with_positions / total_days * 100, 1) if total_days > 0 else 0
    M["avg_position"] = round(nf["position_weight"].mean() * 100, 2)

    # failed_entry_rate
    matched, _ = fifo_match(trades_full)
    valid = matched[matched["pnl_pct"].notna()]
    if len(valid) > 0:
        stop_kw = ["stop", "loss", "atr"]
        early = (valid["holding_days"] <= 10) & valid["exit_reason"].apply(lambda r: any(k in str(r).lower() for k in stop_kw))
        big = valid["pnl_pct"] < -0.05
        M["failed_entry_rate"] = round(len(valid[early | big]) / len(valid) * 100, 1)
    else:
        M["failed_entry_rate"] = 0

    buys = trades_full[trades_full["side"] == "BUY"]
    buy_val = buys["cost"].sum() if "cost" in buys.columns else 0
    avg_nav = nf["total_value"].mean()
    M["annual_turnover"] = round(buy_val / avg_nav / (len(nf) / 252), 2) if avg_nav > 0 else 0

    # max_year_profit_pct (based on NAV absolute profit)
    total_profit = nf["total_value"].iloc[-1] - nf["total_value"].iloc[0]
    yearly_profits = {}
    for yr in range(2018, 2027):
        sn = nf[nf["year"] == yr]
        if len(sn) >= 2:
            yearly_profits[yr] = sn["total_value"].iloc[-1] - sn["total_value"].iloc[0]
    if total_profit > 0:
        pos_profits = [v for v in yearly_profits.values() if v > 0]
        M["max_year_profit_pct"] = round(max(pos_profits) / total_profit * 100, 1) if pos_profits else 100
    else:
        M["max_year_profit_pct"] = 100

    M["annual_return_pct"] = round(full_m.get("annual_return_pct", 0), 2)
    M["total_trades"] = len(trades_full)
    M["avg_position"] = round(nf["position_weight"].mean() * 100, 2)

    # ── Scores ──
    S = {"raw": M}
    S["calmar_score"] = round(np.clip(M["train_calmar"] * 0.5 + M["val_calmar"] * 0.5, -1.0, 3.0), 3)
    S["no_2024_score"] = round(min(M["full_no_2024_pct"] / 15.0, 2.0), 3)
    rec = (max(0, M["ret_2019"] - 2.0) + max(0, M["ret_2020"] + 5.0)) / 20.0
    S["recovery_score"] = round(min(rec, 1.0), 3)
    bear = (max(0, abs(M["dd_2018"]) - 1.5) / 10.0 + max(0, abs(M["dd_2022"]) - 7.0) / 10.0) / 2
    S["bear_penalty"] = round(bear, 3)
    fer_p = max(0, M["failed_entry_rate"] - 20) / 30.0
    S["failed_entry_penalty"] = round(fer_p, 3)
    to_p = max(0, M["annual_turnover"] - 12) / 20.0
    S["turnover_penalty"] = round(to_p, 3)
    dep_p = max(0, M["max_year_profit_pct"] - 50) / 50.0
    S["dependency_penalty"] = round(dep_p, 3)

    fitness = (1.0 * S["calmar_score"] + 0.6 * S["no_2024_score"] + 0.3 * S["recovery_score"]
               - 0.5 * S["bear_penalty"] - 0.3 * S["failed_entry_penalty"]
               - 0.2 * S["turnover_penalty"] - 0.5 * S["dependency_penalty"])
    S["final_fitness"] = round(fitness, 3)
    return S


def evaluate_candidate(genes):
    tm, tn, tt = _run_period(genes, TRAIN)
    vm, vn, vt = _run_period(genes, VAL)
    fm, fn, ft = _run_period(genes, FULL)
    return compute_fitness(tm, vm, fm, fn, ft), {"train": tm, "val": vm, "full": fm}


# ═══════════════════════════════════════════════════════════════════
# GA operators
# ═══════════════════════════════════════════════════════════════════

def random_genes():
    """Generate random genes within PARAM_BOUNDS."""
    genes = {}
    for name, (lo, hi, step, is_int) in PARAM_BOUNDS.items():
        if is_int:
            genes[name] = float(random.randint(int(lo), int(hi)))
        else:
            genes[name] = round(random.uniform(lo, hi), 2)
    return genes


def tournament_select(population, tournament_size=3):
    """Tournament selection: pick best of k random candidates by fitness."""
    pool = random.sample(population, min(tournament_size, len(population)))
    return max(pool, key=lambda c: c["fitness"])


def uniform_crossover(g1, g2, crossover_rate=0.7):
    """Uniform crossover: each gene 50% from each parent, 70% overall prob."""
    if random.random() > crossover_rate:
        return copy.deepcopy(g1) if random.random() < 0.5 else copy.deepcopy(g2)
    child = {}
    for name in PARAM_BOUNDS:
        child[name] = g1[name] if random.random() < 0.5 else g2[name]
    return child


def mutate(genes, mutation_rate=0.15):
    """Gaussian mutation per gene, clamped to PARAM_BOUNDS."""
    mutated = copy.deepcopy(genes)
    for name, (lo, hi, step, is_int) in PARAM_BOUNDS.items():
        if random.random() < mutation_rate:
            sigma = (hi - lo) * 0.1
            new_val = genes[name] + random.gauss(0, sigma)
            new_val = max(lo, min(hi, new_val))
            if is_int:
                new_val = round(new_val) if abs(round(new_val) - new_val) < 0.3 else new_val
                new_val = float(max(int(lo), min(int(hi), int(round(new_val)))))
                # Ensure integer steps
                possible = [float(v) for v in range(int(lo), int(hi) + 1, int(step))]
                new_val = min(possible, key=lambda x: abs(x - new_val))
            else:
                new_val = round(new_val / step) * step
                new_val = round(max(lo, min(hi, new_val)), 2)
            mutated[name] = new_val
    return mutated


def genes_equal(g1, g2):
    """Check if two gene dicts are equal."""
    return all(g1[k] == g2[k] for k in PARAM_BOUNDS)


# ═══════════════════════════════════════════════════════════════════
# Gene hash & evaluation cache
# ═══════════════════════════════════════════════════════════════════

_EVAL_CACHE: dict[str, dict] = {}


def compute_gene_hash(genes):
    """Deterministic hash of a gene dict (sorted keys, canonical JSON)."""
    canonical = json.dumps({k: genes[k] for k in sorted(genes.keys())}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def cached_evaluate(genes):
    """Evaluate candidate with gene_hash cache. Returns (fitness_dict, metrics_dict_dict)."""
    gh = compute_gene_hash(genes)
    if gh in _EVAL_CACHE:
        cached = _EVAL_CACHE[gh]
        return cached["fitness"], cached["metrics_dict"], gh, True
    fitness, metrics_dict = evaluate_candidate(genes)
    _EVAL_CACHE[gh] = {"fitness": fitness, "metrics_dict": metrics_dict, "genes": genes}
    return fitness, metrics_dict, gh, False


def preload_cache(genes):
    """Pre-evaluate and cache a gene set (e.g. baseline)."""
    gh = compute_gene_hash(genes)
    if gh not in _EVAL_CACHE:
        fitness, metrics_dict = evaluate_candidate(genes)
        _EVAL_CACHE[gh] = {"fitness": fitness, "metrics_dict": metrics_dict, "genes": genes}
    return gh


def run_pilot(pop_size=12, n_generations=3, n_workers=4, seed=42):
    """Run small-scale GA pilot (pop=12, gen=3, workers=4)."""
    setup_file_log()
    random.seed(seed)
    np.random.seed(seed)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "ga_results" / f"v2_pilot_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"GA v2 PILOT")
    logger.info(f"  pop={pop_size}  gen={n_generations}  workers={n_workers}  seed={seed}")
    logger.info(f"  output: {out_dir}")
    logger.info("=" * 60)

    # Build initial population
    population = [{"id": "baseline", "genes": BASELINE_GENES.copy(), "gen": 0}]
    for i in range(1, pop_size):
        population.append({"id": f"gen0_r{i:02d}", "genes": random_genes(), "gen": 0})

    # Preload baseline into cache
    preload_cache(BASELINE_GENES)

    all_candidates = []
    gen_top5 = {}
    total_generated = 0
    total_cache_hits = 0

    for gen in range(n_generations):
        logger.info(f"\n{'='*60}")
        logger.info(f"GENERATION {gen}")
        logger.info(f"{'='*60}")

        # Evaluate unevaluated candidates in parallel
        unevaluated = [c for c in population if "fitness" not in c]
        gen_generated = len(population)
        gen_cache_hits = 0
        if unevaluated:
            logger.info(f"Evaluating {len(unevaluated)} candidates ({n_workers} workers)...")
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = {executor.submit(cached_evaluate, c["genes"]): c for c in unevaluated}
                for future in as_completed(futures):
                    c = futures[future]
                    try:
                        fitness, metrics_dict, gh, was_cached = future.result()
                    except Exception as e:
                        logger.error(f"  {c['id']} FAILED: {e}")
                        fitness = {"final_fitness": -99.0, "raw": {}, "calmar_score": 0, "no_2024_score": 0,
                                   "recovery_score": 0, "bear_penalty": 0, "failed_entry_penalty": 0,
                                   "turnover_penalty": 0, "dependency_penalty": 0}
                        metrics_dict = {"train": {}, "val": {}, "full": {}}
                        gh = "FAILED"; was_cached = False
                    c["fitness"] = fitness["final_fitness"]
                    c["fitness_decomposition"] = {k: v for k, v in fitness.items() if k != "raw"}
                    c["raw_metrics"] = fitness["raw"]
                    c["gene_hash"] = gh
                    c["metrics_dict"] = metrics_dict
                    if was_cached:
                        gen_cache_hits += 1
                    S = fitness; M = fitness.get("raw", {})
                    tag = " [CACHE]" if was_cached else ""
                    logger.info(f"  {c['id']}: fitness={S['final_fitness']:.3f} "
                                f"cal={S['calmar_score']:.3f} no24={S['no_2024_score']:.3f} "
                                f"rec={S['recovery_score']:.3f} "
                                f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)}{tag}")
            elapsed = time.time() - t0
            eval_count = len(unevaluated) - gen_cache_hits
            logger.info(f"  Generation {gen} eval done in {elapsed:.0f}s "
                        f"(generated={gen_generated} unique={len(unevaluated)} "
                        f"duplicates={gen_generated - len(unevaluated)} "
                        f"cache_hits={gen_cache_hits} evaluated={eval_count})")

            # Collect results
            all_candidates.extend([{k: v for k, v in c.items() if k != "metrics_dict"} for c in unevaluated])

        # Generation stats
        sorted_gen = sorted(population, key=lambda c: c.get("fitness", -999), reverse=True)
        fits = [c["fitness"] for c in sorted_gen if "fitness" in c]
        if fits:
            logger.info(f"  Gen {gen} top5:")
            for rank, c in enumerate(sorted_gen[:5]):
                S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
                logger.info(f"    #{rank+1} {c['id']}: fitness={c['fitness']:.3f} "
                            f"cal={S.get('calmar_score','?'):.3f} no24={S.get('no_2024_score','?'):.3f} "
                            f"ret={M.get('annual_return_pct','?'):.1f}% trades={M.get('total_trades','?')}")
            logger.info(f"  Gen {gen} stats: best={max(fits):.3f} mean={np.mean(fits):.3f} "
                        f"std={np.std(fits):.3f} min={min(fits):.3f}")
            gen_top5[f"gen_{gen}"] = [c["id"] for c in sorted_gen[:5]]

        # Build next generation (except after last)
        if gen < n_generations - 1:
            # Elite preservation: baseline + top 2 non-baseline
            non_baseline = [c for c in sorted_gen if c["id"] != "baseline" and "fitness" in c]
            elites = [copy.deepcopy(sorted_gen[0])]  # best overall
            if non_baseline:
                seen_ids = {sorted_gen[0]["id"]}
                for c in non_baseline:
                    if c["id"] not in seen_ids and len(elites) < 3:
                        elites.append(copy.deepcopy(c))
                        seen_ids.add(c["id"])
            # Always ensure baseline is in elites
            bl = next((c for c in sorted_gen if c["id"] == "baseline"), None)
            if bl and "baseline" not in {e["id"] for e in elites}:
                elites.append(copy.deepcopy(bl))

            new_pop = []
            for e in elites:
                if e["id"] == "baseline":
                    # Carry baseline forward with cached result (deterministic, skip re-eval)
                    fresh = {"id": "baseline", "genes": BASELINE_GENES.copy(), "gen": gen + 1,
                             "fitness": bl["fitness"], "fitness_decomposition": bl["fitness_decomposition"],
                             "raw_metrics": bl["raw_metrics"]}
                else:
                    fresh = {"id": f"gen{gen+1}_elite_{e['id']}",
                             "genes": copy.deepcopy(e["genes"]), "gen": gen + 1}
                new_pop.append(fresh)

            # Fill remaining with crossover + mutation
            eligible = [c for c in population if "fitness" in c]
            max_attempts = pop_size * 10
            attempts = 0
            while len(new_pop) < pop_size and attempts < max_attempts:
                attempts += 1
                p1 = tournament_select(eligible)
                p2 = tournament_select(eligible)
                child_genes = uniform_crossover(p1["genes"], p2["genes"])
                child_genes = mutate(child_genes)
                # Avoid exact duplicates
                dup = any(genes_equal(child_genes, c["genes"]) for c in new_pop)
                if dup:
                    continue
                new_pop.append({"id": f"gen{gen+1}_{len(new_pop):02d}",
                                "genes": child_genes, "gen": gen + 1})
            if len(new_pop) < pop_size:
                logger.warning(f"  Gen {gen}→{gen+1}: only {len(new_pop)}/{pop_size} filled "
                               f"(max attempts reached, adding randoms)")
                while len(new_pop) < pop_size:
                    new_pop.append({"id": f"gen{gen+1}_r{len(new_pop):02d}",
                                    "genes": random_genes(), "gen": gen + 1})

            logger.info(f"  Gen {gen}→{gen+1}: elites={[e['id'] for e in elites[:3]]} "
                        f"children={len(new_pop)-len(elites)}")
            population = new_pop

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info("PILOT RESULTS")
    logger.info(f"{'='*60}")
    sorted_all = sorted(all_candidates, key=lambda c: c.get("fitness", -999), reverse=True)
    for rank, c in enumerate(sorted_all[:10]):
        S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
        logger.info(f"\n#{rank+1} {c['id']} (gen {c['gen']}): fitness={c['fitness']:.3f}")
        logger.info(f"  calmar={S.get('calmar_score',0):.3f}  no24={S.get('no_2024_score',0):.3f}  "
                    f"rec={S.get('recovery_score',0):.3f}")
        logger.info(f"  bear_raw={S.get('bear_penalty',0):.3f} contrib={-0.5*S.get('bear_penalty',0):.3f}  "
                    f"fer_raw={S.get('failed_entry_penalty',0):.3f} contrib={-0.3*S.get('failed_entry_penalty',0):.3f}")
        logger.info(f"  to_raw={S.get('turnover_penalty',0):.3f} contrib={-0.2*S.get('turnover_penalty',0):.3f}  "
                    f"dep_raw={S.get('dependency_penalty',0):.3f} contrib={-0.5*S.get('dependency_penalty',0):.3f}")
        logger.info(f"  ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                    f"no24={M.get('full_no_2024_pct',0):.1f}% "
                    f"2019={M.get('ret_2019',0):+.1f}% 2020={M.get('ret_2020',0):+.1f}%")

    # Baseline check
    bl = next((c for c in sorted_all if c["id"] == "baseline"), None)
    if bl:
        logger.info(f"\nBaseline fitness: {bl['fitness']:.3f}")
        best = sorted_all[0]
        if best["id"] != "baseline":
            delta = best["fitness"] - bl["fitness"]
            logger.info(f"Best ({best['id']}) exceeds baseline by {delta:+.3f}")

    # ── Save outputs ──
    # Clean records for JSON (remove non-serializable)
    clean_records = []
    for c in all_candidates:
        rec = {k: v for k, v in c.items()}
        clean_records.append(rec)

    with open(out_dir / "all_candidates.json", "w") as f:
        json.dump(clean_records, f, indent=2, ensure_ascii=False, default=str)

    # CSV
    csv_rows = []
    for c in all_candidates:
        row = {"id": c["id"], "gen": c["gen"], "fitness": c["fitness"]}
        S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
        row.update({f"gene_{k}": v for k, v in c["genes"].items()})
        row.update(M)
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(out_dir / "all_candidates.csv", index=False)

    # Generation top5
    with open(out_dir / "generation_top5.json", "w") as f:
        json.dump(gen_top5, f, indent=2)

    # Final top10
    top10 = sorted_all[:10]
    with open(out_dir / "final_top10.json", "w") as f:
        json.dump([{k: v for k, v in c.items()} for c in top10], f, indent=2, ensure_ascii=False, default=str)

    # config
    config = {"mode": "pilot", "seed": seed, "pop_size": pop_size,
              "n_generations": n_generations, "n_workers": n_workers,
              "data_md5": "c79f9f1649895c897af28961e5d3c1fb",
              "baseline_fitness": bl["fitness"] if bl else None}
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # report.md
    report_lines = [
        f"# GA v2 Pilot Report",
        f"",
        f"**Date**: {ts}",
        f"**Config**: pop={pop_size}, gen={n_generations}, workers={n_workers}, seed={seed}",
        f"",
        f"## Baseline",
        f"",
    ]
    if bl:
        S = bl.get("fitness_decomposition", {}); M = bl.get("raw_metrics", {})
        report_lines += [
            f"- **fitness**: {bl['fitness']:.3f}",
            f"- **calmar_score**: {S.get('calmar_score',0):.3f}",
            f"- **no_2024_score**: {S.get('no_2024_score',0):.3f}",
            f"- **recovery_score**: {S.get('recovery_score',0):.3f}",
            f"- **bear_penalty**: {S.get('bear_penalty',0):.3f}",
            f"- **failed_entry_penalty**: {S.get('failed_entry_penalty',0):.3f}",
            f"- **turnover_penalty**: {S.get('turnover_penalty',0):.3f}",
            f"- **dependency_penalty**: {S.get('dependency_penalty',0):.3f}",
            f"- **annual_return**: {M.get('annual_return_pct',0):.2f}%",
            f"- **total_trades**: {M.get('total_trades',0)}",
            f"- **full_no_2024**: {M.get('full_no_2024_pct',0):.2f}%",
            f"- **ret_2019**: {M.get('ret_2019',0):+.2f}%",
            f"- **ret_2020**: {M.get('ret_2020',0):+.2f}%",
            f"- **dd_2018**: {M.get('dd_2018',0):.2f}%",
            f"- **dd_2022**: {M.get('dd_2022',0):.2f}%",
            f"- **failed_entry_rate**: {M.get('failed_entry_rate',0):.1f}%",
            f"- **annual_turnover**: {M.get('annual_turnover',0):.2f}",
            f"- **max_year_profit_pct**: {M.get('max_year_profit_pct',0):.1f}%",
            f"",
        ]

    report_lines += [
        f"## Top 10 Candidates",
        f"",
        f"| Rank | ID | Gen | Fitness | Calmar | No24 | Rec | Bear | Fer | TO | Dep | Ret% | Trades | No24% | 2019% | 2020% |",
        f"|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for rank, c in enumerate(sorted_all[:10]):
        S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
        report_lines.append(
            f"| {rank+1} | {c['id']} | {c['gen']} | {c['fitness']:.3f} | "
            f"{S.get('calmar_score',0):.3f} | {S.get('no_2024_score',0):.3f} | "
            f"{S.get('recovery_score',0):.3f} | {S.get('bear_penalty',0):.3f} | "
            f"{S.get('failed_entry_penalty',0):.3f} | {S.get('turnover_penalty',0):.3f} | "
            f"{S.get('dependency_penalty',0):.3f} | "
            f"{M.get('annual_return_pct',0):.1f} | {M.get('total_trades',0)} | "
            f"{M.get('full_no_2024_pct',0):.1f} | {M.get('ret_2019',0):+.1f} | "
            f"{M.get('ret_2020',0):+.1f} |"
        )

    best = sorted_all[0]
    report_lines += [
        f"",
        f"## Best vs Baseline",
        f"",
    ]
    if best["id"] != "baseline":
        delta_f = best["fitness"] - bl["fitness"]
        report_lines.append(f"Best candidate **{best['id']}** (gen {best['gen']}) exceeds baseline by **{delta_f:+.3f}**.")
        S_b = bl.get("fitness_decomposition", {}); S_x = best.get("fitness_decomposition", {})
        report_lines.append(f"")
        for comp_name, key in [("Calmar", "calmar_score"), ("No_2024", "no_2024_score"),
                                ("Recovery", "recovery_score"), ("Bear penalty", "bear_penalty"),
                                ("FER penalty", "failed_entry_penalty"), ("Turnover penalty", "turnover_penalty"),
                                ("Dependency penalty", "dependency_penalty")]:
            bv = S_b.get(key, 0); xv = S_x.get(key, 0)
            report_lines.append(f"- **{comp_name}**: baseline {bv:.3f} → best {xv:.3f} (Δ {xv-bv:+.3f})")
    else:
        report_lines.append(f"No candidate exceeded baseline (fitness={bl['fitness']:.3f}).")

    with open(out_dir / "report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    logger.info(f"\nSaved to {out_dir}")
    return out_dir


# ═══════════════════════════════════════════════════════════════════
# Phase 1: Single-parameter neighborhood scan
# ═══════════════════════════════════════════════════════════════════

PHASE1_SWEEP = {
    "score_high":      [0.68, 0.70, 0.72, 0.74, 0.76],
    "score_low":       [0.26, 0.28, 0.30, 0.32, 0.34],
    "breakout_bull":   [6.0, 8.0, 10.0, 12.0, 14.0],
    "breakout_bear":   [30.0, 35.0, 40.0, 45.0, 50.0],
    "vol_ratio_bull":  [0.91, 1.01, 1.11, 1.21, 1.31],
    "vol_ratio_bear":  [1.53, 1.63, 1.73, 1.83, 1.93, 2.03, 2.13],
    "atr_bull":        [2.86, 3.11, 3.36, 3.61, 3.86],
    "atr_bear":        [0.89, 1.04, 1.19, 1.34, 1.49],
    "support_bull":    [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    "support_bear":    [9.0, 11.0, 13.0, 15.0, 17.0],
}


def generate_phase1_candidates():
    """Generate single-parameter perturbation candidates from baseline."""
    candidates = [{"id": "baseline", "genes": BASELINE_GENES.copy(),
                   "changed_param": "none", "changed_value": None}]
    for param, values in PHASE1_SWEEP.items():
        for v in values:
            if v == BASELINE_GENES[param]:
                continue  # skip baseline value (already included)
            genes = BASELINE_GENES.copy()
            genes[param] = v
            candidates.append({
                "id": f"{param}_{v}",
                "genes": genes,
                "changed_param": param,
                "changed_value": v,
            })
    return candidates


def run_local_phase1(n_workers=4, seed=42):
    """Single-parameter neighborhood scan around baseline."""
    setup_file_log()
    random.seed(seed)
    np.random.seed(seed)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "ga_results" / f"local_search_phase1_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("LOCAL SEARCH — Phase 1: Single-Parameter Scan")
    logger.info(f"  params={len(PHASE1_SWEEP)}  workers={n_workers}  seed={seed}")
    logger.info(f"  output: {out_dir}")
    logger.info("=" * 60)

    # Preload baseline
    logger.info("Preloading baseline into cache...")
    t0 = time.time()
    bl_hash = preload_cache(BASELINE_GENES)
    logger.info(f"  baseline cached (hash={bl_hash}, {time.time()-t0:.0f}s)")

    # Generate candidates
    candidates = generate_phase1_candidates()
    total = len(candidates)
    baseline_count = sum(1 for c in candidates if c["id"] == "baseline")
    sweep_count = total - baseline_count
    logger.info(f"\nCandidates: {total} total ({baseline_count} baseline + {sweep_count} sweep)")

    # Evaluate sweep candidates in parallel (baseline already cached)
    sweep = [c for c in candidates if c["id"] != "baseline"]
    cache_hits = 0
    evaluated = 0

    logger.info(f"Evaluating {len(sweep)} sweep candidates ({n_workers} workers)...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(cached_evaluate, c["genes"]): c for c in sweep}
        for future in as_completed(futures):
            c = futures[future]
            try:
                fitness, metrics_dict, gh, was_cached = future.result()
            except Exception as e:
                logger.error(f"  {c['id']} FAILED: {e}")
                fitness = {"final_fitness": -99.0, "raw": {}, "calmar_score": 0, "no_2024_score": 0,
                           "recovery_score": 0, "bear_penalty": 0, "failed_entry_penalty": 0,
                           "turnover_penalty": 0, "dependency_penalty": 0}
                metrics_dict = {"train": {}, "val": {}, "full": {}}
                gh = "FAILED"; was_cached = False
            c["fitness"] = fitness["final_fitness"]
            c["fitness_decomposition"] = {k: v for k, v in fitness.items() if k != "raw"}
            c["raw_metrics"] = fitness["raw"]
            c["gene_hash"] = gh
            if was_cached:
                cache_hits += 1
            else:
                evaluated += 1
            S = fitness; M = fitness.get("raw", {})
            tag = " [CACHE]" if was_cached else ""
            logger.info(f"  {c['id']}: fitness={S['final_fitness']:.3f} "
                        f"cal={S['calmar_score']:.3f} no24={S['no_2024_score']:.3f} "
                        f"rec={S['recovery_score']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)}{tag}")
    elapsed = time.time() - t0
    logger.info(f"  Evaluation done in {elapsed:.0f}s "
                f"(generated={total} unique={len(sweep)} "
                f"cache_hits={cache_hits} evaluated={evaluated})")

    # Attach baseline result from cache
    bl_cached = _EVAL_CACHE[bl_hash]
    bl = next(c for c in candidates if c["id"] == "baseline")
    bl["fitness"] = bl_cached["fitness"]["final_fitness"]
    bl["fitness_decomposition"] = {k: v for k, v in bl_cached["fitness"].items() if k != "raw"}
    bl["raw_metrics"] = bl_cached["fitness"]["raw"]
    bl["gene_hash"] = bl_hash

    # ── Sensitivity analysis ──
    logger.info(f"\n{'='*60}")
    logger.info("PARAMETER SENSITIVITY")
    logger.info(f"{'='*60}")

    sensitivity_rows = []
    for param in PHASE1_SWEEP:
        param_cands = [c for c in candidates if c["changed_param"] == param and c.get("fitness") is not None]
        if not param_cands:
            continue
        fits = [c["fitness"] for c in param_cands]
        base_val = BASELINE_GENES[param]
        base_fit = bl["fitness"]
        max_fit = max(fits)
        max_val = next(c["changed_value"] for c in param_cands if c["fitness"] == max_fit)
        sensitivity = max_fit - base_fit

        # Check for boundary hugging
        bounds = PARAM_BOUNDS[param]
        at_lower = any(c["changed_value"] == bounds[0] and c["fitness"] == max_fit
                       for c in param_cands)
        at_upper = any(c["changed_value"] == bounds[1] and c["fitness"] == max_fit
                       for c in param_cands)

        logger.info(f"\n  {param} (baseline={base_val}):")
        logger.info(f"    fitness range: {min(fits):.3f} ~ {max_fit:.3f}  (Δ vs baseline: {sensitivity:+.3f})")
        logger.info(f"    best value: {max_val}")
        if at_lower:
            logger.info(f"    ⚠ 最佳值贴下边界 ({bounds[0]})")
        if at_upper:
            logger.info(f"    ⚠ 最佳值贴上边界 ({bounds[1]})")
        for c in sorted(param_cands, key=lambda x: -x["fitness"])[:3]:
            M = c.get("raw_metrics", {})
            logger.info(f"    {c['changed_value']}: fitness={c['fitness']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                        f"no24={M.get('full_no_2024_pct',0):.1f}% "
                        f"dd_2018={M.get('dd_2018',0):.1f}% dd_2022={M.get('dd_2022',0):.1f}%")

        sensitivity_rows.append({
            "param": param,
            "baseline_value": base_val,
            "best_value": max_val,
            "best_fitness": max_fit,
            "baseline_fitness": base_fit,
            "sensitivity": round(sensitivity, 3),
            "at_lower_boundary": at_lower,
            "at_upper_boundary": at_upper,
            "fitness_range": round(max_fit - min(fits), 3),
        })

    # ── Summary ──
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 1 SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Baseline fitness: {bl['fitness']:.3f}")
    best_overall = max(candidates, key=lambda c: c.get("fitness", -999))
    if best_overall["id"] != "baseline":
        delta = best_overall["fitness"] - bl["fitness"]
        logger.info(f"Best overall: {best_overall['id']} (fitness={best_overall['fitness']:.3f}, Δ={delta:+.3f})")
    else:
        logger.info(f"No candidate exceeded baseline.")

    # Find stable improvements (>0.05)
    improvers = [c for c in candidates
                 if c["id"] != "baseline" and c.get("fitness", -999) > bl["fitness"] + 0.05]
    if improvers:
        logger.info(f"\nStable improvers (>0.05): {len(improvers)}")
        for c in sorted(improvers, key=lambda x: -x["fitness"]):
            logger.info(f"  {c['id']}: fitness={c['fitness']:.3f} (Δ={c['fitness']-bl['fitness']:+.3f})")
    else:
        logger.info(f"\nNo stable improvers (>0.05) found.")

    # Trades/drawdown warnings
    for c in candidates:
        M = c.get("raw_metrics", {})
        if M.get("total_trades", 0) > bl["raw_metrics"]["total_trades"] * 3:
            logger.warning(f"  Trades spike: {c['id']} trades={M.get('total_trades',0)} "
                          f"(vs baseline {bl['raw_metrics']['total_trades']})")
        if M.get("max_drawdown_pct", 0) and abs(M.get("max_drawdown_pct", 0)) > abs(bl["raw_metrics"].get("max_drawdown_pct", 0)) * 1.5:
            # max_drawdown_pct is negative
            pass  # Already covered by penalty

    # ── Save outputs ──
    all_records = []
    for c in candidates:
        if "fitness" not in c:
            continue
        S = c.get("fitness_decomposition", {})
        M = c.get("raw_metrics", {})
        rec = {
            "id": c["id"],
            "changed_param": c["changed_param"],
            "changed_value": c["changed_value"],
            "gene_hash": c.get("gene_hash", ""),
            "genes": c["genes"],
            "final_fitness": c["fitness"],
            "fitness_decomposition": S,
            "raw_metrics": M,
        }
        all_records.append(rec)

    with open(out_dir / "phase1_results.json", "w") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False, default=str)

    # CSV
    csv_rows = []
    for rec in all_records:
        row = {
            "id": rec["id"], "changed_param": rec["changed_param"],
            "changed_value": rec["changed_value"], "gene_hash": rec["gene_hash"],
            "final_fitness": rec["final_fitness"],
        }
        S = rec["fitness_decomposition"]; M = rec["raw_metrics"]
        row.update({f"gene_{k}": v for k, v in rec["genes"].items()})
        row.update({k: v for k, v in S.items() if k != "final_fitness"})
        row.update(M)
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(out_dir / "phase1_results.csv", index=False)

    # Sensitivity CSV
    sens_df = pd.DataFrame(sensitivity_rows)
    sens_df = sens_df.sort_values("sensitivity", ascending=False)
    sens_df.to_csv(out_dir / "parameter_sensitivity.csv", index=False)
    logger.info(f"\nParameter sensitivity (sorted):")
    for _, row in sens_df.iterrows():
        flags = ""
        if row["at_lower_boundary"]:
            flags += " ⚠LOWER"
        if row["at_upper_boundary"]:
            flags += " ⚠UPPER"
        logger.info(f"  {row['param']}: sensitivity={row['sensitivity']:+.3f} "
                    f"(best={row['best_value']} fit={row['best_fitness']:.3f}){flags}")

    # config
    config = {"mode": "local_search_phase1", "seed": seed, "n_workers": n_workers,
              "data_md5": "c79f9f1649895c897af28961e5d3c1fb",
              "baseline_fitness": bl["fitness"], "baseline_hash": bl_hash,
              "total_candidates": total, "evaluated": evaluated, "cache_hits": cache_hits}
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # report.md
    report_lines = [
        f"# Local Search Phase 1 Report",
        f"",
        f"**Date**: {ts}",
        f"**Config**: params={len(PHASE1_SWEEP)}, workers={n_workers}, seed={seed}",
        f"**Baseline fitness**: {bl['fitness']:.3f}",
        f"",
        f"## Sensitivity Ranking",
        f"",
        f"| Rank | Parameter | Sensitivity | Best Value | Best Fitness | Boundary? |",
        f"|---|---|:---:|:---:|:---:|---|",
    ]
    for rank, (_, row) in enumerate(sens_df.iterrows()):
        flags = ""
        if row["at_lower_boundary"]:
            flags += " ⚠LOWER"
        if row["at_upper_boundary"]:
            flags += " ⚠UPPER"
        report_lines.append(
            f"| {rank+1} | {row['param']} | {row['sensitivity']:+.3f} | "
            f"{row['best_value']} | {row['best_fitness']:.3f} | {flags} |"
        )

    report_lines += [
        f"",
        f"## Best vs Baseline",
        f"",
    ]
    if best_overall["id"] != "baseline":
        delta = best_overall["fitness"] - bl["fitness"]
        report_lines.append(f"Best candidate **{best_overall['id']}** exceeds baseline by **{delta:+.3f}**.")
        S_b = bl.get("fitness_decomposition", {})
        S_x = best_overall.get("fitness_decomposition", {})
        for comp_name, key in [("Calmar", "calmar_score"), ("No_2024", "no_2024_score"),
                                ("Recovery", "recovery_score"), ("Bear penalty", "bear_penalty"),
                                ("FER penalty", "failed_entry_penalty"),
                                ("Turnover penalty", "turnover_penalty"),
                                ("Dependency penalty", "dependency_penalty")]:
            bv = S_b.get(key, 0); xv = S_x.get(key, 0)
            report_lines.append(f"- **{comp_name}**: baseline {bv:.3f} → best {xv:.3f} (Δ {xv-bv:+.3f})")
    else:
        report_lines.append(f"No candidate exceeded baseline (fitness={bl['fitness']:.3f}).")

    if improvers:
        report_lines.append(f"\n## Stable Improvers (>0.05)\n")
        report_lines.append(f"{len(improvers)} candidate(s) found.")
    else:
        report_lines.append(f"\n## Stable Improvers (>0.05)\n")
        report_lines.append(f"None found.")

    with open(out_dir / "report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    logger.info(f"\nSaved to {out_dir}")
    return out_dir


# ═══════════════════════════════════════════════════════════════════
# Phase 1b: Boundary expansion + top validation
# ═══════════════════════════════════════════════════════════════════

PHASE1B_SWEEP = {
    "atr_bear":       [0.65, 0.75, 0.89, 1.04, 1.19],
    "breakout_bull":  [10.0, 12.0, 14.0, 16.0, 18.0],
    "atr_bull":       [2.36, 2.61, 2.86, 3.11, 3.36],
    "score_high":     [0.72, 0.74, 0.76, 0.78, 0.80],
    "support_bull":   [2.0, 3.0, 4.0, 5.0, 6.0],
    "support_bear":   [5.0, 7.0, 9.0, 11.0, 13.0],
}

PHASE1B_VALIDATION = {
    "breakout_bear": [35.0],
}


def generate_phase1b_candidates():
    """Generate Phase 1b candidates: boundary expansion + top validation."""
    seen_hashes = set()
    candidates = []

    def add_candidate(genes, changed_param, changed_value, tag):
        gh = compute_gene_hash(genes)
        if gh not in seen_hashes:
            seen_hashes.add(gh)
            candidates.append({
                "id": f"{changed_param}_{changed_value}" if changed_param != "none" else "baseline",
                "genes": genes.copy(),
                "changed_param": changed_param,
                "changed_value": changed_value,
                "tag": tag,
            })

    # Baseline
    add_candidate(BASELINE_GENES, "none", None, "baseline")

    # Validation group (Phase 1 top performers)
    for param, values in PHASE1B_VALIDATION.items():
        for v in values:
            genes = BASELINE_GENES.copy()
            genes[param] = v
            add_candidate(genes, param, v, "validation")

    # Boundary expansion
    for param, values in PHASE1B_SWEEP.items():
        for v in values:
            genes = BASELINE_GENES.copy()
            genes[param] = v
            add_candidate(genes, param, v, "expansion")

    return candidates


def run_local_phase1b(n_workers=4, seed=42):
    """Phase 1b: boundary expansion + validation of Phase 1 top performers."""
    setup_file_log()
    random.seed(seed)
    np.random.seed(seed)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "ga_results" / f"local_search_phase1b_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("LOCAL SEARCH — Phase 1b: Boundary Expansion + Validation")
    logger.info(f"  params={len(PHASE1B_SWEEP)} expansion + {len(PHASE1B_VALIDATION)} validation")
    logger.info(f"  workers={n_workers}  seed={seed}")
    logger.info(f"  output: {out_dir}")
    logger.info("=" * 60)

    # Preload baseline
    logger.info("Preloading baseline into cache...")
    t0 = time.time()
    bl_hash = preload_cache(BASELINE_GENES)
    logger.info(f"  baseline cached (hash={bl_hash}, {time.time()-t0:.0f}s)")

    # Generate candidates
    candidates = generate_phase1b_candidates()
    total = len(candidates)
    validation_count = sum(1 for c in candidates if c["tag"] == "validation")
    expansion_count = sum(1 for c in candidates if c["tag"] == "expansion")
    baseline_in_list = sum(1 for c in candidates if c["tag"] == "baseline")
    logger.info(f"\nCandidates: {total} total ({baseline_in_list} baseline, "
                f"{validation_count} validation, {expansion_count} expansion)")

    # Evaluate sweep candidates in parallel (baseline already cached)
    sweep = [c for c in candidates if c["id"] != "baseline"]
    cache_hits = 0
    evaluated = 0

    logger.info(f"Evaluating {len(sweep)} sweep candidates ({n_workers} workers)...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(cached_evaluate, c["genes"]): c for c in sweep}
        for future in as_completed(futures):
            c = futures[future]
            try:
                fitness, metrics_dict, gh, was_cached = future.result()
            except Exception as e:
                logger.error(f"  {c['id']} FAILED: {e}")
                fitness = {"final_fitness": -99.0, "raw": {}, "calmar_score": 0, "no_2024_score": 0,
                           "recovery_score": 0, "bear_penalty": 0, "failed_entry_penalty": 0,
                           "turnover_penalty": 0, "dependency_penalty": 0}
                metrics_dict = {"train": {}, "val": {}, "full": {}}
                gh = "FAILED"; was_cached = False
            c["fitness"] = fitness["final_fitness"]
            c["fitness_decomposition"] = {k: v for k, v in fitness.items() if k != "raw"}
            c["raw_metrics"] = fitness["raw"]
            c["gene_hash"] = gh
            if was_cached:
                cache_hits += 1
            else:
                evaluated += 1
            S = fitness; M = fitness.get("raw", {})
            tag = f" [{c['tag']}]" + (" [CACHE]" if was_cached else "")
            logger.info(f"  {c['id']}: fitness={S['final_fitness']:.3f} "
                        f"cal={S['calmar_score']:.3f} no24={S['no_2024_score']:.3f} "
                        f"rec={S['recovery_score']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)}{tag}")
    elapsed = time.time() - t0
    logger.info(f"  Evaluation done in {elapsed:.0f}s "
                f"(generated={total} unique={len(sweep)} "
                f"cache_hits={cache_hits} evaluated={evaluated})")

    # Attach baseline result from cache
    bl_cached = _EVAL_CACHE[bl_hash]
    bl = next(c for c in candidates if c["id"] == "baseline")
    bl["fitness"] = bl_cached["fitness"]["final_fitness"]
    bl["fitness_decomposition"] = {k: v for k, v in bl_cached["fitness"].items() if k != "raw"}
    bl["raw_metrics"] = bl_cached["fitness"]["raw"]
    bl["gene_hash"] = bl_hash

    # ── Sensitivity & boundary analysis ──
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 1b RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Baseline fitness: {bl['fitness']:.3f}")

    # Per-parameter analysis for expansion params
    all_params = list(PHASE1B_SWEEP.keys()) + list(PHASE1B_VALIDATION.keys())
    sensitivity_rows = []

    for param in all_params:
        param_cands = [c for c in candidates if c["changed_param"] == param and c.get("fitness") is not None]
        if not param_cands:
            continue
        fits = [c["fitness"] for c in param_cands]
        base_val = BASELINE_GENES[param]
        base_fit = bl["fitness"]
        max_fit = max(fits)
        max_cand = max(param_cands, key=lambda c: c["fitness"])
        max_val = max_cand["changed_value"]

        bounds = PARAM_BOUNDS.get(param, (0, 1, 0.01, False))
        at_lower = (max_val == min(c["changed_value"] for c in param_cands))
        at_upper = (max_val == max(c["changed_value"] for c in param_cands))

        logger.info(f"\n  {param} (baseline={base_val}):")
        logger.info(f"    fitness range: {min(fits):.3f} ~ {max_fit:.3f}  (Δ vs baseline: {max_fit - base_fit:+.3f})")
        logger.info(f"    best value: {max_val}")
        if at_lower and max_val < base_val:
            logger.info(f"    ⚠ 最佳值在下边界，可能需要继续下探")
        if at_upper and max_val > base_val:
            logger.info(f"    ⚠ 最佳值在上边界，可能需要继续上探")
        for c in sorted(param_cands, key=lambda x: -x["fitness"])[:3]:
            M = c.get("raw_metrics", {})
            logger.info(f"    {c['changed_value']}: fitness={c['fitness']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                        f"no24={M.get('full_no_2024_pct',0):.1f}% "
                        f"dd_2018={M.get('dd_2018',0):.1f}% dd_2022={M.get('dd_2022',0):.1f}%")

        sensitivity_rows.append({
            "param": param,
            "baseline_value": base_val,
            "best_value": max_val,
            "best_fitness": max_fit,
            "baseline_fitness": base_fit,
            "sensitivity": round(max_fit - base_fit, 3),
            "at_lower_boundary": at_lower,
            "at_upper_boundary": at_upper,
            "fitness_range": round(max_fit - min(fits), 3),
            "tag": max_cand.get("tag", ""),
        })

    # ── Summary ──
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 1b SUMMARY")
    logger.info(f"{'='*60}")

    all_valid = [c for c in candidates if "fitness" in c]
    sorted_all = sorted(all_valid, key=lambda c: c["fitness"], reverse=True)
    best_overall = sorted_all[0]
    if best_overall["id"] != "baseline":
        delta = best_overall["fitness"] - bl["fitness"]
        logger.info(f"Best overall: {best_overall['id']} (fitness={best_overall['fitness']:.3f}, Δ={delta:+.3f})")
    else:
        logger.info(f"No candidate exceeded baseline.")

    # Top 10
    logger.info(f"\nTop 10:")
    for rank, c in enumerate(sorted_all[:10]):
        S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
        logger.info(f"  #{rank+1} {c['id']}: fitness={c['fitness']:.3f} "
                    f"cal={S.get('calmar_score',0):.3f} no24={S.get('no_2024_score',0):.3f} "
                    f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                    f"dd2022={M.get('dd_2022',0):.1f}%")

    # Trades/DD check
    bl_trades = bl["raw_metrics"]["total_trades"]
    for c in sorted_all[:5]:
        if c["id"] == "baseline":
            continue
        M = c.get("raw_metrics", {})
        trades = M.get("total_trades", 0)
        if trades > bl_trades * 1.5:
            logger.warning(f"  ⚠ Trades spike: {c['id']} trades={trades} (+{(trades/bl_trades-1)*100:.0f}%)")
        dd = abs(M.get("max_drawdown_pct", 0)) if M.get("max_drawdown_pct") else 0
        if dd > 12:
            logger.warning(f"  ⚠ DD warning: {c['id']} max_dd={dd:.1f}%")

    # ── Save outputs ──
    all_records = []
    for c in candidates:
        if "fitness" not in c:
            continue
        S = c.get("fitness_decomposition", {})
        M = c.get("raw_metrics", {})
        rec = {
            "id": c["id"],
            "changed_param": c["changed_param"],
            "changed_value": c["changed_value"],
            "tag": c.get("tag", ""),
            "gene_hash": c.get("gene_hash", ""),
            "genes": c["genes"],
            "final_fitness": c["fitness"],
            "fitness_decomposition": S,
            "raw_metrics": M,
        }
        all_records.append(rec)

    with open(out_dir / "phase1b_results.json", "w") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False, default=str)

    # CSV
    csv_rows = []
    for rec in all_records:
        row = {
            "id": rec["id"], "changed_param": rec["changed_param"],
            "changed_value": rec["changed_value"], "tag": rec["tag"],
            "gene_hash": rec["gene_hash"], "final_fitness": rec["final_fitness"],
        }
        S = rec["fitness_decomposition"]; M = rec["raw_metrics"]
        row.update({f"gene_{k}": v for k, v in rec["genes"].items()})
        row.update({k: v for k, v in S.items() if k != "final_fitness"})
        row.update(M)
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(out_dir / "phase1b_results.csv", index=False)

    # Sensitivity CSV
    sens_df = pd.DataFrame(sensitivity_rows)
    sens_df = sens_df.sort_values("sensitivity", ascending=False)
    sens_df.to_csv(out_dir / "parameter_sensitivity.csv", index=False)
    logger.info(f"\nParameter sensitivity (sorted):")
    for _, row in sens_df.iterrows():
        flags = ""
        if row["at_lower_boundary"]:
            flags += " ⚠LOWER"
        if row["at_upper_boundary"]:
            flags += " ⚠UPPER"
        logger.info(f"  {row['param']}: sensitivity={row['sensitivity']:+.3f} "
                    f"(best={row['best_value']} fit={row['best_fitness']:.3f}){flags}")

    # config
    config = {"mode": "local_search_phase1b", "seed": seed, "n_workers": n_workers,
              "data_md5": "c79f9f1649895c897af28961e5d3c1fb",
              "baseline_fitness": bl["fitness"], "baseline_hash": bl_hash,
              "total_candidates": total, "evaluated": evaluated, "cache_hits": cache_hits}
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # report.md
    report_lines = [
        f"# Local Search Phase 1b Report",
        f"",
        f"**Date**: {ts}",
        f"**Config**: expansion params={len(PHASE1B_SWEEP)}, validation params={len(PHASE1B_VALIDATION)}, "
        f"workers={n_workers}, seed={seed}",
        f"**Baseline fitness**: {bl['fitness']:.3f}",
        f"",
        f"## Sensitivity Ranking",
        f"",
        f"| Rank | Parameter | Sensitivity | Best Value | Best Fitness | Boundary? | Tag |",
        f"|---|---|:---:|:---:|:---:|---|---|",
    ]
    for rank, (_, row) in enumerate(sens_df.iterrows()):
        flags = ""
        if row["at_lower_boundary"]:
            flags += " ⚠LOWER"
        if row["at_upper_boundary"]:
            flags += " ⚠UPPER"
        report_lines.append(
            f"| {rank+1} | {row['param']} | {row['sensitivity']:+.3f} | "
            f"{row['best_value']} | {row['best_fitness']:.3f} | {flags} | {row['tag']} |"
        )

    report_lines += [
        f"",
        f"## Top 10 Candidates",
        f"",
        f"| Rank | ID | Fitness | Calmar | No24 | Rec | Ret% | Trades | DD2022% | Tag |",
        f"|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|",
    ]
    for rank, c in enumerate(sorted_all[:10]):
        S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
        report_lines.append(
            f"| {rank+1} | {c['id']} | {c['fitness']:.3f} | "
            f"{S.get('calmar_score',0):.3f} | {S.get('no_2024_score',0):.3f} | "
            f"{S.get('recovery_score',0):.3f} | {M.get('annual_return_pct',0):.1f} | "
            f"{M.get('total_trades',0)} | {M.get('dd_2022',0):.1f} | {c.get('tag','')} |"
        )

    report_lines += [
        f"",
        f"## Best vs Baseline",
        f"",
    ]
    if best_overall["id"] != "baseline":
        delta = best_overall["fitness"] - bl["fitness"]
        report_lines.append(f"Best candidate **{best_overall['id']}** exceeds baseline by **{delta:+.3f}**.")
        S_b = bl.get("fitness_decomposition", {})
        S_x = best_overall.get("fitness_decomposition", {})
        for comp_name, key in [("Calmar", "calmar_score"), ("No_2024", "no_2024_score"),
                                ("Recovery", "recovery_score"), ("Bear penalty", "bear_penalty"),
                                ("FER penalty", "failed_entry_penalty"),
                                ("Turnover penalty", "turnover_penalty"),
                                ("Dependency penalty", "dependency_penalty")]:
            bv = S_b.get(key, 0); xv = S_x.get(key, 0)
            report_lines.append(f"- **{comp_name}**: baseline {bv:.3f} → best {xv:.3f} (Δ {xv-bv:+.3f})")
    else:
        report_lines.append(f"No candidate exceeded baseline (fitness={bl['fitness']:.3f}).")

    # Boundary notes
    report_lines += [
        f"",
        f"## Boundary Analysis",
        f"",
    ]
    boundary_params = [r for r in sensitivity_rows if r["at_lower_boundary"] or r["at_upper_boundary"]]
    if boundary_params:
        for r in boundary_params:
            direction = "LOWER" if r["at_lower_boundary"] else "UPPER"
            report_lines.append(f"- **{r['param']}**: best value {r['best_value']} at {direction} boundary "
                                f"(fitness={r['best_fitness']:.3f}, sensitivity={r['sensitivity']:+.3f})")
    else:
        report_lines.append(f"No boundary-hugging detected. All optima are interior points.")

    with open(out_dir / "report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    logger.info(f"\nSaved to {out_dir}")
    return out_dir


# ═══════════════════════════════════════════════════════════════════
# Phase 1c: score_high expansion + support_bear deep probe
# ═══════════════════════════════════════════════════════════════════

PHASE1C_SWEEP = {
    "score_high":   [0.76, 0.78, 0.80, 0.82, 0.84, 0.86, 0.88, 0.90],
    "support_bear": [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0],
}


def run_local_phase1c(n_workers=4, seed=42):
    """Phase 1c: score_high boundary expansion + support_bear deep probe."""
    setup_file_log()
    random.seed(seed)
    np.random.seed(seed)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "ga_results" / f"local_search_phase1c_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("LOCAL SEARCH — Phase 1c: score_high Expansion + support_bear Probe")
    logger.info(f"  score_high range: {PHASE1C_SWEEP['score_high']}")
    logger.info(f"  support_bear range: {PHASE1C_SWEEP['support_bear']}")
    logger.info(f"  workers={n_workers}  seed={seed}")
    logger.info(f"  output: {out_dir}")
    logger.info("=" * 60)

    # Preload baseline
    logger.info("Preloading baseline into cache...")
    t0 = time.time()
    bl_hash = preload_cache(BASELINE_GENES)
    logger.info(f"  baseline cached (hash={bl_hash}, {time.time()-t0:.0f}s)")

    # Generate candidates with gene_hash dedup
    seen_hashes = {bl_hash}
    candidates = [{"id": "baseline", "genes": BASELINE_GENES.copy(),
                   "changed_param": "none", "changed_value": None}]

    for param, values in PHASE1C_SWEEP.items():
        for v in values:
            genes = BASELINE_GENES.copy()
            genes[param] = v
            gh = compute_gene_hash(genes)
            if gh not in seen_hashes:
                seen_hashes.add(gh)
                candidates.append({"id": f"{param}_{v}", "genes": genes,
                                   "changed_param": param, "changed_value": v})
            else:
                logger.info(f"  Skip duplicate: {param}={v} (hash={gh})")

    total = len(candidates)
    logger.info(f"\nCandidates: {total} total ({sum(1 for c in candidates if c['changed_param']=='score_high')} score_high, "
                f"{sum(1 for c in candidates if c['changed_param']=='support_bear')} support_bear, "
                f"{sum(1 for c in candidates if c['changed_param']=='none')} baseline)")

    # Evaluate in parallel
    sweep = [c for c in candidates if c["id"] != "baseline"]
    cache_hits = 0
    evaluated = 0

    logger.info(f"Evaluating {len(sweep)} sweep candidates ({n_workers} workers)...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(cached_evaluate, c["genes"]): c for c in sweep}
        for future in as_completed(futures):
            c = futures[future]
            try:
                fitness, metrics_dict, gh, was_cached = future.result()
            except Exception as e:
                logger.error(f"  {c['id']} FAILED: {e}")
                fitness = {"final_fitness": -99.0, "raw": {}, "calmar_score": 0, "no_2024_score": 0,
                           "recovery_score": 0, "bear_penalty": 0, "failed_entry_penalty": 0,
                           "turnover_penalty": 0, "dependency_penalty": 0}
                metrics_dict = {"train": {}, "val": {}, "full": {}}
                gh = "FAILED"; was_cached = False
            c["fitness"] = fitness["final_fitness"]
            c["fitness_decomposition"] = {k: v for k, v in fitness.items() if k != "raw"}
            c["raw_metrics"] = fitness["raw"]
            c["gene_hash"] = gh
            if was_cached:
                cache_hits += 1
            else:
                evaluated += 1
            # Augment raw_metrics with extra yearly returns from full metrics
            fm = metrics_dict.get("full", {})
            rm = c["raw_metrics"]
            if "total_return_pct" not in rm and "total_return_pct" in fm:
                rm["total_return_pct"] = fm["total_return_pct"]
            if "max_drawdown_pct" not in rm and "max_drawdown_pct" in fm:
                rm["max_drawdown_pct"] = fm["max_drawdown_pct"]
            S = fitness; M = rm
            tag = f" [{c['changed_param']}]" + (" [CACHE]" if was_cached else "")
            logger.info(f"  {c['id']}: fitness={S['final_fitness']:.3f} "
                        f"cal={S['calmar_score']:.3f} no24={S['no_2024_score']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)}{tag}")
    elapsed = time.time() - t0
    logger.info(f"  Evaluation done in {elapsed:.0f}s "
                f"(generated={total} evaluated={evaluated} cache_hits={cache_hits})")

    # Attach baseline
    bl_cached = _EVAL_CACHE[bl_hash]
    bl = candidates[0]
    bl["fitness"] = bl_cached["fitness"]["final_fitness"]
    bl["fitness_decomposition"] = {k: v for k, v in bl_cached["fitness"].items() if k != "raw"}
    bl["raw_metrics"] = bl_cached["fitness"]["raw"]
    bl["gene_hash"] = bl_hash

    # ── Per-parameter analysis ──
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 1c RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Baseline fitness: {bl['fitness']:.3f}")

    sensitivity_rows = []
    for param in PHASE1C_SWEEP:
        param_cands = [c for c in candidates if c["changed_param"] == param and c.get("fitness") is not None]
        if not param_cands:
            continue
        fits = [c["fitness"] for c in param_cands]
        base_val = BASELINE_GENES[param]
        base_fit = bl["fitness"]
        max_fit = max(fits)
        max_cand = max(param_cands, key=lambda c: c["fitness"])
        max_val = max_cand["changed_value"]

        # Boundary check against sweep edges, not PARAM_BOUNDS
        sweep_vals = sorted(PHASE1C_SWEEP[param])
        at_lower = (max_val == sweep_vals[0])
        at_upper = (max_val == sweep_vals[-1])

        logger.info(f"\n  {param} (baseline={base_val}):")
        logger.info(f"    fitness range: {min(fits):.3f} ~ {max_fit:.3f}  (Δ vs baseline: {max_fit - base_fit:+.3f})")
        logger.info(f"    best value: {max_val}")
        if at_lower:
            logger.info(f"    ⚠ 贴在扫描下边界 {sweep_vals[0]}，可能需继续下探")
        if at_upper:
            logger.info(f"    ⚠ 贴在扫描上边界 {sweep_vals[-1]}，可能需继续上扩")

        for c in sorted(param_cands, key=lambda x: -x["fitness"])[:5]:
            M = c.get("raw_metrics", {})
            logger.info(f"    {c['changed_value']}: fitness={c['fitness']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                        f"no24={M.get('full_no_2024_pct',0):.1f}% dd22={M.get('dd_2022',0):.1f}% "
                        f"r19={M.get('ret_2019',0):+.1f}% r20={M.get('ret_2020',0):+.1f}%")

        sensitivity_rows.append({
            "param": param, "baseline_value": base_val,
            "best_value": max_val, "best_fitness": max_fit,
            "baseline_fitness": base_fit,
            "sensitivity": round(max_fit - base_fit, 3),
            "at_lower_boundary": at_lower, "at_upper_boundary": at_upper,
            "fitness_range": round(max_fit - min(fits), 3),
        })

    # ── Summary ──
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 1c SUMMARY")
    logger.info(f"{'='*60}")

    all_valid = [c for c in candidates if "fitness" in c]
    sorted_all = sorted(all_valid, key=lambda c: c["fitness"], reverse=True)
    best_overall = sorted_all[0]
    delta = best_overall["fitness"] - bl["fitness"]
    logger.info(f"Best: {best_overall['id']} fitness={best_overall['fitness']:.3f} (Δ={delta:+.3f})")

    # Top 10
    logger.info(f"\nTop 10:")
    for rank, c in enumerate(sorted_all[:10]):
        S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
        logger.info(f"  #{rank+1} {c['id']}: fitness={c['fitness']:.3f} "
                    f"cal={S.get('calmar_score',0):.3f} no24={S.get('no_2024_score',0):.3f} "
                    f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                    f"dd22={M.get('dd_2022',0):.1f}% r19={M.get('ret_2019',0):+.1f}% r20={M.get('ret_2020',0):+.1f}%")

    # Trades/exposure check
    bl_trades = bl["raw_metrics"]["total_trades"]
    for c in sorted_all[:5]:
        if c["id"] == "baseline":
            continue
        M = c.get("raw_metrics", {})
        trades = M.get("total_trades", 0)
        if trades < bl_trades * 0.5:
            logger.warning(f"  ⚠ Trades collapse: {c['id']} trades={trades} (-{(1-trades/bl_trades)*100:.0f}%)")
        if trades > bl_trades * 2:
            logger.warning(f"  ⚠ Trades spike: {c['id']} trades={trades} (+{(trades/bl_trades-1)*100:.0f}%)")

    # score_high trend analysis
    sh_cands = sorted(
        [c for c in candidates if c["changed_param"] == "score_high" and c.get("fitness")],
        key=lambda c: c["changed_value"]
    )
    if sh_cands:
        logger.info(f"\n  score_high trend (value → fitness):")
        for c in sh_cands:
            M = c.get("raw_metrics", {})
            at_edge = ""
            if c["changed_value"] == PHASE1C_SWEEP["score_high"][-1] and c["fitness"] == max(
                    cc["fitness"] for cc in sh_cands):
                at_edge = " ⚠UPPER_EDGE"
            logger.info(f"    {c['changed_value']:.2f}: f={c['fitness']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                        f"no24={M.get('full_no_2024_pct',0):.1f}% dd22={M.get('dd_2022',0):.1f}%{at_edge}")

    # ── Save outputs ──
    all_records = []
    for c in candidates:
        if "fitness" not in c:
            continue
        S = c.get("fitness_decomposition", {})
        M = c.get("raw_metrics", {})
        rec = {
            "id": c["id"], "changed_param": c["changed_param"],
            "changed_value": c["changed_value"],
            "gene_hash": c.get("gene_hash", ""), "genes": c["genes"],
            "final_fitness": c["fitness"],
            "fitness_decomposition": S,
            "raw_metrics": M,
        }
        all_records.append(rec)

    with open(out_dir / "phase1c_results.json", "w") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False, default=str)

    # CSV
    csv_rows = []
    metric_keys = ["annual_return_pct", "total_return_pct", "max_drawdown_pct", "calmar_ratio",
                   "full_no_2024_pct", "val_no_2024_pct",
                   "ret_2019", "ret_2020", "ret_2021", "ret_2022", "ret_2023", "ret_2024",
                   "dd_2018", "dd_2022",
                   "failed_entry_rate", "annual_turnover", "max_year_profit_pct",
                   "total_trades", "train_calmar", "val_calmar"]
    for rec in all_records:
        row = {
            "id": rec["id"], "changed_param": rec["changed_param"],
            "changed_value": rec["changed_value"], "gene_hash": rec["gene_hash"],
            "final_fitness": rec["final_fitness"],
        }
        S = rec["fitness_decomposition"]; M = rec["raw_metrics"]
        row.update({f"gene_{k}": v for k, v in rec["genes"].items()})
        row.update({k: v for k, v in S.items() if k != "final_fitness"})
        for k in metric_keys:
            row[k] = M.get(k, "")
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(out_dir / "phase1c_results.csv", index=False)

    # Sensitivity CSV
    sens_df = pd.DataFrame(sensitivity_rows)
    sens_df = sens_df.sort_values("sensitivity", ascending=False)
    sens_df.to_csv(out_dir / "parameter_sensitivity.csv", index=False)
    logger.info(f"\nParameter sensitivity:")
    for _, row in sens_df.iterrows():
        flags = ""
        if row["at_lower_boundary"]:
            flags += " ⚠LOWER"
        if row["at_upper_boundary"]:
            flags += " ⚠UPPER"
        logger.info(f"  {row['param']}: sensitivity={row['sensitivity']:+.3f} "
                    f"(best={row['best_value']} fit={row['best_fitness']:.3f}){flags}")

    # config
    config = {"mode": "local_search_phase1c", "seed": seed, "n_workers": n_workers,
              "data_md5": "c79f9f1649895c897af28961e5d3c1fb",
              "baseline_fitness": bl["fitness"], "baseline_hash": bl_hash,
              "total_candidates": total, "evaluated": evaluated, "cache_hits": cache_hits,
              "score_high_range": PHASE1C_SWEEP["score_high"],
              "support_bear_range": PHASE1C_SWEEP["support_bear"]}
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # report.md
    report_lines = [
        f"# Local Search Phase 1c Report",
        f"",
        f"**Date**: {ts}",
        f"**Config**: score_high={PHASE1C_SWEEP['score_high']}, support_bear={PHASE1C_SWEEP['support_bear']}",
        f"**Workers**: {n_workers}, seed={seed}",
        f"**Baseline fitness**: {bl['fitness']:.3f}",
        f"",
        f"## score_high Expansion Trend",
        f"",
        f"| Value | Fitness | Ret% | Trades | No24% | DD22% | R19% | R20% | Edge? |",
        f"|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    sh_sorted = sorted(sh_cands, key=lambda c: c["changed_value"])
    top_sh = max(sh_cands, key=lambda c: c["fitness"]) if sh_cands else None
    for c in sh_sorted:
        M = c.get("raw_metrics", {})
        edge = ""
        if top_sh and c["changed_value"] == top_sh["changed_value"] and c["changed_value"] == PHASE1C_SWEEP["score_high"][-1]:
            edge = "⚠ UPPER"
        report_lines.append(
            f"| {c['changed_value']:.2f} | {c['fitness']:.3f} | {M.get('annual_return_pct',0):.1f} | "
            f"{M.get('total_trades',0)} | {M.get('full_no_2024_pct',0):.1f} | "
            f"{M.get('dd_2022',0):.1f} | {M.get('ret_2019',0):+.1f} | {M.get('ret_2020',0):+.1f} | {edge} |"
        )

    report_lines += [
        f"",
        f"## support_bear Deep Probe",
        f"",
        f"| Value | Fitness | Ret% | Trades | No24% | DD22% | R19% | R20% | Edge? |",
        f"|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    sb_cands = sorted(
        [c for c in candidates if c["changed_param"] == "support_bear" and c.get("fitness")],
        key=lambda c: c["changed_value"]
    )
    top_sb = max(sb_cands, key=lambda c: c["fitness"]) if sb_cands else None
    for c in sb_cands:
        M = c.get("raw_metrics", {})
        edge = ""
        if top_sb and c["changed_value"] == top_sb["changed_value"] and c["changed_value"] == PHASE1C_SWEEP["support_bear"][0]:
            edge = "⚠ LOWER"
        report_lines.append(
            f"| {c['changed_value']:.0f} | {c['fitness']:.3f} | {M.get('annual_return_pct',0):.1f} | "
            f"{M.get('total_trades',0)} | {M.get('full_no_2024_pct',0):.1f} | "
            f"{M.get('dd_2022',0):.1f} | {M.get('ret_2019',0):+.1f} | {M.get('ret_2020',0):+.1f} | {edge} |"
        )

    report_lines += [
        f"",
        f"## Best vs Baseline",
        f"",
    ]
    if best_overall["id"] != "baseline":
        report_lines.append(f"Best candidate **{best_overall['id']}** exceeds baseline by **{delta:+.3f}**.")
        S_b = bl.get("fitness_decomposition", {})
        S_x = best_overall.get("fitness_decomposition", {})
        for comp_name, key in [("Calmar", "calmar_score"), ("No_2024", "no_2024_score"),
                                ("Recovery", "recovery_score"), ("Bear penalty", "bear_penalty"),
                                ("FER penalty", "failed_entry_penalty"),
                                ("Turnover penalty", "turnover_penalty"),
                                ("Dependency penalty", "dependency_penalty")]:
            bv = S_b.get(key, 0); xv = S_x.get(key, 0)
            report_lines.append(f"- **{comp_name}**: baseline {bv:.3f} → best {xv:.3f} (Δ {xv-bv:+.3f})")

    report_lines += [
        f"",
        f"## Conclusion",
        f"",
    ]
    if top_sh and top_sh["changed_value"] == PHASE1C_SWEEP["score_high"][-1]:
        report_lines.append(f"**score_high** still improving at upper boundary ({PHASE1C_SWEEP['score_high'][-1]}). "
                           f"Strong signal: continue expansion beyond {PHASE1C_SWEEP['score_high'][-1]}.")
    else:
        report_lines.append(f"**score_high** optimum found at {top_sh['changed_value']}.")

    if top_sb and top_sb["changed_value"] == PHASE1C_SWEEP["support_bear"][0]:
        report_lines.append(f"**support_bear** still improving at lower boundary ({PHASE1C_SWEEP['support_bear'][0]}).")
    else:
        report_lines.append(f"**support_bear** optimum found at {top_sb['changed_value']}.")

    with open(out_dir / "report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    logger.info(f"\nSaved to {out_dir}")
    return out_dir


# ═══════════════════════════════════════════════════════════════════
# Phase 2-mini: Top 3 params small 3D grid
# ═══════════════════════════════════════════════════════════════════

PHASE2MINI_GRID = {
    "score_high":    [0.78, 0.80, 0.82],
    "breakout_bear": [30.0, 35.0, 40.0],
    "atr_bear":      [0.65, 0.75, 0.89],
}


def run_local_phase2mini(n_workers=4, seed=42):
    """Phase 2-mini: 3x3x3 grid on top 3 parameters."""
    setup_file_log()
    random.seed(seed)
    np.random.seed(seed)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "ga_results" / f"local_search_phase2mini_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("PHASE 2-MINI: 3D Grid on Top 3 Parameters")
    logger.info(f"  grid: {PHASE2MINI_GRID}")
    logger.info(f"  total combinations: 3x3x3 = 27")
    logger.info(f"  workers={n_workers}  seed={seed}")
    logger.info(f"  output: {out_dir}")
    logger.info("=" * 60)

    # Preload baseline
    logger.info("Preloading baseline into cache...")
    t0t = time.time()
    bl_hash = preload_cache(BASELINE_GENES)
    logger.info(f"  baseline cached (hash={bl_hash}, {time.time()-t0t:.0f}s)")

    # Generate full 3D grid
    seen_hashes = {bl_hash}
    candidates = [{"id": "baseline", "genes": BASELINE_GENES.copy()}]

    sh_vals = PHASE2MINI_GRID["score_high"]
    bb_vals = PHASE2MINI_GRID["breakout_bear"]
    ab_vals = PHASE2MINI_GRID["atr_bear"]
    total_combos = len(sh_vals) * len(bb_vals) * len(ab_vals)

    for sh in sh_vals:
        for bb in bb_vals:
            for ab in ab_vals:
                genes = BASELINE_GENES.copy()
                genes["score_high"] = sh
                genes["breakout_bear"] = bb
                genes["atr_bear"] = ab
                gh = compute_gene_hash(genes)
                if gh not in seen_hashes:
                    seen_hashes.add(gh)
                    candidates.append({
                        "id": f"sh{sh}_bb{bb}_ab{ab}",
                        "genes": genes,
                        "score_high": sh, "breakout_bear": bb, "atr_bear": ab,
                    })

    total = len(candidates)
    dup_count = total_combos + 1 - total
    logger.info(f"\nCandidates: {total} total ({total_combos} grid + 1 baseline, {dup_count} duplicates skipped)")

    # Evaluate
    sweep = [c for c in candidates if c["id"] != "baseline"]
    cache_hits = 0
    evaluated = 0

    logger.info(f"Evaluating {len(sweep)} candidates ({n_workers} workers)...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(cached_evaluate, c["genes"]): c for c in sweep}
        for future in as_completed(futures):
            c = futures[future]
            try:
                fitness, metrics_dict, gh, was_cached = future.result()
            except Exception as e:
                logger.error(f"  {c['id']} FAILED: {e}")
                fitness = {"final_fitness": -99.0, "raw": {}, "calmar_score": 0, "no_2024_score": 0,
                           "recovery_score": 0, "bear_penalty": 0, "failed_entry_penalty": 0,
                           "turnover_penalty": 0, "dependency_penalty": 0}
                metrics_dict = {"train": {}, "val": {}, "full": {}}
                gh = "FAILED"; was_cached = False
            c["fitness"] = fitness["final_fitness"]
            c["fitness_decomposition"] = {k: v for k, v in fitness.items() if k != "raw"}
            c["raw_metrics"] = fitness["raw"]
            c["gene_hash"] = gh
            if was_cached:
                cache_hits += 1
            else:
                evaluated += 1
            # Augment with full-metrics data
            fm = metrics_dict.get("full", {})
            rm = c["raw_metrics"]
            if "total_return_pct" not in rm and "total_return_pct" in fm:
                rm["total_return_pct"] = fm["total_return_pct"]
            if "max_drawdown_pct" not in rm and "max_drawdown_pct" in fm:
                rm["max_drawdown_pct"] = fm["max_drawdown_pct"]
            S = fitness; M = rm
            tag = " [CACHE]" if was_cached else ""
            logger.info(f"  {c['id']}: fitness={S['final_fitness']:.3f} "
                        f"cal={S['calmar_score']:.3f} no24={S['no_2024_score']:.3f} "
                        f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)}{tag}")
    elapsed = time.time() - t0
    logger.info(f"  Evaluation done in {elapsed:.0f}s "
                f"(evaluated={evaluated} cache_hits={cache_hits})")

    # Attach baseline
    bl_cached = _EVAL_CACHE[bl_hash]
    bl = candidates[0]
    bl["fitness"] = bl_cached["fitness"]["final_fitness"]
    bl["fitness_decomposition"] = {k: v for k, v in bl_cached["fitness"].items() if k != "raw"}
    bl["raw_metrics"] = bl_cached["fitness"]["raw"]
    bl["gene_hash"] = bl_hash
    # Add grid params to baseline
    bl["score_high"] = BASELINE_GENES["score_high"]
    bl["breakout_bear"] = BASELINE_GENES["breakout_bear"]
    bl["atr_bear"] = BASELINE_GENES["atr_bear"]

    # ── Summary ──
    logger.info(f"\n{'='*60}")
    logger.info("PHASE 2-MINI RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Baseline fitness: {bl['fitness']:.3f}")

    all_valid = [c for c in candidates if "fitness" in c]
    sorted_all = sorted(all_valid, key=lambda c: c["fitness"], reverse=True)
    best_overall = sorted_all[0]
    delta = best_overall["fitness"] - bl["fitness"]
    sh_best = None
    # Best single-param score_high=0.80 reference
    sh_best = next((c for c in all_valid if c.get("score_high") == 0.80
                    and c.get("breakout_bear") == 40.0 and c.get("atr_bear") == 1.19), None)
    if sh_best:
        logger.info(f"Single-param best (sh=0.80): fitness={sh_best['fitness']:.3f}")
    logger.info(f"Best overall: {best_overall['id']} fitness={best_overall['fitness']:.3f} (Δ={delta:+.3f})")
    if sh_best and best_overall["fitness"] > sh_best["fitness"]:
        delta_sh = best_overall["fitness"] - sh_best["fitness"]
        logger.info(f"  vs single-param best: Δ={delta_sh:+.3f}")

    # Top 15
    logger.info(f"\nTop 15:")
    for rank, c in enumerate(sorted_all[:15]):
        S = c.get("fitness_decomposition", {}); M = c.get("raw_metrics", {})
        logger.info(f"  #{rank+1} {c['id']}: fitness={c['fitness']:.3f} "
                    f"cal={S.get('calmar_score',0):.3f} no24={S.get('no_2024_score',0):.3f} "
                    f"ret={M.get('annual_return_pct',0):.1f}% trades={M.get('total_trades',0)} "
                    f"dd22={M.get('dd_2022',0):.1f}% r19={M.get('ret_2019',0):+.1f}% r20={M.get('ret_2020',0):+.1f}%")

    # Quality checks
    bl_ret = bl["raw_metrics"].get("annual_return_pct", 7.8)
    bl_trades = bl["raw_metrics"].get("total_trades", 1231)
    for c in sorted_all[:5]:
        if c["id"] == "baseline":
            continue
        M = c.get("raw_metrics", {})
        trades = M.get("total_trades", 0)
        ret = M.get("annual_return_pct", 0)
        if ret < bl_ret * 0.9:
            logger.warning(f"  ⚠ Return drop: {c['id']} ret={ret:.1f}% (< {bl_ret*0.9:.1f}%)")
        if trades < bl_trades * 0.5:
            logger.warning(f"  ⚠ Trades collapse: {c['id']} trades={trades}")
        if trades > bl_trades * 2:
            logger.warning(f"  ⚠ Trades spike: {c['id']} trades={trades}")

    # ── Save outputs ──
    all_records = []
    for c in candidates:
        if "fitness" not in c:
            continue
        S = c.get("fitness_decomposition", {})
        M = c.get("raw_metrics", {})
        rec = {
            "id": c["id"],
            "score_high": c.get("score_high"),
            "breakout_bear": c.get("breakout_bear"),
            "atr_bear": c.get("atr_bear"),
            "gene_hash": c.get("gene_hash", ""),
            "genes": c["genes"],
            "final_fitness": c["fitness"],
            "fitness_decomposition": S,
            "raw_metrics": M,
        }
        all_records.append(rec)

    with open(out_dir / "phase2mini_results.json", "w") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False, default=str)

    # CSV
    metric_keys = [
        "annual_return_pct", "total_return_pct", "max_drawdown_pct", "calmar_ratio",
        "full_no_2024_pct", "val_no_2024_pct",
        "ret_2018", "ret_2019", "ret_2020", "ret_2021", "ret_2022", "ret_2023", "ret_2024",
        "dd_2018", "dd_2019", "dd_2020", "dd_2021", "dd_2022", "dd_2023", "dd_2024",
        "failed_entry_rate", "annual_turnover", "max_year_profit_pct",
        "total_trades", "exposure", "avg_position",
        "train_calmar", "val_calmar",
    ]
    csv_rows = []
    for rec in all_records:
        row = {
            "id": rec["id"],
            "score_high": rec["score_high"], "breakout_bear": rec["breakout_bear"],
            "atr_bear": rec["atr_bear"], "gene_hash": rec["gene_hash"],
            "final_fitness": rec["final_fitness"],
        }
        S = rec["fitness_decomposition"]; M = rec["raw_metrics"]
        row.update({f"gene_{k}": v for k, v in rec["genes"].items()})
        row.update({k: v for k, v in S.items() if k != "final_fitness"})
        for k in metric_keys:
            row[k] = M.get(k, "")
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(out_dir / "phase2mini_results.csv", index=False)

    # Top candidates
    top_candidates = sorted_all[:10]
    top_out = []
    for c in top_candidates:
        S = c.get("fitness_decomposition", {})
        M = c.get("raw_metrics", {})
        top_out.append({
            "id": c["id"],
            "score_high": c.get("score_high"), "breakout_bear": c.get("breakout_bear"),
            "atr_bear": c.get("atr_bear"),
            "fitness": c["fitness"],
            "calmar_score": S.get("calmar_score", 0),
            "no_2024_score": S.get("no_2024_score", 0),
            "recovery_score": S.get("recovery_score", 0),
            "bear_penalty": S.get("bear_penalty", 0),
            "dependency_penalty": S.get("dependency_penalty", 0),
            "annual_return_pct": M.get("annual_return_pct", 0),
            "total_trades": M.get("total_trades", 0),
            "full_no_2024_pct": M.get("full_no_2024_pct", 0),
            "dd_2022": M.get("dd_2022", 0),
        })
    with open(out_dir / "top_candidates.json", "w") as f:
        json.dump(top_out, f, indent=2)

    # config
    config = {"mode": "local_search_phase2mini", "seed": seed, "n_workers": n_workers,
              "data_md5": "c79f9f1649895c897af28961e5d3c1fb",
              "baseline_fitness": bl["fitness"], "baseline_hash": bl_hash,
              "grid": PHASE2MINI_GRID,
              "total_grid_combos": total_combos, "total_evaluated": total,
              "evaluated_new": evaluated, "cache_hits": cache_hits}
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # report.md
    report_lines = [
        f"# Phase 2-Mini Report",
        f"",
        f"**Date**: {ts}",
        f"**Grid**: score_high={sh_vals}, breakout_bear={bb_vals}, atr_bear={ab_vals}",
        f"**Total**: {total_combos} combinations, {evaluated} evaluated, {cache_hits} cache hits",
        f"**Baseline fitness**: {bl['fitness']:.3f}",
        f"",
        f"## Top 10",
        f"",
        f"| Rank | ID | sh | bb | ab | Fitness | Calmar | No24 | Ret% | Trades | DD22% | R19% | R20% |",
        f"|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for rank, c in enumerate(sorted_all[:10]):
        M = c.get("raw_metrics", {})
        report_lines.append(
            f"| {rank+1} | {c['id']} | {c.get('score_high','')} | {c.get('breakout_bear','')} | "
            f"{c.get('atr_bear','')} | {c['fitness']:.3f} | "
            f"{c.get('fitness_decomposition',{}).get('calmar_score',0):.3f} | "
            f"{c.get('fitness_decomposition',{}).get('no_2024_score',0):.3f} | "
            f"{M.get('annual_return_pct',0):.1f} | {M.get('total_trades',0)} | "
            f"{M.get('dd_2022',0):.1f} | {M.get('ret_2019',0):+.1f} | {M.get('ret_2020',0):+.1f} |"
        )

    report_lines += [
        f"",
        f"## Best vs Baseline",
        f"",
    ]
    if best_overall["id"] != "baseline":
        report_lines.append(f"Best candidate **{best_overall['id']}** exceeds baseline by **{delta:+.3f}**.")
        S_b = bl.get("fitness_decomposition", {})
        S_x = best_overall.get("fitness_decomposition", {})
        for comp_name, key in [("Calmar", "calmar_score"), ("No_2024", "no_2024_score"),
                                ("Recovery", "recovery_score"), ("Bear penalty", "bear_penalty"),
                                ("FER penalty", "failed_entry_penalty"),
                                ("Turnover penalty", "turnover_penalty"),
                                ("Dependency penalty", "dependency_penalty")]:
            bv = S_b.get(key, 0); xv = S_x.get(key, 0)
            report_lines.append(f"- **{comp_name}**: baseline {bv:.3f} → best {xv:.3f} (Δ {xv-bv:+.3f})")

        if sh_best and best_overall["fitness"] > sh_best["fitness"]:
            report_lines.append(f"")
            report_lines.append(f"Exceeds single-param best (sh=0.80, fitness={sh_best['fitness']:.3f}) "
                               f"by **{best_overall['fitness']-sh_best['fitness']:+.3f}**.")
    else:
        report_lines.append(f"No candidate exceeded baseline.")

    report_lines += [
        f"",
        f"## Quality Check",
        f"",
    ]
    report_lines.append(f"- Baseline annual_return: {bl_ret:.1f}%")
    for c in sorted_all[:5]:
        if c["id"] == "baseline":
            continue
        M = c.get("raw_metrics", {})
        ret = M.get("annual_return_pct", 0)
        trades = M.get("total_trades", 0)
        notes = []
        if ret < bl_ret * 0.9:
            notes.append(f"return {ret:.1f}% < {bl_ret*0.9:.1f}%")
        if trades < bl_trades * 0.5:
            notes.append(f"trades collapse {trades}")
        if trades > bl_trades * 2:
            notes.append(f"trades spike {trades}")
        report_lines.append(f"- {c['id']}: ret={ret:.1f}% trades={trades} {'⚠ ' + ', '.join(notes) if notes else '✓'}")

    report_lines += [
        f"",
        f"## Conclusion",
        f"",
    ]
    if best_overall["fitness"] > bl["fitness"] + 0.03:
        report_lines.append(f"Phase 2-mini found improvement over baseline (+{delta:+.3f}).")
        if sh_best and best_overall["fitness"] > sh_best["fitness"] + 0.03:
            report_lines.append(f"Multi-parameter combination exceeds single-parameter optimum. "
                               f"Worth further grid refinement.")
        else:
            report_lines.append(f"Multi-parameter combination did not significantly exceed single-parameter optimum. "
                               f"Single-parameter tuning may be sufficient.")
    else:
        report_lines.append(f"No significant improvement found.")

    with open(out_dir / "report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    logger.info(f"\nSaved to {out_dir}")
    return out_dir


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--local-phase1", action="store_true")
    parser.add_argument("--local-phase1b", action="store_true")
    parser.add_argument("--local-phase1c", action="store_true")
    parser.add_argument("--local-phase2mini", action="store_true")
    parser.add_argument("--pop", type=int, default=12)
    parser.add_argument("--gen", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.pilot:
        run_pilot(pop_size=args.pop, n_generations=args.gen,
                  n_workers=args.workers, seed=args.seed)
        return

    if args.local_phase1:
        run_local_phase1(n_workers=args.workers, seed=args.seed)
        return

    if args.local_phase1b:
        run_local_phase1b(n_workers=args.workers, seed=args.seed)
        return

    if args.local_phase1c:
        run_local_phase1c(n_workers=args.workers, seed=args.seed)
        return

    if args.local_phase2mini:
        run_local_phase2mini(n_workers=args.workers, seed=args.seed)
        return

    setup_file_log()

    random.seed(args.seed)
    np.random.seed(args.seed)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "ga_results" / f"v2_smoke_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.baseline_only:
        logger.info(f"GA v2 — Baseline Control Only")
        logger.info(f"  seed={args.seed}")
    else:
        logger.info(f"GA Optimizer v2 Smoke Test")
        logger.info(f"  pop=4, gen=1, seed={args.seed}, serial")
    logger.info(f"  output: {out_dir}")

    # Build population
    candidates = [{"id": "baseline", "genes": BASELINE_GENES.copy()}]
    n_random = 0 if args.baseline_only else 3
    for i in range(1, n_random + 1):
        genes = {}
        for name, (lo, hi, step, is_int) in PARAM_BOUNDS.items():
            if is_int:
                genes[name] = float(random.randint(int(lo), int(hi)))
            else:
                genes[name] = round(random.uniform(lo, hi), 2)
        candidates.append({"id": f"random_{i}", "genes": genes})

    results = []
    for c in candidates:
        logger.info(f"Evaluating {c['id']}...")
        t0 = time.time()
        fitness, metrics_dict = evaluate_candidate(c["genes"])
        elapsed = time.time() - t0
        S = fitness
        M = S["raw"]
        logger.info(f"  {c['id']}: fitness={S['final_fitness']:.3f} "
                     f"cal={S['calmar_score']:.3f} no24={S['no_2024_score']:.3f} "
                     f"rec={S['recovery_score']:.3f} "
                     f"ret={M['annual_return_pct']:.1f}% trades={M['total_trades']} ({elapsed:.0f}s)")

        record = {
            "id": c["id"],
            "genes": c["genes"],
            "fitness": S["final_fitness"],
            "fitness_decomposition": {k: v for k, v in S.items() if k != "raw"},
            "raw_metrics": M,
            "seed": args.seed,
            "run_ts": ts,
        }
        results.append(record)

    # Re-log cleanly
    logger.info("\n" + "="*60)
    logger.info("SMOKE RESULTS")
    logger.info("="*60)
    for r in sorted(results, key=lambda x: -x["fitness"]):
        S = r["fitness_decomposition"]; M = r["raw_metrics"]
        logger.info(f"\n{r['id']}: fitness={r['fitness']:.3f}")
        logger.info(f"  calmar={S['calmar_score']:.3f}  no24={S['no_2024_score']:.3f}  "
                     f"rec={S['recovery_score']:.3f}")
        logger.info(f"  bear_raw={S['bear_penalty']:.3f} contrib={-0.5*S['bear_penalty']:.3f}  "
                     f"fer_raw={S['failed_entry_penalty']:.3f} contrib={-0.3*S['failed_entry_penalty']:.3f}")
        logger.info(f"  to_raw={S['turnover_penalty']:.3f} contrib={-0.2*S['turnover_penalty']:.3f}  "
                     f"dep_raw={S['dependency_penalty']:.3f} contrib={-0.5*S['dependency_penalty']:.3f}")
        logger.info(f"  ret={M['annual_return_pct']:.1f}% trades={M['total_trades']} "
                     f"no24={M['full_no_2024_pct']:.1f}% "
                     f"2019={M['ret_2019']:+.1f}% 2020={M['ret_2020']:+.1f}%")

    # Find baseline
    bl = next(r for r in results if r["id"] == "baseline")
    logger.info(f"\nBaseline fitness: {bl['fitness']:.3f} (expected ~1.656)")

    # Save
    with open(out_dir / "candidates.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    config = {"seed": args.seed, "pop": 4, "gen": 1, "data_md5": "c79f9f1649895c897af28961e5d3c1fb"}
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()
