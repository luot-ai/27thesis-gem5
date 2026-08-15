"""Single-core RISC-V BOOM-like O3 baseline for gem5 SE mode.

This configuration is inspired by public BOOM configurations. It is not a
cycle-accurate reproduction of BOOM.
"""

import argparse
import os
import sys

import m5
from m5.objects import *

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from boom_like_profiles import get_profile


PAPER_STRIDE_CONFIG = "o3_stridepf_l1d_l2_l3_d8"
STRIDE_CONFIGS = ("o3_stridepf", "o3_stridepf_d8", PAPER_STRIDE_CONFIG)
ZIRCON_WIDTH_CONFIGS = (
    "o3_zircon_width_nopf",
    "o3_stream_axi_functional_zircon_width",
)
ZIRCON_BOOM_MEDIUM_CONFIGS = (
    "o3_zircon_boom_medium_nopf",
    "o3_stream_axi_functional_zircon_boom_medium",
)
ZIRCON_BLOCKING_CACHE_CONFIGS = (
    "o3_zircon_blocking_cache_nopf",
    "o3_stream_axi_functional_zircon_blocking_cache",
)
SINGLE_LSU_CONFIGS = (
    "o3_single_lsu_nopf",
    "o3_stream_axi_functional_single_lsu",
    *ZIRCON_WIDTH_CONFIGS,
    *ZIRCON_BOOM_MEDIUM_CONFIGS,
    *ZIRCON_BLOCKING_CACHE_CONFIGS,
)
STREAM_CONFIGS = (
    "o3_stream_axi_functional",
    "o3_stream_axi_functional_single_lsu",
    "o3_stream_axi_functional_zircon_width",
    "o3_stream_axi_functional_zircon_boom_medium",
    "o3_stream_axi_functional_zircon_blocking_cache",
)
CONFIG_CHOICES = (
    "o3_nopf",
    "o3_single_lsu_nopf",
    "o3_zircon_width_nopf",
    "o3_zircon_boom_medium_nopf",
    "o3_zircon_blocking_cache_nopf",
    *STRIDE_CONFIGS,
    *STREAM_CONFIGS,
)


class L1ICache(Cache):
    is_read_only = True


class L1DCache(Cache):
    pass


class L2Cache(Cache):
    pass


class L3Cache(Cache):
    pass


class SingleLsuRdWrPort(RdWrPort):
    count = 1


class SingleLsuFUPool(FUPool):
    FUList = [
        IntALU(),
        IntMultDiv(),
        FP_ALU(),
        FP_MultDiv(),
        ReadPort(),
        SIMD_Unit(),
        Matrix_Unit(),
        System_Unit(),
        PredALU(),
        WritePort(),
        SingleLsuRdWrPort(),
    ]


def selected_profile_name(args):
    if args.profile == "auto":
        if args.config == PAPER_STRIDE_CONFIG:
            return "paper_pf_stride_like"
        if args.config in ZIRCON_BLOCKING_CACHE_CONFIGS:
            return "zircon_blocking_cache_like"
        if args.config in ZIRCON_BOOM_MEDIUM_CONFIGS:
            return "zircon_boom_medium_like"
        if args.config in ZIRCON_WIDTH_CONFIGS:
            return "zircon_width_like"
        return "medium_boom_like"
    return args.profile


def stride_prefetch_degree(args):
    if args.config in ("o3_stridepf_d8", PAPER_STRIDE_CONFIG):
        return 8
    return args.stridepf_degree


def stride_prefetch_latency(args):
    if args.config in ("o3_stridepf_d8", PAPER_STRIDE_CONFIG):
        return 1
    return args.stridepf_latency


def make_stride_prefetcher(args):
    return StridePrefetcher(
        degree=stride_prefetch_degree(args),
        latency=stride_prefetch_latency(args),
        prefetch_on_access=args.stridepf_on_access,
    )


def apply_o3_profile(cpu, profile, single_lsu=False):
    cpu.fetchWidth = profile.fetch_width
    cpu.decodeWidth = profile.decode_width
    cpu.renameWidth = profile.rename_width
    cpu.dispatchWidth = profile.dispatch_width
    cpu.issueWidth = profile.issue_width
    cpu.wbWidth = profile.wb_width
    cpu.commitWidth = profile.commit_width
    cpu.squashWidth = profile.squash_width

    cpu.numROBEntries = profile.rob_entries
    iq_args = {"numEntries": profile.iq_entries}
    if single_lsu:
        iq_args["fuPool"] = SingleLsuFUPool()
        cpu.cacheLoadPorts = 1
        cpu.cacheStorePorts = 1
    cpu.instQueues = [IQUnit(**iq_args)]
    cpu.LQEntries = profile.lq_entries
    cpu.SQEntries = profile.sq_entries

    cpu.numPhysIntRegs = profile.phys_int_regs
    cpu.numPhysFloatRegs = profile.phys_float_regs
    cpu.numPhysVecRegs = profile.phys_vec_regs


def make_cache(
    cache_cls,
    cache_profile,
    prefetcher=None,
    mshrs=None,
    tgts_per_mshr=None,
    **kwargs,
):
    cache = cache_cls(
        size=cache_profile.size,
        assoc=cache_profile.assoc,
        tag_latency=cache_profile.tag_latency,
        data_latency=cache_profile.data_latency,
        response_latency=cache_profile.response_latency,
        mshrs=cache_profile.mshrs if mshrs is None else mshrs,
        tgts_per_mshr=(
            cache_profile.tgts_per_mshr
            if tgts_per_mshr is None
            else tgts_per_mshr
        ),
        **kwargs,
    )
    if prefetcher is not None:
        cache.prefetcher = prefetcher
    return cache


