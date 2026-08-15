#!/usr/bin/env python3
"""运行 origin vadd 的 cache MSHR 数量扫描并汇总 ROI。"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RUN_GEM5 = ROOT_DIR / "scripts" / "run_gem5.py"
DEFAULT_GEM5 = (
    ROOT_DIR / "tools" / "gem5" / "build" / "RISCV" / "gem5.opt"
)
DEFAULT_BENCHMARK = ROOT_DIR / "build" / "vadd_N1024.riscv"
STAT_KEYS = {
    "cycles": "system.cpu.numCycles",
    "ipc": "system.cpu.ipc",
    "l1d_misses": "system.cpu.dcache.overallMisses::total",
    "l2_misses": "system.l2cache.overallMisses::total",
    "l1d_mshr_hits": "system.cpu.dcache.overallMshrHits::total",
    "l1d_mshr_misses": "system.cpu.dcache.overallMshrMisses::total",
    "l1d_blocked_no_mshrs": "system.cpu.dcache.blockedCycles::no_mshrs",
    "l1d_blocked_no_targets": "system.cpu.dcache.blockedCycles::no_targets",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5-bin", default=str(DEFAULT_GEM5))
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--values", default="1,2,4,8,16,32")
    parser.add_argument("--targets-per-mshr", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT_DIR / "results" / "vadd_N1024_mshr_sweep"),
    )
    return parser.parse_args()


def parse_values(raw):
    values = []
    for item in raw.split(","):
        value = int(item.strip())
        if value <= 0:
            raise ValueError("MSHR values must be positive")
        if value not in values:
            values.append(value)
    if not values:
        raise ValueError("at least one MSHR value is required")
    return values


def parse_first_stats(path):
    stats = {}
    in_block = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "Begin Simulation Statistics" in line:
            in_block = True
            continue
        if "End Simulation Statistics" in line and in_block:
            break
        if not in_block:
            continue
        fields = line.split()
        if len(fields) >= 2:
            stats[fields[0]] = fields[1]
    return stats


def run_point(args, output_dir, mshrs):
    result_name = f"mshr_{mshrs}_targets_{args.targets_per_mshr}"
    cmd = [
        sys.executable,
        str(RUN_GEM5),
        "--gem5-bin",
        str(Path(args.gem5_bin).resolve()),
        "--benchmark",
        str(Path(args.benchmark).resolve()),
        "--bench-name",
        output_dir.name,
        "--results-dir",
        str(output_dir.parent),
        "--result-name",
        result_name,
        "--config",
        "o3_zircon_width_nopf",
        "--cache-mshrs",
        str(mshrs),
        "--cache-targets-per-mshr",
        str(args.targets_per_mshr),
    ]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)

    stats = parse_first_stats(output_dir / result_name / "stats.txt")
    row = {
        "mshrs": mshrs,
        "targets_per_mshr": args.targets_per_mshr,
        "result_dir": result_name,
    }
    for column, key in STAT_KEYS.items():
        row[column] = stats.get(key, "")
    return row


def add_improvements(rows):
    first_cycles = int(rows[0]["cycles"])
    previous_cycles = None
    for row in rows:
        cycles = int(row["cycles"])
        row["speedup_vs_mshr1"] = f"{first_cycles / cycles:.6f}"
        row["reduction_vs_mshr1_pct"] = (
            f"{(first_cycles - cycles) / first_cycles * 100:.6f}"
        )
        row["reduction_vs_previous_pct"] = (
            ""
            if previous_cycles is None
            else f"{(previous_cycles - cycles) / previous_cycles * 100:.6f}"
        )
        previous_cycles = cycles


def write_summary(path, rows):
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    values = parse_values(args.values)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = [run_point(args, output_dir, mshrs) for mshrs in values]
    add_improvements(rows)
    summary = output_dir / f"mshr_sweep_targets_{args.targets_per_mshr}.csv"
    write_summary(summary, rows)
    print(f"wrote {summary}")
    for row in rows:
        step_reduction = row["reduction_vs_previous_pct"]
        step_text = f"{step_reduction}%" if step_reduction else "-"
        print(
            f"MSHR={row['mshrs']:>2}: cycles={row['cycles']}, "
            f"step_reduction={step_text}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
