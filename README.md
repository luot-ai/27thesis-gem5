# gem5 RISC-V O3 Baseline

This project is building a reproducible gem5 RISC-V O3 baseline for thesis experiments on streaming memory-access optimization.

本阶段只是建立 baseline，不代表 stream engine 已经完成。

## Current Status

- Minimal benchmark source: `benchmarks/vadd/vadd.c`
- Default problem size: `N = 1024`
- Build script: `scripts/build_benchmarks.sh`
- Environment notes: `notes/env_check.md`
- gem5 O3 runs: not yet available
- stream engine: not implemented in this stage

## RISC-V Toolchain

Install a RISC-V Linux GNU compiler, or point `RISCV_GCC` at an existing compiler.

On Ubuntu:

```bash
sudo ./scripts/bootstrap_host_deps.sh
```

Build the current benchmark:

```bash
./scripts/build_benchmarks.sh
```

Useful overrides:

```bash
RISCV_GCC=riscv64-linux-gnu-gcc OPT=-O3 N=1024 ./scripts/build_benchmarks.sh
```

## gem5

gem5 source has been cloned to `tools/gem5`. No local `gem5.opt` has been built yet.

Build the RISCV target:

```bash
cd tools/gem5
scons build/RISCV/gem5.opt -j2
```

`-j2` is a conservative default for the current VM. If memory pressure is low, `-j4` is also reasonable.

Future run scripts will accept `--gem5-bin /path/to/gem5.opt`, so the project does not depend on a hard-coded absolute path.

## Baseline Scope

The immediate goal is to run `vadd_N1024` on gem5 O3 with no prefetching. After that, the project will add a stride-prefetch baseline and a BOOM-like O3 profile inspired by public BOOM configurations.

This is a BOOM-like O3 baseline inspired by public BOOM configurations. It is not a cycle-accurate reproduction of BOOM.

## Group Meeting Wording

本阶段目标不是完成 stream engine 建模，而是先建立可信的 O3 CPU baseline。

后续 stream engine 的收益不仅要和普通 O3 CPU 比，也要和 gem5 中的 stride prefetcher 比。

stride prefetcher 主要解决数据提前进入 cache 的问题，但不会减少动态 load/store 指令，也不会减少地址生成、rename、issue、commit 等流水线压力。

stream engine 后续要验证的是：能否把规则访存从主指令流中解耦，由硬件维护索引更新、buffer 状态和访存请求，从而降低边缘端 signal / AI 小 kernel 中访存相关指令对计算流水的干扰。
