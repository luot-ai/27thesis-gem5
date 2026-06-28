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


class L1ICache(Cache):
    is_read_only = True


class L1DCache(Cache):
    pass


class L2Cache(Cache):
    pass


def apply_o3_profile(cpu, profile):
    cpu.fetchWidth = profile.fetch_width
    cpu.decodeWidth = profile.decode_width
    cpu.renameWidth = profile.rename_width
    cpu.dispatchWidth = profile.dispatch_width
    cpu.issueWidth = profile.issue_width
    cpu.wbWidth = profile.wb_width
    cpu.commitWidth = profile.commit_width
    cpu.squashWidth = profile.squash_width

    cpu.numROBEntries = profile.rob_entries
    cpu.instQueues = [IQUnit(numEntries=profile.iq_entries)]
    cpu.LQEntries = profile.lq_entries
    cpu.SQEntries = profile.sq_entries

    cpu.numPhysIntRegs = profile.phys_int_regs
    cpu.numPhysFloatRegs = profile.phys_float_regs
    cpu.numPhysVecRegs = profile.phys_vec_regs


def make_cache(cache_cls, cache_profile, prefetcher=None, **kwargs):
    cache = cache_cls(
        size=cache_profile.size,
        assoc=cache_profile.assoc,
        tag_latency=cache_profile.tag_latency,
        data_latency=cache_profile.data_latency,
        response_latency=cache_profile.response_latency,
        mshrs=cache_profile.mshrs,
        tgts_per_mshr=cache_profile.tgts_per_mshr,
        **kwargs,
    )
    if prefetcher is not None:
        cache.prefetcher = prefetcher
    return cache


def build_system(args):
    profile = get_profile(args.profile)
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
    apply_o3_profile(system.cpu, profile)

    dcache_prefetcher = None
    if args.config == "o3_stridepf":
        dcache_prefetcher = StridePrefetcher(
            degree=args.stridepf_degree,
            latency=args.stridepf_latency,
            prefetch_on_access=args.stridepf_on_access,
        )

    system.cpu.icache = make_cache(L1ICache, profile.l1i)
    system.cpu.dcache = make_cache(L1DCache, profile.l1d, dcache_prefetcher)
    system.l2cache = make_cache(L2Cache, profile.l2)

    system.membus = SystemXBar()
    system.l2bus = L2XBar()

    system.cpu.icache.cpu_side = system.cpu.icache_port
    system.cpu.dcache.cpu_side = system.cpu.dcache_port
    system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
    system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

    system.l2cache.cpu_side = system.l2bus.mem_side_ports
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
        choices=("o3_nopf", "o3_stridepf"),
        default="o3_nopf",
        help="Baseline configuration. o3_stridepf is prepared for Step 7.",
    )
    parser.add_argument("--profile", default="medium_boom_like")
    parser.add_argument("--mem-size", default="512MiB")
    parser.add_argument("--cache-line-size", type=int, default=64)
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

    print(
        "Beginning simulation: "
        f"config={args.config}, profile={args.profile}, cmd={args.cmd}"
    )
    exit_event = m5.simulate()
    print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")


if __name__ in ("__m5_main__", "__main__"):
    main()
