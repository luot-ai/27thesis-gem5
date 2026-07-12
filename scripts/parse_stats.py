#!/usr/bin/env python3
"""Parse a small, stable subset of gem5 stats into CSV."""

import argparse
import csv
from pathlib import Path


FIELDS = [
    ("simInsts", "simInsts"),
    ("simTicks", "simTicks"),
    ("finalTick", "finalTick"),
    ("hostSeconds", "hostSeconds"),
    ("numCycles", "system.cpu.numCycles"),
    ("ipc", "system.cpu.ipc"),
    ("cpi", "system.cpu.cpi"),
    ("committedInsts", "system.cpu.commitStats0.numInsts"),
    ("committedInstsNotNOP", "system.cpu.commitStats0.numInstsNotNOP"),
    ("l1d_overall_misses", "system.cpu.dcache.overallMisses::total"),
    ("l1d_overall_miss_rate", "system.cpu.dcache.overallMissRate::total"),
    ("l1i_overall_misses", "system.cpu.icache.overallMisses::total"),
    ("l1i_overall_miss_rate", "system.cpu.icache.overallMissRate::total"),
    ("l2_overall_misses", "system.l2cache.overallMisses::total"),
    ("l2_overall_miss_rate", "system.l2cache.overallMissRate::total"),
    ("l3_overall_misses", "system.l3cache.overallMisses::total"),
    ("l3_overall_miss_rate", "system.l3cache.overallMissRate::total"),
    ("prefetch_issued", "system.cpu.dcache.prefetcher.pfIssued"),
    ("prefetch_useful", "system.cpu.dcache.prefetcher.pfUseful"),
    ("prefetch_unused", "system.cpu.dcache.prefetcher.pfUnused"),
    ("prefetch_accuracy", "system.cpu.dcache.prefetcher.accuracy"),
    ("prefetch_coverage", "system.cpu.dcache.prefetcher.coverage"),
    ("prefetch_late", "system.cpu.dcache.prefetcher.pfLate"),
    ("l2_prefetch_issued", "system.l2cache.prefetcher.pfIssued"),
    ("l2_prefetch_useful", "system.l2cache.prefetcher.pfUseful"),
    ("l2_prefetch_unused", "system.l2cache.prefetcher.pfUnused"),
    ("l2_prefetch_accuracy", "system.l2cache.prefetcher.accuracy"),
    ("l2_prefetch_coverage", "system.l2cache.prefetcher.coverage"),
    ("l2_prefetch_late", "system.l2cache.prefetcher.pfLate"),
    ("l3_prefetch_issued", "system.l3cache.prefetcher.pfIssued"),
    ("l3_prefetch_useful", "system.l3cache.prefetcher.pfUseful"),
    ("l3_prefetch_unused", "system.l3cache.prefetcher.pfUnused"),
    ("l3_prefetch_accuracy", "system.l3cache.prefetcher.accuracy"),
    ("l3_prefetch_coverage", "system.l3cache.prefetcher.coverage"),
    ("l3_prefetch_late", "system.l3cache.prefetcher.pfLate"),
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--stat-block",
        choices=("first", "last"),
        default="first",
        help=(
            "Which statistics block to parse when stats.txt contains ROI "
            "dump/reset sections. The first block is the ROI block for the "
            "current benchmarks."
        ),
    )
    return parser.parse_args()


def parse_stats_file(path: Path, stat_block: str):
    blocks = []
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if "Begin Simulation Statistics" in stripped:
            current = {}
            continue
        if "End Simulation Statistics" in stripped:
            if current is not None:
                blocks.append(current)
                current = None
            continue
        if current is None:
            continue
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        key, value = parts[0], parts[1]
        current[key] = value
    if not blocks:
        return {}
    return blocks[0] if stat_block == "first" else blocks[-1]


def row_for_stats(stats_path: Path, results_dir: Path, stat_block: str):
    rel = stats_path.relative_to(results_dir)
    bench = rel.parts[0] if len(rel.parts) >= 3 else ""
    config = rel.parts[1] if len(rel.parts) >= 3 else ""
    stats = parse_stats_file(stats_path, stat_block)
    row = {
        "benchmark": bench,
        "config": config,
        "stats_path": str(stats_path),
    }
    for column, gem5_key in FIELDS:
        row[column] = stats.get(gem5_key, "")
    return row


def main():
    args = parse_args()
    results_dir = Path(args.results_dir).resolve()
    output = Path(args.output).resolve() if args.output else results_dir / "summary.csv"

    rows = [
        row_for_stats(path, results_dir, args.stat_block)
        for path in sorted(results_dir.glob("*/*/stats.txt"))
    ]

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["benchmark", "config", "stats_path"] + [name for name, _ in FIELDS]
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {output} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
