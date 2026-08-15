#!/usr/bin/env python3
"""批量运行 benchmark/config 组合。"""

import argparse
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
RUN_GEM5 = ROOT_DIR / "scripts" / "run_gem5.py"
PARSE_STATS = ROOT_DIR / "scripts" / "parse_stats.py"

DEFAULT_GEM5_BIN = ROOT_DIR / "tools" / "gem5" / "build" / "RISCV" / "gem5.opt"
DEFAULT_RESULTS_DIR = ROOT_DIR / "results"
DEFAULT_BENCHMARKS = ("matmul_inner_M32_N32_K32",)
CONFIGS = (
    "o3_nopf",
    "o3_stridepf",
    "o3_stridepf_d8",
    "o3_stridepf_l1d_l2_l3_d8",
    "o3_stream_axi_functional",
    "o3_single_lsu_nopf",
    "o3_stream_axi_functional_single_lsu",
    "o3_zircon_width_nopf",
    "o3_stream_axi_functional_zircon_width",
    "o3_zircon_boom_medium_nopf",
    "o3_stream_axi_functional_zircon_boom_medium",
    "o3_zircon_blocking_cache_nopf",
    "o3_stream_axi_functional_zircon_blocking_cache",
)


def split_list(values, default):
    if not values:
        values = list(default)

    items = []
    for value in values:
        for part in value.split(","):
            part = part.strip()
            if part:
                items.append(part)
    return items


def discover_benchmarks():
    build_dir = ROOT_DIR / "build"
    return {path.stem: path for path in sorted(build_dir.glob("*.riscv"))}


def resolve_benchmarks(values):
    specs = split_list(values, DEFAULT_BENCHMARKS)
    discovered = discover_benchmarks()
    if specs == ["all"]:
        if not discovered:
            raise SystemExit("error: build/ 下没有找到 *.riscv benchmark")
        return list(discovered.items())

    resolved = []
    for spec in specs:
        path = Path(spec)
        if path.suffix == ".riscv" or "/" in spec:
            path = path if path.is_absolute() else ROOT_DIR / path
            name = path.stem
        else:
            name = spec
            path = discovered.get(spec, ROOT_DIR / "build" / f"{spec}.riscv")

        if not path.is_file():
            raise SystemExit(
                f"error: benchmark not found: {path}\n"
                "hint: 先运行 ./scripts/build_benchmarks.sh"
            )
        resolved.append((name, path.resolve()))
    return resolved


def resolve_configs(values):
    specs = split_list(values, ("all",))
    if specs == ["all"]:
        return list(CONFIGS)

    unknown = [item for item in specs if item not in CONFIGS]
    if unknown:
        available = ", ".join(CONFIGS)
        raise SystemExit(
            f"error: unknown config(s): {', '.join(unknown)}\n"
            f"available configs: {available}"
        )
    return specs


def parse_args():
    parser = argparse.ArgumentParser(
        description="批量运行 gem5 benchmark/config 组合"
    )
    parser.add_argument(
        "--gem5-bin",
        default=str(DEFAULT_GEM5_BIN),
        help="gem5.opt 路径",
    )
    parser.add_argument(
        "--benchmark",
        action="append",
        default=[],
        help=(
            "benchmark 名称或 .riscv 路径，可重复或逗号分隔；"
            "默认 matmul_inner_M32_N32_K32，传 all 表示 build/ 下全部"
        ),
    )
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        help="config 名称，可重复或逗号分隔；默认 all",
    )
    parser.add_argument("--profile", default="auto")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--mem-size", default="512MiB")
    parser.add_argument("--cache-line-size", type=int, default=64)
    parser.add_argument("--stream-segment-bytes", type=int, default=128)
    parser.add_argument("--sys-clock", default="1GHz")
    parser.add_argument("--cpu-clock", default="2GHz")
    parser.add_argument("--stridepf-on-access", action="store_true")
    parser.add_argument("--gem5-arg", action="append", default=[])
    parser.add_argument("--bench-arg", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--no-parse-stats",
        action="store_true",
        help="运行完成后不刷新 results/summary.csv",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出可发现的 benchmark 和可用 config 后退出",
    )
    return parser.parse_args()


def command_for(args, bench_name, bench_path, config):
    cmd = [
        sys.executable,
        str(RUN_GEM5),
        "--gem5-bin",
        args.gem5_bin,
        "--benchmark",
        str(bench_path),
        "--bench-name",
        bench_name,
        "--config",
        config,
        "--profile",
        args.profile,
        "--results-dir",
        args.results_dir,
        "--mem-size",
        args.mem_size,
        "--cache-line-size",
        str(args.cache_line_size),
        "--stream-segment-bytes",
        str(args.stream_segment_bytes),
        "--sys-clock",
        args.sys_clock,
        "--cpu-clock",
        args.cpu_clock,
    ]
    for gem5_arg in args.gem5_arg:
        cmd.extend(["--gem5-arg", gem5_arg])
    for bench_arg in args.bench_arg:
        cmd.extend(["--bench-arg", bench_arg])
    if args.stridepf_on_access:
        cmd.append("--stridepf-on-access")
    if args.dry_run:
        cmd.append("--dry-run")
    return cmd


def print_available():
    print("可发现的 benchmark:")
    for name, path in discover_benchmarks().items():
        print(f"  {name}: {path}")
    print("\n可用 config:")
    for config in CONFIGS:
        print(f"  {config}")


def refresh_summary(args):
    cmd = [
        sys.executable,
        str(PARSE_STATS),
        "--results-dir",
        args.results_dir,
    ]
    print("刷新 stats 汇总:", flush=True)
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT_DIR).returncode


def main():
    args = parse_args()

    if args.list:
        print_available()
        return 0

    benchmarks = resolve_benchmarks(args.benchmark)
    configs = resolve_configs(args.config)
    total = len(benchmarks) * len(configs)
    failures = []

    for index, (bench_name, bench_path) in enumerate(benchmarks, start=1):
        for config_index, config in enumerate(configs, start=1):
            ordinal = (index - 1) * len(configs) + config_index
            print(f"[{ordinal}/{total}] {bench_name} / {config}", flush=True)
            cmd = command_for(args, bench_name, bench_path, config)
            completed = subprocess.run(cmd, cwd=ROOT_DIR)
            if completed.returncode != 0:
                failures.append((bench_name, config, completed.returncode))
                if not args.continue_on_error:
                    break
        if failures and not args.continue_on_error:
            break

    if failures:
        print("\n失败的组合:")
        for bench_name, config, returncode in failures:
            print(f"  {bench_name} / {config}: exit {returncode}")
        return 1

    if not args.dry_run and not args.no_parse_stats:
        return refresh_summary(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
