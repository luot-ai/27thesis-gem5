# Environment Check

Date: 2026-06-28

## Current repository contents

- Current working directory: `/home/luot/27thesis`
- Existing task note: `instCodex/gem5.md`
- Benchmark paths found before setup: none
- gem5 scripts/configs found before setup: none

## Benchmark paths

- Created minimal benchmark source: `benchmarks/vadd/vadd.c`
- Planned first binary output: `build/vadd_N1024.riscv`

## RISC-V compiler

- `riscv64-unknown-linux-gnu-gcc`: not found in `PATH`
- `riscv64-linux-gnu-gcc`: not found in `PATH`
- `riscv64-unknown-elf-gcc`: not found in `PATH`

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
- `scons`: not found in `PATH`
- `sudo`: available, but non-interactive passwordless sudo is not enabled
- `python3 -m pip`: not available
- `python3 -m venv`: module exists, but `ensurepip` is unavailable until `python3.12-venv` is installed

## Missing items

- RISC-V Linux GNU toolchain
- host packages needed to build gem5 and create Python virtual environments
- built `gem5.opt`
- benchmark binaries
- gem5 run results

## Next step

1. Install host packages:

   ```bash
   sudo ./scripts/bootstrap_host_deps.sh
   ```

2. Compile the minimal benchmark:

   ```bash
   ./scripts/build_benchmarks.sh
   ```

3. Build gem5 for the RISCV target:

   ```bash
   cd tools/gem5
   scons build/RISCV/gem5.opt -j2
   ```

4. Add the minimal gem5 O3 no-prefetch run script after `gem5.opt` is available.
