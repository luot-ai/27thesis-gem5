# Environment Check

Date: 2026-06-28

This file records the initial setup check and the current repository status.
Some items that were missing during the first check have since been installed or
generated.

## Current status after setup

- Current working directory: `/home/luot/27thesis`
- RISC-V compiler now found: `/usr/bin/riscv64-linux-gnu-gcc`
- Minimal benchmark source: `benchmarks/vadd/vadd.c`
- Built benchmark binary: `build/vadd_N1024.riscv`
- Binary format: static 64-bit RISC-V Linux ELF
- Local gem5 source checkout: `tools/gem5`
- Local `gem5.opt`: not found yet at `tools/gem5/build/RISCV/gem5.opt`
- BOOM-like O3 config: `gem5_configs/riscv_o3_baseline.py`
- BOOM-like profile definitions: `gem5_configs/boom_like_profiles.py`
- gem5 run wrapper: `scripts/run_gem5.py`

The current blocker for the first real gem5 run is the missing `gem5.opt`
binary. The wrapper can already be dry-run to record the intended command:

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_nopf \
  --dry-run
```

## Current repository contents

- Current working directory: `/home/luot/27thesis`
- Existing task note: `instCodex/gem5.md`
- Benchmark paths found before setup: none
- gem5 scripts/configs found before setup: none

## Benchmark paths

- Created minimal benchmark source: `benchmarks/vadd/vadd.c`
- Planned first binary output: `build/vadd_N1024.riscv`

## RISC-V compiler

- `riscv64-unknown-linux-gnu-gcc`: not found during initial check
- `riscv64-linux-gnu-gcc`: now found at `/usr/bin/riscv64-linux-gnu-gcc`
- `riscv64-unknown-elf-gcc`: not found during initial check

The build script supports overriding the compiler:

```bash
RISCV_GCC=/path/to/riscv64-linux-gnu-gcc ./scripts/build_benchmarks.sh
```

Recommended Ubuntu package path:

```bash
sudo apt update
sudo apt install gcc-riscv64-linux-gnu g++-riscv64-linux-gnu
```

## gem5

- Local `gem5.opt`: not found
- Local gem5 source checkout: `tools/gem5`
- gem5 branch: `stable`
- gem5 commit checked out: `c8222cc`

Recommended source setup:

```bash
git clone https://github.com/gem5/gem5.git tools/gem5
cd tools/gem5
scons build/RISCV/gem5.opt -j$(nproc)
```

The run scripts should accept `--gem5-bin` rather than relying on an absolute path.

## Host environment

- OS: Ubuntu 24.04.3 LTS
- Kernel: Linux 6.14.0-37-generic
- `git`: found
- `python3`: found
- `g++`: found
- `make`: found
- `scons`: now found at `/usr/bin/scons`
- `sudo`: available, but non-interactive passwordless sudo is not enabled
- `python3 -m pip`: now available
- `python3 -m venv`: now available

## Missing items

- built `gem5.opt`
- gem5 run results

## Next step

1. Finish building gem5 for the RISCV target:

   ```bash
   cd tools/gem5
   scons build/RISCV/gem5.opt -j2
   ```

2. Run the minimal O3 no-prefetch baseline:

   ```bash
   python3 scripts/run_gem5.py \
     --gem5-bin tools/gem5/build/RISCV/gem5.opt \
     --benchmark build/vadd_N1024.riscv \
     --bench-name vadd_N1024 \
     --config o3_nopf
   ```

3. Inspect `results/vadd_N1024/o3_nopf/simout`,
   `results/vadd_N1024/o3_nopf/simerr`, and
   `results/vadd_N1024/o3_nopf/stats.txt`.
