#!/usr/bin/env python3
"""Run one benchmark with the project gem5 baseline config."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_SCRIPT = ROOT_DIR / "gem5_configs" / "riscv_o3_baseline.py"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5-bin", required=True, help="Path to gem5.opt")
    parser.add_argument(
        "--benchmark",
        required=True,
        help="Path to RISC-V benchmark binary",
    )
    parser.add_argument(
        "--bench-name",
        required=True,
        help="Name used under results/, e.g. vadd_N1024",
    )
    parser.add_argument(
        "--config",
        choices=("o3_nopf", "o3_stridepf"),
        default="o3_nopf",
        help="Baseline config to pass to the gem5 config script",
    )
    parser.add_argument(
        "--profile",
        default="medium_boom_like",
        help="BOOM-like profile name",
    )
    parser.add_argument(
        "--results-dir",
        default=str(ROOT_DIR / "results"),
        help="Top-level results directory",
    )
    parser.add_argument(
        "--config-script",
        default=str(DEFAULT_CONFIG_SCRIPT),
        help="gem5 Python config script",
    )
    parser.add_argument(
        "--gem5-arg",
        action="append",
        default=[],
        help="Extra argument passed before the gem5 config script",
    )
    parser.add_argument(
        "--bench-arg",
        action="append",
        default=[],
        help="Extra argument passed to the benchmark",
    )
    parser.add_argument("--mem-size", default="512MiB")
    parser.add_argument("--cache-line-size", type=int, default=64)
    parser.add_argument("--sys-clock", default="1GHz")
    parser.add_argument("--cpu-clock", default="2GHz")
    parser.add_argument("--stridepf-degree", type=int, default=4)
    parser.add_argument("--stridepf-latency", type=int, default=1)
    parser.add_argument("--stridepf-on-access", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print and record the command without executing gem5",
    )
    return parser.parse_args()


def require_file(path: Path, label: str):
    if not path.is_file():
        raise SystemExit(f"error: {label} not found: {path}")


def build_command(args, outdir: Path):
    gem5_bin = Path(args.gem5_bin).resolve()
    benchmark = Path(args.benchmark).resolve()
    config_script = Path(args.config_script).resolve()

    cmd = [
        str(gem5_bin),
        f"--outdir={outdir}",
        *args.gem5_arg,
        str(config_script),
        "--cmd",
        str(benchmark),
        "--config",
        args.config,
        "--profile",
        args.profile,
        "--mem-size",
        args.mem_size,
        "--cache-line-size",
        str(args.cache_line_size),
        "--sys-clock",
        args.sys_clock,
        "--cpu-clock",
        args.cpu_clock,
        "--stridepf-degree",
        str(args.stridepf_degree),
        "--stridepf-latency",
        str(args.stridepf_latency),
    ]
    if args.stridepf_on_access:
        cmd.append("--stridepf-on-access")
    if args.bench_arg:
        cmd.append("--options")
        cmd.extend(args.bench_arg)
    return cmd


def write_config_json(args, outdir: Path, cmd):
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bench_name": args.bench_name,
        "config": args.config,
        "profile": args.profile,
        "gem5_bin": str(Path(args.gem5_bin).resolve()),
        "benchmark": str(Path(args.benchmark).resolve()),
        "config_script": str(Path(args.config_script).resolve()),
        "results_dir": str(outdir),
        "command": cmd,
        "gem5_args": args.gem5_arg,
        "bench_args": args.bench_arg,
        "system": {
            "mem_size": args.mem_size,
            "cache_line_size": args.cache_line_size,
            "sys_clock": args.sys_clock,
            "cpu_clock": args.cpu_clock,
        },
        "stride_prefetcher": {
            "enabled": args.config == "o3_stridepf",
            "degree": args.stridepf_degree,
            "latency": args.stridepf_latency,
            "prefetch_on_access": args.stridepf_on_access,
        },
        "note": (
            "BOOM-like gem5 O3 baseline inspired by public BOOM configs; "
            "not a cycle-accurate BOOM reproduction."
        ),
    }
    with (outdir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def main():
    args = parse_args()
    gem5_bin = Path(args.gem5_bin).resolve()
    benchmark = Path(args.benchmark).resolve()
    config_script = Path(args.config_script).resolve()

    if args.dry_run and not gem5_bin.is_file():
        print(f"dry run: gem5 binary not found yet: {gem5_bin}", file=sys.stderr)
    else:
        require_file(gem5_bin, "gem5 binary")
    require_file(benchmark, "benchmark")
    require_file(config_script, "gem5 config script")

    outdir = Path(args.results_dir).resolve() / args.bench_name / args.config
    outdir.mkdir(parents=True, exist_ok=True)

    cmd = build_command(args, outdir)
    write_config_json(args, outdir, cmd)

    print(" ".join(cmd))
    if args.dry_run:
        print(f"dry run: wrote {outdir / 'config.json'}")
        return 0

    with (outdir / "simout").open("w", encoding="utf-8") as stdout, (
        outdir / "simerr"
    ).open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(cmd, cwd=ROOT_DIR, stdout=stdout, stderr=stderr)

    if completed.returncode != 0:
        print(
            f"gem5 failed with exit code {completed.returncode}; "
            f"see {outdir / 'simout'} and {outdir / 'simerr'}",
            file=sys.stderr,
        )
    else:
        print(f"gem5 completed; results in {outdir}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
