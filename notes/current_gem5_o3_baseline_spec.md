# Current gem5 O3 Baseline Specification

## Scope

This note records the current implemented and verified gem5 RISC-V O3 baseline
in a compact machine-configuration style.

Important wording:

```text
This is a BOOM-like gem5 O3 baseline inspired by public BOOM configurations.
It is not a cycle-accurate reproduction of BOOM.
```

The values below are taken from:

- `gem5_configs/boom_like_profiles.py`
- `gem5_configs/riscv_o3_baseline.py`
- verified run config: `results/vadd_N16384/o3_nopf/config.ini`

## Short Configuration Block

```text
CPU clock: 2.0GHz
System clock: 1.0GHz
ISA / mode: RISC-V SE-mode, timing memory mode

Single-core gem5 BaseO3CPU
4-wide fetch/decode/rename/dispatch/issue/writeback/commit
64 IQ entries
32 LQ, 32 SQ
128 ROB
128 Int physical registers
128 FP physical registers
128 Vec physical registers
Store-set memory dependence predictor enabled by gem5 O3 defaults

Function Units from gem5 default FUPool:
6 Int ALU, 1-cycle, pipelined
2 Int Mult/Div units:
  IntMult 3-cycle, pipelined
  IntDiv 20-cycle, non-pipelined
4 FP ALU-class units:
  FloatAdd / FloatCmp / FloatCvt 2-cycle, pipelined
2 FP Mult/Div-class units:
  FloatMult 4-cycle, pipelined
  FloatMultAcc 5-cycle, pipelined
  FloatMisc 3-cycle, pipelined
  FloatDiv 12-cycle, non-pipelined
  FloatSqrt 24-cycle, non-pipelined
4 SIMD units, 1-cycle, pipelined
4 combined memory units for MemRead/MemWrite and vector memory ops, 1-cycle, pipelined

Branch predictor:
gem5 BranchPredictor wrapper
TournamentBP conditional predictor
SimpleBTB, 4096 entries, 1-way, 16 tag bits
SimpleIndirectPredictor, 256 sets, 2-way, 16 tag bits
ReturnAddrStack, 16 entries
Speculative branch history update enabled

Private L1 I-cache:
32KiB, 4-way, 64B line
8 MSHRs, 16 targets/MSHR
tag/data/response latency: 2/2/2 cycles

Private L1 D-cache:
32KiB, 4-way, 64B line
16 MSHRs, 16 targets/MSHR
tag/data/response latency: 2/2/2 cycles

L2 cache:
512KiB, 8-way, 64B line
32 MSHRs, 16 targets/MSHR
tag/data/response latency: 12/12/12 cycles

L1-to-L2 bus:
gem5 CoherentXBar / L2XBar
32-byte width
frontend/header/response latency: 1/1/1 cycles

Memory bus:
gem5 SystemXBar
16-byte width
frontend/header/forward/response latency: 3/1/4/2 cycles

DRAM:
gem5 DDR3_1600_8x8
single MemCtrl, 512MiB address range
8-bit device bus width, 8 devices/rank, 2 ranks/channel
tCK = 1.25ns, burst length = 8
theoretical single-channel DDR3-1600 x64 bandwidth is about 12.8GB/s

No shared L3 cache in the current baseline.
```

## What This Is Not

This is not the kind of configuration below:

```text
8-wide fetch/issue/commit
192 ROB
256 Int RF / 256 FP RF
32KiB 8-way L1
256KiB 16-way L2
8MiB shared L3
```

Those values describe a stronger out-of-order machine than the current
implemented baseline. Our current model is intentionally more conservative and
keeps the first gem5 flow fast enough to iterate.

## Current Baseline vs Example Strong OOO Core

| Component | Current gem5 baseline | Strong example in prompt |
| --- | --- | --- |
| CPU clock | 2.0GHz | 2.0GHz |
| Width | 4-wide | 8-wide |
| IQ | 64 | 64 |
| LQ / SQ | 32 / 32 | 32 / 32 |
| ROB | 128 | 192 |
| Int RF | 128 | 256 |
| FP RF | 128 | 256 |
| Int ALU | 6, 1-cycle | 6, 1-cycle |
| Int Mult/Div | 2, 3/20-cycle | 2, 3/20-cycle |
| FP ALU | 4, 2-cycle | 4, 2-cycle |
| FP Mult/Div | 2, 4/12-cycle | 2, 4/12-cycle |
| SIMD | 4, 1-cycle | 4, 1-cycle |
| L1 I-cache | 32KiB, 4-way | 32KiB, 8-way |
| L1 D-cache | 32KiB, 4-way | 32KiB, 8-way |
| L2 | 512KiB, 8-way | 256KiB, 16-way |
| L3 | none | 8MiB, shared |
| DRAM | DDR3_1600_8x8, one MemCtrl | 2-channel DDR3-1600 in example |

## Notes on FU Accuracy

The FU list above is the gem5 `FUPool` accepted in the generated `config.ini`.
It is not a BOOM RTL FU description. BOOM's public configs expose issue queue
types and execution-unit organization, while gem5 models functional units with
`FUDesc` and `OpDesc` classes.

For reporting, use:

```text
The gem5 O3 baseline uses gem5's default FUPool, whose generated config
contains 6 integer ALUs, 2 integer multiply/divide units, 4 FP ALU-class units,
2 FP multiply/divide-class units, and 4 SIMD units.
```

Avoid:

```text
The BOOM core has exactly these functional units.
```

## Recommended Report Wording

```text
We use a single-core RISC-V gem5 BaseO3CPU configured as a BOOM-like
out-of-order baseline. The core runs at 2GHz with 4-wide frontend/backend
widths, 128 ROB entries, 64 IQ entries, 32-entry load/store queues, and private
32KiB L1 I/D caches backed by a 512KiB L2 and DDR3-1600 memory. This baseline is
inspired by public BOOM configuration families but does not reproduce BOOM RTL
timing or its exact execution-unit and branch-predictor implementation.
```

