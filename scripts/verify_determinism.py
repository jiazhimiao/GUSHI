"""Verify determinism: run A 3 times in separate processes, compare results."""
import subprocess, json, sys
from pathlib import Path
ROOT = Path("D:/Trae_pro/cc/gushi")

results = []
for i in range(1, 4):
    print(f"\n=== Run {i}/3 ===")
    r = subprocess.run(
        [sys.executable, "scripts/experiment_matrix.py", "--experiment", "A"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    # Find the latest A.json
    exp_dirs = sorted((ROOT / "data" / "experiments").glob("experiment_matrix_*"))
    latest = exp_dirs[-1]
    with open(latest / "A.json") as f:
        rec = json.load(f)
    m = rec["metrics"]
    results.append(m)
    print(f"  total_return={m['total_return_pct']:.1f}%  trades={m['total_trades']}  "
          f"dd={m['max_drawdown_pct']:.1f}%  calmar={m['calmar']}  "
          f"exp={m['exposure']}%  avg_pos={m['avg_position']}%")

print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
keys = ["total_return_pct", "annual_return_pct", "max_drawdown_pct",
        "calmar", "total_trades", "exposure", "avg_position"]
for k in keys:
    vals = [r[k] for r in results]
    unique = len(set(str(round(v, 6)) for v in vals))
    status = "IDENTICAL" if unique == 1 else f"DIFFER ({unique} values: {vals})"
    print(f"  {k}: {status}")

print("\n=== CONCLUSION ===")
all_identical = all(
    len(set(str(round(r[k], 6)) for r in results)) == 1
    for k in keys
)
if all_identical:
    print("ALL METRICS IDENTICAL — deterministic baseline confirmed.")
else:
    print("DIFFERENCES FOUND — determinism not achieved.")
    sys.exit(1)
