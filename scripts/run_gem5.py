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
PAPER_STRIDE_CONFIG = "o3_stridepf_l1d_l2_l3_d8"
STRIDE_CONFIGS = ("o3_stridepf", "o3_stridepf_d8", PAPER_STRIDE_CONFIG)
ZIRCON_WIDTH_CONFIGS = (
    "o3_zircon_width_nopf",
    "o3_stream_axi_functional_zircon_width",
)
ZIRCON_BLOCKING_CACHE_CONFIGS = (
    "o3_zircon_blocking_cache_nopf",
    "o3_stream_axi_functional_zircon_blocking_cache",
)
SINGLE_LSU_CONFIGS = (
    "o3_single_lsu_nopf",
    "o3_stream_axi_functional_single_lsu",
    *ZIRCON_WIDTH_CONFIGS,
    *ZIRCON_BLOCKING_CACHE_CONFIGS,
)
STREAM_CONFIGS = (
    "o3_stream_axi_functional",
    "o3_stream_axi_functional_single_lsu",
    "o3_stream_axi_functional_zircon_width",
    "o3_stream_axi_functional_zircon_blocking_cache",
)
CONFIG_CHOICES = (
    "o3_nopf",
    "o3_single_lsu_nopf",
    "o3_zircon_width_nopf",
    "o3_zircon_blocking_cache_nopf",
    *STRIDE_CONFIGS,
    *STREAM_CONFIGS,
)


def selected_profile_name(args):
    if args.profile == "auto":
        if args.config == PAPER_STRIDE_CONFIG:
            return "paper_pf_stride_like"
        if args.config in ZIRCON_BLOCKING_CACHE_CONFIGS:
            return "zircon_blocking_cache_like"
        if args.config in ZIRCON_WIDTH_CONFIGS:
            return "zircon_width_like"
        return "medium_boom_like"
    return args.profile


def effective_stride_degree(args):
    if args.config in ("o3_stridepf_d8", PAPER_STRIDE_CONFIG):
        return 8
    return args.stridepf_degree


def effective_stride_latency(args):
    if args.config in ("o3_stridepf_d8", PAPER_STRIDE_CONFIG):
        return 1
    return args.stridepf_latency


def stride_prefetch_levels(config):
    if config == PAPER_STRIDE_CONFIG:
        return ["l1d", "l2", "l3"]
    if config in ("o3_stridepf", "o3_stridepf_d8"):
        return ["l1d"]
    return []


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
        choices=CONFIG_CHOICES,
        default="o3_nopf",
        help="Baseline config to pass to the gem5 config script",
    )
    parser.add_argument(
        "--profile",
        default="auto",
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
    parser.add_argument("--stream-segment-bytes", type=int, default=128)
    parser.add_argument("--stream-mem-burst-latency", type=int, default=176)
    parser.add_argument("--stream-mem-refill-latency", type=int)
    parser.add_argument("--stream-mem-drain-latency", type=int)
    parser.add_argument("--stream-mem-burst-words", type=int, default=32)
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
    profile_name = selected_profile_name(args)

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
        profile_name,
        "--mem-size",
        args.mem_size,
        "--cache-line-size",
        str(args.cache_line_size),
        "--stream-segment-bytes",
        str(args.stream_segment_bytes),
        "--stream-mem-burst-latency",
        str(args.stream_mem_burst_latency),
        "--stream-mem-refill-latency",
        str(
            args.stream_mem_refill_latency
            if args.stream_mem_refill_latency is not None
            else args.stream_mem_burst_latency
        ),
        "--stream-mem-drain-latency",
        str(
            args.stream_mem_drain_latency
            if args.stream_mem_drain_latency is not None
            else args.stream_mem_burst_latency
        ),
        "--stream-mem-burst-words",
        str(args.stream_mem_burst_words),
        "--sys-clock",
        args.sys_clock,
        "--cpu-clock",
        args.cpu_clock,
        "--stridepf-degree",
        str(effective_stride_degree(args)),
        "--stridepf-latency",
        str(effective_stride_latency(args)),
    ]
    if args.stridepf_on_access:
        cmd.append("--stridepf-on-access")
    if args.bench_arg:
        cmd.append("--options")
        cmd.extend(args.bench_arg)
    return cmd


def write_run_metadata(args, outdir: Path, cmd):
    stride_levels = stride_prefetch_levels(args.config)
    stream_enabled = args.config in STREAM_CONFIGS
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "bench_name": args.bench_name,
        "config": args.config,
        "requested_profile": args.profile,
        "profile": selected_profile_name(args),
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
            "single_lsu": args.config in SINGLE_LSU_CONFIGS,
            "cache_load_ports": (
                1 if args.config in SINGLE_LSU_CONFIGS else 200
            ),
            "cache_store_ports": (
                1 if args.config in SINGLE_LSU_CONFIGS else 200
            ),
        },
        "stride_prefetcher": {
            "enabled": bool(stride_levels),
            "levels": stride_levels,
            "degree": effective_stride_degree(args),
            "latency": effective_stride_latency(args),
            "prefetch_on_access": args.stridepf_on_access,
        },
        "stream_engine": {
            "enabled": stream_enabled,
            "mode": "axi_functional" if stream_enabled else "none",
            "stream_segment_bytes": (
                args.stream_segment_bytes if stream_enabled else None
            ),
            "mem_burst_latency": (
                args.stream_mem_burst_latency if stream_enabled else None
            ),
            "mem_refill_latency": (
                args.stream_mem_refill_latency
                if stream_enabled and args.stream_mem_refill_latency is not None
                else args.stream_mem_burst_latency
                if stream_enabled
                else None
            ),
            "mem_drain_latency": (
                args.stream_mem_drain_latency
                if stream_enabled and args.stream_mem_drain_latency is not None
                else args.stream_mem_burst_latency
                if stream_enabled
                else None
            ),
            "mem_burst_words": (
                args.stream_mem_burst_words if stream_enabled else None
            ),
        },
        "note": (
            "BOOM-like gem5 O3 baseline inspired by public BOOM configs; "
            "not a cycle-accurate BOOM reproduction."
        ),
    }
    with (outdir / "run_metadata.json").open("w", encoding="utf-8") as f:
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
    write_run_metadata(args, outdir, cmd)

    print(" ".join(cmd))
    if args.dry_run:
        print(f"dry run: wrote {outdir / 'run_metadata.json'}")
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