def build_system(args):
    profile = get_profile(selected_profile_name(args))
    system = System()
    system.mem_mode = "timing"
    system.mem_ranges = [AddrRange(args.mem_size)]
    system.cache_line_size = args.cache_line_size

    system.voltage_domain = VoltageDomain(voltage=args.sys_voltage)
    system.clk_domain = SrcClockDomain(
        clock=args.sys_clock,
        voltage_domain=system.voltage_domain,
    )

    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain(
        clock=args.cpu_clock,
        voltage_domain=system.cpu_voltage_domain,
    )

    system.cpu = RiscvO3CPU(cpu_id=0)
    system.cpu.clk_domain = system.cpu_clk_domain
    apply_o3_profile(
        system.cpu,
        profile,
        single_lsu=args.config in SINGLE_LSU_CONFIGS,
    )

    if args.config in STREAM_CONFIGS:
        system.stream_engine = StreamEngine(
            fifo_count=4,
            stream_segment_bytes=args.stream_segment_bytes,
            mem_refill_latency=args.stream_mem_refill_latency,
            mem_drain_latency=args.stream_mem_drain_latency,
            mem_burst_words=args.stream_mem_burst_words,
            compute_latency=3,
            initiation_interval=1,
        )

    dcache_prefetcher = None
    if args.config in STRIDE_CONFIGS:
        dcache_prefetcher = make_stride_prefetcher(args)

    l2_prefetcher = None
    l3_prefetcher = None
    if args.config == PAPER_STRIDE_CONFIG:
        l2_prefetcher = make_stride_prefetcher(args)
        l3_prefetcher = make_stride_prefetcher(args)

    cache_overrides = {
        "mshrs": args.cache_mshrs,
        "tgts_per_mshr": args.cache_targets_per_mshr,
    }
    system.cpu.icache = make_cache(
        L1ICache, profile.l1i, **cache_overrides
    )
    system.cpu.dcache = make_cache(
        L1DCache, profile.l1d, dcache_prefetcher, **cache_overrides
    )
    system.l2cache = make_cache(
        L2Cache, profile.l2, l2_prefetcher, **cache_overrides
    )

    system.membus = SystemXBar()
    system.l2bus = L2XBar()

    system.cpu.icache.cpu_side = system.cpu.icache_port
    system.cpu.dcache.cpu_side = system.cpu.dcache_port
    system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
    system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

    system.l2cache.cpu_side = system.l2bus.mem_side_ports
    if args.config == PAPER_STRIDE_CONFIG:
        if profile.l3 is None:
            raise ValueError(
                f"profile '{selected_profile_name(args)}' has no L3 cache for "
                f"config '{PAPER_STRIDE_CONFIG}'"
            )
        system.l3bus = L2XBar(width=16)
        system.l3cache = make_cache(
            L3Cache, profile.l3, l3_prefetcher, **cache_overrides
        )
        system.l2cache.mem_side = system.l3bus.cpu_side_ports
        system.l3cache.cpu_side = system.l3bus.mem_side_ports
        system.l3cache.mem_side = system.membus.cpu_side_ports
    else:
        system.l2cache.mem_side = system.membus.cpu_side_ports

    system.cpu.createInterruptController()
    system.system_port = system.membus.cpu_side_ports

    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8(range=system.mem_ranges[0])
    system.mem_ctrl.port = system.membus.mem_side_ports

    binary = os.path.abspath(args.cmd)
    process = Process(pid=100)
    process.executable = binary
    process.cmd = [binary] + args.options
    process.cwd = os.getcwd()

    system.workload = SEWorkload.init_compatible(binary)
    system.cpu.workload = process
    system.cpu.createThreads()

    return system


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", required=True, help="RISC-V benchmark binary")
    parser.add_argument(
        "--options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Arguments passed to the benchmark after --options",
    )
    parser.add_argument(
        "--config",
        choices=CONFIG_CHOICES,
        default="o3_nopf",
        help="Baseline or stride-prefetch configuration.",
    )
    parser.add_argument("--profile", default="auto")
    parser.add_argument("--mem-size", default="512MiB")
    parser.add_argument("--cache-line-size", type=int, default=64)
    parser.add_argument("--cache-mshrs", type=int)
    parser.add_argument("--cache-targets-per-mshr", type=int)
    parser.add_argument("--stream-segment-bytes", type=int, default=128)
    parser.add_argument("--stream-mem-burst-latency", type=int, default=176)
    parser.add_argument("--stream-mem-refill-latency", type=int, default=176)
    parser.add_argument("--stream-mem-drain-latency", type=int, default=176)
    parser.add_argument("--stream-mem-burst-words", type=int, default=32)
    parser.add_argument("--sys-clock", default="1GHz")
    parser.add_argument("--cpu-clock", default="2GHz")
    parser.add_argument("--sys-voltage", default="1.0V")
    parser.add_argument("--stridepf-degree", type=int, default=4)
    parser.add_argument("--stridepf-latency", type=int, default=1)
    parser.add_argument("--stridepf-on-access", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    root = Root(full_system=False, system=build_system(args))
    m5.instantiate()

    profile_name = selected_profile_name(args)
    print(
        "Beginning simulation: "
        f"config={args.config}, profile={profile_name}, cmd={args.cmd}"
    )
    exit_event = m5.simulate()
    print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")


if __name__ in ("__m5_main__", "__main__"):
    main()
