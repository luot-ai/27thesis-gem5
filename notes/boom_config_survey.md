# BOOM Public Configuration Survey

## Purpose

This note surveys public BOOM configurations and identifies a practical
BOOM-like gem5 O3 baseline for this thesis stage.

This is a BOOM-like O3 baseline inspired by public BOOM configurations.
It is not a cycle-accurate reproduction of BOOM.

## Sources

- BOOM documentation: parameterization and generator overview
  - https://docs.boom-core.org/en/latest/sections/parameterization.html
- BOOM public config mixins
  - https://github.com/riscv-boom/riscv-boom/blob/master/src/main/scala/v3/common/config-mixins.scala
- Chipyard BOOM configuration wrappers
  - https://github.com/ucb-bar/chipyard/blob/main/generators/chipyard/src/main/scala/config/BoomConfigs.scala

## Public BOOM Configuration Families

Public BOOM configurations are usually exposed through Chipyard / BOOM config
mixins rather than as fixed standalone RTL files. Common families include:

- Small BOOM
- Medium BOOM
- Large BOOM
- Mega / bigger BOOM variants in some Chipyard configurations

These configurations mainly scale the core width and structure sizes. The most
important knobs are:

- fetch width
- decode width
- dispatch width
- issue width / issue queue structure
- commit width
- reorder buffer entries
- load queue entries
- store queue entries
- physical register file sizes
- branch predictor / BTB / RAS parameters
- cache and TLB configuration through the surrounding Chipyard system

## Parameters That Map Reasonably to gem5 O3

The following BOOM-style parameters can be mapped to gem5 O3 CPU parameters
with reasonable approximation:

| BOOM concept | gem5 O3 parameter area | Notes |
| --- | --- | --- |
| Fetch width | `fetchWidth` | Similar high-level meaning. |
| Decode width | `decodeWidth` | Similar high-level meaning. |
| Rename / dispatch width | `renameWidth`, `dispatchWidth` | gem5 separates several pipeline widths. |
| Issue width | `issueWidth` | Useful approximation, not exact scheduling model. |
| Commit width | `commitWidth`, `squashWidth` | Similar high-level retirement width. |
| ROB entries | `numROBEntries` | Directly useful. |
| Integer physical registers | `numPhysIntRegs` | Approximate. |
| Floating physical registers | `numPhysFloatRegs` | Approximate. |
| Load queue entries | `LQEntries` | Directly useful. |
| Store queue entries | `SQEntries` | Directly useful. |
| Branch predictor | gem5 branch predictor object | Approximate only. |
| BTB / RAS | BTB / RAS predictor parameters | Approximate only. |
| L1/L2 cache sizes | gem5 cache objects | Reasonable classic-cache approximation. |

## Parameters That Do Not Map Cleanly

Some BOOM details should not be claimed as reproduced by gem5 O3:

- exact Chisel pipeline timing
- exact BOOM issue queue implementation
- exact bypass network timing
- exact functional-unit latency and arbitration
- exact branch predictor implementation details
- exact frontend FTQ / fetch target queue behavior
- exact memory dependence predictor behavior
- exact cache coherence / TileLink behavior
- exact Rocket-Chip / Chipyard tile integration
- Chisel-generated RTL structure
- physical design effects, FPGA timing, or synthesized area/power

These differences matter because gem5 O3 is a simulator model with its own
pipeline implementation, not generated BOOM RTL.

## Candidate Baselines

### Small-like O3

A Small-like baseline would use a narrow O3 core with modest queues:

- 2-wide frontend/backend
- relatively small ROB
- modest load/store queues
- small physical register files

This is easier to run but may be too weak as a comparison point for a thesis
baseline intended to represent an aggressive out-of-order CPU.

### Medium-like O3

A Medium-like baseline is a better first target:

- 3-wide or 4-wide frontend/backend
- moderate ROB
- moderate load/store queues
- moderate physical register files
- conventional private L1 caches and an L2

This gives a credible O3 baseline without making simulation cost excessive.

### Large-like O3

A Large-like baseline would use wider pipeline widths and larger queues:

- wider fetch/decode/rename/issue/commit
- larger ROB
- larger LSQ
- larger physical register files
- stronger branch prediction

This may be useful later, but it is likely overkill before the minimal
benchmark flow and stats pipeline are stable.

## Recommended BOOM-like Baseline for This Stage

Use a Medium-like BOOM-inspired gem5 O3 profile as the main baseline.

Recommended initial profile:

| Parameter | Suggested gem5 value | Rationale |
| --- | ---: | --- |
| `fetchWidth` | 4 | Medium aggressive frontend. |
| `decodeWidth` | 4 | Matches a practical medium-wide O3 target. |
| `renameWidth` | 4 | Keeps frontend/backend balanced. |
| `dispatchWidth` | 4 | Keeps backend balanced. |
| `issueWidth` | 4 | Avoids an unrealistically huge machine. |
| `wbWidth` | 4 | Balanced with issue width. |
| `commitWidth` | 4 | Medium O3 retirement bandwidth. |
| `squashWidth` | 4 | Matches commit/fetch scale. |
| `numROBEntries` | 128 | Moderate ROB, good first baseline. |
| `numIQEntries` | 64 | Moderate issue queue. |
| `LQEntries` | 32 | Enough for streaming kernels. |
| `SQEntries` | 32 | Enough for simple memory kernels. |
| `numPhysIntRegs` | 128 | Moderate physical integer file. |
| `numPhysFloatRegs` | 128 | Moderate physical FP/vector scalar file approximation. |
| L1 I-cache | 32 KiB, 4-way | Conventional private L1. |
| L1 D-cache | 32 KiB, 4-way | Conventional private L1. |
| L2 cache | 512 KiB to 1 MiB | Reasonable shared/private next-level cache for single-core runs. |

The exact cache hierarchy can be refined after the first gem5 run succeeds.
For Step 6, the first implementation should prioritize a working single-core
SE-mode O3 configuration over perfect BOOM fidelity.

## Why This Fits the Thesis Stage

The current thesis stage needs a credible CPU baseline for later comparison
with stream-engine mechanisms. A Medium-like O3 baseline is appropriate because:

- it is stronger than an in-order or tiny O3 baseline;
- it keeps gem5 simulation time manageable;
- it exposes pressure on rename, issue, LSQ, ROB, and cache hierarchy;
- it can be compared against both no-prefetch and stride-prefetch variants;
- it avoids claiming cycle-accurate BOOM reproduction.

## Wording for Reports

Use the following wording:

This is a BOOM-like O3 baseline inspired by public BOOM configurations.
It is not a cycle-accurate reproduction of BOOM.

The goal is to provide a credible out-of-order CPU baseline in gem5, not to
reproduce BOOM RTL timing, Chisel implementation details, or Chipyard system
integration.

